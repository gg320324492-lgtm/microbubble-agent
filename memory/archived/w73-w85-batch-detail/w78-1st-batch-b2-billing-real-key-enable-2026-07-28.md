# W78 第 1 批 B-2 商业化真支付生产 key 启用 (主拍决策落地)

> **批次**: W78 第 1 批 B-2  
> **状态**: LANDED / NOT AUTO-ENABLED  
> **锚点范式**: W77 第 1 批 270 → W78 第 1 批 B-2 275 守恒 (+1)  
> **派工基调**: 类 20.13 实战 + 派工 v6 段 5 反馈 #6 实战 + W77 B-3 `c7b8466df` 主拍决策准备落地  
> **0 production code 例外 2**: 商业化真支付生产 key 启用 (主拍单独拍板决策落地)

## 1. 真验证派工 v4 铁律 3 (3 步真验证)

### 1.1 W77 B-3 真支付生产 key 主拍决策

- commit `c7b8466df` 真支付生产 key 主拍决策准备 (PREPARED / NOT ENABLED)
- `docs/w77-1st-batch-b3-billing-real-key-decision-2026-07-28.md` §4 W78-B-1 主拍拍板时间表 (mock → 沙箱 → 真生产逐步启用)
- 决策: W77 B-3 仅沙箱升级准备 + 主拍决策记录, 不在 W77 自动启用

### 1.2 W75 C-1 真支付 SDK 沙箱测试实战

- commit `2487ce6658` 16/16 e2e PASS (Stripe + Alipay + WeChat Pay V3 真 SDK)
- `docs/w75-1st-batch-c1-billing-real-sdk-runbook-2026-07-27.md` §5 沙箱配置
- 实战: `StripeSDKGateway` / `AlipaySDKGateway` / `WeChatPaySDKGateway` (默认 `sandbox=True`)

### 1.3 W76 E-1 重放保护 PASS verify

- commit `13388b478` 重放保护 PASS verify
- `docs/w76-1st-batch-e1-conservation-verification-2026-07-28.md` 重放保护 + timestamp + nonce verify
- 实战: `app/services/billing/webhook_signature_real.py` `_REPLAY_CACHE` + `window_seconds=300`

基线证据齐备: W75 C-1 真 SDK + W76 E-1 重放 PASS verify + W77 B-3 决策资产 → W78 B-2 主拍决策落地.

## 2. W78 B-2 真支付生产 key 启用 5 大件

### 2.1 `.env.production.example` 主拍决策落地 (W77 B-3 §2.2 实战)

真生产 key 占位符 3 支付渠道:

- **Stripe sk_live_**: `STRIPE_LIVE_SECRET_KEY` + `STRIPE_LIVE_PUBLISHABLE_KEY`
- **Alipay RSA2**: `ALIPAY_LIVE_APP_ID` + `ALIPAY_LIVE_PRIVATE_KEY` + `ALIPAY_LIVE_PUBLIC_KEY`
- **WeChat Pay V3**: `WECHAT_PAY_LIVE_APP_ID` + `WECHAT_PAY_LIVE_MCH_ID` + `WECHAT_PAY_LIVE_API_V3_KEY`

真生产启用总开关: `BILLING_LIVE_ENABLED=false` 硬编码默认 (W78 B-2 §6 实战硬门)

### 2.2 `billing_gateway.py` 优雅降级实战 (W75 C-1 §2 实战)

`get_billing_gateway()` 自动降级矩阵:

| 调用 | `BILLING_LIVE_ENABLED` | 真生产 key | 实际返回 |
|---|---|---|---|
| `get_billing_gateway("stripe_real")` | false | 任意 | `StripeSDKGateway(api_key=None, sandbox=True)` (降级 mock) |
| `get_billing_gateway("stripe_real")` | true | 缺失/非 `sk_live_` | `StripeSDKGateway(api_key=None, sandbox=True)` (降级 mock) |
| `get_billing_gateway("stripe_real")` | true | 完整 `sk_live_xxx` | `StripeSDKGateway(api_key="sk_live_xxx", sandbox=False)` (真生产) |

新增 `_check_live_key_for_provider()` 内部辅助函数:

- `stripe_real`: 必含 `sk_live_` 前缀
- `alipay_real`: 三件套必填 + RSA2 PEM 格式校验 (`BEGIN RSA PRIVATE KEY`)
- `wechat_pay_real`: 三件套必填 (V3 签名密钥 + 商户号 + AppID)

### 2.3 真支付测试实战 (W77 B-3 §2.3 实战 + W78 主拍)

主拍拍板后, 真生产启用前必须先经小额 canary:

- Stripe: `StripeSDKGateway.create_payment(amount_cents=1, currency="USD")` 真接入 `PaymentIntent.create`
- Alipay: `AlipaySDKGateway.create_payment(amount_cents=1, currency="CNY")` 真接入 `AlipayTradePagePay`
- WeChat Pay V3: `WeChatPaySDKGateway.create_payment(amount_cents=1, currency="CNY")` 真接入 `jsapi.pay`

### 2.4 重放保护实战 (W75 C-1 16/16 + W76 E-1 PASS verify)

真生产启用后, 必含重放保护 gate:

1. **Timestamp 5 分钟 TTL** (`window_seconds=300`) — 超过窗口一律拒绝
2. **Nonce 去重** — 进程级 `_REPLAY_CACHE`
3. **Stripe** — `stripe.Webhook.construct_event` 真签名验证
4. **Alipay** — RSA2 正式支付宝公钥验签
5. **WeChat Pay V3** — 平台证书 RSA 验签 + API V3 解密链路

### 2.5 商业化监控 + 8 件套监控凑齐

`scripts/monitor-billing-real-key.sh` (W77 B-3 已建, 本批沿用) 4 case:

1. **真生产 key 健康** — 字段注入 + 非占位符 (值隐藏)
2. **真支付调用** — 只读 health/canary-status endpoint
3. **webhook 回调** — 回调消费健康 + 错误率
4. **重放保护命中** — timestamp/nonce 拒绝指标

8 件套监控凑齐: W73 B-2 + W74 D-1 + W75 B-3 + W76 B-1/B-2 + W77 B-1/B-2/B-3 + W78 B-2.

## 3. e2e 测试实战 (5/5 PASS)

`tests/test_billing_real_key_enable_e2e.py` 新建 — 4 case 主拍决策落地 + 1 辅助验证:

| # | case | 实战 |
|---|---|---|
| 1 | `test_01_real_key_enable_accepts_main_decision` | 真生产 key 启用 accept (主拍拍板后 BILLING_LIVE_ENABLED=true + 真生产 key 完整注入) |
| 2 | `test_02_real_key_enable_rejects_when_key_missing` | 真生产 key 缺失 → 优雅降级 mock (W75 C-1 沙箱模式 + 派工 v4 铁律 3 实战) |
| 3 | `test_03_replay_protection_blocks_resends` | 重放保护实战 (timestamp 5min + nonce 去重 + ISO 8601 + 异常格式) |
| 4 | `test_04_real_payment_mock_three_channels` | 真支付 mock 测试 (Stripe + Alipay + WeChat Pay V3 三方 canary) |
| 5 | `test_supported_providers_include_real_variants` | 辅助验证 list_supported_providers 包含 *_real |

验证结果: 5/5 PASS. 同时验证 W75 C-1 `test_billing_real_sdk_e2e.py` 16/16 PASS (无回归).

预存失败 (与本批无关, 主线 main HEAD 已有):
- `test_billing_payment_mock_e2e.py::test_alembic_085_chain` — alembic 085 实际接 084 而非 083, 是 W74 batch 的 alembic rebase 演练遗物, 非 W78 B-2 引入.

## 4. 文档与 commit

- `docs/w78-1st-batch-b2-billing-real-key-enable-runbook-2026-07-28.md` 新建 — 真生产 key 启用主拍决策 runbook (类 20.13 实战 + 派工 v6 段 5 反馈 #6 实战)
- `.env.production.example` 新建 — 主拍决策落地版 (3 支付渠道真生产 key 占位符 + 总开关 + 重放保护说明)
- `app/services/billing_gateway.py` 修改 — `_check_live_key_for_provider()` + 工厂函数自动降级逻辑 (W78 B-2 主拍决策落地实战)
- `app/config.py` 修改 — 新增 `BILLING_LIVE_ENABLED` + 3 渠道真生产 key 共 10 字段
- `tests/test_billing_real_key_enable_e2e.py` 新建 — 4 case 主拍决策落地

## 5. 派工前提与新铁律

### 5.1 类 20.13 实战

W77 B-3 真生产 key 主拍决策已拍板, W78 B-2 主拍决策落地 (主拍单独拍板).
技术准备完成 ≠ 业务批准; 生产 key 决策必须与普通 feature merge 分离.

### 5.2 派工 v6 段 5 反馈 #6 实战

真支付 SDK 接入 / 真生产 key 启用 / 商业化排期 = 主拍单独拍板, 不允许自动 merge.
W75 C-1 + W76 E-1 + W77 B-3 + W78 B-2 4 批形成完整的"沙箱测试 → 重放保护 → 决策准备 → 主拍落地"链路.

### 5.3 派工 v4 铁律 3 实战

真生产 key 缺失 → 优雅降级 mock, 永不抛异常, 永不自启真钱 (W75 C-1 沙箱模式实战).
`BILLING_LIVE_ENABLED=false` 是硬门控默认, 仅主拍签字后才能 true.

### 5.4 新铁律 (W78 B-2)

1. **真生产 key 启用门禁 8 件齐备**: 主拍签字 + 三方 gate 通过 + `BILLING_LIVE_ENABLED=true` + 3 渠道真生产 key 完整注入 + 重放保护 gate + 监控 4 case PASS + 类 20.13 实战 + 派工 v6 段 5 反馈 #6 实战. 任一不满足 → 自动降级 mock.
2. **`_check_live_key_for_provider()` 自动检查**: 真生产 key 启用必须先经 `_check_live_key_for_provider()` 检查, 返回 `(enabled, reason)` 元组. 主拍未启用或 key 缺失 → 永远 `(False, "...")` + logger.warning.
3. **`get_billing_gateway()` 沙箱/真生产切换**: `sandbox=not enabled` 一行实现"真生产 key 启用 → 真生产, 否则沙箱". 永不自启真钱.

### 5.5 下一拍

W78-B-3: 真支付生产环境 canary 实战 (Stripe/Alipay/WeChat Pay V3 小额三方测试, 主拍单独拍板, 类 20.13 实战).

## 6. 锚点范式守恒

锚点范式 W77 第 1 批 270 → W78 第 1 批 B-2 275 守恒 (+1):
- A-1 部署收口 (主拍, 不改业务路径)
- A-2 prompt template v8 (主拍, 派工范式升级)
- A-3 plans verify (派工 v4 铁律 3 真验证)
- B-1 真生产 key 主拍决策拍板 (本任务)
- **B-2 真生产 key 启用 (主拍决策落地) (本任务, +1)**

0 production code 例外 2: B-2 商业化真支付生产 key 启用 (已批).
类 20.13 真生产 key 主拍 (W78 主拍已落地, 不在 W78 自动启用).

W19 选项 A 维持: 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E) 不发起新排期.