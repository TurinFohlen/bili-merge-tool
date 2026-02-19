#!/usr/bin/env python3
"""文件操作组件（文件存在检查、复制、移动）- 增强版"""
import os
import math
import time
import logging
from registry import registry

# 配置日志
logger = logging.getLogger(__name__)

@registry.register("file.operator", "service", "copy(src: str, dst: str) -> bool")
class FileOperator:
    def __init__(self):
        self.chunk_threshold = 20 * 1024 * 1024
        self.chunk_size = 10 * 1024 * 1024
        self.rish_exec = None  # 延迟注入
        self.command_delay = 0.1  # 每次命令后的延迟（秒），可配置

    def set_rish_executor(self, rish_exec):
        self.rish_exec = rish_exec

    def _call_rish(self, command, check=True, timeout=30):
        """内部调用 rish_exec，自动处理延迟和异常记录"""
        if not self.rish_exec:
            raise RuntimeError("rish_exec 未注入")
        try:
            result = self.rish_exec(command, check=check, timeout=timeout)
            time.sleep(self.command_delay)
            return result
        except Exception as e:
            logger.debug(f"rish 命令失败: {command[:60]}... - {e}")
            raise

    def check_exists(self, path: str) -> bool:
        """检查远程文件是否存在"""
        try:
            rc, _, _ = self._call_rish(f"test -f '{path}'", check=False, timeout=15)
            return rc == 0
        except Exception as e:
            logger.warning(f"检查文件存在性失败 (可能连接问题): {path} - {e}")
            # 返回 False 表示不存在（但实际可能不确定）
            return False

    def get_size(self, path: str) -> int:
        """获取远程文件大小（字节）"""
        try:
            _, out, _ = self._call_rish(f"stat -c %s '{path}'", check=False, timeout=15)
            return int(out.strip())
        except Exception as e:
            logger.warning(f"获取文件大小失败: {path} - {e}")
            return -1

    def copy(self, src: str, dst: str) -> bool:
        """复制文件（自动分片）"""
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        size = self.get_size(src)
        if size < 0:
            logger.error(f"无法获取源文件大小，复制失败: {src}")
            return False
        if size > self.chunk_threshold:
            return self._copy_chunked(src, dst, size)
        return self._copy_direct(src, dst)

    def _copy_direct(self, src: str, dst: str) -> bool:
        try:
            self._call_rish(f"cp '{src}' '{dst}'", timeout=480)
            if not os.path.exists(dst):
                raise FileNotFoundError("复制后文件不存在")
            return True
        except Exception as e:
            logger.error(f"直接复制失败 {src} -> {dst}: {e}")
            return False

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
                self._call_rish(cmd, timeout=300)
                if not os.path.exists(part):
                    raise FileNotFoundError(f"分片 {i} 不存在")
                print(f"  🔍   片 {i+1}/{n_chunks} ✓", flush=True)
            with open(dst, "wb") as out_f:
                for part in parts:
                    with open(part, "rb") as pf:
                        out_f.write(pf.read())
            return True
        except Exception as e:
            logger.error(f"分片复制失败 {src}: {e}")
            return False
        finally:
            for part in parts:
                try:
                    if os.path.exists(part): os.remove(part)
                except Exception:
                    pass