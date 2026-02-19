#!/usr/bin/env python3
"""测试错误日志系统（嵌套调用）"""
import sys, os, tempfile
import error_log

test_log_dir = tempfile.mkdtemp(prefix="bili_error_test_")
error_log.export_dir = test_log_dir
error_log.enabled = True

print("=" * 70)
print("错误日志系统测试（嵌套调用）")
print("=" * 70)
print(f"📁 日志目录: {test_log_dir}\n")

# 加载组件
import loader
from registry import registry

print("\n── 创建模拟组件 ──")

# 注册两个测试组件
@registry.register("test.caller", "service", "call() -> None")
class TestCaller:
    def call(self):
        """调用者组件"""
        print("  TestCaller.call()")
        # 在 component_context 中调用 callee
        with registry.component_context("test.caller"):
            callee = registry.get_service("test.callee")
            callee.do_work()

@registry.register("test.callee", "service", "do_work() -> None")
class TestCallee:
    def do_work(self):
        """被调用者组件（会抛出异常）"""
        print("  TestCallee.do_work()")
        with registry.component_context("test.callee"):
            raise FileNotFoundError("模拟文件不存在错误")

print("✅ 测试组件已注册\n")

print("── 执行嵌套调用（触发异常）──")
try:
    caller = registry.get_service("test.caller")
    caller.call()
except FileNotFoundError as e:
    print(f"  ✅ 异常已捕获: {e}\n")

print("── 错误日志统计 ──")
stats = error_log.get_stats()
print(f"  · 事件总数: {stats['total_events']}")
print(f"  · 错误分布: {stats['error_distribution']}\n")

print("── 导出日志 ──")
error_log.export_error_log(registry)
print()

print("── 检查导出文件 ──")
for f in sorted(os.listdir(test_log_dir)):
    if f.endswith(('.json', '.wl')):
        path = os.path.join(test_log_dir, f)
        size = os.path.getsize(path)
        print(f"  ✅ {f} ({size} bytes)")

print("\n" + "=" * 70)
print("✅ 错误日志测试完成！")
print("=" * 70)
print(f"\n📁 日志位置: {test_log_dir}")

# 读取并显示部分 JSON
import json
for f in os.listdir(test_log_dir):
    if f.startswith("error_events") and f.endswith(".json"):
        with open(os.path.join(test_log_dir, f)) as fp:
            data = json.load(fp)
            print(f"\n📊 {f} 内容预览:")
            print(f"  · prime_map: {data['prime_map']}")
            print(f"  · events 数量: {len(data['events'])}")
            if data['events']:
                print(f"  · 首个事件: {data['events'][0]}")
