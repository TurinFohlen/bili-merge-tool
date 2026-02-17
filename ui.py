#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户界面层 - 命令行交互和主流程控制
版本: 2.0

职责:
- 程序入口和主流程
- 用户交互和输入处理
- 日志输出
- 进度管理
- 调用底层模块完成任务

依赖:
- shizuku_access.py
- data_processor.py
"""
import shutil #详见后文
import os
import sys
import json
import subprocess
import re
from pathlib import Path
from typing import Dict, Optional

# 导入自定义模块
import shizuku_access as sa
import data_processor as dp

# ============================================================================
# 常量配置
# ============================================================================

# ffmpeg路径（Termux默认安装位置）
FFMPEG_PATH = "/data/data/com.termux/files/usr/bin/ffmpeg"

# 临时文件目录基础路径
TEMP_BASE = "/storage/emulated/0/Download/bili_temp"

# 输出目录（存放合并后的MP4文件）
OUTPUT_DIR = "/storage/emulated/0/Download/B站视频"

# 进度记录文件
PROGRESS_FILE = None  # 将在ensure_output_dir中设置

# 导出失败时的备用路径（纯英文，避免中文路径问题）
EXPORT_FALLBACK = "/storage/emulated/0/Download/BiliExported"

# ============================================================================
# 日志函数
# ============================================================================

def log(msg: str, level: str = "INFO"):
    """
    打印日志信息
    
    Args:
        msg: 日志消息
        level: 日志级别（INFO, SUCCESS, WARNING, ERROR, DEBUG）
    """
    prefix = {
        "INFO": "ℹ️",
        "SUCCESS": "✅",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "DEBUG": "🔍"
    }.get(level, "•")
    print(f"{prefix} {msg}")


# ============================================================================
# 输出目录管理
# ============================================================================

def ensure_output_dir():
    """
    确保输出目录存在
    
    注意:
        - 优先使用rish创建目录
        - Python侧二次验证
        - 如果包含中文或无法访问，降级到英文路径
    """
    global OUTPUT_DIR, PROGRESS_FILE
    
    try:
        # 使用rish创建目录
        sa.create_remote_dir(OUTPUT_DIR)
        
        # Python侧验证（需要存储权限）
        if not os.path.exists(OUTPUT_DIR):
            # 尝试降级到英文路径
            OUTPUT_DIR = "/storage/emulated/0/Download/BiliMerged"
            PROGRESS_FILE = f"{OUTPUT_DIR}/.bili_progress.json"
            
            log(f"输出目录不可访问，降级到: {OUTPUT_DIR}", "WARNING")
            
            # 再次创建
            sa.create_remote_dir(OUTPUT_DIR)
        else:
            PROGRESS_FILE = f"{OUTPUT_DIR}/.bili_progress.json"
    
    except Exception as e:
        log(f"创建输出目录失败: {e}", "ERROR")
        raise


# ============================================================================
# 进度管理
# ============================================================================

def load_progress() -> Dict[str, bool]:
    """
    加载进度记录
    
    Returns:
        {c_folder: True} 格式的字典
    """
    try:
        if PROGRESS_FILE and os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        log(f"读取进度文件失败: {e}", "WARNING")
    
    return {}


def save_progress(progress: Dict[str, bool]):
    """
    保存进度记录（使用临时文件原子替换）
    
    Args:
        progress: 进度字典
    """
    try:
        if not PROGRESS_FILE:
            return
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
        
        # 写入临时文件
        temp_path = f"{PROGRESS_FILE}.tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
        
        # 原子替换
        os.replace(temp_path, PROGRESS_FILE)
        
    except Exception as e:
        log(f"保存进度文件失败: {e}", "WARNING")


# ============================================================================
# 视频处理
# ============================================================================

def merge_video(temp_dir: str, output_path: str) -> bool:
    """
    使用ffmpeg合并音视频文件
    
    Args:
        temp_dir: 临时目录路径
        output_path: 输出MP4文件路径
    
    Returns:
        是否成功
    """
    video_file = f"{temp_dir}/video.m4s"
    audio_file = f"{temp_dir}/audio.m4s"
    
    # 检查ffmpeg是否存在
    if not os.path.exists(FFMPEG_PATH):
        log(f"ffmpeg未安装: {FFMPEG_PATH}", "ERROR")
        log("请运行: pkg install ffmpeg", "INFO")
        return False
    
    # 构建ffmpeg命令
    cmd = [
        FFMPEG_PATH,
        "-i", video_file,
        "-i", audio_file,
        "-c", "copy",  # 直接复制流，不重新编码
        "-y",  # 覆盖已存在的文件
        output_path
    ]
    
    try:
        log(f"正在合并视频...", "INFO")
        
        # 执行ffmpeg（不设超时，等待完成）
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 最长10分钟
        )
        
        # 检查输出文件是否存在
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            log(f"合并成功: {os.path.basename(output_path)}", "SUCCESS")
            return True
        else:
            log(f"合并失败: 输出文件不存在或为空", "ERROR")
            if result.stderr:
                log(f"ffmpeg stderr: {result.stderr[:200]}", "DEBUG")
            return False
    
    except subprocess.TimeoutExpired:
        log("ffmpeg执行超时 (>10分钟)", "ERROR")
        return False
    
    except Exception as e:
        log(f"ffmpeg执行失败: {e}", "ERROR")
        return False


def cleanup_temp(temp_dir: str):
    """
    清理临时文件
    
    Args:
        temp_dir: 临时目录路径
    """
    try:
        if os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir)
            log(f"临时文件已清理", "DEBUG")
    except Exception as e:
        log(f"清理临时文件失败: {e}", "WARNING")


def process_single_video(uid: str, c_folder: str, progress: Dict) -> bool:
    """
    处理单个视频缓存
    
    Args:
        uid: 用户ID
        c_folder: c_*文件夹名
        progress: 进度字典
    
    Returns:
        是否成功
    """
    # 检查是否已完成
    if progress.get(c_folder):
        log(f"已完成，跳过: {c_folder}", "INFO")
        return True
    
    log(f"处理视频: {c_folder}", "INFO")
    
    temp_dir = None
    
    try:
        # 1. 读取entry.json
        entry = sa.read_entry_json(uid, c_folder)
        if not entry or not dp.validate_entry_json(entry):
            log(f"无效的entry.json: {c_folder}", "WARNING")
            return False
        
        # 2. 提取标题
        title = dp.extract_title(entry)
        output_filename = f"{title}.mp4"
        output_path = f"{OUTPUT_DIR}/{output_filename}"
        
        log(f"标题: {title}", "INFO")

        # 3. 查找最高质量视频：直接取实际存在的质量目录（新版B站通常只有一个）
        quality_dirs = sa.list_quality_dirs(uid, c_folder)
        if not quality_dirs:
            log(f"未找到可用质量目录: {c_folder}", "WARNING")
            return False
        # 按数字降序排序，取最大的质量（如果有多个，选最高的）
        quality_dirs.sort(key=int, reverse=True)
        quality = quality_dirs[0]
        log(f"选择质量: {quality}", "DEBUG")
        # 4. 复制到临时目录
        temp_dir = f"{TEMP_BASE}/bili_{c_folder}"
        os.makedirs(temp_dir, exist_ok=True)
        
        video_src = f"{sa.BILI_ROOT}/{uid}/{c_folder}/{quality}/video.m4s"
        audio_src = f"{sa.BILI_ROOT}/{uid}/{c_folder}/{quality}/audio.m4s"
        
        video_dst = f"{temp_dir}/video.m4s"
        audio_dst = f"{temp_dir}/audio.m4s"
        
        log(f"复制文件...", "DEBUG")
        
        if not sa.copy_file(video_src, video_dst):
            log(f"复制视频文件失败: {c_folder}", "ERROR")
            return False
        
        if not sa.copy_file(audio_src, audio_dst):
            log(f"复制音频文件失败: {c_folder}", "ERROR")
            return False
        
        # 5. 合并视频
        success = merge_video(temp_dir, output_path)
        
        # 6. 记录进度
        if success:
            progress[c_folder] = True
            save_progress(progress)
        
        return success
    
    except sa.ShizukuError as e:
        log(f"Shizuku错误 ({c_folder}): {e}", "ERROR")
        return False
    
    except Exception as e:
        log(f"处理失败 ({c_folder}): {e}", "ERROR")
        return False
    
    finally:
        # 7. 清理临时文件（无论成功失败）
        if temp_dir:
            cleanup_temp(temp_dir)


# ============================================================================
# 导出功能
# ============================================================================

def export_videos():
    """
    导出（移动）已合并的视频到指定目录
    """
    print("\n" + "=" * 50)
    log("视频导出功能", "INFO")
    print("=" * 50)
    
    # 列出所有MP4文件
    try:
        mp4_files = [
            f for f in os.listdir(OUTPUT_DIR)
            if f.endswith('.mp4')
        ]
        
        if not mp4_files:
            log("没有可导出的视频文件", "WARNING")
            return
        
        log(f"找到 {len(mp4_files)} 个视频文件", "INFO")
        
    except Exception as e:
        log(f"列出视频文件失败: {e}", "ERROR")
        return
    
    # 询问导出路径
    print("\n请输入导出目标路径 (支持 /sdcard 或 /storage/emulated/0):")
    print("示例: /sdcard/Movies 或 /storage/emulated/0/DCIM")
    print("(直接回车取消导出)")
    
    export_path = input("导出路径: ").strip()
    
    if not export_path:
        log("已取消导出", "INFO")
        return
    
    # 转换 /sdcard 到标准路径
    if export_path.startswith('/sdcard'):
        export_path = export_path.replace('/sdcard', '/storage/emulated/0', 1)
    
    # 检查中文字符，强制使用英文路径
    if re.search(r'[\u4e00-\u9fff]', export_path):
        log(f"路径包含中文字符，自动改为: {EXPORT_FALLBACK}", "WARNING")
        export_path = EXPORT_FALLBACK
    
    # 创建目标目录
    try:
        os.makedirs(export_path,exist_ok=True)
        log(f"目标目录已准备: {export_path}", "SUCCESS")
    except Exception as e:
        log(f"创建目标目录失败: {e}", "ERROR")
        return
    
    # 移动文件
    success_count = 0
    fail_count = 0
    
    for filename in mp4_files:
        src = f"{OUTPUT_DIR}/{filename}"
        dst = f"{export_path}/{filename}"
        
        try:
            log(f"移动: {filename}", "INFO")
            shutil.move(src, dst)          # 本地操作，无需 rish
            success_count += 1
        
        except Exception as e:              # 捕获所有异常
            fail_count += 1
            log(f"移动失败 ({filename}): {e}", "ERROR")
    
    # 统计
    print("\n" + "=" * 50)
    log(f"导出完成: 成功 {success_count}, 失败 {fail_count}", "SUCCESS")
    print("=" * 50)


# ============================================================================
# 主函数
# ============================================================================

def main():
    """主函数"""
    print("=" * 60)
    print("         B站缓存视频合并工具 v2.0")
    print("=" * 60)
    print()
    
    # 环境检查
    log("正在检查环境...", "INFO")
    
    # 检查rish
   # if not available:available, msg = sa.test_rish_availability()
    #if not available:
     #   log(f"rish不可用: {msg}", "ERROR")
      #  log("请确保:", "INFO")
       # log("1. Shizuku服务正在运行", "INFO")
        #log("2. rish已导出到正确位置", "INFO")
        #log("3. Termux已在Shizuku中授权", "INFO")
        #return 1
    
       
    # 检查ffmpeg
    if not os.path.exists(FFMPEG_PATH):
        log(f"ffmpeg未安装: {FFMPEG_PATH}", "ERROR")
        log("请运行: pkg install ffmpeg", "INFO")
        return 1
    
    log("✓ ffmpeg已安装", "SUCCESS")
    print()
    
    # 确保输出目录存在
    try:
        ensure_output_dir()
        log(f"✓ 输出目录: {OUTPUT_DIR}", "SUCCESS")
    except Exception as e:
        log(f"无法创建输出目录: {e}", "ERROR")
        return 1
    
    print()
    
    # 加载进度
    progress = load_progress()
    log(f"已完成 {len(progress)} 个视频", "INFO")
    print()
    
    # 扫描UID
    try:
        log("正在扫描B站缓存...", "INFO")
        uids = sa.list_uids()
        
        if not uids:
            log("未发现任何UID文件夹", "WARNING")
            log("请确保B站客户端已缓存视频", "INFO")
            return 1
        
        log(f"发现 {len(uids)} 个UID文件夹", "SUCCESS")
    
    except Exception as e:
        log(f"扫描失败: {e}", "ERROR")
        return 1
    
    print()
    
    # 统计
    stats = dp.VideoStats()
    
    # 遍历所有UID
    for i, uid in enumerate(uids, 1):
        log(f"处理UID [{i}/{len(uids)}]: {uid}", "INFO")
        
        try:
            # 列出c_*文件夹
            c_folders = sa.list_c_folders(uid)
            
            if not c_folders:
                log(f"  未找到缓存文件夹", "WARNING")
                continue
            
            log(f"  发现 {len(c_folders)} 个缓存文件夹", "INFO")
            
            # 处理每个视频
            for c_folder in c_folders:
                # 检查是否已完成
                if progress.get(c_folder):
                    stats.add_skipped()
                    continue
                
                # 处理单个视频
                success = process_single_video(uid, c_folder, progress)
                
                if success:
                    stats.add_success()
                else:
                    stats.add_failed()
                
                print()
        
        except sa.ShizukuError as e:
            log(f"  处理UID失败: {e}", "ERROR")
            continue
    
    # 最终统计
    print("\n" + "=" * 60)
    log("合并完成!", "SUCCESS")
    print("=" * 60)
    print(f"{stats}")
    print("=" * 60)
    print()
    
    # 询问是否导出
    if stats.success > 0 or stats.skipped > 0:
        print("是否导出已合并的视频? (y/n)")
        choice = input("选择: ").strip().lower()
        
        if choice == 'y':
            export_videos()
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n用户中断")
        sys.exit(130)
    except Exception as e:
        log(f"未预期的错误: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        sys.exit(1)
