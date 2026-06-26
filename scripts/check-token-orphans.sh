#!/usr/bin/env bash
# scripts/check-token-orphans.sh
#
# 检查 var(--token, #fallback) 形式中 token 在全局 CSS 文件是否定义
# 沉淀自 v73 docs/color-tokens.md 13.6 节
# v74 升级: 加 .token-orphan-allowlist 白名单 (--i 等本地计算变量)
#
# 退出码:
#   0 = 无 orphan (白名单项已自动 skip)
#   1 = 找到 orphan (打印详情)
#   2 = 配置错误
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

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

echo "🔍 扫描 var(--token, ...) 中的孤儿 token..."
echo "   token 定义源:"
for src in "${TOKEN_SOURCES[@]}"; do
  echo "   - $src"
done
echo "   白名单: $ALLOWLIST_FILE (${#ALLOWLIST[@]} 项)"
echo ""

ORPHAN_COUNT=0
WHITELISTED_COUNT=0

# 提取所有唯一 token 名
TOKENS=$(grep -rEho 'var\(--[a-z0-9_-]+,' web/src/ 2>/dev/null | sort -u)
for v in $TOKENS; do
  token=$(echo "$v" | sed -E 's/var\((--[a-z0-9_-]+).*/\1/')

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
    echo "ORPHAN: $v (token=$token)"
    ORPHAN_COUNT=$((ORPHAN_COUNT + 1))
  fi
done

echo ""
echo "📊 扫描结果: $ORPHAN_COUNT 真 orphan, $WHITELISTED_COUNT 白名单跳过"

if [ "$ORPHAN_COUNT" -gt 0 ]; then
  exit 1
fi
exit 0
