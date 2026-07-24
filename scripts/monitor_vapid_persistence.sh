#!/usr/bin/env bash
# scripts/monitor_vapid_persistence.sh
#
# W68 第 11 批 D-5: VAPID 密钥持久化实时监测脚本 (2026-07-24)
# 锚点范式第 146 守恒 — 主指挥 SSH 部署后跑, 保证 Web Push VAPID 密钥不丢/不变。
#
# 背景 (docs/mobile-pwa-push-backend.md §2):
#   VAPID 密钥**必须**持久化到磁盘, 否则每次重启生成新 key →
#   所有已订阅用户的 push subscription 全部失效 (公钥变了, 老订阅无法解密)。
#   公钥**变更**是私钥泄露/被覆盖的强信号, 必须报警。
#
# 检查项:
#   §1 持久化目录存在 (默认 /data/push)
#   §2 私钥文件存在 (vapid_private.pem) + 权限 600
#   §3 公钥文件存在 (vapid_public.pem)
#   §4 后端 /api/v1/push/vapid-public-key 返公钥 (base64url)
#   §5 公钥值不变 (上次检查记录 vs 当前) — 变更 = 报警
#
# 报警条件 (退出码 1):
#   - 缺持久化目录
#   - 缺私钥/公钥文件
#   - 公钥变更 (私钥泄露/覆盖信号)
#
# 日志: logs/vapid-monitor-$(date +%Y%m%d).log
# 基线快照: logs/.vapid-public-key.baseline (跨运行持久化, 供公钥对比)
#
# 必做时机 (docs/main-command-scripts-2026-07-24.md):
#   - 部署后 24h 内一次
#   - 每周 1 次例行
#   - 季度 backup (scp vapid_*.pem) 前一次
#
# 纪律:
#   - 仅 scripts/, 0 production code 改动
#   - 兼容 Linux (云 server) + Windows Git Bash (本地 PC)
#
# 用法:
#   bash scripts/monitor_vapid_persistence.sh
#   VAPID_DIR=/data/push BASE_URL=https://agent.mnb-lab.cn bash scripts/monitor_vapid_persistence.sh
#
# 环境变量 (全部可选):
#   VAPID_DIR         - VAPID 持久化目录, 默认 /data/push
#   VAPID_PRIVATE     - 私钥文件名, 默认 vapid_private.pem
#   VAPID_PUBLIC      - 公钥文件名, 默认 vapid_public.pem
#   BASE_URL          - 后端 API base, 默认 https://localhost
#   BASELINE_FILE     - 公钥基线快照路径, 默认 logs/.vapid-public-key.baseline
#   DRY_RUN           - 1 = 只打印不真跑, 默认 0
#
# 退出码: 0 = 全部正常 / 1 = 有报警 (需人工介入) / 2 = 配置错误

set -u

# ---------- 0. 颜色 + 工具 ----------
if [ -t 1 ] && command -v tput >/dev/null 2>&1 && [ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]; then
    GREEN="$(tput setaf 2)"; RED="$(tput setaf 1)"; YELLOW="$(tput setaf 3)"
    BLUE="$(tput setaf 4)"; BOLD="$(tput bold)"; RESET="$(tput sgr0)"
else
    GREEN=""; RED=""; YELLOW=""; BLUE=""; BOLD=""; RESET=""
fi

VAPID_DIR="${VAPID_DIR:-/data/push}"
VAPID_PRIVATE="${VAPID_PRIVATE:-vapid_private.pem}"
VAPID_PUBLIC="${VAPID_PUBLIC:-vapid_public.pem}"
BASE_URL="${BASE_URL:-https://localhost}"
BASE_URL="${BASE_URL%/}"
DRY_RUN="${DRY_RUN:-0}"

# 日志目录 (相对仓库根或当前目录)
LOG_DIR="${LOG_DIR:-logs}"
mkdir -p "$LOG_DIR" 2>/dev/null || true
LOG_FILE="${LOG_DIR}/vapid-monitor-$(date +%Y%m%d).log"
BASELINE_FILE="${BASELINE_FILE:-${LOG_DIR}/.vapid-public-key.baseline}"

ALERT_COUNT=0; PASS_COUNT=0

_ts() { date '+%Y-%m-%d %H:%M:%S'; }
_write_log() { printf '[%s] %s\n' "$(_ts)" "$1" >> "$LOG_FILE" 2>/dev/null || true; }
log_pass()  { printf "  %s✓ PASS%s  %s\n" "$GREEN" "$RESET" "$1"; _write_log "PASS  $1"; PASS_COUNT=$((PASS_COUNT+1)); }
log_alert() { printf "  %s✗ ALERT%s %s\n" "$RED" "$RESET" "$1"; [ -n "${2:-}" ] && printf "          原因: %s\n" "$2"; _write_log "ALERT $1 ${2:-}"; ALERT_COUNT=$((ALERT_COUNT+1)); }
log_info()  { printf "  %s·%s      %s\n" "$BLUE" "$RESET" "$1"; _write_log "INFO  $1"; }
log_warn()  { printf "  %s!%s      %s\n" "$YELLOW" "$RESET" "$1"; _write_log "WARN  $1"; }
section()   { printf "\n%s== %s ==%s\n" "$BOLD" "$1" "$RESET"; _write_log "=== $1 ==="; }

section "VAPID 密钥持久化监测 (W68 第 11 批 D-5)"
log_info "VAPID_DIR     = ${VAPID_DIR}"
log_info "BASE_URL      = ${BASE_URL}"
log_info "LOG_FILE      = ${LOG_FILE}"
log_info "BASELINE_FILE = ${BASELINE_FILE}"
log_info "DRY_RUN       = ${DRY_RUN}"

CURL_BIN="$(command -v curl || true)"
PRIV_PATH="${VAPID_DIR}/${VAPID_PRIVATE}"
PUB_PATH="${VAPID_DIR}/${VAPID_PUBLIC}"

if [ "$DRY_RUN" = "1" ]; then
    log_info "DRY_RUN — 打印将执行的检查, 不真跑"
    log_info "  [1] test -d ${VAPID_DIR}"
    log_info "  [2] test -f ${PRIV_PATH} && stat perm == 600"
    log_info "  [3] test -f ${PUB_PATH}"
    log_info "  [4] curl -sk ${BASE_URL}/api/v1/push/vapid-public-key"
    log_info "  [5] diff 当前公钥 vs ${BASELINE_FILE}"
    exit 0
fi

# ---------- §1 持久化目录 ----------
section "§1 持久化目录"
if [ -d "$VAPID_DIR" ]; then
    log_pass "持久化目录存在: ${VAPID_DIR}"
else
    log_alert "持久化目录缺失: ${VAPID_DIR}" "重启后 VAPID key 会重新生成 → 所有订阅失效。请挂载 volume 或 mkdir -p ${VAPID_DIR}"
fi

# ---------- §2 私钥文件 + 权限 ----------
section "§2 私钥文件 + 权限"
if [ -f "$PRIV_PATH" ]; then
    log_pass "私钥存在: ${PRIV_PATH}"
    # 权限检查 (Linux stat -c; macOS/BSD stat -f; Git Bash 可能无 stat)
    PERM=""
    if stat -c '%a' "$PRIV_PATH" >/dev/null 2>&1; then
        PERM="$(stat -c '%a' "$PRIV_PATH")"
    elif stat -f '%Lp' "$PRIV_PATH" >/dev/null 2>&1; then
        PERM="$(stat -f '%Lp' "$PRIV_PATH")"
    fi
    if [ -z "$PERM" ]; then
        log_warn "无法读取权限 (Git Bash/Windows 无 POSIX stat) — 跳过权限检查"
    elif [ "$PERM" = "600" ] || [ "$PERM" = "400" ]; then
        log_pass "私钥权限安全: ${PERM}"
    else
        log_warn "私钥权限 ${PERM} 非 600/400 — 建议 chmod 600 ${PRIV_PATH} (防泄露)"
    fi
else
    log_alert "私钥缺失: ${PRIV_PATH}" "VAPID 未持久化, 重启后会重新生成。"
fi

# ---------- §3 公钥文件 ----------
section "§3 公钥文件"
FILE_PUB=""
if [ -f "$PUB_PATH" ]; then
    log_pass "公钥文件存在: ${PUB_PATH}"
    FILE_PUB="$(cat "$PUB_PATH" 2>/dev/null | tr -d '[:space:]')"
else
    log_alert "公钥文件缺失: ${PUB_PATH}" "客户端 subscribe 需要公钥。"
fi

# ---------- §4 后端 endpoint 返公钥 ----------
section "§4 后端 /api/v1/push/vapid-public-key"
API_PUB=""
if [ -z "$CURL_BIN" ]; then
    log_warn "curl 缺失 — 跳过 endpoint 检查"
else
    RESP="$("$CURL_BIN" -sk --max-time 10 "${BASE_URL}/api/v1/push/vapid-public-key" 2>/dev/null || true)"
    if [ -z "$RESP" ]; then
        log_alert "endpoint 无响应" "curl -sk ${BASE_URL}/api/v1/push/vapid-public-key 返回空。检查后端是否启动。"
    else
        # 提取 base64url 公钥 (JSON {"public_key":"..."} 或 {"vapid_public_key":"..."} 或纯串)
        API_PUB="$(printf '%s' "$RESP" | grep -oE '[A-Za-z0-9_-]{80,}' | head -1)"
        if [ -n "$API_PUB" ]; then
            log_pass "endpoint 返公钥 (长度 ${#API_PUB}, 前 12 位 ${API_PUB:0:12}...)"
        else
            log_alert "endpoint 响应无有效公钥" "响应片段: $(printf '%s' "$RESP" | head -c 120)"
        fi
    fi
fi

# ---------- §5 公钥值不变 (基线对比) ----------
section "§5 公钥不变性 (私钥泄露/覆盖信号)"
CURRENT_PUB="${API_PUB:-$FILE_PUB}"
if [ -z "$CURRENT_PUB" ]; then
    log_warn "无法确定当前公钥 (文件与 endpoint 均未拿到) — 跳过对比"
elif [ -f "$BASELINE_FILE" ]; then
    BASELINE_PUB="$(cat "$BASELINE_FILE" 2>/dev/null | tr -d '[:space:]')"
    if [ "$CURRENT_PUB" = "$BASELINE_PUB" ]; then
        log_pass "公钥与基线一致 (未变更) — 前 12 位 ${CURRENT_PUB:0:12}..."
    else
        log_alert "公钥已变更!" "基线 ${BASELINE_PUB:0:12}... → 当前 ${CURRENT_PUB:0:12}... 私钥可能被覆盖/泄露/重生成, 所有旧订阅失效。确认无恶意后手动更新基线: echo '${CURRENT_PUB}' > ${BASELINE_FILE}"
    fi
    # 文件公钥 vs endpoint 公钥一致性
    if [ -n "$FILE_PUB" ] && [ -n "$API_PUB" ] && [ "$FILE_PUB" != "$API_PUB" ]; then
        log_alert "文件公钥与 endpoint 公钥不一致" "磁盘 ${FILE_PUB:0:12}... != API ${API_PUB:0:12}... 后端可能加载了不同的 key。"
    fi
else
    log_info "首次运行 — 写入基线快照 ${BASELINE_FILE}"
    printf '%s\n' "$CURRENT_PUB" > "$BASELINE_FILE" 2>/dev/null && log_pass "基线已建立 (前 12 位 ${CURRENT_PUB:0:12}...)" || log_warn "基线写入失败 (只读文件系统?)"
fi

# ---------- 汇总 ----------
section "汇总"
log_info "PASS = ${PASS_COUNT}   ALERT = ${ALERT_COUNT}"
_write_log "SUMMARY PASS=${PASS_COUNT} ALERT=${ALERT_COUNT}"
if [ "$ALERT_COUNT" -gt 0 ]; then
    printf "\n%s✗ 有 %d 项报警, 需人工介入。%s 详见 %s\n" "$RED" "$ALERT_COUNT" "$RESET" "$LOG_FILE"
    printf "%s恢复路径:%s\n" "$BOLD" "$RESET"
    printf "  1. 缺目录: mkdir -p %s && docker compose restart app (会重新生成并写盘)\n" "$VAPID_DIR"
    printf "  2. 缺密钥: 确认 volume 挂载 (docker inspect microbubble-agent-app-1 | grep %s)\n" "$VAPID_DIR"
    printf "  3. 公钥变更: 若为私钥泄露, 立即轮换 + 通知用户重新订阅; 若为合法重生成, 更新基线\n"
    exit 1
fi
printf "\n%s✓ VAPID 持久化健康。%s 日志: %s\n" "$GREEN" "$RESET" "$LOG_FILE"
exit 0
