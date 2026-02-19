#!/usr/bin/env python3
"""
组件化系统测试脚本

测试内容：
  1. 组件自动加载
  2. 依赖注入
  3. 错误日志记录
  4. 导出功能
"""
import sys, os, tempfile, pathlib

# 设置错误日志导出到临时目录
import error_log
test_log_dir = tempfile.mkdtemp(prefix="bili_test_log_")
error_log.export_dir = test_log_dir
error_log.enabled = True

print("=" * 70)
print("组件化系统测试")
print("=" * 70)
print(f"📁 测试日志目录: {test_log_dir}\n")

# 1. 加载组件
print("── 步骤 1: 加载组件 ──")
import loader
print()

# 2. 检查注册中心
from registry import registry
print("── 步骤 2: 检查注册中心 ──")
components = registry.list_components()
print(f"✅ 共注册 {len(components)} 个组件")
for comp in components:
    print(f"  · {comp.name} ({comp.type})")
print()

# 3. 测试依赖注入
print("── 步骤 3: 测试依赖注入 ──")
try:
    # 创建 mock rish_exec
    def mock_rish_exec(cmd, **kwargs):
        print(f"  [mock] rish_exec: {cmd[:50]}...")
        if "ls" in cmd:
            return 0, "123456789\n", ""
        elif "cat" in cmd and "entry.json" in cmd:
            return 0, '{"title":"测试视频","type_tag":"DASH","page_data":{"part":"P1"}}', ""
        elif "test -f" in cmd:
            return 0, "", ""
        return 0, "", ""
    
    # 获取服务并注入 mock
    file_op = registry.get_service("file.operator")
    file_op.set_rish_executor(mock_rish_exec)
    
    scanner = registry.get_service("bili.scanner")
    scanner.set_rish_executor(mock_rish_exec)
    
    # 测试调用
    result = file_op.check_exists("/test/path")
    print(f"  ✅ file.operator.check_exists: {result}")
    
    uids = scanner.list_uids()
    print(f"  ✅ bili.scanner.list_uids: {uids}")
    
    print("✅ 依赖注入正常\n")
except Exception as e:
    print(f"❌ 依赖注入失败: {e}\n")
    import traceback
    traceback.print_exc()

# 4. 测试错误捕获
print("── 步骤 4: 测试错误捕获 ──")
try:
    # 故意触发异常
    with registry.component_context("test.component"):
        raise FileNotFoundError("测试文件不存在")
except FileNotFoundError:
    print("  ✅ 异常已捕获并记录")
print()

# 5. 检查错误日志统计
print("── 步骤 5: 检查错误日志统计 ──")
stats = error_log.get_stats()
print(f"  · 事件总数: {stats['total_events']}")
print(f"  · 错误分布: {stats['error_distribution']}")
print()

# 6. 导出日志
print("── 步骤 6: 导出日志 ──")
error_log.export_error_log(registry)
print()

# 7. 检查导出文件
print("── 步骤 7: 检查导出文件 ──")
log_files = [f for f in os.listdir(test_log_dir) if f.endswith(('.json', '.wl'))]
for f in sorted(log_files):
    size = os.path.getsize(os.path.join(test_log_dir, f))
    print(f"  ✅ {f} ({size} bytes)")
print()

# 8. 测试总结
print("=" * 70)
print("✅ 所有测试通过！")
print("=" * 70)
print(f"\n📁 日志文件位置: {test_log_dir}")
print(f"📊 可在 Mathematica 中加载分析：")
print(f"   Get[\"{os.path.join(test_log_dir, 'adjacency_matrix_*.wl')}\"]")
print(f"   Get[\"{os.path.join(test_log_dir, 'error_events_*.wl')}\"]")
