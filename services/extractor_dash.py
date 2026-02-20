#!/usr/bin/env python3
"""DASH 格式提取器（复制 video.m4s + audio.m4s）- v2.0 递归查找版"""
import os
import re
from typing import Optional, List, Tuple
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
    
    def _parse_ls(self, stdout: str) -> List[str]:
        """清洗 ls 输出"""
        result = []
        for line in stdout.splitlines():
            name = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
            if name and not name.startswith('.'):
                result.append(name)
        return result
    
    def _find_files_recursive(self, base_dir: str, target_names: List[str], max_depth: int = 3) -> List[Tuple[str, int]]:
        """
        递归查找文件，返回 (完整路径, 深度) 列表
        
        Args:
            base_dir: 起始目录
            target_names: 目标文件名列表（如 ["video.m4s", "video.mp4"]）
            max_depth: 最大递归深度
        
        Returns:
            [(path, depth), ...] 按深度升序排列（浅层优先）
        """
        if not self.rish_exec:
            return []
        
        found = []
        
        def search(current_dir: str, depth: int):
            if depth > max_depth:
                return
            
            try:
                rc, out, _ = self.rish_exec(f"ls '{current_dir}'", check=False, timeout=15)
                if rc != 0:
                    return
                
                items = self._parse_ls(out)
                
                # 检查当前层是否有目标文件
                for item in items:
                    if item in target_names:
                        full_path = f"{current_dir}/{item}"
                        # 验证确实存在
                        if self.file_operator.check_exists(full_path):
                            found.append((full_path, depth))
                            print(f"  🔍 找到: {full_path} (深度 {depth})")
                
                # 递归搜索子目录（仅数字目录，如 quality 目录）
                for item in items:
                    if item.isdigit():
                        search(f"{current_dir}/{item}", depth + 1)
            
            except Exception as e:
                print(f"  ⚠️  搜索 {current_dir} 失败: {e}")
        
        search(base_dir, 0)
        
        # 按深度排序（浅层优先）
        found.sort(key=lambda x: x[1])
        return found
    
    def extract(self, uid: str, c_folder: str, quality: str, temp_dir: str, fmt: str) -> tuple:
        """
        提取 DASH/MP4 格式文件到临时目录（v3.1.1 音频优化版）
        
        改进：
          - 不再硬编码 quality 子目录
          - 从 c_folder 根目录递归查找视频/音频文件
          - 优先选择浅层文件（通常是最新版本）
          - 🆕 找到视频后，直接在视频所在目录搜索音频（避免二次递归遗漏）
        
        Returns:
            (video_dst, audio_dst, success)
        """
        base = f"{self.bili_root}/{uid}/{c_folder}"
        video_dst = f"{temp_dir}/video.m4s"
        audio_dst = f"{temp_dir}/audio.m4s"
        
        # 视频文件：优先级根据格式决定
        v_names = ["video.m4s", "video.mp4"] if fmt == "dash" else ["video.mp4", "video.m4s"]
        print(f"  🔍 递归查找视频文件: {v_names}")
        video_candidates = self._find_files_recursive(base, v_names, max_depth=3)
        
        if not video_candidates:
            print(f"❌ 视频文件不存在（已递归搜索 .m4s/.mp4）: {c_folder}")
            print(f"   搜索起点: {base}")
            return None, None, False
        
        video_src = video_candidates[0][0]  # 取最浅层的
        print(f"  ✅ 选择视频: {video_src}")
        
        # 🆕 音频文件：直接在视频所在目录查找（避免二次递归可能错过同目录音频）
        video_dir = os.path.dirname(video_src)
        a_names = ["audio.m4s", "audio.mp4", "audio.m4a", "audio.mp3"]
        print(f"  🔍 在视频目录 {os.path.basename(video_dir)}/ 直接搜索音频: {a_names}")
        
        audio_src = None
        for a_name in a_names:
            candidate = f"{video_dir}/{a_name}"
            if self.file_operator.check_exists(candidate):
                audio_src = candidate
                print(f"  ✅ 选择音频: {audio_src}")
                break
        
        if not audio_src:
            print("  ⚠️  视频目录下未找到音频文件，将仅 remux 视频")
        
        # 复制文件
        print("  🔍 开始复制...")
        try:
            if not self.file_operator.copy(video_src, video_dst):
                print(f"❌ 复制视频文件失败: {c_folder}")
                return None, None, False
        except Exception as e:
            print(f"❌ 复制视频文件异常: {e}")
            return None, None, False
        
        if audio_src:
            try:
                if not self.file_operator.copy(audio_src, audio_dst):
                    print(f"❌ 复制音频文件失败: {c_folder}")
                    return None, None, False
            except Exception as e:
                print(f"⚠️  复制音频文件异常，将仅使用视频: {e}")
                audio_dst = None
        else:
            audio_dst = None
        
        return video_dst, audio_dst, True
