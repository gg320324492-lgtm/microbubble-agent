"""
detectors/retrieval_recall.py — 检索质量检测器 (P1)

# 2026-07-01 新增 (BGE m3 reranker 升级伴随)
- 对比 ground_truth_refs vs search_knowledge 实际返回的 doc IDs
- 计算 recall@5 / MRR, 报告检索质量
- 集成到 qa-bench runner.py 作为 P1 检测器

设计参考: scripts/eval_recall.py (历史 38 题手工评估)
"""
import re
from typing import Any, Dict, List


def collect_search_k_doc_ids(events: List[Dict[str, Any]]) -> List[int]:
    """从 search_knowledge tool_result events 收集 doc IDs

    SSE tool_result event 格式:
        {
            "type": "tool_result",
            "tool_name": "search_knowledge",
            "tool_output": {"status": "success", "results": [{"id": 1, ...}, ...]}
        }
    """
    ids = []
    for e in events:
        if e.get("type") != "tool_result":
            continue
        if e.get("tool_name") != "search_knowledge":
            continue
        output = e.get("tool_output", {})
        if not isinstance(output, dict):
            continue
        results = output.get("results", [])
        if not isinstance(results, list):
            continue
        for r in results:
            if isinstance(r, dict) and "id" in r:
                ids.append(int(r["id"]))
    return ids


def detect_retrieval_recall(
    events: List[Dict[str, Any]], ground_truth_refs: List[str]
) -> List[Dict[str, Any]]:
    """检测检索质量

    Args:
        events: SSE 事件流
        ground_truth_refs: qa-bench 题目的金标准 (e.g. ["kb://a/a1-x1", "kb://a/a1-x3"])

    Returns:
        issue dict 列表 (severity=warn, 不阻止 PASS)
    """
    issues = []
    if not ground_truth_refs:
        return issues

    # 解析 ground_truth_refs (kb://a/a1-x1 → 数字 ID "x1")
    # 注: kb:// 格式的 suffix 部分对应 knowledge.id (测试题库约定)
    gt_ids = set()
    for ref in ground_truth_refs:
        m = re.match(r"kb://.+/(\S+)", ref)
        if m:
            suffix = m.group(1)
            # 如果 suffix 是纯数字 (legacy 格式), 直接用
            if suffix.isdigit():
                gt_ids.add(int(suffix))
            # 否则跳过 (新格式 "x1/x2/x3" 在客户端知识库地图查, server 端无法直接 match)
            # 未来需要扩展: 客户端维护 kb://x1 → knowledge.id 映射表

    if not gt_ids:
        # 题库没标注数字 ID, 检测器静默跳过
        return issues

    retrieved = collect_search_k_doc_ids(events)
    if not retrieved:
        issues.append({
            "type": "retrieval_no_results",
            "severity": "warn",
            "ground_truth_ids": sorted(gt_ids),
            "actual": "0 docs returned",
            "context": "search_knowledge 0 结果",
        })
        return issues

    # Recall@5
    top5 = retrieved[:5]
    hits_at_5 = gt_ids & set(top5)
    if not hits_at_5:
        issues.append({
            "type": "retrieval_recall_zero",
            "severity": "warn",
            "ground_truth_ids": sorted(gt_ids),
            "retrieved_top5": top5,
            "context": "top-5 没有命中任何 ground_truth doc",
        })

    # MRR
    for rank, doc_id in enumerate(retrieved, 1):
        if doc_id in gt_ids:
            if rank > 5:
                issues.append({
                    "type": "retrieval_rank_too_low",
                    "severity": "warn",
                    "rank": rank,
                    "ground_truth_ids": sorted(gt_ids),
                })
            break
    else:
        # 走 for-else: 完全没命中
        issues.append({
            "type": "retrieval_missed",
            "severity": "warn",
            "ground_truth_ids": sorted(gt_ids),
            "retrieved": retrieved[:10],
            "context": "top-10 都没命中",
        })

    return issues
