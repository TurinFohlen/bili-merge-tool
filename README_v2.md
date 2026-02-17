# B站缓存视频合并工具 v2.0

## 📋 项目简介

这是一个专为 Android + Termux + Shizuku 环境设计的 B 站缓存视频合并工具，能够自动扫描 B 站客户端缓存的音视频分离文件（.m4s），并通过 ffmpeg 合并为 MP4 格式。

### ⭐ 版本2.0新特性

- ✨ **模块化架构**: 代码拆分为三个独立模块，提高可维护性
- 🔧 **修复rish通信**: 使用标准输入传递命令，兼容更多设备
- 📝 **字节截断**: 按UTF-8字节截断文件名，避免文件名过长错误
- 🎯 **改进错误处理**: 标准化异常类型，提供更友好的错误提示
- ✅ **完整测试覆盖**: 模块化测试，易于验证功能正确性

### 主要特性

- ✅ **自动扫描**: 自动发现所有 UID 文件夹和缓存视频
- ✅ **断点续传**: 支持中断后继续，已完成的视频不会重复处理
- ✅ **质量优先**: 自动选择最高质量的视频（1080P+ → 1080P → 720P → ...）
- ✅ **标题提取**: 自动从 entry.json 提取视频标题并清理非法字符
- ✅ **导出功能**: 合并完成后可将视频移动到指定目录
- ✅ **错误容错**: 单个视频失败不影响其他视频处理
- ✅ **零依赖**: 仅使用 Python 3 标准库，无需额外安装包

---

## 🏗️ 架构说明

### 模块结构

```
bili_merge_tool_v2/
├── shizuku_access.py      # Shizuku访问层
├── data_processor.py      # 数据处理层
├── ui.py                  # 用户界面层（主程序）
├── test_modules.py        # 模块化测试
└── README.md             # 本文档
```

### 模块职责

#### 1. shizuku_access.py - Shizuku访问层
**职责**: 封装所有与rish的通信，提供Android文件系统访问接口

**核心函数**:
- `rish_exec(command)` - 执行rish命令（通过标准输入）
- `list_uids()` - 列出所有UID文件夹
- `list_c_folders(uid)` - 列出c_*缓存文件夹
- `read_entry_json(uid, c_folder)` - 读取entry.json
- `check_file_exists(...)` - 检查音视频文件是否存在
- `copy_file(src, dst)` - 复制文件到Termux
- `create_remote_dir(path)` - 创建远程目录
- `move_file(src, dst)` - 移动文件（导出功能）

**异常类型**:
- `RishNotFoundError` - rish文件未找到
- `RishTimeoutError` - rish命令超时
- `RishPermissionError` - 权限被拒绝
- `RishExecutionError` - 命令执行失败

#### 2. data_processor.py - 数据处理层
**职责**: 处理原始数据的解析、过滤和转换

**核心函数**:
- `parse_ls_output(output)` - 解析ls输出，清理控制字符
- `clean_filename(filename, max_bytes)` - 按字节截断文件名
- `extract_title(entry)` - 从entry.json提取标题
- `select_best_quality(qualities)` - 选择最高质量
- `filter_completed(c_folders, progress)` - 过滤已完成的视频

**辅助类**:
- `VideoStats` - 视频处理统计
- `VideoTask` - 视频任务信息
- `VideoState` - 视频处理状态

#### 3. ui.py - 用户界面层
**职责**: 命令行交互和主流程控制

**核心函数**:
- `main()` - 程序入口
- `process_single_video(...)` - 处理单个视频
- `merge_video(...)` - 调用ffmpeg合并
- `export_videos()` - 导出功能
- `load_progress()` / `save_progress()` - 进度管理

---

## 🔧 环境准备

### 1. 必需软件

#### 1.1 Termux
从 F-Droid 或 GitHub 下载安装 Termux：
- F-Droid: https://f-droid.org/packages/com.termux/
- GitHub: https://github.com/termux/termux-app/releases

#### 1.2 Shizuku
从 Google Play 或 GitHub 下载安装 Shizuku：
- Google Play: https://play.google.com/store/apps/details?id=moe.shizuku.privileged.api
- GitHub: https://github.com/RikkaApps/Shizuku/releases

#### 1.3 B 站客户端
- 安装 B 站客户端并缓存一些视频

### 2. 环境配置

#### 2.1 安装 Python 和 ffmpeg

在 Termux 中运行：

```bash
pkg update
pkg install python ffmpeg
```

#### 2.2 授予 Termux 存储权限

```bash
termux-setup-storage
```

执行后会弹出权限请求，点击"允许"。

#### 2.3 启动 Shizuku

1. 打开 Shizuku 应用
2. 根据提示启动 Shizuku 服务（需要 root 或无线调试）
   - **无 root 方式**: 使用 ADB 无线调试（需要 PC）
   - **Root 方式**: 直接在应用内启动

#### 2.4 导出 rish

**重要说明**: 部分设备（如OPPO）的 `/sdcard` 分区无法执行文件，需要将rish复制到Termux内部目录。

**方法1: 导出到 /sdcard（默认）**

在 Shizuku 应用中：
1. 进入"终端"或"Rish"页面
2. 点击"导出 rish"
3. 选择导出位置为 `/sdcard/shizuku-rish/`

**方法2: 复制到 Termux 内部目录（推荐）**

```bash
# 创建目录
mkdir -p ~/shizuku-rish

# 从 /sdcard 复制到 Termux
cp /sdcard/shizuku-rish/rish ~/shizuku-rish/
cp /sdcard/shizuku-rish/*.dex ~/shizuku-rish/ 2>/dev/null || true

# 设置执行权限
chmod +x ~/shizuku-rish/rish
```

#### 2.5 授权 Termux 使用 Shizuku

1. 在 Shizuku 应用中进入"授权管理"
2. 找到 Termux 并授予权限

---

## 📦 安装使用

### 1. 下载脚本

将所有Python文件放到同一目录，例如：

```bash
cd ~
mkdir bili_merge
cd bili_merge
# 将 shizuku_access.py, data_processor.py, ui.py 放到这里
```

### 2. 配置路径（如果rish在Termux内部）

如果rish在Termux内部目录，运行前先配置：

```bash
# 编辑 shizuku_access.py
nano shizuku_access.py

# 修改第18行为:
RISH_PATH = "/data/data/com.termux/files/home/shizuku-rish/rish"
# 或
RISH_PATH = os.path.expanduser("~/shizuku-rish/rish")
```

或者通过环境变量设置（推荐）：

```bash
export BILI_RISH_PATH=~/shizuku-rish/rish
```

### 3. 运行脚本

```bash
python ui.py
```

### 4. 脚本执行流程

脚本会自动执行以下操作：

1. **环境检查**: 验证 rish 和 ffmpeg 是否存在
2. **扫描 UID**: 自动发现所有 B 站缓存用户
3. **扫描视频**: 列出每个 UID 下的所有缓存视频
4. **提取信息**: 读取 entry.json 获取标题
5. **质量检测**: 查找最高质量的音视频文件
6. **复制文件**: 将文件复制到 Termux 临时目录
7. **合并视频**: 使用 ffmpeg 合并音视频
8. **清理临时**: 删除临时文件
9. **记录进度**: 保存已完成的视频记录

### 5. 输出位置

合并后的视频默认保存在：

```
/storage/emulated/0/Download/B站视频/
```

如果该路径不可访问，会自动降级到：

```
/storage/emulated/0/Download/BiliMerged/
```

### 6. 导出功能

合并完成后，脚本会询问是否导出视频。

**注意**:
- 路径会自动转换 `/sdcard` 为 `/storage/emulated/0`
- 如果路径包含中文字符，会自动改为 `/storage/emulated/0/Download/BiliExported`

---

## 🧪 测试

### 运行测试

```bash
python test_modules.py
```

### 测试覆盖

1. **data_processor模块**: 测试数据解析、文件名清理、标题提取等
2. **shizuku_access模块**: 测试rish通信、文件操作等
3. **集成测试**: 测试完整工作流程

### 测试输出示例

```
============================================================
      B站缓存视频合并工具 - 模块化测试
============================================================

============================================================
【测试组1】data_processor模块
============================================================

测试1: ls输出解析
  ✓ 正常输出解析
  ✓ 控制字符清理

测试2: 文件名清理
  ✓ 非法字符清理
  ✓ 字节截断

...

============================================================
测试完成!
============================================================
总计: 3 个测试组
  ✅ 通过: 3
  ❌ 失败: 0
============================================================
```

---

## 🔍 常见问题

### Q1: rish 未找到或无法执行

**错误信息**:
```
❌ rish不可用: rish文件不存在或无法执行
```

**解决方法**:

方案1: 检查路径
```bash
ls -l /sdcard/shizuku-rish/rish
# 或
ls -l ~/shizuku-rish/rish
```

方案2: 复制到Termux内部（推荐）
```bash
mkdir -p ~/shizuku-rish
cp /sdcard/shizuku-rish/rish ~/shizuku-rish/
cp /sdcard/shizuku-rish/*.dex ~/shizuku-rish/ 2>/dev/null || true
chmod +x ~/shizuku-rish/rish
```

方案3: 修改配置
编辑 `shizuku_access.py`，设置正确的 `RISH_PATH`

### Q2: rish 命令超时

**错误信息**:
```
❌ rish命令超时 (>30秒)
提示: 部分系统需关闭电池优化，否则rish会超时
```

**解决方法**:
1. 在系统设置中关闭 Shizuku 和 Termux 的电池优化
2. 确保 Shizuku 服务正在运行
3. 尝试重启 Shizuku 服务

### Q3: 权限被拒绝

**错误信息**:
```
❌ 权限被拒绝
```

**解决方法**:
1. 确认已运行 `termux-setup-storage`
2. 在 Shizuku 中授权 Termux
3. 确保 Shizuku 服务正在运行
4. 检查rish文件是否有执行权限: `chmod +x ~/shizuku-rish/rish`

### Q4: 文件名过长错误

**错误信息**:
```
❌ Errno 36: File name too long
```

**解决方法**:
这个问题在v2.0中已修复。如果仍然出现：
1. 更新到最新版本
2. 或手动调整 `data_processor.py` 中的 `max_bytes` 参数（默认180）

### Q5: ffmpeg 未安装

**错误信息**:
```
❌ ffmpeg未安装
```

**解决方法**:
```bash
pkg install ffmpeg
```

### Q6: 未发现任何 UID 文件夹

**错误信息**:
```
⚠️ 未发现任何UID文件夹
```

**可能原因**:
1. B 站客户端未缓存任何视频
2. 缓存路径错误
3. Shizuku 未正确授权

**解决方法**:
1. 在 B 站客户端中下载一些视频
2. 验证路径：`/storage/emulated/0/Android/data/tv.danmaku.bili/download`
3. 检查 Shizuku 授权状态

---

## ⚙️ 高级配置

### 自定义rish路径

**方法1: 环境变量（推荐）**
```bash
export BILI_RISH_PATH=~/shizuku-rish/rish
python ui.py
```

**方法2: 修改代码**
编辑 `shizuku_access.py`:
```python
RISH_PATH = os.path.expanduser("~/shizuku-rish/rish")
```

### 自定义输出目录

编辑 `ui.py`:
```python
OUTPUT_DIR = "/storage/emulated/0/Download/我的视频"
```

### 修改质量优先级

编辑 `data_processor.py`:
```python
QUALITY_LIST = ['80', '64', '32']  # 只选择 1080P, 720P, 480P
```

质量对照表：
- `112`: 1080P+ (高码率)
- `80`: 1080P
- `64`: 720P
- `32`: 480P
- `16`: 360P

### 修改文件名长度限制

编辑 `data_processor.py` 的 `clean_filename` 函数:
```python
def clean_filename(filename: str, max_bytes: int = 150) -> str:
    # 降低到150字节以适应更多设备
```

---

## 🐛 故障排查

### 1. 检查环境

```bash
# 检查 Python 版本
python --version

# 检查 ffmpeg 版本
ffmpeg -version

# 检查 rish
ls -l ~/shizuku-rish/rish
# 或
ls -l /sdcard/shizuku-rish/rish

# 测试 rish
~/shizuku-rish/rish -p com.termux
# 然后输入: echo test
# 按 Ctrl+D
```

### 2. 验证权限

```bash
# 测试 rish 访问
~/shizuku-rish/rish -p com.termux
# 输入: ls /storage/emulated/0/Android/data/
# 按 Ctrl+D

# 测试存储权限
ls /storage/emulated/0/
```

### 3. 查看详细日志

运行时会打印详细的日志信息：
- ℹ️ INFO: 普通信息
- ✅ SUCCESS: 成功操作
- ⚠️ WARNING: 警告
- ❌ ERROR: 错误
- 🔍 DEBUG: 调试信息

### 4. 运行测试

```bash
# 运行完整测试
python test_modules.py

# 单独测试数据处理
python data_processor.py

# 测试rish可用性
python shizuku_access.py
```

---

## 📝 更新日志

### v2.0 (2026-02-13)
- 🏗️ 模块化重构：拆分为三个独立模块
- 🔧 修复rish通信：改用标准输入传递命令
- 📝 字节截断：按UTF-8字节截断文件名
- 🎯 改进错误处理：标准化异常和友好提示
- ✅ 完整测试覆盖：模块化测试框架

### v1.0 (2026-02-13)
- 初始版本
- 基本功能实现

---

## 📁 文件说明

### 源代码
- `shizuku_access.py` - Shizuku访问层（约400行）
- `data_processor.py` - 数据处理层（约350行）
- `ui.py` - 用户界面层（约500行）

### 测试
- `test_modules.py` - 模块化测试（约450行）

### 临时文件位置
- **临时目录**: `/data/data/com.termux/files/usr/tmp/bili_*`
- **输出目录**: `/storage/emulated/0/Download/B站视频/`
- **进度文件**: `/storage/emulated/0/Download/B站视频/.bili_progress.json`

---

## 💡 性能优化建议

### 1. 减少rish调用（当前已优化）
- 批量获取UID和c_*列表
- 使用缓存减少重复查询

### 2. 并发处理（可选，未实现）
- 多个视频可同时合并
- 需要注意磁盘I/O竞争

### 3. ffmpeg优化
```bash
# 在 merge_video 函数中添加 -preset ultrafast
cmd = [
    FFMPEG_PATH,
    "-i", video_file,
    "-i", audio_file,
    "-c", "copy",
    "-preset", "ultrafast",  # 加快处理速度
    "-y",
    output_path
]
```

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

**开发建议**:
1. 修改前先运行测试确保功能正常
2. 添加新功能时同步更新测试
3. 遵循现有的模块化结构
4. 添加详细的注释和文档

---

## 📄 许可证

MIT License

---

## 👤 作者

本工具由 Claude 4.5 Sonnet 开发，基于详细的技术规格说明书。

---

## 📞 支持

如果遇到问题，请：

1. 查看本 README 的常见问题部分
2. 运行测试验证模块功能: `python test_modules.py`
3. 运行单模块测试: `python data_processor.py` 或 `python shizuku_access.py`
4. 检查 Termux、Shizuku、rish 环境是否正确配置
5. 提交 Issue 并附上完整的错误信息和日志

---

**祝你使用愉快！** 🎉
