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
        if not self.rish_exec:
            raise RuntimeError("rish_exec 未注入")
        rc, out, err = self.rish_exec(f"/system/bin/ls -1 '{self.bili_root}'")
        print(f"[DEBUG] ls output length: {len(out)}")
        print(f"[DEBUG] ls output first 500 chars: {out[:500]}")
        print(f"[DEBUG] ls stderr: {err}")
        
        # 按行解析
        lines = self._parse_ls(out)
        uids = [n for n in lines if n.isdigit()]
        
        # 如果解析出的行数太少且输出总长度很大，可能是缺少换行，尝试正则提取
        if len(uids) == 1 and len(out) > 1000:
            import re
            all_numbers = re.findall(r'\d+', out)
            uids = [n for n in all_numbers if n.isdigit()]
            print(f"[DEBUG] 正则提取到 {len(uids)} 个 UID")
        else:
            print(f"[DEBUG] 按行解析到 {len(uids)} 个 UID")
        
        return uids
    
    def list_c_folders(self, uid: str) -> List[str]:
        if not self.rish_exec:
            raise RuntimeError("rish_exec 未注入")
        path = f"{self.bili_root}/{uid}"
        _, out, _ = self.rish_exec(f"ls '{path}'")
        return [n for n in self._parse_ls(out) if n.startswith("c_")]
    
    def list_quality_dirs(self, uid: str, c_folder: str) -> List[str]:
        if not self.rish_exec:
            raise RuntimeError("rish_exec 未注入")
        path = f"{self.bili_root}/{uid}/{c_folder}"
        _, out, _ = self.rish_exec(f"ls '{path}'")
        return [n for n in self._parse_ls(out) if n.isdigit()]