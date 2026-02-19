#!/usr/bin/env python3
"""entry.json 读取组件 - 增强版，支持解析失败时重试"""
import json
import time
from typing import Optional, Dict
from registry import registry

@registry.register("bili.entry_reader", "service", "read(uid: str, c_folder: str) -> Optional[Dict]")
class BiliEntryReader:
    def __init__(self):
        self.bili_root = "/storage/emulated/0/Android/data/tv.danmaku.bili/download"
        self.rish_exec = None
        self.max_retries = 3          # 解析失败时重试次数
        self.retry_delay_base = 0.5    # 初始延迟（秒）

    def set_rish_executor(self, rish_exec):
        self.rish_exec = rish_exec

    def read(self, uid: str, c_folder: str) -> Optional[Dict]:
        """读取并解析 entry.json，失败返回 None 并打印详细原因"""
        if not self.rish_exec:
            raise RuntimeError("rish_exec 未注入")
        path = f"{self.bili_root}/{uid}/{c_folder}/entry.json"

        for attempt in range(self.max_retries + 1):
            try:
                rc, out, err = self.rish_exec(f"cat '{path}'", check=False)
                if rc != 0:
                    print(f"  🔍 entry.json 读取失败 (rc={rc}): {c_folder} — {err[:100]}")
                    return None

                # 基本校验：空内容或明显不是 JSON 对象开头
                if not out:
                    print(f"  🔍 entry.json 内容为空: {c_folder}")
                    return None
                if not out.lstrip().startswith('{'):
                    print(f"  🔍 entry.json 内容不以 '{{' 开头，可能不是有效 JSON: {c_folder}")
                    return None

                # 尝试解析
                return json.loads(out)

            except json.JSONDecodeError as e:
                print(f"  🔍 entry.json JSON 解析错误 (尝试 {attempt+1}/{self.max_retries+1}): {c_folder} — {e}")
                if attempt < self.max_retries:
                    delay = self.retry_delay_base * (2 ** attempt)
                    print(f"  ⏳ 等待 {delay:.1f} 秒后重试...")
                    time.sleep(delay)
                else:
                    print(f"  ❌ 已达到最大重试次数，放弃: {c_folder}")
                    return None

            except Exception as e:
                print(f"  🔍 entry.json 未知错误: {c_folder} — {e}")
                return None

        return None  # 不会执行到这里