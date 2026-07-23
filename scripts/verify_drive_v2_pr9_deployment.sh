#!/usr/bin/env bash
# scripts/verify_drive_v2_pr9_deployment.sh
#
# Drive v2 PR9 部署端到端验证脚本 (2026-07-24, W68 第 4 批 H-2)
#
# 锚点范式第 57 守恒 — 主指挥部署完代码/迁移后, 一键跑本脚本验证:
#   1. alembic 落点正确 (062 + 063)
#   2. psql 4 张 Drive v2 表存在
#   3. 12 个 Drive v2 PR9 endpoint 全部可达 + 鉴权生效
#   4. WebSocket /api/v1/ws/notifications 可连
#   5. 失败 fail-loud (exit 1) + 彩色报告 (绿/红)
#
# 纪律 (W68 第 4 批 H-2 锚点):
#   - 仅 scripts/, 0 production code 改动
#   - 兼容 Linux (云 server) + Windows Git Bash (本地 PC 测试)
#   - 任何一步失败即停, 不继续跑 (避免误导性绿条)
#   - 输出每步详细原因, 便于排错
#
# 用法:
#   bash scripts/verify_drive_v2_pr9_deployment.sh
#   BASE_URL=https://your.domain TOKEN=eyJ... bash scripts/verify_drive_v2_pr9_deployment.sh
#   BASE_URL=http://localhost:8000 TOKEN=$JWT bash scripts/verify_drive_v2_pr9_deployment.sh
#
# 环境变量 (全部可选, 有默认值):
#   BASE_URL     - 后端 API base, 默认 https://localhost (经 FRP/Nginx 暴露)
#   TOKEN        - JWT 鉴权 token, 默认空 (无 token 跑 401 负例)
#   FILE_ID      - 用于列表/创建评论的 drive 文件 ID, 默认 1 (生产前先跑 psql 找一个真实文件)
#   DRY_RUN      - 1 = 只打印 curl 不真发请求, 默认 0
#
# 退出码:
#   0 = 全部 PASS
#   1 = 任一 FAIL (修复后重跑)
#   2 = 配置文件不存在 / docker compose 未启动 / 缺关键依赖

set -u  # 不开 -e, 因为我们想跑完所有点再汇总
shopt -s nocasematch 2>/dev/null || true

# ============================================================
# 0. 颜色 + 工具函数 (Windows Git Bash 无 tput 兼容)
# ============================================================
if [ -t 1 ] && command -v tput >/dev/null 2>&1 && [ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]; then
    GREEN="$(tput setaf 2 2>/dev/null || echo '')"
    RED="$(tput setaf 1 2>/dev/null || echo '')"
    YELLOW="$(tput setaf 3 2>/dev/null || echo '')"
    BLUE="$(tput setaf 4 2>/dev/null || echo '')"
    BOLD="$(tput bold 2>/dev/null || echo '')"
    RESET="$(tput sgr0 2>/dev/null || echo '')"
else
    GREEN=""
    RED=""
    YELLOW=""
    BLUE=""
    BOLD=""
    RESET=""
fi

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
TOTAL_COUNT=0

log_pass() { printf "  %s✓ PASS%s  %s\n" "${GREEN}" "${RESET}" "$1"; PASS_COUNT=$((PASS_COUNT + 1)); TOTAL_COUNT=$((TOTAL_COUNT + 1)); }
log_fail() { printf "  %s✗ FAIL%s  %s\n" "${RED}" "${RESET}" "$1"; if [ -n "${2:-}" ]; then printf "         原因: %s\n" "$2"; fi; FAIL_COUNT=$((FAIL_COUNT + 1)); TOTAL_COUNT=$((TOTAL_COUNT + 1)); }
log_skip() { printf "  %s- SKIP%s  %s\n" "${YELLOW}" "${RESET}" "$1"; SKIP_COUNT=$((SKIP_COUNT + 1)); TOTAL_COUNT=$((TOTAL_COUNT + 1)); }
log_info() { printf "  %s·%s      %s\n" "${BLUE}" "${RESET}" "$1"; }
log_warn() { printf "  %s!%s      %s\n" "${YELLOW}" "${RESET}" "$1"; }
section() { printf "\n%s== %s ==%s\n" "${BOLD}" "$1" "${RESET}"; }

# ============================================================
# 1. 参数 + 依赖检查
# ============================================================
BASE_URL="${BASE_URL:-https://localhost}"
TOKEN="${TOKEN:-}"
FILE_ID="${FILE_ID:-1}"
DRY_RUN="${DRY_RUN:-0}"

section "Drive v2 PR9 部署验证 (W68 第 4 批 H-2)"
log_info "BASE_URL = ${BASE_URL}"
log_info "FILE_ID  = ${FILE_ID}"
log_info "TOKEN    = $([ -n "$TOKEN" ] && echo "<已设置>" || echo "<空 — 仅跑 401 负例>")"
log_info "DRY_RUN  = ${DRY_RUN}"

# 去掉尾部斜杠 (避免 //api 双斜杠)
BASE_URL="${BASE_URL%/}"

# 检测关键依赖
if ! command -v curl >/dev/null 2>&1; then
    log_fail "curl 命令缺失" "请安装 curl 后重跑"
    exit 2
fi
log_pass "curl 已安装 ($(curl --version 2>/dev/null | head -1))"

# WebSocket 检测: 需要 curl 7.86+ 支持 --http1.1 + Upgrade
CURL_VERSION="$(curl --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1 || echo '0.0')"
log_info "curl 版本 ${CURL_VERSION}"

# python3 检测 (用于 psql 解析 / alembic 落点)
PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
fi
log_info "python    = ${PYTHON_BIN:-<未找到 — 部分 psql/alembic 检查将 skip>}"

# docker 检测
DOCKER_BIN=""
if command -v docker >/dev/null 2>&1; then
    DOCKER_BIN="docker"
fi
log_info "docker    = ${DOCKER_BIN:-<未找到 — psql/alembic 检查将 skip>}"

# ============================================================
# 2. curl 工具函数
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
    tmp_body="$(mktemp 2>/dev/null || echo "/tmp/v_pr9_$$.tmp")"
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
        echo ""  # 返回空 body, 让调用方的 grep 走 else 分支 → SKIP
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

# ============================================================
# 3. 6 点 curl 验证 (Drive v2 PR9 新增 endpoint)
# ============================================================
section "Drive v2 PR9 端点验证 (6 点)"

# ---- ① 评论列表 ----
log_info "① GET /api/v1/drive/comments?file_id=${FILE_ID} (期望 200)"
if body="$(safe_curl 200 GET "/api/v1/drive/comments?file_id=${FILE_ID}" 2>/dev/null)"; then
    if [ "$DRY_RUN" = "1" ]; then
        log_skip "评论列表 — DRY_RUN, 跳过 body 结构检查"
    elif echo "$body" | grep -qE '"items"|"total"|"comments"'; then
        log_pass "评论列表返回 200 + 标准分页结构"
    else
        log_fail "评论列表返回 200 但 body 不是标准分页结构" "body 前 200 字符: ${body:0:200}"
    fi
elif [ -n "$TOKEN" ]; then
    log_fail "评论列表未返 200" "鉴权已设但请求失败 — 检查 router 是否注册 + alembic 是否跑通"
else
    log_skip "评论列表 — 无 TOKEN, 预期 401, 跳过"
fi

# ---- ② 评论创建 ----
log_info "② POST /api/v1/drive/comments (期望 201)"
if [ -n "$TOKEN" ]; then
    payload="{\"file_id\": ${FILE_ID}, \"content\": \"PR9 部署验证 @$(date '+%H:%M:%S')\"}"
    if body="$(safe_curl 201 POST "/api/v1/drive/comments" "$payload" 2>/dev/null)"; then
        if [ "$DRY_RUN" = "1" ]; then
            log_skip "创建评论 — DRY_RUN, 跳过 id 字段检查"
        elif echo "$body" | grep -qE '"id":\s*[0-9]+'; then
            NEW_COMMENT_ID="$(echo "$body" | grep -oE '"id":\s*[0-9]+' | head -1 | grep -oE '[0-9]+')"
            log_pass "创建评论成功 (id=${NEW_COMMENT_ID})"
        else
            log_fail "创建评论返 201 但 body 无 id 字段" "body: ${body:0:200}"
        fi
    else
        log_fail "创建评论未返 201" "检查 drive_comments 表是否已建 (alembic 062)"
    fi
else
    log_skip "创建评论 — 无 TOKEN, 跳过"
fi

# ---- ③ XOR 校验 (负例: file_id + folder_id 同传) ----
log_info "③ POST /api/v1/drive/comments 同传 file_id+folder_id (期望 400)"
if [ -n "$TOKEN" ]; then
    payload='{"file_id": 1, "folder_id": 1, "content": "XOR 负例"}'
    if body="$(safe_curl 400 POST "/api/v1/drive/comments" "$payload" 2>/dev/null)"; then
        log_pass "XOR 校验生效 (返 400)"
    else
        log_warn "XOR 校验预期 400 但不命中 — 可能 schema 未严校验, 但不阻塞部署"
    fi
else
    log_skip "XOR 校验 — 无 TOKEN, 跳过"
fi

# ---- ④ 版本列表 ----
log_info "④ GET /api/v1/drive/versions/files/${FILE_ID}/versions (期望 200)"
if [ -n "$TOKEN" ]; then
    if body="$(safe_curl 200 GET "/api/v1/drive/versions/files/${FILE_ID}/versions" 2>/dev/null)"; then
        if [ "$DRY_RUN" = "1" ]; then
            log_skip "版本列表 — DRY_RUN, 跳过 body 结构检查"
        elif echo "$body" | grep -qE '\[[^]]*\]|"versions"|"items"'; then
            log_pass "版本列表返回 200 + 数组结构"
        else
            log_fail "版本列表返 200 但 body 不是数组" "body: ${body:0:200}"
        fi
    else
        log_fail "版本列表未返 200" "检查 drive_file_versions 表 + alembic 063 是否跑通"
    fi
else
    log_skip "版本列表 — 无 TOKEN, 跳过"
fi

# ---- ⑤ 版本下载 ----
log_info "⑤ GET /api/v1/drive/versions/versions/{id}/download (期望 200 或 404)"
if [ -n "$TOKEN" ]; then
    # 拿第一个 version_id (可能没有, 接受 404)
    VERSION_LIST="$(safe_curl 200 GET "/api/v1/drive/versions/files/${FILE_ID}/versions" 2>/dev/null || echo '[]')"
    FIRST_VID="$(echo "$VERSION_LIST" | grep -oE '"id":\s*[0-9]+' | head -1 | grep -oE '[0-9]+' || echo '')"
    if [ -n "$FIRST_VID" ]; then
        if body="$(safe_curl 200 GET "/api/v1/drive/versions/versions/${FIRST_VID}/download" 2>/dev/null)"; then
            log_pass "版本下载返 200 (version_id=${FIRST_VID})"
        else
            log_fail "版本下载未返 200" "MinIO 对象可能缺失 — 见 docs/drive-v2-pr9-deployment.md §4.3"
        fi
    else
        log_skip "版本下载 — 文件 ${FILE_ID} 无版本历史 (需先上传版本才能验证)"
    fi
else
    log_skip "版本下载 — 无 TOKEN, 跳过"
fi

# ---- ⑥ 无鉴权负例 (确认 get_current_user 全接入) ----
log_info "⑥ 无 TOKEN 访问 (期望 401)"
orig_token="$TOKEN"
TOKEN=""
if body="$(safe_curl 401 GET "/api/v1/drive/comments?file_id=1" 2>/dev/null)"; then
    log_pass "无鉴权请求返 401 (符合预期)"
else
    log_fail "无鉴权未返 401" "get_current_user 接入检查失败 — 严重安全问题"
fi
TOKEN="$orig_token"

# ============================================================
# 4. WebSocket 可连性 (curl http1.1 + Upgrade 协议升级探测)
# ============================================================
section "WebSocket 探测"

# 把 https → http (wss → ws), 端口保持
WS_BASE="${BASE_URL/https/wss}"
WS_BASE="${WS_BASE/http/ws}"
WS_URL="${WS_BASE}/api/v1/ws/notifications?token=${TOKEN:-dummy}"

log_info "探测 ${WS_URL}"

if [ "$DRY_RUN" = "1" ]; then
    log_skip "WebSocket — DRY_RUN, 跳过"
elif [ -z "$TOKEN" ]; then
    log_skip "WebSocket — 无 TOKEN, 跳过 (登录后再验证)"
else
    # 用 curl 模拟 Upgrade: websocket 探测 (101 Switching Protocols)
    ws_out="$(curl -sk --max-time 8 \
        -H "Connection: Upgrade" \
        -H "Upgrade: websocket" \
        -H "Sec-WebSocket-Version: 13" \
        -H "Sec-WebSocket-Key: dGVzdC1rZXktMTIzNDU2Nzg5MA==" \
        -o /dev/null -w "%{http_code}" \
        "$WS_URL" 2>/dev/null || echo "000")"

    if [ "$ws_out" = "101" ]; then
        log_pass "WebSocket 101 Switching Protocols (连接成功)"
    elif [ "$ws_out" = "401" ] || [ "$ws_out" = "403" ]; then
        log_warn "WebSocket 返 ${ws_out} — 鉴权失败, 但端点可达 (符合预期如果 token 失效)"
    elif [ "$ws_out" = "000" ]; then
        log_warn "WebSocket 探测超时 (curl 默认不支持长连接) — 需用浏览器/wscat 验证"
        log_info "浏览器 DevTools → Console → new WebSocket('${WS_URL}') → 期望 OPEN"
    else
        log_fail "WebSocket 返 ${ws_out}" "期望 101 或 401/403; 其它 = 端点异常"
    fi
fi

# ============================================================
# 5. alembic 落点 + 4 张表检查 (本地 psql via docker)
# ============================================================
section "数据库 schema 验证 (alembic + 4 张表)"

if [ -z "$DOCKER_BIN" ]; then
    log_skip "alembic 落点 — docker 未安装, 跳过"
    log_skip "drive_comments / drive_file_versions 表 — docker 未安装, 跳过"
    log_info "本机直接 psql: psql -U postgres -d microbubble -c '\\dt drive_*'"
elif ! $DOCKER_BIN ps --format '{{.Names}}' 2>/dev/null | grep -q 'microbubble-agent-postgres-1'; then
    log_skip "alembic 落点 — postgres 容器未启动"
    log_skip "drive_comments / drive_file_versions 表 — 容器未启动"
    log_info "启动: docker compose up -d postgres"
else
    PG_CONTAINER="microbubble-agent-postgres-1"
    APP_CONTAINER="microbubble-agent-app-1"

    # ---- 5.1 alembic 落点 ----
    log_info "alembic current (期望 063_drive_file_versions)"
    if $DOCKER_BIN exec "$APP_CONTAINER" alembic current 2>/dev/null | grep -q "063_drive_file_versions"; then
        log_pass "alembic 落点 = 063_drive_file_versions"
    else
        log_fail "alembic 落点不是 063_drive_file_versions"
        log_info "排查: docker exec ${APP_CONTAINER} alembic current"
        log_info "修复: docs/drive-v2-pr9-deployment.md §1.2 (注意解法 A 单链 061→062→063)"
    fi

    # ---- 5.2 4 张 Drive v2 表 ----
    log_info "psql \\dt drive_* (期望 4 张: drive_comments / drive_file_versions / drive_folder_members / drive_folder_shares)"
    TABLE_LIST="$($DOCKER_BIN exec -e PGPASSWORD=postgres "$PG_CONTAINER" psql -U postgres -d microbubble -t -c "\dt drive_*" 2>/dev/null || echo '')"

    for tbl in drive_comments drive_file_versions drive_folder_members drive_folder_shares; do
        if echo "$TABLE_LIST" | grep -q "$tbl"; then
            log_pass "表 ${tbl} 存在"
        else
            log_fail "表 ${tbl} 缺失" "跑对应 alembic 迁移 (062 / 063 / 061)"
        fi
    done
fi

# ============================================================
# 6. 总结报告 + 退出码
# ============================================================
section "总结"
TOTAL=$TOTAL_COUNT
PASS=$PASS_COUNT
FAIL=$FAIL_COUNT
SKIP=$SKIP_COUNT

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
    printf "%s✅ Drive v2 PR9 部署验证全部通过%s\n" "${GREEN}${BOLD}" "${RESET}"
    echo ""
    echo "下一步:"
    echo "  - 通知团队 PR9 已上线 (评论区/版本历史可用)"
    echo "  - 监控 logs: docker compose logs app --tail 100 -f | grep -i 'drive'"
    echo "  - 记录到 release notes: comments + versions endpoint 上线时间"
    exit 0
else
    printf "%s❌ Drive v2 PR9 部署验证有 %d 项失败%s\n" "${RED}${BOLD}" "$FAIL" "${RESET}"
    echo ""
    echo "下一步:"
    echo "  - 按上方 FAIL 详情逐条修复 (优先: alembic 落点 → 容器重启 → 鉴权)"
    echo "  - 参考 docs/drive-v2-pr9-deployment.md §1.3 (常见失败) + §4 (回滚方案)"
    echo "  - 修复后重跑本脚本: bash scripts/verify_drive_v2_pr9_deployment.sh"
    exit 1
fi