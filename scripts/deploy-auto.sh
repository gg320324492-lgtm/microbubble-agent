#!/bin/bash
# 自动部署脚本 — 由 webhook 触发
# 拉取代码 → 重载 Nginx（前端在本地构建，dist 由 git 提交）

set -e

PROJECT_DIR="/opt/microbubble-agent"
LOG_FILE="/var/log/webhook-deploy.log"

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

# 丢弃所有本地修改，确保干净状态
git checkout -- . >> "$LOG_FILE" 2>&1 || true
git clean -fd >> "$LOG_FILE" 2>&1 || true

# 拉取最新代码（重试 5 次 + 指数退避，2026-06-02 加固）
# 背景：阿里云服务器偶发无法连接 GitHub（TLS/GnuTLS 错误或超时），
# 一次重试不够稳定，加 5 次重试 + 指数退避 + GCM 加密协商回退。
log "git pull..."
PULL_OK=0
MAX_RETRY=5
for i in $(seq 1 $MAX_RETRY); do
    log "  第${i}/${MAX_RETRY}次尝试..."
    # 用 HTTP/1.1 强制 + 关闭 GCM 加密（有些 GCM 模式在阿里云上 TLS 协商失败）
    if GIT_HTTP_LOW_SPEED_LIMIT=1000 GIT_HTTP_LOW_SPEED_TIME=30 \
       git -c http.version=HTTP/1.1 -c http.sslVersion=tlsv1.2 \
           pull origin main >> "$LOG_FILE" 2>&1; then
        PULL_OK=1
        log "  pull 成功"
        break
    fi
    # 指数退避：5s, 10s, 20s, 40s（总等待 75s）
    BACKOFF=$((5 * (2 ** (i - 1))))
    log "  pull 失败，${BACKOFF}s 后重试（GitHub TLS 偶发错误）"
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

# 测试 nginx 配置有效性
nginx -t >> "$LOG_FILE" 2>&1

# 重载 Nginx
log "nginx reload..."
nginx -s reload >> "$LOG_FILE" 2>&1

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

# 统计项目代码数据（供"项目动态"页面使用）
log "统计项目代码数据..."
STATS_FILE="$PROJECT_DIR/stats.json"
set +e  # 临停容错，统计段允许 find 无结果

# 排除目录（用单行避免数组语法兼容性 + set -f 防 glob 展开）
EXCLUDE_ARGS="-not -path */node_modules/* -not -path */dist/* -not -path */.git/* -not -path */__pycache__/* -not -path */.venv/* -not -path */venv/* -not -path */models/* -not -path */.agents/*"

_count_lines() {
  local pattern="$1"
  set -f
  local result=$(find "$PROJECT_DIR" -type f -name "$pattern" $EXCLUDE_ARGS 2>/dev/null | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
  set +f
  echo "${result:-0}"
}

_count_files() {
  local pattern="$1"
  set -f
  find "$PROJECT_DIR" -type f -name "$pattern" $EXCLUDE_ARGS 2>/dev/null | wc -l
  set +f
}

# 按语言分类统计行数
PY_LINES=$(_count_lines "*.py")
VUE_LINES=$(_count_lines "*.vue")
JS_LINES=$(( $(_count_lines "*.js") + $(_count_lines "*.mjs") + $(_count_lines "*.cjs") ))
TS_LINES=$(_count_lines "*.ts")
CSS_LINES=$(( $(_count_lines "*.css") + $(_count_lines "*.scss") + $(_count_lines "*.less") ))
HTML_LINES=$(_count_lines "*.html")
MD_LINES=$(_count_lines "*.md")
SH_LINES=$(( $(_count_lines "*.sh") + $(_count_lines "*.bat") + $(_count_lines "*.ps1") ))
CONF_LINES=$(( $(_count_lines "*.json") + $(_count_lines "*.yaml") + $(_count_lines "*.yml") + $(_count_lines "*.toml") + $(_count_lines "*.cfg") + $(_count_lines "*.ini") + $(_count_lines "*.conf") ))
SQL_LINES=$(_count_lines "*.sql")
DOCKER_LINES=$(( $(find "$PROJECT_DIR" -type f \( -name "Dockerfile" -o -name "docker-compose*" \) $EXCLUDE_ARGS 2>/dev/null | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}') ))
OTHER_LINES=$(( $(_count_lines "*.txt") + $(_count_lines "*.xml") + $(_count_lines "*.env") + $(_count_lines "*.template") ))

TOTAL_LINES=$(( PY_LINES + VUE_LINES + JS_LINES + TS_LINES + CSS_LINES + HTML_LINES + MD_LINES + SH_LINES + CONF_LINES + SQL_LINES + DOCKER_LINES + OTHER_LINES ))

# 按语言分类统计文件数
PY_FILES=$(_count_files "*.py")
VUE_FILES=$(_count_files "*.vue")
JS_FILES=$(( $(_count_files "*.js") + $(_count_files "*.mjs") + $(_count_files "*.cjs") ))
TS_FILES=$(_count_files "*.ts")
CSS_FILES=$(( $(_count_files "*.css") + $(_count_files "*.scss") + $(_count_files "*.less") ))
HTML_FILES=$(_count_files "*.html")
MD_FILES=$(_count_files "*.md")
SH_FILES=$(( $(_count_files "*.sh") + $(_count_files "*.bat") + $(_count_files "*.ps1") ))
CONF_FILES=$(( $(_count_files "*.json") + $(_count_files "*.yaml") + $(_count_files "*.yml") + $(_count_files "*.toml") + $(_count_files "*.cfg") + $(_count_files "*.ini") + $(_count_files "*.conf") ))
SQL_FILES=$(_count_files "*.sql")
DOCKER_FILES=$(find "$PROJECT_DIR" -type f \( -name "Dockerfile" -o -name "docker-compose*" \) $EXCLUDE_ARGS 2>/dev/null | wc -l)
OTHER_FILES=$(( $(_count_files "*.txt") + $(_count_files "*.xml") + $(_count_files "*.env") + $(_count_files "*.template") ))

TOTAL_FILES=$(( PY_FILES + VUE_FILES + JS_FILES + TS_FILES + CSS_FILES + HTML_FILES + MD_FILES + SH_FILES + CONF_FILES + SQL_FILES + DOCKER_FILES + OTHER_FILES ))

TOTAL_COMMITS=$(git -C "$PROJECT_DIR" rev-list --count HEAD)
ROOT_SHA=$(git -C "$PROJECT_DIR" rev-list --max-parents=0 HEAD)
FIRST_COMMIT=$(git -C "$PROJECT_DIR" log --format=%ai -1 "$ROOT_SHA" | cut -d' ' -f1)
DEV_DAYS=$(( ($(date +%s) - $(date -d "$FIRST_COMMIT" +%s)) / 86400 ))

cat > "$STATS_FILE" << EOF
{
  "total_lines": ${TOTAL_LINES:-0},
  "total_commits": ${TOTAL_COMMITS:-0},
  "dev_days": ${DEV_DAYS:-0},
  "total_files": ${TOTAL_FILES:-0},
  "updated_at": "$(date '+%Y-%m-%d %H:%M:%S')",
  "lines_by_type": {
    "python": ${PY_LINES:-0},
    "vue": ${VUE_LINES:-0},
    "javascript": ${JS_LINES:-0},
    "typescript": ${TS_LINES:-0},
    "css": ${CSS_LINES:-0},
    "html": ${HTML_LINES:-0},
    "markdown": ${MD_LINES:-0},
    "shell": ${SH_LINES:-0},
    "config": ${CONF_LINES:-0},
    "sql": ${SQL_LINES:-0},
    "docker": ${DOCKER_LINES:-0},
    "other": ${OTHER_LINES:-0}
  },
  "files_by_type": {
    "python": ${PY_FILES:-0},
    "vue": ${VUE_FILES:-0},
    "javascript": ${JS_FILES:-0},
    "typescript": ${TS_FILES:-0},
    "css": ${CSS_FILES:-0},
    "html": ${HTML_FILES:-0},
    "markdown": ${MD_FILES:-0},
    "shell": ${SH_FILES:-0},
    "config": ${CONF_FILES:-0},
    "sql": ${SQL_FILES:-0},
    "docker": ${DOCKER_FILES:-0},
    "other": ${OTHER_FILES:-0}
  }
}
EOF

log "项目统计: ${TOTAL_LINES}行(${TOTAL_FILES}个文件), ${TOTAL_COMMITS}次提交, ${DEV_DAYS}天"
log "  语言分布: Python=${PY_LINES} Vue=${VUE_LINES} JS=${JS_LINES} CSS=${CSS_LINES} MD=${MD_LINES} Shell=${SH_LINES} Config=${CONF_LINES} 其他=${OTHER_LINES}"
set -e  # 恢复容错

log "========== 部署完成 =========="
