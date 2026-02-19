#!/usr/bin/env python3
"""ffmpeg 合并组件（DASH + BLV）"""
import os, subprocess
from typing import Optional
from registry import registry

@registry.register("merger.ffmpeg", "service", "merge_dash(...) -> bool")
class MergerFFmpeg:
    def __init__(self):
        self.ffmpeg_path = "/data/data/com.termux/files/usr/bin/ffmpeg"
    
    def merge_dash(self, temp_dir: str, output_path: str, audio_file: Optional[str] = None) -> bool:
        """合并 DASH 格式（video.m4s + audio.m4s）"""
        if not os.path.exists(self.ffmpeg_path):
            print(f"❌ ffmpeg 未安装: {self.ffmpeg_path}")
            return False
        
        video_file = f"{temp_dir}/video.m4s"
        if audio_file is None:
            audio_file = f"{temp_dir}/audio.m4s" if os.path.exists(f"{temp_dir}/audio.m4s") else None
        
        if audio_file and os.path.exists(audio_file):
            cmd = [self.ffmpeg_path, "-i", video_file, "-i", audio_file, "-c", "copy", "-y", output_path]
            print("ℹ️  合并音视频 (DASH)...")
        else:
            cmd = [self.ffmpeg_path, "-i", video_file, "-c", "copy", "-y", output_path]
            print("⚠️  仅 remux 视频（无音频流）...")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                print(f"✅ 合并成功: {os.path.basename(output_path)}")
                return True
            print(f"❌ 合并失败: 输出文件不存在或为空")
            if result.stderr:
                print(f"🔍 ffmpeg stderr: {result.stderr[:300]}")
            return False
        except subprocess.TimeoutExpired:
            print("❌ ffmpeg 超时 (>10min)")
            return False
        except Exception as e:
            print(f"❌ ffmpeg 异常: {e}")
            return False
    
    def merge_blv(self, temp_dir: str, output_path: str) -> bool:
        """合并 BLV 分段（concat demuxer）"""
        if not os.path.exists(self.ffmpeg_path):
            print(f"❌ ffmpeg 未安装: {self.ffmpeg_path}")
            return False
        
        blv_files = sorted(
            [f for f in os.listdir(temp_dir) if f.endswith(".blv")],
            key=lambda n: int(n.split(".")[0]) if n.split(".")[0].isdigit() else 0
        )
        if not blv_files:
            print("❌ 临时目录内未找到 .blv 文件")
            return False
        
        concat_list = os.path.join(temp_dir, "concat.txt")
        with open(concat_list, "w", encoding="utf-8") as f:
            for name in blv_files:
                escaped = os.path.join(temp_dir, name).replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")
        
        cmd = [self.ffmpeg_path, "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", "-y", output_path]
        print(f"ℹ️  合并 {len(blv_files)} 段 BLV → MP4...")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                print(f"✅ BLV 合并成功: {os.path.basename(output_path)}")
                return True
            print("❌ BLV 合并失败: 输出文件不存在或为空")
            if result.stderr:
                print(f"🔍 ffmpeg stderr: {result.stderr[:300]}")
            return False
        except subprocess.TimeoutExpired:
            print("❌ ffmpeg BLV 合并超时 (>10min)")
            return False
        except Exception as e:
            print(f"❌ ffmpeg BLV 合并异常: {e}")
            return False
