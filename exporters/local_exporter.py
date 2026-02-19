#!/usr/bin/env python3
"""本地导出组件（移动视频到用户指定目录）"""
import os, shutil, re
from typing import List
from registry import registry

@registry.register("exporter.local", "service", "export(source_dir, target_dir) -> tuple")
class LocalExporter:
    def __init__(self):
        self.fallback_dir = "/storage/emulated/0/Download/BiliExported"
    
    def list_mp4_files(self, source_dir: str) -> List[str]:
        """列出源目录下所有 MP4 文件"""
        try:
            return [f for f in os.listdir(source_dir) if f.endswith('.mp4')]
        except Exception as e:
            print(f"❌ 列出视频文件失败: {e}")
            return []
    
    def sanitize_path(self, path: str) -> str:
        """清洗路径：去中文、统一分隔符"""
        if path.startswith('/sdcard'):
            path = path.replace('/sdcard', '/storage/emulated/0', 1)
        if re.search(r'[\u4e00-\u9fff]', path):
            print(f"⚠️  路径含中文，改为: {self.fallback_dir}")
            path = self.fallback_dir
        return path
    
    def export(self, source_dir: str, target_dir: str) -> tuple:
        """
        导出视频到目标目录
        
        Returns:
            (success_count, fail_count)
        """
        mp4_files = self.list_mp4_files(source_dir)
        if not mp4_files:
            print("⚠️  没有可导出的视频文件")
            return 0, 0
        
        print(f"ℹ️  找到 {len(mp4_files)} 个视频文件")
        target_dir = self.sanitize_path(target_dir)
        
        try:
            os.makedirs(target_dir, exist_ok=True)
            print(f"✅ 目标目录已准备: {target_dir}")
        except Exception as e:
            print(f"❌ 创建目标目录失败: {e}")
            return 0, 0
        
        success_count = 0
        fail_count = 0
        
        for filename in mp4_files:
            src = f"{source_dir}/{filename}"
            dst = f"{target_dir}/{filename}"
            try:
                print(f"ℹ️  移动: {filename}")
                shutil.move(src, dst)
                success_count += 1
            except Exception as e:
                fail_count += 1
                print(f"❌ 移动失败 ({filename}): {e}")
        
        return success_count, fail_count
