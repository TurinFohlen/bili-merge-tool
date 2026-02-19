#!/usr/bin/env python3
"""DASH 格式提取器（复制 video.m4s + audio.m4s）"""
import os
from typing import Optional
from registry import registry

@registry.register("extractor.dash", "service", "extract(uid, c_folder, quality, temp_dir) -> tuple")
class ExtractorDash:
    def __init__(self):
        self.bili_root = "/storage/emulated/0/Android/data/tv.danmaku.bili/download"
        self.file_operator = None
        self.rish_exec = None
    
    def set_dependencies(self, file_operator, rish_exec):
        self.file_operator = file_operator
        self.rish_exec = rish_exec
    
    def extract(self, uid: str, c_folder: str, quality: str, temp_dir: str, fmt: str) -> tuple:
        """
        提取 DASH/MP4 格式文件到临时目录
        
        Returns:
            (video_dst, audio_dst, success)
        """
        base = f"{self.bili_root}/{uid}/{c_folder}/{quality}"
        video_dst = f"{temp_dir}/video.m4s"
        audio_dst = f"{temp_dir}/audio.m4s"
        
        # 视频文件：优先级根据格式决定
        v_order = ("video.m4s", "video.mp4") if fmt == "dash" else ("video.mp4", "video.m4s")
        video_src = None
        for vname in v_order:
            candidate = f"{base}/{vname}"
            if self.file_operator.check_exists(candidate):
                video_src = candidate
                break
        
        if not video_src:
            print(f"❌ 视频文件不存在（已尝试 .m4s/.mp4）: {c_folder}")
            return None, None, False
        
        # 音频文件：同理（允许缺失）
        a_order = ("audio.m4s", "audio.mp4") if fmt == "dash" else ("audio.mp4", "audio.m4s")
        audio_src = None
        for aname in a_order:
            candidate = f"{base}/{aname}"
            if self.file_operator.check_exists(candidate):
                audio_src = candidate
                break
        
        if not audio_src:
            print("⚠️  未找到音频文件，将仅 remux 视频")
        
        # 复制文件
        print("🔍 复制文件...")
        if not self.file_operator.copy(video_src, video_dst):
            print(f"❌ 复制视频文件失败: {c_folder}")
            return None, None, False
        
        if audio_src:
            if not self.file_operator.copy(audio_src, audio_dst):
                print(f"❌ 复制音频文件失败: {c_folder}")
                return None, None, False
        else:
            audio_dst = None
        
        return video_dst, audio_dst, True
