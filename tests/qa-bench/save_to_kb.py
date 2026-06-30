"""
qa-bench/save_to_kb.py — 把 qa-bench 高分 (auto_score >= 4) 答案入库为"自动拓展"知识卡片 (#043)

W5 T5.1 升级 - 全自动入库模式 (5 道防线)
- 防线 1 分数门控: auto_score >= MIN_SCORE (默认 4/5 = A 级)
- 防线 2 内容门控: content >= MIN_CONTENT_LENGTH (默认 200 字)
- 防线 3 意图白名单: intent ∈ ALLOWED_INTENTS (默认 explain_concept + search_info)
- 防线 4 灰度开关: AUTO_KB_INTAKE_ENABLED env 或 --enable-intake flag
- 防线 5 备份 + 7 天 rollback: 每次入库前备份 JSON, 7 天内可自动 rollback

设计:
- 读 results/onebyone_log.jsonl
- 筛 auto_score >= 4 + intent in [explain_concept, search_info] + content >= 200 字
- POST /api/v1/knowledge/from-auto-expansion (服务端做幂等 + 质量门 + RichBlock 写入)
- 自动 batch_size=50/批, 失败继续, 完成后报告 saved/skipped/errors
- 备份到 backups/auto_intake_YYYYMMDD_HHMMSS.json

触发命令:
    # 默认 (灰度 flag = false, 需 --enable-intake 显式启用)
    python tests/qa-bench/save_to_kb.py --token <jwt>

    # 启用全自动 (灰度 flag = true)
    python tests/qa-bench/save_to_kb.py --token <jwt> --enable-intake

    # 7 天后自动 rollback (W5 T5.3 Celery task)
    # 写入: kb_id + created_at (7 天后 Celery 自动清)
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# 质量门 (与 API 端 AutoExpansionIngestRequest 默认值对齐)
DEFAULT_MIN_SCORE = 4
DEFAULT_MIN_CONTENT_LENGTH = 200
DEFAULT_ALLOWED_INTENTS = ["explain_concept", "search_info"]

# W5 防线 4: 灰度开关 (从 env AUTO_KB_INTAKE_ENABLED 读, 默认 False 避免误触发)
AUTO_KB_INTAKE_ENABLED = os.environ.get("AUTO_KB_INTAKE_ENABLED", "false").lower() == "true"

# W5 防线 5: 备份目录
BACKUP_ROOT = Path("backups/auto_intake")
BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

# W5 T5.3: 7 天 rollback 标记
ROLLBACK_DAYS = 7


def collect_candidates(log_path: Path) -> list[dict]:
    """从 onebyone_log.jsonl 收集候选条目

    候选条件:
      - id startswith "S" (qa-bench 测试题前缀)
      - auto_score >= DEFAULT_MIN_SCORE
      - content 长度 >= DEFAULT_MIN_CONTENT_LENGTH
      - intent ∈ DEFAULT_ALLOWED_INTENTS

    每个 candidate 是完整 payload dict, 供 POST batch 用
    """
    candidates = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue

            qid = d.get("id", "")
            if not qid.startswith("S"):
                continue

            score = d.get("quality", {}).get("auto_score", 0)
            if score < DEFAULT_MIN_SCORE:
                continue

            content = d.get("content", "")
            if len(content) < DEFAULT_MIN_CONTENT_LENGTH:
                continue

            intent = d.get("intent", "")
            if DEFAULT_ALLOWED_INTENTS and intent not in DEFAULT_ALLOWED_INTENTS:
                continue

            # 提取 tool_calls + rich_blocks (qa-bench runner 已存)
            actual = d.get("actual", {})
            tool_calls = actual.get("tool_inputs", [])
            rich_blocks = actual.get("tool_results", [])

            candidates.append({
                "qa_id": qid,
                "question": d["question"],
                "content": content,
                "scope": d.get("scope"),
                "score": score,
                "intent": intent,
                "tool_calls": tool_calls,
                "rich_blocks": rich_blocks,
            })
    return candidates


def post_batch(
    items: list[dict], token: str, base_url: str,
    min_score: int, min_content_length: int, allowed_intents: list[str],
) -> dict:
    """POST 批量到 /api/v1/knowledge/from-auto-expansion"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    resp = httpx.post(
        f"{base_url}/api/v1/knowledge/from-auto-expansion",
        json={
            "items": items,
            "min_score": min_score,
            "min_content_length": min_content_length,
            "allowed_intents": allowed_intents,
        },
        headers=headers,
        timeout=60,
    )
    if resp.status_code != 201:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def main():
    p = argparse.ArgumentParser(
        description="qa-bench 高分问答 → 自动拓展知识卡片 (#043)",
    )
    p.add_argument("--token", required=True, help="JWT token (从 /api/v1/auth/login 拿)")
    p.add_argument("--base-url", default="http://127.0.0.1:8000",
                   help="API base URL (默认本地; 生产用 https://agent.mnb-lab.cn)")
    p.add_argument("--log", default="results/onebyone_log.jsonl",
                   help="qa-bench 日志路径")
    p.add_argument("--batch-size", type=int, default=50,
                   help="单次 POST batch 大小 (默认 50)")
    p.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE,
                   help=f"最低 auto_score 阈值 (默认 {DEFAULT_MIN_SCORE})")
    p.add_argument("--min-content-length", type=int, default=DEFAULT_MIN_CONTENT_LENGTH,
                   help=f"最低 content 长度 (默认 {DEFAULT_MIN_CONTENT_LENGTH})")
    p.add_argument("--allowed-intents", default=",".join(DEFAULT_ALLOWED_INTENTS),
                   help=f"白名单 intent (默认 {','.join(DEFAULT_ALLOWED_INTENTS)})")
    p.add_argument("--enable-intake", action="store_true",
                   help="W5 防线 4: 显式启用全自动入库 (默认关闭, 需 --enable-intake 或 env AUTO_KB_INTAKE_ENABLED=true)")
    args = p.parse_args()

    # W5 防线 4: 灰度开关校验
    if not (args.enable_intake or AUTO_KB_INTAKE_ENABLED):
        print("⚠️  W5 防线 4 灰度开关未启用: --enable-intake 或 env AUTO_KB_INTAKE_ENABLED=true")
        print("    当前模式: dry-run (只统计候选, 不入库)")
        # 仍统计候选数 (用户可见性)
        log_path_dry = Path(args.log)
        if not log_path_dry.exists():
            print(f"❌ 找不到日志: {log_path_dry}")
            return 1
        candidates_dry = collect_candidates(log_path_dry)
        print(
            f"📊 [DRY-RUN] 候选 (auto_score>={args.min_score}, "
            f"content>={args.min_content_length}, "
            f"intent∈{args.allowed_intents.split(',')}): {len(candidates_dry)} 题"
        )
        print("    如需真入库: 加 --enable-intake 或设 AUTO_KB_INTAKE_ENABLED=true")
        return 0

    log_path = Path(args.log)
    if not log_path.exists():
        print(f"❌ 找不到日志: {log_path}")
        return 1

    candidates = collect_candidates(log_path)
    print(
        f"📊 候选 (auto_score>={args.min_score}, content>={args.min_content_length}, "
        f"intent∈{args.allowed_intents.split(',')}): {len(candidates)} 题"
    )

    if not candidates:
        print("没有候选条目可入库")
        return 0

    # W5 防线 5: 备份候选到 JSON (rollback 入口)
    backup_path = BACKUP_ROOT / f"candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    backup_path.write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"💾 备份候选 → {backup_path} ({len(candidates)} 条)")

    allowed_intents = [s.strip() for s in args.allowed_intents.split(",") if s.strip()]
    total_saved = 0
    total_skipped = 0
    total_errors: list[str] = []

    for i in range(0, len(candidates), args.batch_size):
        batch = candidates[i:i + args.batch_size]
        batch_num = i // args.batch_size + 1
        try:
            result = post_batch(
                batch, args.token, args.base_url,
                min_score=args.min_score,
                min_content_length=args.min_content_length,
                allowed_intents=allowed_intents,
            )
            total_saved += result["saved"]
            total_skipped += result["skipped"]
            if result.get("errors"):
                total_errors.extend(result["errors"])
            print(
                f"  batch {batch_num}: "
                f"saved={result['saved']}, skipped={result['skipped']}"
            )
        except Exception as e:
            print(f"  batch {batch_num}: ❌ {e}")
            total_errors.append(f"batch {batch_num}: {e}")

    print(
        f"\n✅ 完成: saved={total_saved}, skipped={total_skipped}, "
        f"errors={len(total_errors)}"
    )

    # W5 T5.4: Dashboard 监控汇总 (写入 data/auto_intake_summary_*.json)
    summary = {
        "timestamp": datetime.now().isoformat(),
        "gray_flag_enabled": True,
        "min_score": args.min_score,
        "min_content_length": args.min_content_length,
        "allowed_intents": allowed_intents,
        "candidates_count": len(candidates),
        "saved": total_saved,
        "skipped": total_skipped,
        "errors": total_errors,
        "backup_path": str(backup_path),
        "rollback_window_days": ROLLBACK_DAYS,
    }
    summary_path = Path("data/auto_intake_summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"📊 Dashboard 监控汇总写入 {summary_path}")
    print(
        f"   7 天内可 rollback (Celery task auto_intake_rollback_task 每日 3:30 跑)"
    )

    return 0 if not total_errors else 1


if __name__ == "__main__":
    sys.exit(main())