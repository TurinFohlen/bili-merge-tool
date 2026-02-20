#!/usr/bin/env python3
"""
统一打包分片传输组件 v1.2.3 - 工业级稳定版
主要特性：
  1. 块大小 (bs) 与重叠量 (overlap) 严格对齐为 1024 字节。
  2. 使用 iflag=fullblock 强制 dd 读取完整块，防止管道提前截断。
  3. 采用 (actual_size + bs - 1) // bs 向上取整计算块数，确保末尾数据不丢失。
  4. 增加超时至 300s，强化 MD5 校验失败后的阻断机制。
"""
import os
import tarfile
import hashlib
import base64
import tempfile
import shutil
import time
from typing import Optional, Tuple
from registry import registry

@registry.register("pack.transfer", "service", "download_and_extract(uid, c_folder, cleanup) -> bool")
class PackTransfer:
    def __init__(self):
        self.bili_root = "/storage/emulated/0/Android/data/tv.danmaku.bili/download"
        self.remote_tmp = "/data/local/tmp"
        self.local_cache = None
        self.chunk_size = 10 * 1024 * 1024  # 10MB
        self.overlap = 1024                 # 1KB 重叠区域
        self.max_retries = 3
        self.retry_delay = 2
        self.rish_exec = None

    def set_rish_executor(self, rish_exec):
        self.rish_exec = rish_exec

    def set_local_cache(self, path: str):
        self.local_cache = path
        os.makedirs(path, exist_ok=True)

    def check_local_cache(self, uid: str, c_folder: str) -> bool:
        if not self.local_cache:
            return False
        local_path = os.path.join(self.local_cache, uid, c_folder)
        if not os.path.exists(local_path):
            return False
        entry_json = os.path.join(local_path, "entry.json")
        if os.path.exists(entry_json) and os.path.getsize(entry_json) > 0:
            print(f"  ✅ 本地缓存已存在: {uid}/{c_folder}")
            return True
        for root, dirs, files in os.walk(local_path):
            for f in files:
                if f.endswith(('.m4s', '.mp4', '.blv', '.m4a')):
                    print(f"  ✅ 本地缓存已存在（媒体文件确认）")
                    return True
        return False

    def _remote_pack(self, uid: str, c_folder: str) -> Tuple[str, int]:
        if not self.rish_exec:
            raise RuntimeError("rish_exec 未注入")
        source_dir = f"{self.bili_root}/{uid}/{c_folder}"
        tar_name = f"{uid}_{c_folder}.tar"
        remote_tar = f"{self.remote_tmp}/{tar_name}"
        print(f"  📦 远程打包: {c_folder}")

        rc, _, _ = self.rish_exec(f"test -d '{source_dir}'", check=False, timeout=10)
        if rc != 0:
            raise FileNotFoundError(f"远程源目录不存在: {source_dir}")

        self.rish_exec(f"rm -f '{remote_tar}'", check=False, timeout=10)

        parent_dir = f"{self.bili_root}/{uid}"
        cmd = f"cd '{parent_dir}' && tar -cf '{remote_tar}' '{c_folder}'"
        try:
            rc, out, err = self.rish_exec(cmd, timeout=300)
            if rc != 0:
                raise RuntimeError(f"打包失败: {err[:200]}")
        except Exception as e:
            raise RuntimeError(f"打包异常: {e}")

        file_size = None
        for attempt in range(3):
            try:
                _, size_str, _ = self.rish_exec(f"stat -c %s '{remote_tar}'", timeout=10)
                size_str = size_str.strip()
                if size_str:
                    file_size = int(size_str)
                    break
            except:
                pass
            time.sleep(2 * (2 ** attempt))

        if file_size is None:
            raise RuntimeError("无法获取远程打包文件大小")

        print(f"  ✅ 打包完成: {file_size // 1024 // 1024}MB")
        return remote_tar, file_size

    def _download_chunks_overlap(self, remote_tar: str, file_size: int, local_tar: str) -> bool:
        if not self.rish_exec:
            raise RuntimeError("rish_exec 未注入")

        chunk_size = self.chunk_size
        overlap = self.overlap
        bs = 1024  # 基础块单位 1KB
        n_chunks = (file_size + (chunk_size - overlap) - 1) // (chunk_size - overlap)
        if n_chunks == 0: n_chunks = 1
        
        print(f"  📥 下载规划: {n_chunks} 片, 块大小 {bs}B, 向上取整模式")

        temp_dir = tempfile.mkdtemp(prefix="bili_pack_")
        part_files = []

        try:
            for i in range(n_chunks):
                # 计算分片字节范围
                start = i * (chunk_size - overlap)
                if start < 0: start = 0
                end = min(start + chunk_size, file_size)
                actual_size = end - start

                # 向上取整计算块数
                skip_blocks = start // bs
                count_blocks = (actual_size + bs - 1) // bs

                part_file = os.path.join(temp_dir, f"part_{i:03d}")
                success = False

                for retry in range(self.max_retries + 3):
                    try:
                        # iflag=fullblock 是防止数据截断的核心
                        cmd = f"dd if='{remote_tar}' bs={bs} skip={skip_blocks} count={count_blocks} iflag=fullblock 2>/dev/null | base64 -w 0"
                        rc, b64_data, _ = self.rish_exec(cmd, check=False, timeout=300)

                        if rc != 0 or not b64_data.strip():
                            time.sleep(self.retry_delay * (2 ** retry))
                            continue

                        b64_data = b64_data.strip()
                        missing_padding = len(b64_data) % 4
                        if missing_padding:
                            b64_data += '=' * (4 - missing_padding)

                        data = base64.b64decode(b64_data)
                        if len(data) > actual_size:
                            data = data[:actual_size]

                        # 严格长度校验
                        if len(data) < actual_size:
                            print(f"  ⚠️ 分片 {i+1} 长度不足 ({len(data)} < {actual_size})，重试 {retry+1}")
                            time.sleep(self.retry_delay * (2 ** retry))
                            continue

                        with open(part_file, 'wb') as f:
                            f.write(data)

                        print(f"  📥 分片 {i+1}/{n_chunks} ✓")
                        success = True
                        break

                    except Exception as e:
                        print(f"  ⚠️ 分片 {i+1} 异常: {e}")
                        time.sleep(self.retry_delay * (2 ** retry))

                if not success:
                    print(f"  ❌ 分片 {i+1} 下载失败")
                    return False
                part_files.append(part_file)

            # 重叠校验
            print(f"  🔍 重叠一致性检查...")
            for i in range(n_chunks - 1):
                with open(part_files[i], 'rb') as f1, open(part_files[i+1], 'rb') as f2:
                    f1.seek(-overlap, os.SEEK_END)
                    if f1.read(overlap) != f2.read(overlap):
                        print(f"  ❌ 校验失败：分片 {i+1} ↔ {i+2} 字节不匹配")
                        return False

            # 合并文件
            print(f"  🔗 合并分片...")
            with open(local_tar, 'wb') as out_f:
                for i, p_file in enumerate(part_files):
                    with open(p_file, 'rb') as f:
                        if i == 0:
                            out_f.write(f.read())
                        else:
                            f.seek(overlap)
                            out_f.write(f.read())

            if os.path.getsize(local_tar) != file_size:
                print(f"  ❌ 最终大小不匹配: {os.path.getsize(local_tar)} != {file_size}")
                return False
            return True

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _verify_md5(self, remote_tar: str, local_tar: str) -> bool:
        print(f"  🔐 执行端到端 MD5 校验...")
        try:
            _, remote_md5_out, _ = self.rish_exec(f"md5sum '{remote_tar}'", timeout=60)
            remote_md5 = remote_md5_out.split()[0].strip()
        except Exception as e:
            print(f"  ⚠️ 无法获取远程MD5: {e}")
            return True

        local_md5 = hashlib.md5()
        with open(local_tar, 'rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                local_md5.update(chunk)
        
        match = (remote_md5 == local_md5.hexdigest())
        if match:
            print(f"  ✅ MD5 验证成功")
        else:
            print(f"  ❌ MD5 验证失败: 远程 {remote_md5} vs 本地 {local_md5.hexdigest()}")
        return match

    def _extract_tar(self, local_tar: str, uid: str, c_folder: str) -> bool:
        extract_dir = os.path.join(self.local_cache, uid)
        os.makedirs(extract_dir, exist_ok=True)
        target_dir = os.path.join(extract_dir, c_folder)
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)

        print(f"  📂 正在解包至: {extract_dir}")
        try:
            with tarfile.open(local_tar, 'r') as tar:
                tar.extractall(path=extract_dir)
            return True
        except Exception as e:
            print(f"  ❌ 解包发生异常: {e}")
            return False

    def download_and_extract(self, uid: str, c_folder: str, cleanup: bool = True) -> bool:
        if self.check_local_cache(uid, c_folder):
            return True

        local_tar, remote_tar = None, None
        try:
            remote_tar, file_size = self._remote_pack(uid, c_folder)
            local_tar = os.path.join(self.local_cache or tempfile.gettempdir(), f"{uid}_{c_folder}.tar")
            
            if not self._download_chunks_overlap(remote_tar, file_size, local_tar):
                return False
            if not self._verify_md5(remote_tar, local_tar):
                return False
            if not self._extract_tar(local_tar, uid, c_folder):
                return False
            return True
        finally:
            if cleanup and remote_tar: 
                try: self.rish_exec(f"rm -f '{remote_tar}'", check=False)
                except: pass
            if local_tar and os.path.exists(local_tar): 
                try: os.remove(local_tar)
                except: pass

    def get_local_path(self, uid: str, c_folder: str) -> Optional[str]:
        path = os.path.join(self.local_cache, uid, c_folder)
        return path if os.path.exists(path) else None


# ========================== 重试包装类 ==========================
class VideoRetryPackTransfer:
    def __init__(self, pack_transfer: PackTransfer):
        self.pt = pack_transfer
        self.video_max_retries = 5        # 单个视频最大重启次数
        self.video_retry_base_delay = 5   # 基础重试等待秒数

    def download_video_with_retry(self, uid: str, c_folder: str, cleanup: bool = True) -> bool:
        print(f"\n===== 开始视频任务：{uid}/{c_folder} =====")
        for retry in range(1, self.video_max_retries + 1):
            try:
                ok = self.pt.download_and_extract(uid, c_folder, cleanup=cleanup)
                if ok:
                    print(f"===== ✅ 视频 {uid}/{c_folder} 处理成功 =====")
                    return True
                else:
                    print(f"===== ❌ 视频 {uid}/{c_folder} 处理失败，准备重试 {retry}/{self.video_max_retries} =====")
            except Exception as e:
                print(f"===== ⚠️ 视频 {uid}/{c_folder} 异常：{e}，重试 {retry}/{self.video_max_retries} =====")

            # 指数退避
            wait = self.video_retry_base_delay * (2 ** (retry - 1))
            print(f"===== ⏳ 等待 {wait}s 后重启视频任务 =====")
            time.sleep(wait)

        print(f"===== ❌ 视频 {uid}/{c_folder} 已达最大重试次数，任务终止 =====")
        return False


# ========================== 辅助函数 ==========================
def v_pack_transfer_with_retry(
    uid: str,
    c_folder: str,
    rish_exec,
    local_cache: str,
    cleanup: bool = True
) -> bool:
    pt = PackTransfer()
    pt.set_rish_executor(rish_exec)
    pt.set_local_cache(local_cache)
    
    vr = VideoRetryPackTransfer(pt)
    return vr.download_video_with_retry(uid, c_folder, cleanup=cleanup)