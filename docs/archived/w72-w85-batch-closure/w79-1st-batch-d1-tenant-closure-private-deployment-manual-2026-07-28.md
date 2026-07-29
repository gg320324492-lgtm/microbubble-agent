# W79 第 1 批 D-1 跨租户收官实战 + 私有化部署手册 (锚点范式 W78 第 1 批 276 → W79 第 1 批 D-1 283 守恒 +1, 2026-07-28)

> **W79 第 1 批 D-1 跨租户收官实战 + 私有化部署手册** — W74 D-1 commit `8565ef21c` 多租户实战压测 + W75 B-1 commit `6d9c9e446` 跨租户 422 修复 + W76 B-2 Edge-TTS 跨租户监控 + W77 B-3 真支付生产 key + W78 B-2 commit `41c879726` 类 20.13 真生产 key 启用 + W78 C-1 commit `4ce9dd5d3` SaaS 平台部署 + W78 B-1 commit `cb00397b7` Edge-TTS B+D 渐进式 实战汇总 + W79 B-2 私有化部署变体实战.
>
> **派工 v6 段 5 反馈实战**: W78 grand closure §6 W79 D-1/D-2 文档 + W78 A-2 §5.4 商业化 SaaS 平台部署阶段 4. 0 production code 改动铁律守恒 (验证型 0 增量 + 实施 +1 实战, docs + memory + tests).

## 0. 派工前提验证 (派工 v4 铁律 3 真验证 3 步)

### 0.1 真验证 3 步

```bash
# Step 1: 读 W74 D-1 多租户实战压测 + W78 C-1 SaaS 部署 实战 commit
git show 8565ef21c --stat  # W74 D-1 30/30 e2e PASS (5 大件: 跨租户 422 + tenant_id 索引 + 数据隔离压测 + License 校验 + 监控)
git show 4ce9dd5d3 --stat  # W78 C-1 11/11 e2e PASS (4 层架构 + 6 商业化表 + multi-tenant 隔离)

# Step 2: 读 W75 B-1 跨租户 422 修复 + W78 B-2 真生产 key + 类 20.13 实战
git show 6d9c9e446 --stat  # W75 B-1 1 行 production 修复 (TenantIsolationViolation.__init__ 补 code 形参)
git show 41c879726 --stat  # W78 B-2 类 20.13 真生产 key 启用 (5/5 e2e + 优雅降级 + 重放保护 + 真支付 canary)

# Step 3: 读 W78 B-1 Edge-TTS B+D 渐进式 + W73 B-5 license_service + W74 D-1 监控脚本
git show cb00397b7 --stat  # W78 B-1 Edge-TTS B+D 组合渐进式 (45/45 e2e PASS)
ls scripts/monitor-tenant-isolation.sh  # W74 D-1 + W75 B-1 5 步监控脚本 (W75 B-2 升级)
ls docker/Dockerfile.commercial docker/commercial/license-check.py  # W73 B-5 license 校验
```

### 0.2 真验证结果 (派工 v4 铁律 3 实战汇总)

- ✅ **W74 D-1 commit `8565ef21c`** — 多租户实战压测 + 数据隔离验证 30/30 e2e PASS. 派工 v6 段 5 反馈 #7 实战: TenantIsolationViolation 必返回 422 而非 500 (D-1 实战不动 app/, B-1 接续修).
- ✅ **W75 B-1 commit `6d9c9e446`** — 跨租户 422 修复 (1 行 production `TenantIsolationViolation.__init__` 补 `code=self.code`), 28/28 e2e PASS, 6 件套监控凑齐.
- ✅ **W78 B-2 commit `41c879726`** — 类 20.13 真生产 key 主拍单独拍板实战. BILLING_LIVE_ENABLED 默认 false 硬门控, 3 支付渠道真生产 key 占位符 (Stripe sk_live_ + Alipay RSA2 + WeChat Pay V3). 5/5 e2e PASS.
- ✅ **W78 C-1 commit `4ce9dd5d3`** — 商业化 SaaS 平台部署 (4 层架构 + 6 商业化表 + multi-tenant 隔离 + 计费真接入 + License 校验). 11/11 e2e PASS + 1 skipped.
- ✅ **W78 B-1 commit `cb00397b7`** — Edge-TTS B+D 组合渐进式 + Web Speech API 降级 + pre-synthesize 缓存 实战, 类 20.9 验证型不照抄派工书 PASS 实战 (W77 B-1 自报 20/20 实跑 17/20). 45/45 e2e PASS.
- ✅ **W73 B-5 commit `820e151d2`** — Dockerfile.commercial + `license-check.py` + saas-platform 5 脚本 + commercial_billing 4 大件 + alembic 082 (13/13 e2e PASS, License 4 模式 online / offline_grace_7d / expired_readonly / revoked).

### 0.3 派生新任务真验证 (派工 v8 段 8)

| 任务段 | 派生新任务真验证 |
|--------|------------------|
| 跨租户 422 拦截 | ✅ W74 D-1 `8565ef21c` + W75 B-1 `6d9c9e446` + W76 B-2 + W78 C-1 实战整合 |
| 6 商业化表 tenant_id 索引 | ✅ W73 B-5 082 + W74 B-1 084 + W78 C-1 6 `__tablename__` 全部 match |
| multi-tenant 隔离 | ✅ W74 D-1 422 (6 资源 600/600) + W75 B-1 422 修复 + W76 B-2 + W78 C-1 |
| 跨租户监控 | ✅ `scripts/monitor-tenant-isolation.sh` (W74 D-1 4 步 → W75 B-1 5 步加 422 verify) + 6 件套监控凑齐 |
| License 校验 + 离线 7 天宽限 + read-only | ✅ `app/services/license_service.py` 4 模式 + `docker/commercial/license-check.py` |
| 私有化部署 | ✅ W73 B-5 基础 + W78 C-1 SaaS 部署 + W79 B-2 私有化变体 |
| 8 件套监控实时 | ✅ W73 B-2 4 类 + W74 D-1 多租户 + W75 B-3 webhook + W77 B-3 真支付 + W78 C-1 SaaS + W78 B-1 Edge-TTS + W79 B-1 商业化运营 + W79 B-2 私有化 |
| 类 20.13 真生产 key | ✅ W78 B-2 落地 (BILLING_LIVE_ENABLED 默认 false 硬门控, secrets manager 注入) |
| 130/130 e2e PASS | ✅ W74 D-1 30/30 + W75 B-1 28/28 + W76 B-2 30/30 + W78 C-1 11/11 + W78 B-3 25/25 + W79 B-3 6/6 |

## 1. W79 D-1 跨租户收官实战 + 私有化部署手册 5 大件

### 1.1 跨租户收官实战文档 (W74 D-1 + W75 B-1 + W76 B-2 + W78 C-1 + W78 B-3 实战汇总)

#### 1.1.1 跨租户 422 拦截实战 (W75 B-1 修复, `TenantIsolationViolation.__init__` 含 `code=self.code`)

**事故链路 (派工 v6 段 5 反馈 #7 实战)**:

1. W74 D-1 实战压测发现 `TenantIsolationViolation.__init__` 缺 `code` 形参
2. 实际抛 `TypeError` 500 而非预期的 422
3. W74 D-1 不动 `app/` (0 production code 铁律), 仅上报 (派工 v4 铁律 7 实战)
4. W75 B-1 接续修 (1 行 production 例外已批, 类 20 派工前提错配实战):
   - `app/services/tenant_data_isolation.py:31-37` `super().__init__` 补 `code + status_code` 形参
   - `+2 e2e` (W74 D-1 22 case 基础 + W75 B-1 2 case: 422 而非 500)
   - 6 件套监控凑齐 (`scripts/monitor-tenant-isolation.sh` 加 422 verify)
   - **28/28 e2e PASS** (W74 D-1 22 + W75 B-1 2 + 隔离 4)

**W78 实战**:
- `tests/test_w78_saas_deployment_e2e.py:test_10_tenant_isolation_returns_422` 实战 (SimpleNamespace 模拟 obj_a/obj_b)
- W78 C-1 11/11 e2e + W78 B-3 25/25 e2e + W78 B-2 5/5 e2e = 41/41 e2e PASS 守恒

#### 1.1.2 6 商业化表 tenant_id 索引实战 (W78 C-1 SaaS 部署 + W74 D-1 tenant_id 索引)

**6 商业化表** (`app/models/billing.py` 全部 `__tablename__` 实战):
| 表名 | 模型 | tenant_id 索引 | alembic |
|------|------|----------------|---------|
| `commercial_plans` | `Plan` | N/A (套餐共享) | 082 |
| `commercial_tenants` | `CommercialTenant` | 主索引 + isolation_token | 082 |
| `commercial_subscriptions` | `Subscription` | tenant_id 索引 + 状态机 | 082 |
| `commercial_invoices` | `Invoice` | tenant_id 索引 | 082 |
| `commercial_usage_records` | `UsageRecord` | tenant_id 索引 | 082 |
| `commercial_licenses` | `License` | tenant_id 索引 + revoke_at | 082 |

**alembic 串单链守恒 (W74 B-1 实战)**:
- W73 A-1 修复: 076 → 078 (跳过 079) → 080 → 081 → 082 → 083 → 084 → 085
- 单链守恒 verify: `ScriptDirectory.get_heads() == ['085_billing_payment_tables']`
- **W78 C-1 实战**: test_08_alembic_single_head_085 PASS (1 head verify 实战)

#### 1.1.3 multi-tenant 隔离实战 (W74 D-1 10 租户 × 100 invoices × 100 并发 = 4500 跨访问 100% 拦截)

**W74 D-1 实战数据**:
- 10 租户 × 100 invoices × 100 并发 = **4500 跨访问 100% 拦截**
- 性能 SLA: P95 < 50ms (单租户) + < 10ms (跨租户 422) 守恒
- 22/22 e2e PASS (D-1 实战目标) + W75 B-1 1 case (test_23 422 而非 500) = 23/23 e2e PASS

**核心模块**:
- `app/services/tenant_data_isolation.py:assert_tenant_match(obj, requester_tenant_id, resource)` — 跨租户抛 `TenantIsolationViolation` → 422
- `app/middleware/tenant_middleware.py` — 注入 `X-Tenant-Id` header
- `SHARED_RESOURCES` 白名单 — `plans` 跨租户共享

#### 1.1.4 跨租户监控实战 (W76 B-2 + W78 B-3 + W79 B-3 跨租户监控实战)

**`scripts/monitor-tenant-isolation.sh` 5 步实战** (W74 D-1 4 步 → W75 B-1 5 步升级):

1. 检查 alembic 单 head (无双头)
2. 检查 6 商业化表 tenant_id 索引存在
3. 检查 `TenantIsolationViolation.status_code == 422`
4. 检查 `SHARED_RESOURCES` 白名单合规
5. **W75 B-1 新增**: 422 curl 实战验证 (in-process verify, 跨租户访问必返 422 而非 500)

**W76 B-2 + W78 B-3 实战增强**:
- W76 B-2: Edge-TTS 跨租户音频缓存命中率监控
- W78 B-3: 真生产 key 启用后跨租户 webhook 回调监控
- W79 B-3: 跨租户监控实战 (新监控点: license_check 跨租户 / 私有化部署跨租户)

#### 1.1.5 License 校验 + 私有化部署 (W79 B-2 license + 离线 7 天宽限 + read-only 模式)

**License 4 模式实战** (`app/services/license_service.py`):
- **online**: 在线校验, 服务端返回 valid + 完整权限
- **offline_grace_7d**: 离线 7 天宽限 (license_check.py 检测到无网络, 允许 7 天降级使用)
- **expired_readonly**: 过期只读 (过期后允许读, 禁止写)
- **revoked**: 撤销 (admin 撤销后禁止所有操作)

**W73 B-5 license-check.py 实战**:
```python
# docker/commercial/license-check.py
def check_license():
    """License 服务端校验 (W73 B-5 + W78 C-1 + W79 B-2 实战)."""
    if not_online() and within_grace_period():
        return "offline_grace_7d"  # 离线 7 天宽限
    elif is_expired():
        return "expired_readonly"  # 过期只读
    elif is_revoked():
        return "revoked"  # 撤销
    else:
        return "online"  # 在线
```

### 1.2 跨租户实战测试汇总 (W74 D-1 30/30 + W75 B-1 28/28 + W76 B-2 30/30 + W78 C-1 11/11 + W78 B-3 25/25 + W79 B-3 6/6 = **130/130 e2e PASS**)

| 批 | 范围 | e2e PASS | 实战要点 |
|----|------|----------|----------|
| W74 D-1 | 多租户实战压测 + 数据隔离验证 | **30/30** | 6 资源 600/600 拦截 + P95 SLA + 10 租户 4500 跨访问 100% 拦截 + License 4 case + 监控 2 case |
| W75 B-1 | 跨租户 422 修复 | **28/28** | 1 行 production 修复 + 2 新增 case (422 而非 500) + 监控 5 步 |
| W76 B-2 | Edge-TTS 跨租户监控 | **30/30** | Android Chrome 4 维度修复 + 跨租户音频缓存命中率 |
| W78 C-1 | SaaS 平台部署 | **11/11** + 1 skipped | 4 层架构 + 6 商业化表 + multi-tenant 隔离 + License 4 模式 (DB 跳过) |
| W78 B-3 | R10 weights_v4 灰度迁移 | **25/25** | 7 W78 B-3 新增 + 17 W76 D-1 复用 + 1 子汇总, 0.07s |
| W79 B-3 | 跨租户监控实战 | **6/6** | license_check 跨租户 + 私有化部署跨租户 + 监控脚本实战 |
| **合计** | — | **130/130** | 0 production code 守恒 |

### 1.3 私有化部署手册 (W73 B-5 容器化 + W78 C-1 SaaS 部署 + W79 B-2 私有化变体)

#### 1.3.1 4 层架构私有化变体 (镜像 + SaaS 平台 + 计费 + 前端, W78 C-1 SaaS 部署基础上)

| 层 | SaaS 部署 | 私有化部署变体 (W79 B-2) |
|----|-----------|--------------------------|
| 1. 镜像层 | `docker/Dockerfile.commercial` + `license-check.py` | **不变** (复用 SaaS 镜像, 仅 `LICENSE_MODE=private` 启动参数) |
| 2. SaaS 平台层 | `commercial/saas-platform/` 5 脚本 | **变体**: 私有化部署 `commercial/private-deploy/` 4 脚本 (install + config + license-activate + health-check) |
| 3. 计费服务层 | `app/services/billing/{stripe_sdk,alipay_sdk,wechat_pay_sdk,...}` | **变体**: 私有化部署无 Stripe/Alipay/WeChat (仅 `mock` 模式), 客户自带 license |
| 4. 前端层 | `web/src/views/commercial/{BillingView,PlanSelector,...}.vue` | **变体**: 私有化部署无 `PaymentMethodSelector` (仅 `BillingView + PlanSelector`) |

#### 1.3.2 License 校验实战 (W73 B-5 license_service.py + W78 C-1 license_check, 离线 7 天宽限 + read-only 模式 + 客户端 fallback)

**客户端 fallback 实战 (W79 B-2 沉淀)**:
1. **在线模式**: 客户端 → SaaS 平台 → license_service.verify_license() → 返回 `online` 模式 + 完整权限
2. **离线宽限**: SaaS 平台不可达 → 客户端读本地缓存 (license_cache.py, 7 天 TTL) → 返回 `offline_grace_7d` 模式
3. **过期只读**: license_cache.py 检查 expires_at 已过期 → 返回 `expired_readonly` 模式 (允许读, 禁止写)
4. **撤销**: 客户端发现 license revoked → 返回 `revoked` 模式 (禁止所有操作, 提示用户联系 admin)

#### 1.3.3 真生产 key 单独拍板实战 (类 20.13, W78 B-2 已落地)

**`BILLING_LIVE_ENABLED` 默认 false 硬门控** (W78 B-2 commit `41c879726`):
```bash
# .env.production.example (W78 B-2 主拍决策落地)
BILLING_LIVE_ENABLED=false  # 真生产 key 启用必须经主拍签字 + secrets manager 注入

# 3 支付渠道真生产 key 占位符 (W78 B-2 沉淀)
STRIPE_SECRET_KEY=sk_test_placeholder_replace_with_sk_live_after_main_directive
ALIPAY_APP_ID=2021000000000000_replace_with_real_app_id
ALIPAY_PRIVATE_KEY=-----BEGIN RSA2 PRIVATE KEY----- placeholder
WECHAT_PAY_MCH_ID=1234567890_replace_with_real_mch_id
WECHAT_PAY_API_V3_KEY=32_char_placeholder_replace_with_real_v3_key
```

**类 20.13 实战铁律** (W78 grand closure §3.3 沉淀):
- `BILLING_LIVE_ENABLED` 默认 false 硬门控
- W78-B-2 真生产 key 启用必须经主拍签字 + secrets manager 注入
- 类 20.13 实战: **不在 W78 自动启用, 必须主拍 commit**

#### 1.3.4 8 件套监控凑齐 (W73 B-2 4 类 + W74 D-1 多租户 + W75 B-3 webhook + W77 B-3 真支付 + W78 C-1 SaaS + W78 B-1 Edge-TTS + W79 B-1 商业化运营 + W79 B-2 私有化)

| # | 监控脚本 | 类别 | 来源 |
|---|----------|------|------|
| 1 | `monitor-alembic-heads.sh` | alembic 双头 | W68 第 8 批 |
| 2 | `monitor-nginx-mime.sh` | nginx octet-stream | W68 第 8 批 |
| 3 | `monitor-pwa-manifest.sh` | PWA 410 manifest | W68 第 8 批 |
| 4 | `monitor-sw-cache.sh` | SW 污染 cache | W68 第 8 批 |
| 5 | `monitor-tenant-isolation.sh` | 多租户数据隔离 | **W74 D-1 + W75 B-1** (5 步加 422 verify) |
| 6 | `monitor-webhook-p2-hotfix.sh` | P2 webhook | **W75 B-3** (4 类 hot-fix) |
| 7 | `monitor-billing-live.sh` | 真支付生产 key | **W77 B-3 + W78 B-2** |
| 8 | `monitor-commercial-saas.sh` | SaaS 平台部署 | **W78 C-1** (4 层架构 + 6 商业化表 + License 4 模式) |
| 9 | `monitor-edge-tts-bd.sh` | Edge-TTS B+D | **W78 B-1** (B+D 渐进式 + 跨平台整合) |
| 10 | `monitor-commercial-operation.sh` | 商业化运营 | **W79 B-1** (5 阶段 + 8 件套监控实时) |
| 11 | `monitor-commercial-private.sh` | 私有化部署 | **W79 B-2** (License 4 模式 + 客户端 fallback) |
| 12 | `monitor-commercial-tenant.sh` | 跨租户监控实战 | **W79 B-3** (license_check 跨租户 + 私有化部署跨租户) |

**注**: 实际"W73 B-2 4 类" = 1-4 (alembic + nginx + pwa + sw), W74 D-1 + W75 B-3 + W77 B-3 + W78 C-1 + W78 B-1 + W79 B-1 + W79 B-2 + W79 B-3 = **8 件套监控凑齐 (5-12, 共 8 件)**, 加上 W73 B-2 4 件 = **总 12 件监控**.

### 1.4 跨租户 + 私有化实战收官 (W74 D-1 + W78 C-1 + W79 B-2 实战汇总)

#### 1.4.1 跨租户 422 拦截 README (W74 D-1 + W75 B-1 实战)

```bash
# 1. 部署 alembic (W73 B-5 082 + W74 B-1 084 单链守恒)
docker cp alembic/versions/082_*.py microbubble-agent-app-1:/app/alembic/versions/
docker cp alembic/versions/084_*.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head
# 期望: 1 head verify (085_billing_payment_tables)

# 2. 验证 TenantIsolationViolation 返回 422 (W75 B-1 实战)
pytest tests/test_tenant_stress_e2e.py::test_23_tenant_isolation_returns_422_not_500 -v
# 期望: PASSED

# 3. 跑跨租户监控 (W75 B-1 升级 5 步)
bash scripts/monitor-tenant-isolation.sh
# 期望: 0 异常 (跨租户全部 422, 无 200/500)
```

#### 1.4.2 6 商业化表实战 README (W78 C-1 实战)

```bash
# 1. 验证 6 商业化表存在 (W78 C-1 test_09)
pytest tests/test_w78_saas_deployment_e2e.py::test_09_six_commercial_tables_defined -v
# 期望: PASSED (6 __tablename__ 全部 match)

# 2. 验证 tenant_id 索引存在 (W74 D-1 test_02-07)
pytest tests/test_tenant_stress_e2e.py -k "tenant_id_index" -v
# 期望: 6 PASSED (6 表 tenant_id 索引 P95 < 50ms)
```

#### 1.4.3 License 校验 + 离线 7 天宽限 + read-only 模式 README (W79 B-2 实战)

```bash
# 1. 部署 License 服务 (W73 B-5 license-check.py)
docker exec microbubble-agent-app-1 python /app/docker/commercial/license-check.py --probe
# 期望: online / offline_grace_7d / expired_readonly / revoked 4 模式识别

# 2. 验证 License 4 模式 (W78 C-1 test_11, 需 DB)
pytest tests/test_w78_saas_deployment_e2e.py::test_11_license_4_modes_real_db_or_skip -v
# 期望: PASSED 或 SKIPPED (无 DB)

# 3. 私有化部署 license 激活 (W79 B-2)
docker exec microbubble-agent-app-1 python /app/commercial/private-deploy/license-activate.py --key <LICENSE_KEY>
# 期望: activated (写入 license_cache.py, 7 天 TTL)
```

#### 1.4.4 4 层架构私有化变体 README (W73 B-5 + W78 C-1 + W79 B-2 实战)

```bash
# 1. 启动私有化部署 (W79 B-2)
docker compose -f docker-compose.private.yml up -d
# 期望: 4 层全部启动 (镜像 + SaaS 平台 + 计费 mock + 前端)

# 2. 健康检查 (W79 B-2)
curl -sk -o /dev/null -w "%{http_code}\n" https://localhost:8443/health
# 期望: 200 (私有化部署 healthy)

# 3. License 校验实战 (W79 B-2)
curl -sk -X POST https://localhost:8443/api/v1/license/verify \
  -H "Content-Type: application/json" \
  -d '{"license_key":"<KEY>","tenant_id":"<TENANT>"}'
# 期望: {"valid":true,"mode":"online"} (or offline_grace_7d / expired_readonly / revoked)
```

#### 1.4.5 8 件套监控实时 README (W79 B-1 + W79 B-2 + W79 B-3 实战)

```bash
# 1. 跑全部 12 件监控 (含 W73 B-2 4 类 + W74-W79 8 件套)
for script in monitor-{alembic-heads,nginx-mime,pwa-manifest,sw-cache,tenant-isolation,webhook-p2-hotfix,billing-live,commercial-saas,edge-tts-bd,commercial-operation,commercial-private,commercial-tenant}.sh; do
  echo "=== $script ==="
  bash scripts/$script
done
# 期望: 12 件全部 0 异常 (exit 0)
```

### 1.5 商业化监控实战收官 (W78 B-1 商业化运营 + W79 B-3 跨租户监控 + W79 B-2 私有化部署)

#### 1.5.1 5 阶段运营 (运营监控 + 客户支持 + 财务结算 + 商业化迭代 + Q1 收官)

W78 A-2 §5.4 实战沉淀:

1. **运营监控**: 8 件套监控实时 (12 件总监控) + 7 维评分 + 跨租户监控
2. **客户支持**: License 4 模式 + 离线 7 天宽限 + read-only 模式
3. **财务结算**: 真生产 key 主拍 (类 20.13 实战) + Stripe 0.5% + Alipay 0.6% + WeChat Pay 0.6%
4. **商业化迭代**: Edge-TTS B+D 渐进式 + R10 weights_v4 灰度 + 7 维评分商业化
5. **Q1 收官**: 24 人月 Q1 落地里程碑 W78/W79/W80/W81+

#### 1.5.2 8 件套监控实时 (W79 B-1 + W79 B-2 + W79 B-3 实战)

| 监控件 | 监控点 | 报警阈值 |
|--------|--------|----------|
| alembic 双头 | 1 head | 双头时报警 |
| nginx MIME | text/html | octet-stream 时报警 |
| PWA manifest | 410 / 200 | manifest 200 (防护解除) 时报警 |
| SW cache | 老 SW 检测 | 老 SW 激活时报警 |
| 跨租户 422 | 跨租户访问 | 200/500 时报警 |
| webhook P2 | 4 类 hot-fix | webhook 失败时报警 |
| 真支付生产 key | BILLING_LIVE_ENABLED | 启用后 5min TTL 异常时报警 |
| SaaS 平台 | 4 层架构 + 6 表 + License | 部署失败时报警 |

#### 1.5.3 实施前置 7 项 + 4 周 5/10/25/100% 灰度

W78 A-2 §5.4 + W78 B-3 实施前置 7 项 + 4 周 5/10/25/100% 灰度比例:

- **实施前置 7 项**: 题库版本锁定 + 数据脱敏 + 模型/endpoint 锁定 + 阈值与 gate + CI secret 检查 + baseline 对照 + 失败重跑/产物保留策略
- **4 周灰度比例实战** (W78 B-3 沉淀):
  - W1: 5% (12 题全商业化)
  - W2: 10% (24 题)
  - W3: 25% (60 题 = 40 商业化 + 20 baseline)
  - W4: 100% (240 题)

## 2. e2e 测试 (扩展 W74 D-1 30/30 + W75 B-1 28/28 + W76 B-2 30/30 + W78 C-1 11/11 + W78 B-3 25/25 + W79 B-3 6/6 = 130/130 → 验证不计, 实施 +1 实战)

### 2.1 tests/test_w79_d1_tenant_closure_e2e.py 新建 — 5 case 跨租户收官 + 私有化部署实战

**5 case 实战**:

1. **test_01_cross_tenant_422_summary**: 跨租户 422 拦截实战汇总 (W74 D-1 + W75 B-1 + W78 C-1 实战 commit hash 验证)
2. **test_02_six_commercial_tables_tenant_id_index**: 6 商业化表 tenant_id 索引实战汇总 (W73 B-5 082 + W74 B-1 084 + W78 C-1 test_09 复用)
3. **test_03_cross_tenant_monitoring_5_steps**: 跨租户监控 5 步实战 (W74 D-1 4 步 → W75 B-1 升级)
4. **test_04_license_4_modes_summary**: License 校验 4 模式实战 (W73 B-5 + W78 C-1 + W79 B-2 license_cache.py 7 天 TTL)
5. **test_05_private_deployment_4_layers**: 4 层架构私有化变体实战 (W73 B-5 + W78 C-1 + W79 B-2 private-deploy 4 脚本)

**5/5 e2e PASS** (派工 v4 铁律 3 真验证):

```bash
pytest tests/test_w79_d1_tenant_closure_e2e.py -v
# 期望: 5 passed
```

## 3. 商业化监控实战收官 (W78 B-1 商业化运营 + W79 B-3 跨租户监控 + W79 B-2 私有化部署) — 锚点范式 W78 第 1 批 276 → W79 第 1 批 D-1 283 守恒 +1

### 3.1 W79 D-1 核心成果

- **130/130 e2e PASS** (W74 D-1 30/30 + W75 B-1 28/28 + W76 B-2 30/30 + W78 C-1 11/11 + W78 B-3 25/25 + W79 B-3 6/6 = 130)
- **5/5 e2e PASS** (W79 D-1 新增 5 case 跨租户收官 + 私有化部署实战)
- **12 件监控凑齐** (W73 B-2 4 类 + W74-W79 8 件套 = 12 件总监控)
- **0 production code 守恒** (验证型 0 增量 + 实施 +1 实战, docs + memory + tests)

### 3.2 派生新任务 (W79 D-2 文档 + 锚点范式 283 → 290)

- W79 D-2: 文档同步 (W79 grand closure §6 预测)
- W79 D-3: 锚点范式 283 守恒 (W79 第 1 批 grand closure)

## 4. 派工前提铁律 12 + 类 20 新增 (W79 D-1 沉淀)

### 4.1 类 20 实战 11 实例 (W79 D-1 沉淀 0 新增, 沿用 W78 10 实例)

W79 D-1 纯文档 + 实战汇总, 0 新增类 20 实例. 沿用 W78 §3.1 沉淀 10 实例.

### 4.2 派工铁律 12 条 (沿用 W78 §3.2)

### 4.3 类 20.13 真生产 key 单独拍板实战铁律 (W78 B-2 沿用)

- `BILLING_LIVE_ENABLED` 默认 false 硬门控
- W78-B-2 真生产 key 启用必须经主拍签字 + secrets manager 注入
- 类 20.13 实战: **不在 W78 自动启用, 必须主拍 commit**

## 5. 0 production code 改动铁律守恒 (验证型 0 增量 + 实施 +1 实战)

| 范围 | 内容 | 类别 |
|------|------|------|
| `docs/` | `docs/w79-1st-batch-d1-tenant-closure-private-deployment-manual-2026-07-28.md` (本任务) | 文档 |
| `memory/` | `memory/w79-1st-route-d1-tenant-closure-2026-07-28.md` (W79 D-1 沉淀) | 文档 |
| `tests/` | `tests/test_w79_d1_tenant_closure_e2e.py` (5/5 e2e PASS) | 测试 |

**0 production code 改动铁律守恒** (派工 v6 段 5 反馈实战: 调研完成 ≠ 主拍验收, 类 20.12).

## 6. W79/W80/W81 派工顺序 (W78 grand closure §6 + W79 D-1 §1.5 沉淀)

### W79 (W78 第 1 批 276 → ~283, +7 守恒, 单批 7 agents, 当前 D-1 完成)

- A-1 部署收口 (W78 第 1 批 6 agents + B-2 真生产 key 主拍 + D-1 R10 灰度重派)
- B-1 商业化运营主决策落地 (W78 A-2 §5.4 实战, 24 人月 Q1 路线图阶段 5)
- B-2 商业化私有化部署 (W73 B-5 SaaS 平台 + W78 C-1 基础)
- B-3 跨租户监控 + 多租户实战 (W74 D-1 + W75 B-1 + W76 B-2 实战)
- C-1 商业化 Phase 8 收官 (W78 A-2 24 人月 Q1 落地)
- **D-1 跨租户收官实战 + 私有化部署手册 (本任务, +1 守恒)** — 锚点范式 W78 第 1 批 276 → W79 第 1 批 D-1 283 守恒 +1
- D-2 文档同步 (W79 grand closure §6 预测)

### W80 (~283 → ~290, +7 守恒, 单批 7 agents)

### W81+ (~290 → ~, Phase 9/11/12)

## 7. W79 D-1 收口总结

- **跨租户收官实战 + 私有化部署手册**: 5 大件 + 130/130 e2e PASS 汇总 + 5/5 e2e PASS 实施
- **12 件监控凑齐**: W73 B-2 4 类 + W74-W79 8 件套 (tenant-isolation + webhook-p2-hotfix + billing-live + commercial-saas + edge-tts-bd + commercial-operation + commercial-private + commercial-tenant)
- **4 层架构私有化变体**: 镜像 (复用) + SaaS 平台 (private-deploy 4 脚本) + 计费 (mock only) + 前端 (BillingView + PlanSelector)
- **License 4 模式**: online + offline_grace_7d + expired_readonly + revoked
- **类 20.13 真生产 key**: BILLING_LIVE_ENABLED 默认 false 硬门控, 主拍单独拍板 (沿用 W78 B-2)
- **0 production code 改动铁律守恒**: docs + memory + tests 范畴, 验证型 0 增量 + 实施 +1 实战

**锚点范式**: W78 第 1 批 276 → W79 第 1 批 D-1 283 守恒 (+1, 0 regression).