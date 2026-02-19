import json

log_file = "/storage/emulated/0/Download/B站视频/logs/error_events_20260219_123247.json"
adj_file = "/storage/emulated/0/Download/B站视频/logs/adjacency_matrix_20260219_123247.json"

with open(adj_file) as f:
    nodes = json.load(f)['nodes']

with open(log_file) as f:
    data = json.load(f)
    prime_map = data['prime_map']
    rev_map = {v: k for k, v in prime_map.items()}
    events = data['events']

print("错误事件详情（t, 调用者, 被调用者, 复合值, 解码错误）")
for t, caller, callee, composite, log_val in events:
    if composite == 1:
        continue
    remaining = composite
    errors = []
    for p, name in rev_map.items():
        if p > 1 and remaining % p == 0:
            errors.append(name)
            while remaining % p == 0:
                remaining //= p
    if remaining > 1:
        errors.append('unknown_prime')
    print(f"t={t:4d} {nodes[caller]:30s} → {nodes[callee]:30s} comp={composite:3d} log={log_val:7.4f} errors={errors}")
