频位于 `c_folder/112/video.m4s` (深度1)，二次递归从 `c_folder` 根目录开始，可能因为深度限制或子目录筛选错过同目录的 `audio.m4s`

**解决方案**（services/extractor_dash.py）：

```python
# ❌ 旧版：二次全局递归（可能错过同目录音频）
audio_candidates = self._find_files_recursive(base, a_names, max_depth=3)

# ✅ 新版：找到视频后，直接在视频所在目录搜索音频
video_dir = os.path.dirname(video_src)
a_names = ["audio.m4s", "audio.mp4", "audio.m4a", "audio.mp3"]
for a_name in a_names:
    candidate = f"{video_dir}/{a_name}"
    if self.file_operator.check_exists(candidate):
        audio_src = candidate
        break
```

**改进点**：
1. 避免二次递归可能的深度/过滤问题
2. 扩展音频文件名列表（新增 .m4a, .mp3）
3. 直接在视频目录搜索，逻辑更直观

**预期效果**：
- 音频遗漏错误大幅减少
- 与MT管理器手动操作逻辑一致

---

### 修复 2：entry.json 容错增强

**问题根因**：
- 大量 entry.json 为**空文件**或**格式错误**（数据层面问题，程序无法修复）
- 旧版虽然跳过了，但错误分类不清晰

**解决方案**（services/bili_entry_reader.py）：

1. **内容校验**
   ```python
   # 检查是否为空
   if not out or not out.strip():
       print(f"  ⚠️  entry.json 为空文件（数据缺失）: {c_folder}")
       return None
   
   # 基础格式校验
   if not out.startswith('{'):
       print(f"  ⚠️  entry.json 格式异常（非JSON）: {c_folder}")
       return None
   ```

2. **错误分类统计**
   ```python
   self.stats = {
       'empty_file': 0,      # 空文件
       'invalid_json': 0,    # JSON格式错误
       'missing_file': 0,    # 文件不存在
       'other_error': 0,     # 其他错误
   }
   ```

3. **统计输出**（程序结束时）
   ```
   entry.json 错误分类统计：
     · 空文件（数据缺失）：15
     · JSON 格式错误：3
     · 文件不存在：2
     · 其他错误：1
     总计：21
   ```

**改进点**：
- 更友好的错误提示（区分空文件、格式错误、不存在）
- 统计输出帮助用户理解失败分布
- 为未来可能的数据修复提供依据

---

## 📊 预期改进效果

### 修复前（v3.1.0）

```
71个视频仅成功1个（成功率 1.4%）
主要失败原因：
  - 音频文件遗漏（即使同目录）
  - entry.json 错误（无明确分类）
```

### 修复后（v3.1.1 预期）

```
成功率预期提升至 30-50%（音频优化后）
失败原因更清晰：
  - entry.json 空文件（数据缺失，无法修复）：X%
  - 视频文件不存在（数据缺失）：Y%
  - 真实错误（需进一步调查）：Z%
```

---

## 🧪 验证方法

### 运行测试

```bash
python main.py
```

观察日志：
1. 应看到更多成功合并的视频
2. 音频查找日志应显示：
   ```
   🔍 在视频目录 112/ 直接搜索音频: ['audio.m4s', 'audio.mp4', 'audio.m4a', 'audio.mp3']
   ✅ 选择音频: .../112/audio.m4s
   ```
3. 程序结束时应显示 entry.json 错误统计

### 对比v3.1.0

- 成功数应显著增加
- 音频缺失导致的失败应大幅减少

---

## 📝 已知限制

以下问题**不在本次修复范围**（属于数据层面或需进一步调查）：

1. **entry.json 空文件** - 数据缺失，程序无法恢复
2. **视频文件真实缺失** - 下载不完整，需用户重新下载
3. **Shizuku 连接不稳定** - 已通过递归重试缓解，但未根治

---

## 🔬 技术细节

### 音频查找流程变化

**v3.1.0**：
```
c_folder 根目录
  → 递归查找视频（找到 c_folder/112/video.m4s）
  → 从 c_folder 根目录再次递归查找音频
  → 可能因深度限制错过 c_folder/112/audio.m4s
```

**v3.1.1**：
```
c_folder 根目录
  → 递归查找视频（找到 c_folder/112/video.m4s）
  → 提取视频目录：c_folder/112
  → 直接在 c_folder/112/ 搜索音频
  → 确保音视频同目录时能被找到
```

### entry.json 容错增强

**v3.1.0**：
```python
try:
    return json.loads(out)
except json.JSONDecodeError:
    print("JSON 解析错误")
    return None
```

**v3.1.1**：
```python
# 1. 检查是否为空
if not out.strip():
    print("空文件（数据缺失）")
    stats['empty_file'] += 1
    return None

# 2. 基础格式校验
if not out.startswith('{'):
    print("格式异常（非JSON）")
    stats['invalid_json'] += 1
    return None

# 3. 解析 + 完整性校验
data = json.loads(out)
if 'title' not in data:
    print("缺少必需字段")
```

---

## 🚀 升级指南

### 从 v3.1.0 升级

```bash
cd bili-merge-tool
git pull origin main
# 或替换以下文件：
# - services/extractor_dash.py
# - services/bili_entry_reader.py
# - uis/cli_main.py
```

### 验证升级

```bash
python main.py
# 观察：
# 1. 音频查找日志是否显示"在视频目录直接搜索"
# 2. 程序结束时是否显示 entry.json 错误统计
# 3. 成功率是否提升
```

---

## 📚 相关文档

- **CHANGELOG_v3.1.md** - v3.0 → v3.1 变更日志
- **UPGRADE_v3.0_to_v3.1.md** - v3.0 → v3.1 升级指南
- **V3.1_RELEASE_NOTES.md** - v3.1.0 发布说明

---

## 🙏 致谢

感谢用户提供的详细Bug报告（BR-20260219-001），包含：
- 71个视频的大规模测试数据
- 精确的问题分类（音频遗漏、entry.json 错误）
- 明确的修复建议（在视频目录直接搜索音频）

这种高质量的反馈是开源项目进步的关键！

---

**v3.1.1 专注于解决实际运行中的核心问题，提升成功率！** 🚀
