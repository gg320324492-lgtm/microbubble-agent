#!/bin/bash
# MicroBubble Agent - Docker Desktop GUI 重启后一键恢复脚本
# 调用: bash scripts/restart-recovery-after-gui-restart.sh
# 前置: 用户已 Docker Desktop Quit + 重新启动 (图标变绿)
# 用途: 自动 attach app 到 network + 验证本地+服务器 7 个端点全部恢复

set -uo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

echo "============================================"
echo " Docker Desktop GUI 重启后一键恢复"
echo "============================================"

# Step 1: 验证 Docker Desktop GUI 已就绪
echo "--- Step 1: 检查 Docker daemon ---"
if ! docker info >/dev/null 2>&1; then
  fail "Docker daemon 无响应, GUI 重启未完成"
fi
RUNNING=$(docker ps --format "{{.Names}}" 2>&1 | wc -l)
ok "Docker daemon 在线, 当前 $RUNNING containers 跑着"

# Step 2: 补 .env (worktree 下可能缺失)
echo "--- Step 2: 补 .env (worktree 路径) ---"
if [ ! -f ".env" ] && [ -f "../.env" ]; then
  cp ../.env .env && ok "复制 .env 到 worktree 路径"
elif [ -f ".env" ]; then
  ok ".env 已存在"
else
  warn ".env 缺失且找不到 ../.env, 继续 (可能 .env 在别处)"
fi

# Step 3: 验证 app-1 是否在 default network
echo "--- Step 3: 验证 app-1 在 default network ---"
APP_ON_NET=$(docker network inspect microbubble-agent_default --format '{{range .Containers}}{{.Name}} {{"\n"}}{{end}}' 2>/dev/null | grep -c "microbubble-agent-app-1" || true)
if [ "$APP_ON_NET" = "0" ]; then
  warn "app-1 漏 attach 到 default network, 自动 attach"
  docker network connect --alias app microbubble-agent_default microbubble-agent-app-1 2>&1 || fail "attach 失败, 请确认 Docker Desktop GUI 已完全启动"
  ok "app-1 已 attach"
else
  ok "app-1 已在 default network"
fi

# Step 4: 验证 DNS
echo "--- Step 4: 验证容器 DNS 解析 ---"
DB_IP=$(docker exec microbubble-agent-app-1 bash -c "getent hosts microbubble-agent-db-1" 2>/dev/null | awk '{print $1}' | head -1)
if [ -z "$DB_IP" ]; then
  fail "DNS 解析失败, Docker Desktop 端口转发缓存可能没清. 请确认 GUI 是 Quit 后重新启动, 不是仅重启系统"
fi
ok "DNS 解析 OK: db-1 = $DB_IP"

# Step 5: 验证本地 /health
echo "--- Step 5: 验证本地 /health ---"
LOCAL_CODE=$(curl -sk -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health 2>&1)
if [ "$LOCAL_CODE" != "200" ]; then
  fail "本地 /health = $LOCAL_CODE, app 还没起来"
fi
ok "本地 /health = 200"

# Step 6: 验证服务器 7 个端点
echo "--- Step 6: 验证服务器 7 个端点 ---"
SERVER_ENDPOINTS=(
  "/health"
  "/api/v1/auth/me"
  "/api/v1/members?page_size=100"
  "/api/v1/meetings?status=recording&page_size=1"
  "/api/v1/tasks?page_size=100"
  "/api/v1/notifications?unread_only=false&limit=50"
  "/api/v1/dashboard/stats"
)
PASS=0
TOTAL=${#SERVER_ENDPOINTS[@]}
for ep in "${SERVER_ENDPOINTS[@]}"; do
  code=$(curl -sk -o /dev/null -w "%{http_code}" "https://agent.mnb-lab.cn$ep" 2>&1)
  case "$ep" in
    /health) expected="200";;
    *)       expected="401";;
  esac
  if [ "$code" = "$expected" ]; then
    ok "  $ep → $code (期望 $expected)"
    PASS=$((PASS+1))
  else
    warn "  $ep → $code (期望 $expected)"
  fi
done
echo "  PASS: $PASS / $TOTAL"
[ "$PASS" = "$TOTAL" ] && ok "服务器全部恢复" || fail "服务器部分仍异常, 看上方"

# Step 7: 5 件套守恒验证
echo "--- Step 7: 5 件套守恒验证 ---"
HEAD=$(docker exec microbubble-agent-app-1 python -m alembic heads 2>&1 | head -1)
[ "$HEAD" = "105_fix_drift (head)" ] \
  && ok "alembic head 守恒: $HEAD" \
  || fail "alembic head 漂移: $HEAD (期望 105_fix_drift)"

CELERY=$(docker exec microbubble-agent-celery-worker-1 celery -A app.core.celery inspect ping --timeout 5 2>&1 | grep -c "pong")
[ "$CELERY" -ge "1" ] && ok "celery worker 响应 ($CELERY pong)" || fail "celery worker 无响应"

# Step 8: 提示用户清理浏览器 (类 20.155, 后端 JWT 无法清前端缓存)
echo "--- Step 8: 提示用户清理浏览器 (前端 JWT 已过期) ---"
echo "  后端 API 全恢复, 但浏览器 localStorage 仍缓存旧 access_token + refresh_token."
echo "  单纯 reload 会触发 401 → /auth/refresh → 限流 → 429 → redirect 循环."
echo "  用户必须执行:"
echo "    1) 浏览器 DevTools → Application → Storage → Clear site data"
echo "    2) 或浏览器右上角 avatar → 退出登录 (若按钮可见)"
echo "    3) 硬刷 Ctrl+Shift+R"
echo "    4) 重新输入账号密码登录"
echo "  原因: refresh_token 7 天过期, 即使服务端仍健康, 旧 token 无法续命"
echo "  根因 / 修复 / 铁律: 类 20.155 (memory/server-shutdown-refresh-429-loop-2026-08-13.md)"
ok "前端清理步骤已显示"

echo ""
echo "============================================"
echo -e "${GREEN} 全部恢复完成${NC}"
echo "============================================"
echo "下次开机恢复指南: docs/w100-meeting-pipeline-restart-2026-08-04.md"