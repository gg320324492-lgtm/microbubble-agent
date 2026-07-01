#!/bin/sh
# scripts/setup-hooks.sh
#
# 一键安装所有 git hooks (CLAUDE.md 2026-07-01 教训沉淀)
# 教训: 项目 hooks (.git/hooks/) 不在 git tracked 里, 新成员 clone 后
# 手动 cp scripts/* 到 .git/hooks/ 易遗漏. 此脚本统一安装.
#
# 用法:
#   bash scripts/setup-hooks.sh         # 安装/更新
#   bash scripts/setup-hooks.sh --check # 检查状态 (不安装)
#
# 安装的 hooks:
#   1. pre-commit  → scripts/check-secrets-before-commit.sh + check-dist-before-commit.sh
#                    (串联, secrets 优先 hard block, dist 后 soft auto-add)
#   2. post-commit → 自动 git push origin main (CLAUDE.md 2026-06-26 教训)

set -e

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ROOT" ]; then
    echo "❌ 错误: 不在 git 仓库里"
    exit 1
fi

HOOKS_DIR="$REPO_ROOT/.git/hooks"
SCRIPTS_DIR="$REPO_ROOT/scripts"

# ---- 1. 检查所有 hook script 存在 ----
REQUIRED_SCRIPTS="check-secrets-before-commit.sh check-dist-before-commit.sh"
for s in $REQUIRED_SCRIPTS; do
    if [ ! -f "$SCRIPTS_DIR/$s" ]; then
        echo "❌ 错误: 缺 $SCRIPTS_DIR/$s"
        echo "   请检查 git 是否正确 clone (含 scripts/ 目录)"
        exit 1
    fi
done

# ---- 2. 检查模式 (--check) ----
if [ "$1" = "--check" ]; then
    echo "🔍 检查 hook 状态"
    echo ""
    NEEDS_INSTALL=0

    if [ ! -f "$HOOKS_DIR/pre-commit" ]; then
        echo "❌ pre-commit 不存在"
        NEEDS_INSTALL=1
    elif ! grep -q "check-secrets-before-commit.sh" "$HOOKS_DIR/pre-commit" 2>/dev/null; then
        echo "❌ pre-commit 不含 secrets 检查 (过时版本)"
        NEEDS_INSTALL=1
    elif ! grep -q "check-dist-before-commit.sh" "$HOOKS_DIR/pre-commit" 2>/dev/null; then
        echo "❌ pre-commit 不含 dist 检查 (过时版本)"
        NEEDS_INSTALL=1
    else
        echo "✅ pre-commit 已正确配置 (secrets + dist)"
    fi

    if [ ! -f "$HOOKS_DIR/post-commit" ]; then
        echo "❌ post-commit 不存在"
        NEEDS_INSTALL=1
    elif ! grep -q "git push origin main" "$HOOKS_DIR/post-commit" 2>/dev/null; then
        echo "❌ post-commit 不含 git push (过时版本)"
        NEEDS_INSTALL=1
    else
        echo "✅ post-commit 已正确配置 (auto-push main)"
    fi

    if [ $NEEDS_INSTALL = 1 ]; then
        echo ""
        echo "💡 修复: bash scripts/setup-hooks.sh"
        exit 1
    fi
    exit 0
fi

# ---- 3. 安装/更新 pre-commit ----
echo "📦 安装 pre-commit hook..."

# 备份旧 hook (如果有)
if [ -f "$HOOKS_DIR/pre-commit" ]; then
    cp "$HOOKS_DIR/pre-commit" "$HOOKS_DIR/pre-commit.bak.$(date +%Y%m%d-%H%M%S)"
    echo "   备份旧 hook 到 pre-commit.bak.<timestamp>"
fi

cat > "$HOOKS_DIR/pre-commit" << 'HOOK_EOF'
#!/bin/sh
# .git/hooks/pre-commit
#
# 串联两个独立检查 (顺序很重要):
#   1. secrets: hard block (admin JWT 等凭据绝不能入库)
#   2. dist:    soft auto-fix (漏 add web/dist/ 自动补)
#
# 为什么顺序: secrets 必须在 dist 之前
#   - secrets fail → commit 中止, 不应让 dist hook 再 auto-add 文件
#   - dist auto-add 可能改变 staged diff, 让 secrets check 错位
#
# 安装方式: bash scripts/setup-hooks.sh (CLAUDE.md 2026-07-01 沉淀)

REPO_ROOT="$(git rev-parse --show-toplevel)"

# 1. Secrets check (hard block, 教训: 2026-07-01 commit 6573f2b3 删 _login/_token 后沉淀)
sh "$REPO_ROOT/scripts/check-secrets-before-commit.sh" "$@"

# 2. Dist check (soft auto-fix, 含 token-orphan hard block, 教训: CLAUDE.md 2026-06-26 f6a2bc3d)
sh "$REPO_ROOT/scripts/check-dist-before-commit.sh" "$@"
HOOK_EOF

chmod +x "$HOOKS_DIR/pre-commit"
echo "   ✅ pre-commit 已更新 (串联 secrets + dist)"

# ---- 4. 安装/更新 post-commit ----
echo "📦 安装 post-commit hook..."

if [ -f "$HOOKS_DIR/post-commit" ]; then
    cp "$HOOKS_DIR/post-commit" "$HOOKS_DIR/post-commit.bak.$(date +%Y%m%d-%H%M%S)"
    echo "   备份旧 hook 到 post-commit.bak.<timestamp>"
fi

cat > "$HOOKS_DIR/post-commit" << 'HOOK_EOF'
#!/bin/sh
# v28 step 59: commit 后自动 push 到 origin main
# 用 git symbolic-ref HEAD 判断是否在 main 分支，避免在其他分支误 push
current_branch=$(git symbolic-ref HEAD 2>/dev/null)
if [ "$current_branch" = "refs/heads/main" ]; then
    git push origin main
fi
HOOK_EOF

chmod +x "$HOOKS_DIR/post-commit"
echo "   ✅ post-commit 已更新 (auto-push main)"

# ---- 5. 验证 ----
echo ""
echo "✅ 所有 hooks 已安装"
echo ""
echo "📋 验证:"
echo "   bash scripts/setup-hooks.sh --check"
echo ""
echo "🚀 下次 commit 会自动跑:"
echo "   1. secrets hook (hard block, 拒绝 admin JWT 入库)"
echo "   2. dist hook (soft auto-add, 漏 commit web/dist/ 时自动补)"
echo "   3. post-commit (main 分支自动 push)"
echo ""
echo "⚠️  提醒:"
echo "   - .env 里的 SECRET_KEY 必须不是默认占位符 (change-this-to-a-...)"
echo "   - admin 密码不能用 123456 这种弱密码 (bot 攻击秒破)"
echo "   - 任何 e2e 脚本必须用测试账号 xiaoqi_testbot, 不能用 wangtianzhi"