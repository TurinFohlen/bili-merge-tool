# 快速开始指南

---

## 1. 环境准备

### 必需软件

1. **Termux**（终端模拟器）
2. **Shizuku**（系统级权限管理）
3. **Python 3**
4. **ffmpeg**

```bash
# 在 Termux 中安装
pkg update
pkg install python ffmpeg
```

### Shizuku 配置

1. 在 Shizuku 应用中启动服务
2. 授权 Termux 使用 Shizuku
3. 导出 rish 文件到 Termux

```bash
# 在 Termux 中
mkdir -p ~/shizuku-rish
# 将 rish 文件复制到此目录
chmod +x ~/shizuku-rish/rish
```

---

## 2. 安装工具

### 解压文件

```bash
cd ~
unzip bili_merge_tool_v3.0_componentized.zip -d bili-merge-tool
cd bili-merge-tool
```

### 修改配置（可选）

编辑 `config.ini`：

```ini
[paths]
rish_path = /data/data/com.termux/files/home/shizuku-rish/rish
bili_root = /storage/emulated/0/Android/data/tv.danmaku.bili/download
output_dir = /storage/emulated/0/Download/B站视频
```

---

## 3. 运行测试

### 测试组件系统

```bash
python test_components.py
```

预期输出：
```
✅ 共注册 12 个组件
✅ 依赖注入正常
✅ 所有测试通过！
```

### 测试错误日志

```bash
python test_error_log.py
```

预期输出：
```
✅ 错误日志测试完成！
📁 日志位置: /tmp/bili_error_test_xxx
```

---

## 4. 开始使用

### 批量处理视频

```bash
python main.py
```

程序流程：
1. ✅ 扫描并注册组件
2. ✅ 检查环境（rish + ffmpeg）
3. ℹ️  扫描 B站缓存...
4. ℹ️  处理 UID [1/3]: 123456789
5. ✅ 合并成功: 测试视频.mp4
6. 📊 导出错误日志...

### 导出视频（可选）

程序结束时会询问：

```
是否导出已合并的视频? (y/n): y
请输入导出目标路径: /sdcard/Movies
✅ 导出完成: 成功 10，失败 0
```

---

## 5. 查看错误日志

### 日志位置

```
/storage/emulated/0/Download/B站视频/logs/
├── adjacency_matrix_20260219_035720.json
├── adjacency_matrix_20260219_035720.wl
├── error_events_20260219_035720.json
└── error_events_20260219_035720.wl
```

### 在 Mathematica 中分析

```wolfram
(* 加载数据 *)
SetDirectory["/path/to/logs/"]
Get["adjacency_matrix_20260219_035720.wl"]
Get["error_events_20260219_035720.wl"]

(* 查看组件依赖图 *)
g = AdjacencyGraph[staticDepA, 
  VertexLabels -> Table[i -> nodes[[i]], {i, n}],
  VertexSize -> Medium,
  GraphLayout -> "LayeredDigraphEmbedding"]

(* 分析错误传播 *)
receivedError = Table[Total[Normal[errorTensor][[All, j, All]], 2], {j, n}]
BarChart[receivedError, 
  ChartLabels -> nodes,
  ChartStyle -> "Rainbow",
  PlotLabel -> "各组件接收到的错误量"]

(* 找出问题组件 *)
problemComponents = nodes[[Ordering[receivedError, -5]]]
Print["错误最多的 5 个组件: ", problemComponents]
```

---

## 6. 常见问题

### Q: rish 命令超时

**A:** 检查电池优化设置

```bash
# 1. 关闭 Shizuku 的电池优化
# 2. 关闭 Termux 的电池优化
# 3. 在 config.ini 中增加 max_retries
```

### Q: ffmpeg 合并失败

**A:** 检查 ffmpeg 版本

```bash
ffmpeg -version
# 确保版本 >= 4.0
```

### Q: 文件名过长错误（Errno 36）

**A:** 工具已自动按字节截断，无需手动处理

---

## 7. 进阶使用

### 添加自定义组件

创建新文件 `services/my_service.py`：

```python
from registry import registry

@registry.register("my.service", "service", "do_work() -> None")
class MyService:
    def do_work(self):
        print("我的自定义服务")
```

重新运行 `python main.py`，组件会自动加载并获得：
- ✅ 依赖追踪
- ✅ 错误日志记录
- ✅ 调用链可视化

### 自定义错误类型

编辑 `error_log.py`：

```python
# 在 prime_map 中添加新类型
prime_map = {
    # ... 现有映射 ...
    "custom_error": 19,  # 分配新素数
}

# 在 _exception_map 中映射异常
_exception_map = {
    # ... 现有映射 ...
    MyCustomException: "custom_error",
}
```

---

## 8. 获取帮助

- **文档**：`README_v3.md`（完整功能说明）
- **架构**：`ARCHITECTURE_COMPARISON.md`（v2.3 vs v3.0）
- **Issues**：GitHub Issues 或社区论坛

---

## 9. 卸载

```bash
cd ~
rm -rf bili-merge-tool
```

配置文件和输出视频不会被删除。

---

**享受组件化架构带来的强大可观测性！** 🚀
