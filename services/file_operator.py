#!/usr/bin/env python3
"""文件操作组件（文件存在检查、复制、移动）"""
import os, math
from registry import registry

@registry.register("file.operator", "service", "copy(src: str, dst: str) -> bool")
class FileOperator:
    def __init__(self):
        self.chunk_threshold = 20 * 1024 * 1024
        self.chunk_size = 10 * 1024 * 1024
        self.rish_exec = None  # 延迟注入
    
    def set_rish_executor(self, rish_exec):
        self.rish_exec = rish_exec
    
    def check_exists(self, path: str) -> bool:
        """检查远程文件是否存在"""
        if not self.rish_exec:
            raise RuntimeError("rish_exec 未注入")
        try:
            rc, _, _ = self.rish_exec(f"test -f '{path}'", check=False, timeout=15)
            return rc == 0
        except Exception:
            return False
    
    def get_size(self, path: str) -> int:
        """获取远程文件大小（字节）"""
        if not self.rish_exec:
            raise RuntimeError("rish_exec 未注入")
        try:
            _, out, _ = self.rish_exec(f"stat -c %s '{path}'", check=False, timeout=15)
            return int(out.strip())
        except Exception:
            return -1
    
    def copy(self, src: str, dst: str) -> bool:
        """复制文件（自动分片）"""
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        size = self.get_size(src)
        if size > self.chunk_threshold:
            return self._copy_chunked(src, dst, size)
        return self._copy_direct(src, dst)
    
    def _copy_direct(self, src: str, dst: str) -> bool:
        if not self.rish_exec:
            raise RuntimeError("rish_exec 未注入")
        self.rish_exec(f"cp '{src}' '{dst}'", timeout=480)
        if not os.path.exists(dst):
            raise FileNotFoundError("复制后文件不存在")
        return True
    
    def _copy_chunked(self, src: str, dst: str, total_size: int) -> bool:
        """分片复制"""
        n_chunks = math.ceil(total_size / self.chunk_size)
        parts = []
        print(f"  🔍 分片复制 {os.path.basename(src)} ({total_size//1024//1024}MB, {n_chunks} 片)")
        try:
            for i in range(n_chunks):
                part = f"{dst}.part{i}"
                parts.append(part)
                cmd = f"dd if='{src}' of='{part}' bs={self.chunk_size} skip={i} count=1 2>/dev/null"
                self.rish_exec(cmd, timeout=300)
                if not os.path.exists(part):
                    raise FileNotFoundError(f"分片 {i} 不存在")
                print(f"  🔍   片 {i+1}/{n_chunks} ✓", flush=True)
            with open(dst, "wb") as out_f:
                for part in parts:
                    with open(part, "rb") as pf:
                        out_f.write(pf.read())
            return True
        finally:
            for part in parts:
                try:
                    if os.path.exists(part): os.remove(part)
                except Exception:
                    pass
