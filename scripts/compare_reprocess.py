"""对比 baseline vs current 重处理结果"""
import json

b = json.load(open("/tmp/reprocess_120_result_BASELINE.json"))
n = json.load(open("/tmp/reprocess_120_result.json"))

print("=== 前后对比 (BASELINE vs NOW) ===")
print(f"n_segments:     {b['n_segments']} vs {n['n_segments']}  (一致: {b['n_segments'] == n['n_segments']})")
print(f"n_valid_embs:   {b['n_valid_embs']} vs {n['n_valid_embs']}  (一致: {b['n_valid_embs'] == n['n_valid_embs']})")
print(f"n_clusters:     {b['n_clusters']} vs {n['n_clusters']}  (一致: {b['n_clusters'] == n['n_clusters']})")
print(f"silhouette:     {b['silhouette']:.3f} vs {n['silhouette']:.3f}")
print()
print("=== 聚类一致性 ===")
for cid in sorted(b["cluster_names"].keys()):
    bn = b["cluster_names"][cid]
    nn = n["cluster_names"][cid]
    name_match = bn["name"] == nn["name"]
    votes_match = bn["votes"] == nn["votes"]
    conf_diff = abs(bn["avg_conf"] - nn["avg_conf"])
    print(f"  聚类 {cid}: {bn['name']:6s} (votes={bn['votes']:4d}, conf={bn['avg_conf']:.3f}, n={bn['total_segments']:4d})")
    print(f"         -> {nn['name']:6s} (votes={nn['votes']:4d}, conf={nn['avg_conf']:.3f}, n={nn['total_segments']:4d})")
    print(f"         名字: {name_match} | votes: {votes_match} | conf_diff: {conf_diff:.4f}")
print()
print("=== new_speaker 数组一致性 ===")
match_count = sum(1 for i in range(len(b["new_speaker"])) if b["new_speaker"][i] == n["new_speaker"][i])
total = len(b["new_speaker"])
print(f"  {match_count}/{total} 段 speaker 完全一致 ({100*match_count/total:.1f}%)")
diffs = [(i, b["new_speaker"][i], n["new_speaker"][i]) for i in range(total) if b["new_speaker"][i] != n["new_speaker"][i]]
if diffs:
    print(f"  差异段: {len(diffs)} 段")
    for i, b_name, n_name in diffs[:10]:
        print(f"    [{i}] {b_name} -> {n_name}")
else:
    print(f"  无差异 ✓ (完全幂等)")
