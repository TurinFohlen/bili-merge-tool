#!/usr/bin/env python3
"""B站缓存扫描组件（扫描 UID 和 c_* 文件夹）"""
import re
from typing import List
from registry import registry

@registry.register("bili.scanner", "service", "list_uids() -> List[str]")
class BiliScanner:
    def __init__(self):
        self.bili_root = "/storage/emulated/0/Android/data/tv.danmaku.bili/download"
        self.rish_exec = None
    
    def set_rish_executor(self, rish_exec):
        self.rish_exec = rish_exec
    
    def _parse_ls(self, stdout: str) -> List[str]:
        """清洗 ls 输出"""
        result = []
        for line in stdout.splitlines():
            name = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
            if name:
                result.append(name)
        return result
    
    def list_uids(self) -> List[str]:
        """返回所有纯数字 UID 文件夹"""
        if not self.rish_exec:
            raise RuntimeError("rish_exec 未注入")
        _, out, _ = self.rish_exec(f"ls '{self.bili_root}'")
        return [n for n in self._parse_ls(out) if n.isdigit()]
    
    def list_c_folders(self, uid: str) -> List[str]:
        """返回指定 UID 下所有 c_* 文件夹"""
        if not self.rish_exec:
            raise RuntimeError("rish_exec 未注入")
        path = f"{self.bili_root}/{uid}"
        _, out, _ = self.rish_exec(f"ls '{path}'")
        return [n for n in self._parse_ls(out) if n.startswith("c_")]
    
    def list_quality_dirs(self, uid: str, c_folder: str) -> List[str]:
        """返回质量目录（纯数字目录）"""
        if not self.rish_exec:
            raise RuntimeError("rish_exec 未注入")
        path = f"{self.bili_root}/{uid}/{c_folder}"
        _, out, _ = self.rish_exec(f"ls '{path}'")
        return [n for n in self._parse_ls(out) if n.isdigit()]
