# 升级指南：v3.0 → v3.1

---

## 升级概述

**v3.1.0** 基于素数编码错误日志系统的分析，修复了两个核心问题：
- ✅ unknown 错误（29次）→ 新增 execution_error 类型
- ✅ file_not_found 错误（6次）→ 采用递归查找策略

**兼容性**：完全向后兼容，无需修改配置文件

---

## 快速升级

### 方法 1：直接替换（推荐）

```bash
cd bili-merge-tool

# 备份当前版本
cp error_log.py error_log.py.v3.0.bak
cp services/rish_executor.py services/rish_executor.py.v3.0.bak
cp services/extractor_dash.py services/extractor_dash.py.v3.0.bak

# 从 GitHub 拉取最新版本
git pull origin main

# 验证修复
python test_v3.1_fixes.py
```

### 方法 2：手动替换文件

下载以下三个文件并替换：
1. `error_log.py`
2. `services/rish_executor.py`
3. `services/extractor_dash.py`

---

## 核心修改内容

### 1. error_log.py

**新增错误类型**：
```python
prime_map = {
    ...
    "execution_error": 19,  # 新增：命令执行失败
}
```

**新增异常映射**：
```python
_exception_map = {
    ...
    RuntimeError: "execution_error",  # 新增
}
```

### 2. services/rish_executor.py

**异常细化逻辑**：
```python
def exec(self, command: str, ...) -> Tuple[int, str, str]:
    if check and result.returncode != 0:
        stderr_lower = result.stderr.lower()
        
        # 根据 stderr 抛出具体异常
        if "no such file or directory" in stderr_lower:
            raise FileNotFoundError(...)
        elif "permission denied" in stderr_lower:
            raise PermissionError(...)
        elif "no space left" in stderr_lower:
            raise OSError(...)
        else:
            raise RuntimeError(...)  # execution_error
```

### 3. services/extractor_dash.py

**新增递归查找方法**：
```python
def _find_files_recursive(base_dir, target_names, max_depth=3):
    """
    从 c_folder 根目录递归搜索视频文件
    返回 [(path, depth), ...] 按深度升序
    """
```

**修改路径构造策略**：
- ❌ 旧版：`base = f"{bili_root}/{uid}/{c_folder}/{quality}"`
- ✅ 新版：`base = f"{bili_root}/{uid}/{c_folder}"` + 递归查找

---

## 验证修复

### 运行测试

```bash
python test_v3.1_fixes.py
```

预期输出：
```
✅ 所有 v3.1 修复验证测试通过！

修复总结：
  1. ✅ RuntimeError → execution_error (素数 19)
  2. ✅ rish_executor 异常细化（4 种类型）
  3. ✅ extractor_dash 递归查找（深度优先）
  4. ✅ 素数编码完整性（9 种错误类型）
  5. ✅ 复合错误编解码正常

预期效果：
  · unknown 错误: 29 → 0
  · file_not_found 错误: 6 → ~0
  · execution_error 错误: 0 → ~15-20
```

### 检查错误日志

升级后重新运行 `main.py`，然后查看错误统计：

```bash
python main.py
python stats.py  # 如果你有这个脚本
```

预期结果：
```
错误类型统计：
  none                : XXXX
  execution_error     : ~15-20  ← 从 unknown 细化而来
  file_not_found      : ~0-2    ← 大幅减少
  permission_denied   : ~5-10   ← 从 unknown 细化而来
  timeout             : ...
  unknown             : 0       ← 应为 0
```

---

## 回滚方法

如果升级后出现问题，可快速回滚：

```bash
cd bili-merge-tool

# 恢复备份文件
mv error_log.py.v3.0.bak error_log.py
mv services/rish_executor.py.v3.0.bak services/rish_executor.py
mv services/extractor_dash.py.v3.0.bak services/extractor_dash.py

# 或使用 git
git checkout de2ef75~1  # v3.0 的最后一个提交
```

---

## 常见问题

### Q1: 升级后 unknown 错误仍然很多？

**A**: 检查 `error_log.py` 是否正确更新：
```bash
grep "execution_error" error_log.py
# 应显示: "execution_error": 19,
```

### Q2: file_not_found 错误没有减少？

**A**: 检查 `extractor_dash.py` 是否包含 `_find_files_recursive` 方法：
```bash
grep "_find_files_recursive" services/extractor_dash.py
# 应显示方法定义
```

### Q3: 如何确认修复生效？

**A**: 查看日志中是否出现递归查找的输出：
```
🔍 递归查找视频文件: ['video.m4s', 'video.mp4']
🔍 找到: .../c_folder/video.m4s (深度 0)
✅ 选择视频: .../c_folder/video.m4s
```

---

## 技术细节

### 素数编码更新

| 错误类型 | 素数 | 来源 |
|---------|------|------|
| none | 1 | 无错误 |
| timeout | 2 | subprocess.TimeoutExpired |
| permission_denied | 3 | PermissionError |
| file_not_found | 5 | FileNotFoundError |
| network_error | 7 | ConnectionError |
| disk_full | 11 | OSError (磁盘满) |
| auth_failed | 13 | 认证失败 |
| unknown | 17 | 未识别异常 |
| **execution_error** | **19** | **RuntimeError (新增)** |

### 递归查找优先级

1. **深度 0**：`c_folder/video.m4s` （新版，优先）
2. **深度 1**：`c_folder/112/video.m4s` （旧版）
3. **深度 2**：`c_folder/quality/80/video.m4s` （更旧版）

算法自动选择最浅层文件，符合 "最新版本优先" 的直觉。

---

## 相关文档

- **CHANGELOG_v3.1.md** - 完整变更日志
- **test_v3.1_fixes.py** - 修复验证测试
- **README_v3.md** - 完整功能说明

---

**升级后记得清空旧日志以观察新的错误分布！** 🚀
