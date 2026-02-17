#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shizuku访问层 - 封装所有与rish的通信
版本: 2.0

职责:
- 封装rish命令执行
- 提供Android文件系统访问接口
- 标准化错误处理

依赖: 仅Python标准库
"""

import os
import subprocess
import json
from typing import Tuple, List, Optional, Dict

# ============================================================================
# 配置变量
# ============================================================================

# rish可执行文件路径
RISH_PATH = "/data/data/com.termux/files/home/shizuku-rish/rish"

# rish调用时的应用ID
RISH_APP_ID = "com.termux"

# B站缓存根目录
BILI_ROOT = "/storage/emulated/0/Android/data/tv.danmaku.bili/download"

# ============================================================================
# 异常类
# ============================================================================

class ShizukuError(Exception):
    """Shizuku相关错误的基类"""
    pass


class RishNotFoundError(ShizukuError):
    """rish可执行文件未找到"""
    pass


class RishTimeoutError(ShizukuError):
    """rish命令执行超时"""
    pass


class RishPermissionError(ShizukuError):
    """rish权限被拒绝"""
    pass


class RishExecutionError(ShizukuError):
    """rish命令执行失败"""
    pass


# ============================================================================
# 配置函数
# ============================================================================

def set_rish_path(path: str):
    """
    设置rish可执行文件路径
    
    Args:
        path: rish文件的完整路径
    """
    global RISH_PATH
    RISH_PATH = path


def set_rish_app_id(app_id: str):
    """
    设置rish应用ID
    
    Args:
        app_id: 应用包名，如 com.termux
    """
    global RISH_APP_ID
    RISH_APP_ID = app_id


def set_bili_root(path: str):
    """
    设置B站缓存根目录
    
    Args:
        path: B站缓存目录路径
    """
    global BILI_ROOT
    BILI_ROOT = path


# ============================================================================
# 核心函数
# ============================================================================
def rish_exec(command: str, check: bool = True, timeout: int = 30) -> Tuple[int, str, str]:
    """
    通过rish执行命令（使用标准输入方式，通过环境变量传递应用ID）
    """
    if not os.path.exists(RISH_PATH):
        raise RishNotFoundError(
            f"rish未找到: {RISH_PATH}\n"
            f"请确保已从Shizuku导出rish，或将rish复制到Termux内部目录"
        )
    
    # 构建命令（只包含rish路径，不加 -p 参数）
    full_cmd = [RISH_PATH]
    
    # 设置环境变量，传递应用ID
    env = os.environ.copy()
    if RISH_APP_ID:
        env['RISH_APPLICATION_ID'] = RISH_APP_ID
    
    try:
        # 通过标准输入传递命令
        result = subprocess.run(
            full_cmd,
            input=command,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env  # 传递环境变量
        )
        
        # 检查权限错误
        if "Permission denied" in result.stderr:
            raise RishPermissionError(
                f"权限被拒绝\n"
                f"请确保:\n"
                f"1. Shizuku服务正在运行\n"
                f"2. Termux已在Shizuku中授权\n"
                f"3. rish文件有执行权限"
            )
        
        # 检查返回码
        if check and result.returncode != 0:
            raise RishExecutionError(
                f"命令执行失败 (返回码: {result.returncode})\n"
                f"命令: {command}\n"
                f"错误: {result.stderr[:200]}"
            )
        
        return result.returncode, result.stdout, result.stderr
    
    except subprocess.TimeoutExpired:
        raise RishTimeoutError(
            f"命令执行超时 (>{timeout}秒)\n"
            f"命令: {command}\n"
            f"提示: 部分系统需关闭电池优化，否则rish会超时"
        )
    except FileNotFoundError:
        raise RishNotFoundError(
            f"rish文件不存在或无法执行: {RISH_PATH}\n"
            f"如果在/sdcard下无法执行，请将rish复制到Termux内部目录"
        )

def safe_path(path: str) -> str:
    """
    安全化路径，用于shell命令
    
    Args:
        path: 原始路径
    
    Returns:
        用单引号包裹的路径
    """
    # 替换单引号为 '\''
    escaped = path.replace("'", "'\\''")
    return f"'{escaped}'"


# ============================================================================
# 高层次接口
# ============================================================================

def list_uids() -> List[str]:
    """
    列出B站缓存根目录下的所有UID文件夹
    
    Returns:
        UID列表（纯数字文件夹名）
    
    Raises:
        ShizukuError: rish相关错误
    """
    try:
        _, stdout, _ = rish_exec(f"ls {safe_path(BILI_ROOT)}")
        
        # 解析输出（只保留纯数字文件夹）
        lines = stdout.splitlines()
        uids = []
        
        for line in lines:
            cleaned = line.strip()
            # 移除ANSI转义序列
            import re
            cleaned = re.sub(r'\x1b\[[0-9;]*m', '', cleaned)
            
            if cleaned and cleaned.isdigit():
                uids.append(cleaned)
        
        return uids
    
    except ShizukuError:
        raise
    except Exception as e:
        raise ShizukuError(f"列出UID失败: {e}")


def list_c_folders(uid: str) -> List[str]:
    """
    列出指定UID下的所有c_*文件夹
    
    Args:
        uid: 用户ID
    
    Returns:
        c_*文件夹名列表
    
    Raises:
        ShizukuError: rish相关错误
    """
    uid_path = f"{BILI_ROOT}/{uid}"
    
    try:
        _, stdout, _ = rish_exec(f"ls {safe_path(uid_path)}")
        
        # 解析输出（只保留c_开头的文件夹）
        lines = stdout.splitlines()
        c_folders = []
        
        for line in lines:
            cleaned = line.strip()
            # 移除ANSI转义序列
            import re
            cleaned = re.sub(r'\x1b\[[0-9;]*m', '', cleaned)
            
            if cleaned and cleaned.startswith('c_'):
                c_folders.append(cleaned)
        
        return c_folders
    
    except ShizukuError:
        raise
    except Exception as e:
        raise ShizukuError(f"列出c_*文件夹失败 (UID={uid}): {e}")


def read_entry_json(uid: str, c_folder: str) -> Optional[Dict]:
    """
    读取entry.json文件
    
    Args:
        uid: 用户ID
        c_folder: c_*文件夹名
    
    Returns:
        解析后的JSON对象，失败返回None
    """
    entry_path = f"{BILI_ROOT}/{uid}/{c_folder}/entry.json"
    
    try:
        _, stdout, _ = rish_exec(f"cat {safe_path(entry_path)}")
        return json.loads(stdout)
    
    except (ShizukuError, json.JSONDecodeError):
        return None
    except Exception:
        return None


def check_file_exists(uid: str, c_folder: str, quality: str, file_type: str) -> bool:
    """
    检查音视频文件是否存在
    
    Args:
        uid: 用户ID
        c_folder: c_*文件夹名
        quality: 质量编号（如'112'）
        file_type: 文件类型（'video'或'audio'）
    
    Returns:
        文件是否存在
    """
    file_path = f"{BILI_ROOT}/{uid}/{c_folder}/{quality}/{file_type}.m4s"
    
    try:
        returncode, _, _ = rish_exec(
            f"test -f {safe_path(file_path)}",
            check=False
        )
        return returncode == 0
    
    except Exception:
        return False


def copy_file(src_remote: str, dst_local: str) -> bool:
    """
    从Android远程路径复制文件到Termux本地路径
    
    Args:
        src_remote: 远程源文件路径
        dst_local: 本地目标路径
    
    Returns:
        是否成功
    
    Raises:
        ShizukuError: 复制失败
    """
    try:
        # 确保目标目录存在
        dst_dir = os.path.dirname(dst_local)
        os.makedirs(dst_dir, exist_ok=True)
        
        # 执行复制
        rish_exec(f"cp {safe_path(src_remote)} {safe_path(dst_local)}",timeout=480)
        
        # 验证文件是否存在
        if not os.path.exists(dst_local):
            raise ShizukuError("复制后文件不存在")
        
        return True
    
    except ShizukuError:
        raise
    except Exception as e:
        raise ShizukuError(f"复制文件失败: {e}")


def create_remote_dir(path: str) -> bool:
    """
    在远程创建目录
    
    Args:
        path: 目录路径
    
    Returns:
        是否成功
    
    Raises:
        ShizukuError: 创建失败
    """
    try:
        rish_exec(f"mkdir -p {safe_path(path)}", check=False)
        return True
    
    except ShizukuError:
        raise
    except Exception as e:
        raise ShizukuError(f"创建目录失败: {e}")


def move_file(src: str, dst: str) -> bool:
    """
    移动文件（用于导出功能）
    
    Args:
        src: 源文件路径
        dst: 目标文件路径
    
    Returns:
        是否成功
    
    Raises:
        ShizukuError: 移动失败
    """
    try:
        rish_exec(f"mv {safe_path(src)} {safe_path(dst)}")
        
        # 验证文件是否存在于目标位置
        returncode, _, _ = rish_exec(
            f"test -f {safe_path(dst)}",
            check=False
        )
        
        if returncode != 0:
            raise ShizukuError("移动后文件不存在于目标位置")
        
        return True
    
    except ShizukuError:
        raise
    except Exception as e:
        raise ShizukuError(f"移动文件失败: {e}")


# ============================================================================
# 工具函数
# ============================================================================

def test_rish_availability() -> Tuple[bool, str]:
    """
    测试rish是否可用
    
    Returns:
        (是否可用, 错误信息或成功信息)
    """
    try:
        if not os.path.exists(RISH_PATH):
            return False, f"rish文件不存在: {RISH_PATH}"
        
        # 尝试执行简单命令
        returncode, stdout, stderr = rish_exec("echo test", check=False, timeout=120)
        
        if returncode == 0 and "test" in stdout:
            return True, "rish可用"
        else:
            return False, f"rish执行失败: {stderr}"
    
    except RishNotFoundError as e:
        return False, str(e)
    except RishTimeoutError:
        return False, "rish超时，请检查Shizuku服务状态和电池优化设置"
    except RishPermissionError as e:
        return False, str(e)
    except Exception as e:
        return False, f"未知错误: {e}"


if __name__ == "__main__":
    # 简单测试
    print("测试Shizuku访问层...")
    
    available, msg = test_rish_availability()
    if available:
        print(f"✓ {msg}")
        
        try:
            uids = list_uids()
            print(f"✓ 发现 {len(uids)} 个UID")
        except Exception as e:
            print(f"✗ 列出UID失败: {e}")
    else:
        print(f"✗ {msg}")

def list_quality_dirs(uid: str, c_folder: str) -> List[str]:
    """
    列出c_folder下存在的质量目录（如112、80等）
    """
    import re
    c_path = f"{BILI_ROOT}/{uid}/{c_folder}"
    try:
        _, stdout, _ = rish_exec(f"ls {safe_path(c_path)}")
        items = stdout.splitlines()
        dirs = []
        for line in items:
            cleaned = line.strip()
            # 移除ANSI控制字符
            cleaned = re.sub(r'\x1b\[[0-9;]*m', '', cleaned)
            # 只保留纯数字（质量目录）
            if cleaned and cleaned.isdigit():
                dirs.append(cleaned)
        return dirs
    except Exception:
        return []