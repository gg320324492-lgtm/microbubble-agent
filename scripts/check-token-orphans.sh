#!/usr/bin/env bash
# scripts/check-token-orphans.sh
#
# 检查 var(--token, #fallback) 形式中 token 在全局 CSS 文件是否定义
# 沉淀自 v73 docs/color-tokens.md 13.6 节
# v74 升级: 加 .token-orphan-allowlist 白名单 (--i 等本地计算变量)
# v76.5 升级: 加 --ci-mode 输出 GitHub Actions annotation 格式 (::error file=...,line=...::)
#
# 退出码:
#   0 = 无 orphan (白名单项已自动 skip)
#   1 = 找到 orphan (打印详情)
#   2 = 配置错误
#
# 用法:
#   bash scripts/check-token-orphans.sh                # 人类可读输出
#   bash scripts/check-token-orphans.sh --ci-mode      # GitHub Actions annotation 格式
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# v76.5: --ci-mode flag 切换输出格式
CI_MODE=0
for arg in "$@"; do
  case "$arg" in
    --ci-mode) CI_MODE=1 ;;
    -h|--help)
      echo "用法: $0 [--ci-mode]"
      echo "  --ci-mode    输出 GitHub Actions annotation 格式 (::error file=...line=...)"
      exit 0
      ;;
  esac
done

# 全局 token 定义源
TOKEN_SOURCES=(
  "web/src/assets/variables.css"
  "web/src/assets/nutui-theme.scss"
  "web/src/assets/mobile-base.css"
)

# v74: 白名单文件 (一行一个 token, # 开头是注释)
ALLOWLIST_FILE="scripts/.token-orphan-allowlist"

# 加载白名单
declare -A ALLOWLIST
if [ -f "$ALLOWLIST_FILE" ]; then
  while IFS= read -r line; do
    # 跳过空行和注释
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    ALLOWLIST["$line"]=1
  done < "$ALLOWLIST_FILE"
fi

# v76.5: CI 模式静默, 不打印扫描进度
if [ "$CI_MODE" -eq 0 ]; then
  echo "🔍 扫描 var(--token, ...) 中的孤儿 token..."
  echo "   token 定义源:"
  for src in "${TOKEN_SOURCES[@]}"; do
    echo "   - $src"
  done
  echo "   白名单: $ALLOWLIST_FILE (${#ALLOWLIST[@]} 项)"
  echo ""
fi

ORPHAN_COUNT=0
WHITELISTED_COUNT=0

# v76.5: 用 grep -n 取文件:行号 (CI 模式用得上)
# 格式: web/src/path/Foo.vue:42:var(--color-x, ...
TOKENS=$(grep -rEn 'var\(--[a-z0-9_-]+,' web/src/ 2>/dev/null | sort -u)

# 关联数组收集 orphan 的 (file, line, token) (按 token 名聚合, 但保留每个 occurrence)
declare -a ORPHAN_LINES  # 形式: "file:line|token|full_var_call"

while IFS= read -r line; do
  [ -z "$line" ] && continue
  # 拆分 path:lineno:rest
  file=$(echo "$line" | cut -d: -f1)
  lineno=$(echo "$line" | cut -d: -f2)
  rest=$(echo "$line" | cut -d: -f3-)
  # 提取 token 名
  token=$(echo "$rest" | grep -oE 'var\(--[a-z0-9_-]+' | head -1 | sed 's/var(//')

  # 白名单优先
  if [ "${ALLOWLIST[$token]:-}" = "1" ]; then
    WHITELISTED_COUNT=$((WHITELISTED_COUNT + 1))
    continue
  fi

  found=0
  for src in "${TOKEN_SOURCES[@]}"; do
    if grep -qE "(^|[[:space:]])${token}([[:space:]]|:|=)" "$src" 2>/dev/null; then
      found=1
      break
    fi
  done
  if [ "$found" -eq 0 ]; then
    if [ "$CI_MODE" -eq 1 ]; then
      # v76.5: GitHub Actions annotation 格式
      echo "::error file=$file,line=$lineno::var($token) is not defined in variables.css / nutui-theme.scss / mobile-base.css"
    else
      # 默认人类可读格式 (保持 v73 兼容)
      echo "ORPHAN: var($token, ...) at $file:$lineno"
    fi
    ORPHAN_COUNT=$((ORPHAN_COUNT + 1))
    ORPHAN_LINES+=("$file:$lineno|$token")
  fi
done <<< "$TOKENS"

# v76.5: 输出汇总
if [ "$CI_MODE" -eq 0 ]; then
  echo ""
  echo "📊 扫描结果: $ORPHAN_COUNT 真 orphan, $WHITELISTED_COUNT 白名单跳过"
else
  # CI 模式只打印一行汇总 (GitHub Actions log summary)
  echo "::notice::Token orphan check: $ORPHAN_COUNT orphans, $WHITELISTED_COUNT whitelisted"
fi

if [ "$ORPHAN_COUNT" -gt 0 ]; then
  exit 1
fi
exit 0