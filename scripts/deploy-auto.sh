#!/bin/bash
# 自动部署脚本 — 由 webhook 触发
# 拉取代码 → 重载 Nginx（前端在本地构建，dist 由 git 提交）
# 容错策略：关键步骤手动 exit，非关键步骤允许失败继续

PROJECT_DIR="/opt/microbubble-agent"
# 2026-06-13 加固：LOG_FILE 允许环境变量覆盖（deploy 用户调试时可指定可写路径）
LOG_FILE="${LOG_FILE:-/var/log/webhook-deploy.log}"

# 2026-06-02 修复：阿里云→GitHub HTTPS 出口网络持续 130s 超时
# 改用 SSH 拉取（走 22 端口，绕开 HTTPS 链路问题）
# 但用户专用 SSH key 在 ~/.ssh/github_deploy（非默认名 id_*），
# 所以需要显式设 GIT_SSH_COMMAND 让 git 用这个 key
export GIT_SSH_COMMAND="ssh -i /root/.ssh/github_deploy -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
# 注：StrictHostKeyChecking=no + UserKnownHostsFile=/dev/null 防止 "host key verification failed"
#      阻塞（首次 SSH 连接时）。生产环境如果想更安全，可以预先生成 known_hosts。

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [DEPLOY] $1" >> "$LOG_FILE"
}

log "========== 开始部署 =========="

cd "$PROJECT_DIR"

# 2026-06-17 加固 v2：webhook secret 持久化文件自愈机制
# 教训：guard 必须在 git clean 之前 + git clean 排除 .env.webhook + 缺失时从 PID 进程环境恢复
# 6/17 v1 版本：guard 在 clean 之前检查 → 通过 → git clean -fdx 删 .env.webhook → 下次 deploy 失败循环
# 6/17 v2 版本：自愈（从 PID 3023112 process memory 重新写） + git clean 排除 (-e .env.webhook)
if [ ! -f "$PROJECT_DIR/.env.webhook" ]; then
    log "[recovery] .env.webhook 缺失，尝试从 webhook 进程环境恢复..."
    PID=$(pgrep -f "scripts/webhook.py" | head -1)
    if [ -n "$PID" ] && [ -r /proc/$PID/environ ]; then
        SECRET=$(cat /proc/$PID/environ 2>/dev/null | tr '\0' '\n' | grep -E "^WEBHOOK_SECRET=" | cut -d= -f2)
        if [ -n "$SECRET" ]; then
            echo "WEBHOOK_SECRET=$SECRET" > "$PROJECT_DIR/.env.webhook"
            chmod 600 "$PROJECT_DIR/.env.webhook"
            chown root:root "$PROJECT_DIR/.env.webhook" 2>/dev/null || true
            log "[recovery] ✓ 从 PID $PID 恢复 .env.webhook (${#SECRET} 字符)"
        else
            log "ERROR: PID $PID 存在但读不到 WEBHOOK_SECRET"
            exit 1
        fi
    else
        log "ERROR: .env.webhook 缺失 + 找不到 webhook 进程（pgrep failed）"
        log "ERROR: 手动修复：sudo systemctl restart webhook 会失败因为 EnvironmentFile 缺失"
        log "ERROR: 需要手动：1) 写 .env.webhook  2) systemctl daemon-reload  3) systemctl restart webhook"
        exit 1
    fi
fi

# 2026-06-13 加固：丢弃所有本地修改 + untracked 文件，确保干净工作区
# （之前 git checkout + git clean 分两步有时不彻底，残留 untracked 文件阻塞 git pull fast-forward）
# 2026-06-17 v2 加：-e .env.webhook 排除该文件（虽然它在 .gitignore 内但 git clean -fdx 仍会删）
git checkout -- . >> "$LOG_FILE" 2>&1 || true
git clean -fdx -e .env.webhook >> "$LOG_FILE" 2>&1 || true  # -x 也清 .gitignore 内的文件，但 -e 排除指定

# 拉取最新代码（重试 5 次 + 指数退避，2026-06-02 加固）
# 背景：阿里云服务器偶发无法连接 GitHub（TLS/GnuTLS 错误或超时），
# 一次重试不够稳定，加 5 次重试 + 指数退避 + GCM 加密协商回退。
log "git pull..."
PULL_OK=0
MAX_RETRY=5
for i in $(seq 1 $MAX_RETRY); do
    log "  第${i}/${MAX_RETRY}次尝试..."
    # 2026-06-13 改：直接用 fetch + reset --hard 模式，不依赖 git pull 的合并逻辑
    # 原因：服务器是 immutable infra（部署后不保留任何本地修改），
    # git pull 在 dirty working tree 下可能被本地 untracked 文件阻塞 → "Cannot fast-forward"
    # fetch + reset --hard 永远只把 working tree 强制对齐 origin/main
    if git fetch origin main >> "$LOG_FILE" 2>&1 && \
       git reset --hard origin/main >> "$LOG_FILE" 2>&1; then
        PULL_OK=1
        log "  fetch + reset --hard 成功"
        break
    fi
    # 指数退避：5s, 10s, 20s, 40s（总等待 75s）
    BACKOFF=$((5 * (2 ** (i - 1))))
    log "  fetch 失败，${BACKOFF}s 后重试（GitHub TLS 偶发错误）"
    sleep $BACKOFF
done

if [ $PULL_OK -eq 0 ]; then
    # 2026-06-02 修复：git pull 失败时尝试 fetch + reset --hard origin/main（绕开合并冲突）
    log "WARN: git pull 5 次都失败，尝试 fetch + reset 模式..."
    if git fetch origin main >> "$LOG_FILE" 2>&1 && \
       git reset --hard origin/main >> "$LOG_FILE" 2>&1; then
        PULL_OK=1
        log "  fetch + reset 成功"
    else
        log "ERROR: git pull/fetch 都失败，跳过本次部署"
        log "========== 部署中止 =========="
        exit 1
    fi
fi

# 2026-07-10 P0 修复：检测 .py 文件变更 → 提醒手动重启 Docker app container
# 根因：服务器后端架构 = nginx(云) → frps(云) → frpc(本地 PC) → Docker app (本地 PC)
#       云端 git pull 后只是云端磁盘新文件，**Python 进程没自动 reload**
#       → 任何 .py / alembic 改动必须手动在本地 PC `docker restart microbubble-agent-app-1 microbubble-agent-celery-worker-1`
# 修复前症状: 用户 push 修复 → 服务器 curl 仍是旧响应（如 folder delete 404 返 FastAPI 默认 {detail}）
# 修复: deploy-auto.sh 自动检测 .py/alembic 改动 → log 醒目的提醒 + 列出受影响的本地 PC 重启命令
# 注意: 这是**临时**缓解方案。彻底解决需要 frps 在 git pull 后自动触发本地 PC 重启
#       (未来可加 scripts/local-auto-restart.sh: 本地 PC daemon 监听云端 signal 或 git pull 通知)
PY_CHANGED=$(git diff --name-only HEAD@{1} HEAD 2>/dev/null | grep -E '^(app/|alembic/)' | wc -l)
if [ "$PY_CHANGED" -gt 0 ]; then
    log "================================================================"
    log "⚠️  Python 代码有 ${PY_CHANGED} 个文件变更 — 必须手动重启本地 PC Docker！"
    log "================================================================"
    log "受影响的文件 (前 10 个):"
    git diff --name-only HEAD@{1} HEAD 2>/dev/null | grep -E '^(app/|alembic/)' | head -10 | while read f; do
        log "    - $f"
    done
    log ""
    log "本地 PC 必须执行（让新代码生效）:"
    log "    ssh user@local-pc 'docker restart microbubble-agent-app-1 microbubble-agent-celery-worker-1'"
    log "    或 Windows 本地:"
    log "    docker restart microbubble-agent-app-1 microbubble-agent-celery-worker-1"
    log ""
    log "注意: 不重启的话 curl 服务器 200 但 Python 进程仍在跑旧代码！"
    log "================================================================"
fi

# 检查可用磁盘空间（至少 500MB）
AVAILABLE_MB=$(df -m /opt | tail -1 | awk '{print $4}')
if [ "$AVAILABLE_MB" -lt 500 ]; then
    log "ERROR: 磁盘空间不足 (${AVAILABLE_MB}MB)，部署中止"
    log "========== 部署中止 =========="
    exit 1
fi

# 使用 git 已提交的 dist（不在服务器上构建，避免 2核2G OOM）
cd "$PROJECT_DIR"
if [ ! -f "$PROJECT_DIR/web/dist/index.html" ]; then
    log "ERROR: dist/index.html 不存在，部署中止"
    log "========== 部署中止 =========="
    exit 1
fi

# 2026-06-03 健全性检查：dist 必须包含至少 10 个 JS 文件
# 背景：commit d619f33 漏 build，删了 23 个旧 dist 但没补新文件，
# 导致 index.html 引用 index-mZemtrw0.js 但 dist 不存在 → 白屏
# 这个检查会拦住未来类似的"只删不建" commit
DIST_JS_COUNT=$(find "$PROJECT_DIR/web/dist/assets" -maxdepth 1 -name 'index-*.js' 2>/dev/null | wc -l)
if [ "$DIST_JS_COUNT" -lt 1 ]; then
    log "ERROR: dist/assets/index-*.js 不存在（$DIST_JS_COUNT 个），部署中止"
    log "可能原因：commit 漏 npm run build，或 build 失败"
    log "请在本地执行 'cd web && npm run build' 后重新 commit"
    log "========== 部署中止 =========="
    exit 1
fi
# 二次检查：index.html 引用的 JS 是否在 dist 里
INDEX_HASH=$(grep -oE 'assets/index-[A-Za-z0-9_-]+\.js' "$PROJECT_DIR/web/dist/index.html" | head -1)
if [ -n "$INDEX_HASH" ] && [ ! -f "$PROJECT_DIR/web/dist/$INDEX_HASH" ]; then
    log "ERROR: index.html 引用 $INDEX_HASH，但该文件不在 dist 中"
    log "dist/assets/ 里实际有: $(ls $PROJECT_DIR/web/dist/assets/ 2>/dev/null | grep -E 'index-.*\.js' | tr '\n' ' ')"
    log "========== 部署中止 =========="
    exit 1
fi
log "dist 健全性检查通过（$DIST_JS_COUNT 个 index-*.js，index.html 引用 $INDEX_HASH 存在）"

# PWA SW 健全性检查：dist/sw.js 不能引用 unhashed manifest.webmanifest
# 背景：vite-plugin-pwa 自动把 manifest.webmanifest 加进 precache 列表（globIgnores 对它无效），
# 必须由 web/scripts/postbuild-fix-manifest.js 改写 sw.js 把 URL 替换成 manifest.{hash}.webmanifest。
# 漏改会导致 SW install 阶段 precache 拉旧 URL → 服务器 c855f0e commit 设的 410 Gone
# → bad-precaching-response → SW install 失败 → 用户浏览器永久污染 cache（新 SW 永远激活不了）。
# 这个检查会拦住未来类似的"build 链路瞬态失败但 npm run build 退出码 0"的 commit。
if [ -f "$PROJECT_DIR/web/dist/sw.js" ]; then
    SW_MANIFEST_OLD_URL=$(grep -oE '"url":"manifest\.webmanifest"' "$PROJECT_DIR/web/dist/sw.js" 2>/dev/null | head -1)
    if [ -n "$SW_MANIFEST_OLD_URL" ]; then
        log "ERROR: dist/sw.js 仍引用 unhashed $SW_MANIFEST_OLD_URL"
        log "服务器 c855f0e commit 把 /manifest.webmanifest 设为 410 Gone"
        log "→ SW install 阶段 precache 失败 → 用户浏览器永久污染"
        log "修复方法：cd web && npm run build（必须走 && node scripts/postbuild-fix-manifest.js）"
        log "如果 npm run build 仍失败，看 postbuild-fix-manifest.js 第 4 步健全性自检的报错"
        log "========== 部署中止 =========="
        exit 1
    fi
    log "PWA SW precache 检查通过（sw.js 不含 unhashed manifest 引用）"
fi

# PWA SW 健全性检查 (staged diff)：防 commit 59187ce8 回归再次发生
# 背景：上面 line 167-178 检查磁盘上的 web/dist/sw.js，但 commit 59187ce8 cascade folder delete
# 是开发者本地 `vite build` 直跑 (绕开 `npm run build` 末尾的 postbuild-fix-manifest.js) → 磁盘上
# 的 sw.js 含 unhashed manifest.webmanifest → 上面检查能拦。但**如果开发者重跑 npm run build 后
# 手动 force-add 了老的 unhashed dist 文件** (例如 cache 里残留 + git add -f web/dist/) → 磁盘 sw.js
# 是干净的 (postbuild 已修) → 上面检查过 → 但 git diff --cached 可能仍含 unhashed 引用 →
# commit push 后 webhook 部署会用 git HEAD 的旧 sw.js 替换磁盘的干净 sw.js → 回归。
# 修法：在 git commit 之前 grep staged diff，命中即 abort。
if git rev-parse --git-dir >/dev/null 2>&1; then
    STAGED_MANIFEST_OLD=$(git diff --cached -- web/dist/ 2>/dev/null | grep -E '"url":\s*"manifest\.webmanifest"' | head -3)
    if [ -n "$STAGED_MANIFEST_OLD" ]; then
        log "ERROR: git diff --cached 含 unhashed manifest.webmanifest 引用 (commit 59187ce8 回归点)"
        log "staged diff 含以下 unhashed 引用:"
        echo "$STAGED_MANIFEST_OLD" | while IFS= read -r line; do log "  $line"; done
        log "修复方法：cd web && npm run build (重跑 postbuild-fix-manifest.js 自动 hash 化)"
        log "        然后 git reset HEAD web/dist/ 再 git add -f web/dist/ 重新 stage"
        log "========== 部署中止 =========="
        exit 1
    fi
    log "PWA staged diff 检查通过 (git diff --cached 不含 unhashed manifest 引用)"
fi

# 同步 Nginx 配置（tunnel.conf → /etc/nginx/conf.d/default.conf）
# 注意：此步骤在 git pull 之后执行，配置变更下次部署生效
if [ -f "$PROJECT_DIR/nginx/conf.d/tunnel.conf" ]; then
    cp "$PROJECT_DIR/nginx/conf.d/tunnel.conf" /etc/nginx/conf.d/default.conf
    log "nginx config synced"
fi

# 补充/修正 woff2 MIME 类型（Nginx 默认 mime.types 可能不含 woff2，或旧值不正确）
if ! grep -q 'font/woff2' /etc/nginx/mime.types 2>/dev/null; then
    # 删除旧的错误条目（application/font-woff2）
    grep -v 'application/font-woff2' /etc/nginx/mime.types > /tmp/mime.types.new
    # 在 woff 行后插入正确的 woff2
    awk '/application\/font-woff.*woff;/{print;print "    font/woff2                           woff2;";next}1' /tmp/mime.types.new > /etc/nginx/mime.types
    rm -f /tmp/mime.types.new
    log "woff2 MIME type fixed in mime.types"
fi

# 2026-06-13 webhint 修复：注入 webmanifest MIME 类型到 mime.types
# 背景：Nginx 1.27 之前默认 mime.types 不含 .webmanifest → application/octet-stream
# → 浏览器拒绝解析 PWA manifest。
#
# ⚠️ 关键纪律：必须在 http 块的 mime.types 里加，**不要**在 server context 用
# types { } block —— types 指令在 server context **完全覆盖**默认 mime.types，
# 会让 .html/.css/.js 全变 octet-stream（白屏事故 2026-06-13 commit 0a29290）。
# http context 的 mime.types 是合并语义（additive），不会丢失默认 MIME。
if ! grep -q 'application/manifest+json' /etc/nginx/mime.types 2>/dev/null; then
    # 用 sed 在 application/json 行后追加 webmanifest（更可靠，awk 在某些 Nginx 默认
    # mime.types 行尾含 \r 时会失效）。
    # 匹配 "application/json" 整行（含可能尾随空格/CR），在新行后插入 webmanifest。
    sed -i '/^application\/json[[:space:]]/a\    application/manifest+json           webmanifest;' /etc/nginx/mime.types
    if grep -q 'application/manifest+json' /etc/nginx/mime.types 2>/dev/null; then
        log "webmanifest MIME type added to mime.types"
    else
        log "ERROR: webmanifest MIME sed injection failed"
    fi
fi

# ============================================================================
# 2026-06-14 方案 C Stage 5 收尾：agent_traces 表迁移
# 自动跑 alter_agent_traces_stage3.sql（加 7 列：intent/critique/status 等）
# 幂等（用 ADD COLUMN IF NOT EXISTS），重复跑安全
# ============================================================================
MIGRATION_SQL="$PROJECT_DIR/scripts/alter_agent_traces_stage3.sql"
if [ -f "$MIGRATION_SQL" ]; then
    PG_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'postgres|db' | head -1)
    if [ -n "$PG_CONTAINER" ]; then
        log "运行 agent_traces schema 迁移（7 列）..."
        if docker exec -i "$PG_CONTAINER" psql -U postgres -d microbubble < "$MIGRATION_SQL" >> "$LOG_FILE" 2>&1; then
            log "agent_traces 迁移成功（intentional 幂等）"
        else
            log "WARN: agent_traces 迁移失败，请手动跑："
            log "  docker exec $PG_CONTAINER psql -U postgres -d microbubble -f scripts/alter_agent_traces_stage3.sql"
        fi
    else
        log "WARN: 未找到 postgres 容器，跳过迁移（请手动跑 ALTER TABLE）"
    fi
else
    log "WARN: $MIGRATION_SQL 不存在（首次部署？git pull 可能漏了）"
fi

# ============================================================================
# 2026-06-15 提醒 v2 迁移：reminders 表加 6 列 (ack/snooze/11AM 批次)
# 触发场景: 提醒策略 v2 改动 (commit 223ea74 + ba75e32) 加了 6 个新列
# 但 DB 没同步 ALTER TABLE → /api/v1/reminders 报 500 错误
# 幂等（ADD COLUMN IF NOT EXISTS），重复跑安全
# ============================================================================
MIGRATION_SQL="$PROJECT_DIR/scripts/alter_reminders_v2.sql"
if [ -f "$MIGRATION_SQL" ]; then
    PG_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'postgres|db' | head -1)
    if [ -n "$PG_CONTAINER" ]; then
        log "运行 reminders v2 schema 迁移（6 列）..."
        if docker exec -i "$PG_CONTAINER" psql -U postgres -d microbubble < "$MIGRATION_SQL" >> "$LOG_FILE" 2>&1; then
            log "reminders v2 迁移成功（幂等）"
        else
            log "WARN: reminders v2 迁移失败，请手动跑："
            log "  docker exec $PG_CONTAINER psql -U postgres -d microbubble -f scripts/alter_reminders_v2.sql"
        fi
    else
        log "WARN: 未找到 postgres 容器，跳过 reminders v2 迁移"
    fi
else
    log "WARN: $MIGRATION_SQL 不存在（首次部署？）"
fi

# 测试 + 重载 Nginx（失败只 warn 不退出）
if nginx -t >> "$LOG_FILE" 2>&1; then
    log "nginx reload..."
    nginx -s reload >> "$LOG_FILE" 2>&1 || log "WARN: nginx reload 失败"
else
    log "ERROR: nginx -t 失败，跳过 reload"
fi

# 后处理 mnb-lab.cn CSS（修复 webhint vendor prefix 警告）
MNB_CSS_DIR="/var/www/mnb-lab/_next/static/css"
if [ -d "$MNB_CSS_DIR" ]; then
    for css in "$MNB_CSS_DIR"/*.css; do
        # 添加标准属性（如果只有 webkit 前缀）
        sed -i 's/-webkit-backdrop-filter:blur(20px)/-webkit-backdrop-filter:blur(20px);backdrop-filter:blur(20px)/g' "$css"
        sed -i 's/-webkit-text-size-adjust:100%/-webkit-text-size-adjust:100%;text-size-adjust:100%/g' "$css"
    done
    log "mnb-lab CSS vendor prefixes fixed"
fi

# 统计项目代码数据（供"项目动态"页面使用）— 独立子 shell 执行，失败不影响部署
log "统计项目代码数据..."
STATS_FILE="$PROJECT_DIR/app/stats.json"
(
  # 整个统计段跑在子 shell 里，任何错误都只影响统计不影响部署
  EXCLUDE_ARGS="-not -path */node_modules/* -not -path */dist/* -not -path */.git/* -not -path */__pycache__/* -not -path */.venv/* -not -path */venv/* -not -path */models/* -not -path */.agents/*"

  _cl() { set -f; find "$PROJECT_DIR" -type f -name "$1" $EXCLUDE_ARGS 2>/dev/null | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}'; set +f; }
  _cf() { set -f; find "$PROJECT_DIR" -type f -name "$1" $EXCLUDE_ARGS 2>/dev/null | wc -l; set +f; }

  PY_LINES=$( _cl "*.py" || echo 0); VUE_LINES=$( _cl "*.vue" || echo 0)
  JS_LINES=$(( $( _cl "*.js" || echo 0) + $( _cl "*.mjs" || echo 0) + $( _cl "*.cjs" || echo 0) ))
  TS_LINES=$( _cl "*.ts" || echo 0)
  CSS_LINES=$(( $( _cl "*.css" || echo 0) + $( _cl "*.scss" || echo 0) + $( _cl "*.less" || echo 0) ))
  HTML_LINES=$( _cl "*.html" || echo 0); MD_LINES=$( _cl "*.md" || echo 0)
  SH_LINES=$(( $( _cl "*.sh" || echo 0) + $( _cl "*.bat" || echo 0) + $( _cl "*.ps1" || echo 0) ))
  CONF_LINES=$(( $( _cl "*.json" || echo 0) + $( _cl "*.yaml" || echo 0) + $( _cl "*.yml" || echo 0) + $( _cl "*.toml" || echo 0) + $( _cl "*.cfg" || echo 0) + $( _cl "*.ini" || echo 0) + $( _cl "*.conf" || echo 0) ))
  SQL_LINES=$( _cl "*.sql" || echo 0)
  DOCKER_LINES=$(( $(find "$PROJECT_DIR" -type f \( -name "Dockerfile" -o -name "docker-compose*" \) $EXCLUDE_ARGS 2>/dev/null | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}' || echo 0) ))
  OTHER_LINES=$(( $( _cl "*.txt" || echo 0) + $( _cl "*.xml" || echo 0) + $( _cl "*.env" || echo 0) + $( _cl "*.template" || echo 0) ))
  TOTAL_LINES=$(( PY_LINES + VUE_LINES + JS_LINES + TS_LINES + CSS_LINES + HTML_LINES + MD_LINES + SH_LINES + CONF_LINES + SQL_LINES + DOCKER_LINES + OTHER_LINES ))

  PY_FILES=$( _cf "*.py" || echo 0); VUE_FILES=$( _cf "*.vue" || echo 0)
  JS_FILES=$(( $( _cf "*.js" || echo 0) + $( _cf "*.mjs" || echo 0) + $( _cf "*.cjs" || echo 0) ))
  TS_FILES=$( _cf "*.ts" || echo 0)
  CSS_FILES=$(( $( _cf "*.css" || echo 0) + $( _cf "*.scss" || echo 0) + $( _cf "*.less" || echo 0) ))
  HTML_FILES=$( _cf "*.html" || echo 0); MD_FILES=$( _cf "*.md" || echo 0)
  SH_FILES=$(( $( _cf "*.sh" || echo 0) + $( _cf "*.bat" || echo 0) + $( _cf "*.ps1" || echo 0) ))
  CONF_FILES=$(( $( _cf "*.json" || echo 0) + $( _cf "*.yaml" || echo 0) + $( _cf "*.yml" || echo 0) + $( _cf "*.toml" || echo 0) + $( _cf "*.cfg" || echo 0) + $( _cf "*.ini" || echo 0) + $( _cf "*.conf" || echo 0) ))
  SQL_FILES=$( _cf "*.sql" || echo 0)
  DOCKER_FILES=$(find "$PROJECT_DIR" -type f \( -name "Dockerfile" -o -name "docker-compose*" \) $EXCLUDE_ARGS 2>/dev/null | wc -l || echo 0)
  OTHER_FILES=$(( $( _cf "*.txt" || echo 0) + $( _cf "*.xml" || echo 0) + $( _cf "*.env" || echo 0) + $( _cf "*.template" || echo 0) ))
  TOTAL_FILES=$(( PY_FILES + VUE_FILES + JS_FILES + TS_FILES + CSS_FILES + HTML_FILES + MD_FILES + SH_FILES + CONF_FILES + SQL_FILES + DOCKER_FILES + OTHER_FILES ))

  TOTAL_COMMITS=$(git -C "$PROJECT_DIR" rev-list --count HEAD 2>/dev/null || echo 0)
  ROOT_SHA=$(git -C "$PROJECT_DIR" rev-list --max-parents=0 HEAD 2>/dev/null || echo "")
  if [ -n "$ROOT_SHA" ]; then
    FIRST_COMMIT=$(git -C "$PROJECT_DIR" log --format=%ai -1 "$ROOT_SHA" 2>/dev/null | cut -d' ' -f1)
    DEV_DAYS=$(( ($(date +%s) - $(date -d "$FIRST_COMMIT" +%s 2>/dev/null || echo 0) + 86399) / 86400 ))
  else
    DEV_DAYS=0
  fi

  cat > "$STATS_FILE" << EOFOUTER
{"total_lines":${TOTAL_LINES:-0},"total_commits":${TOTAL_COMMITS:-0},"first_commit_date":"${FIRST_COMMIT:-}","dev_days":${DEV_DAYS:-0},"total_files":${TOTAL_FILES:-0},"updated_at":"$(date '+%Y-%m-%d %H:%M:%S')","lines_by_type":{"python":${PY_LINES:-0},"vue":${VUE_LINES:-0},"javascript":${JS_LINES:-0},"typescript":${TS_LINES:-0},"css":${CSS_LINES:-0},"html":${HTML_LINES:-0},"markdown":${MD_LINES:-0},"shell":${SH_LINES:-0},"config":${CONF_LINES:-0},"sql":${SQL_LINES:-0},"docker":${DOCKER_LINES:-0},"other":${OTHER_LINES:-0}},"files_by_type":{"python":${PY_FILES:-0},"vue":${VUE_FILES:-0},"javascript":${JS_FILES:-0},"typescript":${TS_FILES:-0},"css":${CSS_FILES:-0},"html":${HTML_FILES:-0},"markdown":${MD_FILES:-0},"shell":${SH_FILES:-0},"config":${CONF_FILES:-0},"sql":${SQL_FILES:-0},"docker":${DOCKER_FILES:-0},"other":${OTHER_FILES:-0}}}
EOFOUTER

  log "项目统计: ${TOTAL_LINES}行(${TOTAL_FILES}个文件), ${TOTAL_COMMITS}次提交, ${DEV_DAYS}天"
  log "  语言分布: Python=${PY_LINES} Vue=${VUE_LINES} JS=${JS_LINES} CSS=${CSS_LINES} MD=${MD_LINES} Shell=${SH_LINES} Config=${CONF_LINES} 其他=${OTHER_LINES}"
) || log "WARN: 项目统计失败（不影响部署）"

log "========== 部署完成 =========="
exit 0
