#!/usr/bin/env python3
"""
本地文件查找组件 - 用于处理已下载的本地缓存

特点：
  - 不需要 rish，直接操作本地文件系统
  - 递归查找视频/音频文件
  - 读取 entry.json
"""
import os
import json
import re
from typing import Optional, List, Tuple, Dict
from registry import registry

@registry.register("local.file_finder", "service", "find_media(path) -> dict")
class LocalFileFinder:
    def __init__(self):
        pass
    
    def read_entry_json(self, base_path: str) -> Optional[Dict]:
        """
        读取本地 entry.json
        
        Args:
            base_path: c_folder 本地路径
        
        Returns:
            dict 或 None
        """
        entry_path = os.path.join(base_path, "entry.json")
        
        if not os.path.exists(entry_path):
            print(f"  ⚠️  entry.json 不存在")
            return None
        
        try:
            with open(entry_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                
                if not content:
                    print(f"  ⚠️  entry.json 为空文件")
                    return None
                
                if not content.startswith('{'):
                    print(f"  ⚠️  entry.json 格式异常")
                    return None
                
                data = json.loads(content)
                
                if not isinstance(data, dict):
                    print(f"  ⚠️  entry.json 内容无效")
                    return None
                
                return data
        
        except json.JSONDecodeError as e:
            print(f"  ⚠️  entry.json JSON 解析错误: {e}")
            return None
        
        except Exception as e:
            print(f"  ❌ entry.json 读取失败: {e}")
            return None
    
    def find_media_files(self, base_path: str) -> Tuple[Optional[str], Optional[str], str]:
        """
        递归查找视频和音频文件
        
        Args:
            base_path: c_folder 本地路径
        
        Returns:
            (video_path, audio_path, format)
            - video_path: 视频文件完整路径
            - audio_path: 音频文件完整路径（可能为None）
            - format: "dash" / "mp4" / "blv" / "unknown"
        """
        video_names = ["video.m4s", "video.mp4"]
        audio_names = ["audio.m4s", "audio.mp4", "audio.m4a", "audio.mp3"]
        blv_pattern = re.compile(r'^\d+\.blv$')
        
        found_videos = []
        found_audios = []
        found_blvs = []
        
        print(f"  🔍 递归搜索媒体文件...")
        
        # 递归遍历所有文件
        for root, dirs, files in os.walk(base_path):
            depth = root[len(base_path):].count(os.sep)
            
            for filename in files:
                full_path = os.path.join(root, filename)
                
                # 视频文件
                if filename in video_names:
                    found_videos.append((full_path, depth))
                    print(f"  🔍   找到视频: {os.path.relpath(full_path, base_path)} (深度 {depth})")
                
                # 音频文件
                elif filename in audio_names:
                    found_audios.append((full_path, depth))
                    print(f"  🔍   找到音频: {os.path.relpath(full_path, base_path)} (深度 {depth})")
                
                # BLV 分段
                elif blv_pattern.match(filename):
                    found_blvs.append((full_path, depth))
        
        # 优先选择浅层文件（新版结构）
        found_videos.sort(key=lambda x: x[1])
        found_audios.sort(key=lambda x: x[1])
        
        # 判断格式
        if found_blvs:
            fmt = "blv"
            video_path = None  # BLV 格式不需要单独视频文件
            audio_path = None
            print(f"  ✅ 检测格式: BLV ({len(found_blvs)} 分段)")
        
        elif found_videos:
            video_path = found_videos[0][0]
            
            # 在视频同目录下查找音频
            video_dir = os.path.dirname(video_path)
            audio_path = None
            
            for a_name in audio_names:
                candidate = os.path.join(video_dir, a_name)
                if os.path.exists(candidate):
                    audio_path = candidate
                    print(f"  ✅ 选择音频: {os.path.relpath(audio_path, base_path)}")
                    break
            
            if not audio_path:
                print(f"  ⚠️  未找到音频文件（将生成无声视频）")
            
            # 判断是 DASH 还是 MP4
            if video_path.endswith('.m4s'):
                fmt = "dash"
            else:
                fmt = "mp4"
            
            print(f"  ✅ 选择视频: {os.path.relpath(video_path, base_path)}")
            print(f"  ✅ 检测格式: {fmt.upper()}")
        
        else:
            print(f"  ❌ 未找到任何媒体文件")
            return None, None, "unknown"
        
        return video_path, audio_path, fmt
    
    def list_blv_segments(self, base_path: str) -> List[str]:
        """
        列出所有 BLV 分段文件（按序号排序）
        
        Returns:
            分段文件路径列表
        """
        blv_pattern = re.compile(r'^(\d+)\.blv$')
        segments = []
        
        for root, dirs, files in os.walk(base_path):
            for filename in files:
                match = blv_pattern.match(filename)
                if match:
                    seq = int(match.group(1))
                    full_path = os.path.join(root, filename)
                    segments.append((seq, full_path))
        
        # 按序号排序
        segments.sort(key=lambda x: x[0])
        return [path for seq, path in segments]
    
    def extract_title(self, entry: Optional[Dict], c_folder: str) -> str:
        """
        从 entry.json 提取标题，失败则使用 c_folder
        
        Returns:
            清洗后的标题
        """
        if not entry or not isinstance(entry, dict):
            return self._sanitize_filename(c_folder)
        
        title = entry.get('title', '')
        page_data = entry.get('page_data', {})
        part = page_data.get('part', '') if isinstance(page_data, dict) else ''
        
        if part and part != title:
            full_title = f"{title}-{part}"
        else:
            full_title = title or c_folder
        
        return self._sanitize_filename(full_title)
    
    def _sanitize_filename(self, name: str) -> str:
        """
        清洗文件名（去除非法字符）
        """
        # 去除非法字符
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
        cleaned = cleaned.strip('. ')
        
        # 按字节截断（防 Errno 36）
        max_bytes = 200
        encoded = cleaned.encode('utf-8')
        if len(encoded) > max_bytes:
            encoded = encoded[:max_bytes]
            while encoded:
                try:
                    cleaned = encoded.decode('utf-8')
                    break
                except UnicodeDecodeError:
                    encoded = encoded[:-1]
        
        return cleaned or "unnamed"
