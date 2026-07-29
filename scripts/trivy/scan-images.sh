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
    "Dockerfile.voice-pipeline"
    "Dockerfile.whisper"
    "web/Dockerfile"
    "docker/Dockerfile.commercial"
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
