# WebSocket 持久化连接设计方案

**版本**：v1.0 (实验性)  
**目标**：解决Shizuku连接不稳定问题，同时避免BV号混淆

---

## 问题背景

### Shizuku 稳定性测试结果

```python
# 测试序列长度 L=2，每种序列重复10次
理论预期：全1序列（stdout）
实际结果：
  00: 9 次   ← stderr, stderr
  01: 13 次  ← stderr, stdout
  10: 4 次   ← stdout, stderr
  11: 12 次  ← stdout, stdout (仅30%正确)
  ?1: 2 次   ← timeout/unknown

结论：Shizuku 进程模式连接具有高度随机性
```

### 当前方案（v3.1.1）

**进程模式 + 递归重试**：
- 每次命令创建新进程
- 失败后指数退避重试（最多100次）
- 稳定但效率低

**问题**：
- 大量重试导致处理时间长
- 每次新建进程开销大
- 连接不稳定的根本原因未解决

---

## WebSocket 方案探索

### 双窗口方案的问题

**现象**：BV号混淆
- 窗口A处理视频1，窗口B处理视频2
- 响应可能被错误分配（窗口A收到视频2的响应）

**根因**：
- WebSocket 是全双工通信，无法区分响应属于哪个请求
- 双窗口并发时，响应顺序不保证

---

## 设计方案：分时复用 + 请求ID

### 核心思想

1. **单连接**：全局仅一个WebSocket连接
2. **请求ID**：每个命令附带唯一ID
3. **响应匹配**：根据ID匹配请求和响应
4. **串行处理**：同时只处理一个命令（避免混淆）

### 架构图

```
┌─────────────────────────────────────────────────┐
│           Python 主程序（客户端）                │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │   WebSocketManager (单例)                │  │
│  │   - 维持持久连接                          │  │
│  │   - 分配请求ID                            │  │
│  │   - 匹配响应                              │  │
│  └──────────────────────────────────────────┘  │
│                    ↕ (WebSocket)               │
├─────────────────────────────────────────────────┤
│        WebSocket 服务端（Node.js/Python）        │
├─────────────────────────────────────────────────┤
│                    ↕ (rish)                    │
├─────────────────────────────────────────────────┤
│              Shizuku / Android Shell            │
└─────────────────────────────────────────────────┘
```

### 协议设计

#### 请求格式（JSON）

```json
{
  "id": "req_1234567890",
  "command": "cat /path/to/entry.json",
  "timeout": 30
}
```

#### 响应格式（JSON）

```json
{
  "id": "req_1234567890",
  "returncode": 0,
  "stdout": "{...}",
  "stderr": "",
  "duration": 0.123
}
```

---

## 实现方案

### 方案 1：完全串行（推荐，最稳定）

**特点**：
- 同时只处理一个命令
- 无需复杂的并发控制
- 响应匹配简单

**实现**：

```python
class WebSocketManager:
    def __init__(self):
        self.ws = None
        self.lock = threading.Lock()
        self.pending_requests = {}
        self.request_id = 0
    
    async def connect(self):
        """建立持久连接"""
        self.ws = await websockets.connect("ws://localhost:8080")
        asyncio.create_task(self._listen())
    
    async def _listen(self):
        """监听响应"""
        async for message in self.ws:
            data = json.loads(message)
            req_id = data['id']
            if req_id in self.pending_requests:
                future = self.pending_requests.pop(req_id)
                future.set_result(data)
    
    async def exec(self, command: str, timeout: int = 30) -> tuple:
        """串行执行命令（带锁）"""
        with self.lock:  # 确保串行
            req_id = f"req_{self.request_id}"
            self.request_id += 1
            
            # 创建Future等待响应
            future = asyncio.Future()
            self.pending_requests[req_id] = future
            
            # 发送请求
            await self.ws.send(json.dumps({
                'id': req_id,
                'command': command,
                'timeout': timeout
            }))
            
            # 等待响应
            try:
                response = await asyncio.wait_for(future, timeout=timeout+5)
                return response['returncode'], response['stdout'], response['stderr']
            except asyncio.TimeoutError:
                self.pending_requests.pop(req_id, None)
                raise TimeoutError(f"WebSocket 超时: {command[:80]}")
```

### 方案 2：分时复用（并发优化版）

**特点**：
- 允许多个命令并发发送
- 通过请求ID匹配响应
- 复杂度较高，但效率更好

**实现**：

```python
class WebSocketManager:
    async def exec(self, command: str, timeout: int = 30) -> tuple:
        """并发执行（无锁）"""
        req_id = f"req_{uuid.uuid4().hex}"
        
        future = asyncio.Future()
        self.pending_requests[req_id] = future
        
        await self.ws.send(json.dumps({
            'id': req_id,
            'command': command,
            'timeout': timeout
        }))
        
        try:
            response = await asyncio.wait_for(future, timeout=timeout+5)
            return response['returncode'], response['stdout'], response['stderr']
        except asyncio.TimeoutError:
            self.pending_requests.pop(req_id, None)
            raise TimeoutError(f"WebSocket 超时: {command[:80]}")
```

---

## WebSocket 服务端（Node.js 示例）

```javascript
const WebSocket = require('ws');
const { spawn } = require('child_process');

const wss = new WebSocket.Server({ port: 8080 });

wss.on('connection', (ws) => {
  console.log('Client connected');
  
  ws.on('message', (message) => {
    const { id, command, timeout } = JSON.parse(message);
    
    // 执行 rish 命令
    const rish = spawn('/sdcard/shizuku-rish/rish', ['-c', command], {
      env: { RISH_APPLICATION_ID: 'ru.iiec.pydroid3' }
    });
    
    let stdout = '';
    let stderr = '';
    const startTime = Date.now();
    
    rish.stdout.on('data', (data) => {
      stdout += data.toString();
    });
    
    rish.stderr.on('data', (data) => {
      stderr += data.toString();
    });
    
    rish.on('close', (code) => {
      const duration = (Date.now() - startTime) / 1000;
      
      // 返回响应（带上请求ID）
      ws.send(JSON.stringify({
        id: id,  // 关键：返回请求ID
        returncode: code,
        stdout: stdout,
        stderr: stderr,
        duration: duration
      }));
    });
    
    // 超时处理
    setTimeout(() => {
      rish.kill();
      ws.send(JSON.stringify({
        id: id,
        returncode: -1,
        stdout: '',
        stderr: 'Timeout',
        duration: timeout
      }));
    }, timeout * 1000);
  });
});
```

---

## 优势对比

| 维度 | 进程模式（v3.1.1） | WebSocket串行 | WebSocket并发 |
|------|-------------------|--------------|--------------|
| 稳定性 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 效率 | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 复杂度 | ⭐⭐⭐⭐⭐（简单） | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| BV号混淆 | 不会 | 不会 | 不会（ID匹配） |
| 连接开销 | 高（每次新建） | 低（持久） | 低（持久） |

---

## 实施计划

### 阶段 1：原型验证（1-2天）

1. 实现简单的Node.js WebSocket服务端
2. 实现Python WebSocketManager（串行版）
3. 测试稳定性（运行Shizuku稳定性测试）

### 阶段 2：集成到工具（2-3天）

1. 创建 `services/rish_executor_ws.py`
2. 保留进程模式作为后备
3. 配置文件添加 `use_websocket` 开关

### 阶段 3：性能优化（可选）

1. 实现并发版（如果串行版稳定）
2. 连接池管理
3. 断线重连机制

---

## 回退策略

**如果WebSocket方案不稳定**：
- 保留进程模式作为默认
- WebSocket作为实验性功能
- 用户可通过配置切换

---

## 测试指标

### 稳定性测试

```bash
# 运行 Shizuku 稳定性测试
python shizuku_stability_test.py

# 目标：
# - 全1序列比例 >80% （vs 当前30%）
# - 超时/?序列 <5% （vs 当前5%）
```

### 性能测试

```bash
# 处理100个视频
time python main.py

# 目标：
# - 总时间 <50% 进程模式
# - 成功率 ≥ 进程模式
```

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| WebSocket服务端崩溃 | 中 | 高 | 自动重启 + 后备进程模式 |
| 响应ID混淆 | 低 | 高 | 充分测试 + UUID保证唯一性 |
| 连接断开 | 中 | 中 | 断线重连 + 请求重试 |

---

## 结论

**推荐方案**：WebSocket 串行模式
- 稳定性高（避免并发冲突）
- 实现简单（无需复杂锁）
- 效率提升显著（持久连接）

**实施建议**：
1. 先实现串行版并充分测试
2. 确认稳定后再考虑并发优化
3. 保留进程模式作为后备

---

**下一步**：创建原型并进行稳定性测试 🚀
