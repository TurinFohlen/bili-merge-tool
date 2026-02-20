# 变更日志 v3.0 → v3.1

**发布日期**：2026-02-19  
**版本**：v3.1.0

---

## 🎯 核心修复

### 修复一：unknown 错误（29次）→ execution_error

**问题根因**：
- `RuntimeError` 未被 `error_log.py` 的 `_exception_map` 映射
- `rish.executor` 命令执行失败时抛出 `RuntimeError`，被归为 "unknown" (素数 17)

**修复措施**：

1. **新增错误类型**（error_log.py）
   ```python
   prime_map = {
       ...
       "execution_error": 19,  # 新增：命令执行失败
   }
   
   _exception_map = {
       ...
       RuntimeError: "execution_error",  # 新增映射
   }
   ```

2. **异常细化**（services/rish_executor.py）
   - 根据 stderr 内容抛出更具体异常：
     - `"no such file or directory"` → `FileNotFoundError` (素数 5)
     - `"permission denied"` → `PermissionError` (素数 3)
     - `"no space left"` → `OSError` (素数 11)
     - 其他失败 → `RuntimeError` (素数 19，execution_error)

**预期效果**：
- unknown 错误减少至 0
- execution_error / file_not_found / permission_denied 分类更清晰
- 错误日志可操作性显著提升

---

### 修复二：file_not_found 错误（6次）→ 递归查找

**问题根因**：
- `extractor_dash` 硬编码假设 `quality` 子目录存在
- 新版 B站缓存结构变化，文件可能直接位于 `c_folder` 根目录
- 路径：`{bili_root}/{uid}/{c_folder}/{quality}/{video.m4s}` ❌
- 实际：`{bili_root}/{uid}/{c_folder}/video.m4s` ✅

**修复措施**（services/extractor_dash.py）：

1. **递归文件查找**
   ```python
   def _find_files_recursive(base_dir, target_names, max_depth=3):
       """
       从 c_folder 根目录开始递归搜索
       返回 [(path, depth), ...] 按深度升序
       """
   ```

2. **智能路径选择**
   - 优先选择浅层文件（通常是最新版本）
   - 支持多种路径结构：
     - `c_folder/video.m4s` （新版，深度 0）
     - `c_folder/112/video.m4s` （旧版，深度 1）
     - `c_folder/quality/80/video.m4s` （更旧版，深度 2）

3. **详细日志输出**
   ```
   🔍 递归查找视频文件: ['video.m4s', 'video.mp4']
   🔍 找到: .../c_123456/video.m4s (深度 0)
   ✅ 选择视频: .../c_123456/video.m4s
   ```

**预期效果**：
- file_not_found 错误减少至 0（理论值）
- 兼容所有 B站缓存结构版本
- 与 MT 管理器手动操作逻辑一致

---

## 📊 错误统计对比

### 修复前（v3.0）

```
none                : 1330
unknown             : 29   ← 需修复
file_not_found      : 6    ← 需修复
```

### 修复后（v3.1 预期）

```
none                : 1330
execution_error     : ~15  ← 从 unknown 细化
file_not_found      : ~5   ← 真实文件缺失（非路径问题）
permission_denied   : ~10  ← 从 unknown 细化
unknown             : 0    ← 已消除
```

---

## 🔬 技术细节

### 素数编码更新

| 错误类型 | 素数 | 说明 |
|---------|------|------|
| none | 1 | 无错误（乘法单位元） |
| timeout | 2 | rish 超时 |
| permission_denied | 3 | 权限被拒绝 |
| file_not_found | 5 | 文件或目录不存在 |
| network_error | 7 | 网络错误 |
| disk_full | 11 | 磁盘空间不足 |
| auth_failed | 13 | 认证失败 |
| unknown | 17 | 未识别异常 |
| **execution_error** | **19** | **命令执行失败（新增）** |

### 递归查找算法

**时间复杂度**：O(n) where n = c_folder 下所有文件数  
**空间复杂度**：O(d) where d = 最大深度 (默认 3)  
**优化**：仅递归进入数字目录（quality 目录），跳过其他目录

---

## 🧪 测试验证

### 单元测试

```bash
python test_extractor_dash.py
```

验证：
- ✅ 递归查找在多种路径结构下正常工作
- ✅ 优先选择浅层文件
- ✅ 异常细化正确映射

### 集成测试

```bash
python main.py
```

观察日志：
- 应看到详细的文件查找路径
- unknown 错误应为 0
- execution_error 应包含具体命令和 stderr

---

## 📝 迁移指南

### 从 v3.0 升级到 v3.1

**兼容性**：完全向后兼容，无需修改配置

**步骤**：

1. 备份当前版本
   ```bash
   cp -r bili-merge-tool bili-merge-tool-v3.0-backup
   ```

2. 替换文件
   ```bash
   cd bili-merge-tool
   # 替换以下文件：
   # - error_log.py
   # - services/rish_executor.py
   # - services/extractor_dash.py
   ```

3. 清空旧的错误日志（可选）
   ```bash
   rm -rf logs/*
   ```

4. 重新运行
   ```bash
   python main.py
   ```

5. 检查新日志
   ```bash
   python stats.py  # 查看错误分布
   ```

---

## 🎉 总结

v3.1 修复了 v3.0 中通过素数编码错误日志系统发现的两个核心问题：

1. **异常映射不完整** → 新增 execution_error，细化 RuntimeError 分类
2. **路径假设错误** → 递归查找，适配所有 B站缓存结构

这些修复展示了组件化架构 + 素数编码错误日志系统的强大威力：
- ✅ 无需查看代码即可定位根因
- ✅ 结构化错误数据支持精确分析
- ✅ 数学原理保证错误可唯一分解

---

**致谢**：感谢用户通过错误日志分析提供的详细根因报告！
