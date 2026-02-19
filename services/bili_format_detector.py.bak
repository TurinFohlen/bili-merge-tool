#!/usr/bin/env python3
"""缓存格式检测组件（DASH / MP4 / BLV）"""
from registry import registry

# 格式常量
FMT_DASH = "dash"
FMT_MP4 = "mp4"
FMT_BLV = "blv"
FMT_UNKNOWN = "unknown"

QUALITY_LABEL = {"112":"1080P+","80":"1080P","64":"720P","32":"480P","16":"360P"}

@registry.register("bili.format_detector", "service", "detect(uid: str, c_folder: str, quality: str) -> str")
class BiliFormatDetector:
    def __init__(self):
        self.bili_root = "/storage/emulated/0/Android/data/tv.danmaku.bili/download"
        self.rish_exec = None
    
    def set_rish_executor(self, rish_exec):
        self.rish_exec = rish_exec
    
    def detect(self, uid: str, c_folder: str, quality: str) -> str:
        """探测格式：dash / mp4 / blv / unknown"""
        if not self.rish_exec:
            raise RuntimeError("rish_exec 未注入")
        base = f"{self.bili_root}/{uid}/{c_folder}/{quality}"
        for fmt, fname in [(FMT_DASH,"video.m4s"),(FMT_MP4,"video.mp4"),(FMT_BLV,"index.json")]:
            try:
                rc, _, _ = self.rish_exec(f"test -f '{base}/{fname}'", check=False, timeout=15)
                if rc == 0:
                    return fmt
            except Exception:
                continue
        return FMT_UNKNOWN
    
    def quality_label(self, q: str) -> str:
        """质量标签"""
        l = QUALITY_LABEL.get(q)
        return f"{q} ({l})" if l else q
