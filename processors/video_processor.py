#!/usr/bin/env python3
"""视频处理器（核心编排组件）"""
import os, shutil
from typing import Dict
from registry import registry

@registry.register("video.processor", "processor", "process(uid, c_folder, progress) -> bool")
class VideoProcessor:
    def __init__(self):
        self.scanner = None
        self.entry_reader = None
        self.format_detector = None
        self.extractor_dash = None
        self.extractor_blv = None
        self.merger = None
        self.progress_mgr = None
        
        self.output_dir = "/storage/emulated/0/Download/B站视频"
        self.temp_base = "/storage/emulated/0/Download/bili_temp"
    
    def set_dependencies(self, **kwargs):
        """注入所有依赖组件"""
        self.scanner = kwargs.get('scanner')
        self.entry_reader = kwargs.get('entry_reader')
        self.format_detector = kwargs.get('format_detector')
        self.extractor_dash = kwargs.get('extractor_dash')
        self.extractor_blv = kwargs.get('extractor_blv')
        self.merger = kwargs.get('merger')
        self.progress_mgr = kwargs.get('progress_mgr')
    
    def _validate_entry(self, entry) -> bool:
        """验证 entry.json"""
        if not entry:
            return False
        if not isinstance(entry, dict):
            return False
        if 'type_tag' not in entry or 'page_data' not in entry:
            return False
        return True
    
    def _extract_title(self, entry: dict) -> str:
        """提取标题并清洗文件名"""
        import re
        page_data = entry.get('page_data', {})
        part = page_data.get('part', '')
        title = entry.get('title', '未命名')
        
        if part and part != title:
            full_title = f"{title}-{part}"
        else:
            full_title = title
        
        # 清洗非法字符
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', full_title)
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
        
        return cleaned or "未命名"
    
    def _cleanup_temp(self, temp_dir: str):
        """清理临时目录"""
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"⚠️  清理临时目录失败: {e}")
    
    def process(self, uid: str, c_folder: str, progress: Dict) -> bool:
        """
        处理单个视频缓存（完整流程）
        
        流程：
          1. 检查进度 → 跳过已完成
          2. 读取 entry.json → 提取标题
          3. 扫描质量目录 → 选最高质量
          4. 检测格式 (DASH / MP4 / BLV)
          5. 根据格式调用对应 extractor
          6. 调用 merger 合并
          7. 记录进度
        """
        # 1. 检查进度
        if progress.get(c_folder):
            print(f"ℹ️  已完成，跳过: {c_folder}")
            return True
        
        print(f"ℹ️  处理视频: {c_folder}")
        temp_dir = None
        
        try:
            # 2. 读取 entry.json
            entry = self.entry_reader.read(uid, c_folder)
            if not self._validate_entry(entry):
                print(f"⚠️  无效的 entry.json: {c_folder}")
                return False
            
            # 3. 提取标题
            title = self._extract_title(entry)
            output_filename = f"{title}.mp4"
            output_path = f"{self.output_dir}/{output_filename}"
            print(f"ℹ️  标题: {title}")
            
            # 4. 扫描质量目录
            quality_dirs = self.scanner.list_quality_dirs(uid, c_folder)
            if not quality_dirs:
                print(f"⚠️  未找到质量目录: {c_folder}")
                return False
            quality_dirs.sort(key=int, reverse=True)
            quality = quality_dirs[0]
            
            # 5. 检测格式
            fmt = self.format_detector.detect(uid, c_folder, quality)
            quality_label = self.format_detector.quality_label(quality)
            print(f"ℹ️  质量: {quality_label}  格式: {fmt}")
            
            # 6. 创建临时目录
            temp_dir = f"{self.temp_base}/bili_{c_folder}"
            os.makedirs(temp_dir, exist_ok=True)
            
            # 7. 根据格式提取 + 合并
            if fmt == "blv":
                success = self.extractor_blv.extract(uid, c_folder, quality, temp_dir)
                if not success:
                    return False
                success = self.merger.merge_blv(temp_dir, output_path)
            
            elif fmt in ("dash", "mp4"):
                video_dst, audio_dst, success = self.extractor_dash.extract(
                    uid, c_folder, quality, temp_dir, fmt
                )
                if not success:
                    return False
                success = self.merger.merge_dash(temp_dir, output_path, audio_file=audio_dst)
            
            else:
                print(f"❌ 未知格式: {fmt}")
                return False
            
            # 8. 记录进度
            if success:
                progress[c_folder] = True
                self.progress_mgr.save(progress)
            
            return success
        
        except Exception as e:
            print(f"❌ 处理失败 ({c_folder}): {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            if temp_dir:
                self._cleanup_temp(temp_dir)
