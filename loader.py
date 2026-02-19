#!/usr/bin/env python3
"""
全库引入者·智能版 —— 自动扫描并导入所有组件模块。
"""

import os
import sys
import importlib.util
from pathlib import Path

# 要扫描的顶层包名列表
PACKAGES = [
    'services',
    'processors',
    'uis',
    'exporters',
]

def import_module_from_file(py_file: Path, package_name: str, rel_path: Path):
    """动态导入单个 .py 文件作为模块"""
    # 将相对路径转换为模块点号分隔名
    sub_module = ".".join(rel_path.with_suffix('').parts)
    module_name = f"{package_name}.{sub_module}"
    
    spec = importlib.util.spec_from_file_location(module_name, py_file)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[module_name] = module
        return True
    return False

def scan_and_import():
    """扫描所有指定包目录，导入每个 .py 文件（非 __init__）"""
    root_dir = Path(__file__).parent
    imported = [] # 存储 (depth, module_name)
    
    for pkg in PACKAGES:
        pkg_dir = root_dir / pkg
        if not pkg_dir.exists():
            continue
        
        # 递归扫描
        for py_file in pkg_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            try:
                # 获取相对于当前包（pkg）的路径
                rel_path = py_file.relative_to(pkg_dir)
                # 计算深度：顶层为 0，每进一级目录 +1
                depth = len(rel_path.parts) - 1
                
                if import_module_from_file(py_file, pkg, rel_path):
                    mod_full_name = f"{pkg}.{'.'.join(rel_path.with_suffix('').parts)}"
                    imported.append((depth, mod_full_name))
            except Exception as e:
                print(f"⚠️ 导入失败 {py_file.name}: {e}")
    
    return imported

# ========== 执行自动扫描导入 ==========
loaded_modules = scan_and_import()
print(f"✅ 全库智能加载完成，已注册 {len(loaded_modules)} 个组件")

# --- 核心修改部分：严格按照要求进行树状打印 ---
from collections import defaultdict

def build_tree(module_list):
    """将模块名列表转换为嵌套字典树"""
    tree = lambda: defaultdict(tree)
    root = tree()
    for _, mod in module_list:
        parts = mod.split(".")
        node = root
        for part in parts:
            node = node[part]
    return root

def print_tree(node, prefix="", name=""):
    """递归打印树状结构"""
    if name:
        print(prefix + "└── " + name)
        prefix += "        "
    children = list(node.keys())
    for child in children:
        print_tree(node[child], prefix, child)

# ========== 执行自动扫描导入 ==========
loaded_modules = scan_and_import()
print(f"✅ 全库智能加载完成，已注册 {len(loaded_modules)} 个组件\n")

# 构建并打印树
tree = build_tree(loaded_modules)
print_tree(tree)
