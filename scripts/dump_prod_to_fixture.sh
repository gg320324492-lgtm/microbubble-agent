#!/usr/bin/env bash
# scripts/dump_prod_to_fixture.sh — 导出生产数据快照供 qa-bench 隔离测试栈灌入
#
# W68 第 7 批 A-3 (2026-07-24): plan qa-bench-isolation-a1.md 核心交付物.
#
# 流程:
#   1. pg_dump --data-only 生产数据 (排除 alembic_version + 大日志表)
#   2. 写入 fixtures/prod_dump_$(date +%Y%m%d).sql
#   3. 提示下一步 sanitize (脱敏) — 本脚本不自动脱敏, 保证原始快照可追溯
#
# ⚠️ 默认 dry-run (只 echo pg_dump 命令, 不真跑). 加 --apply 才真导出.
# ⚠️ dump 产物含 PII (email/phone/wechat_id), 必须经 sanitize_fixture.py --apply 脱敏
#    才能进 git. .gitignore 已排除 fixtures/*.sql (仅 *.sanitized.sql 白名单可提交).
#
# 用法:
#   bash scripts/dump_prod_to_fixture.sh                       # dry-run (默认)
#   bash scripts/dump_prod_to_fixture.sh --apply               # 真导出
#   PROD_DATABASE_URL=postgresql://... bash scripts/dump_prod_to_fixture.sh --apply

set -euo pipefail

APPLY=0
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    *) echo "未知参数: $arg" >&2; exit 2 ;;
  esac
done

PROD_URL="${PROD_DATABASE_URL:-postgresql://postgres:microbubble2026@localhost:5432/microbubble}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE_DIR="${FIXTURE_DIR:-$REPO_ROOT/fixtures}"
TS="$(date +%Y%m%d)"
FIXTURE_FILE="$FIXTURE_DIR/prod_dump_${TS}.sql"

# 排除表: alembic_version (每栈自己 alembic upgrade head) + 大审计日志表
EXCLUDE_ARGS=(
  --exclude-table=alembic_version
  --exclude-table=audit_log
  --exclude-table=login_history
)

DUMP_CMD=(pg_dump --data-only --no-privileges --no-owner "${EXCLUDE_ARGS[@]}" "$PROD_URL")

echo "==> qa-bench 生产数据 dump"
echo "    PROD_URL      : ${PROD_URL%%@*}@***(masked)"
echo "    FIXTURE_FILE  : $FIXTURE_FILE"
echo "    EXCLUDE       : alembic_version, audit_log, login_history"

if [[ "$APPLY" -eq 0 ]]; then
  echo
  echo "[dry-run] 未加 --apply, 不真导出. 将执行的命令:"
  printf '    %q ' "${DUMP_CMD[@]}"; echo "> $FIXTURE_FILE"
  echo
  echo "下一步 (加 --apply 后):"
  echo "    1. bash scripts/dump_prod_to_fixture.sh --apply"
  echo "    2. python scripts/sanitize_fixture.py $FIXTURE_FILE --apply"
  echo "    3. python tests/qa-bench/runner.py --use-test-stack --fixture-sql fixtures/prod_dump_${TS}.sanitized.sql ..."
  exit 0
fi

mkdir -p "$FIXTURE_DIR"

echo
echo "[1/3] 检查生产 DB 连通性..."
if ! pg_isready -d "$PROD_URL" >/dev/null 2>&1; then
  echo "ERROR: 生产 DB 不可达 ($PROD_URL). 检查 PROD_DATABASE_URL." >&2
  exit 1
fi

echo "[2/3] pg_dump 导出 (--data-only)..."
"${DUMP_CMD[@]}" > "$FIXTURE_FILE"

LINES="$(wc -l < "$FIXTURE_FILE")"
SIZE="$(du -h "$FIXTURE_FILE" | awk '{print $1}')"
if [[ "$LINES" -lt 10 ]]; then
  echo "ERROR: dump 只有 $LINES 行, 疑似空导出. 检查生产 DB." >&2
  exit 1
fi

echo "[3/3] 完成: $FIXTURE_FILE ($SIZE, $LINES 行)"
echo
echo "⚠️  该文件含 PII, 未脱敏严禁进 git. 下一步脱敏:"
echo "    python scripts/sanitize_fixture.py $FIXTURE_FILE --apply"
