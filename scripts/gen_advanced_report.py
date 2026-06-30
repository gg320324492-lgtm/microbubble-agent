#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W4 T4.7 — 高级能力报告 (P 102 题专项分析)"""
import json, sys, io
from collections import Counter, defaultdict
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = Path("e:/microbubble-agent/tests/qa-bench")
W2 = BASE / "questions_w2_final.jsonl"
OUT = BASE / "results/advanced_capability_report.md"

def main():
    qs = [json.loads(l) for l in open(W2, encoding="utf-8")]
    p_qs = [q for q in qs if q['category'] == 'P']
    print(f"P class total: {len(p_qs)}")

    report = ["# 小气助手能力测评 - 高级能力报告 (W4 T4.7)\n"]
    report.append(f"**生成时间**: 2026-06-30")
    report.append(f"**P 高级题**: {len(p_qs)} 题 (W1 gen780.py 模板生成)")
    report.append(f"**场景**: Self-RAG / fan-out / plan_step / 持久化 / abort / grounding\n")

    # 1. 子题分布
    report.append("## 1. P 高级 6 子类分布\n")
    sub_dist = Counter(q['subcategory'] for q in p_qs)
    for k, v in sorted(sub_dist.items()):
        report.append(f"- **{k}**: {v} 题")
    report.append("")

    # 2. 子类期望工具分布
    report.append("## 2. 子类期望工具分布\n")
    sub_tools = defaultdict(lambda: Counter())
    for q in p_qs:
        for t in q.get('expect', {}).get('tools_any', []):
            sub_tools[q['subcategory']][t] += 1
    for sub in sorted(sub_dist.keys()):
        report.append(f"### {sub}")
        for t, c in sorted(sub_tools[sub].items(), key=lambda x: -x[1])[:5]:
            report.append(f"- {t}: {c} 题")
        report.append("")

    # 3. 难度 × 子类 矩阵
    report.append("## 3. P 子类 × 难度 矩阵\n")
    sub_diff = defaultdict(lambda: Counter())
    for q in p_qs:
        sub_diff[q['subcategory']][q['difficulty']] += 1
    diffs = ['L1', 'L2', 'L3', 'L4']
    report.append("| 子类 | " + " | ".join(diffs) + " | 合计 |")
    report.append("|" + "|".join(["---"] * 6) + "|")
    for sub in sorted(sub_dist.keys()):
        row = [sub]
        total = 0
        for d in diffs:
            c = sub_diff[sub].get(d, 0)
            row.append(str(c))
            total += c
        row.append(str(total))
        report.append("| " + " | ".join(row) + " |")
    report.append("")

    # 4. W4 T3.4 Self-RAG 3-tier 改进
    report.append("## 4. W4 T3.4 Self-RAG 3-tier 分级改进\n")
    report.append("### 4.1 改进前 (W1 阶段)")
    report.append("- 单阈值 0.6: confidence >= 0.6 不重检索, 否则触发")
    report.append("- 缺点: 模糊查询 (e.g. 0.55) 立即重检索, 增加 latency 30%+")
    report.append("- 缺点: 高置信度 (e.g. 0.85) 与中置信度 (e.g. 0.65) 走相同路径, 无差别化日志")
    report.append("")
    report.append("### 4.2 改进后 (W4 T3.4)")
    report.append("- **高置信度 (≥0.8)**: 直接出, 日志 `✅ high_confidence`")
    report.append("- **中高置信度 (≥0.6)**: 不重检索, 日志 `✓ mid_high_confidence`")
    report.append("- **中置信度 (≥0.4) + can_answer**: 不重检索, 日志 `~ mid_confidence`")
    report.append("- **低置信度 (<0.4)**: 触发重检索, 日志 `↻ low_confidence`")
    report.append("- **max_reached**: 重试耗尽, 日志 `🛑 max_reretrieve_reached`")
    report.append("")
    report.append("### 4.3 实施位置")
    report.append("- `app/agent/agentic_loop.py:615-665` (3-tier 决策块)")
    report.append("- `app/config.py:166-171` (阈值配置)")
    report.append("")

    # 5. W4 T3.5 性能优化 (deferred)
    report.append("## 5. W4 T3.5 性能优化 (deferred)\n")
    report.append("**目标**: Phase 0.5 (Self-RAG) 与 Phase 1 首轮检索并行")
    report.append("")
    report.append("**为什么 defer**:")
    report.append("- 主循环重构风险高 (动 Phase 0.5 / 1 的串联逻辑)")
    report.append("- 并发引入数据竞争 (messages/tool_calls 共享状态)")
    report.append("- 需配合 LLM provider 并发配置")
    report.append("- 单题 25s 已基本可用, 无紧急性")
    report.append("")
    report.append("**留给 W5/W6 安排**:\n")
    report.append("- W5: save_to_kb.py 全自动改造 + 回归基线 (性能测试机会)")
    report.append("- W6: 性能基准 (latency P95 < 20s, TTFT < 3s)")
    report.append("")

    # 6. 5 弱项改进回顾
    report.append("## 6. 5 弱项改进计划回顾 (来自 plan 5.1)\n")
    improvements = [
        ("A. 跨域 4 域综合", "W3 T3.3 4-段 checklist + 5-段 LLM 自检", "✅ 实施", "prompts.py"),
        ("B. Self-RAG 阈值优化", "W4 T3.4 3-tier 分级 (0.8/0.6/0.4)", "✅ 实施", "agentic_loop.py"),
        ("C. 持久化聊天", "W1 #043 8 phase 收官 (跨 session 摘要)", "✅ 收官", "app/services/chat_history*"),
        ("D. 任务创建参数解析", "W2 验收 — 测试集覆盖 B3 5 题", "✅ 完成", "manual_234.jsonl"),
        ("E. 性能优化", "W4 T3.5 deferred (需主循环重构)", "⏸ W5/W6", "agentic_loop.py"),
    ]
    report.append("| 弱项 | 改进 | 状态 | 文件 |")
    report.append("|---|---|---|---|")
    for name, desc, status, file in improvements:
        report.append(f"| {name} | {desc} | {status} | {file} |")
    report.append("")

    # 7. 实际跑测结果 (如果存在 smoke 结果)
    smoke_path = BASE / "results/smoke/results.json"
    if smoke_path.exists():
        try:
            r = json.load(open(smoke_path, encoding="utf-8"))
            sm = r.get("summary", {})
            report.append("## 7. Smoke 实测结果 (W3 T3.0 bug 修复后)\n")
            report.append(f"- **总题数**: {sm.get('total')}")
            report.append(f"- **PASS**: {sm.get('pass')}")
            report.append(f"- **WARN**: {sm.get('warn')}")
            report.append(f"- **FAIL**: {sm.get('fail')}")
            report.append(f"- **ERROR**: {sm.get('error')}")
            pass_rate = sm.get('pass', 0) / max(sm.get('total', 1), 1) * 100
            report.append(f"- **通过率**: {pass_rate:.1f}%")
            issue_dist = sm.get("issue_distribution", {})
            report.append(f"- **TOP 5 issue**: {sorted(issue_dist.items(), key=lambda x: -x[1])[:5]}")
            report.append("")
            report.append("**注**: Smoke 仅 5 题, 不是 P 专项结果; 完整 P 102 题跑测需过夜调度 (3.7h+)")
        except Exception:
            pass

    # 8. 后续计划
    report.append("## 8. 后续计划 (W5-W6)\n")
    report.append("### W5 (KB 入库 + 回归)")
    report.append("- save_to_kb.py 全自动改造 + 5 道防线 (分数门控 + 7天 rollback + dashboard 监控 + 灰度 flag + 白名单)")
    report.append("- 200 题 smoke baseline (基于 W2 合并题库)")
    report.append("- 回归基线 v3.0 锁定")
    report.append("- 2 轮稳定性测试 (同题二次一致性 ≥ 95%)")
    report.append("")
    report.append("### W6 (交付)")
    report.append("- 雷达图 (7 维可视化)")
    report.append("- 趋势报告 (v2.x → v3.0 提升)")
    report.append("- 决策项清单 (产品/架构/前端)")
    report.append("- 文档交付 (README + 运维手册 + 题库维护 SOP)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(report), encoding="utf-8")
    print(f"\n[OK] 高级能力报告写入 {OUT}")
    print(f"     字数: {sum(len(r) for r in report)}")

if __name__ == "__main__":
    main()