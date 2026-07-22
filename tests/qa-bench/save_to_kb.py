"""
qa-bench/save_to_kb.py — 把 qa-bench 高分 (auto_score >= 4) 答案入库为"自动拓展"知识卡片 (#043)

W5 T5.1 升级 - 全自动入库模式 (5 道防线)
- 防线 1 分数门控: auto_score >= MIN_SCORE (默认 4/5 = A 级)
- 防线 2 内容门控: content >= MIN_CONTENT_LENGTH (默认 200 字)
- 防线 3 意图白名单: intent ∈ ALLOWED_INTENTS (默认 explain_concept + search_info)
- 防线 4 灰度开关: AUTO_KB_INTAKE_ENABLED env 或 --enable-intake flag
- 防线 5 备份 + 7 天 rollback: 每次入库前备份 JSON, 7 天内可自动 rollback

W62 T6.2 D2 升级 - 灰度扩展 (5/25/100 三档)
- KB_INTAKE_GRAYSCALE env 或 --grayscale N 参数 (0-100 整数)
- 灰度逻辑: hash(question_id) % 100 < N → 进入入库路径
- 与 AUTO_KB_INTAKE_ENABLED=true 兼容 (= grayscale=100)
- 与 --enable-intake flag 兼容 (隐含 grayscale=100)
- observer 集成: 每次 intake 调 observer.record_intake + 跑完检查 rollback

设计:
- 读 results/onebyone_log.jsonl
- 筛 auto_score >= 4 + intent in [explain_concept, search_info] + content >= 200 字
- POST /api/v1/knowledge/from-auto-expansion (服务端做幂等 + 质量门 + RichBlock 写入)
- 自动 batch_size=50/批, 失败继续, 完成后报告 saved/skipped/errors
- 备份到 backups/auto_intake_YYYYMMDD_HHMMSS.json

触发命令:
    # 默认 dry-run (灰度 = 0, 需 --enable-intake 或 AUTO_KB_INTAKE_ENABLED=true)
    python tests/qa-bench/save_to_kb.py --token <jwt>

    # 启用全自动 + grayscale=100 (隐含)
    python tests/qa-bench/save_to_kb.py --token <jwt> --enable-intake

    # 灰度 5% (D2 渐进开启)
    python tests/qa-bench/save_to_kb.py --token <jwt> --grayscale 5

    # 灰度 25% (D2 中阶段)
    python tests/qa-bench/save_to_kb.py --token <jwt> --grayscale 25

    # 灰度 100% (D2 全量, 等价 --enable-intake)
    python tests/qa-bench/save_to_kb.py --token <jwt> --grayscale 100

    # 7 天后自动 rollback (W5 T5.3 Celery task)
    # 写入: kb_id + created_at (7 天后 Celery 自动清)
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx

# W62 D2: observer 模块 (同目录)
sys.path.insert(0, str(Path(__file__).parent))
from observer import (
    check_rollback_threshold,
    get_daily_stats,
    record_intake,
)

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

# W62 D2: 灰度百分比 (0-100, 默认 0 完全跳过入库)
def _parse_grayscale_env() -> int:
    """解析 KB_INTAKE_GRAYSCALE env, 非法值降级为 0"""
    raw = os.environ.get("KB_INTAKE_GRAYSCALE", "0").strip()
    try:
        v = int(raw)
        if v < 0:
            return 0
        if v > 100:
            return 100
        return v
    except ValueError:
        return 0


KB_INTAKE_GRAYSCALE_ENV = _parse_grayscale_env()

# W5 防线 5: 备份目录
BACKUP_ROOT = Path("backups/auto_intake")
BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

# W5 T5.3: 7 天 rollback 标记
ROLLBACK_DAYS = 7


def is_in_grayscale(qa_id: str, grayscale_pct: int) -> bool:
    """灰度命中判定: 同一 question_id 永远命中同一档, 跨多次跑一致

    Args:
        qa_id: 题号 (e.g. "S-001")
        grayscale_pct: 0-100 整数百分比

    Returns:
        True if 该题本次应进入入库路径
    """
    if grayscale_pct <= 0:
        return False
    if grayscale_pct >= 100:
        return True
    # 稳定 hash: SHA-256 前 8 hex 字符 → int → mod 100
    h = hashlib.sha256(qa_id.encode("utf-8")).hexdigest()[:8]
    bucket = int(h, 16) % 100
    return bucket < grayscale_pct


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
        description="qa-bench 高分问答 → 自动拓展知识卡片 (#043) — D2 灰度版",
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
                   help="W5 防线 4: 显式启用全自动入库 (灰度 100%, 等价 --grayscale 100)")
    p.add_argument("--grayscale", type=int, default=None,
                   help="W62 D2: 灰度百分比 0-100 (与 --enable-intake / AUTO_KB_INTAKE_ENABLED 互斥时取大者)")
    args = p.parse_args()

    # W62 D2: 计算最终 grayscale (优先级: --grayscale > env KB_INTAKE_GRAYSCALE > --enable-intake 隐含 100 > env AUTO_KB_INTAKE_ENABLED 隐含 100)
    grayscale = 0
    if args.grayscale is not None:
        grayscale = max(0, min(100, args.grayscale))
    elif KB_INTAKE_GRAYSCALE_ENV > 0:
        grayscale = KB_INTAKE_GRAYSCALE_ENV
    elif args.enable_intake or AUTO_KB_INTAKE_ENABLED:
        grayscale = 100

    # 灰度 = 0 → dry-run (兼容旧行为)
    if grayscale <= 0:
        print("⚠️  灰度开关未启用: --grayscale N>0 或 --enable-intake 或 env AUTO_KB_INTAKE_ENABLED=true / KB_INTAKE_GRAYSCALE>0")
        print("    当前模式: dry-run (只统计候选, 不入库)")
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
        print("    如需真入库: 加 --grayscale 5/25/100 或 --enable-intake 或设 KB_INTAKE_GRAYSCALE=5")
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

    # W62 D2: 灰度过滤 (稳定 hash, 同一题跨多次跑命中一致)
    grayscale_candidates = [c for c in candidates if is_in_grayscale(c["qa_id"], grayscale)]
    grayscale_skipped = len(candidates) - len(grayscale_candidates)
    print(
        f"🎚️  灰度={grayscale}%, 命中={len(grayscale_candidates)} 题, "
        f"跳过={grayscale_skipped} 题"
    )

    if not grayscale_candidates:
        print("没有候选命中灰度, 无需入库")
        # 仍写 summary (灰度 = 0 入库但报告完整)
        summary = {
            "timestamp": datetime.now().isoformat(),
            "gray_flag_enabled": True,
            "grayscale_pct": grayscale,
            "min_score": args.min_score,
            "min_content_length": args.min_content_length,
            "allowed_intents": [s.strip() for s in args.allowed_intents.split(",") if s.strip()],
            "candidates_count": len(candidates),
            "grayscale_hit": 0,
            "grayscale_skipped": grayscale_skipped,
            "saved": 0,
            "skipped": 0,
            "errors": [],
            "rollback_window_days": ROLLBACK_DAYS,
        }
        summary_path = Path("data/auto_intake_summary.json")
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"📊 Dashboard 监控汇总写入 {summary_path}")
        return 0

    # W5 防线 5: 备份灰度命中候选到 JSON (rollback 入口)
    backup_path = BACKUP_ROOT / f"candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    backup_path.write_text(
        json.dumps(grayscale_candidates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"💾 备份灰度命中候选 → {backup_path} ({len(grayscale_candidates)} 条)")

    allowed_intents = [s.strip() for s in args.allowed_intents.split(",") if s.strip()]
    total_saved = 0
    total_skipped = 0
    total_errors: list[str] = []

    for i in range(0, len(grayscale_candidates), args.batch_size):
        batch = grayscale_candidates[i:i + args.batch_size]
        batch_num = i // args.batch_size + 1
        batch_qa_ids = [c["qa_id"] for c in batch]
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
            # W62 D2: observer 记录 (batch 成功 = 全部题 success)
            for qa_id in batch_qa_ids:
                record_intake(question_id=qa_id, success=True)
        except Exception as e:
            print(f"  batch {batch_num}: ❌ {e}")
            total_errors.append(f"batch {batch_num}: {e}")
            # W62 D2: observer 记录 (batch 失败 = 全部题 fail, 记第一条 error_msg)
            for qa_id in batch_qa_ids:
                record_intake(question_id=qa_id, success=False, error_msg=str(e)[:200])

    print(
        f"\n✅ 完成: saved={total_saved}, skipped={total_skipped}, "
        f"errors={len(total_errors)}"
    )

    # W5 T5.4 + W62 D2: Dashboard 监控汇总
    summary = {
        "timestamp": datetime.now().isoformat(),
        "gray_flag_enabled": True,
        "grayscale_pct": grayscale,
        "min_score": args.min_score,
        "min_content_length": args.min_content_length,
        "allowed_intents": allowed_intents,
        "candidates_count": len(candidates),
        "grayscale_hit": len(grayscale_candidates),
        "grayscale_skipped": grayscale_skipped,
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

    # W62 D2: rollback 检查 (error_rate > 5% AND 样本 ≥ 20)
    rollback = check_rollback_threshold()
    if rollback:
        stats = get_daily_stats()
        print(
            f"\n⚠️  ⚠️  ⚠️  ROLLBACK 触发条件达成 ⚠️  ⚠️  ⚠️"
        )
        print(
            f"   error_rate={stats['error_rate']:.2%} (阈值 5%)"
        )
        print(
            f"   今日 intake: total={stats['total']}, success={stats['success']}, "
            f"errors={stats['errors']}"
        )
        print(
            f"   自动切 grayscale=5 (下一档保守)"
        )
        print(
            f"   建议: 排查 errors 字段 / 联系 dev / 手动 disable intake"
        )

    return 0 if not total_errors else 1


if __name__ == "__main__":
    sys.exit(main())
