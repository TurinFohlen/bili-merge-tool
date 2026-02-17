#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据处理层 - 处理原始数据的解析、过滤和转换
版本: 2.0

职责:
- 解析ls输出和JSON数据
- 文件名清理和字节截断
- 标题提取和拼接
- 质量优先级选择
- 进度过滤

依赖: 仅Python标准库
"""

import re
from typing import List, Dict, Optional

# ============================================================================
# 常量配置
# ============================================================================

# 视频质量优先级列表（从高到低）
# 112=1080P+, 80=1080P, 64=720P, 32=480P, 16=360P
QUALITY_LIST = ['112', '80', '64', '32', '16']

# ============================================================================
# ls输出解析
# ============================================================================

def parse_ls_output(output: str) -> List[str]:
    """
    解析rish ls命令的输出
    
    Args:
        output: ls命令的原始输出
    
    Returns:
        清洗后的条目列表
    
    注意:
        - 输出可能包含\r, \x1b[0m等控制字符
        - 必须使用splitlines()而非split()
        - 需要strip()每一行并过滤空行
    """
    lines = output.splitlines()
    items = []
    
    for line in lines:
        # 清理控制字符和空白
        cleaned = line.strip()
        
        # 移除ANSI转义序列
        cleaned = re.sub(r'\x1b\[[0-9;]*m', '', cleaned)
        
        # 过滤空行
        if cleaned:
            items.append(cleaned)
    
    return items


# ============================================================================
# 文件名处理
# ============================================================================

def clean_filename(filename: str, max_bytes: int = 180) -> str:
    r"""
    清理文件名并按字节截断
    
    Args:
        filename: 原始文件名
        max_bytes: 最大字节数（默认180，为Linux文件名限制255减去扩展名和余量）
    
    Returns:
        清理并截断后的文件名
    
    注意:
        - 移除非法字符: \ / : * ? " < > |
        - 按UTF-8字节截断，避免截断多字节字符
        - 确保不为空，空字符串返回"untitled"
    """
    # 移除Windows/Linux不允许的字符
    cleaned = re.sub(r'[\\/:\*\?"<>\|]', '_', filename)
    
    # 移除前后空白
    cleaned = cleaned.strip()
    
    # 确保不为空
    if not cleaned:
        return "untitled"
    
    # 按字节截断（避免Errno 36: File name too long）
    encoded = cleaned.encode('utf-8')
    
    if len(encoded) <= max_bytes:
        return cleaned
    
    # 截断到max_bytes，确保不破坏UTF-8字符
    truncated = encoded[:max_bytes]
    
    # 尝试解码，如果失败则回退一个字节直到成功
    while truncated:
        try:
            return truncated.decode('utf-8')
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    
    return "untitled"


# ============================================================================
# 标题提取
# ============================================================================

def extract_title(entry: Dict) -> str:
    """
    从entry.json提取视频标题
    
    Args:
        entry: entry.json的解析结果
    
    Returns:
        清理后的标题
    
    逻辑:
        - 主标题: entry['title']
        - 分P标题: entry['page_data']['part'] 或 entry['index_title']
        - 如果分P标题存在且不同于主标题，则拼接为: "主标题 - 分P标题"
    """
    try:
        # 主标题
        title = entry.get('title', 'untitled')
        
        # 分P标题（优先使用page_data.part，其次index_title）
        page_data = entry.get('page_data', {})
        part = page_data.get('part') or entry.get('index_title', '')
        
        # 拼接标题
        if part and part != title:
            full_title = f"{title} - {part}"
        else:
            full_title = title
        
        # 清理文件名
        return clean_filename(full_title)
    
    except Exception:
        return "untitled"


# ============================================================================
# 质量选择
# ============================================================================

def select_best_quality(available_qualities: List[str]) -> Optional[str]:
    """
    根据优先级列表选择最高质量
    
    Args:
        available_qualities: 可用的质量列表
    
    Returns:
        最高质量编号，找不到返回None
    """
    for quality in QUALITY_LIST:
        if quality in available_qualities:
            return quality
    
    return None


def set_quality_priority(quality_list: List[str]):
    """
    设置质量优先级列表
    
    Args:
        quality_list: 质量列表，从高到低
    """
    global QUALITY_LIST
    QUALITY_LIST = quality_list


# ============================================================================
# 进度过滤
# ============================================================================

def filter_completed(c_folders: List[str], progress: Dict[str, bool]) -> List[str]:
    """
    过滤已完成的视频
    
    Args:
        c_folders: 所有c_*文件夹列表
        progress: 进度字典 {c_folder: True}
    
    Returns:
        未完成的c_*文件夹列表
    """
    return [c for c in c_folders if not progress.get(c, False)]


# ============================================================================
# 数据验证
# ============================================================================

def is_valid_uid(uid: str) -> bool:
    """
    验证UID是否有效（纯数字）
    
    Args:
        uid: UID字符串
    
    Returns:
        是否有效
    """
    return uid.isdigit()


def is_valid_c_folder(c_folder: str) -> bool:
    """
    验证c_*文件夹名是否有效
    
    Args:
        c_folder: 文件夹名
    
    Returns:
        是否有效
    """
    return c_folder.startswith('c_') and len(c_folder) > 2


def validate_entry_json(entry: Dict) -> bool:
    """
    验证entry.json数据是否有效
    
    Args:
        entry: entry.json解析结果
    
    Returns:
        是否有效
    """
    # 至少需要有title字段
    return isinstance(entry, dict) and 'title' in entry


# ============================================================================
# 统计辅助
# ============================================================================

class VideoStats:
    """视频统计信息"""
    
    def __init__(self):
        self.total = 0
        self.success = 0
        self.failed = 0
        self.skipped = 0
    
    def add_success(self):
        """添加成功计数"""
        self.success += 1
        self.total += 1
    
    def add_failed(self):
        """添加失败计数"""
        self.failed += 1
        self.total += 1
    
    def add_skipped(self):
        """添加跳过计数"""
        self.skipped += 1
    
    def __str__(self) -> str:
        """字符串表示"""
        return (
            f"总计: {self.total}, "
            f"成功: {self.success}, "
            f"失败: {self.failed}, "
            f"跳过: {self.skipped}"
        )


# ============================================================================
# 状态管理（可选）
# ============================================================================

class VideoState:
    """视频处理状态"""
    PENDING = "pending"        # 待处理
    COPYING = "copying"        # 正在复制
    MERGING = "merging"        # 正在合并
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"          # 失败


class VideoTask:
    """视频任务信息"""
    
    def __init__(self, uid: str, c_folder: str, title: str, quality: str):
        self.uid = uid
        self.c_folder = c_folder
        self.title = title
        self.quality = quality
        self.state = VideoState.PENDING
        self.error = None
    
    def set_state(self, state: str, error: Optional[str] = None):
        """设置状态"""
        self.state = state
        self.error = error
    
    def __repr__(self) -> str:
        return f"VideoTask({self.c_folder}, {self.title}, {self.state})"


# ============================================================================
# 测试函数
# ============================================================================

def run_tests():
    """运行简单的单元测试"""
    print("测试数据处理层...")
    
    # 测试1: parse_ls_output
    output1 = "12345678\n87654321\n11111111"
    result1 = parse_ls_output(output1)
    assert result1 == ["12345678", "87654321", "11111111"], "正常输出解析失败"
    print("✓ ls输出解析正确")
    
    # 测试2: clean_filename
    result2 = clean_filename(r'测试视频:<>?*"|\\/')
    assert all(c not in result2 for c in r':<>?*"|\/'), "非法字符未清理"
    print(f"✓ 文件名清理正确: {result2}")
    
    # 测试3: 字节截断
    result3 = clean_filename("a" * 200, max_bytes=100)
    assert len(result3.encode('utf-8')) <= 100, "字节截断失败"
    print(f"✓ 字节截断正确: {len(result3.encode('utf-8'))} <= 100")
    
    # 测试4: extract_title
    entry4 = {
        "title": "测试视频",
        "page_data": {"part": "P1"}
    }
    result4 = extract_title(entry4)
    assert "测试视频" in result4 and "P1" in result4, "标题提取失败"
    print(f"✓ 标题提取正确: {result4}")
    
    # 测试5: select_best_quality
    result5 = select_best_quality(['64', '112', '32'])
    assert result5 == '112', "质量选择失败"
    print(f"✓ 质量选择正确: {result5}")
    
    # 测试6: filter_completed
    progress6 = {'c_1': True, 'c_2': True}
    result6 = filter_completed(['c_1', 'c_2', 'c_3'], progress6)
    assert result6 == ['c_3'], "进度过滤失败"
    print(f"✓ 进度过滤正确: {result6}")
    
    # 测试7: VideoStats
    stats7 = VideoStats()
    stats7.add_success()
    stats7.add_failed()
    stats7.add_skipped()
    assert stats7.total == 2 and stats7.success == 1, "统计失败"
    print(f"✓ 统计正确: {stats7}")
    
    print("\n所有测试通过!")


if __name__ == "__main__":
    run_tests()
