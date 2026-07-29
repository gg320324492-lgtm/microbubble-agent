# W78 第 1 批 B-2 商业化真支付生产 key 启用 Runbook (主拍决策落地版)

> 状态：**LANDED / NOT AUTO-ENABLED**。W78 第 1 批 B-2 把 W77 B-3 真支付生产 key 主拍决策准备 (`c7b8466df` PREPARED / NOT ENABLED) 落地为可执行代码 (类 20.13 实战 + 派工 v6 段 5 反馈 #6 实战); 真生产 key 启用仍然受主拍单独拍板硬门控 — `BILLING_LIVE_ENABLED` 默认为 false, 仅在主拍签字且 secrets manager 注入后才生效。

## 0. 派工 v4 铁律 3 真验证

1. W77 B-3 commit `c7b8466df` 主拍决策准备 (`docs/w77-1st-batch-b3-billing-real-key-decision-2026-07-28.md`) 已声明 W78 主拍单独拍板才启用真生产。
2. W75 C-1 commit `2487ce6658` 16/16 e2e PASS (Stripe + Alipay + WeChat Pay V3 真 SDK + webhook 签名 + 重放保护实战)。
3. W76 E-1 commit `13388b478` 重放保护 PASS verify (`window_seconds=300` + nonce + 三方签名)。
4. W77 第 1 批 grand closure memory (`068626ecc`) W77 B-3 撤回实战 + 类 20.13 真生产 key 实战。

基线证据：W75 C-1 16/16 + W76 E-1 重放 PASS verify + W77 B-3 决策资产齐备 (4/4 决策 e2e PASS).

## 1. 主拍决策落地 (类 20.13 实战 + 派工 v6 段 5 反馈 #6)

### 1.1 真生产启用总开关 (硬门)

`app/config.py` 新增 `BILLING_LIVE_ENABLED: bool = False` 默认值。**默认 false**, 任何代码路径都不会自动启用真生产支付, 必须:

1. 主拍决策 (技术/财务/安全/on-call 全部签字)
2. 由 1Password / Vault / 云 Secret Manager 注入真生产 key (`.env.production.example` 模板)
3. 设置 `BILLING_LIVE_ENABLED=true` 才允许 `get_billing_gateway("stripe_real")` 等返回真实 SDK 启用态

`get_billing_gateway()` 在检测到 `BILLING_LIVE_ENABLED=false` 或任一渠道真生产 key 缺失时, 走 `sandbox=True` 的 `StripeSDKGateway` / `AlipaySDKGateway` / `WeChatPaySDKGateway` — W75 C-1 沙箱模式实战 (派工 v4 铁律 3 实战 + 派工 v6 段 5 反馈 #6 实战).

### 1.2 真生产 key 模板 (主拍决策后由 secrets manager 注入)

`.env.production.example` (W77 B-3 已建, W78 B-2 主拍决策落地版):

| 字段 | 渠道 | 必含检查 |
|---|---|---|
| `STRIPE_LIVE_SECRET_KEY` | Stripe | `sk_live_` 前缀 |
| `STRIPE_LIVE_PUBLISHABLE_KEY` | Stripe | `pk_live_` 前缀 |
| `ALIPAY_LIVE_APP_ID` | Alipay | 非空字符串 |
| `ALIPAY_LIVE_PRIVATE_KEY` | Alipay | 含 `BEGIN RSA PRIVATE KEY` (PEM) |
| `ALIPAY_LIVE_PUBLIC_KEY` | Alipay | 非空字符串 |
| `WECHAT_PAY_LIVE_APP_ID` | WeChat Pay V3 | 非空字符串 |
| `WECHAT_PAY_LIVE_MCH_ID` | WeChat Pay V3 | 非空字符串 |
| `WECHAT_PAY_LIVE_API_V3_KEY` | WeChat Pay V3 | 非空字符串 |
| `WECHAT_PAY_LIVE_PRIVATE_KEY` | WeChat Pay V3 | 商户 RSA 私钥 (V3 签名) |
| `WECHAT_PAY_LIVE_PLATFORM_CERT` | WeChat Pay V3 | 微信平台证书 (V3 回调验签) |

`_check_live_key_for_provider()` 在 `app/services/billing_gateway.py` 实现了 3 渠道的真生产 key 自动检查:

- `stripe_real`: 必含 `sk_live_` 前缀
- `alipay_real`: 三件套必填 + RSA2 PEM 格式校验
- `wechat_pay_real`: 三件套必填 (V3 签名密钥 + 商户号 + AppID)

任一条件不满足 → 优雅降级 mock (永不抛异常, 永不自启真钱).

## 2. 真支付测试实战 (W78 B-2 主拍决策落地 + 派工 v6 段 5 反馈 #6 实战)

### 2.1 三方 canary (小额 $0.01/¥0.01)

主拍拍板后, 真生产启用前必须先经小额 canary:

- Stripe: `StripeSDKGateway.create_payment(amount_cents=1, currency="USD")` 真接入 `PaymentIntent.create`
- Alipay: `AlipaySDKGateway.create_payment(amount_cents=1, currency="CNY")` 真接入 `AlipayTradePagePay`
- WeChat Pay V3: `WeChatPaySDKGateway.create_payment(amount_cents=1, currency="CNY")` 真接入 `jsapi.pay`

任一渠道 canary 失败 → 立即关闭 `BILLING_LIVE_ENABLED` + 退款 + 回 sandbox.

### 2.2 重放保护 gate (W75 C-1 16/16 + W76 E-1 PASS verify)

真生产启用后, 必含重放保护 gate:

1. **Timestamp 5 分钟 TTL** (`window_seconds=300`) — 超过窗口一律拒绝
2. **Nonce 去重** — 进程级 `_REPLAY_CACHE` (`app/services/billing/webhook_signature_real.py:27-28`)
3. **Stripe** — `stripe.Webhook.construct_event` 真签名验证
4. **Alipay** — RSA2 正式支付宝公钥验签, 不允许 permissive fallback 进入生产
5. **WeChat Pay V3** — 平台证书 RSA 验签 + API V3 解密链路, 不允许缺 public key 的 permissive fallback 进入生产

## 3. 优雅降级实战 (W75 C-1 沙箱模式 + 派工 v4 铁律 3 实战)

`get_billing_gateway()` 自动降级矩阵:

| 调用 | `BILLING_LIVE_ENABLED` | 真生产 key | 实际返回 |
|---|---|---|---|
| `get_billing_gateway("stripe_real")` | false | 任意 | `StripeSDKGateway(api_key=None, sandbox=True)` (降级 mock) |
| `get_billing_gateway("stripe_real")` | true | 缺失/非 `sk_live_` | `StripeSDKGateway(api_key=None, sandbox=True)` (降级 mock, 仅真生产 key 缺失) |
| `get_billing_gateway("stripe_real")` | true | 完整 `sk_live_xxx` | `StripeSDKGateway(api_key="sk_live_xxx", sandbox=False)` (真生产) |

alipay_real / wechat_pay_real 同理.

## 4. 验证与锚点守恒

```bash
SKIP_DB_SETUP=1 pytest -q tests/test_billing_real_key_enable_e2e.py
```

预期：5/5 e2e PASS (4 主拍决策落地 case + 1 supported_providers 辅助验证).

```bash
# 确认现有 W75 C-1 真 SDK e2e 仍全绿 (无回归)
SKIP_DB_SETUP=1 pytest -q tests/test_billing_real_sdk_e2e.py
```

预期：16/16 e2e PASS.

- 锚点范式：W77 第 1 批 270 → W78 第 1 批 B-2 275 守恒 (+1).
- 0 production code 例外 2：商业化真支付生产 key 启用, 类 20.13 主拍单独拍板决策落地; 本提交仅 `.env.production.example`、`app/services/billing_gateway.py`、`app/config.py`、`tests/test_billing_real_key_enable_e2e.py`、`docs/`、`memory/`, 不动老 billing 链路 (MockBillingGateway / 旧 payment_service / webhook_handler 等保持原样).

## 5. 监控与容错 (8 件套监控凑齐)

W78 B-2 监控已纳入 8 件套监控口径 (派工 v6 段 5 反馈 #6 + 类 20.13 实战):

| 件 | 批次 | 监控脚本/端点 |
|---|---|---|
| 1 | W73 第 1 批 B-2 | 4 类 hot-fix 监控 |
| 2 | W74 第 1 批 D-1 | 多租户监控 |
| 3 | W75 第 1 批 B-3 | webhook P2 监控 |
| 4 | W76 第 1 批 E-1 | Edge-TTS 守恒监控 |
| 5 | W77 第 1 批 B-3 | 真支付生产 key 决策准备监控 (`scripts/monitor-billing-real-key.sh`) |
| 6 | W77 第 1 批 B-1 | Edge-TTS iOS Safari 主拍接入 |
| 7 | W77 第 1 批 B-2 | Edge-TTS Android Chrome 主拍接入 |
| **8** | **W78 第 1 批 B-2** | **真支付生产 key 启用监控 (本批, 4 case)** |

`scripts/monitor-billing-real-key.sh` (W77 B-3 已建, 本批沿用):

1. **真生产 key 健康** — 字段注入 + 非占位符 (值隐藏)
2. **真支付调用** — 只读 health/canary-status endpoint, 不在监控中扣款
3. **webhook 回调** — 回调消费健康 + 错误率
4. **重放保护命中** — timestamp/nonce 拒绝指标

容错顺序：分渠道熔断 → 关闭 live flag → 回 sandbox/mock → 对未决订单查询 → 必要时退款 → 财务对账 → 事件复盘.

## 6. 真支付生产 key 启用门禁 (类 20.13 实战硬门)

W78 第 1 批 B-2 主拍决策落地 — 真生产启用必须满足:

1. 主拍签字决策记录 (`Decision ID`, `Decision=APPROVE`)
2. 三方 gate 分别通过 (Stripe / Alipay / WeChat Pay V3)
3. `BILLING_LIVE_ENABLED=true` (部署机或 secrets manager 注入)
4. `STRIPE_LIVE_SECRET_KEY` 含 `sk_live_` 前缀 (Stripe)
5. `ALIPAY_LIVE_APP_ID` + `ALIPAY_LIVE_PRIVATE_KEY` + `ALIPAY_LIVE_PUBLIC_KEY` 三件套齐备 (Alipay)
6. `WECHAT_PAY_LIVE_APP_ID` + `WECHAT_PAY_LIVE_MCH_ID` + `WECHAT_PAY_LIVE_API_V3_KEY` 三件套齐备 (WeChat Pay V3)
7. 重放保护 gate (timestamp 5min + nonce + 三方签名) 验证通过
8. 监控 4 case PASS (真生产 key 健康 + 真支付调用 + webhook 回调 + 重放保护命中)

任一条件不满足 → 自动降级 mock (W75 C-1 沙箱模式实战), 永不自启真钱.

## 7. 真生产启用后回滚预案

主拍拍板决策 (`Decision=HOLD` 或 `Decision=REJECT`) → 立即回滚:

1. `BILLING_LIVE_ENABLED=false` (环境变量)
2. `get_billing_gateway("stripe_real")` 等 3 渠道自动降级 mock
3. 真生产 key 仍在 secrets manager, 不删除 (审计需要), 但生产部署引用清空
4. 真支付监控告警升级 on-call

类 20.13 实战: 真生产 key 启用 ≠ 普通 feature merge, 必须单独留下主拍审计记录 + 部署 webhook 调主拍 review.

## 8. 下一拍

W78-B-3 (后续批次): 真支付生产环境 canary 实战 (Stripe/Alipay/WeChat Pay V3 小额三方测试, 主拍单独拍板, 类 20.13 实战).