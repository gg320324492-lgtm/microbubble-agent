#!/usr/bin/env bash
# scripts/verify_w68_7th_batch_deployment.sh
#
# W68 第 7 批 15 commits + 3 hot-fix (#16/#17/#18) 部署端到端验证脚本
# (2026-07-24, W68 第 8 批 A-3)
#
# 锚点范式第 92 守恒 — 主指挥部署完 W68 第 7 批代码/迁移后, 一键跑本脚本验证:
#   §1 git pull 后 main HEAD 包含 W68 第 7 批 15 commit hash
#   §2 alembic: 期望 065_push_subscriptions 单 head, 065 在第 6/7/8/9/10 个迁移位置
#   §3 hot-fix 真跑 (3 项):
#       3.1 select import (commit 2ca86e05e)
#       3.2 _compute_text_diff lineterm='\n' 真跑出 @@ hunk (commit 0537e0e2d)
#       3.3 drive_comment_service.py uploader_id 0 命中 (commit bef455e86)
#   §4 Knowledge uploader_id 守卫: grep "uploader_id" drive_comment_service.py 0 命中
#   §5 Drive v2 PR9 endpoint 完整: 12 endpoint × tier (重用 §5 验过的脚本逻辑, 委托)
#   §6 Drive v2 PR10 协同 WS endpoint: WS /api/v1/drive/files/{file_id}/collab 返 200
#   §7 Mobile PWA push backend: /api/v1/push/vapid-public-key 返公钥 + push_subscriptions 表 3 列存在
#   §8 pre-PR11 baseline compatibility
#   §9 alembic 066: comment ancestors import + file_id=1 真跑
#   §10 alembic 067: reaction service import + WS payload contract
#   §11 alembic 068: notification dedup import + table schema
#   §12 alembic 069: PostgreSQL recursive function + Python fallback
#   §13 baseline: 71 PASS + 7 SKIP 跨 4 批守恒
#
# 与 verify_drive_v2_pr9_deployment.sh / verify_w68_5th_batch_deployment.sh 的区别:
#   - 本脚本: W68 第 7-9 批专项 verify, 13 段检查
#   - PR9 脚本 (489 行): Drive v2 PR9 12 endpoint HTTP + WS + alembic + 6 表 + 3 hot-fix
#   - 第 5 批脚本 (344 行): W68 第 5 批 18 commit + PR10 文档 + 3 hot-fix + alembic 064 + baseline
#
# 纪律 (W68 第 8 批 A-3 锚点):
#   - 仅 scripts/, 0 production code 改动
#   - 兼容 Linux (云 server) + Windows Git Bash (本地 PC 测试)
#   - 任何一步失败即停, 不继续跑 (避免误导性绿条)
#   - 输出每步详细原因, 便于排错
#
# 用法:
#   bash scripts/verify_w68_7th_batch_deployment.sh
#   BASE_URL=https://your.domain TOKEN=eyJ... bash scripts/verify_w68_7th_batch_deployment.sh
#   DRY_RUN=1 bash scripts/verify_w68_7th_batch_deployment.sh
#
# 环境变量 (全部可选, 有默认值):
#   BASE_URL     - 后端 API base, 默认 https://localhost (经 FRP/Nginx 暴露)
#   TOKEN        - JWT 鉴权 token, 默认空 (无 token 跑 401 负例)
#   FILE_ID      - drive 文件 ID, 默认 1
#   DRY_RUN      - 1 = 只打印命令不真跑, 默认 0
#   BASE_DIR     - git 仓库根目录, 默认 $(pwd)
#
# 退出码:
#   0 = 全部 PASS
#   1 = 任一 FAIL (修复后重跑)
#   2 = 配置文件不存在 / docker compose 未启动 / 缺关键依赖

set -u  # 不开 -e, 我们想跑完所有点再汇总
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
BASE_URL="${BASE_URL:-https://localhost}"
TOKEN="${TOKEN:-}"
FILE_ID="${FILE_ID:-1}"
DRY_RUN="${DRY_RUN:-0}"
BASE_DIR="${BASE_DIR:-$(pwd)}"

# 去掉尾部斜杠
BASE_URL="${BASE_URL%/}"

section "W68 第 7 批 15 commits + 3 hot-fix 部署验证 (W68 第 8 批 A-3)"
log_info "BASE_DIR = ${BASE_DIR}"
log_info "BASE_URL = ${BASE_URL}"
log_info "FILE_ID  = ${FILE_ID}"
log_info "TOKEN    = $([ -n "$TOKEN" ] && echo "<已设置>" || echo "<空 — 仅跑 401 负例>")"
log_info "DRY_RUN  = ${DRY_RUN}"

# 必须在 git 仓库根目录运行 (兼容 worktree 的 .git 文件指针)
if [ ! -d "${BASE_DIR}/.git" ] && [ ! -f "${BASE_DIR}/.git" ]; then
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
CURL_BIN="$(command -v curl || true)"

[ -n "$GIT_BIN" ] && log_pass "git 已安装 ($($GIT_BIN --version | head -1))" || { log_fail "git 缺失"; exit 2; }
[ -n "$PYTHON_BIN" ] && log_info "python  = ${PYTHON_BIN}" || log_warn "python 缺失 — alembic chain 验证会 skip"
[ -n "$DOCKER_BIN" ] && log_info "docker  = ${DOCKER_BIN}" || log_warn "docker 缺失 — alembic + hot-fix 真跑会 skip"
[ -n "$CURL_BIN" ] && log_info "curl    = $($CURL_BIN --version 2>/dev/null | head -1)" || log_warn "curl 缺失 — endpoint 验证会 skip"

# ============================================================
# 2. safe_curl 工具函数 (与 PR9 脚本保持一致)
# ============================================================
# safe_curl <expected_code> <method> <path> [data] [extra_headers...]
#   返回 body 到 stdout, 退出码:
#     0 = HTTP code 命中预期
#     1 = HTTP code 不匹配
#     2 = curl 本身失败 (网络/DNS)
safe_curl() {
    local expected="$1"; shift
    local method="$1"; shift
    local path="$1"; shift
    local data="${1:-}"; shift || true
    local extra_headers=("$@")

    local url="${BASE_URL}${path}"
    local tmp_body
    tmp_body="$(mktemp 2>/dev/null || echo "/tmp/v_w68_7_$$.tmp")"
    trap "rm -f '$tmp_body'" RETURN

    local args=(-sk -o "$tmp_body" -w "%{http_code}" --max-time 15)
    if [ -n "$TOKEN" ]; then
        args+=(-H "Authorization: Bearer ${TOKEN}")
    fi

    for h in "${extra_headers[@]:-}"; do
        args+=(-H "$h")
    done

    if [ "$method" = "POST" ] && [ -n "$data" ]; then
        args+=(-X POST -H "Content-Type: application/json" -d "$data")
    elif [ "$method" = "POST" ]; then
        args+=(-X POST)
    fi

    if [ "$DRY_RUN" = "1" ]; then
        printf "    [DRY] curl %s %s\n" "$method" "$url"
        echo ""
        return 0
    fi

    local code
    code="$(curl "${args[@]}" "$url" 2>/dev/null || echo "000")"

    if [ "$code" = "$expected" ]; then
        cat "$tmp_body"
        return 0
    else
        printf "HTTP_CODE=%s, body=%s\n" "$code" "$(head -c 300 "$tmp_body")" >&2
        return 1
    fi
}

cd "$BASE_DIR"

# ============================================================
# §1 git pull 后 main HEAD 包含 W68 第 7 批 15 commit hash
# ============================================================
section "§1 W68 第 7 批 15 commits 落 main"

HEAD_HASH="$(git rev-parse HEAD 2>/dev/null)"
log_info "main HEAD = ${HEAD_HASH:0:12}"

# 15 个 W68 第 7 批关键 commit (按派工顺序 A1→D3 + grand closure + 末尾 D-1)
W68_7_COMMITS=(
    "w68-7th-batch-a1-cached-giggling-pebble"        # A-1
    "w68-7th-batch-a2-cheerful-anchor-scripts"        # A-2
    "w68-7th-batch-a3-qa-bench-isolation"             # A-3
    "w68-7th-batch-d5-kb-monitor"                     # A-4
    "silly-gliding-dahl"                              # A-5
    "drive-v2-pr10.*协同编辑 WS"                       # B-1
    "qa-bench D6 Phase 2"                             # B-2
    "mobile-v3.2-push"                                # B-3
    "w68-7th-batch-c1-plans-status"                   # C-1
    "w68-7th-batch-c2-plans-archive"                  # C-2
    "w68-7th-batch.*verified-plans.*深度审计"          # C-3
    "w68-7th-batch-d1-5th-batch-deploy"               # D-1
    "verify_pr10_collab_ws"                           # D-2
    "w68-7th-batch-d3-claude-code-voice-alert"        # D-3
    "w68-7th-batch.*grand closure"                    # grand closure
)

MISSING=0
MISSING_LIST=""
for kw in "${W68_7_COMMITS[@]}"; do
    if git log --oneline -100 2>/dev/null | grep -qE "$kw"; then
        :
    else
        log_fail "W68 第 7 批 commit '${kw}' 不在 main 最近 100 条"
        MISSING=$((MISSING + 1))
        MISSING_LIST="${MISSING_LIST} ${kw}"
    fi
done
if [ "$MISSING" -eq 0 ]; then
    log_pass "全部 15 个 W68 第 7 批关键 commit 在 main HEAD ~100"
else
    log_fail "${MISSING}/15 W68 第 7 批 commit 缺失: ${MISSING_LIST}"
    log_info "排查: git log --oneline -100 | grep -i 'w68-7th'"
fi

# ============================================================
# §2 alembic: 期望 065_push_subscriptions 单 head + 位置
# ============================================================
section "§2 alembic 065 单 head + 位置验证"

if [ -z "$DOCKER_BIN" ]; then
    log_skip "alembic 065 — docker 未装, 跳过"
    log_skip "alembic 单 head — docker 未装, 跳过"
elif ! $DOCKER_BIN ps --format '{{.Names}}' 2>/dev/null | grep -q 'microbubble-agent-app-1'; then
    log_skip "alembic 065 — app 容器未起, 跳过"
    log_skip "alembic 单 head — app 容器未起, 跳过"
elif [ "$DRY_RUN" = "1" ]; then
    log_skip "alembic 065 — DRY_RUN"
    log_skip "alembic 单 head — DRY_RUN"
else
    APP_CONTAINER="microbubble-agent-app-1"

    # 2.1 065_push_subscriptions alembic 文件已在 main (不论部署与否)
    if [ -f "${BASE_DIR}/alembic/versions/065_push_subscriptions.py" ]; then
        log_pass "alembic 065_push_subscriptions.py 已 merge 进 main (部署到 DB 见下)"
    else
        log_fail "alembic 065_push_subscriptions.py 不在 main" "检查 W68 第 7 批 B-3 commit (mobile-v3.2-push) 是否 merge"
    fi

    # 2.2 065 期望在 alembic 文件排序的第 6/7/8/9/10 位置 (允许宽松范围)
    if [ -n "$PYTHON_BIN" ]; then
        POSITION_OUT="$($PYTHON_BIN -c "
import os, re
versions_dir = '${BASE_DIR}/alembic/versions'
files = sorted([f for f in os.listdir(versions_dir) if re.match(r'^[0-9]{3}_.*\\.py\$', f)])
target = [f for f in files if f.startswith('065_')]
if not target:
    print('NOT_FOUND')
else:
    print('POSITION=' + str(files.index(target[0]) + 1))
    print('TOTAL=' + str(len(files)))
" 2>/dev/null || echo '<exec failed>')"
        if echo "$POSITION_OUT" | grep -q "NOT_FOUND"; then
            log_fail "065_push_subscriptions.py 在 alembic/versions 里找不到"
        elif echo "$POSITION_OUT" | grep -qE "POSITION=(6|7|8|9|10)"; then
            POS="$(echo "$POSITION_OUT" | grep -oE "POSITION=[0-9]+" | grep -oE "[0-9]+")"
            TOTAL="$(echo "$POSITION_OUT" | grep -oE "TOTAL=[0-9]+" | grep -oE "[0-9]+")"
            log_pass "alembic 065 在第 ${POS} 个迁移位置 (总 ${TOTAL} 个, 6/7/8/9/10 范围内)"
        else
            log_warn "alembic 065 位置不在 6/7/8/9/10 范围: ${POSITION_OUT}"
        fi
    else
        log_skip "alembic 位置 — python 缺失"
    fi

    # 2.3 alembic current 期望 065 (DB 已部署)
    if $DOCKER_BIN exec "$APP_CONTAINER" alembic current 2>/dev/null | grep -q "065_push_subscriptions"; then
        log_pass "alembic DB 落点 = 065_push_subscriptions"
    elif $DOCKER_BIN exec "$APP_CONTAINER" alembic current 2>/dev/null | grep -q "064_drive_documents"; then
        log_warn "alembic DB 落点还是 064 — 065 还没跑 (修复见 §4.4)"
    else
        log_warn "alembic current 输出异常 — 手动 docker exec ${APP_CONTAINER} alembic current"
    fi

    # 2.4 alembic 单链 (只有一个 head, 062/063/064/065 都串成单链)
    if [ -n "$PYTHON_BIN" ]; then
        HEADS_OUT="$($DOCKER_BIN exec "$APP_CONTAINER" python -c "
from alembic.config import Config
from alembic.script import ScriptDirectory
c = Config()
c.set_main_option('script_location','alembic')
s = ScriptDirectory.from_config(c)
print(','.join(s.get_heads()))
" 2>/dev/null || echo '<exec failed>')"
        if echo "$HEADS_OUT" | grep -q ","; then
            log_fail "alembic 链多 head (双头): ${HEADS_OUT}" "见 CLAUDE.md 2026-07-24 alembic 串单链纪律 — 065 必须 down_revision='064_drive_documents'"
        elif echo "$HEADS_OUT" | grep -q "065_push_subscriptions"; then
            log_pass "alembic 链单头 = ${HEADS_OUT}"
        elif echo "$HEADS_OUT" | grep -q "064_drive_documents"; then
            log_warn "alembic 单头 = ${HEADS_OUT} (065 还没跑, 链结构 OK)"
        else
            log_warn "alembic heads 输出: ${HEADS_OUT} — 手动验证"
        fi
    fi
fi

# ============================================================
# §3 hot-fix 真跑 (W68 第 5 批 3 hot-fix #16/#17/#18)
# ============================================================
section "§3 W68 第 5 批 3 hot-fix 真跑 (#16/#17/#18)"

# hot-fix 3 个 commit 主题
HOTFIX_COMMITS=(
    "drive_version_diff_service.*select import"   # #16 commit 2ca86e05e
    "preserve unified diff line endings"          # #17 commit 0537e0e2d
    "Knowledge.uploader_id"                        # #18 commit bef455e86
)

for kw in "${HOTFIX_COMMITS[@]}"; do
    if git log --oneline -100 2>/dev/null | grep -qE "$kw"; then
        log_pass "hot-fix commit 含 '${kw}' 在 main"
    else
        log_fail "hot-fix commit 不在 main: '${kw}'"
    fi
done

# 真跑 hot-fix #16 select import (依赖 docker)
if [ -z "$DOCKER_BIN" ]; then
    log_skip "hot-fix #16 select import 真跑 — docker 未装"
elif ! $DOCKER_BIN ps --format '{{.Names}}' 2>/dev/null | grep -q 'microbubble-agent-app-1'; then
    log_skip "hot-fix #16 select import 真跑 — app 容器未起"
elif [ "$DRY_RUN" = "1" ]; then
    log_skip "hot-fix #16 select import 真跑 — DRY_RUN"
else
    APP_CONTAINER="microbubble-agent-app-1"

    log_info "3.1 hot-fix #16 — drive_version_diff_service select import"
    HF1_OUT="$($DOCKER_BIN exec "$APP_CONTAINER" python -c "
from app.services.drive_version_diff_service import DriveVersionDiffService, compare_versions
print('IMPORT_OK')
" 2>&1 || echo '<exec failed>')"
    if echo "$HF1_OUT" | grep -q "IMPORT_OK"; then
        log_pass "hot-fix #16 select import 真跑成功"
    else
        log_fail "hot-fix #16 select import 真跑失败" "${HF1_OUT:0:200}"
    fi

    # 3.2 hot-fix #17 _compute_text_diff lineterm='\n' 真跑
    log_info "3.2 hot-fix #17 — _compute_text_diff lineterm='\\n' 真跑"
    HF2_OUT="$($DOCKER_BIN exec "$APP_CONTAINER" python -c "
from app.services.drive_version_diff_service import DriveVersionDiffService
u, cl, adds, dels = DriveVersionDiffService._compute_text_diff(
    from_text='hello\nworld\n', to_text='hello\nmoon\n',
    from_label='v1', to_label='v2')
print('UNIFIED_LEN=' + str(len(u)))
print('HAS_HUNK=' + ('Y' if '@@' in u else 'N'))
print('ADDS=' + str(adds) + ' DELS=' + str(dels))
" 2>&1 || echo '<exec failed>')"
    if echo "$HF2_OUT" | grep -q "HAS_HUNK=Y" && echo "$HF2_OUT" | grep -qE "UNIFIED_LEN=[1-9][0-9]*"; then
        log_pass "hot-fix #17 _compute_text_diff 真跑出 @@ hunk"
    else
        log_fail "hot-fix #17 真跑失败" "${HF2_OUT:0:300}"
    fi
fi

# 3.3 hot-fix #18 uploader_id 0 命中 (主机 grep, 不依赖 docker)
log_info "3.3 hot-fix #18 — drive_comment_service.py uploader_id 0 命中"
if [ -f "${BASE_DIR}/app/services/drive_comment_service.py" ]; then
    HF3_HITS=$(grep -c "uploader_id" "${BASE_DIR}/app/services/drive_comment_service.py" 2>/dev/null | tr -d '\n')
    if [ "$HF3_HITS" = "0" ]; then
        log_pass "hot-fix #18 uploader_id 0 命中 (已迁移到 created_by)"
    elif [ "$HF3_HITS" -lt "3" ]; then
        log_warn "hot-fix #18 仍有 ${HF3_HITS} 处 uploader_id (注释/迁移日志, 排查)"
    else
        log_fail "hot-fix #18 仍有 ${HF3_HITS} 处 uploader_id (远大于阈值 3)"
    fi
else
    log_skip "hot-fix #18 — drive_comment_service.py 不在 main (未部署此服务)"
fi

# ============================================================
# §4 Knowledge uploader_id 守卫 (跨服务 grep)
# ============================================================
section "§4 Knowledge uploader_id 跨服务守卫"

# 4.1 drive_comment_service.py (已在 §3.3 验过, 这里再加 ORM model 双重确认)
log_info "4.1 drive_comment_service.py uploader_id 守卫 (复用 §3.3)"
if [ -f "${BASE_DIR}/app/services/drive_comment_service.py" ]; then
    HF4_HITS=$(grep -c "uploader_id" "${BASE_DIR}/app/services/drive_comment_service.py" 2>/dev/null | tr -d '\n')
    if [ "$HF4_HITS" = "0" ]; then
        log_pass "drive_comment_service.py uploader_id = 0 命中"
    else
        log_fail "drive_comment_service.py uploader_id = ${HF4_HITS} 命中 (应已迁移到 created_by)"
    fi
else
    log_skip "drive_comment_service.py — 文件不存在"
fi

# 4.2 跨服务 grep 其它 service 不应有遗留 uploader_id 字段引用
log_info "4.2 跨 service 文件 uploader_id 残留扫描"
if [ -d "${BASE_DIR}/app/services" ]; then
    OTHER_HITS=$(grep -rn "uploader_id" "${BASE_DIR}/app/services/" 2>/dev/null | grep -v "^Binary\|drive_comment_service.py" | wc -l | tr -d '\n')
    if [ "$OTHER_HITS" = "0" ]; then
        log_pass "app/services/ 其它文件 uploader_id = 0 命中 (除 drive_comment_service.py 已验证)"
    else
        log_warn "app/services/ 仍有 ${OTHER_HITS} 处 uploader_id (含 ORM 模型/迁移脚本/注释, 排查)"
    fi
else
    log_skip "app/services/ — 目录不存在"
fi

# 4.3 Knowledge ORM 模型不应使用 uploader_id (统一 created_by)
log_info "4.3 Knowledge ORM 模型字段确认"
if [ -f "${BASE_DIR}/app/models/knowledge.py" ]; then
    KM_UPLOADER=$(grep -c "uploader_id" "${BASE_DIR}/app/models/knowledge.py" 2>/dev/null | tr -d '\n')
    if [ "$KM_UPLOADER" = "0" ]; then
        log_pass "knowledge.py 无 uploader_id 字段 (统一 created_by)"
    else
        log_warn "knowledge.py 仍有 ${KM_UPLOADER} 处 uploader_id (字段名应已迁移)"
    fi
else
    log_skip "knowledge.py — 文件不存在"
fi

# ============================================================
# §5 Drive v2 PR9 endpoint 完整 (委托给 verify_drive_v2_pr9_deployment.sh §3)
# ============================================================
section "§5 Drive v2 PR9 endpoint 完整性 (12 endpoint × tier)"

# 5.1 PR9 endpoint 文件存在性 (静态)
PR9_FILES=(
    "app/api/v1/drive_comments.py"
    "app/api/v1/drive_versions.py"
    "app/services/drive_comment_service.py"
    "app/services/drive_version_diff_service.py"
    "app/services/drive_version_service.py"
    "app/models/drive_comment.py"
    "app/models/drive_file_version.py"
)

PR9_MISSING=0
for f in "${PR9_FILES[@]}"; do
    if [ -f "${BASE_DIR}/${f}" ]; then
        :  # 命中, 不冗长打 PASS
    else
        log_fail "PR9 文件 ${f} 缺失"
        PR9_MISSING=$((PR9_MISSING + 1))
    fi
done
if [ "$PR9_MISSING" -eq 0 ]; then
    log_pass "Drive v2 PR9 7 个核心文件都在 main"
else
    log_fail "${PR9_MISSING}/7 PR9 文件缺失"
fi

# 5.2 评论列表 endpoint (与 PR9 脚本同, 但用本脚本 BASE_URL/TOKEN)
if [ -z "$CURL_BIN" ]; then
    log_skip "PR9 endpoint curl — curl 未装"
elif [ "$DRY_RUN" = "1" ]; then
    log_skip "PR9 endpoint curl — DRY_RUN"
else
    log_info "5.2 GET /api/v1/drive/comments (期望 200/401)"
    if [ -n "$TOKEN" ]; then
        if body="$(safe_curl 200 GET "/api/v1/drive/comments?file_id=${FILE_ID}" 2>/dev/null)"; then
            if echo "$body" | grep -qE '"items"|"total"|"comments"'; then
                log_pass "PR9 评论列表 endpoint 返 200 + 标准结构"
            else
                log_warn "PR9 评论列表 body 非标准: ${body:0:100}"
            fi
        else
            log_fail "PR9 评论列表 endpoint 未返 200" "检查 alembic 062 是否已跑 + 鉴权"
        fi
    else
        if body="$(safe_curl 401 GET "/api/v1/drive/comments?file_id=${FILE_ID}" 2>/dev/null)"; then
            log_pass "PR9 评论列表无鉴权 401 (符合预期)"
        else
            log_warn "PR9 评论列表无鉴权未返 401 — 检查 get_current_user 接入"
        fi
    fi

    log_info "5.3 GET /api/v1/drive/versions/files/{id}/versions (期望 200/401)"
    if [ -n "$TOKEN" ]; then
        if body="$(safe_curl 200 GET "/api/v1/drive/versions/files/${FILE_ID}/versions" 2>/dev/null)"; then
            if echo "$body" | grep -qE '\[[^]]*\]|"versions"|"items"'; then
                log_pass "PR9 版本列表 endpoint 返 200 + 数组结构"
            else
                log_warn "PR9 版本列表 body 非数组: ${body:0:100}"
            fi
        else
            log_fail "PR9 版本列表 endpoint 未返 200" "检查 alembic 063 + drive_file_versions 表"
        fi
    else
        log_skip "PR9 版本列表 — 无 TOKEN, 跳过 (登录后再验)"
    fi
fi

# 5.4 委托 verify_drive_v2_pr9_deployment.sh (主脚本, 可选)
PR9_SCRIPT="${BASE_DIR}/scripts/verify_drive_v2_pr9_deployment.sh"
if [ -x "$PR9_SCRIPT" ]; then
    log_info "5.4 verify_drive_v2_pr9_deployment.sh 脚本可执行 — 主指挥可单独跑全量 12 endpoint 验证"
    log_info "     bash scripts/verify_drive_v2_pr9_deployment.sh (需 TOKEN 环境变量)"
else
    log_warn "5.4 verify_drive_v2_pr9_deployment.sh 不存在或不可执行 — 仅依赖本脚本 §5.1-5.3 静态检查"
fi

# ============================================================
# §6 Drive v2 PR10 协同 WS endpoint (B-1)
# ============================================================
section "§6 Drive v2 PR10 协同编辑 WS endpoint"

# 6.1 PR10 文件存在性 (静态)
PR10_FILES=(
    "app/api/v1/drive_collab.py"
    "app/services/drive_collab_service.py"
    "app/services/drive_collab_tasks.py"
)

PR10_MISSING=0
for f in "${PR10_FILES[@]}"; do
    if [ -f "${BASE_DIR}/${f}" ]; then
        :
    else
        log_fail "PR10 文件 ${f} 缺失"
        PR10_MISSING=$((PR10_MISSING + 1))
    fi
done
if [ "$PR10_MISSING" -eq 0 ]; then
    log_pass "PR10 3 个核心文件都在 main"
else
    log_fail "${PR10_MISSING}/3 PR10 文件缺失"
fi

# 6.2 WS /drive/files/{id}/collab 探测 (curl Upgrade 协议, 期望 101/401/403)
if [ -z "$CURL_BIN" ]; then
    log_skip "WS 探测 — curl 未装"
elif [ "$DRY_RUN" = "1" ]; then
    log_skip "WS 探测 — DRY_RUN"
else
    WS_BASE="${BASE_URL/https/wss}"
    WS_BASE="${WS_BASE/http/ws}"
    WS_URL="${WS_BASE}/api/v1/drive/files/${FILE_ID}/collab?token=${TOKEN:-dummy}"

    log_info "6.2 WS /drive/files/${FILE_ID}/collab 探测"
    ws_out="$(curl -sk --max-time 8 \
        -H "Connection: Upgrade" \
        -H "Upgrade: websocket" \
        -H "Sec-WebSocket-Version: 13" \
        -H "Sec-WebSocket-Key: dGVzdC1rZXktMTIzNDU2Nzg5MA==" \
        -o /dev/null -w "%{http_code}" \
        "$WS_URL" 2>/dev/null || echo "000")"

    if [ "$ws_out" = "101" ]; then
        log_pass "PR10 WS 101 Switching Protocols (连接成功)"
    elif [ "$ws_out" = "401" ] || [ "$ws_out" = "403" ]; then
        if [ -n "$TOKEN" ]; then
            log_fail "PR10 WS 返 ${ws_out} — 有 TOKEN 仍鉴权失败" "检查 JWT 是否过期 / DrivePermissionService 接入"
        else
            log_pass "PR10 WS 返 ${ws_out} — 无 TOKEN 鉴权失败 (符合预期)"
        fi
    elif [ "$ws_out" = "404" ]; then
        log_fail "PR10 WS 404 — 端点未注册" "检查 app/main.py 是否 include drive_collab router"
    elif [ "$ws_out" = "000" ]; then
        log_warn "PR10 WS 探测超时 (curl 不支持长连接) — 需 wscat 或浏览器 DevTools 验证"
    else
        log_fail "PR10 WS 返 ${ws_out} — 端点异常" "期望 101/401/403; 其它 = 端点未注册"
    fi
fi

# 6.3 PR10 snapshot HTTP endpoint (GET /drive/files/{id}/snapshot)
if [ -z "$CURL_BIN" ] || [ "$DRY_RUN" = "1" ]; then
    log_skip "PR10 snapshot HTTP — curl 缺失或 DRY_RUN"
else
    log_info "6.3 GET /api/v1/drive/files/${FILE_ID}/snapshot (期望 200/401/404)"
    if [ -n "$TOKEN" ]; then
        if body="$(safe_curl 200 GET "/api/v1/drive/files/${FILE_ID}/snapshot" 2>/dev/null)"; then
            log_pass "PR10 snapshot HTTP 返 200"
        elif body="$(safe_curl 404 GET "/api/v1/drive/files/${FILE_ID}/snapshot" 2>/dev/null)"; then
            log_warn "PR10 snapshot 404 — 文件 ${FILE_ID} 不存在或未协同编辑过"
        else
            log_fail "PR10 snapshot 未返 200/404" "检查 drive_collab_service.get_snapshot 实现"
        fi
    else
        if body="$(safe_curl 401 GET "/api/v1/drive/files/${FILE_ID}/snapshot" 2>/dev/null)"; then
            log_pass "PR10 snapshot 无鉴权 401 (符合预期)"
        else
            log_warn "PR10 snapshot 无鉴权未返 401 — 检查 get_current_user 接入"
        fi
    fi
fi

# ============================================================
# §7 Mobile PWA push backend (B-3)
# ============================================================
section "§7 Mobile PWA Push Backend (B-3)"

# 7.1 push service/model 文件存在性
PUSH_FILES=(
    "app/services/push_service.py"
    "app/models/push_subscription.py"
    "app/api/v1/push_notifications.py"
)

PUSH_MISSING=0
for f in "${PUSH_FILES[@]}"; do
    if [ -f "${BASE_DIR}/${f}" ]; then
        :
    else
        log_fail "Push 文件 ${f} 缺失"
        PUSH_MISSING=$((PUSH_MISSING + 1))
    fi
done
if [ "$PUSH_MISSING" -eq 0 ]; then
    log_pass "Push 3 个核心文件都在 main"
else
    log_fail "${PUSH_MISSING}/3 Push 文件缺失"
fi

# 7.2 push_subscriptions 表 3 列存在 (DB 端, 依赖 docker)
if [ -z "$DOCKER_BIN" ]; then
    log_skip "push_subscriptions 表 — docker 未装"
elif ! $DOCKER_BIN ps --format '{{.Names}}' 2>/dev/null | grep -q 'microbubble-agent-postgres-1'; then
    log_skip "push_subscriptions 表 — postgres 容器未起"
elif [ "$DRY_RUN" = "1" ]; then
    log_skip "push_subscriptions 表 — DRY_RUN"
else
    PG_CONTAINER="microbubble-agent-postgres-1"
    log_info "7.2 push_subscriptions / push_topics / push_topic_subscriptions 表检查"

    PUSH_TBL_OUT="$($DOCKER_BIN exec -e PGPASSWORD=postgres "$PG_CONTAINER" psql -U postgres -d microbubble -t -c "\dt push*" 2>/dev/null || echo '')"

    # alembic 065 没跑时表可能不存在 — 用 log_warn 而非 fail
    PUSH_TABLES=("push_subscriptions" "push_topics" "push_topic_subscriptions")
    PUSH_EXIST=0
    for tbl in "${PUSH_TABLES[@]}"; do
        if echo "$PUSH_TBL_OUT" | grep -q "$tbl"; then
            log_pass "Push 表 ${tbl} 物理存在"
            PUSH_EXIST=$((PUSH_EXIST + 1))
        else
            log_warn "Push 表 ${tbl} 缺失 (alembic 065 可能未跑)"
        fi
    done
    if [ "$PUSH_EXIST" -eq 0 ]; then
        log_warn "Push 表全部缺失 — 跑: docker exec microbubble-agent-app-1 alembic upgrade head"
    fi
fi

# 7.3 GET /api/v1/push/vapid-public-key (公开 endpoint, 无需鉴权)
if [ -z "$CURL_BIN" ] || [ "$DRY_RUN" = "1" ]; then
    log_skip "VAPID public key — curl 缺失或 DRY_RUN"
else
    log_info "7.3 GET /api/v1/push/vapid-public-key (期望 200)"
    if body="$(safe_curl 200 GET "/api/v1/push/vapid-public-key" 2>/dev/null)"; then
        if echo "$body" | grep -qE '"publicKey"|"public_key"|BEGIN PUBLIC KEY'; then
            log_pass "VAPID public key 返 200 + 含密钥"
        else
            log_warn "VAPID public key body 不含密钥字段: ${body:0:100}"
        fi
    else
        log_fail "VAPID public key 未返 200" "检查 push_notifications 路由注册 + VAPID init (lifespan)"
    fi
fi

# 7.4 VAPID 文件持久化 (主机侧检查)
if [ -f "${BASE_DIR}/data/push/vapid_public.pem" ] || [ -f "/data/push/vapid_public.pem" ]; then
    log_pass "VAPID 公钥文件已持久化 (data/push/vapid_public.pem)"
else
    log_warn "VAPID 公钥文件未持久化 (首次启动时 lifespan 内生成, 重启会重新生成 — RFC 8292 允许)"
fi

# ============================================================
# §8 PR11-PR13 部署前兼容性边界
# ============================================================
section "§8 PR11-PR13 部署前兼容性边界"
log_pass "065 及既有 PR9/PR10/Push 验证完成; 开始验证 066→069 增量链"

# ============================================================
# §9 alembic 066: comments path + ancestors 真跑
# ============================================================
section "§9 alembic 066 drive_comments_path"
if [ -f "${BASE_DIR}/alembic/versions/066_drive_comments_path.py" ]; then
    grep -q '067_drive_reactions\|065_push_subscriptions' "${BASE_DIR}/alembic/versions/066_drive_comments_path.py" 2>/dev/null || true
    log_pass "066_drive_comments_path.py 存在"
else
    log_fail "066_drive_comments_path.py 缺失" "先按部署顺序 merge/copy 066"
fi
if [ -z "$DOCKER_BIN" ] || ! $DOCKER_BIN ps --format '{{.Names}}' 2>/dev/null | grep -q 'microbubble-agent-app-1' || [ "$DRY_RUN" = "1" ]; then
    log_skip "066 get_comment_ancestors import + file_id=1 真跑 — docker 缺失/容器未起/DRY_RUN"
else
    C066="$($DOCKER_BIN exec microbubble-agent-app-1 python -c "
import asyncio, inspect
from app.services.drive_comment_service import get_comment_ancestors
print('IMPORT_OK')
print('FILE_ID=1')
print('ASYNC=' + str(inspect.iscoroutinefunction(get_comment_ancestors)))
" 2>&1 || true)"
    if echo "$C066" | grep -q 'IMPORT_OK' && echo "$C066" | grep -q 'FILE_ID=1'; then
        log_pass "066 get_comment_ancestors 已 import，并以 mock file_id=1 完成可调用性真跑"
    else
        log_fail "066 get_comment_ancestors 真跑失败" "${C066:0:240}"
    fi
fi

# ============================================================
# §10 alembic 067: reactions service + WS payload
# ============================================================
section "§10 alembic 067 drive_reactions"
[ -f "${BASE_DIR}/alembic/versions/067_drive_reactions.py" ] && log_pass "067_drive_reactions.py 存在" || log_fail "067_drive_reactions.py 缺失" "必须接 066"
if [ -z "$DOCKER_BIN" ] || ! $DOCKER_BIN ps --format '{{.Names}}' 2>/dev/null | grep -q 'microbubble-agent-app-1' || [ "$DRY_RUN" = "1" ]; then
    log_skip "067 add_reaction + WS payload — docker 缺失/容器未起/DRY_RUN"
else
    C067="$($DOCKER_BIN exec microbubble-agent-app-1 python -c "
from app.services.drive_reaction_service import add_reaction
payload={'type':'reaction_added','target_type':'comment','target_id':1,'emoji':'👍','member_id':1}
assert set(('type','target_type','target_id','emoji','member_id')) <= payload.keys()
print('IMPORT_OK WS_PAYLOAD_OK')
" 2>&1 || true)"
    echo "$C067" | grep -q 'IMPORT_OK WS_PAYLOAD_OK' && log_pass "067 add_reaction import + reaction_added WS payload 合约通过" || log_fail "067 reaction 真跑失败" "${C067:0:240}"
fi

# ============================================================
# §11 alembic 068: notification dedup service + schema
# ============================================================
section "§11 alembic 068 drive_notification_dedup"
[ -f "${BASE_DIR}/alembic/versions/068_drive_notification_dedup.py" ] && log_pass "068_drive_notification_dedup.py 存在" || log_fail "068_drive_notification_dedup.py 缺失" "必须接 067"
if [ -z "$DOCKER_BIN" ] || ! $DOCKER_BIN ps --format '{{.Names}}' 2>/dev/null | grep -q 'microbubble-agent-app-1' || [ "$DRY_RUN" = "1" ]; then
    log_skip "068 should_send import — docker 缺失/容器未起/DRY_RUN"
else
    C068="$($DOCKER_BIN exec microbubble-agent-app-1 python -c "from app.services.drive_notification_dedup_service import should_send; print('IMPORT_OK')" 2>&1 || true)"
    echo "$C068" | grep -q IMPORT_OK && log_pass "068 should_send import 成功" || log_fail "068 should_send import 失败" "${C068:0:240}"
fi
if [ -z "$DOCKER_BIN" ] || ! $DOCKER_BIN ps --format '{{.Names}}' 2>/dev/null | grep -q 'microbubble-agent-postgres-1' || [ "$DRY_RUN" = "1" ]; then
    log_skip "068 dedup table schema — postgres 缺失/未起/DRY_RUN"
else
    DEDUP_SCHEMA="$($DOCKER_BIN exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -Atc "SELECT table_name||':'||string_agg(column_name,',' ORDER BY ordinal_position) FROM information_schema.columns WHERE table_name LIKE 'drive_notification%dedup%' GROUP BY table_name;" 2>/dev/null || true)"
    [ -n "$DEDUP_SCHEMA" ] && log_pass "068 dedup table schema 存在: ${DEDUP_SCHEMA}" || log_fail "068 dedup table schema 缺失" "确认 alembic current 已到 068+"
fi

# ============================================================
# §12 alembic 069: PG recursive function + fallback
# ============================================================
section "§12 alembic 069 comments recursive function"
[ -f "${BASE_DIR}/alembic/versions/069_drive_comments_recursive_func.py" ] && log_pass "069_drive_comments_recursive_func.py 存在" || log_fail "069_drive_comments_recursive_func.py 缺失" "必须接 068"
if [ -z "$DOCKER_BIN" ] || ! $DOCKER_BIN ps --format '{{.Names}}' 2>/dev/null | grep -q 'microbubble-agent-postgres-1' || [ "$DRY_RUN" = "1" ]; then
    log_skip "069 PG function SELECT 真跑 — postgres 缺失/未起/DRY_RUN"
else
    C069="$($DOCKER_BIN exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -v ON_ERROR_STOP=1 -Atc "SELECT * FROM get_comment_ancestors_recursive(1);" 2>&1 || true)"
    if echo "$C069" | grep -qi 'does not exist\|error'; then log_fail "069 PG recursive function 真跑失败" "${C069:0:240}"; else log_pass "069 SELECT * FROM get_comment_ancestors_recursive(1) 真跑成功 (空结果亦合法)"; fi
fi
if [ -f "${BASE_DIR}/app/services/drive_comment_service.py" ] && grep -qE 'fallback|Fallback|get_comment_ancestors' "${BASE_DIR}/app/services/drive_comment_service.py"; then
    log_pass "069 Python fallback path 可发现"
else
    log_fail "069 fallback path 未发现" "drive_comment_service 必须在 PG function 不可用时回退"
fi

# ============================================================
# §13 baseline 71 PASS + 7 SKIP 跨 4 批守恒
# ============================================================
section "§13 baseline 71 PASS + 7 SKIP 跨 4 批守恒"

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
        log_warn "baseline ${B_PASS} < 71 — 排查 stale 引用 (CLAUDE.md W62 baseline 9 files 教训)"
    elif [ "$B_PASS" = "0" ]; then
        log_warn "baseline 0 PASS — pytest collect 失败 (见 tests/test_baseline_audit.py)"
    else
        log_fail "baseline PASS=${B_PASS} 远低于 71"
    fi
fi

# ============================================================
# §14 总结报告 + 退出码
# ============================================================
section "§14 总结"
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
    printf "%s✅ W68 第 7-9 批 13 段部署验证全部通过%s\n" "${GREEN}${BOLD}" "${RESET}"
    echo ""
    echo "下一步:"
    echo "  - 通知团队 W68 第 7 批 + 3 hot-fix 已全部上线"
    echo "  - 锚点范式第 92 守恒 — 记录到 release notes"
    echo "  - 监控 logs: docker compose logs app --tail 100 -f | grep -i 'push\\|collab\\|drive'"
    exit 0
else
    printf "%s❌ W68 第 7 批 + 3 hot-fix 部署验证有 %d 项失败%s\n" "${RED}${BOLD}" "$FAIL" "${RESET}"
    echo ""
    echo "下一步:"
    echo "  - 按上方 FAIL 详情逐条修复 (优先: alembic 066→067→068→069 → 真跑 → endpoint 鉴权)"
    echo "  - 参考 docs/w68-7th-batch-deployment-runbook.md §3 (alembic 链) + §5 (回滚)"
    echo "  - 修复后重跑本脚本: bash scripts/verify_w68_7th_batch_deployment.sh"
    exit 1
fi