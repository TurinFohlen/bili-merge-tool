import json
from collections import Counter

log_file = "/storage/emulated/0/Download/B站视频/logs/error_events_20260219_123247.json"
adj_file = "/storage/emulated/0/Download/B站视频/logs/adjacency_matrix_20260219_123247.json"

with open(log_file) as f:
    data = json.load(f)
prime_map = data['prime_map']
rev_map = {v: k for k, v in prime_map.items()}
events = data['events']

with open(adj_file) as f:
    adj_data = json.load(f)
nodes = adj_data['nodes']  # 组件名列表，索引从0开始

caller_errors = Counter()
callee_errors = Counter()

for t, caller, callee, composite, log_val in events:
    if composite == 1:
        continue
    # 解码错误类型
    remaining = composite
    errors = []
    for p, name in rev_map.items():
        if p > 1 and remaining % p == 0:
            errors.append(name)
            while remaining % p == 0:
                remaining //= p
    if remaining > 1:
        errors.append('unknown_prime')
    for err in errors:
        caller_errors[(nodes[caller], err)] += 1
        callee_errors[(nodes[callee], err)] += 1

print("按调用者统计错误：")
for (comp, err), cnt in caller_errors.most_common():
    print(f"  {comp:30s} {err:20s}: {cnt}")

print("\n按被调用者统计错误：")
for (comp, err), cnt in callee_errors.most_common():
    print(f"  {comp:30s} {err:20s}: {cnt}")
