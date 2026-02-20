#!/usr/bin/env python3
"""entry.json 读取组件 - v3.1.1 容错增强版"""
import json
from typing import Optional, Dict
from registry import registry

@registry.register("bili.entry_reader", "service", "read(uid: str, c_folder: str) -> Optional[Dict]")
class BiliEntryReader:
    def __init__(self):
        self.bili_root = "/storage/emulated/0/Android/data/tv.danmaku.bili/download"
        self.rish_exec = None
        
        # 统计分类
        self.stats = {
            'empty_file': 0,      # 空文件
            'invalid_json': 0,    # JSON格式错误
            'missing_file': 0,    # 文件不存在
            'other_error': 0,     # 其他错误
        }
    
    def set_rish_executor(self, rish_exec):
        self.rish_exec = rish_exec
    
    def read(self, uid: str, c_folder: str) -> Optional[Dict]:
        """
        读取并解析 entry.json，失败返回 None 并打印详细原因
        
        v3.1.1 改进：
          - 增加内容校验（检查是否为空或无效）
          - 错误分类统计
          - 更友好的错误提示
        """
        if not self.rish_exec:
            raise RuntimeError("rish_exec 未注入")
        
        path = f"{self.bili_root}/{uid}/{c_folder}/entry.json"
        
        try:
            rc, out, err = self.rish_exec(f"cat '{path}'", check=False, timeout=15)
            
            # 文件不存在
            if rc != 0:
                if "no such file" in err.lower():
                    print(f"  ⚠️  entry.json 不存在: {c_folder}")
                    self.stats['missing_file'] += 1
                else:
                    print(f"  🔍 entry.json 读取失败 (rc={rc}): {c_folder} — {err[:100]}")
                    self.stats['other_error'] += 1
                return None
            
            # 内容为空
            if not out or not out.strip():
                print(f"  ⚠️  entry.json 为空文件（数据缺失）: {c_folder}")
                self.stats['empty_file'] += 1
                return None
            
            # 基础格式校验
            out = out.strip()
            if not out.startswith('{'):
                print(f"  ⚠️  entry.json 格式异常（非JSON）: {c_folder} — 开头: {out[:20]}")
                self.stats['invalid_json'] += 1
                return None
            
            # 解析JSON
            data = json.loads(out)
            
            # 内容完整性校验
            if not isinstance(data, dict):
                print(f"  ⚠️  entry.json 内容无效（非对象）: {c_folder}")
                self.stats['invalid_json'] += 1
                return None
            
            # 检查必需字段（宽松检查，仅警告）
            if 'title' not in data or 'type_tag' not in data:
                print(f"  ⚠️  entry.json 缺少必需字段: {c_folder}")
            
            return data
        
        except json.JSONDecodeError as e:
            print(f"  ⚠️  entry.json JSON 解析错误: {c_folder} — {e}")
            print(f"     内容预览: {out[:100] if out else '(空)'}")
            self.stats['invalid_json'] += 1
            return None
        
        except Exception as e:
            print(f"  ❌ entry.json 未知错误: {c_folder} — {e}")
            self.stats['other_error'] += 1
            return None
    
    def print_stats(self):
        """打印统计信息"""
        total = sum(self.stats.values())
        if total == 0:
            return
        
        print("\n" + "─" * 60)
        print("entry.json 错误分类统计：")
        print("─" * 60)
        print(f"  · 空文件（数据缺失）：{self.stats['empty_file']}")
        print(f"  · JSON 格式错误：{self.stats['invalid_json']}")
        print(f"  · 文件不存在：{self.stats['missing_file']}")
        print(f"  · 其他错误：{self.stats['other_error']}")
        print(f"  总计：{total}")
        print("─" * 60)
