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
# ---- alembic 守恒: 校验「不变量」, 不写死 head 编号 ----
# 【为什么不能写死编号】CLAUDE.md 明文纪律: "写断言时用「恰为 1 个 head」不变量,
# 别写死编号"(084/085/087 三连修正先例)。原实现在此写死 105_fix_drift —— 那是
# 2026-08-05 当时的 head, 之后每加一个迁移就必然失配。2026-10-09 15:15 手动触发
# 自愈即因此误判: 前 7 步含 7/7 端点全绿, 却在这最后一步 fail, 上报
# success:false。改成校验两条不变量后, head 推进无需再动脚本:
#   1) `alembic heads` 恰为 1 个 —— 0 个 = 链损坏/迁移目录不可读;
#      >1 个 = 双头, `alembic upgrade head` 会报 Multiple head revisions 阻塞部署
#      (CLAUDE.md §2.3 串单链纪律 + 084/085/087 三连修正先例)。
#   2) `alembic current` == head —— DB 已应用版本与迁移链一致, 即 0 schema drift。
# 两条都是真守门: 真出现双头 / DB 落后于 head 时仍然 fail-fast, 不降级为 warn。
# 注意: `alembic heads` 只写 stdout; `alembic current` 的 INFO 前缀行写 stderr,
# 所以两者都取 2>/dev/null 后再解析 (原实现的 `2>&1 | head -1` 在 current 上
# 会抓到 INFO 行而非版本号 —— 第二个潜在 bug, 一并修掉)。
ALEMBIC_HEADS=$(docker exec microbubble-agent-app-1 python -m alembic heads 2>/dev/null); HEADS_RC=$?
if [ "$HEADS_RC" -ne 0 ]; then
  fail "alembic heads 执行失败 (rc=$HEADS_RC), 容器内迁移目录可能不可读"
fi
HEAD_COUNT=$(printf '%s\n' "$ALEMBIC_HEADS" | grep -c '[^[:space:]]' || true)
if [ "$HEAD_COUNT" -ne 1 ]; then
  fail "alembic head 数 = $HEAD_COUNT (期望恰为 1; 双头会阻塞部署). 实际: [$(printf '%s' "$ALEMBIC_HEADS" | tr '\n' ' ')]"
fi
# 取首行第一字段, 剥掉 "(head)" 后缀 → 纯 revision id
HEAD_REV=$(printf '%s\n' "$ALEMBIC_HEADS" | head -1 | awk '{print $1}')

ALEMBIC_CURRENT=$(docker exec microbubble-agent-app-1 python -m alembic current 2>/dev/null); CURRENT_RC=$?
if [ "$CURRENT_RC" -ne 0 ]; then
  fail "alembic current 执行失败 (rc=$CURRENT_RC), DB 不可达?"
fi
CURRENT_REV=$(printf '%s\n' "$ALEMBIC_CURRENT" | grep -v '^[[:space:]]*$' | head -1 | awk '{print $1}')
if [ -z "$CURRENT_REV" ]; then
  fail "alembic current 读不到 DB 已应用版本 (alembic_version 表可能为空或不可读)"
fi
if [ "$CURRENT_REV" != "$HEAD_REV" ]; then
  fail "alembic schema drift: DB current=$CURRENT_REV != head=$HEAD_REV (需手动 alembic upgrade head)"
fi
ok "alembic 守恒: 恰 1 head 且 current==head ($HEAD_REV)"

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