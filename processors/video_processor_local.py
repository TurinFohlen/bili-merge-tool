#!/usr/bin/env python3
"""
视频处理器（本地缓存模式） - v3.2.0

流程：
  1. 使用 pack_transfer 下载并解包到本地
  2. 使用 local_file_finder 查找媒体文件
  3. 复制到临时目录
  4. 调用 ffmpeg 合并
"""
import os
import shutil
from typing import Dict
from registry import registry

@registry.register("video.processor.local", "processor", "process(uid, c_folder, progress) -> bool")
class VideoProcessorLocal:
    def __init__(self):
        self.pack_transfer = None
        self.local_finder = None
        self.merger = None
        self.progress_mgr = None
        
        self.output_dir = "/storage/emulated/0/Download/B站视频"
        self.temp_base = "/storage/emulated/0/Download/bili_temp"
    
    def set_dependencies(self, **kwargs):
        """注入所有依赖组件"""
        self.pack_transfer = kwargs.get('pack_transfer')
        self.local_finder = kwargs.get('local_finder')
        self.merger = kwargs.get('merger')
        self.progress_mgr = kwargs.get('progress_mgr')
    
    def process(self, uid: str, c_folder: str, progress: Dict) -> bool:
        """
        处理单个视频（本地缓存模式）
        
        流程：
          1. 检查进度 → 跳过已完成
          2. 下载并解包到本地（如果未缓存）
          3. 读取 entry.json → 提取标题
          4. 查找媒体文件
          5. 复制到临时目录
          6. 调用 ffmpeg 合并
          7. 记录进度
        """
        # 1. 检查进度
        if progress.get(c_folder):
            print(f"ℹ️  已完成，跳过: {c_folder}")
            return True
        
        print(f"ℹ️  处理视频: {c_folder}")
        temp_dir = None
        
        try:
            # 2. 下载并解包到本地（自动检查缓存）
            print(f"  📦 准备本地缓存...")
            if not self.pack_transfer.download_and_extract(uid, c_folder):
                print(f"❌ 下载或解包失败: {c_folder}")
                return False
            
            # 3. 获取本地路径
            local_path = self.pack_transfer.get_local_path(uid, c_folder)
            if not local_path:
                print(f"❌ 无法获取本地路径: {c_folder}")
                return False
            
            # 4. 读取 entry.json
            entry = self.local_finder.read_entry_json(local_path)
            title = self.local_finder.extract_title(entry, c_folder)
            output_filename = f"{title}.mp4"
            output_path = f"{self.output_dir}/{output_filename}"
            print(f"  ℹ️  标题: {title}")
            
            # 5. 查找媒体文件
            video_path, audio_path, fmt = self.local_finder.find_media_files(local_path)
            
            if fmt == "unknown":
                print(f"❌ 未找到媒体文件: {c_folder}")
                return False
            
            # 6. 创建临时目录
            temp_dir = f"{self.temp_base}/bili_{c_folder}"
            os.makedirs(temp_dir, exist_ok=True)
            
            # 7. 根据格式处理
            if fmt == "blv":
                # BLV 格式：复制所有分段
                blv_segments = self.local_finder.list_blv_segments(local_path)
                if not blv_segments:
                    print(f"❌ BLV 分段列表为空: {c_folder}")
                    return False
                
                print(f"  📋 复制 {len(blv_segments)} 个 BLV 分段...")
                for seg_path in blv_segments:
                    seg_name = os.path.basename(seg_path)
                    dst = os.path.join(temp_dir, seg_name)
                    shutil.copy2(seg_path, dst)
                
                # 合并 BLV
                success = self.merger.merge_blv(temp_dir, output_path)
            
            else:
                # DASH / MP4 格式：复制视频和音频
                if not video_path:
                    print(f"❌ 视频文件为空: {c_folder}")
                    return False
                
                video_dst = f"{temp_dir}/video.m4s"
                audio_dst = f"{temp_dir}/audio.m4s" if audio_path else None
                
                print(f"  📋 复制媒体文件...")
                shutil.copy2(video_path, video_dst)
                
                if audio_path:
                    shutil.copy2(audio_path, audio_dst)
                else:
                    print(f"  ⚠️  无音频，将生成无声视频")
                
                # 合并 DASH/MP4
                success = self.merger.merge_dash(temp_dir, output_path, audio_file=audio_dst)
            
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
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass
