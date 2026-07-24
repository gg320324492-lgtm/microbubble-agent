#!/usr/bin/env bash
# scripts/monitor_deployment_health.sh
#
# W68 第 11 批 D-5: 部署健康实时监测脚本 (2026-07-24)
# 锚点范式第 146 守恒 — 主指挥 SSH 部署后跑, 一键探活 6 endpoint + alembic + baseline。
#
# 背景:
#   W68 累计 170 commits + Drive v2 PR8-12 + Mobile PWA push + qa-bench D6。
#   部署后需要一键探活: endpoint 5xx / 5xx 比率 / alembic 多头 / baseline drift。
#   alembic 多头 (heads != 1) 是 W68 第 3 批的真实事故 (CLAUDE.md 2026-07-24 铁律),
#   会直接阻塞 `alembic upgrade head`, 必须监测。
#
# 检查项:
#   §1 6 endpoint 健康 (逐个探活):
#       /health                              (公开, 期望 200)
#       /api/v1/push/vapid-public-key        (公开, 期望 200)
#       /api/v1/drive/comments               (鉴权, 期望 200 或 401)
#       /api/v1/auth/me                      (鉴权, 期望 200 或 401)
#       /api/v1/chat/sessions                (鉴权, 期望 200 或 401)
#       /api/v1/knowledge                    (鉴权, 期望 200 或 401)
#   §2 5xx 报警: 任一 endpoint 返 5xx
#   §3 5xx 比率: 采样 N 次 /health, 5xx 比率 > 1% 报警
#   §4 alembic heads == 1 (多头阻塞部署)
#   §5 baseline == 71 PASS + 7 SKIP (Lint/CSS 守恒)
#
# 报警条件 (退出码 1):
#   - 任一 endpoint 5xx
#   - 5xx 比率 > 1%
#   - alembic heads != 1
#   - baseline != 71+7 (drift)
#
# 日志: logs/deployment-health-$(date +%Y%m%d).log
#
# 必做时机 (docs/main-command-scripts-2026-07-24.md):
#   - 部署后 1h 内一次
#   - 每天 1 次例行
#   - 任何异常报告时立即
#
# 纪律: 仅 scripts/, 0 production code 改动; 兼容 Linux + Windows Git Bash
#
# 用法:
#   bash scripts/monitor_deployment_health.sh
#   BASE_URL=https://agent.mnb-lab.cn TOKEN=eyJ... bash scripts/monitor_deployment_health.sh
#
# 环境变量 (全部可选):
#   BASE_URL         - 后端 API base, 默认 https://localhost
#   TOKEN            - JWT (有则鉴权 endpoint 期望 200, 无则期望 401)
#   SAMPLE_COUNT     - 5xx 比率采样次数, 默认 20
#   RATE_THRESHOLD   - 5xx 比率报警阈值 (%), 默认 1
#   CHECK_ALEMBIC    - 1 = 检查 alembic heads (需 docker), 默认 1
#   CHECK_BASELINE   - 1 = 检查 lint baseline (需本地跑), 默认 0 (云上跳过)
#   BASELINE_PASS    - 期望 PASS 数, 默认 71
#   BASELINE_SKIP    - 期望 SKIP 数, 默认 7
#   APP_CONTAINER    - app 容器名, 默认 microbubble-agent-app-1
#   DRY_RUN          - 1 = 只打印不真跑, 默认 0
#
# 退出码: 0 = 健康 / 1 = 报警 / 2 = 配置错误

set -u

# ---------- 0. 颜色 + 工具 ----------
if [ -t 1 ] && command -v tput >/dev/null 2>&1 && [ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]; then
    GREEN="$(tput setaf 2)"; RED="$(tput setaf 1)"; YELLOW="$(tput setaf 3)"
    BLUE="$(tput setaf 4)"; BOLD="$(tput bold)"; RESET="$(tput sgr0)"
else
    GREEN=""; RED=""; YELLOW=""; BLUE=""; BOLD=""; RESET=""
fi

BASE_URL="${BASE_URL:-https://localhost}"
BASE_URL="${BASE_URL%/}"
TOKEN="${TOKEN:-}"
SAMPLE_COUNT="${SAMPLE_COUNT:-20}"
RATE_THRESHOLD="${RATE_THRESHOLD:-1}"
CHECK_ALEMBIC="${CHECK_ALEMBIC:-1}"
CHECK_BASELINE="${CHECK_BASELINE:-0}"
BASELINE_PASS="${BASELINE_PASS:-71}"
BASELINE_SKIP="${BASELINE_SKIP:-7}"
APP_CONTAINER="${APP_CONTAINER:-microbubble-agent-app-1}"
DRY_RUN="${DRY_RUN:-0}"

LOG_DIR="${LOG_DIR:-logs}"
mkdir -p "$LOG_DIR" 2>/dev/null || true
LOG_FILE="${LOG_DIR}/deployment-health-$(date +%Y%m%d).log"

ALERT_COUNT=0; PASS_COUNT=0

_ts() { date '+%Y-%m-%d %H:%M:%S'; }
_write_log() { printf '[%s] %s\n' "$(_ts)" "$1" >> "$LOG_FILE" 2>/dev/null || true; }
log_pass()  { printf "  %s✓ PASS%s  %s\n" "$GREEN" "$RESET" "$1"; _write_log "PASS  $1"; PASS_COUNT=$((PASS_COUNT+1)); }
log_alert() { printf "  %s✗ ALERT%s %s\n" "$RED" "$RESET" "$1"; [ -n "${2:-}" ] && printf "          原因: %s\n" "$2"; _write_log "ALERT $1 ${2:-}"; ALERT_COUNT=$((ALERT_COUNT+1)); }
log_info()  { printf "  %s·%s      %s\n" "$BLUE" "$RESET" "$1"; _write_log "INFO  $1"; }
log_warn()  { printf "  %s!%s      %s\n" "$YELLOW" "$RESET" "$1"; _write_log "WARN  $1"; }
section()   { printf "\n%s== %s ==%s\n" "$BOLD" "$1" "$RESET"; _write_log "=== $1 ==="; }

CURL_BIN="$(command -v curl || true)"
DOCKER_BIN="$(command -v docker || true)"

section "部署健康监测 (W68 第 11 批 D-5)"
log_info "BASE_URL       = ${BASE_URL}"
log_info "TOKEN          = $([ -n "$TOKEN" ] && echo "<已设置, 鉴权期望 200>" || echo "<空, 鉴权期望 401>")"
log_info "SAMPLE_COUNT   = ${SAMPLE_COUNT}"
log_info "RATE_THRESHOLD = ${RATE_THRESHOLD}%"
log_info "CHECK_ALEMBIC  = ${CHECK_ALEMBIC}   CHECK_BASELINE = ${CHECK_BASELINE}"
log_info "LOG_FILE       = ${LOG_FILE}"
log_info "DRY_RUN        = ${DRY_RUN}"

# ---------- safe curl: 返回 HTTP status code ----------
http_status() {
    # $1 = url, $2 = auth (1=带token, 0=不带)
    local url="$1" auth="${2:-0}"
    if [ -z "$CURL_BIN" ]; then echo "000"; return; fi
    if [ "$auth" = "1" ] && [ -n "$TOKEN" ]; then
        "$CURL_BIN" -sk -o /dev/null -w "%{http_code}" --max-time 10 \
            -H "Authorization: Bearer ${TOKEN}" "$url" 2>/dev/null || echo "000"
    else
        "$CURL_BIN" -sk -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000"
    fi
}

if [ "$DRY_RUN" = "1" ]; then
    log_info "DRY_RUN — 打印将执行的检查, 不真跑"
    log_info "  [1] curl 6 endpoint 状态码"
    log_info "  [2] 任一 5xx 报警"
    log_info "  [3] 采样 ${SAMPLE_COUNT} 次 /health, 5xx 比率 > ${RATE_THRESHOLD}% 报警"
    log_info "  [4] docker exec ${APP_CONTAINER} alembic heads (期望 1)"
    log_info "  [5] baseline == ${BASELINE_PASS} PASS + ${BASELINE_SKIP} SKIP"
    exit 0
fi

if [ -z "$CURL_BIN" ]; then
    log_alert "curl 缺失" "无法探活 endpoint。请安装 curl。"
fi

# ---------- §1 + §2: 6 endpoint 探活 + 5xx 报警 ----------
section "§1 6 endpoint 探活"
# 格式: "路径|auth(0/1)|描述"
ENDPOINTS="
/health|0|健康检查
/api/v1/push/vapid-public-key|0|VAPID 公钥
/api/v1/drive/comments|1|Drive 评论
/api/v1/auth/me|1|当前用户
/api/v1/chat/sessions|1|聊天会话
/api/v1/knowledge|1|知识库
"

if [ -n "$CURL_BIN" ]; then
    while IFS='|' read -r path auth desc; do
        [ -z "$path" ] && continue
        url="${BASE_URL}${path}"
        code="$(http_status "$url" "$auth")"
        if [ "${code:0:1}" = "5" ]; then
            log_alert "${desc} (${path}) → ${code}" "5xx 服务端错误。检查 docker logs ${APP_CONTAINER}。"
        elif [ "$code" = "000" ]; then
            log_alert "${desc} (${path}) → 无响应" "连接失败/超时。后端是否启动 + FRP 隧道是否通?"
        elif [ "$auth" = "1" ] && [ -z "$TOKEN" ]; then
            # 无 token 时鉴权 endpoint 期望 401/403
            if [ "$code" = "401" ] || [ "$code" = "403" ]; then
                log_pass "${desc} (${path}) → ${code} (无 token 正确拒绝)"
            elif [ "$code" = "200" ]; then
                log_warn "${desc} (${path}) → 200 (无 token 却放行? 检查鉴权)"
            else
                log_warn "${desc} (${path}) → ${code} (非 5xx, 记录)"
            fi
        else
            if [ "$code" = "200" ]; then
                log_pass "${desc} (${path}) → 200"
            else
                log_warn "${desc} (${path}) → ${code} (非 200/5xx, 记录)"
            fi
        fi
    done <<< "$ENDPOINTS"
else
    log_warn "curl 缺失 — endpoint 探活全部 skip"
fi

# ---------- §3: 5xx 比率采样 ----------
section "§3 5xx 比率 (/health × ${SAMPLE_COUNT})"
if [ -n "$CURL_BIN" ]; then
    fail5xx=0; total=0
    i=0
    while [ "$i" -lt "$SAMPLE_COUNT" ]; do
        code="$(http_status "${BASE_URL}/health" 0)"
        total=$((total+1))
        [ "${code:0:1}" = "5" ] && fail5xx=$((fail5xx+1))
        i=$((i+1))
    done
    # 比率 = fail5xx * 100 / total (整数百分比, 保留判断)
    if [ "$total" -gt 0 ]; then
        rate_x100=$(( fail5xx * 10000 / total ))   # 万分比, 精度更高
        rate_pct=$(( rate_x100 / 100 ))
        rate_frac=$(( rate_x100 % 100 ))
        threshold_x100=$(( RATE_THRESHOLD * 100 ))
        if [ "$rate_x100" -gt "$threshold_x100" ]; then
            log_alert "5xx 比率 ${rate_pct}.${rate_frac}% (${fail5xx}/${total}) > ${RATE_THRESHOLD}%" "后端不稳定, 检查资源/日志。"
        else
            log_pass "5xx 比率 ${rate_pct}.${rate_frac}% (${fail5xx}/${total}) <= ${RATE_THRESHOLD}%"
        fi
    fi
else
    log_warn "curl 缺失 — 5xx 比率 skip"
fi

# ---------- §4: alembic heads == 1 ----------
section "§4 alembic heads == 1"
if [ "$CHECK_ALEMBIC" != "1" ]; then
    log_info "CHECK_ALEMBIC=0 — 跳过"
elif [ -z "$DOCKER_BIN" ]; then
    log_warn "docker 缺失 — alembic 检查 skip"
else
    if ! "$DOCKER_BIN" ps --format '{{.Names}}' 2>/dev/null | grep -q "^${APP_CONTAINER}$"; then
        log_warn "容器 ${APP_CONTAINER} 未运行 — alembic 检查 skip"
    else
        HEADS_OUT="$("$DOCKER_BIN" exec -e SKIP_DB_SETUP=1 "$APP_CONTAINER" alembic heads 2>/dev/null || true)"
        # 统计 head 行数 (每个 head 一行, 含 (head))
        HEAD_LINES="$(printf '%s\n' "$HEADS_OUT" | grep -c '(head)' 2>/dev/null || echo 0)"
        if [ "$HEAD_LINES" = "1" ]; then
            log_pass "alembic 单 head (部署链健康)"
        elif [ "$HEAD_LINES" = "0" ]; then
            log_warn "alembic heads 输出无 (head) 标记 — 检查 alembic 配置: ${HEADS_OUT}"
        else
            log_alert "alembic ${HEAD_LINES} 个 head (多头!)" "会阻塞 alembic upgrade head。串单链 (改 down_revision) 后重跑。参考 CLAUDE.md 2026-07-24 alembic 铁律。"
        fi
    fi
fi

# ---------- §5: baseline == 71 PASS + 7 SKIP ----------
section "§5 lint baseline (${BASELINE_PASS} PASS + ${BASELINE_SKIP} SKIP)"
if [ "$CHECK_BASELINE" != "1" ]; then
    log_info "CHECK_BASELINE=0 — 跳过 (云 server 无前端 devDeps, 本地跑设 CHECK_BASELINE=1)"
else
    if [ -f "web/package.json" ] && command -v npm >/dev/null 2>&1; then
        log_info "跑 lint (可能较慢)..."
        LINT_OUT="$(cd web && npm run lint 2>&1 || true)"
        P="$(printf '%s' "$LINT_OUT" | grep -oE '[0-9]+ pass' | grep -oE '[0-9]+' | head -1)"
        S="$(printf '%s' "$LINT_OUT" | grep -oE '[0-9]+ skip' | grep -oE '[0-9]+' | head -1)"
        P="${P:-?}"; S="${S:-?}"
        if [ "$P" = "$BASELINE_PASS" ] && [ "$S" = "$BASELINE_SKIP" ]; then
            log_pass "baseline 守恒: ${P} PASS + ${S} SKIP"
        else
            log_alert "baseline drift: ${P} PASS + ${S} SKIP (期望 ${BASELINE_PASS}+${BASELINE_SKIP})" "有 lint 规则新增/回归。核对改动。"
        fi
    else
        log_warn "web/package.json 或 npm 缺失 — baseline 检查 skip"
    fi
fi

# ---------- 汇总 ----------
section "汇总"
log_info "PASS = ${PASS_COUNT}   ALERT = ${ALERT_COUNT}"
_write_log "SUMMARY PASS=${PASS_COUNT} ALERT=${ALERT_COUNT}"
if [ "$ALERT_COUNT" -gt 0 ]; then
    printf "\n%s✗ 有 %d 项报警。%s 详见 %s\n" "$RED" "$ALERT_COUNT" "$RESET" "$LOG_FILE"
    printf "%s恢复路径:%s\n" "$BOLD" "$RESET"
    printf "  1. endpoint 5xx: docker logs %s --tail 100 定位异常; docker compose restart app\n" "$APP_CONTAINER"
    printf "  2. 5xx 比率高: 检查 CPU/内存/DB 连接池; docker stats\n"
    printf "  3. alembic 多头: docker exec %s alembic heads → 改 down_revision 串单链 → 清 __pycache__ → upgrade head\n" "$APP_CONTAINER"
    printf "  4. baseline drift: cd web && npm run lint 看新增违规, 修复或更新基线\n"
    exit 1
fi
printf "\n%s✓ 部署健康。%s 日志: %s\n" "$GREEN" "$RESET" "$LOG_FILE"
exit 0
