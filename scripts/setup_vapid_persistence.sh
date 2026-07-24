#!/usr/bin/env bash
# scripts/setup_vapid_persistence.sh
#
# W68 第 10 批 C-3: VAPID 密钥持久化一键脚本 (2026-07-24)
#
# 背景:
#   push_service.py 启动时生成 VAPID 密钥 (公/私 PEM), 默认存 /data/push/.
#   **没做**: 部署必做的 (a) 目录创建 + (b) docker volume mount + (c) 验证
#   **后果**: 每次 docker compose restart, VAPID 重新生成, **所有用户
#            subscription 失效 → 用户需手动重新订阅** (浏览器弹"允许通知"框)
#
# 本脚本职责:
#   1. 创建 /data/push/ 持久化目录 (mkdir -p)
#   2. 检查是否已有 VAPID 密钥 (ls vapid_*.pem)
#   3. 如有: 提示 "已存在, 跳过" + 输出公钥
#   4. 如无: 启动 app 一次触发生成 + cp 到 /data/push + 重启 app 加载
#
# 用法 (主指挥 SSH 执行):
#   bash scripts/setup_vapid_persistence.sh              # dry-run 默认 (打印命令不真跑)
#   bash scripts/setup_vapid_persistence.sh --apply      # 真跑
#   bash scripts/setup_vapid_persistence.sh --reset      # 强制重新生成 (警告: 旧订阅失效)
#   bash scripts/setup_vapid_persistence.sh --check      # 仅检查状态 (不创建/不重启)
#
# 环境变量 (全部可选):
#   VAPID_DIR   - 持久化目录 (默认 /data/push, 容器外常用 /var/lib/microbubble/push)
#   APP_CONTAINER - app 容器名 (默认 microbubble-agent-app-1, 自动探测)
#
# 退出码:
#   0 = 成功 (key 已存在或新建)
#   1 = 失败 (目录权限 / docker 未起 / 容器没装 cryptography)
#   2 = 配置文件缺失
#
# 纪律 (W68 第 10 批 C-3):
#   - 仅 scripts/, 0 production code 改动 (push_service 增强另算新功能)
#   - 兼容 Linux (云 server) + Windows Git Bash (本地 PC 测试, dry-run 模式)
#   - 失败 fail-loud (exit 非 0)
#   - **永远不要**自动重启 app (主指挥拍板, 部署窗口管理)

set -u

# ============================================================================
# 配置
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd 2>/dev/null || pwd)"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "")"
DRY_RUN=1  # 默认 dry-run, --apply 切到 0
RESET_MODE=0
CHECK_ONLY=0

VAPID_DIR="${VAPID_DIR:-/data/push}"
APP_CONTAINER="${APP_CONTAINER:-microbubble-agent-app-1}"

LOG_PREFIX="[VAPID-SETUP]"
ERRORS=0

# ============================================================================
# 颜色 (Linux + Git Bash 都支持 ANSI)
# ============================================================================

if [ -t 1 ]; then
    C_RED='\033[0;31m'
    C_GREEN='\033[0;32m'
    C_YELLOW='\033[0;33m'
    C_BLUE='\033[0;34m'
    C_RESET='\033[0m'
else
    C_RED='' C_GREEN='' C_YELLOW='' C_BLUE='' C_RESET=''
fi

log()   { printf "${C_BLUE}${LOG_PREFIX}${C_RESET} %s\n" "$*"; }
ok()    { printf "${C_GREEN}${LOG_PREFIX} ✓${C_RESET} %s\n" "$*"; }
warn()  { printf "${C_YELLOW}${LOG_PREFIX} ⚠${C_RESET} %s\n" "$*"; }
err()   { printf "${C_RED}${LOG_PREFIX} ✗${C_RESET} %s\n" "$*" >&2; ERRORS=$((ERRORS + 1)); }
fatal() { err "$*"; exit 1; }

# ============================================================================
# 参数解析
# ============================================================================

for arg in "$@"; do
    case "$arg" in
        --apply)   DRY_RUN=0 ;;
        --dry-run) DRY_RUN=1 ;;
        --reset)   RESET_MODE=1; DRY_RUN=0 ;;
        --check)   CHECK_ONLY=1 ;;
        --help|-h)
            grep '^#' "${BASH_SOURCE[0]}" | sed 's/^# //; s/^#//'
            exit 0
            ;;
        *)
            err "未知参数: $arg"
            err "用法: bash $0 [--apply|--dry-run|--reset|--check|--help]"
            exit 1
            ;;
    esac
done

# ============================================================================
# 平台探测 (Linux vs Windows)
# ============================================================================

detect_platform() {
    case "$(uname -s 2>/dev/null || echo Windows)" in
        Linux*|Darwin*)  PLATFORM="unix" ;;
        *)                PLATFORM="windows" ;;
    esac
    log "平台探测: $PLATFORM (uname: $(uname -s 2>/dev/null || echo 'N/A'))"
}

# ============================================================================
# 工具函数
# ============================================================================

docker_available() {
    command -v docker >/dev/null 2>&1
}

container_running() {
    docker inspect --format='{{.State.Running}}' "$APP_CONTAINER" 2>/dev/null | grep -q true
}

run_cmd() {
    # dry-run 时打印, apply 时真跑
    local desc="$1"
    shift
    if [ "$DRY_RUN" = "1" ] && [ "$RESET_MODE" = "0" ]; then
        printf "${C_YELLOW}${LOG_PREFIX} [DRY-RUN]${C_RESET} %s\n" "$desc"
        printf "  ${C_YELLOW}→${C_RESET} %s\n" "$*"
    else
        log "$desc"
        if ! "$@"; then
            err "命令失败: $*"
            return 1
        fi
    fi
}

# ============================================================================
# 步骤 0: 前置检查
# ============================================================================

preflight() {
    log "========== 前置检查 =========="

    if [ -z "$REPO_ROOT" ]; then
        warn "不在 git 仓库里 (git rev-parse 失败), 跳过 REPO_ROOT 检查"
        warn "如需 --apply, 请在 microbubble-agent 仓库根目录跑"
    else
        ok "REPO_ROOT = $REPO_ROOT"
    fi

    # docker 可用性
    if docker_available; then
        ok "docker CLI 可用"
    else
        warn "docker CLI 不可用 → 仅能在主机上直接操作文件"
        warn "  本场景常见: 本地 PC Git Bash 测试 (Linux 服务器上有 docker)"
    fi

    # 平台提示
    if [ "$PLATFORM" = "windows" ] && [ "$DRY_RUN" = "0" ]; then
        warn "Windows 平台 + --apply: 仅能在容器/WSL 内操作"
        warn "  推荐: Git Bash 仅跑 --dry-run 验证, 真操作在 Linux 云 server 上"
    fi
}

# ============================================================================
# 步骤 1: 检查现有密钥
# ============================================================================

check_existing_keys() {
    log "========== 检查现有 VAPID 密钥 =========="
    log "VAPID_DIR = $VAPID_DIR"

    local priv="$VAPID_DIR/vapid_private.pem"
    local pub="$VAPID_DIR/vapid_public.pem"

    if [ -f "$priv" ] && [ -f "$pub" ]; then
        ok "VAPID 密钥已存在:"
        ok "  私钥: $priv ($(stat -c%s "$priv" 2>/dev/null || stat -f%z "$priv") bytes)"
        ok "  公钥: $pub ($(stat -c%s "$pub" 2>/dev/null || stat -f%z "$pub") bytes)"
        ok "  权限: $(stat -c%a "$priv" 2>/dev/null || stat -f%Lp "$priv")"

        if [ "$RESET_MODE" = "1" ]; then
            warn "===== --reset 模式: 删除现有密钥 + 重新生成 ====="
            warn "  ⚠ 所有现有 subscription 将失效, 用户需重新订阅"
            warn "  建议先通知用户 + 备份旧密钥!"
            run_cmd "备份旧密钥" cp "$priv" "${priv}.bak-$(date +%Y%m%d-%H%M%S)"
            run_cmd "备份旧公钥" cp "$pub" "${pub}.bak-$(date +%Y%m%d-%H%M%S)"
            run_cmd "删除私钥" rm -f "$priv"
            run_cmd "删除公钥" rm -f "$pub"
            return 1  # 1 = 需要新建
        fi
        return 0  # 0 = 已存在
    else
        log "未发现现有 VAPID 密钥 (路径: $VAPID_DIR)"
        return 1  # 1 = 需要新建
    fi
}

# ============================================================================
# 步骤 2: 创建持久化目录
# ============================================================================

create_directory() {
    log "========== 创建持久化目录 =========="

    # 主机侧
    run_cmd "主机侧 mkdir -p $VAPID_DIR" mkdir -p "$VAPID_DIR"

    # 容器侧 (如有 docker + 容器跑)
    if docker_available && container_running; then
        run_cmd "容器侧 mkdir -p $VAPID_DIR" \
            docker exec "$APP_CONTAINER" mkdir -p "$VAPID_DIR"
    fi

    # 权限校验
    if [ -d "$VAPID_DIR" ]; then
        local perm
        perm=$(stat -c%a "$VAPID_DIR" 2>/dev/null || stat -f%Lp "$VAPID_DIR")
        ok "$VAPID_DIR 已创建 (权限 $perm)"
    else
        if [ "$DRY_RUN" = "1" ]; then
            warn "dry-run 模式: $VAPID_DIR 还未真创建 (这是预期的)"
        else
            err "目录创建失败: $VAPID_DIR 不存在"
            return 1
        fi
    fi
}

# ============================================================================
# 步骤 3: docker volume mount 检查 (主机外, 给主指挥拍板)
# ============================================================================

check_volume_mount() {
    log "========== docker-compose.yml volume 检查 =========="
    log "(仅提示, 不自动改 docker-compose.yml)"
    log "  请确认 app service 含:"
    log "    volumes:"
    log "      - /data/push:/data/push:rw"
    log "  否则重启容器后 /data/push 内文件会丢 (容器内 fs 临时)"

    if docker_available && container_running; then
        # 探测容器内挂载点
        local mount_source
        mount_source=$(docker inspect --format='{{range .Mounts}}{{if eq .Destination "/data/push"}}{{.Source}}{{end}}{{end}}' "$APP_CONTAINER" 2>/dev/null)
        if [ -n "$mount_source" ]; then
            ok "容器 /data/push 已挂载 → 主机: $mount_source"
        else
            warn "容器 /data/push 未挂载 volume (重启会丢密钥)"
            warn "  → 请在 docker-compose.yml 加:"
            warn "       volumes:"
            warn "         - /data/push:/data/push:rw"
        fi
    fi
}

# ============================================================================
# 步骤 4: 触发 VAPID 生成 (启动 app 一次)
# ============================================================================

trigger_generation() {
    log "========== 触发 VAPID 生成 =========="

    if ! docker_available; then
        warn "无 docker → 无法启动 app 触发生成"
        warn "  请手动 docker compose restart app, 然后跑此脚本 --check"
        return 1
    fi

    if ! container_running; then
        err "容器 $APP_CONTAINER 未运行"
        err "  请先 docker compose up -d app, 再跑此脚本"
        return 1
    fi

    # 重启 app → lifespan 调 init_vapid_keys → 生成 + 持久化
    # **永远不要**自动重启, 主指挥拍板
    log "===== 待主指挥手动执行: docker compose restart app ====="
    log "  (本脚本不自动重启, 避免部署窗口期连动)"
    log "  重启后等 5s, 再跑: bash $0 --check"

    if [ "$DRY_RUN" = "0" ]; then
        warn "===== --apply 模式: 重启 app 一次 ====="
        warn "  提示: 这会触发短暂 downtime (lifespan restart ~3-5s)"
        run_cmd "docker compose restart app" docker compose restart app

        log "等 5s 让 lifespan init..."
        if [ "$DRY_RUN" = "0" ]; then
            sleep 5
        fi

        # 验证密钥已生成
        if docker_available && container_running; then
            run_cmd "验证容器侧 vapid_private.pem" \
                docker exec "$APP_CONTAINER" ls -la "$VAPID_DIR/"
        fi
    fi
}

# ============================================================================
# 步骤 5: 输出公钥 (主指挥对账用)
# ============================================================================

show_public_key() {
    log "========== 公钥输出 (对账用) =========="

    local pub="$VAPID_DIR/vapid_public.pem"

    if [ ! -f "$pub" ]; then
        warn "公钥文件不存在: $pub"
        warn "请先 docker compose restart app 触发生成"
        return 1
    fi

    if docker_available && container_running; then
        # 优先从容器读 (更准, 与运行时一致)
        log "VAPID 公钥 (PEM):"
        run_cmd "cat 容器内 vapid_public.pem" \
            docker exec "$APP_CONTAINER" cat "$pub"
    else
        log "VAPID 公钥 (PEM):"
        cat "$pub"
    fi

    log ""
    log "公钥 base64url 形式 (浏览器用, GET /api/v1/push/vapid-public-key):"
    if docker_available && container_running; then
        run_cmd "curl vapid-public-key" \
            docker exec "$APP_CONTAINER" curl -s http://localhost:8000/api/v1/push/vapid-public-key
    else
        log "  (无 docker, 请手动 curl https://<domain>/api/v1/push/vapid-public-key)"
    fi
}

# ============================================================================
# 主流程
# ============================================================================

main() {
    detect_platform
    preflight

    if [ "$CHECK_ONLY" = "1" ]; then
        log "===== --check 模式: 仅检查 ====="
        if check_existing_keys; then
            ok "VAPID 密钥已就绪"
            show_public_key
            exit 0
        else
            warn "VAPID 密钥未就绪"
            exit 1
        fi
    fi

    if check_existing_keys; then
        # 已存在, 显示信息后退出
        show_public_key
        ok "========== 完成 (无需新建) =========="
        exit 0
    fi

    # 未找到 → 创建
    create_directory
    check_volume_mount
    trigger_generation
    show_public_key

    log ""
    if [ "$ERRORS" -gt 0 ]; then
        err "========== 完成 (有 $ERRORS 个错误) =========="
        exit 1
    fi

    if [ "$DRY_RUN" = "1" ]; then
        warn "========== DRY-RUN 完成 (未真跑, 加 --apply 才执行) =========="
        exit 0
    fi

    ok "========== 完成 =========="
    log "后续:"
    log "  1. docker compose restart app (主指挥拍板, 已自动跑)"
    log "  2. 验证公钥不变: curl /api/v1/push/vapid-public-key"
    log "  3. 旧订阅者应仍能收到推送 (VAPID 私钥未变)"
    log "  4. 季度备份: cp -r $VAPID_DIR /backup/vapid-\$(date +%Y%m%d)"
}

main "$@"