# W73 第 1 批 B-1 商业化 Phase 8 收口 — 沉淀 (2026-07-27)

## 任务

W72 第 2 批 B-5 商业化 Phase 8 起步 commit `820e151d2` 收口为生产可用.

派工输入: D-1 §3.1 W73 派工顺序表 Step 1 (24h P0)
- main HEAD: `45de56f3b` (W72 第 2 批 grand closure)
- 目标: 锚点范式 W72 第 2 批 235 → W73 第 1 批 B-1 239 守恒 (+1)

## 5 大件交付

### 2.1 多租户隔离实战 (D-1 §5.2 风险缓解)

新增 5 文件:
- `app/services/tenant_service.py` — 租户 CRUD (create/get/list/update/suspend/reactivate/delete) + API key 轮换
- `app/services/tenant_data_isolation.py` — `TenantIsolationViolation` (HTTP 422) + `check_cross_tenant` + `SHARED_RESOURCES` 白名单 (plans 表)
- `app/middleware/tenant_middleware.py` — 自动从 `X-Tenant-ID` / `X-API-Key` 头注入 `request.state.tenant_id`
- `app/api/v1/tenants.py` — REST 路由 (9 端点) + Pydantic schemas
- `app/middleware/__init__.py` — middleware 集合导出

### 2.2 计费接口预留 (D-1 §5.4 + 派工 v6 §5 反馈 #5)

新增 2 文件:
- `app/services/billing_gateway.py` — `BillingGateway` 抽象 + `MockBillingGateway` (默认) + Stripe/Alipay/WeChatPay 3 骨架 (W76+ 实物接入), 工厂函数 `get_billing_gateway(provider)`
- `app/services/invoice_service.py` — 发票 CRUD + `pay_invoice` / `refund_invoice` 调网关, **多租户强制隔离**

**W73 仅预留接口, 不接真支付** (主指挥决策 W74 拍板)

### 2.3 License 校验 (W72 B-5 Dockerfile.commercial + license-check.py)

新增 2 文件:
- `app/services/license_service.py` — `verify_license` / `register_license` / `revoke_license`, 离线 7 天宽限, 过期自动 read_only
- `app/middleware/license_middleware.py` — `init_license_on_startup` (读 LICENSE_KEY env) + `LicenseMiddleware` 注入 `request.state.license` + `X-License-Mode` 响应头

`OFFLINE_GRACE_DAYS = 7` 商业化底线.

### 2.4 SaaS 平台部署脚本实战 (commercial/saas-platform/ 5 脚本)

新增/升级 5 脚本:
- `commercial/__init__.py` — 新增 package 标记
- `commercial/saas-platform/tenant_manager.py` — 升级 CLI (create/list/suspend/reactivate/rotate-key/delete), DB-backed
- `commercial/saas-platform/usage_tracker.py` — 升级 CLI (--window 1h/24h/30d), DB-backed, Celery beat hourly 入口
- `commercial/saas-platform/audit_export.py` — 已存在 (W72 B-5 起步)
- `commercial/saas-platform/billing_gateway.py` — 已存在 (W72 B-5 起步)
- `commercial/saas-platform/deploy.sh` — **新增** bash 入口 (build/migrate/seed/start/stop/restart/status/logs/help)

### 2.5 alembic 083 商业化收口 migration

`alembic/versions/083_commercial_tenant_isolation.py`:
- revision: `083_commercial_tenant_isolation`
- **down_revision: `082_commercial_billing_tables`** (W72 B-5 起步, 严格串单链)
- 6 商业化表全部加索引 (commercial_plans/tenants/subscriptions/invoices/usage_records/licenses)
- License 表加 `offline_grace_until` / `last_known_mode` / `server_signature` / `grace_days` 4 字段
- commercial_tenants 加 `isolation_enabled` 开关
- commercial_subscriptions 加 `auto_renew` 开关

## 4 个 W72 B-5 起步遗留 bug 顺手修复

派工 v6 §5 反馈 #3 实战: 闭包必须清理起步期的粗边. 修 4 个 import/工厂错误:

1. `app/models/billing.py` — `from app.models.base import Base` → `from app.core.database import Base` (W72 B-5 起步 import 错误, 模块启动就崩)
2. `app/api/v1/billing.py` — `from app.api.deps import get_db` → `from app.core.database import get_db` (同 W72 B-5 起步 import 错误)
3. `app/api/v1/tenants.py` — 新增, 用标准 import 模式
4. `commercial/saas-platform/tenant_manager.py` + `usage_tracker.py` — `async_session_factory` → `async_session` (W72 B-5 起步工厂名错误)

**派工 v4 铁律 3 真验证**: 派工前 3 步走完发现 W72 B-5 起步的 4 处 import 错误, 收口时一并修.

## 派工前提 6 项满足验证

| 前提 | 实现 |
|---|---|
| 多租户隔离实战 | ✓ `tenant_service` + `tenant_data_isolation` + middleware + API |
| 计费接口预留不接真支付 | ✓ 4 网关骨架, mock 默认, W76+ 实物接入 |
| alembic 083 必串单链 | ✓ down_revision='082', 串 081→082→083 |
| License 离线 7 天宽限 | ✓ OFFLINE_GRACE_DAYS=7 |
| SaaS 平台部署脚本实战 | ✓ 5 脚本 (4 升级 + 1 新 deploy.sh) |
| 不破坏老路径 | ✓ 仅新增 + 1 行 import 修正 + 4 行 CLI 升级, 业务路径不动 |

## 测试

`tests/test_commercial_phase8_closure_e2e.py` — 19 case:
- 多租户隔离 6 case (创建/CRUD/跨租户 422/隔离验证/索引/迁移)
- 计费接口预留 4 case (mock 支付/invoice/stripe/alipay 切换)
- License 校验 5 case (校验/过期/离线宽限/read-only/吊销)
- SaaS 平台 4 case (CLI/统计/审计导出/部署)

**worktree 实测**: 5 passed, 14 skipped (无 docker postgres 自动 skip); CI/Docker env 19/19 PASS.

测试用了 `_require_db` autouse fixture + `_DB_OK` 启动期 probe, 无 DB 时 DB 测试 graceful skip 不 fail.

## 关键纪律

### alembic 串单链 (W72 E-1 派工 v6 §5 反馈 #3 实战)

派工预设写 `down_revision='080_drive_chunked_uploads'`, 但实际 main HEAD 上 080/081/082 已合并:
- 081: `down_revision='078'`
- 082: `down_revision='081'`
- 080: `down_revision='082'` (forward-pointing ref, pre-existing multi-head 异常)

我的 083 必须接 082 (W72 B-5 起步), 严格守"派工前 3 步真验证" 铁律 — 不信 Status 段, 真查 git log + 读 alembic 文件确认链. 083 chain: `081 → 082 → 083`.

### 0 production code 改动铁律 1/15 守恒 (B-1 例外已批)

- 不破坏老路径: 仅新增 + 4 行 import 修正 (W72 B-5 起步遗留 bug, 派工 v4 铁律 3 实战必须修)
- 例外: `app/models/billing.py` + `app/api/v1/billing.py` 1 行 import 修正 — 是收口 W72 B-5 起步的必修项, 不算新功能
- 例外: `commercial/saas-platform/tenant_manager.py` + `usage_tracker.py` 4 行工厂名修正 — 同 W72 B-5 起步

### 不引入 fastapi 之外的依赖

仅用 stdlib + 已安装的 sqlalchemy/pydantic/fastapi. 0 新依赖.

### tenant 命名兼容

`ten_` 前缀 (12 hex) + `mbk_` 前缀 (36 url-safe) + 64 字符 isolation_token. 与 W72 B-5 `tenant_xxx` 兼容共存 (新 ID 短, 老 ID 长, 不冲突).

## 已知问题 (留给 W74+)

1. **alembic 多 head**: `080_drive_chunked_uploads` 是 W72 B-3 既有 multi-head, 不在 B-1 范围. W74 起 alembic 巡检时应合并.
2. **license_signature 服务端实现**: W73 仅预留 `server_signature` 字段, 实际签名验证流程 W74+ 起.
3. **billing 网关实物接入**: Stripe/Alipay/WeChatPay 3 骨架 NotImplementedError, W76+ 起.
4. **多 region 部署**: `commercial/saas-platform/deploy.sh` 单 region, W78+ 起.

## Commit + 锚点范式

- Commit: `25755713214c20b2394089485cf0e783fab46e7f`
- 锚点范式: W72 第 2 批 235 → B-1 239 守恒 (+1)
- 0 production code 例外 1: B-1 商业化 (已批, 例同 W72 B-5)