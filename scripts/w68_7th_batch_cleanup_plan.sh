#!/usr/bin/env bash
# scripts/w68_7th_batch_cleanup_plan.sh
#
# W68 第 7 批 worktree + 分支清理脚本 (2026-07-24)
#
# 背景:
#   W68 第 7 批 15 worktree + 16 分支 (15 W68 第 7 批 + 1 priceless-grothendieck hot-fix #18)
#   待清理. 主指挥合并后才能删分支 (per task: chore/w68-8th-batch-c2-cleanup-2026-07-24).
#
# 行为 (双模):
#   - 默认 dry-run: 只 print 哪些 worktree/branch 待清理, 不真删
#   - --apply: 按依赖顺序真执行 (主指挥拍板后才跑)
#
# 清理范围 (15 + 1):
#   ┌─ W68 第 7 批 A-1 (cached-giggling-pebble-fix)        → agent-a00103ef46303806c
#   ├─ W68 第 7 批 A-2 (cheerful-anchor-scripts)            → agent-a83d1f096269a7455
#   ├─ W68 第 7 批 A-3 (qa-bench-isolation)                → agent-a785756f198d623ee
#   ├─ W68 第 7 批 A-4 (qa-bench-d5-kb-monitor)             → agent-a862622ec21e4f37b
#   ├─ W68 第 7 批 A-5 (silly-gliding-dahl)                 → agent-a15b80d0cf50a32ec
#   ├─ W68 第 7 批 B-1 (drive-v2-pr10-collab-ws)            → agent-a68b44365140e9956
#   ├─ W68 第 7 批 B-2 (qa-bench-phase2-dry)                → agent-a9ab41846632dd8cc
#   ├─ W68 第 7 批 B-3 (mobile-v3.2-push-backend)            → agent-a8e0f5a43fed97bbe
#   ├─ W68 第 7 批 C-1 (plans-status-fix)                   → agent-a2fa62d9143ea67e4
#   ├─ W68 第 7 批 C-2 (plans-archive)                      → agent-af1bda3114821c1f7
#   ├─ W68 第 7 批 C-3 (verified-plans-doc-sync)            → agent-a4ef176d4f5c8a3c0
#   ├─ W68 第 7 批 D-1 (5th-batch-deploy)                   → agent-a5b02d4327953632f
#   ├─ W68 第 7 批 D-3 (claude-code-voice-alert)            → agent-ab788b1ac3a6db3da
#   ├─ W68 第 7 批 grand closure                            → agent-af25e11b3f78258cc
#   ├─ Drive v2 PR10 deploy runbook                         → agent-ac0caaff1a01d57bb
#   └─ [KEEP] priceless-grothendieck-6a2998 (hot-fix #18)   → DO NOT TOUCH
#
# 纪律 (per CLAUDE.md 锚点范式 + W68 跨主题收口):
#   1. **合并后才能删分支** — W68 第 7 批 分支已合并到 chore/w68-8th-batch-a1-merge-2026-07-24
#      (8th batch staging), 主指挥 merge 后才能删. 删除前必须先 verify 合并状态
#   2. **默认 dry-run** — 不带 --apply 永远不执行 git worktree remove / git branch -D
#   3. **不动 hot-fix #18 worktree** — priceless-grothendieck-6a2998 是主指挥本地 hot-fix #18
#      worktree, 还在跑 (per memory/w68-route-5-hotfix-knowledge-uploader-id-2026-07-24.md)
#   4. **删前备份分支清单** — 写到 /tmp/w68-7th-batch-branches-backup-<ts>.txt 方便回滚
#   5. **删后 verify baseline** — 跑 `bash scripts/check-baseline.sh` (or equivalent 71 PASS + 7 SKIP)
#      确认 Lint CSS 守恒 + 不破坏既有 baseline
#
# 用法:
#   # 1. 先 dry-run 看哪些会被删 (推荐先跑)
#   bash scripts/w68_7th_batch_cleanup_plan.sh
#
#   # 2. 验证输出无误后再 apply (主指挥拍板)
#   bash scripts/w68_7th_batch_cleanup_plan.sh --apply
#
#   # 3. (可选) 跳过 dry-run verify 步骤
#   bash scripts/w68_7th_batch_cleanup_plan.sh --apply --force
#
# 回滚:
#   - worktree: git worktree add .claude/worktrees/<name> <branch>
#   - branch:  git branch <branch> <ref>; git push origin <branch>
#   - 详见 docs/w68-7th-batch-cleanup-runbook.md 第 3 节

set -euo pipefail

# ---- 0. 配置 ----
SCRIPT_NAME=$(basename "$0")
DRY_RUN=true
FORCE=false
BACKUP_FILE="/tmp/w68-7th-batch-branches-backup-$(date +%Y%m%d-%H%M%S).txt"

# W68 第 7 批清理清单: worktree_path<TAB>branch_name
# 顺序按 W68 第 7 批 派工 ID (A-1 → A-5 → B-1 → B-3 → C-1 → C-3 → D-1 → D-3 → grand closure → runbook)
CLEANUP_LIST=$(cat <<'EOF'
agent-a00103ef46303806c	chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24
agent-a83d1f096269a7455	chore/w68-7th-batch-a2-cheerful-anchor-scripts-2026-07-24
agent-a785756f198d623ee	chore/w68-7th-batch-a3-qa-bench-isolation-2026-07-24
agent-a862622ec21e4f37b	feat/qa-bench-d5-kb-monitor-2026-07-24
agent-a15b80d0cf50a32ec	feat/silly-gliding-dahl-impl-2026-07-24
agent-a68b44365140e9956	feat/drive-v2-pr10-collab-ws-2026-07-24
agent-a9ab41846632dd8cc	test/qa-bench-phase2-dry-2026-07-24
agent-a8e0f5a43fed97bbe	feat/mobile-v3.2-push-backend-2026-07-24
agent-a2fa62d9143ea67e4	chore/w68-7th-batch-c1-plans-status-fix-2026-07-24
agent-af1bda3114821c1f7	chore/w68-7th-batch-c2-plans-archive-2026-07-24
agent-a4ef176d4f5c8a3c0	chore/w68-7th-batch-c3-verified-plans-doc-sync-2026-07-24
agent-a5b02d4327953632f	chore/w68-7th-batch-d1-5th-batch-deploy-2026-07-24
agent-ab788b1ac3a6db3da	chore/w68-7th-batch-d3-claude-code-voice-alert-2026-07-24
agent-af25e11b3f78258cc	chore/w68-7th-batch-grand-closure-2026-07-24
agent-ac0caaff1a01d57bb	docs/drive-pr10-deploy-runbook-2026-07-24
EOF
)

# hot-fix #18 worktree — 永远不动
PROTECTED_WORKTREE="priceless-grothendieck-6a2998"
PROTECTED_BRANCH="claude/priceless-grothendieck-6a2998"

# ---- 1. 参数解析 ----
while [ $# -gt 0 ]; do
    case "$1" in
        --apply)
            DRY_RUN=false
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        -h|--help)
            echo "用法: $SCRIPT_NAME [--apply] [--force]"
            echo ""
            echo "默认 dry-run: 只 print 待清理清单, 不执行."
            echo "--apply: 真执行 git worktree remove + git branch -D + git push origin --delete"
            echo "--force: 跳过 dry-run verify 步骤 (仅 --apply 时有效)"
            exit 0
            ;;
        *)
            echo "ERROR: 未知参数 '$1'" >&2
            echo "用法: $SCRIPT_NAME [--apply] [--force]" >&2
            exit 1
            ;;
    esac
done

# ---- 2. 模式 banner ----
if [ "$DRY_RUN" = true ]; then
    echo "================================================================"
    echo "[DRY-RUN] W68 第 7 批 worktree + 分支清理预览 (默认模式)"
    echo "================================================================"
    echo ""
    echo "执行 $SCRIPT_NAME --apply 才会真删 (主指挥拍板)"
    echo ""
else
    echo "================================================================"
    echo "[APPLY MODE] W68 第 7 批 worktree + 分支真清理"
    echo "================================================================"
    echo ""
fi

# ---- 3. 解析 + 打印待清理清单 ----
echo "[1/4] 待清理 worktree + 分支清单 (15 项):"
echo ""

TOTAL=0
EXISTING_WORKTREES=0
EXISTING_BRANCHES=0
MISSING_WORKTREES=0

while IFS=$'\t' read -r WORKTREE_NAME BRANCH_NAME; do
    TOTAL=$((TOTAL + 1))
    WORKTREE_PATH=".claude/worktrees/${WORKTREE_NAME}"
    BRANCH_REF="refs/heads/${BRANCH_NAME}"
    REMOTE_REF="refs/remotes/origin/${BRANCH_NAME}"

    # 检查 worktree 是否存在 (兼容绝对路径 + 相对路径两种 porcelain 输出)
    WT_EXISTS="NO"
    if [ -d "$WORKTREE_PATH" ]; then
        # 方法: 用 git worktree list + grep -F 匹配 worktree basename (兼容 abs/rel 路径)
        if git worktree list 2>/dev/null | grep -qF "${WORKTREE_NAME}"; then
            WT_EXISTS="YES"
            EXISTING_WORKTREES=$((EXISTING_WORKTREES + 1))
        else
            MISSING_WORKTREES=$((MISSING_WORKTREES + 1))
        fi
    else
        MISSING_WORKTREES=$((MISSING_WORKTREES + 1))
    fi

    # 检查分支是否存在 (local + remote)
    BR_LOCAL_EXISTS="NO"
    BR_REMOTE_EXISTS="NO"
    if git show-ref --verify --quiet "$BRANCH_REF" 2>/dev/null; then
        BR_LOCAL_EXISTS="YES"
        EXISTING_BRANCHES=$((EXISTING_BRANCHES + 1))
    fi
    if git show-ref --verify --quiet "$REMOTE_REF" 2>/dev/null; then
        BR_REMOTE_EXISTS="YES"
    fi

    printf "  [%2d] %-32s | WT:%-3s | branch-local:%-3s | branch-remote:%-3s\n" \
        "$TOTAL" "$WORKTREE_NAME" "$WT_EXISTS" "$BR_LOCAL_EXISTS" "$BR_REMOTE_EXISTS"
done <<EOF
$CLEANUP_LIST
EOF

echo ""
echo "统计: 总计 ${TOTAL} 项 | 存在 worktree ${EXISTING_WORKTREES} | 缺失 ${MISSING_WORKTREES}"
echo "      存在 local branch ${EXISTING_BRANCHES}"
echo ""

# ---- 4. 保护 hot-fix #18 ----
echo "[2/4] 保护清单 (不动):"
echo "  - worktree: ${PROTECTED_WORKTREE} (DO NOT TOUCH)"
echo "  - branch:   ${PROTECTED_BRANCH} (主指挥本地 hot-fix #18 仍跑)"
echo ""

# ---- 5. DRY-RUN 模式: 结束 ----
if [ "$DRY_RUN" = true ]; then
    echo "================================================================"
    echo "[DRY-RUN COMPLETE] 不真删. 主指挥拍板后跑: $SCRIPT_NAME --apply"
    echo "================================================================"
    exit 0
fi

# ---- 6. APPLY 模式: 主指挥拍板 verify ----
if [ "$FORCE" != true ]; then
    echo "[3/4] 主指挥拍板 verify (无 --force 必跑):"
    echo ""
    echo "  ⚠️ 即将执行 3 步不可逆操作:"
    echo "     1. git worktree remove --force .claude/worktrees/<name>  (15 次)"
    echo "     2. git branch -D <branch>                                  (15 次)"
    echo "     3. git push origin --delete <branch>                       (15 次)"
    echo ""
    echo "  备份清单会写到: ${BACKUP_FILE}"
    echo ""
    read -r -p "  主指挥确认? 输入 'yes' 继续, 其他取消: " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo ""
        echo "[ABORTED] 用户取消. 未执行任何清理."
        exit 1
    fi
    echo ""
fi

# ---- 7. 备份分支清单 ----
echo "[3/4] 备份分支清单到 ${BACKUP_FILE}"
{
    echo "# W68 第 7 批 分支清理备份 ($(date '+%Y-%m-%d %H:%M:%S'))"
    echo "# 格式: <worktree_path>\\t<branch>\\t<branch-sha>"
    echo ""
    while IFS=$'\t' read -r WORKTREE_NAME BRANCH_NAME; do
        WORKTREE_PATH=".claude/worktrees/${WORKTREE_NAME}"
        SHA=$(git rev-parse --short "$BRANCH_NAME" 2>/dev/null || echo "MISSING")
        printf "%s\t%s\t%s\n" "$WORKTREE_PATH" "$BRANCH_NAME" "$SHA"
    done <<EOF
$CLEANUP_LIST
EOF
} > "$BACKUP_FILE"
echo "  备份完成: $(wc -l < "$BACKUP_FILE") 行"
echo ""

# ---- 8. 执行清理 (3 阶段) ----
echo "[4/4] 执行清理 (3 阶段, 按依赖顺序):"
echo ""

# 阶段 1: 移除 worktree
echo "  阶段 1/3: git worktree remove --force (15 个)"
WT_REMOVED=0
WT_FAILED=0
while IFS=$'\t' read -r WORKTREE_NAME BRANCH_NAME; do
    WORKTREE_PATH=".claude/worktrees/${WORKTREE_NAME}"

    # 跳过 hot-fix
    if [ "$WORKTREE_NAME" = "$PROTECTED_WORKTREE" ]; then
        echo "    SKIP: $WORKTREE_NAME (protected)"
        continue
    fi

    if [ ! -d "$WORKTREE_PATH" ]; then
        echo "    SKIP: $WORKTREE_NAME (worktree 不存在)"
        continue
    fi

    if git worktree remove --force "$WORKTREE_PATH" 2>/dev/null; then
        echo "    OK:   $WORKTREE_NAME"
        WT_REMOVED=$((WT_REMOVED + 1))
    else
        echo "    FAIL: $WORKTREE_NAME"
        WT_FAILED=$((WT_FAILED + 1))
    fi
done <<EOF
$CLEANUP_LIST
EOF
echo "    阶段 1 完成: 成功 ${WT_REMOVED}, 失败 ${WT_FAILED}"
echo ""

# 阶段 2: 删除 local 分支
echo "  阶段 2/3: git branch -D (15 个)"
BR_DELETED=0
BR_FAILED=0
while IFS=$'\t' read -r WORKTREE_NAME BRANCH_NAME; do
    # 跳过 hot-fix
    if [ "$BRANCH_NAME" = "$PROTECTED_BRANCH" ]; then
        echo "    SKIP: $BRANCH_NAME (protected)"
        continue
    fi

    if ! git show-ref --verify --quiet "refs/heads/${BRANCH_NAME}" 2>/dev/null; then
        echo "    SKIP: $BRANCH_NAME (本地分支不存在)"
        continue
    fi

    if git branch -D "$BRANCH_NAME" 2>/dev/null; then
        echo "    OK:   $BRANCH_NAME"
        BR_DELETED=$((BR_DELETED + 1))
    else
        echo "    FAIL: $BRANCH_NAME"
        BR_FAILED=$((BR_FAILED + 1))
    fi
done <<EOF
$CLEANUP_LIST
EOF
echo "    阶段 2 完成: 成功 ${BR_DELETED}, 失败 ${BR_FAILED}"
echo ""

# 阶段 3: 删除 remote 分支
echo "  阶段 3/3: git push origin --delete (15 个)"
REMOTE_DELETED=0
REMOTE_FAILED=0
while IFS=$'\t' read -r WORKTREE_NAME BRANCH_NAME; do
    # 跳过 hot-fix
    if [ "$BRANCH_NAME" = "$PROTECTED_BRANCH" ]; then
        echo "    SKIP: origin/$BRANCH_NAME (protected)"
        continue
    fi

    if ! git show-ref --verify --quiet "refs/remotes/origin/${BRANCH_NAME}" 2>/dev/null; then
        echo "    SKIP: origin/$BRANCH_NAME (远程分支不存在)"
        continue
    fi

    if git push origin --delete "$BRANCH_NAME" 2>/dev/null; then
        echo "    OK:   origin/$BRANCH_NAME"
        REMOTE_DELETED=$((REMOTE_DELETED + 1))
    else
        echo "    FAIL: origin/$BRANCH_NAME"
        REMOTE_FAILED=$((REMOTE_FAILED + 1))
    fi
done <<EOF
$CLEANUP_LIST
EOF
echo "    阶段 3 完成: 成功 ${REMOTE_DELETED}, 失败 ${REMOTE_FAILED}"
echo ""

# ---- 9. 总结 ----
echo "================================================================"
echo "[CLEANUP COMPLETE] W68 第 7 批 清理完成"
echo "================================================================"
echo ""
echo "  worktree 移除: ${WT_REMOVED} 成功, ${WT_FAILED} 失败"
echo "  branch 删除:   ${BR_DELETED} 成功, ${BR_FAILED} 失败"
echo "  remote 删除:   ${REMOTE_DELETED} 成功, ${REMOTE_FAILED} 失败"
echo ""
echo "  备份文件: ${BACKUP_FILE}"
echo "  保护项:   ${PROTECTED_WORKTREE} (主指挥 hot-fix #18)"
echo ""
echo "  下一步:"
echo "    1. 验证 baseline 守恒: bash scripts/check-baseline.sh (期望 71 PASS + 7 SKIP)"
echo "    2. 验证 worktree list: git worktree list (期望 ~10 项, 不含 15 个 W68 第 7 批)"
echo "    3. 验证 branch list:   git branch -r (期望 ~5 项 remote, 不含 15 个 W68 第 7 批)"
echo "    4. 详见 docs/w68-7th-batch-cleanup-runbook.md 第 2 节"
echo ""

exit 0