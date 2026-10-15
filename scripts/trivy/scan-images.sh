#!/usr/bin/env bash
# W86-C-1: Trivy 本地一次性扫描 (Dockerfile 配置 + 本地已存在镜像)
#
# 用法:
#   bash scripts/trivy/scan-images.sh
#
# 输出: logs/trivy-report.txt + stdout
# 退出码: 任一 HIGH/CRITICAL 命中 > 0 → 1; 全清 → 0
#
# 前置: trivy 已安装 (见 scripts/install-trivy.md)。未安装则 exit 2 (不算扫描失败)。

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

REPORT_DIR="logs"
REPORT="${REPORT_DIR}/trivy-report.txt"
mkdir -p "$REPORT_DIR"

if ! command -v trivy >/dev/null 2>&1; then
    echo "[SKIP] trivy 未安装 — 见 scripts/install-trivy.md" >&2
    exit 2
fi

: > "$REPORT"

log() {
    echo "$*" | tee -a "$REPORT"
}

# 2026-10-15: trivy 每次扫描会在系统 temp 下建 trivy-<随机数>/ 工作目录
# (解压 layer / 解包镜像), 单次可留数 GB, 且**从不自动清理**。
# 实测本机 4 次扫描残留 18.5 G (Temp/trivy-* × 4), C 盘因此只剩 27 G。
# ⚠️ 与 GitHub CI 的 image-scan **无关** —— 那是 runner 上的容器化 action,
# 用 runner 自己的 temp; 这些是**本机 winget 装的 trivy 0.72.0** 留下的
# (2026-07-30 安装; scripts/install-trivy.md 里「本机未安装」那句已过期)。
cleanup_trivy_tmp() {
    local tmp_base n
    tmp_base="$(cygpath -u "${TEMP:-${TMP:-/tmp}}" 2>/dev/null || echo "${TEMP:-${TMP:-/tmp}}")"
    n=0
    for d in "$tmp_base"/trivy-*; do
        [ -d "$d" ] || continue
        # 双保险: glob 已限定 trivy-* 前缀, 这里再要求后缀是纯数字
        case "$(basename "$d")" in
            trivy-[0-9]*) rm -rf "$d" 2>/dev/null && n=$((n+1)) ;;
        esac
    done
    [ "$n" -gt 0 ] && log "已清理 $n 个 trivy 临时目录"
    return 0
}
trap cleanup_trivy_tmp EXIT

log "=== Trivy scan report — $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
log "trivy: $(trivy --version 2>&1 | head -1)"
log ""

FAIL=0

# ---- 1. Dockerfile 配置扫描 (8 个) ----
DOCKERFILES=(
    "Dockerfile"
    "Dockerfile.db"
    "Dockerfile.funasr"
    "Dockerfile.mcp"
    # 2026-10-13 起不再扫 voice-pipeline: 休眠镜像(compose 无服务/本机无镜像),
    # 其 CMD 自述"经主 app 容器挂载运行"即设计上不独立起, 且体积 15.8GB。
    # 主指挥裁定停止扫描; Dockerfile 本身保留不删。
    "Dockerfile.whisper"
    "web/Dockerfile"
    # 2026-10-13 起不再扫 commercial: 休眠镜像(compose 无服务/本机无镜像),
    # runtime 段无 ffmpeg+libreoffice 却 COPY 了整个 app/(19 文件依赖它),
    # 一旦部署即静默缺件。主指挥裁定停止扫描; Dockerfile 本身保留不删。
)

log "--- [1/2] Dockerfile config scan (HIGH,CRITICAL) ---"
for df in "${DOCKERFILES[@]}"; do
    if [ ! -f "$df" ]; then
        log "[WARN] missing: $df"
        continue
    fi
    log ""
    log ">>> $df"
    if trivy config --severity HIGH,CRITICAL --exit-code 1 "$df" 2>&1 | tee -a "$REPORT"; then
        log "    [OK] $df — 0 HIGH/CRITICAL"
    else
        log "    [FAIL] $df — HIGH/CRITICAL 命中"
        FAIL=1
    fi
done

# ---- 2. 本地已存在镜像扫描 ----
IMAGES=(
    "microbubble-agent-app:latest"
    "microbubble-agent-db:latest"
    "microbubble-agent-sensevoice:latest"
)

log ""
log "--- [2/2] local image scan (HIGH,CRITICAL) ---"
for img in "${IMAGES[@]}"; do
    if ! docker image inspect "$img" >/dev/null 2>&1; then
        log "[SKIP] 本地无此镜像: $img"
        continue
    fi
    log ""
    log ">>> $img"
    if trivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 "$img" 2>&1 | tee -a "$REPORT"; then
        log "    [OK] $img — 0 HIGH/CRITICAL (unfixed 已忽略)"
    else
        log "    [FAIL] $img — HIGH/CRITICAL 命中"
        FAIL=1
    fi
done

log ""
if [ "$FAIL" -eq 0 ]; then
    log "=== RESULT: PASS (0 HIGH/CRITICAL) ==="
else
    log "=== RESULT: FAIL (HIGH/CRITICAL 命中, 详见上文) ==="
fi
log "报告: $REPORT"

exit "$FAIL"
