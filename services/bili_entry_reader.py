#!/usr/bin/env python3
"""entry.json 读取组件"""
import json
from typing import Optional, Dict
from registry import registry

@registry.register("bili.entry_reader", "service", "read(uid: str, c_folder: str) -> Optional[Dict]")
class BiliEntryReader:
    def __init__(self):
        self.bili_root = "/storage/emulated/0/Android/data/tv.danmaku.bili/download"
        self.rish_exec = None
    
    def set_rish_executor(self, rish_exec):
        self.rish_exec = rish_exec
    
    def read(self, uid: str, c_folder: str) -> Optional[Dict]:
        """读取并解析 entry.json，失败返回 None 并打印详细原因"""
        if not self.rish_exec:
            raise RuntimeError("rish_exec 未注入")
        path = f"{self.bili_root}/{uid}/{c_folder}/entry.json"
        try:
            rc, out, err = self.rish_exec(f"cat '{path}'", check=False)
            if rc != 0:
                print(f"  🔍 entry.json 读取失败 (rc={rc}): {c_folder} — {err[:100]}")
                return None
            return json.loads(out)
        except json.JSONDecodeError as e:
            print(f"  🔍 entry.json JSON 解析错误: {c_folder} — {e}")
            return None
        except Exception as e:
            print(f"  🔍 entry.json 未知错误: {c_folder} — {e}")
            return None
