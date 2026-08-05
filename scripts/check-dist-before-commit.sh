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
#
# W100 +75c 优化（类 20 永久铁律 - Windows 10min timeout 误判）:
#   - 加 `set +e` 避免 set -e 短路 + 内部 step 短路整个 hook
#   - 跳过已删 dist 文件 (git status --porcelain 过滤 + test -e 检查)
#   - `timeout 30` per-step 防御单步卡死
#   - 末尾加总耗时, 超过 30s 提示"harness timeout 风险"
#   - fail-loud 但不 exit 1 (避免 hook 误判 abort, 输出显眼警告但 commit 继续)

# W100 +75c: set +e (不要 set -e, 否则内部 grep 无匹配返回 1 会短路整个 hook)
set +e

# 总耗时统计 (W100 +75c 新增)
START_TIME=$(date +%s)

# ---- 1. 检测 web/src/ 改动 ----
# 没改 src 就跳过（docs/CI/test commit 不应触发）
if [ -z "$(git diff --cached --name-only -- 'web/src/')" ]; then
    ELAPSED=$(($(date +%s) - START_TIME))
    exit 0
fi

# ---- 1.5 v75: Token orphan 检测（防止 var(--xxx, ...) 引用未定义 token）----
# 集成到 pre-commit 避免 push 后 CI 才报错, dev 体验更早发现问题
if [ -x "scripts/check-token-orphans.sh" ]; then
    # W100 +75c: 加 timeout 30 防单步卡死 (Windows 10min timeout 误判场景)
    ORPHAN_OUTPUT=$(timeout 30 bash scripts/check-token-orphans.sh 2>&1) || true
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

# W100 +75c: 跳过已删 dist 文件 (git status --porcelain 过滤, 避免对 deleted 文件做无谓检查)
# 用 git status --porcelain web/dist/ 拿到 staged 状态, 排除 D (deleted) 行
deleted_dist=$(git status --porcelain -- 'web/dist/' | awk '/^.D / {print $2}' | tr '\n' ' ')

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
        # P3-1 fix (2026-07-08): 原 case "$head_dist" in *"$rel"* 用 unquoted word glob,
        # 只能匹配第一个 word (head_dist 第一行). HEAD 含多行 dist 文件时,
        # 从第二个开始永远不匹配 → 重复 add. 改用 echo | grep -qFx (精确行匹配)
        # 跨 sh 兼容 (dash/bash/zsh) 且无 case glob 限制.
        rel="web/dist/assets/$bn"
        if echo "$head_dist" | grep -qFx "$rel"; then
            continue
        fi
        # W100 +75c: 跳过 staged 已删的 dist (避免 deleted vs new 矛盾, hook 短路)
        case " $deleted_dist " in
            *" $f "*) continue ;;
        esac
        local_new_dist="$local_new_dist $f"
    done
fi

if [ -z "$local_new_dist" ]; then
    ELAPSED=$(($(date +%s) - START_TIME))
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

# W100 +75c: 自动 add 加 timeout 30 防 git 卡死
timeout 30 git add -f web/dist/ || {
    echo ""
    echo "❌ [pre-commit] git add 超时 (30s), 手动跑 git add -f web/dist/"
    exit 0  # W100 +75c: 不阻断 commit, 仅警告
}

# ---- 4. 验证 + 报告 ----
new_staged=$(git diff --cached --name-only -- 'web/dist/' | wc -l)
echo ""
echo "✅ [pre-commit] 已 staged $new_staged 个 web/dist/ 文件, commit 继续"
echo ""

# W100 +75c: 总耗时输出 + 30s 警告
ELAPSED=$(($(date +%s) - START_TIME))
echo "⏱  [pre-commit] hook 总耗时: ${ELAPSED}s"
if [ "$ELAPSED" -gt 30 ]; then
    echo "⚠️  [pre-commit] 耗时 > 30s, 接近 harness timeout (默认 10min, 但 > 30s 体验差)"
    echo "   如果反复触发, 检查 web/dist/ 文件数 (200+ 文件可能触发 git add 慢)"
fi

exit 0
