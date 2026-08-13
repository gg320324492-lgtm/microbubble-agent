#!/bin/bash
# MicroBubble Agent - 自动部署脚本（merge 到 main 后触发）
#
# 完整部署链:
#   1. web/build (PWA dist 必须 force-add 到 git, 服务器不构建)
#   2. alembic check (schema 改动验证)
#   3. git add -f + git commit (合并 commit 含 web/dist)
#   4. git push origin main (触发服务器 webhook → 自动 git pull + Nginx reload)
#   5. 本地 PC: docker cp + __pycache__ clear + docker restart app/celery-worker (后端代码生效)
#
# 设计思路:
#   - 服务器端部署已自动化 (scripts/webhook.py + scripts/deploy-auto.sh)
#   - 本地 PC 的 "merge 后增量同步 + docker restart" 是最后一段空白
#   - 本脚本填补这段空白, 可手动 (bash scripts/auto-deploy.sh) 或通过 .claude/settings.json hook 自动调用
#
# 用法:
#   bash scripts/auto-deploy.sh                    # 完整部署链 (默认)
#   bash scripts/auto-deploy.sh --skip-build       # 跳过前端 build (纯后端改动)
#   bash scripts/auto-deploy.sh --skip-push        # 跳过 git push (仅本地 build + restart)
#   bash scripts/auto-deploy.sh --skip-restart     # 跳过 docker restart (仅 build + push)
#   bash scripts/auto-deploy.sh --dry-run          # 演练, 不执行任何写操作
#
# 关联铁律:
#   - CLAUDE.md 2026-06-13 "PWA manifest 410 回归": npm run build 是唯一合法 build 命令
#   - CLAUDE.md 2026-06-13 "Vue 3.5 bum null bug": build 后必须过健全性自检
#   - CLAUDE.md 2026-07-14 "deploy-auto.sh git clean 排除 web/dist": 服务器依赖 git 里的 dist
#   - CLAUDE.md 752 行铁律: "docker cp + __pycache__ clear + docker restart"
#
# 类 20 沉淀:
#   - 类 20.117 (新增): 自动部署脚本必须含 --dry-run, 演练模式不写任何文件, 默认开启幂等检查

set -euo pipefail

# ============================================
# 参数解析
# ============================================
SKIP_BUILD=0
SKIP_PUSH=0
SKIP_RESTART=0
DRY_RUN=0
COMMIT_MSG=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-build)
            SKIP_BUILD=1
            shift
            ;;
        --skip-push)
            SKIP_PUSH=1
            shift
            ;;
        --skip-restart)
            SKIP_RESTART=1
            shift
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        -m)
            COMMIT_MSG="$2"
            shift 2
            ;;
        --commit-msg)
            COMMIT_MSG="$2"
            shift 2
            ;;
        -h|--help)
            echo "用法: bash scripts/auto-deploy.sh [--skip-build] [--skip-push] [--skip-restart] [--dry-run] [-m 'commit msg']"
            echo ""
            echo "默认完整部署链: web/build + git push + docker restart"
            echo "--dry-run: 演练模式, 不执行任何写操作"
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            exit 1
            ;;
    esac
done

# ============================================
# 颜色 + 日志
# ============================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
section() { echo -e "\n${CYAN}========== $1 ==========${NC}\n"; }

# ============================================
# 环境检测
# ============================================
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

if [ "$DRY_RUN" = "1" ]; then
    info "🔍 DRY-RUN 模式, 不执行任何写操作 (仅打印计划)"
fi

# 当前分支 + 状态
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
info "项目目录: $PROJECT_DIR"
info "当前分支: $CURRENT_BRANCH"

if [ "$CURRENT_BRANCH" != "main" ]; then
    error "当前分支不是 main ($CURRENT_BRANCH), 请先合并到 main"
fi

if [ "$DRY_RUN" = "0" ]; then
    if ! git diff --quiet HEAD 2>/dev/null; then
        warn "工作区有未提交改动, 建议先 commit 或 stash"
        git status --short
        echo ""
        read -p "是否继续? (y/N) " -n 1 -r
        echo
        [[ $REPLY =~ ^[Yy]$ ]] || exit 1
    fi
fi

# ============================================
# 步骤 1: web/build
# ============================================
section "步骤 1/5: 前端构建 (npm run build)"

if [ "$SKIP_BUILD" = "1" ]; then
    info "跳过前端构建 (--skip-build)"
else
    if [ ! -d "web/node_modules" ]; then
        warn "web/node_modules 不存在, 先 npm install"
        if [ "$DRY_RUN" = "1" ]; then
            info "  [DRY-RUN] cd web && npm install"
        else
            cd web && npm install && cd ..
        fi
    fi

    info "构建前端 (PWA + 健全性自检)..."
    if [ "$DRY_RUN" = "1" ]; then
        info "  [DRY-RUN] cd web && npm run build"
        info "  [DRY-RUN] (postbuild-fix-manifest.js 自动 hash 化 manifest)"
    else
        cd web
        # npm run build 内部已经包含: vite build && node scripts/postbuild-fix-manifest.js
        npm run build
        cd ..

        # 健全性自检 (沿用 deploy-auto.sh:170-178 的检查)
        if [ -f "web/dist/sw.js" ]; then
            if grep -qE '"url":"manifest\.webmanifest"' web/dist/sw.js 2>/dev/null; then
                error "dist/sw.js 仍引用 unhashed manifest.webmanifest (postbuild-fix-manifest.js 未生效)"
            fi
            info "✓ PWA SW precache 检查通过 (sw.js 不含 unhashed manifest 引用)"
        fi
        info "✓ 前端构建完成"
    fi
fi

# ============================================
# 步骤 2: alembic 检查
# ============================================
section "步骤 2/5: Alembic schema 检查"

info "检查 alembic head 数..."
if [ "$DRY_RUN" = "1" ]; then
    info "  [DRY-RUN] python -m alembic heads (期望 1 head)"
else
    # grep 无匹配返回 exit 1, 在 set -euo pipefail 下会让管道返回 1 触发脚本中止
    # (alembic 失败或无 head 时 grep 无匹配), 必须加 || echo "0" 兜底 (沿用 line 260 模式)
    HEADS=$(python -m alembic heads 2>&1 | grep -E "^[0-9a-z]+_" | wc -l || echo "0")
    if [ "$HEADS" -ne 1 ]; then
        error "alembic head 数异常 ($HEADS 个), 期望 1 个. 详见 CLAUDE.md 2026-07-24 alembic 串单链纪律"
    fi
    HEAD_NAME=$(python -m alembic heads 2>&1 | head -1)
    info "✓ alembic 1 head: $HEAD_NAME"
fi

# ============================================
# 步骤 3: git add -f web/dist + commit
# ============================================
section "步骤 3/5: Git commit (web/dist force-add)"

if [ "$DRY_RUN" = "1" ]; then
    info "  [DRY-RUN] 检查 web/dist 是否需要 force-add"
    info "  [DRY-RUN] web/dist/ 整个目录被 .gitignore 拦了, 改任何文件必须 force-add -A"
else
    # 关键: web/dist/ 整个目录被 .gitignore 拦了 (CLAUDE.md 2026-07-14 铁律, 服务器 deploy-auto.sh
    # git clean -fdx -e web/dist 排除, 依赖 git 里已 force-add 的 dist), 所以任何 web/dist 改动都
    # 必须 git add -f -A, 不能用 git add web/dist/ (会全部被 .gitignore 静默忽略)
    info "force-add 整个 web/dist (必须 -f, .gitignore 拦了)..."
    git add -f -A web/dist/ 2>&1 | tail -3

    # 二次检查: stage 后是否还有 untracked web/dist 文件 (健全性)
    # 注意: grep 无匹配返回 exit 1, 在 set -euo pipefail 下会让管道返回 1 触发脚本中止
    # (这正是成功场景 - 所有 dist 已 force-add, 无 untracked), 必须加 || true 兜底
    UNTRACKED_DIST=$(git status --porcelain web/dist/ 2>/dev/null | grep "^??" | head -3 || true)
    if [ -n "$UNTRACKED_DIST" ]; then
        warn "⚠️ web/dist 仍有 untracked 文件 (可能 git add -f 被某个 rename 干扰):"
        echo "$UNTRACKED_DIST" | while IFS= read -r line; do info "  $line"; done
        info "逐一 force-add 兜底..."
        echo "$UNTRACKED_DIST" | awk '{print $2}' | while IFS= read -r f; do
            if [ -f "$f" ]; then
                git add -f "$f"
                info "  + $f"
            fi
        done
    fi

    # 检查是否有 staged 改动需要 commit
    if ! git diff --cached --quiet 2>/dev/null; then
        if [ -z "$COMMIT_MSG" ]; then
            COMMIT_MSG="[DEPLOY-BUILD] chore(web): build dist for webhook auto-deploy"
        fi
        info "提交 deploy-build commit..."
        git commit -m "$COMMIT_MSG"
        NEW_COMMIT=$(git rev-parse --short HEAD)
        info "✓ commit $NEW_COMMIT"
    else
        info "无 staged 改动, 跳过 commit"
    fi
fi

# ============================================
# 步骤 4: git push origin main (触发 webhook)
# ============================================
section "步骤 4/5: Git push origin main (触发服务器 webhook)"

if [ "$SKIP_PUSH" = "1" ]; then
    info "跳过 git push (--skip-push)"
else
    AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo "0")
    if [ "$AHEAD" = "0" ]; then
        info "本地与 origin/main 同步, 无需 push"
    else
        info "本地领先 origin/main $AHEAD commits, 准备 push..."
        if [ "$DRY_RUN" = "1" ]; then
            info "  [DRY-RUN] git push origin main"
            info "  [DRY-RUN] 服务器 webhook 会自动触发 deploy-auto.sh"
        else
            git push origin main
            info "✓ push 完成, 服务器 webhook 应已触发"
            info "  服务器日志: tail -f /var/log/webhook-deploy.log (ssh 到服务器)"
        fi
    fi
fi

# ============================================
# 步骤 5: 本地 PC docker restart
# ============================================
section "步骤 5/5: 本地 PC Docker 重启 (后端代码生效)"

if [ "$SKIP_RESTART" = "1" ]; then
    info "跳过 docker restart (--skip-restart)"
else
    # 检测后端是否有改动 (app/ 或 alembic/)
    PY_CHANGED=$(git diff --name-only HEAD@{1} HEAD 2>/dev/null | grep -E '^(app/|alembic/)' | wc -l || echo "0")
    if [ "$PY_CHANGED" = "0" ]; then
        info "无后端改动 (app/ alembic/), 无需重启 docker"
    else
        info "后端有 $PY_CHANGED 个文件变更, 需要 docker restart"
        if [ "$DRY_RUN" = "1" ]; then
            info "  [DRY-RUN] docker cp 后端文件到 app-1 + clear __pycache__ + restart"
        else
            # 先确认 docker 在跑
            if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q "microbubble-agent-app-1"; then
                warn "microbubble-agent-app-1 容器未运行, 跳过 restart"
            else
                info "执行: docker cp app/ → microbubble-agent-app-1:/app/app/"

                # 复制整个 app/ 目录
                docker cp "$PROJECT_DIR/app/." microbubble-agent-app-1:/app/app/ 2>&1 | tail -3
                info "✓ app/ 已同步"

                # 复制 alembic/versions/ (如果有)
                if [ "$PY_CHANGED" -gt 0 ] && git diff --name-only HEAD@{1} HEAD 2>/dev/null | grep -q "^alembic/versions/"; then
                    docker cp "$PROJECT_DIR/alembic/versions/." microbubble-agent-app-1:/app/alembic/versions/ 2>&1 | tail -3
                    info "✓ alembic/versions/ 已同步"
                fi

                # 清理 __pycache__ (CLAUDE.md 752 行铁律)
                info "清理 __pycache__ (防止老 down_revision 继续生效)..."
                docker exec microbubble-agent-app-1 find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
                info "✓ __pycache__ 已清理"

                # 重启容器 (让新代码生效)
                info "重启 app + celery-worker..."
                docker restart microbubble-agent-app-1 microbubble-agent-celery-worker-1
                sleep 5
                info "✓ 重启完成"

                # 验证服务可用
                info "验证 /health..."
                if curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1; then
                    info "✓ /health 200 OK"
                else
                    warn "⚠️ /health 检查失败, 请手动验证"
                fi
            fi
        fi
    fi
fi

# ============================================
# 收尾
# ============================================
section "部署链完成"

if [ "$DRY_RUN" = "1" ]; then
    info "🔍 DRY-RUN 完成, 未执行任何写操作"
else
    info "✅ 完整部署链执行完毕"
    echo ""
    echo "后续验证建议:"
    echo "  1. 服务器端: ssh user@server 'tail -50 /var/log/webhook-deploy.log'"
    echo "  2. 服务器端: curl -sk https://agent.mnb-lab.cn/api/v1/health"
    echo "  3. 本地 PC: docker ps (确认 app/celery-worker 已重启)"
    echo "  4. 浏览器: 硬刷 (Ctrl+Shift+R) 或 DevTools → Clear site data"
    echo "     原因: 后端 JWT/refresh_token 在部署后可能失效, localStorage 旧 token 触发 401→refresh→429 循环 (类 20.155)"
    echo "     若前端改动 (本次 commit 含 web/dist/), 浏览器 SW 也会缓存旧资源, Clear site data 才能生效"
fi
echo ""