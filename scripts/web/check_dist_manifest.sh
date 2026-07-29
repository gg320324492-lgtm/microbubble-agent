#!/usr/bin/env bash
# scripts/web/check_dist_manifest.sh
# W86 第 1 批 D-1 (锚点范式 320 → 321 预期) — pre-commit Hook 5: dist manifest hash
#
# 目的:
#     防止 web/dist/ 里出现 unhashed `manifest.webmanifest` 引用
#     (CLAUDE.md 永久纪律 `npm run build` 唯一合法, 2026-07-11 59187ce8 回归教训)
#
# 事故链路:
#     1. developer 跑 `vite build` (直跑, 绕开 postbuild-fix-manifest.js)
#     2. manifest 保持 unhashed → web/dist/manifest.webmanifest
#     3. nginx `location = /manifest.webmanifest { return 410; }` 拦截
#     4. 浏览器收 410 → "Manifest fetch failed" → PWA install 失败
#
# 本 hook 检查项:
#     - web/dist/sw.js 里不能引用 unhashed `manifest.webmanifest`
#     - web/dist/ 里不能存在 unhashed `manifest.webmanifest` 文件本身
#     - 命中 → exit 1
#
# 退出码:
#     0 = manifest 已 hash 化 (合规)
#     1 = 发现 unhashed manifest (违规)
#
# 用法:
#     bash scripts/web/check_dist_manifest.sh
#
# 集成:
#     .pre-commit-config.yaml → hook: dist-manifest-hash
#     files: ^web/dist/

set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ROOT" ]; then
    echo "❌ [pre-commit] 不在 git 仓库里"
    exit 1
fi

cd "$REPO_ROOT"

# ---- 1. 检查 web/dist/ 是否存在 ----
if [ ! -d "web/dist" ]; then
    echo "INFO: web/dist/ 不存在 (first build?), 跳过 (空仓库不阻断)"
    exit 0
fi

VIOLATIONS=0

# ---- 2. 检查 web/dist/sw.js 是否引用 unhashed manifest ----
if [ -f "web/dist/sw.js" ]; then
    # 检查 staged + 工作区 (含 uncommitted) 的 sw.js 都查一次
    # 模式: '"url": "manifest.webmanifest"' (workbox manifest URL 配置)
    # 排除 hash 化的: 'manifest.<8hex>.webmanifest'

    if grep -qE '"url":[[:space:]]*"manifest\.webmanifest"' web/dist/sw.js 2>/dev/null; then
        echo "❌ [pre-commit] web/dist/sw.js 引用 unhashed manifest.webmanifest"
        echo ""
        echo "📍 位置:"
        grep -nE '"url":[[:space:]]*"manifest\.webmanifest"' web/dist/sw.js | sed 's/^/   /'
        echo ""
        VIOLATIONS=$((VIOLATIONS + 1))
    fi

    # 也检查 staged diff (commit 前最后一次保险)
    STAGED_SW=$(git diff --cached -- web/dist/sw.js 2>/dev/null)
    if echo "$STAGED_SW" | grep -qE '"url":[[:space:]]*"manifest\.webmanifest"'; then
        echo "❌ [pre-commit] staged web/dist/sw.js 含 unhashed manifest 引用"
        echo ""
        echo "$STAGED_SW" | grep -nE '"url":[[:space:]]*"manifest\.webmanifest"' | sed 's/^/   /'
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
fi

# ---- 3. 检查 web/dist/ 是否存在 unhashed manifest.webmanifest 文件本身 ----
# 注意: hashed manifest 应形如 web/dist/manifest.<8hex>.webmanifest
#       unhashed 形如 web/dist/manifest.webmanifest (无 hash 段)
if [ -f "web/dist/manifest.webmanifest" ]; then
    echo "❌ [pre-commit] web/dist/manifest.webmanifest 存在 (未 hash 化)"
    echo ""
    echo "📍 文件: web/dist/manifest.webmanifest"
    echo "   应该改名为 web/dist/manifest.<8hex>.webmanifest (e.g. manifest.4f8d6b64.webmanifest)"
    VIOLATIONS=$((VIOLATIONS + 1))
fi

# ---- 4. 检查 staged 上是否要 stage 一个 unhashed manifest ----
STAGED_FILES=$(git diff --cached --name-only -- web/dist/ 2>/dev/null | grep -E '/manifest\.webmanifest$' || true)
UNHASHED_STAGED=$(echo "$STAGED_FILES" | grep -vE '/manifest\.[a-f0-9]{8}\.webmanifest$' || true)
if [ -n "$UNHASHED_STAGED" ]; then
    echo "❌ [pre-commit] staged 含 unhashed manifest 文件"
    echo ""
    echo "$UNHASHED_STAGED" | sed 's/^/   /'
    VIOLATIONS=$((VIOLATIONS + 1))
fi

# ---- 5. 输出结果 ----
if [ "$VIOLATIONS" -gt 0 ]; then
    echo ""
    echo "🚨 共 $VIOLATIONS 处违反 (CLAUDE.md 永久纪律 `npm run build` 唯一合法)"
    echo ""
    echo "🔧 修复路径:"
    echo "   1) 删 web/dist/manifest.webmanifest (如果存在)"
    echo "   2) 跑 cd web && npm run build (走 postbuild-fix-manifest.js 自动 hash)"
    echo "   3) 重新 staged: git add -f web/dist/manifest.*.webmanifest"
    echo ""
    echo "📖 教训沉淀:"
    echo "   - CLAUDE.md 永久纪律: `npm run build` 唯一合法 (`vite build` 直跑必坏 PWA)"
    echo "   - commit 59187ce8 cascade 引入 regression, commit 5d2bcdfd 修复"
    echo "   - nginx `location = /manifest.webmanifest { return 410; }` 是有意防护"
    echo "     (防 SPA `try_files` fallback 误返 index.html, commit c855f0e 教训)"
    echo ""
    exit 1
fi

echo "✅ [pre-commit] web/dist/ manifest 已 hash 化 (合规)"
exit 0
