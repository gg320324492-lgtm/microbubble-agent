#!/bin/sh
# scripts/check-dist-before-commit.sh
#
# 防止漏 commit web/dist/ 触发服务器 404（CLAUDE.md 2026-06-26 教训 f6a2bc3d）
#
# 触发场景：
#   1. 用户改了 web/src/*.vue (或 js/css)
#   2. 跑了 npm run build 产出新 hash 文件 (index-<8hex>.js 等)
#   3. git add 时漏了 `git add -f web/dist/`（因为 web/dist/ 在 .gitignore 第 50 行）
#   4. git commit 通过，但 git push 后服务器 git pull 只看到 src 改动 + 旧 dist 删除
#   5. 服务器 index.html 引用新 hash → 404 → SPA fallback 返 text/html → 整站白屏
#
# 历史教训（项目内第 4 次踩坑）：
#   - 2026-06-03: d619f33 漏 build 后 commit → 白屏
#   - 2026-06-10: a40e84c `git add -A` 静默跳过 .gitignore 内文件
#   - 2026-06-14: 同样模式再次踩坑
#   - 2026-06-26: f6a2bc3d (v70 P2) 漏 add 95 个新 dist → index-fc61064b.js 404
#
# 行为：
#   1. 检测 staged 是否有 web/src/ 改动（没改 → 跳过，不影响 docs/CI 提交）
#   2. 检测本地 web/dist/ 是否有 hash 命名的 build 产物 不在 HEAD 里
#   3. 两个条件都满足 → echo 警告 + 自动 `git add -f web/dist/` + 继续 commit
#
# 不是 hard block（避免影响 docs/CI 提交），但保证 build 后 dist 不会漏 commit
#
# 用法（pre-commit hook 自动调用，独立调用也行）：
#   sh scripts/check-dist-before-commit.sh
#
# 新成员 setup（CLAUDE.md 纪律）：
#   cp scripts/check-dist-before-commit.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit

set -e

# ---- 1. 检测 web/src/ 改动 ----
# 没改 src 就跳过（docs/CI/test commit 不应触发）
if [ -z "$(git diff --cached --name-only -- 'web/src/')" ]; then
    exit 0
fi

# ---- 1.5 v75: Token orphan 检测（防止 var(--xxx, ...) 引用未定义 token）----
# 集成到 pre-commit 避免 push 后 CI 才报错, dev 体验更早发现问题
if [ -x "scripts/check-token-orphans.sh" ]; then
    ORPHAN_OUTPUT=$(bash scripts/check-token-orphans.sh 2>&1) || true
    ORPHAN_COUNT=$(echo "$ORPHAN_OUTPUT" | grep -oE '[0-9]+ 真 orphan' | grep -oE '[0-9]+' | head -1)
    if [ -n "$ORPHAN_COUNT" ] && [ "$ORPHAN_COUNT" -gt 0 ]; then
        echo ""
        echo "❌ [pre-commit] 发现 $ORPHAN_COUNT 个 var(--token) orphan (CLAUDE.md v73 沉淀)"
        echo "   token 不在 variables.css / nutui-theme.scss / mobile-base.css 定义"
        echo "   修复选项:"
        echo "   1) 改对 token 名 (推荐, 项目已有 token)"
        echo "   2) 在 variables.css 补 token 定义"
        echo "   3) 加到 scripts/.token-orphan-allowlist (仅设计意图)"
        echo ""
        echo "📋 orphan 详情:"
        echo "$ORPHAN_OUTPUT" | grep "ORPHAN:" | sed 's/^/   /'
        echo ""
        echo "🛑 pre-commit 中止 (commit 失败), 修复后重试"
        exit 1
    fi
fi

# ---- 2. 检测本地 web/dist/ 是否有"新" hash 产物 ----
# HEAD 跟踪的 dist 文件
head_dist=$(git ls-tree -r --name-only HEAD -- 'web/dist/' 2>/dev/null || true)

# 本地有但 HEAD 没有的 dist 文件（排除 index.html/sw.js 这些总在 HEAD 的）
# 用 find 列本地 web/dist/assets/ 下 hash 命名的文件
local_new_dist=""
if [ -d "web/dist/assets" ]; then
    # index-<8hex>.js / index-<8hex>.css / <name>-<8hex>.{js,css}
    for f in web/dist/assets/*; do
        [ -f "$f" ] || continue
        bn=$(basename "$f")
        case "$bn" in
            index-[a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9].js) ;;
            index-[a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9].css) ;;
            *-[a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9].js) ;;
            *-[a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9].css) ;;
            *) continue ;;
        esac
        # 跳过 HEAD 已有的
        rel="web/dist/assets/$bn"
        case "$head_dist" in
            *"$rel"*) continue ;;
        esac
        local_new_dist="$local_new_dist $f"
    done
fi

if [ -z "$local_new_dist" ]; then
    exit 0
fi

# ---- 3. 警告 + 自动 add ----
count=$(echo $local_new_dist | wc -w)

echo ""
echo "⚠️  [pre-commit] 检测到 web/src/ 改动 + 本地有 $count 个未 tracked 的 web/dist/ build 产物"
echo "   防止漏 commit dist 触发服务器 404 (CLAUDE.md 2026-06-26 教训 f6a2bc3d)"
echo ""
echo "未 tracked dist 文件 (前 10):"
echo "$local_new_dist" | tr ' ' '\n' | grep -v '^$' | head -10 | sed 's/^/   /'
if [ "$count" -gt 10 ]; then
    echo "   ... (共 $count 个)"
fi
echo ""
echo "🔧 自动执行: git add -f web/dist/ (绕过 .gitignore 第 50 行 'web/dist/')"

# 自动 add
git add -f web/dist/

# ---- 4. 验证 + 报告 ----
new_staged=$(git diff --cached --name-only -- 'web/dist/' | wc -l)
echo ""
echo "✅ [pre-commit] 已 staged $new_staged 个 web/dist/ 文件，commit 继续"
echo ""

exit 0
