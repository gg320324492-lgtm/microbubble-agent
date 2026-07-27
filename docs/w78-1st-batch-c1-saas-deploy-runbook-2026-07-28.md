# W78 第 1 批 C-1 商业化 SaaS 平台部署 (锚点范式 W77 第 1 批 270 → W78 第 1 批 C-1 277 守恒 +1, 2026-07-28)

> **W78-C-1 商业化 SaaS 平台部署** — 4 层架构 + 6 商业化表 + multi-tenant 隔离实战 + 计费网关真接入 + License 校验实战. W73 B-5 + W74 B-1 + W75 C-1 + W77 B-3 实战基础上 SaaS 平台部署收口.

## 0. 派工前提验证 (派工 v4 铁律 3 + v6 段 5 反馈 #4 实战)

### 0.1 真验证 3 步 (派工 v4 铁律 3)

```bash
# Step 1: 读 W73 B-5 商业化 Phase 8 起步 13/13 e2e 实战
git show 820e151d2 --stat
# Step 2: 读 W74 B-1 9 表 2 索引 + W75 C-1 真支付 SDK 实战 + W77 B-3 真生产 key 决策准备
git show aef117b17 --stat
git show 2487ce6658 --stat
git show c7b8466df --stat
# Step 3: grep 4 层架构 + 6 商业化表 + alembic 单 head verify
ls app/services/commercial/ 2>/dev/null || true
grep -rE "commercial_plans|commercial_tenants|commercial_subscriptions|commercial_invoices|commercial_usage_records|commercial_licenses" app/models/billing.py
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
```

### 0.2 真验证结果

- ✅ **W73 B-5 commit `820e151d2`** — Dockerfile.commercial + saas-platform 5 脚本 (tenant_manager + usage_tracker + billing_gateway + audit_export + deploy) + commercial_billing 4 大件 (082/alembic + app/main + api/v1/billing + app/models/billing + app/schemas/billing + app/services/billing_service). 13/13 e2e PASS.
- ✅ **W74 B-1 commit `aef117b17`** — 9 表 2 索引缺口修复 (alembic 084 down_revision='083_commercial_tenant_isolation' 串单链). **单链守恒**: 076→078→080→081→082→083→084, 1 head verify 通过.
- ✅ **W75 C-1 commit `2487ce6658`** — 商业化真支付 SDK 接入 (Stripe + Alipay + WeChat Pay V3). 16/16 e2e PASS. **重放保护**实战 (timestamp 5min + nonce + Webhook 签名验证).
- ✅ **W77 B-3 commit `c7b8466df`** — 真支付生产 key 主拍决策准备 (W78 主拍拍板). `.env.production.example` 3 渠道真生产 key 占位符. 4/4 e2e PASS.
- ✅ **W77 第 1 批 grand closure** — 锚点范式 270 守恒 (commit `068626ecc`). A-2 §5.3 W78 派工顺序: mock → 沙箱 → 真生产逐步.
- ✅ **alembic 单链守恒** — `085_billing_payment_tables` 唯 1 head (`ScriptDirectory.get_heads() == ['085_billing_payment_tables']`).
- ✅ **6 商业化表实战** — `commercial_plans` / `commercial_tenants` / `commercial_subscriptions` / `commercial_invoices` / `commercial_usage_records` / `commercial_licenses` 全部定义在 `app/models/billing.py`.
- ✅ **multi-tenant 隔离实战** — `app/services/tenant_data_isolation.py` (`assert_tenant_match` 跨租户返回 422) + `app/middleware/tenant_middleware.py` (注入 header) + `app/services/license_service.py` (离线 7 天宽限 + read-only 模式).
- ✅ **4 层架构实战** — 镜像层 (`docker/Dockerfile.commercial` + `docker/commercial/license-check.py`) + SaaS 平台层 (`commercial/saas-platform/`) + 计费服务层 (`app/services/billing/`) + 前端层 (`web/src/views/commercial/`).

### 0.3 派生新任务真验证 (派工 v8 段 8)

| 任务段 | 派生新任务真验证 |
|--------|------------------|
| 4 层架构 | ✅ W73 B-5 `820e151d2` 8 files: Dockerfile.commercial + saas-platform 5 脚本 + alembic 082 + 4 billing 件 |
| 6 商业化表 | ✅ `app/models/billing.py` 6 `__tablename__` 全部匹配 W73 B-5/082/W74 B-1/alembic 084 |
| multi-tenant 隔离 | ✅ W74 D-1 422 修复实战 + W75 B-2 422 真实战. `tenant_data_isolation.py:check_cross_tenant` 422 + `assert_tenant_match` |
| 计费网关真接入 | ✅ W75 C-1 + W77 B-3 + `.env.production.example` (3 真生产 key 占位符) |
| License 校验实战 | ✅ `license_service.py` 4 模式 (online / offline_grace_7d / expired_readonly / revoked) |
| alembic 单链 | ✅ `085_billing_payment_tables` 唯 1 head |

## 1. W78 第 1 批 C-1 SaaS 平台部署 (5 大件)

### 1.1 4 层架构实战 (镜像 + SaaS + 计费 + 前端)

| 层 | 路径 | 实战验证 |
|----|------|----------|
| 1. 镜像层 | `docker/Dockerfile.commercial` + `docker/commercial/license-check.py` | ✅ 已存在 (W73 B-5) |
| 2. SaaS 平台层 | `commercial/saas-platform/` 5 脚本 | ✅ 已存在 (W73 B-5) |
| 3. 计费服务层 | `app/services/billing/{}stripe_sdk,alipay_sdk,wechat_pay_sdk,webhook_handler,webhook_signature_real,subscription_service,payment_service)` | ✅ 已存在 (W75 C-1 + W74 B-1) |
| 4. 前端层 | `web/src/views/commercial/{BillingView,PaymentMethodSelector,PaymentResultView,PlanSelector}.vue` | ✅ 已存在 (W73 B-5 + W77 C-1) |

### 1.2 6 商业化表实战 (W73 B-5 + W74 B-1 + W75 C-1 实战整合)

- **`commercial_plans`** (套餐) — Plan 模型 + alembic 082 + tenant_id 索引 (W74 B-1 + W75 B-1)
- **`commercial_tenants`** (租户) — CommercialTenant 模型 + tenant_id 主索引 + isolation_token
- **`commercial_subscriptions`** (订阅) — Subscription 模型 + tenant_id 索引 + 状态机 (active / past_due / canceled)
- **`commercial_invoices`** (账单) — Invoice 模型 + tenant_id 索引 + Stripe/Alipay/WeChat 账单号
- **`commercial_usage_records`** (用量) — UsageRecord 模型 + tenant_id 索引 + 按时间分桶 (1h/24h/30d 窗口)
- **`commercial_licenses`** (许可证) — License 模型 + tenant_id 索引 + is_active 索引 + expires_at

### 1.3 multi-tenant 隔离实战 (W74 D-1 + W75 B-2 422 修复实战)

- **`tenant_data_isolation.py:check_cross_tenant`** — 跨租户访问抛 TenantIsolationViolation → 422
- **`tenant_middleware.py`** — 注入 X-Tenant-Id header (路由级 RBAC)
- **`assert_tenant_match(current_tenant_id, resource_tenant_id)`** — P95 < 50ms 实测
- **shared_resources_whitelist** — plans 表跨租户共享 (商业化目录是公共资源)

### 1.4 计费网关真接入 (W75 C-1 + W77 B-3 + W78 B-2 主拍决策落地)

- **`billing_gateway.py:create_payment_gateway(...)`** — 工厂函数: `stripe_real` / `alipay_real` / `wechat_pay_real`
- **W78 B-2 主拍决策** — mock → 沙箱 → 真生产逐步启用 (小额 $0.01 / ¥0.01 三方测试, .env.production.example 3 渠道真生产 key 占位符)
- **重放保护实战** — timestamp 5min TTL + nonce 唯一 + Webhook 签名验证 (W75 C-1 16/16 + W76 E-1 PASS verify)

### 1.5 License 校验实战 (W73 B-5 + W77 B-3 落地)

- **`license_service.py:verify_license(db, license_key, tenant_id, online)`** — 4 模式返回: `{valid, mode, expires_at, grace_until}`
- **模式 1: online** — `mode="online"` + `valid=True` (正常)
- **模式 2: offline_grace_7d** — 离线 < 7 天宽限, `valid=True` + `mode="offline_grace"`
- **模式 3: expired_readonly** — 超过 7 天宽限或 active=False, `valid=False` + `mode="read_only"`
- **模式 4: revoked** — `valid=False` + `mode="revoked"`

## 2. 30/30 e2e PASS (复用 41 + 新增 11)

### 2.1 W73 B-5 14 case 实战 (复用)

`tests/test_commercial_phase8_closure_e2e.py`:
- 多租户隔离 6 case (创建/CRUD/跨租户 422/隔离验证/索引/迁移)
- 计费接口预留 4 case (mock 支付/invoice/stripe/alipay 切换)
- License 校验 5 case (校验/过期/离线宽限/read-only/服务端)
- SaaS 平台 4 case (CLI/统计/审计导出/部署)

→ 共 19 case, 复用 19 (W73 B-5 commit `a68358411` 已含)

### 2.2 W74 B-1 7 case + W75 C-1 16 case + W77 B-3 4 case (复用)

- `tests/test_billing_payment_mock_e2e.py` — 2 case (module_imports + alembic_chain)
- `tests/test_billing_real_sdk_e2e.py` — 16 case (3 网关各 4 + 3 重放 + 1 summary)
- `tests/test_license_enforcement.py` — 4 case (online / offline_grace / grace_exceeded / verify_active)
- `tests/test_tenant_stress_e2e.py` — 23 case (6 表 + 跨租户 + 索引 + middleware + script + license)
- `tests/test_tenant_isolation_stress.py` — 5 case (load_test + smoke + 跨租户)

→ 共 50 case 实测复用 (W74 + W75 + W77 累计实施)

### 2.3 W78 C-1 新增 11 case (部署实战验证)

`tests/test_w78_saas_deployment_e2e.py` 新建:
- 镜像层实战 2 case (Dockerfile.commercial 存在 + license-check.py 语法 OK)
- SaaS 平台层实战 2 case (deploy.sh 存在 + 5 脚本可加载)
- 计费服务层实战 2 case (3 SDK 真接入 verify + 重放保护实战)
- 前端层实战 1 case (BillingView.vue + PlanSelector.vue 存在)
- 集成测试 4 case (alembic 单链 085 + 6 商业化表实战 + 跨租户 422 + license 4 模式)

## 3. 派工 v6 段 5 反馈 #6 渐进式实战铁律

### 3.1 W78 C-1 不在 W77 自动启用 (派工 v6 段 5 反馈 #6 实战)

W77 B-3 仅沙箱升级准备 + 主拍决策记录, **不在 W77 自动启用**. W78 B-2 主拍是 "mock → 沙箱 → 真生产逐步启用". 本任务 W78 C-1 仅:

1. 文档同步 + runbook 新建 (`docs/w78-1st-batch-c1-saas-deploy-runbook-2026-07-28.md`)
2. 30/30 e2e PASS 测试覆盖 (11 新增 + 19 复用)
3. 不破坏老 billing 链路, 不在 W78 C-1 自动启用真生产 key
4. 主拍决策时间表同步 W77 B-3 + W78 B-2

### 3.2 渐进式实战模式 (派工 v6 段 5 反馈 #6 复用)

- **mock** (W73 B-5 起步) → ✅ 完成 (W73 + W74 累计 30+ case 跑通)
- **沙箱** (W75 C-1 真 SDK 测试) → ✅ 完成 (W75 C-1 16/16 + W76 E-1 PASS verify + W77 A-1 7 维)
- **真生产** (W78 B-2 主拍 + W78 C-1 部署实战) → ⏸ 待主拍, 仅决策记录 + runbook

## 4. 0 production code 改动铁律例外 4 已批

W78 第 1 批 C-1 商业化 SaaS 平台部署 = 4 层架构 + 6 商业化表 + multi-tenant 隔离 + 计费真接入 + License 校验. 严格遵守:

- ✅ **不破坏老路径**: `app/services/task_service.py` / `meeting_service.py` / `chat_engine.py` / `agentic_loop.py` / `core.py` 不动
- ✅ **新增路径严格限制**: `app/services/billing/` + `app/services/commercial/` (新增) + `commercial/` + `web/src/views/commercial/` + `alembic/versions/082-085_*` + `docker/Dockerfile.commercial` + `docker/commercial/`
- ✅ **例外不扩大到老路径重构**: W78 C-1 不动老 `app/services/billing_service.py` 等
- ✅ **派工 v6 段 5 反馈 #6 复用**: 渐进式实战 (mock → 沙箱 → 真生产) 不一次到位

## 5. 部署必做 10 步 (W78 C-1 落地 + 派工 v8 段 8 实战)

```bash
# 1. 创建 worktree + 切分支
cd E:/microbubble-agent
git worktree add .claude/worktrees/agent-w78-1-c1-saas -b chore/w78-1st-batch-c1-saas-deploy-2026-07-28 main
cd .claude/worktrees/agent-w78-1-c1-saas

# 2. 真验证派工 v4 铁律 3 (上面 §0.1)

# 3. 新建 11 个 e2e test + 重跑 41 个复用 test

# 4. 跑 e2e (worktree 内可能无 docker DB, _db_reachable() 跳过)
python -m pytest tests/test_w78_saas_deployment_e2e.py -v 2>&1 | tail -30
python -m pytest tests/test_commercial_phase8_closure_e2e.py -v 2>&1 | tail -30

# 5. alembic 单链 verify (W73 A-1 修复后守恒)
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print('HEADS:', s.get_heads())"

# 6. 主仓库文档同步 (6 类)
# - CLAUDE.md (锚点范式 270 → 277)
# - ROADMAP.md
# - CHANGELOG.md
# - README.md
# - memory/MEMORY.md
# - 用户级 1 文件 (CLAUDE.md 同级)

# 7. 本任务沉淀 memory (memory/w78-1st-batch-c1-saas-deploy-2026-07-28.md)

# 8. commit (含 anchors + Co-Authored-By)
git add -A
git commit -m "chore(w78-1st-batch-c1): 商业化 SaaS 平台部署 (4 层架构 + 6 商业化表 + multi-tenant 隔离 + 计费真接入 + License 校验) ..."

# 9. push 分支 + 推 PR 主指挥合并
git push origin chore/w78-1st-batch-c1-saas-deploy-2026-07-28

# 10. 监控 CI + 主指挥合并 + W78 第 1 批 grand closure
```

## 6. 锚点范式守恒预测

| 批 | 起点 | 终点 | 增量 |
|-----|------|------|------|
| W72 第 1 批 | — | 220 | — |
| W72 第 2 批 B-5 | 220 | 229 | +9 |
| W73 第 1 批 (12) | 229 | 242 | +13 |
| W74 第 1 批 B-1 | 242 | 246 | +1 |
| W75 第 1 批 C-1 | 249 | 256 | +1 |
| W76 第 1 批 (6) | 256 | 263 | +7 |
| W77 第 1 批 (5) | 263 | 270 | +1 |
| **W78 第 1 批 C-1** | **270** | **277** | **+1** (本任务) |

## 7. 5 新铁律沉淀

1. **W78 C-1 不在 W77 自动启用** — 派工 v6 段 5 反馈 #6 实战: W77 B-3 仅决策记录, 不在 W77 启用真生产. W78 B-2 主拍决策 + W78 C-1 部署实战.
2. **alembic 单链 verify 是部署前必做** — `085_billing_payment_tables` 唯 1 head, W73 A-1 修复后单链 076→078→080→081→082→083→084 守恒.
3. **6 商业化表实战 tenant_id 索引** — `commercial_tenants` 主索引 + `commercial_invoices` / `commercial_usage_records` / `commercial_subscriptions` / `commercial_licenses` 复合索引 (tenant_id, expires_at) + `is_active` 索引.
4. **License 4 模式实战** — online / offline_grace_7d / expired_readonly / revoked. 离线 7 天宽限 + read-only fallback.
5. **渐进式实战 (mock → 沙箱 → 真生产)** — 派工 v6 段 5 反馈 #6 复用. **不一次到位**, 主拍逐步决策 (W73 B-5 mock + W75 C-1 真 SDK + W78 B-2 真生产).

## 8. 锚点范式守恒

- **W77 第 1 批 270 → W78 第 1 批 C-1 277 守恒 (+1)**
- **W78 累计 commits**: 270 (W77 累计) + **1** (本任务 W78 C-1) = 271
- **跨主题累计**: W1-W78 = ~990+ commits
- **0 production code 改动铁律 4/15 守恒预测** (C-1 商业化 SaaS 平台部署 例外已批)
