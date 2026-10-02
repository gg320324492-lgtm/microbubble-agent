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
#
# 2026-10-03: 补 web/src/assets/mobile-glass.css。S3.8 拆分把 stylelint 清零后本门禁
# 第一次真正跑到（此前每次都被前一步 lint:css 的 exit 1 短路），随即暴露 **130 条
# ref 行 / 43 个唯一 token**。其中 76 处引用、22 个唯一的 --mg-* 液态玻璃 token
# **本来就定义在 mobile-glass.css 的 :root 里**（web/src/main.js:64 全局 import），
# 只是本脚本的源清单漏了这个文件 —— 是脚本配置漏扫，不是代码债。补上后这 76 条归零。
#
# 纪律: 往本数组增删源时, 下方 CI_MODE 的报错文案必须同步 —— 该文案曾硬编码三个
# 文件名 (见 TOKEN_SOURCES_LABEL 由数组派生, 不要再手写文件名)。
TOKEN_SOURCES=(
  "web/src/assets/variables.css"
  "web/src/assets/nutui-theme.scss"
  "web/src/assets/mobile-base.css"
  "web/src/assets/mobile-glass.css"
)

# 报错文案用的可读源名 (从 TOKEN_SOURCES 派生, 杜绝文案与实际清单脱节)
TOKEN_SOURCES_LABEL=$(printf '%s / ' "${TOKEN_SOURCES[@]}" | sed 's#web/src/assets/##g; s# / $##')

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
# v76.s3: 排除 web/src/data/ 数据文件 (JSON 里的 var() 字符串是描述性文本, 非真实 CSS 代码)
#
# 2026-10-03: 改为**每行每个** token 都展开成独立待检项。此前每行只取 head -1,
# 于是同一行里第 2 个及以后的 var() 完全逃过门禁 —— 实测漏网:
#   DriveDetailRail.vue:1661 "var(--font-mono, monospace); ... var(--color-text-3, #8B968F)"
# --color-text-3 因为跟在 --font-mono 后面而始终不被检查 (它有 fallback, 但从未定义)。
# 修复: 用 awk 把一行里的 N 个 var(--x, 展开成 N 条 "file:line:--token" 记录。
TOKENS=$(
  grep -rEn 'var\(--[a-z0-9_-]+,' web/src/ --exclude-dir=data 2>/dev/null \
  | awk '{
      # 头部严格是 "path:lineno:" —— path 是 Windows 相对路径, 不含冒号;
      # 用 match() 定位, 避免把 CSS 值里的冒号 (如 "background:") 当分隔符。
      head = index($0, ":");
      rest = substr($0, head + 1);
      head2 = index(rest, ":");
      file = substr($0, 1, head - 1);
      lineno = substr(rest, 1, head2 - 1);
      body = substr(rest, head2 + 1);
      n = split(body, a, "var[(][-][-]");
      for (i = 2; i <= n; i++) {
        t = a[i];
        # ⚠️ 两条纪律 (都踩过):
        #  1. 必须保留原 grep 的"逗号守卫": 本门禁只审 var(--token, <fallback>) 形式。
        #     裸 var(--token) (无 fallback, 如 glass.css:27 var(--glass-opacity-light))
        #     是**合法用法**, 不该算 orphan —— 少了守卫会多出 6 个误报
        #     (glass-opacity-dark/light, mg-primary-soft, raw-0e766e/edf1ef/fff)。
        #  2. 取名必须用 match() 的 RSTART/RLENGTH 截取, **不能**靠 sub 删逗号 ——
        #     split 后的片段形如 "vh, 100vh);", 尾部没有逗号, sub(/,$/) 什么也删不掉,
        #     会把整个 fallback 一起当 token 名输出, 白名单匹配随之全部失效。
        if (match(t, /^[a-z0-9_-]+,/)) {
          printf "%s:%s:--%s\n", file, lineno, substr(t, RSTART, RLENGTH - 1);
        }
      }
    }' | sort -u
)

# 关联数组收集 orphan 的 (file, line, token) (按 token 名聚合, 但保留每个 occurrence)
declare -a ORPHAN_LINES  # 形式: "file:line|token|full_var_call"

while IFS= read -r line; do
  [ -z "$line" ] && continue
  # 2026-10-03: 格式已由 awk 预展开为 "path:lineno:--token", 无需再从源码行提 token
  file=$(echo "$line" | cut -d: -f1)
  lineno=$(echo "$line" | cut -d: -f2)
  token=$(echo "$line" | cut -d: -f3-)

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
      echo "::error file=$file,line=$lineno::var($token) is not defined in $TOKEN_SOURCES_LABEL"
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