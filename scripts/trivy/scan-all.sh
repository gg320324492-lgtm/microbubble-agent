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
        # 双保险: 必须名字精确匹配 trivy-* 前缀(已在 glob 里), 且带数字后缀
        case "$(basename "$d")" in
            trivy-[0-9]*) rm -rf "$d" 2>/dev/null && n=$((n+1)) ;;
        esac
    done
    [ "$n" -gt 0 ] && log "已清理 $n 个 trivy 临时目录 ($tmp_base/trivy-*)"
    return 0
}
trap cleanup_trivy_tmp EXIT

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
