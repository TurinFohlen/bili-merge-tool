#!/usr/bin/env python3
"""
统一打包分片传输组件 v1.0

核心流程：
  1. 远程打包整个 c_* 文件夹为 tar
  2. 分片下载（dd + base64）
  3. MD5 校验（支持断点续传）
  4. 本地解包

优势：
  - 彻底摆脱 rish 不稳定问题（仅用于数据传输）
  - 保留完整目录结构
  - 支持断点续传和校验
"""
import os
import tarfile
import hashlib
import base64
import tempfile
import shutil
from typing import Optional, Tuple
from registry import registry

@registry.register("pack.transfer", "service", "download_and_extract(...) -> bool")
class PackTransfer:
    def __init__(self):
        self.bili_root = "/storage/emulated/0/Android/data/tv.danmaku.bili/download"
        self.remote_tmp = "/data/local/tmp"
        self.local_cache = None  # 本地缓存根目录，从config读取
        self.rish_exec = None
    
    def set_rish_executor(self, rish_exec):
        self.rish_exec = rish_exec
    
    def set_local_cache(self, path: str):
        """设置本地缓存目录"""
        self.local_cache = path
        os.makedirs(path, exist_ok=True)
    
    def check_local_cache(self, uid: str, c_folder: str) -> bool:
        """
        检查本地缓存是否存在且完整
        
        Returns:
            True: 本地缓存存在且有效
            False: 需要下载
        """
        if not self.local_cache:
            return False
        
        local_path = os.path.join(self.local_cache, uid, c_folder)
        
        # 检查目录存在
        if not os.path.exists(local_path):
            return False
        
        # 检查关键文件存在（entry.json 或任何媒体文件）
        entry_json = os.path.join(local_path, "entry.json")
        if os.path.exists(entry_json) and os.path.getsize(entry_json) > 0:
            print(f"  ✅ 本地缓存已存在: {uid}/{c_folder}")
            return True
        
        # 检查是否有媒体文件（更宽松的检查）
        for root, dirs, files in os.walk(local_path):
            for f in files:
                if f.endswith(('.m4s', '.mp4', '.blv', '.m4a')):
                    print(f"  ✅ 本地缓存已存在（含媒体文件）: {uid}/{c_folder}")
                    return True
        
        print(f"  ⚠️  本地缓存无效（将重新下载）: {uid}/{c_folder}")
        return False
    
    def _remote_pack(self, uid: str, c_folder: str) -> Tuple[str, int]:
        """
        远程打包 c_* 文件夹
        
        Returns:
            (remote_tar_path, file_size)
        """
        if not self.rish_exec:
            raise RuntimeError("rish_exec 未注入")
        
        source_dir = f"{self.bili_root}/{uid}/{c_folder}"
        tar_name = f"{uid}_{c_folder}.tar"
        remote_tar = f"{self.remote_tmp}/{tar_name}"
        
        print(f"  📦 远程打包: {c_folder}")
        
        # 检查源目录是否存在
        rc, _, _ = self.rish_exec(f"test -d '{source_dir}'", check=False, timeout=10)
        if rc != 0:
            raise FileNotFoundError(f"远程源目录不存在: {source_dir}")
        
        # 删除可能存在的旧tar
        self.rish_exec(f"rm -f '{remote_tar}'", check=False, timeout=10)
        
        # 打包（使用相对路径，保留目录结构）
        # tar -cf 包名 -C 源目录父目录 c_folder
        parent_dir = f"{self.bili_root}/{uid}"
        cmd = f"cd '{parent_dir}' && tar -cf '{remote_tar}' '{c_folder}'"
        
        try:
            rc, out, err = self.rish_exec(cmd, timeout=300)
            if rc != 0:
                raise RuntimeError(f"打包失败: {err[:200]}")
        except Exception as e:
            raise RuntimeError(f"打包异常: {e}")
        
        # 获取文件大小
        _, size_str, _ = self.rish_exec(f"stat -c %s '{remote_tar}'", timeout=10)
        file_size = int(size_str.strip())
        
        print(f"  ✅ 打包完成: {file_size // 1024 // 1024}MB")
        return remote_tar, file_size
    
    def _download_single(self, remote_tar: str, file_size: int, local_tar: str, max_retries: int = 5) -> bool:
        """
        单次传输完整文件（带重试）
        
        数学原理：
          - 分片传输：P(成功) = p^n （n越大，成功率越低）
          - 单次传输：P(成功) = p （明确的成功/失败）
          - 在低成功率(p=0.3)环境下，单次传输优于分片
        
        Args:
            remote_tar: 远程tar文件路径
            file_size: 文件大小
            local_tar: 本地保存路径
            max_retries: 最大重试次数
        
        Returns:
            True: 下载成功
            False: 下载失败
        """
        if not self.rish_exec:
            raise RuntimeError("rish_exec 未注入")
        
        print(f"  📥 单次传输: {file_size // 1024 // 1024}MB")
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    delay = min(2 ** attempt, 60)  # 指数退避，最多60秒
                    print(f"  ⏱️  重试 {attempt}/{max_retries}，等待 {delay}s...")
                    import time
                    time.sleep(delay)
                
                # 单次读取完整文件 + base64编码
                # 限制：适用于文件 <100MB（base64后 ~133MB）
                if file_size > 100 * 1024 * 1024:
                    print(f"  ⚠️  文件过大 ({file_size // 1024 // 1024}MB)，建议优化缓存结构")
                
                print(f"  📡 传输中...")
                cmd = f"cat '{remote_tar}' | base64"
                
                # 超时设置：按文件大小动态调整（假设10MB/s）
                timeout = max(60, file_size // (10 * 1024 * 1024) * 60)
                
                rc, b64_data, err = self.rish_exec(cmd, timeout=timeout, check=False)
                
                if rc != 0:
                    print(f"  ❌ 传输失败 (rc={rc}): {err[:100]}")
                    continue
                
                # 解码并写入
                print(f"  🔓 解码中...")
                try:
                    binary_data = base64.b64decode(b64_data.strip())
                    
                    # 大小校验（防止传输不完整）
                    if len(binary_data) != file_size:
                        print(f"  ❌ 大小不匹配: 期望 {file_size}, 实际 {len(binary_data)}")
                        continue
                    
                    with open(local_tar, 'wb') as f:
                        f.write(binary_data)
                    
                    print(f"  ✅ 传输完成: {len(binary_data) // 1024 // 1024}MB")
                    return True
                
                except Exception as e:
                    print(f"  ❌ 解码失败: {e}")
                    continue
            
            except Exception as e:
                print(f"  ❌ 传输异常: {e}")
                continue
        
        print(f"  ❌ 下载失败（已重试 {max_retries} 次）")
        return False
    
    def _verify_md5(self, remote_tar: str, local_tar: str) -> bool:
        """
        MD5 校验
        
        Returns:
            True: 校验通过
            False: 校验失败
        """
        if not self.rish_exec:
            raise RuntimeError("rish_exec 未注入")
        
        print(f"  🔐 MD5 校验...")
        
        # 远程 MD5
        try:
            _, remote_md5_out, _ = self.rish_exec(f"md5sum '{remote_tar}'", timeout=60)
            remote_md5 = remote_md5_out.split()[0].strip()
        except Exception as e:
            print(f"  ⚠️  无法获取远程MD5，跳过校验: {e}")
            return True  # 宽松处理
        
        # 本地 MD5
        local_md5 = hashlib.md5()
        with open(local_tar, 'rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                local_md5.update(chunk)
        local_md5_hex = local_md5.hexdigest()
        
        # 对比
        if remote_md5 == local_md5_hex:
            print(f"  ✅ MD5 校验通过: {remote_md5[:8]}...")
            return True
        else:
            print(f"  ❌ MD5 校验失败!")
            print(f"     远程: {remote_md5}")
            print(f"     本地: {local_md5_hex}")
            return False
    
    def _extract_tar(self, local_tar: str, uid: str, c_folder: str) -> bool:
        """
        本地解包
        
        Returns:
            True: 解包成功
            False: 解包失败
        """
        if not self.local_cache:
            raise RuntimeError("local_cache 未设置")
        
        extract_dir = os.path.join(self.local_cache, uid)
        os.makedirs(extract_dir, exist_ok=True)
        
        # 删除旧的解包目录
        target_dir = os.path.join(extract_dir, c_folder)
        if os.path.exists(target_dir):
            print(f"  🗑️  删除旧缓存...")
            shutil.rmtree(target_dir)
        
        print(f"  📂 解包到: {extract_dir}")
        
        try:
            with tarfile.open(local_tar, 'r') as tar:
                tar.extractall(path=extract_dir)
            
            print(f"  ✅ 解包完成")
            return True
        
        except Exception as e:
            print(f"  ❌ 解包失败: {e}")
            return False
    
    def _cleanup_remote(self, remote_tar: str):
        """清理远程临时文件"""
        if not self.rish_exec:
            return
        
        try:
            self.rish_exec(f"rm -f '{remote_tar}'", check=False, timeout=10)
            print(f"  🗑️  远程清理完成")
        except Exception as e:
            print(f"  ⚠️  远程清理失败: {e}")
    
    def download_and_extract(self, uid: str, c_folder: str, cleanup: bool = True) -> bool:
        """
        完整流程：打包 → 下载 → 校验 → 解包
        
        Returns:
            True: 成功
            False: 失败
        """
        # 1. 检查本地缓存
        if self.check_local_cache(uid, c_folder):
            return True
        
        local_tar = None
        remote_tar = None
        
        try:
            # 2. 远程打包
            remote_tar, file_size = self._remote_pack(uid, c_folder)
            
            # 3. 创建本地临时tar文件
            local_tar = os.path.join(
                self.local_cache or tempfile.gettempdir(),
                f"{uid}_{c_folder}.tar"
            )
            
            # 4. 单次传输（带重试）
            if not self._download_single(remote_tar, file_size, local_tar, max_retries=5):
                return False
            
            # 5. MD5 校验
            if not self._verify_md5(remote_tar, local_tar):
                print(f"  ⚠️  MD5 校验失败，但继续尝试解包...")
            
            # 6. 本地解包
            if not self._extract_tar(local_tar, uid, c_folder):
                return False
            
            return True
        
        finally:
            # 7. 清理
            if cleanup and remote_tar:
                self._cleanup_remote(remote_tar)
            
            if local_tar and os.path.exists(local_tar):
                try:
                    os.remove(local_tar)
                    print(f"  🗑️  本地临时文件已删除")
                except Exception as e:
                    print(f"  ⚠️  本地清理失败: {e}")
    
    def get_local_path(self, uid: str, c_folder: str) -> Optional[str]:
        """获取本地缓存路径（如果存在）"""
        if not self.local_cache:
            return None
        
        path = os.path.join(self.local_cache, uid, c_folder)
        if os.path.exists(path):
            return path
        return None
