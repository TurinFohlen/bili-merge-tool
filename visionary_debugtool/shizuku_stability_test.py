import subprocess
import os
import time
from itertools import product
from collections import defaultdict

# 配置
RISH_PATH = "/sdcard/shizuku-rish/rish"
PACKAGE_NAME = "ru.iiec.pydroid3"
L = 2                       # 序列长度（位），建议 4~6，否则实验次数会爆炸
REPEATS_PER_SEQUENCE = 10   # 每种理论序列重复实验次数
DELAY = 0.1                 # 每次命令后的延迟

def rish_exec(command):
    env = os.environ.copy()
    env['RISH_APPLICATION_ID'] = PACKAGE_NAME
    try:
        result = subprocess.run(
            ['sh', RISH_PATH, '-c', command],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=5
        )
        return result
    except:
        return None

def get_output_mode():
    """执行 echo hello_shizuku，返回 'stdout' 或 'stderr' 或 'none'"""
    result = rish_exec("echo hello_shizuku")
    if result is None:
        return 'timeout'
    if 'hello_shizuku' in result.stdout:
        if 'hello_shizuku' in result.stderr:
            return 'both'
        return 'stdout'
    elif 'hello_shizuku' in result.stderr:
        return 'stderr'
    else:
        return 'none'

def run_sequence(length):
    """执行 length 次，返回一个由 '1'(stdout) 和 '0'(stderr) 组成的字符串，忽略 both/none/timeout"""
    seq = []
    for _ in range(length):
        mode = get_output_mode()
        if mode == 'stdout':
            seq.append('1')
        elif mode == 'stderr':
            seq.append('0')
        else:
            # 如果出现 both/none/timeout，我们标记为 '?' 并跳过？但为了统计，可以视为异常
            seq.append('?')
        time.sleep(DELAY)
    return ''.join(seq)

def main():
    # 生成所有理论二进制序列
    theoretical_seqs = [''.join(bits) for bits in product('01', repeat=L)]
    print(f"理论序列（共 {len(theoretical_seqs)} 种）：{theoretical_seqs}")

    # 存储实际出现的序列及其计数
    observed_counter = defaultdict(int)

    for t_seq in theoretical_seqs:
        print(f"\n--- 测试理论序列 {t_seq} ---")
        for rep in range(REPEATS_PER_SEQUENCE):
            actual_seq = run_sequence(L)
            observed_counter[actual_seq] += 1
            print(f"  实际序列: {actual_seq}")

    # 输出统计结果
    print("\n\n========== 最终统计 ==========")
    print(f"实验次数总计：{len(theoretical_seqs) * REPEATS_PER_SEQUENCE}")
    print("实际出现的序列及其频次：")
    for seq, count in sorted(observed_counter.items()):
        print(f"  {seq}: {count} 次")

    # 计算每个理论序列被实际复现的比例
    print("\n理论序列与实际序列的匹配情况：")
    for t_seq in theoretical_seqs:
        actual_count = observed_counter.get(t_seq, 0)
        print(f"  {t_seq}: 出现 {actual_count} 次 / 预期 {REPEATS_PER_SEQUENCE} 次")

if __name__ == "__main__":
    main()