"""横比修前 / 修后 RAG 评测基线 (2026-11-04)

判据:
- 类 20.252: 跨轮比较前先确认「参照集」和「表示层」都没变
  (同一份 50 题集、同一 judge 模型、n / n_ok 相同)，不一致就拒绝横比。
- 类 20.226 / 20.255: **只报均值会把 judge 噪声误读成提升或退化**。
  本脚本同时报逐题配对的中位数、标准差、|Δ|>0.1 的题数，并给出
  「效应量 vs 噪声量级」的判读: 效应量小于逐题标准差时不认定为真实变化。

用法:
  PYTHONUTF8=1 python scripts/rag/compare_judge_baselines.py <before.json> <after.json>

⚠️ Windows 本机 Python 默认 GBK (类 20.216 第 3 形态): 本文件含中文与箭头
   等符号, 直接跑会 UnicodeEncodeError ⇒ 必须 PYTHONUTF8=1, 且脚本第一行
   就显式重配 stdout, 不依赖调用方记得设环境变量。
"""
import json
import pathlib
import statistics as stats
import sys

# 类 20.216 第 3 形态: 本机 Python 默认 GBK, 中文/箭头 print 会炸。
# 显式重配 stdout/stderr 为 utf-8 (errors=replace 兜底, 不让判读结果因编码丢失)。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

METRICS = ("mean_faithfulness", "mean_answer_relevancy", "mean_context_precision", "overall")
PER_QUERY = {
    "mean_faithfulness": "faithfulness",
    "mean_answer_relevancy": "answer_relevancy",
    "mean_context_precision": "context_precision",
}


def main(before_path: str, after_path: str) -> int:
    before = json.loads(pathlib.Path(before_path).read_text(encoding="utf-8"))
    after = json.loads(pathlib.Path(after_path).read_text(encoding="utf-8"))

    print("== 可比性检查 ==")
    same_n = before.get("n") == after.get("n") and before.get("n_ok") == after.get("n_ok")
    same_judge = before.get("judge") == after.get("judge")
    print("  n/n_ok 一致: %s (修前 %s/%s, 修后 %s/%s)" % (
        same_n, before.get("n"), before.get("n_ok"), after.get("n"), after.get("n_ok")))
    print("  judge 一致: %s (%s)" % (same_judge, after.get("judge")))
    eval_set = pathlib.Path("results/rag-judge-eval-set-2026-11-04.json")
    if eval_set.exists():
        d = json.loads(eval_set.read_text(encoding="utf-8"))
        print("  固定评测集: seed=%s, %d 题" % (d.get("seed"), len(d.get("queries", []))))
    else:
        print("  ⚠️ 固定评测集文件不存在 —— 无法证明两轮用的是同一组题")
        return 2
    if not (same_n and same_judge):
        print("\n拒绝横比: 参照集不一致, 两组数字不可相减")
        return 2

    print("\n== 指标横比 (均值) ==")
    print("  %-26s %10s %10s %10s" % ("metric", "before", "after", "delta"))
    for k in METRICS:
        a, b = float(before[k]), float(after[k])
        print("  %-26s %10.4f %10.4f %+10.4f" % (k, a, b, b - a))

    # 逐题配对: 用 query 文本对齐, 不假设两份 detail 顺序完全相同
    bd = {r["query"]: r for r in before.get("detail", []) if r.get("query")}
    ad = {r["query"]: r for r in after.get("detail", []) if r.get("query")}
    common = sorted(set(bd) & set(ad))
    print("\n== 逐题配对 (噪声判读) ==")
    print("  可配对题数: %d" % len(common))
    if len(common) != before.get("n"):
        print("  ⚠️ 配对数 != 题数, 两轮可能不是同一组 query")
        return 2

    verdicts = []
    for mean_key, key in PER_QUERY.items():
        diffs = [float(ad[q][key]) - float(bd[q][key]) for q in common
                 if key in bd[q] and key in ad[q]]
        if not diffs:
            continue
        mean = stats.mean(diffs)
        median = stats.median(diffs)
        sd = stats.pstdev(diffs) if len(diffs) > 1 else 0.0
        up = sum(1 for x in diffs if x > 0.01)
        down = sum(1 for x in diffs if x < -0.01)
        big = sum(1 for x in diffs if abs(x) > 0.1)
        print("  %-20s 均值%+.4f 中位%+.4f 标准差%.4f |Δ|>0.1:%d/%d 升%d/降%d/持平%d" % (
            key, mean, median, sd, big, len(diffs), up, down, len(diffs) - up - down))
        # 效应量 < 逐题标准差 ⇒ 与 judge 波动同量级, 不认定为真实变化
        is_noise = abs(mean) < sd and abs(median) < 0.01
        verdicts.append((key, is_noise, mean, sd))

    print("\n== 判读 ==")
    for key, is_noise, mean, sd in verdicts:
        if is_noise:
            print("  %-20s 与 judge 噪声同量级 (|均值|%.4f < 标准差%.4f, 中位≈0) ⇒ 无显著变化" % (
                key, abs(mean), sd))
        else:
            print("  %-20s 均值变化超出噪声量级 ⇒ 需进一步查原因, 别直接归因于本次改动" % key)

    print("\n注: 判「改好还是改坏」不能只看均值。LLM-judge 单题分数本身波动大,")
    print("   两轮答案不同 (生成有随机性)、检索命中也可能随时间变化 ⇒ 均值差几个点")
    print("   完全可能来自噪声。要拿到可信结论, 需固定答案/多轮重复取均值, 或")
    print("   改用确定性的检索层指标 (recall@k / nDCG)。")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    sys.exit(main(sys.argv[1], sys.argv[2]))
