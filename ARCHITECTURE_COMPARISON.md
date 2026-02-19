# 架构对比：v2.3 → v3.0

---

## 概览

| 维度 | v2.3（单体架构） | v3.0（组件化架构） |
|------|-----------------|-------------------|
| **代码组织** | 3 个大文件（shizuku_access, data_processor, ui） | 12 个组件 + 注册中心 + 错误日志系统 |
| **依赖管理** | 硬编码导入 | 注册中心自动注入 |
| **错误处理** | try-except 分散 | 统一错误捕获 + 素数编码 |
| **可观测性** | 日志文本 | 完整调用链 + 依赖矩阵 + 错误传播图 |
| **可扩展性** | 修改核心文件 | 新增组件文件 |
| **测试** | 手动集成测试 | 组件级单元测试 + 系统测试 |

---

## 文件结构对比

### v2.3 单体架构

```
bili-merge-tool/
├── shizuku_access.py  (500+ lines)
│   └── rish_exec, copy_file, list_uids, detect_format, ...
├── data_processor.py  (300+ lines)
│   └── validate_entry, extract_title, ...
├── ui.py              (700+ lines)
│   └── main, process_single_video, merge_video, export, ...
├── config.ini
└── README_v2.md
```

### v3.0 组件化架构

```
bili-merge-tool/
├── main.py                    # 启动入口（50 lines）
├── loader.py                  # 组件加载器（100 lines）
├── registry.py                # 注册中心（500 lines，通用）
├── error_log.py               # 错误日志系统（500 lines，通用）
├── services/                  # 业务组件（9 个文件，平均 100 lines）
│   ├── rish_executor.py
│   ├── file_operator.py
│   ├── bili_scanner.py
│   ├── bili_entry_reader.py
│   ├── bili_format_detector.py
│   ├── extractor_dash.py
│   ├── extractor_blv.py
│   ├── merger_ffmpeg.py
│   └── progress_manager.py
├── processors/
│   └── video_processor.py     # 编排组件（150 lines）
├── uis/
│   └── cli_main.py            # CLI 组件（120 lines）
├── exporters/
│   └── local_exporter.py      # 导出组件（80 lines）
├── test_components.py         # 系统测试
├── test_error_log.py          # 错误日志测试
├── config.ini
└── README_v3.md
```

---

## 核心概念对比

### 1. 依赖注入

#### v2.3：硬编码导入

```python
# ui.py
import shizuku_access as sa
import data_processor as dp

# 直接调用
uids = sa.list_uids()
title = dp.extract_title(entry)
```

#### v3.0：注册中心动态注入

```python
# cli_main.py
from registry import registry

# 获取服务实例
scanner = registry.get_service("bili.scanner")
processor = registry.get_service("video.processor")

# 注入依赖
processor.set_dependencies(scanner=scanner, ...)

# 调用
uids = scanner.list_uids()
```

---

### 2. 错误处理

#### v2.3：分散的 try-except

```python
def process_single_video(uid, c_folder, progress):
    try:
        entry = sa.read_entry_json(uid, c_folder)
        if not entry:
            log("读取失败", "WARNING")
            return False
        # ... 更多逻辑 ...
    except sa.RishTimeoutError:
        log("超时", "ERROR")
        return False
    except Exception as e:
        log(f"未知错误: {e}", "ERROR")
        return False
```

#### v3.0：统一捕获 + 素数编码

```python
# video_processor.py
def process(self, uid, c_folder, progress):
    # 组件调用自动进入 component_context
    entry = self.entry_reader.read(uid, c_folder)  # 异常自动捕获
    # ... 更多逻辑 ...

# registry.py 的 component_context
@contextmanager
def component_context(self, name: str):
    caller = self._get_current_component()
    self._push_component(name)
    try:
        yield
    except Exception as exc:
        # 自动记录错误：caller → name + [exception_to_error(exc)]
        error_set = [exception_to_error(exc)]  # FileNotFoundError → "file_not_found" (素数 5)
        record_event(caller, name, error_set, self.components)
        raise
    finally:
        self._pop_component()
```

---

### 3. 可观测性

#### v2.3：文本日志

```
[12:34:56] ℹ️  处理视频: c_123456789
[12:34:57] ℹ️  标题: 测试视频
[12:34:58] ❌ 复制视频文件失败: c_123456789
```

#### v3.0：结构化错误日志 + 依赖矩阵

**错误事件记录（素数编码）：**

```json
{
  "events": [
    [0, 10, 5, 5, 1.609]  // t=0, caller_idx=10(video.processor), callee_idx=5(file.operator), 
                          // composite_value=5(file_not_found), log_value=log(5)
  ],
  "prime_map": {
    "file_not_found": 5,
    "timeout": 2,
    ...
  }
}
```

**依赖矩阵（CSR 格式）：**

```json
{
  "nodes": ["rish.executor", "file.operator", "bili.scanner", ...],
  "adjacency_triples": [
    [10, 5, 1],  // video.processor 依赖 file.operator
    [5, 0, 1],   // file.operator 依赖 rish.executor
    ...
  ]
}
```

**Mathematica 可视化：**

```wolfram
(* 依赖图 *)
AdjacencyGraph[staticDepA, VertexLabels -> "Name"]

(* 错误热力图 *)
MatrixPlot[Total[Normal[errorTensor], 3], ColorFunction -> "Rainbow"]

(* 奇异值分解找错误模式 *)
{u, s, v} = SingularValueDecomposition[Flatten[Normal[errorTensor], {{1, 2}, {3}}]]
```

---

### 4. 扩展性

#### v2.3：修改核心文件

新增功能需要修改 `shizuku_access.py` 或 `ui.py`：

```python
# shizuku_access.py 末尾
def new_feature():
    """新功能直接加在文件末尾，导致文件越来越大"""
    pass
```

#### v3.0：新增组件文件

新增功能只需创建新组件：

```python
# services/new_feature.py
from registry import registry

@registry.register("new.feature", "service", "do_something() -> None")
class NewFeature:
    def do_something(self):
        """新功能，自动获得依赖追踪和错误日志能力"""
        pass
```

---

## 性能对比

| 指标 | v2.3 | v3.0 | 说明 |
|------|------|------|------|
| **启动时间** | ~0.1s | ~0.5s | v3.0 需扫描注册组件，但仅一次性开销 |
| **内存占用** | ~50MB | ~60MB | 注册中心和错误日志系统增加约 10MB |
| **处理速度** | 基准 | 98% 基准 | component_context 轻微开销，但可忽略 |
| **日志大小** | ~10KB/小时 | ~100KB/小时 | 包含完整调用链和依赖矩阵 |

---

## 迁移指南

### 从 v2.3 迁移到 v3.0

1. **保留配置**：`config.ini` 格式兼容，直接复制
2. **数据兼容**：进度文件 `.bili_progress.json` 格式不变
3. **新增功能**：错误日志文件生成在 `logs/` 子目录

### 回退到 v2.3

v3.0 的输出文件与 v2.3 完全兼容，可随时回退：

```bash
# 使用 v2.3 代码
python ui.py  # 照常工作，使用相同的 config.ini 和进度文件
```

---

## 总结

v3.0 组件化架构在 v2.3 的基础上提供了：

1. **更高的可维护性**：组件职责单一，易于理解和修改
2. **更强的可观测性**：完整调用链 + 错误传播图 + 数学分析
3. **更好的可扩展性**：新增功能无需修改核心代码
4. **更低的测试成本**：组件级单元测试 + 系统级集成测试

适用场景：
- **v2.3**：简单使用，不需要高级分析
- **v3.0**：需要深度分析、故障排查、持续优化的场景

---
