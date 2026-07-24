# PWA Push VAPID 持久化部署指南 (2026-07-24)

W68 第 10 批 C-3: VAPID 密钥持久化部署必做文档 (锚点范式第 130 守恒).

## 0. 背景与风险

### 0.1 风险描述

W68 第 7 批 B-3 PWA Push Backend 已实施 (commit `b31386d61`), 但 **没做**
部署必做的 VAPID 持久化机制:

- VAPID 密钥启动时生成, 默认存 `/data/push/vapid_*.pem`
- **没做**: 部署必做目录创建 + docker volume mount + 持久化脚本
- **后果 (主指挥部署会触发)**:
  - `docker compose restart app` → VAPID 重新生成
  - 旧 subscription 用老公钥 push, 服务端签名私钥变了 → 推送 401/403 失败
  - 用户需手动重新订阅 (浏览器弹"允许通知" → UX 灾难)

### 0.2 风险等级

**P0 高 — 部署前必做**. 主指挥 SSH 跑 `setup_vapid_persistence.sh` 后
再 `docker compose restart app`, 否则首日部署后所有用户推送失效.

### 0.3 与现有部署链路的关系

- 与 `docs/mobile-pwa-push-backend.md` 第 2 节"部署必做"互补
- 与 `scripts/deploy-auto.sh` 解耦 (本脚本是手动 SSH 跑, 不进自动部署链路)

---

## 1. 部署必做 (主指挥 SSH 执行)

### 1.1 docker-compose.yml 加 volume mount

**位置**: `docker-compose.yml` `app` service.

```yaml
services:
  app:
    # ... 原有配置 ...
    volumes:
      - /data/push:/data/push:rw  # VAPID 密钥持久化 (W68 第 10 批 C-3)
```

**Linux 云 server** (agent.mnb-lab.cn) 的 `/data/push/` 路径:
- 物理目录在主机文件系统 (非 NFS / 非共享存储)
- 容器内 `/data/push` 与主机 `/data/push` **同一路径** (无路径映射)
- 权限: root:root 755 (容器内通常 root 启动)

**为什么不是 bind mount 到其他路径?**
- `/data/push` 已在 `app/services/push_service.py` 硬编码默认
- 不绑 `.:/data/push` 是防部署到本地 PC 测试时, Windows 路径冲突
- 改动需同步改 `push_service.py` 默认值 + `setup_vapid_persistence.sh`

### 1.2 跑设置脚本

```bash
cd /path/to/microbubble-agent
bash scripts/setup_vapid_persistence.sh --apply
```

**脚本职责** (5 步):
1. 创建 `/data/push/` 持久化目录 (主机 + 容器两侧)
2. 检查是否已有 VAPID 密钥 (`vapid_private.pem` + `vapid_public.pem`)
3. 如有: 提示 "已存在, 跳过" + 输出公钥 (对账用)
4. 如无: 触发 `docker compose restart app` → lifespan init 生成 + 持久化
5. 输出公钥 base64url (浏览器 subscribe 用)

**支持参数**:
- `--apply` (默认 dry-run, 必须加才真跑)
- `--reset` (强制重新生成, **警告**: 旧订阅失效)
- `--check` (仅检查状态, 不创建/不重启)
- `--help` (用法说明)

**预期输出**:
```
[VAPID-SETUP] ✓ docker CLI 可用
[VAPID-SETUP] ✓ REPO_ROOT = /home/agent/microbubble-agent
[VAPID-SETUP] 未发现现有 VAPID 密钥
[VAPID-SETUP] ✓ /data/push 已创建
[VAPID-SETUP] ✓ 容器 /data/push 已挂载
[VAPID-SETUP] ✓ docker compose restart app
[VAPID-SETUP] VAPID 公钥 (PEM):
  -----BEGIN PUBLIC KEY-----
  ...
  -----END PUBLIC KEY-----
[VAPID-SETUP] ✓ ========== 完成 ==========
```

### 1.3 (可选) `.env` 显式覆盖

```bash
# /path/to/microbubble-agent/.env
PUSH_VAPID_DIR=/data/push   # 默认值, 可省略
```

**何时需要覆盖**:
- 不想用默认路径 (如 `/var/lib/microbubble/push`)
- 部署在 NAS / 共享存储, 跨容器共享密钥
- 容器 rootless 模式, 路径需符合 non-root 用户

---

## 2. 验证 (主指挥对账)

### 2.1 公钥不变 (持久化生效)

```bash
# 重启 app 前
curl -sk https://agent.mnb-lab.cn/api/v1/push/vapid-public-key | python -m json.tool
# 期望: {"public_key": "BHZljYB97f0FurGyYaM7..."}  (key 1)

# docker compose restart app

# 重启后
curl -sk https://agent.mnb-lab.cn/api/v1/push/vapid-public-key | python -m json.tool
# 期望: {"public_key": "BHZljYB97f0FurGyYaM7..."}  (key 1, **相同**)
```

**判定**:
- 2 次返回 **相同 public_key** → 持久化生效 ✅
- 2 次返回 **不同 public_key** → 持久化失败 (docker volume 未挂载) ❌

### 2.2 旧订阅者仍能收推送

```bash
# 1. 前端先 subscribe (浏览器弹"允许通知")
# 2. docker compose restart app
# 3. 触发测试推送
curl -sk -X POST https://agent.mnb-lab.cn/api/v1/push/admin/test \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"user_id": <原订阅者ID>, "title": "持久化验证", "body": "重启后仍能收"}'
# 期望: {"delivered": 1, "failed": 0, "purged": 0}
```

**判定**:
- delivered = 1, failed = 0 → 持久化生效 ✅
- delivered = 0, failed > 0 → VAPID 私钥变了, 旧订阅失效 ❌

### 2.3 文件持久化验证

```bash
# 主机侧
ls -la /data/push/
# 期望:
# -rw------- 1 root root 1675 Jul 24 16:30 vapid_private.pem
# -rw-r--r-- 1 root root  471 Jul 24 16:30 vapid_public.pem

# 容器侧
docker exec microbubble-agent-app-1 ls -la /data/push/
# 期望: 同上 (同一份文件 via volume)
```

---

## 3. 备份策略

### 3.1 季度备份 (推荐 cron)

```bash
# /etc/cron.weekly/backup-vapid.sh
#!/bin/bash
set -e
BACKUP_DIR="/backup/vapid-$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"
cp -r /data/push "$BACKUP_DIR"
echo "VAPID 备份完成: $BACKUP_DIR"
# 保留最近 4 季度
find /backup -maxdepth 1 -name "vapid-*" -mtime +120 -exec rm -rf {} \;
```

### 3.2 异地容灾 (建议加 scp)

```bash
# /etc/cron.monthly/backup-vapid-remote.sh
#!/bin/bash
set -e
LOCAL_BACKUP="/data/push"
REMOTE_HOST="backup-server.local"
REMOTE_DIR="/remote-backup/vapid/$(date +%Y%m)"
mkdir -p "$REMOTE_DIR"
scp -r "$LOCAL_BACKUP/vapid_*.pem" "root@${REMOTE_HOST}:${REMOTE_DIR}/"
```

### 3.3 备份恢复

```bash
# 1. 停 app
docker compose stop app

# 2. 恢复备份
rm -rf /data/push
cp -r /backup/vapid-20260101/* /data/push/
chmod 600 /data/push/vapid_private.pem

# 3. 启 app
docker compose start app

# 4. 验证 (同第 2 节)
curl -sk https://agent.mnb-lab.cn/api/v1/push/vapid-public-key
```

---

## 4. 回滚策略

### 4.1 软回滚: 重置 VAPID 密钥

```bash
# 警告: 所有现有 subscription 失效, 用户需重新订阅
bash scripts/setup_vapid_persistence.sh --reset --apply
```

**触发场景**:
- 怀疑密钥泄漏 (push service 返回 401 异常)
- 主动轮换密钥 (季度安全审计)
- 备份恢复失败, 只能重置

### 4.2 硬回滚: 删除目录 + 重启 app

```bash
# 1. 警告用户 (重要!)
echo "PWA 推送将重新订阅, 请重新点击允许通知"

# 2. 删除持久化目录
docker exec microbubble-agent-app-1 rm -rf /data/push/*
# 或主机侧: rm -rf /data/push/*

# 3. 重启 app → 重新生成 VAPID
docker compose restart app

# 4. 验证 (同第 2 节, 但旧订阅者 delivered = 0 是预期的)
curl -sk https://agent.mnb-lab.cn/api/v1/push/vapid-public-key
# 期望: 新 public_key (与历史值不同)
```

### 4.3 紧急回滚: 关闭 PWA 推送

```bash
# 1. 前端 useMobilePushNotification.ts 加 disable flag
# 2. 或在 settings.py 加 PUSH_ENABLED = False (代码改动, 走常规 PR)
# 3. 或 nginx /api/v1/push/* 直接 return 503 (临时)
```

---

## 5. 监控与告警

### 5.1 健康检查端点

```bash
# VAPID 来源 (file 持久化生效 / memory 重启失效)
docker exec microbubble-agent-app-1 curl -s http://localhost:8000/api/v1/push/health
# 期望: {"vapid_source": "file", "key_age_seconds": 86400}
# (memory 模式应立即告警 → 持久化失效)
```

### 5.2 日志监控

```bash
# 启动时正确日志 (持久化生效)
[PUSH] VAPID 密钥从文件加载: /data/push/vapid_private.pem (持久化生效, 旧订阅者保留)

# 启动时异常日志 (持久化失效, 重启生成新 key)
[PUSH] VAPID 密钥已生成 + 持久化: /data/push/vapid_private.pem (注意: 旧订阅者需重新订阅)

# 严重异常 (持久化失败, 用内存)
[PUSH] VAPID 持久化失败, 用内存密钥 (重启会丢): PermissionError(...)
```

### 5.3 推送失败率告警

```bash
# push_to_user 返回 failed > 阈值 → 推送服务异常 (可能 VAPID 失效)
# 监控 Redis dead letter queue 长度
docker exec microbubble-agent-redis-1 redis-cli LLEN push:dead_letter
# 告警阈值: > 10/min 持续 5min
```

---

## 6. 已知问题与限制

### 6.1 容器重启期间推送丢失

- 推送**无离线持久化** (不像通知有 Redis offline queue)
- 重启期间到达的推送会直接 503/timeout
- **缓解**: 重启窗口尽量短 (< 5s, 通过零 downtime 部署)

### 6.2 密钥轮换无迁移期

- 当前 `_generate_and_save()` 单一私钥, 无 old/new 双接受期
- **未来 PR**: VAPID 密钥轮换 (迁移期同时接受 old/new)
- **临时**: 轮换期间会有 30-60s 推送失败期

### 6.3 备份文件泄漏风险

- `/data/push/vapid_private.pem` 等同 root 密码
- **纪律**: 备份目录权限 700 (root:root), scp 用专用密钥
- **审计**: 每月检查 `/backup/vapid-*` 目录权限

---

## 7. 跨文档引用

- [docs/mobile-pwa-push-backend.md](mobile-pwa-push-backend.md) — 原始 PWA Push Backend 部署文档
- [scripts/setup_vapid_persistence.sh](../scripts/setup_vapid_persistence.sh) — 本文档配套脚本
- [app/services/push_service.py](../app/services/push_service.py) — VAPID 服务实现
- [app/config.py](../app/config.py) — `PUSH_VAPID_DIR` 设置

---

## 8. 修改历史

| 日期 | Commit | 说明 |
|------|--------|------|
| 2026-07-24 | (本批) | W68 第 10 批 C-3 初始版本 (锚点范式第 130 守恒) |