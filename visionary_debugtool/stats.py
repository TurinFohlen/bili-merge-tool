import json
from collections import Counter

log_file = "/storage/emulated/0/Download/B站视频/logs/error_events_20260219_123247.json"
with open(log_file) as f:
    data = json.load(f)

prime_map = data['prime_map']
rev_map = {v: k for k, v in prime_map.items()}
events = data['events']

error_counter = Counter()
for t, caller, callee, composite, log_val in events:
    remaining = composite
    if remaining == 1:
        error_counter['none'] += 1
    else:
        for p, name in rev_map.items():
            if p > 1 and remaining % p == 0:
                while remaining % p == 0:
                    remaining //= p
                error_counter[name] += 1
                # 注意：一次调用可能有多个错误，已分解
                # 但remaining可能还有剩余因子，继续循环
        # 如果所有因子处理完，remaining应为1，否则可能有未知素数
        if remaining > 1:
            error_counter['unknown_prime'] += 1

print("错误类型统计：")
for err, cnt in error_counter.most_common():
    print(f"  {err:20s}: {cnt}")
