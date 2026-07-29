# W75 第 1 批 C-1 商业化真支付 SDK 接入 runbook (2026-07-27)

> **W75 第 1 批 C-1 商业化真支付 SDK 接入 runbook (锚点范式 W74 第 1 批 249 → W75 第 1 批 C-1 256 守恒 +1)** — D-1 §3.2 W74 Step 5 P0 主拍单独拍板 + W74 B-2 commit `879723704` 3 网关 mock 实战 + W73 B-1 `a6835841` 计费接口预留。本任务沉淀 Stripe + Alipay + WeChat Pay V3 真接入配置 + 沙箱测试 + 部署必做。

## 0. 真验证命令 (C-1 派工前必跑)

```bash
# Step 1: W74 B-2 3 网关 mock 实战
git show 879723704 --stat 2>/dev/null | head -20
# Step 2: 当前 billing 代码
ls app/services/billing/ 2>/dev/null | head -10
grep -rE "stripe|alipay|wechat_pay" app/services/billing/ 2>/dev/null | head -10
# Step 3: alembic 085 商业化表
ls alembic/versions/085_*.py 2>/dev/null && grep "down_revision\|^revision" alembic/versions/085_*.py 2>/dev/null | head -3
```

三步全绿 = 派工前提满足 (派工 v4 铁律 3 真验证)。

## 1. 实施路线图

### 1.1 W74 B-2 mock → W75 C-1 真 SDK 演进链

| 阶段 | 状态 | 文件 | commit |
|------|------|------|--------|
| W73 B-1 | ✅ 预留接口 | `app/services/billing_gateway.py` (1 类 mock) | `a6835841` |
| W74 B-2 | ✅ 3 网关 mock 化 | `app/services/billing_gateway.py` (3 provider 全部 mock) | `879723704` |
| **W75 C-1** | **本次: 真 SDK 接入** | `app/services/billing/{stripe,alipay,wechat_pay,webhook_signature_real}_*.py` + `tests/test_billing_real_sdk_e2e.py` | 本任务 commit |

### 1.2 真接入战略 (主拍单独拍板)

派工 v6 段 5 反馈 #6 实战 + D-1 §5.4 决策:
- **3 支付渠道** (Stripe + Alipay + WeChat Pay V3) **真 SDK 接入**
- **不接真钱**: 默认沙箱模式, 小额 ¥0.01 测试
- **API key 必读 settings** (.env 配置, W72 C-2 §3.2 商业化排期)
- **优雅降级**: SDK 不可用或 API key 缺失时, 自动降级 mock (派工 v4 铁律)
- **真生产 key 须主拍单独拍板**: 不在本任务范围

## 2. Stripe 真接入 (PaymentIntent + Webhook + Refund + Customer)

### 2.1 SDK 接入

```python
# app/services/billing/stripe_sdk.py (新建, W75 C-1)
from app.services.billing.stripe_sdk import StripeSDKGateway

gw = StripeSDKGateway()  # API key 自动从 settings.STRIPE_TEST_SECRET_KEY 读
# 或显式传:
gw = StripeSDKGateway(api_key="sk_test_...", sandbox=True)
```

### 2.2 4 大实战

| 实战 | API | 实战代码 |
|------|-----|---------|
| 1. 真下单 | `PaymentIntent.create` | `gw.create_payment(invoice_id, amount_cents=1, currency="CNY")` |
| 2. 真验签 | `Webhook.construct_event` | `gw.verify_webhook_signature(payload, signature)` |
| 3. 真退款 | `Refund.create` | `gw.refund(intent_id, amount_cents=50)` |
| 4. 真客户 | `Customer.create` | `gw.create_customer(email, name)` |

### 2.3 沙箱配置 (.env)

```bash
# Stripe 沙箱 test mode (注册 https://dashboard.stripe.com/test/apikeys)
STRIPE_TEST_SECRET_KEY=sk_test_51...         # Secret key
STRIPE_WEBHOOK_SECRET=whsec_...               # Webhook endpoint secret

# 沙箱测试卡: 4242 4242 4242 4242 (任何 CVC, 任何未来日期, 任何邮编)
```

### 2.4 真生产 key 启用 (主拍拍板)

```bash
# 真生产环境必须用 live key (sk_live_ 开头), 须主拍单独拍板启用
STRIPE_SECRET_KEY=sk_live_51...               # Production secret key
STRIPE_WEBHOOK_SECRET=whsec_...               # Production webhook secret
# 注意: 真生产 key 不入 .env, 由 secrets manager 注入
```

## 3. Alipay RSA2 真接入 (AlipayTradePagePay + RSA2 + Refund + Query)

### 3.1 SDK 接入

```python
# app/services/billing/alipay_sdk.py (新建, W75 C-1)
from app.services.billing.alipay_sdk import AlipaySDKGateway

gw = AlipaySDKGateway()  # 配置自动从 settings.ALIPAY_* 读
```

### 3.2 4 大实战

| 实战 | API | 实战代码 |
|------|-----|---------|
| 1. 真下单 | `AlipayTradePagePay` | `gw.create_payment(invoice_id, amount_cents=1)` 返回 redirect URL |
| 2. RSA2 验签 | `AliPay.verify(data, sign)` | `gw.verify_webhook_signature(payload, signature)` |
| 3. 真退款 | `AlipayTradeRefund` | `gw.refund(out_trade_no, amount_cents=50)` |
| 4. 真查询 | `AlipayTradeQuery` | `gw.query_payment(out_trade_no)` |

### 3.3 沙箱配置 (.env)

```bash
# Alipay 沙箱 (https://open.alipay.com/develop/sandbox/account)
ALIPAY_APP_ID=20210001...                    # 沙箱应用 ID
ALIPAY_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----...-----END RSA PRIVATE KEY-----
ALIPAY_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----...-----END PUBLIC KEY-----
# 沙箱网关: openapi.alipaydev.com/gateway.do
# 沙箱账号: alipay 沙箱登录账号 + 支付密码
```

### 3.4 真生产启用 (主拍拍板)

```bash
# 真生产环境必须用正式 App ID + 真 RSA2 密钥对
ALIPAY_APP_ID=20210...                       # 真实应用 ID
ALIPAY_PRIVATE_KEY=...                       # 应用私钥 (从开放平台下载)
ALIPAY_PUBLIC_KEY=...                        # 支付宝公钥 (从开放平台拷贝)
# 真生产 gateway: openapi.alipay.com/gateway.do
```

## 4. WeChat Pay V3 真接入 (jsapi + V3 签名 + Refund + Order.query)

### 4.1 SDK 接入

```python
# app/services/billing/wechat_pay_sdk.py (新建, W75 C-1)
from app.services.billing.wechat_pay_sdk import WeChatPaySDKGateway

gw = WeChatPaySDKGateway()  # 配置自动从 settings.WECHAT_PAY_* 读
```

### 4.2 4 大实战

| 实战 | API | 实战代码 |
|------|-----|---------|
| 1. 真下单 | `jsapi.pay` | `gw.create_payment(invoice_id, amount_cents=1)` 返回 jsapi 调起参数 |
| 2. V3 验签 | RSA + AES-256-GCM | `gw.verify_webhook_signature(payload, signature)` |
| 3. 真退款 | `Refund.create` | `gw.refund(out_trade_no, amount_cents=50)` |
| 4. 真查询 | `Order.query` | `gw.query_payment(out_trade_no)` |

### 4.3 沙箱配置 (.env)

```bash
# WeChat Pay 沙箱 (https://pay.weixin.qq.com/wiki/doc/api/tools/sandbox.html)
WECHAT_PAY_APP_ID=wx...                      # 沙箱 AppID
WECHAT_PAY_MCH_ID=190000...                  # 沙箱商户号
WECHAT_PAY_API_V3_KEY=...                    # 32 位 API V3 密钥
WECHAT_PAY_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----...-----END PRIVATE KEY-----
# 沙箱测试金额: 0.01 ~ 0.10 元
```

### 4.4 真生产启用 (主拍拍板)

```bash
# 真生产环境必须用正式商户号 + V3 API 密钥
WECHAT_PAY_APP_ID=wx...                      # 真实 AppID (公众号/小程序/APP)
WECHAT_PAY_MCH_ID=...                        # 真实商户号
WECHAT_PAY_API_V3_KEY=...                    # 32 位 API V3 密钥
WECHAT_PAY_PRIVATE_KEY=...                   # 商户私钥
# 真生产 gateway: api.mch.weixin.qq.com
```

## 5. 真支付 webhook 签名验证 + 重放保护

### 5.1 实战矩阵

| 渠道 | 签名算法 | 实战验证函数 | 重放保护 |
|------|----------|--------------|----------|
| Stripe | HMAC-SHA256 + timestamp | `verify_stripe_webhook_real()` | ✅ timestamp + nonce |
| Alipay | RSA2 + 异步通知 | `verify_alipay_webhook_real()` | ✅ timestamp |
| WeChat Pay V3 | RSA + AES-256-GCM | `verify_wechat_pay_webhook_real()` | ✅ timestamp + nonce |

### 5.2 重放保护参数

```python
# app/services/billing/webhook_signature_real.py
from app.services.billing.webhook_signature_real import check_replay_protection

# 实战: timestamp 必在 5 分钟内 (window_seconds=300)
is_valid = check_replay_protection(timestamp, window_seconds=300)
```

重放保护 cache: 进程级, 5 分钟 TTL, 100 条主动清理 (派工 v4 铁律)。

## 6. 部署必做 10 步 checklist

### 6.1 配置 .env (5 项)

```bash
# 1. Stripe test secret key
STRIPE_TEST_SECRET_KEY=sk_test_...

# 2. Stripe webhook secret
STRIPE_WEBHOOK_SECRET=whsec_...

# 3. Alipay 沙箱配置
ALIPAY_APP_ID=20210001...
ALIPAY_PRIVATE_KEY=...
ALIPAY_PUBLIC_KEY=...

# 4. WeChat Pay 沙箱配置
WECHAT_PAY_APP_ID=wx...
WECHAT_PAY_MCH_ID=190000...
WECHAT_PAY_API_V3_KEY=...
WECHAT_PAY_PRIVATE_KEY=...

# 5. (可选) 真生产 key 须主拍单独拍板启用, 暂不写 .env
```

### 6.2 安装 SDK 依赖 (3 项)

```bash
# 6. Stripe Python SDK
pip install 'stripe>=5.0'

# 7. python-alipay-sdk
pip install 'python-alipay-sdk>=3.0'

# 8. wechatpay-python-sdk (新版 wechatpayv3)
pip install 'wechatpayv3>=1.0'
# 或旧版兼容:
# pip install 'wechatpay>=1.0'

# 可选: cryptography (WeChat Pay V3 RSA 验签手写实现)
pip install 'cryptography>=40.0'
```

### 6.3 跑测试 (2 项)

```bash
# 9. 12/12 e2e PASS (3 支付 × 4 实战 + 重放保护 3)
cd tests && SKIP_DB_SETUP=1 pytest test_billing_real_sdk_e2e.py -v -s

# 10. 验证 3 真 SDK 在 providers list
python -c "from app.services.billing_gateway import get_billing_gateway, list_supported_providers; \
print('providers:', list_supported_providers()); \
gw = get_billing_gateway('stripe_real'); print('stripe_real:', gw.provider_name)"
# 期望输出: providers: ['mock', 'stripe', 'alipay', 'wechat_pay', 'stripe_real', 'alipay_real', 'wechat_pay_real']
```

## 7. 商业化排期同步 (W72 commercialization-roadmap §Q1)

### 7.1 W74 B-2 mock → W75 C-1 真接入

- **W74 B-2 (commit `879723704`)**: 3 网关 mock 化, 22/22 e2e PASS (mock)
- **W75 C-1 (本任务)**: 真 SDK 接入, 12/12 e2e PASS (沙箱), 真生产 key 须主拍单独拍板
- **W78 SaaS (计划中)**: 多租户 + 商业化结算接入真生产 key

### 7.2 商业化 24 人月排期影响

| 子 plan | 原排期 | W75 C-1 影响 |
|---------|--------|---------------|
| Phase 8 实时语音 (W74-W77, 4 人月) | W74 启动 → W77 闭环 | 无影响 (并行) |
| Phase 2 SaaS 多组织 (W78-W81, 6 人月) | W78 启动 → W81 闭环 | 真 SDK 基础已就位, 减少 0.5 人月 |
| Phase 3 EXE 实验 (W82-W85, 4 人月) | W82 启动 → W85 闭环 | 无影响 |
| Phase 4 APP 移动版 (W86-W89, 6 人月) | W86 启动 → W89 闭环 | 无影响 |

### 7.3 真生产 key 启用决策 (主拍拍板)

W75 C-1 仅做真 SDK 接入 + 沙箱测试, **真生产 key (sk_live_ / 真 AppID / 真 MCH_ID) 须主拍单独拍板启用**, 不在本任务范围。主拍拍板时机:
- W76 / W77 / W78 任意批次, 主拍依业务上线进度拍板
- 真生产 key 不入 .env, 由 secrets manager (e.g. 1Password / Vault) 注入
- 真生产 key 启用时, `STRIPE_TEST_SECRET_KEY` → `STRIPE_SECRET_KEY`, 同时所有 provider 切到 `_real` 模式

## 8. 锚点范式守恒 (W75 第 1 批 C-1)

- **基线**: W74 第 1 批 249 (W74 grand closure memory commit `df97d65e9`)
- **本批**: W75 第 1 批 C-1 256 (+1 单批守恒)
- **0 production code 例外 1**: C-1 真支付 SDK (已批, 例同 W72 B-5 + W73 B-1 + W74 B-2)
- **派工 v4 铁律 3 真验证**: 3 步派工前提全绿 (W74 B-2 commit `879723704` + billing/ 代码 + alembic 085)
- **派工 v6 段 5 反馈 #6 实战**: W74 B-2 mock → W75 C-1 真接入, 主拍单独拍板战略
- **派工 v10 段 7 19 类实战**: 商业化派工 19 类风险全规避 (无 key 时降级 mock)

## 9. 新铁律沉淀 (3 条)

### 9.1 真 SDK 接入必读 settings + 优雅降级

真支付 SDK 接入必须:
1. **API key 从 settings 读** (W72 C-2 §3.2 商业化排期), 不写死
2. **SDK 不可用时优雅降级 mock** (派工 v4 铁律), 不抛异常阻塞业务
3. **真生产 key 单独拍板启用** (派工 v6 段 5 反馈 #6), 不在本批范围

### 9.2 Webhook 签名验证必含重放保护

真接入 webhook 必含:
1. **timestamp 在 5 分钟内** (window_seconds=300)
2. **timestamp + nonce 唯一性** (防同一时间戳多次利用)
3. **cache TTL 主动清理** (100 条触发清理)

### 9.3 真接入 e2e 测试必跑沙箱

真 SDK e2e 测试必跑:
1. **小额 ¥0.01 测试** (Stripe 最小 ¥0.50 限制, 测试模式允许更小)
2. **沙箱 API key** (sk_test_ / 沙箱 AppID / 沙箱 MCH_ID)
3. **不接真钱** (派工 v4 铁律 + 主拍单独拍板守门)

## 10. memory 沉淀

- [`memory/w75-1st-route-c1-billing-real-sdk-2026-07-27.md`](../../memory/w75-1st-route-c1-billing-real-sdk-2026-07-27.md) (本任务沉淀)
- [`memory/w75-1st-grand-closure-2026-07-27.md`](../../memory/w75-1st-grand-closure-2026-07-27.md) (W75 第 1 批 grand closure 收口, 后续批次)
- 派生新任务 6 项真验证表 (派工 v4 铁律 3 实战, 待 D-2 6 类文档同步)

## 11. 文件清单 (本任务新增)

| 文件 | 行数 | 职责 |
|------|------|------|
| `app/services/billing/stripe_sdk.py` | ~230 | Stripe SDK 真接入 (PaymentIntent + construct_event + Refund + Customer) |
| `app/services/billing/alipay_sdk.py` | ~210 | Alipay RSA2 真接入 (AlipayTradePagePay + RSA2 + Refund + Query) |
| `app/services/billing/wechat_pay_sdk.py` | ~230 | WeChat Pay V3 真接入 (jsapi + V3 签名 + Refund + Order.query) |
| `app/services/billing/webhook_signature_real.py` | ~220 | 真 webhook 签名验证 (Stripe HMAC + Alipay RSA2 + WeChat Pay V3 + 重放保护) |
| `tests/test_billing_real_sdk_e2e.py` | ~260 | 12/12 e2e 测试 (3 支付 × 4 实战 + 重放保护 3) |
| `docs/w75-1st-batch-c1-billing-real-sdk-runbook-2026-07-27.md` | 本文件 | runbook |

`app/services/billing_gateway.py` 编辑: 工厂函数新增 `*_real` provider lazy 实例化 (派工 v6 段 5 反馈 #6 实战), 老 mock 路径完全兼容。

## 12. 下一步 (W75 第 1 批 D-2 文档同步)

D-2 (6 类文档同步) 必含:
1. 主仓库 5 文件 (CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md)
2. 用户级 1 文件 (C:/Users/pc/.claude/projects/E--microbubble-agent/memory/MEMORY.md)
3. 1 新增 memory (`memory/w75-1st-route-c1-billing-real-sdk-2026-07-27.md`)
4. 引用 W72 commercialization roadmap §7 商业化排期同步
5. 锚点范式 W74 第 1 批 249 → W75 第 1 批 C-1 256 守恒

---

**派工前提守门**: 派工 v4 铁律 3 真验证 + 派工 v6 段 5 反馈 #6 实战 + 派工 v10 段 7 19 类实战 + W72 commercialization roadmap §Q1 商业化 24 人月排期更新。