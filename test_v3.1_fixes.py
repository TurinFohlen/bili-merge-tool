#!/usr/bin/env python3
"""
v3.1 修复验证测试

验证内容：
1. RuntimeError 是否正确映射到 execution_error
2. 递归查找是否正常工作
3. 异常细化是否生效
"""
import sys, os, tempfile, pathlib
from unittest.mock import MagicMock, patch

# 设置错误日志
import error_log
test_log_dir = tempfile.mkdtemp(prefix="bili_v31_test_")
error_log.export_dir = test_log_dir
error_log.enabled = True

print("=" * 70)
print("v3.1 修复验证测试")
print("=" * 70)
print(f"📁 测试日志目录: {test_log_dir}\n")

# 加载组件
import loader
from registry import registry

print("\n─── 测试 1: RuntimeError 映射 ───")
try:
    # 检查 prime_map 是否包含 execution_error
    assert "execution_error" in error_log.prime_map, "缺少 execution_error"
    assert error_log.prime_map["execution_error"] == 19, "execution_error 素数错误"
    
    # 检查 _exception_map 是否包含 RuntimeError
    assert RuntimeError in error_log._exception_map, "缺少 RuntimeError 映射"
    assert error_log._exception_map[RuntimeError] == "execution_error", "RuntimeError 映射错误"
    
    # 测试异常映射函数
    exc = RuntimeError("测试错误")
    mapped = error_log.exception_to_error(exc)
    assert mapped == "execution_error", f"映射错误: {mapped}"
    
    print("  ✅ RuntimeError → execution_error 映射正常")
    print(f"     素数: 19")
    print(f"     映射表: RuntimeError → execution_error")

except AssertionError as e:
    print(f"  ❌ 失败: {e}")
    sys.exit(1)

print("\n─── 测试 2: rish_executor 异常细化 ───")
try:
    rish_exec = registry.get_service("rish.executor")
    
    # Mock subprocess.run 返回不同的 stderr
    test_cases = [
        ("no such file or directory", FileNotFoundError, "file_not_found", 5),
        ("permission denied", PermissionError, "permission_denied", 3),
        ("no space left on device", OSError, "disk_full", 11),
        ("unknown error", RuntimeError, "execution_error", 19),
    ]
    
    for stderr_content, expected_exc, expected_error, expected_prime in test_cases:
        with patch('subprocess.run') as mock_run, \
             patch('os.path.exists', return_value=True):  # Mock rish 存在
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = stderr_content
            mock_run.return_value = mock_result
            
            try:
                rish_exec.exec("test command", check=True)
                print(f"  ❌ 应该抛出异常: {stderr_content}")
                sys.exit(1)
            except expected_exc as e:
                mapped = error_log.exception_to_error(e)
                mapped_prime = error_log.prime_map[mapped]
                assert mapped == expected_error, f"映射错误: {mapped} != {expected_error}"
                assert mapped_prime == expected_prime, f"素数错误: {mapped_prime} != {expected_prime}"
                print(f"  ✅ '{stderr_content[:20]}...' → {expected_exc.__name__} → {expected_error} (素数 {expected_prime})")

except Exception as e:
    print(f"  ❌ 失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n─── 测试 3: extractor_dash 递归查找 ───")
try:
    extractor = registry.get_service("extractor.dash")
    
    # Mock rish_exec 模拟不同的目录结构
    def mock_rish_exec(cmd, **kwargs):
        # 模拟新版结构：文件直接在根目录
        if "ls" in cmd:
            if cmd.endswith("/c_test'"):  # 根目录
                return 0, "video.m4s\naudio.m4s\n112\n", ""
            elif cmd.endswith("/112'"):  # quality 子目录
                return 0, "video.mp4\naudio.mp4\n", ""
        elif "test -f" in cmd:
            # check_exists 调用
            if "video.m4s" in cmd or "audio.m4s" in cmd or "video.mp4" in cmd or "audio.mp4" in cmd:
                return 0, "", ""
        return 1, "", "not found"
    
    # 注入 mock
    extractor.rish_exec = mock_rish_exec
    if not extractor.file_operator:
        extractor.file_operator = MagicMock()
    extractor.file_operator.check_exists = MagicMock(return_value=True)
    extractor.file_operator.copy = MagicMock(return_value=True)
    
    # 测试递归查找
    temp_dir = tempfile.mkdtemp()
    base_dir = f"{extractor.bili_root}/123/c_test"
    
    # 查找视频文件
    results = extractor._find_files_recursive(base_dir, ["video.m4s", "video.mp4"], max_depth=2)
    
    assert len(results) > 0, f"未找到任何文件（base_dir={base_dir}）"
    # 应该找到两个文件：根目录的 video.m4s (深度0) 和 112/ 下的 video.mp4 (深度1)
    assert results[0][1] == 0, f"第一个文件深度应为 0，实际为 {results[0][1]}"
    assert "video.m4s" in results[0][0] or "video.mp4" in results[0][0], "第一个文件应是视频文件"
    
    print(f"  ✅ 递归查找找到 {len(results)} 个文件")
    print(f"     第一个: {results[0][0].split('/')[-1]} (深度 {results[0][1]})")
    if len(results) > 1:
        print(f"     第二个: {results[1][0].split('/')[-1]} (深度 {results[1][1]})")
    print(f"     策略: 浅层优先（新版结构优先）")
    
    os.rmdir(temp_dir)

except Exception as e:
    print(f"  ❌ 失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n─── 测试 4: 素数编码完整性 ───")
try:
    # 检查所有错误类型的素数都不同
    primes = list(error_log.prime_map.values())
    assert len(primes) == len(set(primes)), "素数重复！"
    
    # 检查素数都是质数
    def is_prime(n):
        if n < 2: return False
        for i in range(2, int(n**0.5) + 1):
            if n % i == 0: return False
        return True
    
    for error_type, prime in error_log.prime_map.items():
        if error_type != "none":  # none = 1 不是质数但是单位元
            assert is_prime(prime) or prime == 1, f"{error_type} 的值 {prime} 不是质数"
    
    print(f"  ✅ 所有 {len(error_log.prime_map)} 个错误类型素数唯一且有效")
    print(f"     prime_map: {dict(sorted(error_log.prime_map.items(), key=lambda x: x[1]))}")

except AssertionError as e:
    print(f"  ❌ 失败: {e}")
    sys.exit(1)

print("\n─── 测试 5: 复合错误编码 ───")
try:
    # 测试复合错误
    error_set = ["timeout", "execution_error"]
    composite = error_log.composite_value(error_set)
    expected = 2 * 19  # timeout(2) * execution_error(19)
    assert composite == expected, f"复合值错误: {composite} != {expected}"
    
    # 测试解码
    decoded = error_log.decode_errors(composite)
    assert set(decoded) == set(error_set), f"解码错误: {decoded} != {error_set}"
    
    # 测试对数变换
    log_val = error_log.log_composite_value(error_set)
    import math
    expected_log = math.log(2) + math.log(19)
    assert abs(log_val - expected_log) < 0.001, f"对数错误: {log_val} != {expected_log}"
    
    print(f"  ✅ 复合错误编码正常")
    print(f"     timeout(2) * execution_error(19) = {composite}")
    print(f"     log({composite}) = {log_val:.4f}")
    print(f"     解码: {composite} → {decoded}")

except AssertionError as e:
    print(f"  ❌ 失败: {e}")
    sys.exit(1)

# 统计测试结果
print("\n" + "=" * 70)
print("✅ 所有 v3.1 修复验证测试通过！")
print("=" * 70)
print("\n修复总结：")
print("  1. ✅ RuntimeError → execution_error (素数 19)")
print("  2. ✅ rish_executor 异常细化（4 种类型）")
print("  3. ✅ extractor_dash 递归查找（深度优先）")
print("  4. ✅ 素数编码完整性（9 种错误类型）")
print("  5. ✅ 复合错误编解码正常")
print("\n预期效果：")
print("  · unknown 错误: 29 → 0")
print("  · file_not_found 错误: 6 → ~0")
print("  · execution_error 错误: 0 → ~15-20")
print(f"\n📁 测试日志: {test_log_dir}")
