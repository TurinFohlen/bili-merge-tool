#!/usr/bin/env python3
"""rish 命令执行组件（带重试+素数编码错误记录）"""
import os, subprocess, time
from typing import Tuple
from registry import registry
from error_log import record_event, exception_to_error

@registry.register("rish.executor", "service", "exec(command: str, timeout: int = 30) -> Tuple[int,str,str]")
class RishExecutor:
    def __init__(self):
        self.rish_path = "/data/data/com.termux/files/home/shizuku-rish/rish"
        self.app_id = "com.termux"
        self.max_retries = 100
        self.retry_delay_base = 2.0
        self.retry_delay_max = 60.0
    
    def exec(self, command: str, check: bool = True, timeout: int = 30) -> Tuple[int, str, str]:
        """执行单次 rish 命令（不含重试）- v2.0 异常细化版"""
        if not os.path.exists(self.rish_path):
            raise FileNotFoundError(f"rish 未找到: {self.rish_path}")
        
        env = os.environ.copy()
        if self.app_id:
            env["RISH_APPLICATION_ID"] = self.app_id
        
        try:
            result = subprocess.run(
                [self.rish_path], input=command,
                capture_output=True, text=True,
                timeout=timeout, env=env
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"rish 超时 (>{timeout}s): {command[:80]}")
        except FileNotFoundError:
            raise FileNotFoundError(f"rish 无法执行: {self.rish_path}")
        
        # 检查返回码和 stderr，抛出具体异常
        if check and result.returncode != 0:
            stderr_lower = result.stderr.lower()
            
            # 权限错误
            if "permission denied" in stderr_lower:
                raise PermissionError(
                    f"权限被拒绝 — 检查 Shizuku 授权\n"
                    f"命令: {command[:80]}\n"
                    f"stderr: {result.stderr[:200]}"
                )
            
            # 文件不存在错误
            if "no such file or directory" in stderr_lower:
                raise FileNotFoundError(
                    f"文件或目录不存在\n"
                    f"命令: {command[:80]}\n"
                    f"stderr: {result.stderr[:200]}"
                )
            
            # 磁盘空间不足
            if "no space left" in stderr_lower or "disk full" in stderr_lower:
                raise OSError(
                    f"磁盘空间不足\n"
                    f"命令: {command[:80]}\n"
                    f"stderr: {result.stderr[:200]}"
                )
            
            # 通用执行错误
            raise RuntimeError(
                f"命令执行失败 (rc={result.returncode})\n"
                f"命令: {command[:80]}\n"
                f"stderr: {result.stderr[:200]}"
            )
        
        return result.returncode, result.stdout, result.stderr
    
    def exec_with_retry(self, command: str, check: bool = True, timeout: int = 30) -> Tuple[int, str, str]:
        """带指数退避重试的执行"""
        attempt = 0
        last_exc = None
        
        while self.max_retries < 0 or attempt <= self.max_retries:
            try:
                return self.exec(command, check, timeout)
            except TimeoutError as e:
                last_exc = e
                if self.max_retries >= 0 and attempt >= self.max_retries:
                    break
                delay = min(self.retry_delay_base * (2 ** attempt), self.retry_delay_max)
                print(f"  ⚠ rish 超时，{delay:.1f}s 后重试 ({attempt+1})", flush=True)
                time.sleep(delay)
                attempt += 1
            except (FileNotFoundError, PermissionError, RuntimeError):
                raise
        
        raise last_exc  # type: ignore
