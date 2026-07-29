#!/usr/bin/env bash
# scripts/gitleaks/scan-history.sh
#
# 本地全仓库扫描 (W86 第 1 批 A-1)
# 沉淀日期: 2026-07-29
#
# 用法:
#   bash scripts/gitleaks/scan-history.sh                    # 扫全仓库 + 写报告
#   bash scripts/gitleaks/scan-history.sh --since=v1.0       # 扫 v1.0 之后的 commit
#   bash scripts/gitleaks/scan-history.sh --no-redact        # 不脱敏
#
# 退出码:
#   0 = 无泄漏 (干净)
#   1 = 找到凭据
#   2 = gitleaks 未安装 / 配置错误
#
# 依赖:
#   - gitleaks >= 8.x (从 https://github.com/gitleaks/gitleaks/releases 安装)
#   - bash 4.x+ (macOS 自带 3.x 也兼容)
#
# 与 .github/workflows/secret-scan.yml 共享 .gitleaks.toml, 本地/CI 规则一致.

set -euo pipefail

# ---- 路径 ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CONFIG_FILE="${PROJECT_ROOT}/.gitleaks.toml"
LOG_DIR="${PROJECT_ROOT}/logs"
REPORT_JSON="${LOG_DIR}/gitleaks-report.json"
REPORT_SARIF="${LOG_DIR}/gitleaks-report.sarif"

# ---- 颜色 ----
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; BLUE=''; NC=''
fi

# ---- 前置检查 ----
log_info() { printf "${BLUE}[INFO]${NC} %s\n" "$*"; }
log_warn() { printf "${YELLOW}[WARN]${NC} %s\n" "$*"; }
log_err()  { printf "${RED}[ERR ]${NC} %s\n" "$*" >&2; }
log_ok()   { printf "${GREEN}[OK  ]${NC} %s\n" "$*"; }

# 检查 gitleaks 是否安装
if ! command -v gitleaks >/dev/null 2>&1; then
    log_err "gitleaks 未安装"
    echo ""
    echo "装机步骤见 scripts/install-gitleaks.md, 简版:"
    echo "  macOS:  brew install gitleaks"
    echo "  Linux:  wget <github release tarball> && sudo mv gitleaks /usr/local/bin/"
    echo "  Win:    winget install gitleaks"
    echo ""
    exit 2
fi

# 检查 gitleaks 版本 (要求 >= 8.0)
GITLEAKS_VERSION=$(gitleaks version 2>/dev/null | awk '{print $2}' | sed 's/^v//')
log_info "gitleaks 版本: ${GITLEAKS_VERSION}"

# 检查配置文件
if [ ! -f "${CONFIG_FILE}" ]; then
    log_err "配置文件不存在: ${CONFIG_FILE}"
    echo "请确认 .gitleaks.toml 已在项目根"
    exit 2
fi

# 创建 logs 目录 (兜底, .gitignore 已忽略)
mkdir -p "${LOG_DIR}"

# ---- 解析额外参数 ----
EXTRA_ARGS=("$@")

# ---- 跑扫描 ----
log_info "开始扫描: ${PROJECT_ROOT}"
log_info "配置文件: ${CONFIG_FILE}"
log_info "JSON 报告: ${REPORT_JSON}"
log_info "SARIF 报告: ${REPORT_SARIF}"
log_info "额外参数: ${EXTRA_ARGS[*]:-无}"
echo ""

# 主扫描命令
# --source .                  扫当前目录
# --config                    用项目 .gitleaks.toml
# --report-path               JSON 报告
# --report-format json        输出 JSON
# --redact                   默认脱敏 (8.18+)
# --no-banner                不要 banner
# --exit-code 1              找到泄漏退出 1 (默认行为, 显式)
set +e
gitleaks detect \
    --source "${PROJECT_ROOT}" \
    --config "${CONFIG_FILE}" \
    --report-path "${REPORT_JSON}" \
    --report-format json \
    --no-banner \
    --exit-code 1 \
    "${EXTRA_ARGS[@]}"
GITLEAKS_EXIT=$?
set -e

# ---- 结果摘要 ----
echo ""
if [ "${GITLEAKS_EXIT}" -eq 0 ]; then
    log_ok "扫描完成: 无凭据泄漏"
    log_ok "报告: ${REPORT_JSON} (空文件)"
    exit 0
elif [ "${GITLEAKS_EXIT}" -eq 1 ]; then
    log_err "扫描完成: 检测到凭据泄漏!"
    if [ -f "${REPORT_JSON}" ]; then
        TOTAL=$(jq 'length' "${REPORT_JSON}" 2>/dev/null || echo "?")
        log_err "总命中数: ${TOTAL}"
        log_err "命中文件 (前 10):"
        jq -r '.[].File | select(. != null) | "  - \(.)"' "${REPORT_JSON}" 2>/dev/null | sort -u | head -10 || true
        log_err "命中规则 (top 3):"
        jq -r '.[].RuleID' "${REPORT_JSON}" 2>/dev/null | sort | uniq -c | sort -rn | head -3 | awk '{print "  - " $2 ": " $1 " 次"}' || true
        echo ""
        log_warn "修复选项:"
        echo "  1) 凭据立即轮换 (不论入不入库都需轮换)"
        echo "  2) 真凭据替换为占位符 (<REDACTED>) 或环境变量"
        echo "  3) 已知历史泄漏加入 .gitleaks.toml allowlists (凭据已轮换, 等主指挥 git filter-repo)"
        echo "  4) W86 主指挥决定是否 git filter-repo 重写历史"
        echo ""
        log_warn "详细报告: ${REPORT_JSON}"
    fi
    exit 1
else
    log_err "扫描失败: 退出码 ${GITLEAKS_EXIT}"
    log_err "可能是 .gitleaks.toml 语法错误或 gitleaks 版本不兼容"
    exit "${GITLEAKS_EXIT}"
fi