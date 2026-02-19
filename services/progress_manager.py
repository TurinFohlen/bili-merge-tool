#!/usr/bin/env python3
"""进度管理组件（加载/保存进度）"""
import os, json
from typing import Dict
from registry import registry

@registry.register("progress.manager", "service", "load() -> Dict[str, bool]")
class ProgressManager:
    def __init__(self):
        self.progress_file = None
    
    def set_progress_file(self, path: str):
        self.progress_file = path
    
    def load(self) -> Dict[str, bool]:
        """加载进度记录"""
        try:
            if self.progress_file and os.path.exists(self.progress_file):
                with open(self.progress_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️  读取进度文件失败: {e}")
        return {}
    
    def save(self, progress: Dict[str, bool]):
        """保存进度记录"""
        try:
            if not self.progress_file:
                return
            os.makedirs(os.path.dirname(self.progress_file), exist_ok=True)
            tmp = self.progress_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(progress, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.progress_file)
        except Exception as e:
            print(f"⚠️  保存进度文件失败: {e}")
