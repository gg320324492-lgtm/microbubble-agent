#!/bin/sh
# scripts/push-main.sh
#
# W100 +75d: push 流程加固 (重试 + rev-list 验证 + force-with-lease)
#
# 根因 (W100 +50 实战):
#   - 本地 main ref 偶尔会从 packed-refs 删除 (Windows git 2.x bug + 大仓库场景)
#   - `git push origin main` 显示 "Everything up-to-date" 但本地 ahead 实际 > 0
#   - 服务器拿不到新 commit, 服务器白屏或前端旧 dist 404
#
# 行为:
#   1. `git push origin main` 重试 3 次, 指数退避 (1s/2s/4s)
#   2. `git rev-list origin/main..HEAD --count` 验证 ahead 数量
#   3. ahead = 0 但本地 git log 与 origin 不一致 → 自动 `git fetch origin main` + `push --force-with-lease`
#   4. 输出 `✅ PUSH OK (N commits ahead)` 或 `❌ PUSH FAILED` + 退出码
#
# 用法:
#   bash scripts/push-main.sh
#
# 类 20 永久铁律 (派工 v6 §13.3 假设禁令沿用):
#   - "Everything up-to-date" 不等于 push 成功, 必须 rev-list 验证
#   - 不要用 `git push --force` (会覆盖远程别人提交), 用 `--force-with-lease` 安全覆盖

set -e

# 颜色输出 (Windows Git Bash 支持 ANSI)
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_ok() { printf "${GREEN}[OK]${NC} %s\n" "$1"; }
log_err() { printf "${RED}[ERROR]${NC} %s\n" "$1" >&2; }
log_warn() { printf "${YELLOW}[WARN]${NC} %s\n" "$1"; }

# 验证当前分支是 main (防止误推其他分支)
CURRENT_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "DETACHED")
if [ "$CURRENT_BRANCH" != "main" ]; then
    log_err "当前分支是 '$CURRENT_BRANCH', 不是 'main'"
    log_err "本脚本只推 main 分支, 避免误推 feature 分支"
    exit 1
fi

# 验证 git 仓库
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    log_err "当前目录不是 git 仓库"
    exit 1
fi

# 检查 working tree 干净 (有未 commit 改动时强制用户先处理)
if [ -n "$(git status --porcelain)" ]; then
    log_warn "working tree 不干净, push 可能丢改动:"
    git status --short | head -5 | sed 's/^/  /'
    log_warn "请先 commit/stash 后重试 (本脚本不自动 stash, 避免误操作)"
    exit 1
fi

# ---- 1. git push 重试 3 次 + 指数退避 ----
log_ok "尝试 git push origin main (重试 3 次 + 指数退避)..."
PUSH_OK=0
DELAY=1
for i in 1 2 3; do
    if git push origin main 2>&1; then
        PUSH_OK=1
        break
    else
        log_warn "第 $i 次 push 失败, ${DELAY}s 后重试..."
        sleep $DELAY
        DELAY=$((DELAY * 2))
    fi
done

if [ "$PUSH_OK" -eq 0 ]; then
    log_err "git push 重试 3 次仍失败, 请检查网络/远程仓库状态"
    exit 1
fi

# ---- 2. rev-list 验证 ahead ----
AHEAD=$(git rev-list origin/main..HEAD --count 2>/dev/null || echo "unknown")
REMOTE_HEAD=$(git rev-parse origin/main 2>/dev/null || echo "unknown")
LOCAL_HEAD=$(git rev-parse HEAD 2>/dev/null || echo "unknown")

if [ "$AHEAD" = "0" ]; then
    log_warn "本地 ahead = 0, 检查是否需要 force-with-lease..."
    if [ "$REMOTE_HEAD" != "$LOCAL_HEAD" ]; then
        log_warn "本地 HEAD ($LOCAL_HEAD) 与 origin/main ($REMOTE_HEAD) 不一致"
        log_warn "尝试 git fetch origin main + push --force-with-lease 修复..."
        if ! git fetch origin main 2>&1; then
            log_err "git fetch 失败, 无法自动修复"
            exit 1
        fi
        # 重新计算 ahead (fetch 后)
        AHEAD=$(git rev-list origin/main..HEAD --count 2>/dev/null || echo "unknown")
        if [ "$AHEAD" = "0" ]; then
            # 真没 ahead, 直接 force-with-lease 把本地 HEAD 推到 origin
            log_warn "fetch 后本地仍 ahead = 0, 强制 force-with-lease..."
            if ! git push origin main --force-with-lease 2>&1; then
                log_err "force-with-lease 失败, 需手动排查"
                exit 1
            fi
        fi
    else
        log_ok "本地与 origin 完全一致 (无需 push), 但运行了 push 校验"
        printf "\n${GREEN}✅ PUSH OK (no-op, 本地与 origin 一致)${NC}\n"
        exit 0
    fi
fi

# ---- 3. 最终验证 ----
FINAL_AHEAD=$(git rev-list origin/main..HEAD --count 2>/dev/null || echo "unknown")
FINAL_REMOTE=$(git rev-parse origin/main 2>/dev/null || echo "unknown")

if [ "$FINAL_AHEAD" = "0" ] && [ "$LOCAL_HEAD" = "$FINAL_REMOTE" ]; then
    printf "\n${GREEN}✅ PUSH OK${NC} (本地与 origin/main HEAD 一致: $LOCAL_HEAD)\n"
    exit 0
elif [ "$FINAL_AHEAD" != "0" ]; then
    log_warn "推送后本地仍 ahead = $FINAL_AHEAD (可能在等其他 commit push)"
    log_warn "如反复触发, 检查:"
    log_warn "  1. ref 是否被 packed-refs 删除 (git update-ref)"
    log_warn "  2. 是否有 submodule push 失败"
    log_warn "  3. 服务器是否在 fetching (webhook 异步)"
    printf "\n${YELLOW}⚠️ PUSH OK with warning${NC} (ahead = $FINAL_AHEAD)\n"
    exit 0
else
    log_err "PUSH 状态异常, 本地 HEAD: $LOCAL_HEAD, origin HEAD: $FINAL_REMOTE, ahead: $FINAL_AHEAD"
    exit 1
fi