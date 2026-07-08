#!/bin/bash
#
# install-frps-systemd.sh — 一键把 frps 注册为 systemd service
#
# 触发场景 (2026-07-02):
#   - frps 之前用 `nohup ... &` 启动, SSH shell 一关就跟着死
#   - frps 主进程死 → 派生 worker 仍占 8000/2222/9000 (孤儿状态)
#   - nginx proxy_pass 给孤儿 worker → RST → 502 (影响 2 小时没人察觉)
#
# 这个脚本:
#   1. 复制 scripts/frps.service 到 /etc/systemd/system/
#   2. systemctl daemon-reload
#   3. **关键**: 先 kill 当前 (可能 stale 的) frps 进程, 让 systemd 接管
#   4. systemctl enable --now frps
#   5. 验证 frps 在 7000/7500 + 派生 worker 在 8000/2222/9000
#
# 部署方式 (在云服务器 root):
#   bash install-frps-systemd.sh
#
# 回滚 (必要时):
#   sudo systemctl disable --now frps
#   sudo rm /etc/systemd/system/frps.service
#   sudo systemctl daemon-reload
#   # 然后手动 nohup 启动原 frps:
#   #   nohup /usr/local/bin/frps -c /etc/frp/frps.toml > /var/log/frps.log 2>&1 &

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err() { echo -e "${RED}[ERR]${NC} $*"; exit 1; }

# 1. 前置检查
log "1. 前置检查"
[[ -f /etc/frp/frps.toml ]] || err "/etc/frp/frps.toml 不存在, 请先确认 frp 已配置"
[[ -f /usr/local/bin/frps ]] || err "/usr/local/bin/frps 不存在, 请先安装 frps binary"

# 2. 复制 unit 文件
log "2. 复制 scripts/frps.service → /etc/systemd/system/frps.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -f "$SCRIPT_DIR/frps.service" ]]; then
    err "找不到 $SCRIPT_DIR/frps.service (脚本和 unit 文件必须在同一目录)"
fi
sudo cp "$SCRIPT_DIR/frps.service" /etc/systemd/system/frps.service
sudo chmod 644 /etc/systemd/system/frps.service
log "   ✅ /etc/systemd/system/frps.service"

# 3. reload systemd
log "3. systemctl daemon-reload"
sudo systemctl daemon-reload

# 4. **关键**: kill 当前可能 stale 的 frps 进程
log "4. kill 当前 frps 进程 (含派生 orphan workers)"
STALE_PIDS=$(pgrep -f "/usr/local/bin/frps -c /etc/frp/frps.toml" || true)
if [[ -n "$STALE_PIDS" ]]; then
    echo "   找到 stale frps PIDs: $STALE_PIDS"
    # -9 因为 frps 可能 hung, 普通 SIGTERM 杀不死
    sudo kill -9 $STALE_PIDS 2>/dev/null || true
    sleep 2
    log "   ✅ killed"
else
    log "   (没有运行中的 frps, skip)"
fi

# 顺手清理可能残留的孤儿 listener (8000/2222/9000)
log "   检查孤儿 listener"
ORPHAN_FDS=$(sudo lsof -ti :8000,:2222,:9000 2>/dev/null | grep -v "LISTEN\|sshd\|systemd" || true)
if [[ -n "$ORPHAN_FDS" ]]; then
    warn "   仍有进程占 8000/2222/9000, PID: $ORPHAN_FDS — 手动检查"
fi

# 5. enable + start
log "5. systemctl enable --now frps"
sudo systemctl enable frps
sudo systemctl start frps
sleep 3

# 6. 验证
log "6. 验证 frps 状态"
if ! sudo systemctl is-active --quiet frps; then
    err "frps service 没起来! 看日志: journalctl -u frps -n 50"
fi
log "   ✅ frps active (PID $(pgrep -f 'frps -c /etc/frp/frps.toml' | head -1))"

log "--- frps listen ---"
# P3-6 fix (2026-07-08): ss 命令 fallback 到 netstat (Alpine 极简镜像 / 微容器
# 可能没装 iproute2 ss 命令). command -v 探测 + fallback.
if command -v ss &> /dev/null; then
    sudo ss -tnlp 2>/dev/null | grep -E ":7000|:7500|:8000|:2222|:9000" || true
elif command -v netstat &> /dev/null; then
    sudo netstat -tnlp 2>/dev/null | grep -E ":7000|:7500|:8000|:2222|:9000" || true
else
    warn "ss 和 netstat 都不可用, 跳过端口检查 (安装 iproute2 或 net-tools)"
fi

log "--- 最后 10 行 frps log ---"
sudo tail -10 /var/log/frps.log 2>&1 | head -10 || true

log ""
log "🎉 安装完成! 验证 nginx 链路:"
log "   curl -sk -o /dev/null -w '%{http_code}\\n' https://agent.mnb-lab.cn/api/v1/auth/me"
log "   # 期望: 401 (backend alive) — 不是 502 (链路断)"
log ""
log "📋 部署后必做 (本地 Windows):"
log "   Tasklist /FI \"IMAGENAME eq frpc.exe\"   # 看 frpc 是否在跑"
log "   如果 0 进程, 启动:"
log "     Start-Process -FilePath 'X:\\path\\frpc.exe' -ArgumentList '-c', 'X:\\path\\frpc.toml' -WindowStyle Hidden"
log "   ⚠️  注意 frpc.exe 版本必须与 frps 匹配 (建议都用 0.61.1)"
