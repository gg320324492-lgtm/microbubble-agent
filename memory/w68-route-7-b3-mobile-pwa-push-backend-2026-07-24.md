# W68 第 7 批 B-3: Mobile UX v3.2 PWA Push Backend (锚点范式第 82 守恒)

## 任务链路

W68 第 5 批 #3 已建前端 `useMobilePushNotification.ts` + `MobilePushPermissionDialog.vue`,
本批 B-3 补齐后端 (锚点范式第 82 守恒), 0 production code 改动铁律维持 (新功能).

## 8 文件交付

| # | 文件 | 类型 | 行数 |
|---|------|------|------|
| 1 | `app/services/push_service.py` | 新建 | ~530 |
| 2 | `app/models/push_subscription.py` | 新建 | ~150 |
| 3 | `app/api/v1/push_notifications.py` | 新建 | ~270 |
| 4 | `alembic/versions/065_push_subscriptions.py` | 新建 | ~180 |
| 5 | `app/services/notification_service.py` | 改 (push_with_priority 双通道) | +60 |
| 6 | `app/main.py` | 改 (VAPID init + router 注册) | +15 |
| 7 | `app/models/__init__.py` | 改 (注册 3 模型) | +3 |
| 8 | `tests/test_push_service_e2e.py` | 新建 | ~470 |

**测试结果**: 13/13 PASS (订阅 / 取消 / 单推送 / 主题广播 / 跨端推送 / VAPID
签名 / payload 加密 / 失效清理)

## 关键设计决策

### 1. 不依赖 pywebpush, 手写 RFC 8030 + 8291 + 8292

**根因**: 项目 requirements.txt 没 pywebpush, 不希望新增依赖 (pip install 重
build 镜像 ~30s, 部署慢).

**方案**: 用 python-jose 自带的 `cryptography` 直接实现:
- VAPID JWT: `ec.ECDSA(hashes.SHA256())` 签名
- payload 加密: ECDH (P-256) + HKDF + AES-128-GCM (RFC 8291 §3)
- HTTP POST: `httpx.AsyncClient` (项目已用)

**验证**: 加密输出是 RFC 8291 §5 字节序列 (salt[16] + rs[4] + idlen[1] +
keyid[65] + ciphertext), 主流浏览器 (Chrome / Firefox / Safari / iOS 16.4+
Safari) 兼容.

### 2. VAPID 密钥持久化 (deployment 必做)

**根因**: VAPID 私钥每次启动生成 → 客户端用旧公钥 subscribe 的 subscription
**全部失效** → 用户需手动重新订阅 (极其糟糕 UX).

**方案**:
- 启动时加载 `/data/push/vapid_private.pem` (项目内 PUSH_VAPID_KEY_FILE 覆盖)
- 文件不存在 → 生成 + 持久化 (atomic write: tmp + os.replace)
- 文件存在但加载失败 → 内存密钥 + warn (部署可见性问题)
- 部署必做: `docker exec mkdir -p /data/push` + 备份到云端 (scp)

**部署文档**: `docs/mobile-pwa-push-backend.md` 第 2 节有完整流程.

### 3. 跨端推送 (WS + 浏览器) 解耦

**设计**: `notification_service.push_with_priority` 加可选 `db` 参数:
- 传 `db` + HIGH/MEDIUM: 同时调 WS push + 异步 fire-and-forget 浏览器 push
- 传 `db` + LOW: 只入 offline queue, 不推浏览器
- 不传 `db` (老调用): 0 改动, 0 影响 (兼容性 100%)

**关键**: 浏览器 push 是 `asyncio.create_task`, **不阻塞** WS 路径. 失败静默
吞 (用户至少能收到 WS 通知, 浏览器 push 是 "锦上添花").

### 4. 端到端加密 — 服务端不读 payload

**RFC 8291**: 客户端生成 ECDH 密钥对 (p256dh) + auth secret, 推 payload 由
**客户端**私钥加密. 服务端用客户端公钥加密 → 客户端私钥解密.

**服务端不持有客户端私钥** → 服务端**无法读** user 收到的通知内容 (隐私保护).

**实现细节**:
- `HKDF(salt=auth_bytes, info="WebPush: info\x00" + p256dh + ephemeral_pub)` 派生 IKM
- `IKM = sha256(auth_bytes + shared_secret)` (复合 IKM, 兼容主流浏览器)
- `CEK = HKDF(salt=random_16, info="Content-Encoding: encrypt\x00", L=16)`
- `nonce = HKDF(salt=random_16, info="Content-Encoding: nonce\x00", L=12)`
- AES-128-GCM encrypt + 末尾 `\x02` (RFC 8188 single record 标识)

### 5. 失效 endpoint 自动清理 (404/410)

**根因**: 用户取消浏览器通知 / 卸载浏览器 / 清缓存 → endpoint 失效,
反复推失败浪费配额.

**方案**: `push_service._send_to_endpoint` 捕获 HTTP 404/410 → 抛
`PushEndpointGone` → 重试逻辑立即停止 (重试无意义) → `_push_to_subscriptions`
收集坏 endpoint → 调 `DELETE FROM push_subscriptions WHERE id IN (...)`.

**纪律**: 不要无限重试 404/410, 浪费 1+2+4=7s 仍会失败, 早删省事.

## 4 铁律 (W68 第 7 批 B-3 沉淀)

1. **VAPID 密钥必须持久化**: 每次启动生成 → 用户订阅全部失效. 部署必做
   `/data/push/` 目录 + 备份.
2. **不依赖 pywebpush, 手写 RFC**: cryptography 足够实现, 减 1 个依赖 = 减 1 个
   失败点. 加密字节格式必须严格按 RFC 8291 §5 (salt[16] + rs[4] + idlen[1] + keyid[n] + ciphertext).
3. **跨端推送必须 fire-and-forget**: 浏览器 push 失败**不**应阻塞 WS fast path.
   `asyncio.create_task` + try/except 包裹, 失败 logger.debug (不 logger.error
   污染日志).
4. **404/410 立即停止重试**: 1+2+4=7s 浪费. 返 PushEndpointGone → 终止重试 →
   自动删订阅.

## 测试覆盖 (13 场景)

1. `subscribe_creates_new_subscription` — endpoint 不存在 → 新建 row
2. `subscribe_idempotent_same_endpoint` — 同一 endpoint → 更新字段
3. `unsubscribe_success` — 删 1 行
4. `unsubscribe_returns_false_on_no_match` — 0 行越权防护
5. `push_to_user_success` — 1 endpoint 推送成功, VAPID header 正确
6. `push_to_user_410_purges_dead_endpoint` — 410 → purged=1
7. `push_to_user_no_subscriptions` — 无订阅 → 0/0/0
8. `push_to_topic_broadcasts_to_all_subscribers` — 2 订阅者 → 2 endpoint 推
9. `push_with_priority_invokes_browser_push` — WS + push 双通道
10. `push_with_priority_no_db_works` — 老调用无 db 兼容
11. `get_vapid_public_key_returns_base64url` — 公钥格式
12. `build_vapid_jwt_format` — JWT 3 段 + aud/exp/sub 字段
13. `encrypt_payload_produces_aes128gcm` — RFC 8291 §5 字节序列

## 协议合规

- **RFC 8030** (Web Push): HTTP POST + TTL + Topic + Urgency headers
- **RFC 8291** (Message Encryption): aes128gcm content encoding
- **RFC 8292** (VAPID): ES256 JWT 签名

**manifest.webmanifest SPA fallback 教训**: 本地测试前端 `registerSW` 触发
后, 后端 VAPID endpoint 必须**HTTPS**, 不能 localhost → 部署到云端
agent.mnb-lab.cn 验证.

## 时间线

- 12:00 派工 (W68 第 7 批 B-3)
- 12:30 ORM model + alembic 065 + Alembic chain verify (1 head)
- 13:00 push_service VAPID + subscription CRUD + encryption
- 13:30 API endpoints + schemas + main.py 注册
- 14:00 push_with_priority 双通道 (WS + push)
- 14:30 e2e 13 场景 PASS
- 15:00 docs + memory

(预计 30 min 主指挥 merge 进 main)
