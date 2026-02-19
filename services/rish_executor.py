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
        """执行单次 rish 命令（不含重试）"""
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
        
        if "Permission denied" in result.stderr:
            raise PermissionError("权限被拒绝 — 检查 Shizuku 授权")
        
        if check and result.returncode != 0:
            raise RuntimeError(f"命令失败 (rc={result.returncode}): {command[:80]}")
        
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
