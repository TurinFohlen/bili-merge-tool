#!/usr/bin/env python3
"""rish 命令执行组件（递归重试版）- 稳定进程模式"""
import os
import subprocess  # 关键：添加这一行
import time
from typing import Tuple
from registry import registry

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
            stderr_lower = result.stderr.lower()
            if "no such file or directory" in stderr_lower:
                raise FileNotFoundError(f"文件不存在: {command[:80]}")
            elif "permission denied" in stderr_lower:
                raise PermissionError(f"权限不足: {command[:80]}")
            elif "no space left" in stderr_lower:
                raise OSError(f"磁盘空间不足: {command[:80]}")
            else:
                raise RuntimeError(f"命令失败 (rc={result.returncode}): {command[:80]} — {result.stderr[:100]}")

        return result.returncode, result.stdout, result.stderr

    def exec_with_retry(self, command: str, check: bool = True, timeout: int = 30) -> Tuple[int, str, str]:
        """
        带指数退避重试的执行 - 递归实现
        对所有可能由连接波动引起的异常进行重试，但排除确定性错误
        """
        def _retry(attempt: int, retries_left: int):
            try:
                return self.exec(command, check, timeout)
            except (TimeoutError, RuntimeError) as e:
                if isinstance(e, RuntimeError):
                    e_str = str(e).lower()
                    if any(key in e_str for key in ["no such file", "permission denied", "disk full", "no space left"]):
                        raise
                if retries_left <= 0:
                    raise e
                delay = min(self.retry_delay_base * (2 ** attempt), self.retry_delay_max)
                print(f"  ⚠ rish 命令失败 ({type(e).__name__})，{delay:.1f}s 后重试 (剩余 {retries_left} 次)", flush=True)
                time.sleep(delay)
                return _retry(attempt + 1, retries_left - 1)
            except (FileNotFoundError, PermissionError, OSError):
                raise
        return _retry(0, self.max_retries)

    def __call__(self, command: str, check: bool = True, timeout: int = 30) -> Tuple[int, str, str]:
        return self.exec_with_retry(command, check, timeout)