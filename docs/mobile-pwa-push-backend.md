# Mobile v3.2 PWA Push Backend (2026-07-24)

W68 第 7 批 B-3: Mobile UX v3.2 PWA 浏览器推送 backend (锚点范式第 82 守恒).

## 背景

W68 第 5 批 #3 已建前端 `web/src/composables/useMobilePushNotification.ts` +
`MobilePushPermissionDialog.vue`. 后端补齐:
- VAPID 密钥生成 + 持久化
- 浏览器 subscription 持久化 (1 用户多端)
- Web Push 触发 (RFC 8030 + RFC 8291 + RFC 8292)
- 主题广播 (push_topics)
- 跨端推送 (WS + 浏览器原生 push)

## 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│  浏览器 (前端)                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Service Worker (sw.js)                                   │  │
│  │ 1. pushManager.subscribe({ userVisibleOnly: true,        │  │
│  │    applicationServerKey: <VAPID 公钥> })                 │  │
│  │ 2. 收到 push → 显示通知 (showNotification)               │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ POST /api/v1/push/subscribe
                         │ (subscription JSON)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  后端 (FastAPI)                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ GET /api/v1/push/vapid-public-key                        │  │
│  │   → 返 VAPID 公钥 (base64url)                             │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ POST /api/v1/push/subscribe                              │  │
│  │   → 存 push_subscriptions + push_topic_subscriptions     │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ POST /api/v1/push/admin/test                             │  │
│  │   → admin 测试推送 (单用户 / topic)                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         ↓                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ push_service.push_to_user(user_id, title, body, data)    │  │
│  │   → 1. 查 push_subscriptions 找该用户所有 endpoint       │  │
│  │   → 2. ECDH + AES-128-GCM 加密 payload (RFC 8291)        │  │
│  │   → 3. VAPID JWT 签名 (RFC 8292)                          │  │
│  │   → 4. HTTP POST 到 push service (RFC 8030)              │  │
│  │   → 5. 404/410 → 自动删订阅                               │  │
│  │   → 6. 5xx/429 → 3 次指数退避重试                          │  │
│  │   → 7. 失败入 Redis dead letter queue (7 天 TTL)         │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP POST (encrypted)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Push Service (Mozilla / Google / Apple)                         │
│  → 平台特定推送网关 (FCM / Mozilla autopush / APNs)              │
└─────────────────────────────────────────────────────────────────┘
```

## 8 文件清单

| 文件 | 职责 | 行数 |
|------|------|------|
| `app/services/push_service.py` | VAPID + subscription CRUD + 推送触发 | ~530 |
| `app/models/push_subscription.py` | PushSubscription / PushTopic / PushTopicSubscription | ~150 |
| `app/api/v1/push_notifications.py` | 5 REST endpoints + 6 schemas | ~270 |
| `alembic/versions/065_push_subscriptions.py` | 3 表 + 索引 + 约束 | ~180 |
| `app/services/notification_service.py` (改) | push_with_priority 双通道 (WS + push) | +60 |
| `app/main.py` (改) | VAPID init + router 注册 | +15 |
| `app/models/__init__.py` (改) | 注册 3 个模型 | +3 |
| `tests/test_push_service_e2e.py` | 13 场景单元测试 | ~470 |

## 部署必做

### 1. 跑数据库迁移

```bash
# 复制 alembic 065 到 docker 容器
docker cp alembic/versions/065_push_subscriptions.py microbubble-agent-app-1:/app/alembic/versions/

# 清除 __pycache__ (CLAUDE.md 752 行铁律)
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__

# 跑迁移
docker exec microbubble-agent-app-1 alembic upgrade head

# 验证 3 张表存在
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\dt" | grep push
# 期望:
#  push_subscriptions
#  push_topic_subscriptions
#  push_topics
```

### 2. VAPID 密钥持久化

**重要**: VAPID 密钥**必须**持久化到磁盘, 否则每次重启生成新 key → 所有用户
subscription 失效 → 用户需手动重新订阅.

```bash
# 1. 创建持久化目录
docker exec microbubble-agent-app-1 mkdir -p /data/push

# 2. 启动后端 → 自动生成 + 持久化
docker compose restart app

# 3. 验证密钥文件存在
docker exec microbubble-agent-app-1 ls -la /data/push/
# 期望:
#  vapid_private.pem
#  vapid_public.pem

# 4. 备份到云端 (asset 备份 + 异地容灾)
scp root@server:/data/push/vapid_*.pem /local/backup/
```

**环境变量** (可选, 默认值见 `app/services/push_service.py`):
- `PUSH_VAPID_KEY_FILE` — 私钥 PEM 文件路径 (默认 `/data/push/vapid_private.pem`)
- `PUSH_VAPID_PUBLIC_KEY_FILE` — 公钥 PEM 文件路径 (默认 `/data/push/vapid_public.pem`)
- `PUSH_VAPID_SUBJECT` — VAPID JWT `sub` 字段 (默认 `mailto:admin@mnb-lab.cn`)

### 3. HTTPS 必需 (浏览器强制)

Web Push API **强制要求 HTTPS** (RFC 8030 §3). 本项目 `agent.mnb-lab.cn` 已通
Let's Encrypt + Nginx, 无需额外配置.

**本地开发** (localhost) 也支持, 因为 `localhost` 视为安全上下文.

### 4. 验证

```bash
# 1. 后端 VAPID 公开密钥
curl -sk https://agent.mnb-lab.cn/api/v1/push/vapid-public-key | python -m json.tool
# 期望: {"public_key": "BHZljYB97f0FurGyYaM7..."}

# 2. 前端加载 (iOS Safari + Android Chrome + Desktop Chrome)
# 登录 -> 设置 -> 启用 PWA 推送 -> 浏览器弹"允许通知" -> 授权

# 3. admin 测试推送
curl -sk -X POST https://agent.mnb-lab.cn/api/v1/push/admin/test \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "title": "测试", "body": "Hello from server"}'
# 期望: {"delivered": 1, "failed": 0, "purged": 0}
```

## 5 REST 端点

| 方法 | 路径 | 鉴权 | 用途 |
|------|------|------|------|
| GET | `/api/v1/push/vapid-public-key` | 公开 | 客户端 subscribe 用 |
| POST | `/api/v1/push/subscribe` | 登录 | 存 subscription |
| DELETE | `/api/v1/push/subscribe` | 登录 | 取消订阅 |
| POST | `/api/v1/push/subscribe/heartbeat` | 登录 | 更新 last_seen_at |
| GET | `/api/v1/push/subscriptions` | 登录 | 列当前用户所有订阅 |
| POST | `/api/v1/push/admin/test` | admin | 测试推送 |

## 协议合规

- **RFC 8030** (Web Push): HTTP POST + TTL + Topic + Urgency headers
- **RFC 8291** (Message Encryption): aes128gcm content encoding
- **RFC 8292** (VAPID): ES256 JWT 签名

**不**依赖 `pywebpush` (项目未安装), 手写实现 RFC 8030 + 8291 + 8292,
依赖仅 `cryptography` (python-jose 已带).

## 跨端推送 (WS + 浏览器)

`notification_service.push_with_priority` 接收 `db` 参数后:
- HIGH/MEDIUM: 同时调 WS push (在线) + 异步 fire-and-forget 浏览器 push
- LOW: 只入 offline queue, 不推浏览器

**兼容性**: 未传 `db` 时**只**走 WS fast path (老调用方式零影响).

## 已知限制

1. **endpoint 失效清理**: 404/410 立即删, 5xx/429 重试 3 次 (1s/2s/4s 退避)
2. **dead letter queue**: 失败入 Redis list, 7 天 TTL, 运维手动重投递
3. **payload 加密**: 端到端 (浏览器内 SW 解密), 服务端**不**能读
4. **多端订阅**: 1 用户多端 (PC + iOS + Android), 全部推送

## 未来 PR (W69+)

- VAPID 密钥轮换 (迁移期同时接受 old/new)
- push_to_topic 权限模型 (admin 控制谁能广播)
- 推送统计 dashboard (高峰期 / 失败率)
- Web Push 多语言 payload (i18n)
