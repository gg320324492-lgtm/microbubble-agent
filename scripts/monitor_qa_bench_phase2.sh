#!/usr/bin/env bash
# scripts/monitor_qa_bench_phase2.sh
#
# W68 第 11 批 D-5: qa-bench D6 Phase 2 报告实时监测脚本 (2026-07-24)
# 锚点范式第 146 守恒 — Phase 2 真跑后主指挥 SSH 跑, 保证 7 维评分完整 + 90% gate 守住。
#
# 背景:
#   qa-bench v3.0 6 周冲刺 (memory/qa-bench-v3-w1-2026-06-30.md):
#     700 题库 + 3-tier 阈值 + 7 维雷达图。
#   D6 matrix (W68 第 8 批 fallback) Phase 2 真跑产出 phase2 报告 (JSON),
#   本脚本校验报告结构完整 + gate 达标, 防"绿条骗人"(报告缺维度/gate 静默降级)。
#
# 7 维评分 (雷达图):
#   accuracy / completeness / relevance / tool_use /
#   citation / conciseness / safety  (可通过 DIMENSIONS 覆盖)
#
# 检查项:
#   §1 phase2 报告文件存在 (默认 qa-bench/reports/phase2_latest.json)
#   §2 报告为合法 JSON
#   §3 7 维评分字段全部存在且为数值
#   §4 90% gate: overall_score >= GATE_THRESHOLD (默认 0.90)
#   §5 pass_rate / 题目数 sanity (非 0, 覆盖 >= MIN_QUESTIONS)
#   §6 报告新鲜度 (mtime 距今 <= MAX_AGE_HOURS, 防看旧报告)
#
# 报警条件 (退出码 1):
#   - 缺报告
#   - JSON 非法
#   - 7 维评分任一缺失/非数值
#   - overall_score < gate
#   - 报告过旧 (陈旧 = 未真跑)
#
# 日志: logs/qa-bench-phase2-monitor-$(date +%Y%m%d).log
#
# 必做时机 (docs/main-command-scripts-2026-07-24.md):
#   - Phase 2 真跑后立即
#   - 每周 1 次 smoke (确认 gate 未回归)
#
# 纪律: 仅 scripts/, 0 production code 改动; 兼容 Linux + Windows Git Bash
#
# 用法:
#   bash scripts/monitor_qa_bench_phase2.sh
#   REPORT=qa-bench/reports/phase2_20260724.json GATE_THRESHOLD=0.90 bash scripts/monitor_qa_bench_phase2.sh
#
# 环境变量 (全部可选):
#   REPORT           - phase2 报告 JSON 路径, 默认 qa-bench/reports/phase2_latest.json
#   GATE_THRESHOLD   - 90% gate 阈值 (0-1), 默认 0.90
#   MIN_QUESTIONS    - 最少覆盖题数, 默认 30
#   MAX_AGE_HOURS    - 报告最大陈旧小时数, 默认 168 (7 天)
#   DIMENSIONS       - 7 维字段名 (空格分隔), 覆盖默认
#   DRY_RUN          - 1 = 只打印不真跑, 默认 0
#
# 退出码: 0 = gate 达标 / 1 = 报警 / 2 = 配置错误

set -u

# ---------- 0. 颜色 + 工具 ----------
if [ -t 1 ] && command -v tput >/dev/null 2>&1 && [ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]; then
    GREEN="$(tput setaf 2)"; RED="$(tput setaf 1)"; YELLOW="$(tput setaf 3)"
    BLUE="$(tput setaf 4)"; BOLD="$(tput bold)"; RESET="$(tput sgr0)"
else
    GREEN=""; RED=""; YELLOW=""; BLUE=""; BOLD=""; RESET=""
fi

REPORT="${REPORT:-qa-bench/reports/phase2_latest.json}"
GATE_THRESHOLD="${GATE_THRESHOLD:-0.90}"
MIN_QUESTIONS="${MIN_QUESTIONS:-30}"
MAX_AGE_HOURS="${MAX_AGE_HOURS:-168}"
DIMENSIONS="${DIMENSIONS:-accuracy completeness relevance tool_use citation conciseness safety}"
DRY_RUN="${DRY_RUN:-0}"

LOG_DIR="${LOG_DIR:-logs}"
mkdir -p "$LOG_DIR" 2>/dev/null || true
LOG_FILE="${LOG_DIR}/qa-bench-phase2-monitor-$(date +%Y%m%d).log"

ALERT_COUNT=0; PASS_COUNT=0

_ts() { date '+%Y-%m-%d %H:%M:%S'; }
_write_log() { printf '[%s] %s\n' "$(_ts)" "$1" >> "$LOG_FILE" 2>/dev/null || true; }
log_pass()  { printf "  %s✓ PASS%s  %s\n" "$GREEN" "$RESET" "$1"; _write_log "PASS  $1"; PASS_COUNT=$((PASS_COUNT+1)); }
log_alert() { printf "  %s✗ ALERT%s %s\n" "$RED" "$RESET" "$1"; [ -n "${2:-}" ] && printf "          原因: %s\n" "$2"; _write_log "ALERT $1 ${2:-}"; ALERT_COUNT=$((ALERT_COUNT+1)); }
log_info()  { printf "  %s·%s      %s\n" "$BLUE" "$RESET" "$1"; _write_log "INFO  $1"; }
log_warn()  { printf "  %s!%s      %s\n" "$YELLOW" "$RESET" "$1"; _write_log "WARN  $1"; }
section()   { printf "\n%s== %s ==%s\n" "$BOLD" "$1" "$RESET"; _write_log "=== $1 ==="; }

PYTHON_BIN=""
# 验证真能执行 (Windows Store 的 python3 是打开商店的假 stub, 会退出码 49)
if command -v python3 >/dev/null 2>&1 && python3 -c "pass" >/dev/null 2>&1; then PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1 && python -c "pass" >/dev/null 2>&1; then PYTHON_BIN="python"
fi

section "qa-bench D6 Phase 2 报告监测 (W68 第 11 批 D-5)"
log_info "REPORT         = ${REPORT}"
log_info "GATE_THRESHOLD = ${GATE_THRESHOLD}"
log_info "MIN_QUESTIONS  = ${MIN_QUESTIONS}"
log_info "MAX_AGE_HOURS  = ${MAX_AGE_HOURS}"
log_info "DIMENSIONS     = ${DIMENSIONS}"
log_info "LOG_FILE       = ${LOG_FILE}"
log_info "DRY_RUN        = ${DRY_RUN}"

if [ "$DRY_RUN" = "1" ]; then
    log_info "DRY_RUN — 打印将执行的检查, 不真跑"
    log_info "  [1] test -f ${REPORT}"
    log_info "  [2] python -c 'json.load(...)'"
    log_info "  [3] 7 维字段 (${DIMENSIONS}) 全在且为 number"
    log_info "  [4] overall_score >= ${GATE_THRESHOLD}"
    log_info "  [5] question_count >= ${MIN_QUESTIONS}"
    log_info "  [6] report mtime <= ${MAX_AGE_HOURS}h"
    exit 0
fi

# ---------- §1 报告存在 ----------
section "§1 phase2 报告存在"
if [ -f "$REPORT" ]; then
    log_pass "报告存在: ${REPORT}"
else
    log_alert "报告缺失: ${REPORT}" "Phase 2 未真跑, 或路径错误。先跑 D6 Phase 2 生成报告。"
    # 无报告无法继续
    section "汇总"
    log_info "PASS = ${PASS_COUNT}   ALERT = ${ALERT_COUNT}"
    _write_log "SUMMARY PASS=${PASS_COUNT} ALERT=${ALERT_COUNT}"
    printf "\n%s✗ 缺报告, 无法继续。%s 详见 %s\n" "$RED" "$RESET" "$LOG_FILE"
    exit 1
fi

# ---------- §6 报告新鲜度 (先查, 陈旧报告后续检查也无意义) ----------
section "§6 报告新鲜度"
NOW_EPOCH="$(date +%s)"
FILE_EPOCH=""
if stat -c '%Y' "$REPORT" >/dev/null 2>&1; then
    FILE_EPOCH="$(stat -c '%Y' "$REPORT")"
elif stat -f '%m' "$REPORT" >/dev/null 2>&1; then
    FILE_EPOCH="$(stat -f '%m' "$REPORT")"
fi
if [ -n "$FILE_EPOCH" ]; then
    AGE_HOURS=$(( (NOW_EPOCH - FILE_EPOCH) / 3600 ))
    if [ "$AGE_HOURS" -le "$MAX_AGE_HOURS" ]; then
        log_pass "报告新鲜 (${AGE_HOURS}h 前, 阈值 ${MAX_AGE_HOURS}h)"
    else
        log_alert "报告陈旧 (${AGE_HOURS}h 前 > ${MAX_AGE_HOURS}h)" "可能在看旧报告。请重新跑 Phase 2 真跑。"
    fi
else
    log_warn "无法读取 mtime — 跳过新鲜度检查"
fi

# ---------- §2-§5 需要 python 解析 JSON ----------
if [ -z "$PYTHON_BIN" ]; then
    log_warn "python 缺失 — §2-§5 JSON 结构/gate 检查全部 skip"
    section "汇总"
    log_info "PASS = ${PASS_COUNT}   ALERT = ${ALERT_COUNT}"
    _write_log "SUMMARY PASS=${PASS_COUNT} ALERT=${ALERT_COUNT} (python missing)"
    [ "$ALERT_COUNT" -gt 0 ] && exit 1 || exit 0
fi

section "§2-§5 JSON 结构 + 7 维 + gate"
# 用 python 一次性解析并输出结构化结果, shell 逐行判定
PY_OUT="$(REPORT="$REPORT" GATE_THRESHOLD="$GATE_THRESHOLD" MIN_QUESTIONS="$MIN_QUESTIONS" DIMENSIONS="$DIMENSIONS" "$PYTHON_BIN" - <<'PYEOF'
import json, os, sys

report = os.environ["REPORT"]
gate = float(os.environ["GATE_THRESHOLD"])
min_q = int(os.environ["MIN_QUESTIONS"])
dims = os.environ["DIMENSIONS"].split()

def emit(status, key, msg):
    # status: PASS / ALERT / INFO
    print(f"{status}\t{key}\t{msg}")

try:
    with open(report, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception as e:
    emit("ALERT", "json", f"JSON 解析失败: {e}")
    sys.exit(0)

emit("PASS", "json", "合法 JSON")

# 7 维评分: 支持 data["dimensions"][dim] 或 data["scores"][dim] 或顶层 data[dim]
def find_dim_container(d):
    for k in ("dimensions", "scores", "dimension_scores", "radar"):
        if isinstance(d.get(k), dict):
            return d[k]
    return d

dc = find_dim_container(data)
missing = []
non_num = []
present = []
for dim in dims:
    if dim not in dc:
        missing.append(dim)
    else:
        v = dc[dim]
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            present.append(f"{dim}={v}")
        else:
            non_num.append(f"{dim}={v!r}")

if missing:
    emit("ALERT", "dims", f"缺失维度: {', '.join(missing)}")
if non_num:
    emit("ALERT", "dims", f"非数值维度: {', '.join(non_num)}")
if not missing and not non_num:
    emit("PASS", "dims", f"7 维评分完整: {', '.join(present)}")

# overall_score / gate
overall = None
for k in ("overall_score", "overall", "total_score", "score"):
    v = data.get(k)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        overall = v
        break
if overall is None:
    # fallback: 7 维均值
    nums = [dc[d] for d in dims if isinstance(dc.get(d), (int, float)) and not isinstance(dc.get(d), bool)]
    if nums:
        overall = sum(nums) / len(nums)
        emit("INFO", "overall", f"报告无 overall_score, 用 7 维均值 {overall:.4f}")

if overall is None:
    emit("ALERT", "gate", "无法确定 overall_score, gate 无法评估")
else:
    # 归一化: 若 overall > 1 视作百分制
    norm = overall / 100.0 if overall > 1.0 else overall
    if norm >= gate:
        emit("PASS", "gate", f"90% gate 达标: overall={norm:.4f} >= {gate}")
    else:
        emit("ALERT", "gate", f"90% gate 失败: overall={norm:.4f} < {gate}")

# question_count
qc = None
for k in ("question_count", "total_questions", "num_questions", "count"):
    v = data.get(k)
    if isinstance(v, int):
        qc = v
        break
if qc is None and isinstance(data.get("results"), list):
    qc = len(data["results"])
if qc is None:
    emit("INFO", "count", "无法确定 question_count — 跳过覆盖检查")
elif qc >= min_q:
    emit("PASS", "count", f"覆盖题数 {qc} >= {min_q}")
else:
    emit("ALERT", "count", f"覆盖题数 {qc} < {min_q} (样本过少, gate 不可信)")
PYEOF
)"

# 逐行渲染 python 输出
while IFS=$'\t' read -r status key msg; do
    [ -z "$status" ] && continue
    case "$status" in
        PASS)  log_pass "[$key] $msg" ;;
        ALERT) log_alert "[$key] $msg" ;;
        INFO)  log_info "[$key] $msg" ;;
        *)     log_info "$status $key $msg" ;;
    esac
done <<< "$PY_OUT"

# ---------- 汇总 ----------
section "汇总"
log_info "PASS = ${PASS_COUNT}   ALERT = ${ALERT_COUNT}"
_write_log "SUMMARY PASS=${PASS_COUNT} ALERT=${ALERT_COUNT}"
if [ "$ALERT_COUNT" -gt 0 ]; then
    printf "\n%s✗ 有 %d 项报警。%s 详见 %s\n" "$RED" "$ALERT_COUNT" "$RESET" "$LOG_FILE"
    printf "%s恢复路径:%s\n" "$BOLD" "$RESET"
    printf "  1. 缺报告/陈旧: 重跑 Phase 2 真跑生成新报告\n"
    printf "  2. 7 维缺失: 检查评分 pipeline 是否所有维度都产出 (LLM-as-judge prompt)\n"
    printf "  3. gate 失败: 定位失败题目 (results[].score < 阈值), 分析是数据 bug 还是模型退化\n"
    exit 1
fi
printf "\n%s✓ Phase 2 gate 达标, 7 维完整。%s 日志: %s\n" "$GREEN" "$RESET" "$LOG_FILE"
exit 0
