#!/usr/bin/env python3
"""BLV 格式提取器（复制所有 .blv 分段）"""
import os, json, re
from typing import List
from registry import registry

@registry.register("extractor.blv", "service", "extract(uid, c_folder, quality, temp_dir) -> bool")
class ExtractorBlv:
    def __init__(self):
        self.bili_root = "/storage/emulated/0/Android/data/tv.danmaku.bili/download"
        self.file_operator = None
        self.rish_exec = None
    
    def set_dependencies(self, file_operator, rish_exec):
        self.file_operator = file_operator
        self.rish_exec = rish_exec
    
    def _parse_ls(self, stdout: str) -> List[str]:
        result = []
        for line in stdout.splitlines():
            name = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
            if name:
                result.append(name)
        return result
    
    def _list_blv_segments(self, uid: str, c_folder: str, quality: str) -> List[str]:
        """列出所有 .blv 分段"""
        base = f"{self.bili_root}/{uid}/{c_folder}/{quality}"
        try:
            _, out, _ = self.rish_exec(f"ls '{base}'")
            names = [n for n in self._parse_ls(out) if n.endswith(".blv")]
            names.sort(key=lambda n: int(n.split(".")[0]) if n.split(".")[0].isdigit() else 0)
            return [f"{base}/{n}" for n in names]
        except Exception:
            return []
    
    def _read_index_json(self, uid: str, c_folder: str, quality: str):
        """读取 index.json"""
        path = f"{self.bili_root}/{uid}/{c_folder}/{quality}/index.json"
        try:
            _, out, _ = self.rish_exec(f"cat '{path}'")
            return json.loads(out)
        except Exception:
            return None
    
    def _parse_index_json(self, index) -> List[str]:
        """从 index.json 提取分段文件名"""
        if not index:
            return []
        if isinstance(index, list):
            return [str(item) for item in index if str(item).endswith(".blv")]
        if not isinstance(index, dict):
            return []
        if "index" in index and isinstance(index["index"], list):
            return [str(item) for item in index["index"] if str(item).endswith(".blv")]
        if "segments" in index and isinstance(index["segments"], list):
            names = []
            for seg in index["segments"]:
                if isinstance(seg, dict) and "filename" in seg:
                    name = str(seg["filename"])
                    if name.endswith(".blv"):
                        names.append(name)
            return names
        return []
    
    def extract(self, uid: str, c_folder: str, quality: str, temp_dir: str) -> bool:
        """提取 BLV 分段到临时目录"""
        base = f"{self.bili_root}/{uid}/{c_folder}/{quality}"
        segments = self._list_blv_segments(uid, c_folder, quality)
        
        # 后备：尝试从 index.json 获取顺序
        index_data = self._read_index_json(uid, c_folder, quality)
        if index_data:
            names_from_index = self._parse_index_json(index_data)
            if names_from_index:
                segments = [f"{base}/{n}" for n in names_from_index]
        
        if not segments:
            print(f"❌ BLV：未找到分段文件: {c_folder}")
            return False
        
        print(f"ℹ️  BLV 分段数: {len(segments)}")
        for seg_path in segments:
            seg_name = os.path.basename(seg_path)
            dst = os.path.join(temp_dir, seg_name)
            if not self.file_operator.copy(seg_path, dst):
                print(f"❌ 复制分段失败: {seg_name}")
                return False
        
        return True
