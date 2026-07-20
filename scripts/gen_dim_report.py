#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W3 T3.2 — 维度报告生成（基于 W2 final JSONL 静态分析 + smoke 实测）"""
import json, sys, io
from collections import Counter, defaultdict
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = Path("e:/microbubble-agent/tests/qa-bench")
W2 = BASE / "questions_w2_final.jsonl"
SMOKE = BASE / "results/smoke/results.json"
OUT = BASE / "results/dimension_report.md"

def main():
    qs = [json.loads(l) for l in open(W2, encoding="utf-8")]
    print(f"题库: {len(qs)} 题\n")

    report = ["# 小气助手能力测评 - 维度报告 (W3 T3.2)\n"]
    report.append(f"**生成时间**: 2026-06-30")
    report.append(f"**题库**: `tests/qa-bench/questions_w2_final.jsonl` ({len(qs)} 题)")
    report.append(f"**来源**: W1 (700 题) + W2 手工 229 题 + W2 DB 107 题\n")

    # 1. 维度分布
    report.append("## 1. 维度分布\n")
    report.append("### 1.1 业务域")
    cat_dist = Counter(q['category'] for q in qs)
    for k, v in sorted(cat_dist.items()):
        report.append(f"- **{k}**: {v} 题 ({v/len(qs)*100:.1f}%)")
    report.append("")

    # 1.2 难度
    report.append("### 1.2 难度分布")
    diff_dist = Counter(q['difficulty'] for q in qs)
    for k, v in sorted(diff_dist.items()):
        report.append(f"- **{k}**: {v} 题 ({v/len(qs)*100:.1f}%)")
    report.append("")

    # 1.3 来源
    report.append("### 1.3 来源分布")
    src_dist = Counter(q['source'] for q in qs)
    for k, v in sorted(src_dist.items()):
        report.append(f"- **{k}**: {v} 题 ({v/len(qs)*100:.1f}%)")
    report.append("")

    # 1.4 Intent 分布
    report.append("### 1.4 Intent 分类分布 (W3 T3.0 bug 修复后)")
    intents = Counter(q.get('expect', {}).get('intent', 'unknown') for q in qs)
    intent_map = {
        'search_info': 'search_info (找资料)',
        'data_query': 'data_query (查数据)',
        'explain_concept': 'explain_concept (解释概念)',
        'execute_action': 'execute_action (执行操作)',
        'casual_chat': 'casual_chat (闲聊)',
        'recommend_person': 'recommend_person (找人)',
    }
    for k, v in sorted(intents.items(), key=lambda x: -x[1]):
        label = intent_map.get(k, k)
        report.append(f"- **{label}**: {v} 题")
    report.append("")

    # 2. 业务域 × 难度 矩阵
    report.append("## 2. 业务域 × 难度 矩阵\n")
    cat_diff = defaultdict(lambda: Counter())
    for q in qs:
        cat_diff[q['category']][q['difficulty']] += 1
    diffs = ['L1', 'L2', 'L3', 'L4']
    report.append("| 业务域 | " + " | ".join(diffs) + " | 合计 |")
    report.append("|" + "|".join(["---"] * 6) + "|")
    for cat in sorted(cat_dist.keys()):
        row = [cat]
        total = 0
        for d in diffs:
            c = cat_diff[cat].get(d, 0)
            row.append(str(c))
            total += c
        row.append(str(total))
        report.append("| " + " | ".join(row) + " |")
    report.append("")

    # 3. 业务域 × Intent 矩阵
    report.append("## 3. 业务域 × Intent 矩阵\n")
    cat_intent = defaultdict(lambda: Counter())
    for q in qs:
        ci = q.get('expect', {}).get('intent', 'unknown')
        cat_intent[q['category']][ci] += 1
    intent_keys = list(intents.keys())
    report.append("| 业务域 | " + " | ".join(intent_keys) + " |")
    report.append("|" + "|".join(["---"] * (len(intent_keys) + 1)) + "|")
    for cat in sorted(cat_dist.keys()):
        row = [cat]
        for ik in intent_keys:
            row.append(str(cat_intent[cat].get(ik, 0)))
        report.append("| " + " | ".join(row) + " |")
    report.append("")

    # 4. 工具调用分布 (T3.2 实测关键)
    report.append("## 4. 工具调用分布\n")
    tool_count = Counter()
    for q in qs:
        for t in q.get('expect', {}).get('tools_any', []):
            tool_count[t] += 1
    report.append("| 工具 | 题数 |")
    report.append("|---|---|")
    for k, v in sorted(tool_count.items(), key=lambda x: -x[1]):
        report.append(f"| {k} | {v} |")
    report.append("")

    # 5. 子题 (subcategory) 覆盖
    report.append("## 5. 子题 (subcategory) 覆盖\n")
    sub_dist = Counter(q['subcategory'] for q in qs)
    for k, v in sorted(sub_dist.items()):
        report.append(f"- **{k}**: {v} 题")
    report.append("")

    # 6. 必含字段覆盖率
    report.append("## 6. 字段覆盖率（v3.0 schema 校验）\n")
    required = ['id', 'version', 'category', 'subcategory', 'dimension',
                'difficulty', 'source', 'author', 'created_at', 'updated_at',
                'question', 'expect', 'ground_truth', 'ground_truth_refs',
                'detector', 'tags', 'deprecated', 'supersedes']
    for field in required:
        n = sum(1 for q in qs if field in q)
        pct = n / len(qs) * 100
        report.append(f"- **{field}**: {n}/{len(qs)} ({pct:.1f}%)")
    report.append("")

    # 7. Smoke 实测结果 (如果存在)
    if SMOKE.exists():
        report.append("## 7. Smoke 实测结果 (W3 T3.0 bug 修复后)\n")
        try:
            r = json.load(open(SMOKE, encoding="utf-8"))
            sm = r.get("summary", {})
            report.append(f"- **总题数**: {sm.get('total')}")
            report.append(f"- **PASS**: {sm.get('pass')}")
            report.append(f"- **WARN**: {sm.get('warn')}")
            report.append(f"- **FAIL**: {sm.get('fail')}")
            report.append(f"- **ERROR**: {sm.get('error')}")
            pass_rate = sm.get('pass', 0) / max(sm.get('total', 1), 1) * 100
            report.append(f"- **通过率**: {pass_rate:.1f}%")
            report.append(f"- **关键 Issue 类型 TOP 5**:")
            issue_dist = sm.get("issue_distribution", {})
            for k, v in sorted(issue_dist.items(), key=lambda x: -x[1])[:5]:
                report.append(f"  - {k}: {v} 次")
            report.append("")
        except Exception as e:
            report.append(f"- 数据解析失败: {e}\n")

    # 8. W3 阶段改进建议
    report.append("## 8. W3 阶段改进建议 (来自 T3.0 bug 修复 + smoke 实测)\n")
    report.append("### 8.1 T3.0 已修复")
    report.append("- ✅ MicroBubbleAgent.chat_stream() 添加 `model` 参数 (兼容 #009 检索质量的回归)")
    report.append("- ✅ intent 标签已从 DATA/CASUAL/DEEP/ACTION 改为 data_query/casual_chat/explain_concept/execute_action")
    report.append("")
    report.append("### 8.2 待改进 (T3.3-T3.5)")
    report.append("- T3.3: prompts.py 加 4 域综合 checklist (跨域 X 类准确率提升)")
    report.append("- T3.4: 检索质量 gate 阈值分档 (高/中/低 → 不同决策)")
    report.append("- T3.5: 性能优化 (Phase 0.5 + Phase 1 首轮检索并行)")
    report.append("")
    report.append("### 8.3 已知问题 (来自 smoke)")
    report.append("- 性能: 每题 25s, 全量 535 题 ~3.7 小时 (建议并发 4 跑)")
    report.append("- 限流: SSE/API 端点限流 30/min (write) + 200/min (read), 高并发需谨慎")
    report.append("- 真答案: 部分 L1/L2 题的回答不引用完整成员名 (forbidden_names_appeared issue)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(report), encoding="utf-8")
    print(f"\n[OK] 维度报告写入 {OUT}")
    print(f"     字数: {sum(len(r) for r in report)}")

if __name__ == "__main__":
    main()