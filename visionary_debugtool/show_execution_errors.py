import json

log_file = "/storage/emulated/0/Download/B站视频/logs/error_events_20260220_061316.json"
adj_file = "/storage/emulated/0/Download/B站视频/logs/adjacency_matrix_20260220_061316.json"

with open(log_file) as f:
    log = json.load(f)
with open(adj_file) as f:
    adj = json.load(f)

prime_map = log['prime_map']
rev_map = {v: k for k, v in prime_map.items()}
nodes = adj['nodes']

print("execution_error 事件详情：")
for event in log['events']:
    t, caller, callee, composite, log_val = event
    if composite == 19:
        print(f"  事件 {t}: 调用者 {nodes[caller]} -> 被调用者 {nodes[callee]}")