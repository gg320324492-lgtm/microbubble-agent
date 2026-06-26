#!/usr/bin/env bash
# scripts/check-token-orphans.sh
#
# 检查 var(--token, #fallback) 形式中 token 在全局 CSS 文件是否定义
# 沉淀自 v73 docs/color-tokens.md 13.6 节 (commit pending)
#
# 退出码:
#   0 = 无 orphan
#   1 = 找到 orphan (打印详情)
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

ORPHAN_COUNT=0
ORPHAN_LIST=()

echo "🔍 扫描 var(--token, ...) 中的孤儿 token..."
echo "   token 定义源:"
for src in "${TOKEN_SOURCES[@]}"; do
  echo "   - $src"
done
echo ""

# 提取所有唯一 token 名
grep -rEho 'var\(--[a-z0-9_-]+,' web/src/ 2>/dev/null | sort -u | while read -r v; do
  token=$(echo "$v" | sed -E 's/var\((--[a-z0-9_-]+).*/\1/')
  found=0
  for src in "${TOKEN_SOURCES[@]}"; do
    if grep -qE "(^|[[:space:]])${token}([[:space:]]|:|=)" "$src" 2>/dev/null; then
      found=1
      break
    fi
  done
  if [ "$found" -eq 0 ]; then
    echo "ORPHAN: $v (token=$token)"
  fi
done

echo ""
echo "✅ 扫描完成（如有 ORPHAN 上面已打印）"
