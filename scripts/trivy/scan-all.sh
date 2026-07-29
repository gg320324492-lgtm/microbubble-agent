#!/usr/bin/env bash
# W86-C-1: Trivy 全量扫描 (Dockerfile + 所有本地 microbubble 镜像 + sarif 输出)
#
# 用法:
#   bash scripts/trivy/scan-all.sh
#
# 输出:
#   logs/trivy-report-all.txt   — 人读 table
#   logs/trivy-sarif/*.sarif    — 机读 sarif (可上传 GitHub code scanning)
#
# 退出码: 任一 HIGH/CRITICAL 命中 → 1; 全清 → 0; trivy 未安装 → 2
#
# deploy-auto.sh gate 集成 (留给主指挥, 本脚本不改 deploy-auto.sh):
#   bash scripts/trivy/scan-all.sh || { log "ERROR: trivy gate 未通过"; exit 1; }

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

REPORT="logs/trivy-report-all.txt"
SARIF_DIR="logs/trivy-sarif"
mkdir -p "logs" "$SARIF_DIR"

if ! command -v trivy >/dev/null 2>&1; then
    echo "[SKIP] trivy 未安装 — 见 scripts/install-trivy.md" >&2
    exit 2
fi

: > "$REPORT"
log() { echo "$*" | tee -a "$REPORT"; }

log "=== Trivy full scan — $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
log "trivy: $(trivy --version 2>&1 | head -1)"

FAIL=0

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

# ---- 1. Dockerfile 配置扫描 (table + sarif) ----
log ""
log "--- [1/3] Dockerfile config scan ---"
for df in "${DOCKERFILES[@]}"; do
    [ -f "$df" ] || { log "[WARN] missing: $df"; continue; }
    safe="$(echo "$df" | tr '/.' '__')"
    log ""
    log ">>> $df"
    trivy config --severity HIGH,CRITICAL --format sarif \
        --output "${SARIF_DIR}/config-${safe}.sarif" "$df" >/dev/null 2>&1 || true
    if trivy config --severity HIGH,CRITICAL --exit-code 1 "$df" 2>&1 | tee -a "$REPORT"; then
        log "    [OK] $df"
    else
        log "    [FAIL] $df"
        FAIL=1
    fi
done

# ---- 2. 文件系统扫描 (依赖清单 CVE: requirements.txt / package.json) ----
log ""
log "--- [2/3] filesystem dependency scan ---"
if trivy fs --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 \
        --scanners vuln,secret --skip-dirs node_modules --skip-dirs web/dist \
        . 2>&1 | tee -a "$REPORT"; then
    log "    [OK] filesystem — 0 HIGH/CRITICAL"
else
    log "    [FAIL] filesystem — HIGH/CRITICAL 命中"
    FAIL=1
fi

# ---- 3. 所有本地 microbubble* 镜像扫描 ----
log ""
log "--- [3/3] local image scan (microbubble* + 钉死的 base image) ---"
mapfile -t IMAGES < <(docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null \
    | grep -E '^(microbubble|nginx|redis|postgres|neo4j|python|node)' | grep -v '<none>' | sort -u)

if [ "${#IMAGES[@]}" -eq 0 ]; then
    log "[SKIP] 本地无可扫镜像"
fi

for img in "${IMAGES[@]}"; do
    safe="$(echo "$img" | tr '/:.' '___')"
    log ""
    log ">>> $img"
    trivy image --severity HIGH,CRITICAL --ignore-unfixed --format sarif \
        --output "${SARIF_DIR}/image-${safe}.sarif" "$img" >/dev/null 2>&1 || true
    if trivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 "$img" 2>&1 | tee -a "$REPORT"; then
        log "    [OK] $img"
    else
        log "    [FAIL] $img"
        FAIL=1
    fi
done

log ""
if [ "$FAIL" -eq 0 ]; then
    log "=== RESULT: PASS (0 HIGH/CRITICAL) ==="
else
    log "=== RESULT: FAIL (HIGH/CRITICAL 命中) ==="
fi
log "报告: $REPORT"
log "sarif: $SARIF_DIR/"

exit "$FAIL"
