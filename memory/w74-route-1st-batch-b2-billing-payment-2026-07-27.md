# W74 第 1 批 B-2 计费真支付 mock 接入 (锚点范式 242 → 247 守恒 +5)

**派工**: W74 第 1 批 B-2 计费网关真支付接入 agent
**依据**: D-1 §3.2 W74 Step 5 (P0 主拍单独拍板) + W73 B-1 `a6835841` 计费接口预留 + 派工 v6 段 5 反馈 #6 实战
**plan 引用**: `docs/w72-commercialization-roadmap-2026-07-24.md` Q1 商业化扩展
**base HEAD**: `999276dda` (W73 第 1 批 grand closure 收口)
**目标**: 锚点范式 W73 第 1 批 242 → W74 第 1 批 B-2 247 守恒 (+5)
**0 production code 改动铁律例外 1 已批**（计费真支付 mock, 例同 W72 B-5 + W73 B-1 商业化）

## 5 大件交付

### 2.1 3 支付网关 mock 实现 (W74 B-2 关键)

`app/services/billing_gateway.py` 修改:
- 3 支付网关 (StripeBillingGateway / AlipayBillingGateway / WeChatPayBillingGateway) 全部从 `NotImplementedError` 骨架升级为 mock 实现
- 3 实现继承 `MockBillingGateway`, 仅覆盖 `provider_name` + 加 provider 特定字段
  - `StripeBillingGateway`: `publishable_key_prefix` + `webhook_secret_prefix`
  - `AlipayBillingGateway`: `app_id_prefix` + `sign_type = "RSA2"`
  - `WeChatPayBillingGateway`: `mch_id_prefix` + `api_v3_key_prefix`
- **3 实现仅 mock, 不接真支付** — 真接入须主拍单独拍板 (派工 v6 段 5 反馈 #6 实战)
- 共享内存存储 (进程级 `_intents` dict), 仅测试用
- 抽象基类 `BillingGateway` 新增 `verify_webhook_signature(payload, signature) -> bool` 抽象方法 (mock 默认 True)
- 新增 `list_supported_providers()` 工具函数

### 2.2 InvoiceService / PaymentService / SubscriptionService

**`app/services/billing/__init__.py`** 新建:
- 子包入口, 导出 BillingGateway / 4 实现 + PaymentIntent + PaymentResult + get_billing_gateway + list_supported_providers

**`app/services/billing/payment_service.py`** 新建:
- `init_payment(db, invoice_id, tenant_id, provider)` — 调 `gateway.create_payment`, 创建 PaymentIntent + 内存支付记录 (mock)
- `confirm_payment(db, payment_id, tenant_id, provider_ref)` — 调 `gateway.confirm_payment`, 协同 invoice 标 paid
- `refund_payment(db, payment_id, tenant_id, amount_cents)` — 调 `gateway.refund`, 协同 invoice 标 refunded
- `get_payment(payment_id, tenant_id)` / `list_payments_for_invoice(invoice_id, tenant_id)` — 查询
- 进程级 `_PAYMENT_RECORDS` dict 存 mock 支付记录
- 严格 tenant_id 信息隐藏 (NotFoundException 不暴露存在性)

**`app/services/billing/subscription_service.py`** 新建:
- `get_active_subscription(db, tenant_id)` — 当前活跃订阅
- `list_subscriptions(db, tenant_id, limit, offset)` — 历史
- `cancel_subscription(db, subscription_id, tenant_id)` — 取消
- `renew_subscription(db, tenant_id, plan_code, period, invoice_id)` — 续费
- `change_plan(db, tenant_id, new_plan_code, period)` — 升级/降级 (取消老订阅 + 创建新订阅)
- `expire_overdue_subscriptions(db)` — Celery beat 调用, 清理过期订阅
- `is_auto_renew_enabled()` — 自动续费开关 (mock 默认 False, 真接入主拍拍板)

**`app/services/billing/webhook_handler.py`** 新建:
- `handle_webhook_event(provider, payload, signature, event_type, event_id)` — 异步处理 webhook
- 签名验证 (mock `gateway.verify_webhook_signature` 默认 True)
- 幂等性: `_PROCESSED_WEBHOOK_IDS` set 去重
- `get_webhook_event(event_id)` / `clear_webhook_history()` — 测试用

### 2.3 alembic 085 计费真支付 migration

**`alembic/versions/085_billing_payment_tables.py`** 新建:
- `revision = "085_billing_payment_tables"`
- `down_revision = "083_commercial_tenant_isolation"` (W73 B-1 083 接续, 严格守 W73 A-1 修复后单链 `076 → 079 → 078 → 080 → 081 → 082 → 083`)
- **串单链验证**: alembic `get_heads()` 返回 `['085_billing_payment_tables']`, 单 head 守恒
- **4 张新表**:
  1. `billing_payments`: 支付记录主表 (payment_id PK + invoice_id FK + tenant_id FK + provider + intent_id + provider_ref + amount_cents + status + client_secret + redirect_url + error + 3 索引)
  2. `billing_subscriptions_audit`: 订阅审计 (audit_id PK + subscription_id FK + tenant_id FK + action + actor + old_plan_code + new_plan_code + details JSON + 3 索引)
  3. `billing_invoices_ext`: invoice 扩展 (ext_id PK + invoice_id UNIQUE FK + tenant_id FK + last_payment_id FK + refund_amount_cents + refund_reason + 2 索引)
  4. `billing_webhook_events`: webhook 事件日志 (event_id PK + provider + event_type + payload_size + signature_verified + processed + received_at + 2 索引)
- 3 支付渠道字段完整 (stripe / alipay / wechat_pay)
- 状态机: pending → success / failed / refunded
- 4 表全部加 tenant_id 索引 (W72 B-5 082 索引纪律复用)

### 2.4 Webhook 端点 (3 支付渠道)

**`app/api/v1/billing_webhooks.py`** 新建:
- `/api/v1/billing/webhooks/stripe` (POST) — Stripe-Signature header 验证
- `/api/v1/billing/webhooks/alipay` (POST) — X-Alipay-Signature header 验证
- `/api/v1/billing/webhooks/wechat_pay` (POST) — X-Wechatpay-Signature header 验证
- `/api/v1/billing/webhooks/events/{event_id}` (GET) — 查询 webhook 事件 (调试用)
- WebhookResponse Pydantic model
- 3 端点全部 mock 签名验证 (真接入主拍拍板)
- 幂等性: webhook_event_id 去重

### 2.5 前端 UI

**`web/src/views/commercial/PaymentMethodSelector.vue`** 新建 (3 支付方式选择):
- 3 支付方式卡片 (stripe 💳 / alipay 🅰️ / wechat_pay 💚)
- 单选切换 + 移动端 long-press `navigator.vibrate(10)` 触觉反馈
- 6 主题 dark mode 适配 (`:root[data-theme="dark"]` + `html[data-theme="dark"]` + `html.dark` + `.theme-dark`)
- init_payment + confirm_payment 二步流程 (调 `/api/v1/commercial/billing/payments/init` + `/confirm`)
- emit `payment-success` / `payment-error`

**`web/src/views/commercial/PaymentResultView.vue`** 新建 (支付结果页):
- 4 状态显示 (success ✓ / failed ✗ / pending ⏳ / refunded ↩)
- 支付详情卡片 (payment_id + intent_id + provider badge + amount + completed_at)
- 移动端 long-press `navigator.vibrate(10)` 触觉反馈
- 6 主题 dark mode 适配
- emit `return` + 路由 push `/commercial/billing`

## 测试 22/22 PASS

**`tests/test_billing_payment_mock_e2e.py`** 新建 (22 case):
- 3 支付网关切换 3 case (stripe / alipay / wechat_pay + 默认 mock)
- InvoiceService 4 case (创建 / 查询签名 / pay 签名 / refund 签名)
- PaymentService 4 case (模块导入 / init 校验 / confirm not found / refund not found)
- Webhook 端点 6 case (stripe 处理 / stripe 重复幂等 / alipay 处理 / alipay 不支持 provider 拒绝 / wechat_pay 处理 / mock 默认)
- 前端 UI 3 case (PaymentMethodSelector 存在含 3 方式 + vibrate + dark / PaymentResultView 4 状态 + vibrate / dark mode 6 主题)
- 模块导入 smoke 1 case
- alembic 085 串单链 1 case (验证 revision + down_revision)

```
SKIP_DB_SETUP=1 pytest tests/test_billing_payment_mock_e2e.py -v
======================= 22 passed, 3 warnings in 0.64s ========================
```

## 关键铁律沉淀

### 铁律 1: 3 支付网关仅 mock, 真接入主拍单独拍板

派工 v6 段 5 反馈 #6 实战: W74 B-2 全部 mock 化 3 实现, **不接真支付**. 真接入 (Stripe SDK / Alipay SDK / WeChat Pay SDK) 须主拍单独拍板, 包含:
- API key 申请 / 商户号申请 / 证书配置
- 签名验证逻辑 (Stripe webhook / Alipay RSA2 / WeChat Pay V3)
- 真实回调地址 (webhook URL) 配置
- 资金流沙箱测试

### 铁律 2: alembic 串单链严格 1 head

W74 B-2 085 `down_revision = "083_commercial_tenant_isolation"`, 严格接 W73 B-1 083, 串单链 `076 → 079 → 078 → 080 → 081 → 082 → 083 → 085`. 验证 `alembic get_heads()` 返回 `['085_billing_payment_tables']`, 单 head 守恒.

### 铁律 3: 进程级内存存储仅测试用

`_intents` / `_PAYMENT_RECORDS` / `_PROCESSED_WEBHOOK_IDS` / `_WEBHOOK_EVENTS` 4 个进程级 dict 都仅测试用. 生产环境必须替换为 PostgreSQL 表 (`billing_payments` + `billing_webhook_events`) + Redis (短期缓存).

### 铁律 4: 严格 tenant_id 信息隐藏

PaymentService / SubscriptionService / Webhook 全部按 W73 B-1 信息隐藏纪律: 跨 tenant 访问抛 `NotFoundException` 不抛 `ForbiddenException`, 不暴露资源存在性.

### 铁律 5: 移动端 long-press 触觉反馈 + 6 主题 dark mode 跨组件必须非 scoped

W72 第 2 批 C-3 实战 (CLAUDE.md v77 P2.6 强化): 移动端支付按钮 + 支付方式卡片全部带 `navigator.vibrate(10)`. 6 主题 dark mode 跨组件必须非 scoped 块: `:root[data-theme="dark"]` + `html[data-theme="dark"]` + `html.dark` + `.theme-dark` 4 选择器必须全部覆盖.

### 铁律 6: SKIP_DB_SETUP=1 用于 mock 测试

纯 mock 测试 (不依赖 docker postgres) 必须用 `SKIP_DB_SETUP=1 pytest`, 否则 conftest.py 会尝试连接 DB 报 ConnectionRefusedError. W74 B-2 mock 测试全部 SKIP_DB_SETUP=1 通过.

## 锚点范式数字

- **W73 第 1 批 242 → W74 第 1 批 B-2 247 守恒 (+5)**
- 累计 commits: W68 + W69 + W70 + W71 + W72 + W73 = ~290 commits, 含 W74 第 1 批 B-2 +5

## 后续待派

- **W74 第 1 批 B-3**: 计费 dashboard UI (PlanSelector 集成 PaymentMethodSelector)
- **W74 第 1 批 B-4**: 计费 7 维评分 qa-bench 改造
- **W74 第 1 批 D-2**: 6 类文档同步
- **W74 第 1 批 D-3**: 锚点范式实际收束 247
- **W76+**: 3 支付网关真接入 (主拍单独拍板) — Stripe SDK + Alipay SDK + WeChat Pay SDK