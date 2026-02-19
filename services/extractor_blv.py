#!/usr/bin/env python3
"""BLV 格式提取器（复制所有 .blv 分段）- 增强版，支持递归查找和根目录模式"""
import os
import json
import re
from typing import List, Tuple
from registry import registry

@registry.register("extractor.blv", "service", "extract(uid, c_folder, quality, temp_dir) -> bool")
class ExtractorBlv:
    def __init__(self):
        self.bili_root = "/storage/emulated/0/Android/data/tv.danmaku.bili/download"
        self.file_operator = None
        self.rish_exec = None
        self.max_depth = 5  # 递归最大深度

    def set_dependencies(self, file_operator, rish_exec):
        self.file_operator = file_operator
        self.rish_exec = rish_exec

    def _parse_ls(self, stdout: str) -> List[str]:
        result = []
        for line in stdout.splitlines():
            name = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
            if name:
                result.append(name)
        return result

    def _find_all_blv_files(self, start_dir: str, max_depth: int = 5) -> List[str]:
        """
        递归查找所有 .blv 文件，返回按文件名中的数字排序的完整路径列表
        """
        from collections import deque

        blv_files = []
        queue = deque([(start_dir, 0)])  # (当前目录, 当前深度)

        while queue:
            cur_dir, depth = queue.popleft()
            if depth > max_depth:
                continue

            try:
                rc, out, _ = self.rish_exec(f"ls -1 '{cur_dir}'", timeout=15)
                if rc != 0:
                    continue

                items = self._parse_ls(out)
                subdirs = []

                for item in items:
                    item_path = f"{cur_dir}/{item}"
                    # 检查是否为目录
                    rc2, _, _ = self.rish_exec(f"test -d '{item_path}'", check=False)
                    if rc2 == 0:
                        subdirs.append(item_path)
                        continue

                    # 检查是否为文件且后缀为 .blv
                    if item.endswith('.blv'):
                        # 验证文件确实存在
                        if self.file_operator.check_exists(item_path):
                            blv_files.append(item_path)

                # 将子目录加入队列
                for sd in subdirs:
                    queue.append((sd, depth + 1))

            except Exception as e:
                print(f"  ⚠️  搜索 {cur_dir} 失败: {e}")
                continue

        # 按文件名中的数字排序（例如 0.blv, 1.blv ...）
        def extract_number(filename):
            base = os.path.basename(filename)
            num_part = base.split('.')[0]
            try:
                return int(num_part)
            except ValueError:
                return float('inf')  # 无法解析的放最后

        blv_files.sort(key=extract_number)
        return blv_files

    def _read_index_json(self, base_dir: str) -> dict:
        """从指定目录读取 index.json（递归查找第一个找到的）"""
        # 简单实现：从 start_dir 开始查找 index.json
        from collections import deque
        queue = deque([(base_dir, 0)])
        while queue:
            cur_dir, depth = queue.popleft()
            if depth > self.max_depth:
                continue
            try:
                rc, out, _ = self.rish_exec(f"ls -1 '{cur_dir}'", timeout=15)
                if rc != 0:
                    continue
                items = self._parse_ls(out)
                if 'index.json' in items:
                    # 读取 index.json
                    rc2, content, _ = self.rish_exec(f"cat '{cur_dir}/index.json'", timeout=15)
                    if rc2 == 0:
                        return json.loads(content)
                # 加入子目录继续搜索
                for item in items:
                    if item.isdigit():  # 只进入数字目录（质量目录）
                        queue.append((f"{cur_dir}/{item}", depth + 1))
            except:
                pass
        return None

    def _parse_index_json(self, index) -> List[str]:
        """从 index.json 提取分段文件名"""
        if not index:
            return []
        if isinstance(index, list):
            return [str(item) for item in index if str(item).endswith(".blv")]
        if not isinstance(index, dict):
            return []
        if "index" in index and isinstance(index["index"], list):
            return [str(item) for item in index["index"] if str(item).endswith(".blv")]
        if "segments" in index and isinstance(index["segments"], list):
            names = []
            for seg in index["segments"]:
                if isinstance(seg, dict) and "filename" in seg:
                    name = str(seg["filename"])
                    if name.endswith(".blv"):
                        names.append(name)
            return names
        return []

    def extract(self, uid: str, c_folder: str, quality: str, temp_dir: str) -> bool:
        """
        提取 BLV 分段到临时目录
        支持 quality='.' 表示从 c_folder 根目录开始递归查找
        """
        if quality == '.':
            start_dir = f"{self.bili_root}/{uid}/{c_folder}"
        else:
            start_dir = f"{self.bili_root}/{uid}/{c_folder}/{quality}"

        # 1. 递归查找所有 .blv 文件
        print(f"  🔍 递归查找 BLV 文件: {start_dir}")
        segments = self._find_all_blv_files(start_dir, self.max_depth)

        # 2. 后备：尝试从 index.json 获取顺序（如果存在）
        index_data = self._read_index_json(start_dir)
        if index_data:
            names_from_index = self._parse_index_json(index_data)
            if names_from_index:
                # 根据 index.json 中的文件名重建顺序，但文件可能不在同一个目录，需要定位
                # 简单做法：如果找到了 index.json，且它提供了顺序，我们就用这个顺序，
                # 但需要将文件名映射到实际路径。这里我们假设 index.json 中的文件名与递归找到的文件名一致，
                # 我们重新构造路径：基于 start_dir 拼接文件名，并验证存在性。
                ordered_segments = []
                for name in names_from_index:
                    # 尝试在 start_dir 下直接找，或在递归结果中匹配
                    candidate = f"{start_dir}/{name}"
                    if self.file_operator.check_exists(candidate):
                        ordered_segments.append(candidate)
                    else:
                        # 尝试在递归结果中查找
                        found = [s for s in segments if os.path.basename(s) == name]
                        if found:
                            ordered_segments.append(found[0])
                        else:
                            print(f"  ⚠️  index.json 中指定的文件 {name} 未找到，跳过")
                if ordered_segments:
                    segments = ordered_segments

        if not segments:
            print(f"❌ BLV：未找到分段文件: {c_folder}")
            return False

        print(f"ℹ️  BLV 分段数: {len(segments)}")
        for seg_path in segments:
            seg_name = os.path.basename(seg_path)
            dst = os.path.join(temp_dir, seg_name)
            if not self.file_operator.copy(seg_path, dst):
                print(f"❌ 复制分段失败: {seg_name}")
                return False

        return True