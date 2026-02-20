#!/usr/bin/env python3
"""
B站视频合并工具 v3.2.0 - 本地缓存模式启动入口

架构亮点：
  - 统一打包分片传输
  - 本地缓存复用（断点续传）
  - 彻底摆脱 rish 不稳定问题
  - MD5 校验确保数据完整性
"""
import sys
import os
import atexit

# 1. 设置错误日志导出目录
import error_log
error_log.export_dir = "/storage/emulated/0/Download/B站视频/logs"
error_log.enabled = True

# 2. 扫描并加载所有组件（自动注册）
print("=" * 60)
print("🔍 扫描并注册组件...")
print("=" * 60)
import loader  # 这会自动执行 scan_and_import()
print()

# 3. 注册 atexit 钩子：程序结束时导出错误日志
from registry import registry

def cleanup():
    """程序退出时导出错误日志"""
    print("\n" + "=" * 60)
    print("📊 导出错误日志...")
    print("=" * 60)
    error_log.export_error_log(registry)
    print()

atexit.register(cleanup)

# 4. 获取 UI 组件并执行主流程（使用 v2 本地缓存模式）
def main():
    try:
        cli = registry.get_service("ui.cli.v2")
        return cli.main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        return 130
    except Exception as e:
        print(f"❌ 未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
