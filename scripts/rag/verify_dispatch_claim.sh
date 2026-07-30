#!/usr/bin/env bash
# verify_dispatch_claim.sh
# ----------------------------------------------------------------------------
# Purpose:
#   据实上报铁律 4 路搜证 (Truthful Reporting Iron Rule - 4-Track Forensics)
#   验证派工 brief 中 commit / PR / feature-keyword 真实落地的工具脚本.
#
# 4 路搜证原理 (4-Track Forensics):
#   路径 1 (origin log):   git log --all --oneline | grep <pattern>
#                          → 验证 commit 真在 origin log 中出现 (≥1)
#   路径 2 (git grep):      git grep <feature-keyword>
#                          → 验证 feature-keyword 真在工作树/索引中落地 (≥1 行)
#   路径 3 (reflog):        git reflog --all | grep <pattern>
#                          → 验证 commit 走过 reflog (≥1)
#   路径 4 (commit hash):   git cat-file -t <hash>
#                          → 验证 commit object 真存在 (object type = "commit")
#
# 铁律引用 (Iron Rule References):
#   - W82 B-2 拦截 (类 20.13 实战 16): 派工前提错配, 调研报告与实际 import 不符
#   - W84 据实上报 3 实例沉淀回写: A-2 + C-1 + C-2 派工 brief 与实测不符
#   - W85 D-2 锚点范式 314→320 据实上报: 派工前提错配 18 实例沉淀
#   - W68 §1.1 plans 审计纪律: Status 段必须描述真实 commit, 不能借用同 wave
#   - W68 §1.2 plans 审计纪律: 必须读 plan 全文 + git show + grep -r 验证
#
# Usage:
#   bash scripts/rag/verify_dispatch_claim.sh <commit-hash-or-pattern>
#   bash scripts/rag/verify_dispatch_claim.sh "087_add_knowledge_original_parent_id"
#   bash scripts/rag/verify_dispatch_claim.sh "W88 +0"
#   bash scripts/rag/verify_dispatch_claim.sh "embedding_truncation_policy"
#
# Exit codes:
#   0 = 4 路全 PASS (commit/feature 真存在)
#   1 = 任一 FAIL (commit/feature 不存在 / 不落地)
#
# 绝不动其他代码. 只读 git 对象库, 不修改任何工作树状态.
# ----------------------------------------------------------------------------

set -euo pipefail

# ---- 参数校验 ---------------------------------------------------------------
if [[ $# -lt 1 ]]; then
  echo "用法: bash $0 <commit-hash-or-pattern>" >&2
  echo "  示例: bash $0 \"087_add_knowledge_original_parent_id\"" >&2
  echo "  示例: bash $0 \"embedding_truncation_policy\"" >&2
  exit 2
fi

PATTERN="$1"

# ---- 自动定位 git 仓库根 ----------------------------------------------------
# 必须在 git 仓库内运行. 用 git -C 找根, 不依赖 cwd.
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${REPO_ROOT}" ]]; then
  echo "ERROR: 当前目录不在 git 仓库内 (git rev-parse --show-toplevel 失败)" >&2
  exit 2
fi

# ---- 状态初始化 ------------------------------------------------------------
PASS_COUNT=0
FAIL_COUNT=0
ALL_RESULTS=()

# 通用 logger (时间戳 + 路径标识)
log_path() {
  local path_id="$1"
  local result="$2"
  local detail="$3"
  printf "%-30s %-6s [%s]\n" "${path_id}:" "${result}" "${detail}"
}

# ---- 路径 1: origin log ----------------------------------------------------
# 用 git log --all (覆盖所有 refs: local + remote tracking + tag)
# 模式命中数 ≥ 1 视为 PASS
verify_path1_origin_log() {
  local pattern="$1"
  local count=0
  local output=""

  # 4 路独立 try-catch: set +e 临时禁用 -e 防止 grep 0 命中退出码 1 误杀
  set +e
  output="$(git -C "${REPO_ROOT}" log --all --oneline 2>/dev/null | grep -F -- "${pattern}" || true)"
  set -e
  # 鲁棒计数: 过滤空行后取行数 (避免 Windows wc -l 输出 "0\n0" 双行问题)
  count=$(printf '%s\n' "${output}" | sed '/^$/d' | wc -l | tr -d '[:space:]' 2>/dev/null)
  if [[ ! "${count}" =~ ^[0-9]+$ ]]; then
    count=0
  fi

  if [[ "${count}" -ge 1 ]]; then
    log_path "路径 1 (origin log)" "PASS" "${count} commits"
    PASS_COUNT=$((PASS_COUNT + 1))
    return 0
  else
    log_path "路径 1 (origin log)" "FAIL" "0 commits"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    return 1
  fi
}

# ---- 路径 2: git grep ------------------------------------------------------
# 在工作树 + 索引中搜索 feature-keyword
# 命中行数 ≥ 1 视为 PASS
verify_path2_git_grep() {
  local pattern="$1"
  local count=0

  set +e
  # --untracked: 含未跟踪文件; -I: 跳过二进制; -n: 行号
  count=$(git -C "${REPO_ROOT}" grep --untracked -I -n -F -- "${pattern}" 2>/dev/null | wc -l | tr -d '[:space:]')
  set -e
  # wc -l 在 0 行时输出 "0", 兜底空值 + 非数字容错
  if [[ ! "${count}" =~ ^[0-9]+$ ]]; then
    count=0
  fi

  if [[ "${count}" -ge 1 ]]; then
    log_path "路径 2 (git grep)" "PASS" "${count} hits"
    PASS_COUNT=$((PASS_COUNT + 1))
    return 0
  else
    log_path "路径 2 (git grep)" "FAIL" "0 hits"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    return 1
  fi
}

# ---- 路径 3: reflog --------------------------------------------------------
# 验证 commit 走过 reflog (本地/检出/合并/重置都会留痕)
# reflog 命中数 ≥ 1 视为 PASS
verify_path3_reflog() {
  local pattern="$1"
  local count=0

  set +e
  # --all 含所有 reflog (refs/stash, refs/notes 等)
  count=$(git -C "${REPO_ROOT}" reflog --all 2>/dev/null | grep -F -- "${pattern}" | wc -l | tr -d '[:space:]')
  set -e
  if [[ ! "${count}" =~ ^[0-9]+$ ]]; then
    count=0
  fi

  if [[ "${count}" -ge 1 ]]; then
    log_path "路径 3 (reflog)" "PASS" "${count} reflogs"
    PASS_COUNT=$((PASS_COUNT + 1))
    return 0
  else
    log_path "路径 3 (reflog)" "FAIL" "0 reflogs"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    return 1
  fi
}

# ---- 路径 4: commit hash 真实性 --------------------------------------------
# 用 git cat-file -t 验证 commit object 真存在
# 仅在 PATTERN 看起来像 commit hash (7-40 位 hex) 时跑, 否则 SKIP 标 FAIL
# 其他模式 (例如 "W88 +0" / feature-keyword) 不能用 cat-file, 必须明确标 FAIL
verify_path4_commit_hash() {
  local pattern="$1"
  local object_type=""
  local skip_reason=""

  # commit hash 判定: 7-40 位 hex
  if [[ ! "${pattern}" =~ ^[0-9a-fA-F]{7,40}$ ]]; then
    log_path "路径 4 (commit hash)" "FAIL" "pattern 不是 commit hash 格式 (7-40 hex), 跳过验证"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    return 1
  fi

  set +e
  object_type="$(git -C "${REPO_ROOT}" cat-file -t "${pattern}" 2>/dev/null || true)"
  set -e

  if [[ "${object_type}" == "commit" ]]; then
    log_path "路径 4 (commit hash)" "PASS" "object type = ${object_type}"
    PASS_COUNT=$((PASS_COUNT + 1))
    return 0
  else
    log_path "路径 4 (commit hash)" "FAIL" "object type = '${object_type:-<not found>}'"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    return 1
  fi
}

# ---- 主流程 ----------------------------------------------------------------
echo "=================================================================="
echo "据实上报铁律 4 路搜证 (Truthful Reporting - 4-Track Forensics)"
echo "=================================================================="
echo "Pattern: ${PATTERN}"
echo "Repo:    ${REPO_ROOT}"
echo "------------------------------------------------------------------"

# 4 路独立搜证 (各路独立 try-catch, 一路失败不阻塞其他路)
verify_path1_origin_log "${PATTERN}" || true
verify_path2_git_grep "${PATTERN}" || true
verify_path3_reflog "${PATTERN}" || true
verify_path4_commit_hash "${PATTERN}" || true

echo "------------------------------------------------------------------"
echo "汇总: PASS=${PASS_COUNT} / FAIL=${FAIL_COUNT} / TOTAL=4"

# ---- 退出码 ----------------------------------------------------------------
if [[ "${FAIL_COUNT}" -eq 0 ]]; then
  echo "RESULT: 4 路全 PASS — commit/feature 真实落地, 派工 brief 据实."
  exit 0
else
  echo "RESULT: ${FAIL_COUNT} 路 FAIL — commit/feature 不可验证, 派工 brief 与实际不符."
  exit 1
fi
