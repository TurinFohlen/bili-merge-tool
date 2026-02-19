# B站缓存视频合并工具 v3.0

**组件化架构 + 素数编码错误日志系统**

---

## 架构升级亮点

### 1. 组件注册中心
- 所有功能模块化为独立组件
- 自动依赖追踪和注入
- 运行时调用链完整记录

### 2. 素数编码错误日志
- **唯一性保证**：每种错误类型映射到唯一素数
- **可逆分解**：复合错误值 = 素数乘积，基于算术基本定理可唯一还原
- **线性化**：对数变换后 log(p1·p2) = log(p1)+log(p2)，便于张量分析

### 3. 多格式导出
- **JSON 格式**：便于程序消费
- **Wolfram Language 格式**：直接导入 Mathematica 进行高级分析

---

## 目录结构

```
bili-merge-tool/
├── main.py                    # 启动入口
├── loader.py                  # 组件自动加载器
├── registry.py                # 组件注册中心
├── error_log.py               # 素数编码错误日志系统
├── config.ini                 # 配置文件
├── services/                  # 服务组件
│   ├── rish_executor.py       # rish 命令执行（带重试）
│   ├── file_operator.py       # 文件操作（分片复制）
│   ├── bili_scanner.py        # B站缓存扫描
│   ├── bili_entry_reader.py   # entry.json 读取
│   ├── bili_format_detector.py # 格式检测（DASH/MP4/BLV）
│   ├── extractor_dash.py      # DASH 格式提取
│   ├── extractor_blv.py       # BLV 格式提取
│   ├── merger_ffmpeg.py       # ffmpeg 合并
│   └── progress_manager.py    # 进度管理
├── processors/                # 处理器组件
│   └── video_processor.py     # 视频处理编排
├── uis/                       # 用户界面组件
│   └── cli_main.py            # 命令行界面
└── exporters/                 # 导出组件
    └── local_exporter.py      # 本地导出
```

---

## 使用方法

### 基础使用

```bash
python main.py
```

程序会自动：
1. 扫描并注册所有组件
2. 检查环境（rish + ffmpeg）
3. 扫描 B站缓存目录
4. 批量处理视频
5. 导出错误日志（JSON + Wolfram）

### 配置文件

编辑 `config.ini` 修改：
- 路径配置（rish_path, bili_root, output_dir）
- 重试策略（max_retries, retry_delay）
- 分片阈值（chunk_threshold, chunk_size）
- 日志级别（log_level）

---

## 错误日志分析

### 导出文件

程序结束后会生成 4 个文件（位于 `/storage/emulated/0/Download/B站视频/logs`）：

1. `adjacency_matrix_<timestamp>.json` - 静态依赖矩阵（JSON）
2. `error_events_<timestamp>.json` - 错误事件列表（JSON）
3. `adjacency_matrix_<timestamp>.wl` - 静态依赖矩阵（Wolfram）
4. `error_events_<timestamp>.wl` - 错误事件列表（Wolfram）

### 在 Mathematica 中分析

```wolfram
(* 加载数据 *)
Get["adjacency_matrix_20260219_035720.wl"]
Get["error_events_20260219_035720.wl"]

(* 查看组件依赖图 *)
AdjacencyGraph[staticDepA, VertexLabels -> Table[i -> nodes[[i]], {i, n}]]

(* 分析错误传播 *)
receivedError = Table[Total[Normal[errorTensor][[All, j, All]], 2], {j, n}]
producedError = Table[Total[Normal[errorTensor][[i, All, All]], 2], {i, n}]

(* 找出错误最多的组件 *)
Ordering[receivedError, -5]  (* 接收错误最多的 5 个组件 *)
Ordering[producedError, -5]  (* 产生错误最多的 5 个组件 *)

(* 张量分解（找出错误模式）*)
{u, s, v} = SingularValueDecomposition[Flatten[Normal[errorTensor], {{1, 2}, {3}}]]
ListPlot[Diagonal[s], PlotLabel -> "错误奇异值分布"]
```

### 素数编码示例

```python
# 错误类型 → 素数映射
{
    "none": 1,              # 无错误（乘法单位元）
    "timeout": 2,
    "permission_denied": 3,
    "file_not_found": 5,
    "network_error": 7,
    "disk_full": 11,
    "auth_failed": 13,
    "unknown": 17
}

# 复合错误计算
# 如果一次调用同时触发 timeout(2) 和 file_not_found(5)
composite_value = 2 * 5 = 10
log_value = log(10) = log(2) + log(5) = 2.302...

# 反向解码（唯一分解定理）
10 = 2 × 5  →  ["timeout", "file_not_found"]
```

---

## 测试

### 运行组件系统测试

```bash
python test_components.py
```

验证：
- 组件自动加载
- 依赖注入
- 服务调用

### 运行错误日志测试

```bash
python test_error_log.py
```

验证：
- 嵌套调用记录
- 异常捕获和映射
- 日志导出（4 个文件）

---

## 技术细节

### 组件自动包装

注册中心在组件注册时自动包装所有公共方法：

```python
@registry.register("my.service", "service", "...")
class MyService:
    def method(self):
        # 自动进入 component_context
        # 调用其他组件时自动记录依赖
        other = registry.get_service("other.service")
        other.do_something()  # 自动记录：my.service → other.service
```

### 错误日志自动记录

在 `component_context` 退出时：

```python
# 正常路径：记录 caller → callee + ["none"]
# 异常路径：记录 caller → callee + [exception_to_error(exc)]
record_event(caller, callee, error_set, components)
```

### CSR 稀疏矩阵

依赖矩阵用 CSR（Compressed Sparse Row）格式存储：

```python
{
    'data': [1, 1, 1, ...],        # 边权重（全为 1）
    'indices': [2, 5, 7, ...],     # 列索引
    'row_ptrs': [0, 2, 5, 8, ...]  # 行指针（累积和）
}
```

优势：
- 内存高效（仅存储非零元素）
- 快速行切片
- Mathematica `SparseArray` 原生支持

---

## 收益总结

1. **统一可观测性**：完整调用链，无盲区
2. **结构化错误日志**：素数编码 → 唯一分解 → 张量分析
3. **自动化分析**：Wolfram 格式 → Mathematica → 高级可视化
4. **低侵入性**：基于装饰器和上下文管理器，业务代码无感知
5. **可扩展性**：新增组件自动获得日志能力

---

## 许可证

MIT License - 参见 `LICENSE` 文件

---

## 致谢

- 组件架构灵感来自 dependency injection 设计模式
- 素数编码错误日志系统受 Gödel numbering 启发
- CSR 稀疏矩阵来自 SciPy 的 `scipy.sparse.csr_matrix`
