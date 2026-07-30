"""ground_truth_loader 题库加载 (PR5 W91 +4)

设计 (RAG 工业级 v1.1 §3.2 PR5 + 派工 brief §2):
- 默认题库: tests/qa-bench/questions_smoke_200.jsonl (200 题, 满足 ≥ 100 门禁)
- 格式: JSONL, 每行 1 题, 字段: id/question/ground_truth/ground_truth_refs/expect/...
- 派工 brief "200 题 vs 新建 ≥ 100 题路径" 二选一: 实测 200 题真存在, 走 200 题路径, 新建路径不实施

errata (派工 v11 段 3 + 类 20 #31 据实上报):
- 派工 brief 标注 "200 题 vs 新建 ≥ 100 题路径" 二选一
- 实测: tests/qa-bench/questions_smoke_200.jsonl 200 题真存在, 200 题路径已经足 ≥ 100
- 据实: 走 200 题主路径, 新建 ≥ 100 题路径不实施 (类 20 #31)
- 后续 PR5 pytest 22 case 全部基于 200 题 question_id 子集

filter:
- deprecated=False (False 题跳过)
- 字段缺失过滤 (无 question or ground_truth_refs 的跳过)
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("microbubble.rag_eval.ground_truth_loader")


# 默认题库路径 (PR5 派工 brief §2 据实 200 题真存在)
DEFAULT_GT_PATH = Path(__file__).resolve().parent.parent.parent / "tests" / "qa-bench" / "questions_smoke_200.jsonl"


def load_ground_truth(
    path: Optional[Path] = None,
    *,
    limit: Optional[int] = None,
    skip_deprecated: bool = True,
) -> List[Dict]:
    """加载 ground-truth 题库 (JSONL 格式)

    Args:
        path: 题库路径, 默认 DEFAULT_GT_PATH
        limit: 截取前 N 题 (用于 PR5 e2e 子集, 跑得更快)
        skip_deprecated: 跳过 deprecated=True 题

    Returns:
        List[Dict] 每题至少含 id/question/ground_truth_refs (List[int], 解析自 kb://xxx)
        跳过: deprecated=True / 缺 question / 缺 ground_truth_refs 的题

    Notes:
        - 200 题默认全部加载 (满足派工 brief ≥ 100)
        - 限制 limit 是为 PR5 e2e 22 case 跑得更快 (22 题子集)
        - 字段容错: kb://a/a1-x1 解析失败时返回空 List (触发 class 20 #31)
    """
    path = path or DEFAULT_GT_PATH
    if not path.exists():
        logger.warning(f"ground-truth file not found: {path}")
        return []

    out: List[Dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning(f"line {line_no}: JSONDecodeError {e}")
                continue

            # 跳过 deprecated
            if skip_deprecated and obj.get("deprecated", False):
                continue

            # 必填字段检查
            q = obj.get("question")
            refs = obj.get("ground_truth_refs")
            if not q or not refs:
                continue

            # 解析 ids (kb://a/a1-x1 → 暂留字符串, 跑评估时按知识匹配)
            # PR5: 直接用 ref 字符串列表对比 retrieved 中的 knowledge_id (text)
            # 真生产环境需解析 kb:// → knowledge.id 映射, 本 PR 简化留字符串
            out.append({
                "id": obj.get("id", f"q-{line_no}"),
                "question": q,
                "ground_truth": obj.get("ground_truth"),
                "ground_truth_refs": refs,
                "category": obj.get("category"),
                "difficulty": obj.get("difficulty"),
            })

            if limit and len(out) >= limit:
                break

    logger.info(f"loaded {len(out)} ground-truth questions from {path}")
    return out


def count_ground_truth(path: Optional[Path] = None) -> int:
    """仅统计题数 (PAT 派工 brief E27 ground-truth 题库验证)

    Returns: 题数 (200 真存在)
    """
    return len(load_ground_truth(path=path, skip_deprecated=True))
