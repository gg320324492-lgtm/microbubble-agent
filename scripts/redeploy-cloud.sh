#!/usr/bin/env bash
# 手动补部署 —— 云端 webhook 投递**偶发失败**时用这个（2026-10-25）
#
# 背景: 部署链路是 `push → GitHub webhook → 云端 nginx → webhook.py(9001) → deploy-auto.sh`。
#   2026-10-25 实测有一次投递返回 **502 且请求根本没到云端 nginx**(GitHub deliveries 里
#   status=502、云端 access.log 无记录) ⇒ 表现为「push 成功、CI 绿, 但线上没更新」。
#   主指挥 2026-10-25 拍板: **不装自动补部署定时任务, 失败时手动补** ⇒ 本脚本就是那条手动路径。
#
# 用法:
#   bash scripts/redeploy-cloud.sh            # 补部署 + 校验
#   DEPLOY_HOST=... DEPLOY_KEY=... bash scripts/redeploy-cloud.sh
#
# 判据(类 20.220: 别信日志, 看副作用):
#   **云端 HEAD == 本地 HEAD** 且 生产 /health 200 ⇒ 真的更新了。
#   「push 成功」「CI 全绿」「部署日志没报错」都**不能**证明线上已更新。

set -uo pipefail

HOST="${DEPLOY_HOST:-agent.mnb-lab.cn}"
KEY="${DEPLOY_KEY:-$HOME/.ssh/id_ed25519}"
REMOTE_DIR="${DEPLOY_DIR:-/opt/microbubble-agent}"
PROD="${DEPLOY_PROD:-https://agent.mnb-lab.cn}"

LOCAL_SHA=$(git rev-parse HEAD 2>/dev/null || echo "")
LOCAL_SHORT=$(git log --oneline -1 2>/dev/null || echo "")
echo "==> 本地 HEAD : $LOCAL_SHORT"

echo "==> 补部署到 $HOST ..."
LOG_TMP=$(mktemp)
ssh -o BatchMode=yes -o ConnectTimeout=20 -i "$KEY" "root@$HOST" \
  "cd '$REMOTE_DIR' && bash scripts/deploy-auto.sh" >"$LOG_TMP" 2>&1
SSH_RC=$?
tail -n 12 "$LOG_TMP"
if [ "$SSH_RC" -ne 0 ]; then
  echo "!! SSH/部署返回非 0 (rc=$SSH_RC)，完整日志: $LOG_TMP"
  exit "$SSH_RC"
fi
rm -f "$LOG_TMP"

echo "==> 云端 HEAD :"
REMOTE_SHA=$(ssh -o BatchMode=yes -o ConnectTimeout=20 -i "$KEY" "root@$HOST" \
  "git -C '$REMOTE_DIR' rev-parse HEAD 2>/dev/null || echo ''")
echo "    $REMOTE_SHA"

echo "==> 生产探活 :"
curl -sk -o /dev/null -w "    health=%{http_code}\n" "$PROD/health"
curl -sk -o /dev/null -w "    root=%{http_code}\n" "$PROD/"

if [ -n "$LOCAL_SHA" ] && [ "$REMOTE_SHA" = "$LOCAL_SHA" ]; then
  echo "✅ 云端 HEAD 与本地一致 ⇒ 线上已是最新"
else
  echo "⚠️  云端 HEAD 与本地不一致 ⇒ 线上还没更新, 检查上面的部署日志"
  exit 1
fi
