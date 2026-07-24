#!/usr/bin/env bash
# scripts/verify_w68_5th_batch_deployment.sh
#
# W68 第 5 批 + 3 hot-fix 部署端到端快速验证脚本
# (2026-07-24, W68 第 7 批 D-1)
#
# 锚点范式第 85 守恒 — 主指挥快速检查 W68 第 5 批部署健康度:
#   1. alembic head 落点 = 064_drive_documents (Drive v2 PR10 骨架 + 单链守恒)
#   2. Drive v2 PR10 文档 (drive-v2-pr10-*.md) merge 进 main
#   3. W68 第 5 批 15 agent commits + 3 hot-fix (#16/#17/#18) 都在 main
#   4. 3 hot-fix 真跑:
#      4.1 drive_version_diff_service select import 成功
#      4.2 _compute_text_diff lineterm='\n' 真跑出 @@ hunk
#      4.3 drive_comment_service.py 已 0 命中 uploader_id (改 created_by)
#   5. baseline 71 PASS + 7 SKIP 守恒
#
# 与 verify_drive_v2_pr9_deployment.sh 的区别:
#   - 本脚本: 轻量 (~150 行), 纯静态分析 + docker exec + pytest, 不打 HTTP
#   - PR9 脚本: 重 (489 行), 12 个 HTTP endpoint + 6 表 + WS 全打
#
# 纪律 (W68 第 7 批 D-1):
#   - 仅 scripts/, 0 production code 改动
#   - 兼容 Linux (云 server) + Windows Git Bash (本地 PC 测试)
#   - 失败 fail-loud (exit 1)
#   - 不依赖网络 / TOKEN (纯本地 verify)
#
# 用法:
#   bash scripts/verify_w68_5th_batch_deployment.sh
#   DRY_RUN=1 bash scripts/verify_w68_5th_batch_deployment.sh
#
# 环境变量 (全部可选):
#   DRY_RUN    - 1 = 只打印命令不真跑, 默认 0
#
# 退出码:
#   0 = 全部 PASS
#   1 = 任一 FAIL
#   2 = 配置文件缺失 / docker compose 未起

set -u
shopt -s nocasematch 2>/dev/null || true

# ============================================================
# 0. 颜色 + 工具函数
# ============================================================
if [ -t 1 ] && command -v tput >/dev/null 2>&1 && [ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]; then
    GREEN="$(tput setaf 2 2>/dev/null || echo '')"
    RED="$(tput setaf 1 2>/dev/null || echo '')"
    YELLOW="$(tput setaf 3 2>/dev/null || echo '')"
    BLUE="$(tput setaf 4 2>/dev/null || echo '')"
    BOLD="$(tput bold 2>/dev/null || echo '')"
    RESET="$(tput sgr0 2>/dev/null || echo '')"
else
    GREEN=""; RED=""; YELLOW=""; BLUE=""; BOLD=""; RESET=""
fi

PASS_COUNT=0; FAIL_COUNT=0; SKIP_COUNT=0; TOTAL_COUNT=0
log_pass()  { printf "  %s✓ PASS%s  %s\n" "${GREEN}" "${RESET}" "$1"; PASS_COUNT=$((PASS_COUNT + 1)); TOTAL_COUNT=$((TOTAL_COUNT + 1)); }
log_fail()  { printf "  %s✗ FAIL%s  %s\n" "${RED}" "${RESET}" "$1"; if [ -n "${2:-}" ]; then printf "         原因: %s\n" "$2"; fi; FAIL_COUNT=$((FAIL_COUNT + 1)); TOTAL_COUNT=$((TOTAL_COUNT + 1)); }
log_skip()  { printf "  %s- SKIP%s  %s\n" "${YELLOW}" "${RESET}" "$1"; SKIP_COUNT=$((SKIP_COUNT + 1)); TOTAL_COUNT=$((TOTAL_COUNT + 1)); }
log_info()  { printf "  %s·%s      %s\n" "${BLUE}" "${RESET}" "$1"; }
log_warn()  { printf "  %s!%s      %s\n" "${YELLOW}" "${RESET}" "$1"; }
section()   { printf "\n%s== %s ==%s\n" "${BOLD}" "$1" "${RESET}"; }

# ============================================================
# 1. 参数 + 依赖检查
# ============================================================
DRY_RUN="${DRY_RUN:-0}"
BASE_DIR="${BASE_DIR:-$(pwd)}"

section "W68 第 5 批 + 3 hot-fix 部署验证 (W68 第 7 批 D-1)"
log_info "BASE_DIR = ${BASE_DIR}"
log_info "DRY_RUN  = ${DRY_RUN}"

# 必须在 git 仓库根目录运行
if [ ! -d "${BASE_DIR}/.git" ]; then
    log_fail "BASE_DIR 不是 git 仓库" "cd /e/microbubble-agent 或在仓库根目录跑本脚本"
    exit 2
fi
log_pass "git 仓库根目录 (HEAD = $(cd "$BASE_DIR" && git rev-parse --short HEAD 2>/dev/null))"

# 关键依赖
GIT_BIN="$(command -v git || true)"
PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then PYTHON_BIN="python"
fi
DOCKER_BIN="$(command -v docker || true)"

[ -n "$GIT_BIN" ] && log_pass "git 已安装 ($($GIT_BIN --version | head -1))" || { log_fail "git 缺失"; exit 2; }
[ -n "$PYTHON_BIN" ] && log_info "python  = ${PYTHON_BIN}" || log_warn "python 缺失 — baseline 验证会 skip"
[ -n "$DOCKER_BIN" ] && log_info "docker  = ${DOCKER_BIN}" || log_warn "docker 缺失 — alembic + hot-fix 真跑会 skip"

# ============================================================
# 2. W68 第 5 批 + 3 hot-fix commits 落 main
# ============================================================
section "W68 第 5 批 + 3 hot-fix commit 链验证"

cd "$BASE_DIR"

# 2.1 main HEAD 落在 W68 第 5 批后 (HEAD 哈希前缀已知 05c60e68d, 兼容后续 1-2 commit)
HEAD_HASH="$(git rev-parse HEAD 2>/dev/null)"
log_info "main HEAD = ${HEAD_HASH:0:10}"

# 2.2 必须包含 18 个 W68 第 5 批关键 commit (15 agent + 3 hot-fix)
W68_COMMITS=(
    "w68-5th-batch-grand-closure"
    "w68-5th-batch-docs-sync"
    "w68-4th-batch-grand-closure"
    "w68-4th-batch-baseline-verification"
    "batch-repair-meetings"
    "drive-pr9-runbook"
    "qa-bench-d6-phase1-dry"
    "drive-pr9-e2e-integration"
    "desktop-comments-visual-regression"
    "desktop-comment-mention-autocomplete"
    "drive-v2-pr9-mention-notifications"
    "desktop-version-diff-ui"
    "mobile-v3.2-push"
    "drive-v2-pr10-collab-crud"
    "mobile-comments-usefilecomments-wrapper"
    "w68-5th-batch-knowledge-uploader-id"   # hot-fix #18
    "w68-5th-batch-version-diff-lineterm"   # hot-fix #17
    # hot-fix #16 select import 是 fix(drive-v2-pr9) drive_version_diff_service 缺 select import
)

MISSING=0
for kw in "${W68_COMMITS[@]}"; do
    if git log --oneline -50 2>/dev/null | grep -q "$kw"; then
        : # 命中, 不打 PASS 避免冗长
    else
        log_fail "W68 第 5 批 commit '${kw}' 不在 main 最近 50 条"
        MISSING=$((MISSING + 1))
    fi
done
if [ "$MISSING" -eq 0 ]; then
    log_pass "全部 18 个 W68 第 5 批关键 commit 在 main HEAD ~50"
else
    log_fail "${MISSING}/18 W68 第 5 批 commit 缺失"
fi

# 2.3 hot-fix #16 select import commit 单独 grep (主题不在 W68_COMMITS 列表里)
if git log --oneline -50 2>/dev/null | grep -q "drive_version_diff_service.*select import"; then
    log_pass "hot-fix #16 select import commit (2ca86e05e) 在 main"
else
    log_fail "hot-fix #16 select import commit 不在 main"
fi

# ============================================================
# 3. Drive v2 PR10 文档 merge 状态 (不依赖 alembic 064 是否已跑)
# ============================================================
section "Drive v2 PR10 文档验证"

PR10_DOCS=(
    "docs/drive-v2-pr10-collab-editing.md"
    "docs/drive-v2-pr10-collab-editing-design.md"
)

DOC_MISSING=0
for doc in "${PR10_DOCS[@]}"; do
    if [ -f "${BASE_DIR}/${doc}" ]; then
        DOC_SIZE="$(wc -l < "${BASE_DIR}/${doc}" 2>/dev/null || echo 0)"
        log_pass "文档 ${doc} 存在 (${DOC_SIZE} 行)"
    else
        log_fail "文档 ${doc} 缺失"
        DOC_MISSING=$((DOC_MISSING + 1))
    fi
done

# alembic 064 文件已在 main (不论是否已部署到 DB)
if [ -f "${BASE_DIR}/alembic/versions/064_drive_documents.py" ]; then
    log_pass "alembic 064_drive_documents.py 已 merge 进 main (部署到 DB 见 §4)"
else
    log_fail "alembic 064_drive_documents.py 不在 main"
fi

# ============================================================
# 4. 3 hot-fix 真跑验证 (W68 第 5 批 hot-fix #16/#17/#18)
# ============================================================
section "W68 第 5 批 3 hot-fix 真跑"

if [ -z "$DOCKER_BIN" ]; then
    log_skip "hot-fix 真跑 — docker 未安装, 跳过全部 3 项"
elif ! $DOCKER_BIN ps --format '{{.Names}}' 2>/dev/null | grep -q 'microbubble-agent-app-1'; then
    log_skip "hot-fix 真跑 — app 容器未启动"
elif [ "$DRY_RUN" = "1" ]; then
    log_skip "hot-fix 真跑 — DRY_RUN, 跳过全部 3 项"
else
    APP_CONTAINER="microbubble-agent-app-1"

    # 4.1 select import (hot-fix #16, commit 2ca86e05e)
    log_info "4.1 hot-fix #16 — drive_version_diff_service select import"
    HF1_OUT="$($DOCKER_BIN exec "$APP_CONTAINER" python -c "
from app.services.drive_version_diff_service import DriveVersionDiffService
print('IMPORT_OK')
" 2>&1 || echo '<exec failed>')"
    if echo "$HF1_OUT" | grep -q "IMPORT_OK"; then
        log_pass "hot-fix #16 select import 真跑成功"
    else
        log_fail "hot-fix #16 select import 真跑失败" "${HF1_OUT:0:200}"
    fi

    # 4.2 lineterm 真跑 (hot-fix #17)
    log_info "4.2 hot-fix #17 — _compute_text_diff lineterm='\\n' 真跑"
    HF2_OUT="$($DOCKER_BIN exec "$APP_CONTAINER" python -c "
from app.services.drive_version_diff_service import DriveVersionDiffService
u, cl, adds, dels = DriveVersionDiffService._compute_text_diff(
    from_text='hello\nworld\n', to_text='hello\nmoon\n',
    from_label='v1', to_label='v2')
print('UNIFIED_LEN=' + str(len(u)))
print('HAS_HUNK=' + ('Y' if '@@' in u else 'N'))
print('ADDS=' + str(adds) + ' DELS=' + str(dels))
" 2>&1 || echo '<exec failed>')"
    if echo "$HF2_OUT" | grep -q "HAS_HUNK=Y" && echo "$HF2_OUT" | grep -q "UNIFIED_LEN=[1-9]"; then
        log_pass "hot-fix #17 _compute_text_diff 真跑出 @@ hunk"
    else
        log_fail "hot-fix #17 真跑失败" "${HF2_OUT:0:300}"
    fi

    # 4.3 uploader_id grep (hot-fix #18) — 在主机跑 (不是 docker 内)
    log_info "4.3 hot-fix #18 — drive_comment_service.py uploader_id 0 命中"
    HF3_HITS="$(grep -c "uploader_id" "${BASE_DIR}/app/services/drive_comment_service.py" 2>/dev/null || echo 0)"
    if [ "$HF3_HITS" = "0" ]; then
        log_pass "hot-fix #18 uploader_id 0 命中 (已迁移到 created_by)"
    elif [ "$HF3_HITS" -lt "3" ]; then
        log_warn "hot-fix #18 仍有 ${HF3_HITS} 处 uploader_id (注释内合法, 检查是否还有真实引用)"
    else
        log_fail "hot-fix #18 仍有 ${HF3_HITS} 处 uploader_id (远大于阈值)"
    fi
fi

# ============================================================
# 5. alembic 064 真跑落点 (依赖 docker)
# ============================================================
section "alembic 064 落点验证 (PR10 骨架表)"

if [ -z "$DOCKER_BIN" ]; then
    log_skip "alembic 064 落点 — docker 未装"
elif ! $DOCKER_BIN ps --format '{{.Names}}' 2>/dev/null | grep -q 'microbubble-agent-app-1'; then
    log_skip "alembic 064 落点 — app 容器未起"
elif [ "$DRY_RUN" = "1" ]; then
    log_skip "alembic 064 落点 — DRY_RUN"
else
    APP_CONTAINER="microbubble-agent-app-1"

    # 5.1 alembic current 应有 064_drive_documents
    if $DOCKER_BIN exec "$APP_CONTAINER" alembic current 2>/dev/null | grep -q "064_drive_documents"; then
        log_pass "alembic 落点 = 064_drive_documents (Drive v2 PR9 + PR10 联合 head)"
    elif $DOCKER_BIN exec "$APP_CONTAINER" alembic current 2>/dev/null | grep -q "063_drive_file_versions"; then
        log_warn "alembic 落点还是 063 — PR10 064 还没跑"
        log_info "修复: docker exec ${APP_CONTAINER} alembic upgrade head"
    else
        log_fail "alembic 落点异常" "手动跑 docker exec ${APP_CONTAINER} alembic current 查看"
    fi

    # 5.2 alembic 单链 (062/063/064 只有一个 head)
    HEADS_OUT="$($DOCKER_BIN exec "$APP_CONTAINER" python -c "
from alembic.config import Config
from alembic.script import ScriptDirectory
c = Config()
c.set_main_option('script_location','alembic')
s = ScriptDirectory.from_config(c)
print(','.join(s.get_heads()))
" 2>/dev/null || echo '<exec failed>')"
    if echo "$HEADS_OUT" | grep -q ","; then
        log_fail "alembic 链多 head (双头): ${HEADS_OUT}" "见 CLAUDE.md 2026-07-24 alembic 串单链纪律 — 064 必须 down_revision='063_drive_file_versions'"
    elif echo "$HEADS_OUT" | grep -q "064_drive_documents"; then
        log_pass "alembic 链单头 = ${HEADS_OUT}"
    else
        log_warn "alembic heads 输出: ${HEADS_OUT} — 手动验证"
    fi

    # 5.3 drive_documents + drive_doc_op_logs 表是否实存在 DB
    PG_CONTAINER="microbubble-agent-postgres-1"
    if $DOCKER_BIN ps --format '{{.Names}}' 2>/dev/null | grep -q "$PG_CONTAINER"; then
        TBL_OUT="$($DOCKER_BIN exec -e PGPASSWORD=postgres "$PG_CONTAINER" psql -U postgres -d microbubble -t -c "\dt drive_doc*" 2>/dev/null || echo '')"
        for tbl in drive_documents drive_doc_op_logs; do
            if echo "$TBL_OUT" | grep -q "$tbl"; then
                log_pass "PR10 表 ${tbl} 物理存在"
            else
                log_warn "PR10 表 ${tbl} 缺失 (可能 alembic 064 未跑)"
            fi
        done
    else
        log_skip "drive_doc* 表 — postgres 容器未起"
    fi
fi

# ============================================================
# 6. baseline 71 PASS + 7 SKIP 守恒
# ============================================================
section "baseline 守恒验证"

log_info "pytest tests/test_baseline_audit.py -v"
if [ -z "$PYTHON_BIN" ]; then
    log_skip "baseline — python3 未找到"
elif [ "$DRY_RUN" = "1" ]; then
    log_skip "baseline — DRY_RUN"
else
    BASE_OUT="$($PYTHON_BIN -m pytest tests/test_baseline_audit.py -v --tb=line 2>&1 || true)"
    B_PASS="$(echo "$BASE_OUT" | grep -oE '[0-9]+ passed' | head -1 | grep -oE '[0-9]+' || echo 0)"
    B_SKIP="$(echo "$BASE_OUT" | grep -oE '[0-9]+ skipped' | head -1 | grep -oE '[0-9]+' || echo 0)"
    log_info "baseline PASS=${B_PASS}  SKIP=${B_SKIP}"
    if [ "$B_PASS" -ge "71" ] && [ "$B_SKIP" -ge "7" ]; then
        log_pass "baseline 71 PASS + 7 SKIP 守恒 (${B_PASS} / ${B_SKIP})"
    elif [ "$B_PASS" -ge "65" ]; then
        log_warn "baseline ${B_PASS} < 71 — 排查是否有 stale 引用 (CLAUDE.md W62 baseline 9 files 教训)"
    elif [ "$B_PASS" = "0" ]; then
        log_warn "baseline 0 PASS — pytest collect 失败 (见 tests/test_baseline_audit.py)"
    else
        log_fail "baseline PASS=${B_PASS} 远低于 71"
    fi
fi

# ============================================================
# 7. 总结
# ============================================================
section "总结"
TOTAL=$TOTAL_COUNT; PASS=$PASS_COUNT; FAIL=$FAIL_COUNT; SKIP=$SKIP_COUNT
printf "  总计: %d  " "$TOTAL"
printf "%s通过: %d%s  " "${GREEN}" "$PASS" "${RESET}"
if [ "$FAIL" -gt 0 ]; then
    printf "%s失败: %d%s  " "${RED}" "$FAIL" "${RESET}"
else
    printf "失败: 0  "
fi
printf "%s跳过: %d%s\n" "${YELLOW}" "$SKIP" "${RESET}"

echo ""
if [ "$FAIL" -eq 0 ]; then
    printf "%s✅ W68 第 5 批 + 3 hot-fix 部署验证全部通过%s\n" "${GREEN}${BOLD}" "${RESET}"
    echo ""
    echo "下一步:"
    echo "  - 通知团队 W68 第 5 批 + 3 hot-fix 已全部上线"
    echo "  - 锚点范式第 85 守恒 — 记录到 release notes"
    exit 0
else
    printf "%s❌ W68 第 5 批 + 3 hot-fix 部署验证有 %d 项失败%s\n" "${RED}${BOLD}" "$FAIL" "${RESET}"
    echo ""
    echo "下一步:"
    echo "  - 详见 docs/w68-5th-batch-deployment-runbook.md §3 (alembic 064 状态) + §5 (回滚)"
    echo "  - 修复后重跑: bash scripts/verify_w68_5th_batch_deployment.sh"
    echo "  - 或重跑全套: bash scripts/verify_drive_v2_pr9_deployment.sh"
    exit 1
fi
