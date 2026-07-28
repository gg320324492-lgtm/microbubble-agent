# W80 第 1 批 B-2 商业化私有化部署 + 客户支持 Runbook

**批次**: W80 第 1 批 B-2  
**日期**: 2026-07-28  
**锚点范式**: W79 第 1 批 283 → W80 第 1 批 B-2 288 守恒 (+1)  
**依据**: W78 C-1 `4ce9dd5d3` + W79 B-2 `4009a6dbb` + W79 B-3 `0b961707973c4f66e0a7aa7ad35f369e309f0eef`

---

## 段 0 前置条件 + 依赖链

| 依赖 | commit | 验证命令 |
|------|--------|---------|
| W78 C-1 SaaS 部署 11/11 e2e | `4ce9dd5d3` | `git show 4ce9dd5d3 --stat` |
| W79 B-2 私有化部署 10/10 e2e | `4009a6dbb` | `git show 4009a6dbb --stat` |
| W79 B-3 跨租户监控 6/6 e2e | `0b961707973c` | `git show 0b961707973c --stat` |
| W73 B-5 商业化 Phase 8 起步 | `820e151d2` | `git show 820e151d2 --stat` |

**0 production code 改动铁律例外 3 已批**:
1. W79 B-2 已批: `commercial/private-deployment/` 新增 (3 文件)
2. W79 B-2 已批: `scripts/private_deployment_monitor.sh` 新增
3. W80 B-2 新批: `scripts/private_deployment_support.sh` 新增 + `tests/test_w80_b2_private_support_e2e.py` 新增

---

## 段 1 4 层架构私有化变体

### 1.1 架构概览

```
私有化部署 = W78 C-1 SaaS 4 层架构的 offline-first 单租户变体

镜像层     Dockerfile.commercial (W73 B-5) + offline-first 标识
SaaS 平台层 5 脚本单租户变体 (tenant_manager/usage_tracker/billing_gateway/audit_export/deploy)
计费服务层  billing_degrade.py — 离线时 mock 降级, BILLING_LIVE_ENABLED=false 硬门控 (类 20.13)
前端层     BillingView/PlanSelector 公网隐藏 (私有化部署不暴露公网自助购买)
```

### 1.2 私有化 vs SaaS 4 大差异

| 维度 | SaaS | 私有化 |
|------|------|--------|
| 网络 | 强制在线 | offline-first, 7 天宽限 |
| 租户 | multi-tenant | single-tenant (6 商业化表仍在) |
| 计费 | 必真支付 | 可降级 mock (网关不可达时) |
| 前端 | 公网自助购买 | 公网隐藏 |

### 1.3 验证命令

```bash
# 验证 4 层架构文件存在
ls commercial/private-deployment/
# 期望: __init__.py  billing_degrade.py  private_config.py

# 验证 BILLING_LIVE_ENABLED 硬门控 (类 20.13)
grep "BILLING_LIVE_ENABLED" commercial/private-deployment/billing_degrade.py
# 期望: BILLING_LIVE_ENABLED 默认 false

# 验证 OFFLINE_GRACE_DAYS 三处口径一致
grep -r "OFFLINE_GRACE_DAYS" commercial/private-deployment/ app/services/license_service.py 2>/dev/null
# 期望: 全部 = 7
```

---

## 段 2 License 校验 4 模式

### 2.1 4 模式状态机

```
在线校验 ──→ 成功 ──→ 正常运行
           └→ 失败 ──→ 进入离线宽限 (7 天)
                        ├→ 宽限内 ──→ 正常运行 (降级警告)
                        └→ 宽限到期 ──→ read-only 模式
                                         └→ License 续期 ──→ 恢复正常
```

### 2.2 关键常量 (三处口径必须一致 = 7)

| 文件 | 常量名 | 值 |
|------|--------|-----|
| `commercial/private-deployment/__init__.py` | `OFFLINE_GRACE_DAYS` | 7 |
| `commercial/private-deployment/private_config.py` | `OFFLINE_GRACE_DAYS` | 7 |
| `app/services/license_service.py` (W73 B-5) | `OFFLINE_GRACE_DAYS` | 7 |

### 2.3 read-only 模式触发条件

```python
# private_config.py
def should_degrade_read_only(license_status) -> bool:
    # 触发: 离线宽限到期 OR License 过期
    return license_status in ("expired", "grace_exceeded")
```

### 2.4 客户端 fallback

```python
# billing_degrade.py
# BILLING_LIVE_ENABLED=false (类 20.13 硬门控) → 直接 mock
# BILLING_LIVE_ENABLED=true 但网关超时 5s → 自动降级 + 告警
result = process_payment_with_fallback(amount, currency)
# DegradedPaymentResult(success=True, mode="mock", reason="gateway_timeout")
```

---

## 段 3 6 商业化表 + 跨租户隔离

### 3.1 6 商业化表 (W78 C-1 alembic 082 + W73 B-5 起步)

```sql
commercial_plans          -- 套餐定义 (starter/pro/enterprise)
commercial_tenants        -- 租户注册 + 状态
commercial_subscriptions  -- 订阅关系 (tenant → plan)
commercial_invoices       -- 发票 + 财务结算
commercial_usage_records  -- 用量计费记录
commercial_licenses       -- License 校验 + 离线宽限
```

### 3.2 私有化单租户模式

```bash
# 私有化部署: 6 商业化表仍在, 但只落 1 个 tenant_id
# 跨租户 422 拦截仍然有效 (W79 B-3 实战)
grep "tenant_id" commercial/private-deployment/private_config.py
# 期望: PRIVATE_TENANT_ID = "private-001" (单租户固定值)
```

### 3.3 跨租户 422 验证 (W79 B-3 实战)

```bash
# 验证跨租户 422 拦截 e2e 存在
grep -l "422\|TenantIsolationViolation" tests/
# 期望: tests/test_w79_b3_tenant_monitoring_e2e.py
```

---

## 段 4 客户支持流程

### 4.1 客户 Onboarding 流程

```
1. 客户申请私有化部署
   └→ 生成 License key (W73 B-5 license_service.py)
   └→ 提供 Dockerfile.commercial + docker-compose.private.yml

2. 部署验证 (客户侧)
   └→ bash scripts/private_deployment_monitor.sh
   └→ 期望: 全部 PASS

3. License 激活
   └→ 在线校验成功 → 正常运行
   └→ 离线环境 → 7 天宽限自动启动

4. 持续监控
   └→ crontab: 0 */2 * * * bash scripts/private_deployment_support.sh
```

### 4.2 SLA 监控

| 指标 | 目标 | 监控脚本 |
|------|------|---------|
| License 在线校验 | < 5s | `private_deployment_monitor.sh` case 1 |
| 离线宽限剩余天数 | ≥ 1 天告警 | `private_deployment_monitor.sh` case 2 |
| 计费降级状态 | BILLING_LIVE_ENABLED=false | `private_deployment_support.sh` case 3 |
| 跨租户隔离 | 422 拦截 100% | `test_w79_b3_tenant_monitoring_e2e.py` |

### 4.3 财务结算流程

```
commercial_invoices 表:
  - 月结: Celery beat 每月 1 日生成发票
  - 用量: commercial_usage_records 汇总
  - 退款: invoice.status = "refunded" + usage_record 冲销

私有化部署财务结算:
  - BILLING_LIVE_ENABLED=false → mock 模式 (不真实扣款)
  - 需要真实计费时: 主拍决策 + BILLING_LIVE_ENABLED=true (类 20.13)
```

### 4.4 工单处理

```bash
# 工单触发监控告警
WEBHOOK_URL="https://your-webhook" bash scripts/private_deployment_support.sh
# 异常时自动发送 webhook 告警

# 手动触发全套监控
bash scripts/private_deployment_monitor.sh  # W79 B-2: 4 case
bash scripts/private_deployment_support.sh  # W80 B-2: 4 case
```

---

## 段 5 8 件套监控完整性 (W78 C-1 → W80 B-2 累计)

| 件 | 脚本 | 来源 | 监控内容 |
|----|------|------|---------|
| 1 | `monitor-alembic-heads.sh` | W78 C-1 | alembic 单链 1 head |
| 2 | `monitor-nginx-mime.sh` | W78 C-1 | nginx MIME 类型 |
| 3 | `monitor-pwa-manifest.sh` | W78 C-1 | PWA manifest hash |
| 4 | `monitor-sw-cache.sh` | W78 C-1 | SW 缓存污染 |
| 5 | `monitor-tenant-isolation.sh` | W78 C-1 | 多租户隔离 |
| 6 | `monitor-9-table-index.sh` | W78 C-1 | 9 表索引 |
| 7 | `private_deployment_monitor.sh` | W79 B-2 | 私有化 4 case |
| 8 | `private_deployment_support.sh` | W80 B-2 | 客户支持 4 case |

```bash
# 验证 8 件套完整性
ls scripts/monitor-*.sh scripts/private_deployment*.sh 2>/dev/null | wc -l
# 期望: ≥ 6 (部分 monitor-*.sh 可能在 W78 C-1 部署时生成)
```

---

## 段 6 e2e 测试运行

```bash
# W80 B-2 新增 12 case
pytest tests/test_w80_b2_private_support_e2e.py -v
# 期望: 12/12 PASS

# 复用 W79 B-2 10 case
pytest tests/test_w79_commercial_private_deployment_e2e.py -v
# 期望: 10/10 PASS

# 复用 W79 B-3 6 case
pytest tests/test_w79_b3_tenant_monitoring_e2e.py -v
# 期望: 6/6 PASS

# 全套 28 case
pytest tests/test_w80_b2_private_support_e2e.py \
       tests/test_w79_commercial_private_deployment_e2e.py \
       tests/test_w79_b3_tenant_monitoring_e2e.py -v
# 期望: 28/28 PASS
```

---

## 段 7 类 20.13 真生产 key 单独拍板实战

> **铁律**: `BILLING_LIVE_ENABLED` 默认 `false` 硬门控不变。私有化部署环境启用真实支付必须主拍决策。

```bash
# 当前状态验证
grep "BILLING_LIVE_ENABLED" commercial/private-deployment/billing_degrade.py
# 期望: os.getenv("BILLING_LIVE_ENABLED", "false") — 默认 false

# 启用真实支付 (需要主拍决策)
# 1. 主指挥拍板确认
# 2. 设置环境变量: BILLING_LIVE_ENABLED=true
# 3. 配置真实支付网关凭据 (W75 C-1 Stripe/Alipay/WeChat)
# 4. 运行 e2e 验证: pytest tests/test_w80_b2_private_support_e2e.py::test_billing_live_enabled_default_false
```

---

## 段 8 锚点范式守恒

```
W79 第 1 批 283 → W80 第 1 批 B-2 288 守恒 (+1)

新增文件 (本 commit):
  scripts/private_deployment_support.sh    (+1 监控脚本)
  tests/test_w80_b2_private_support_e2e.py (+12 e2e case)
  docs/w80-1st-batch-b2-commercial-private-support-runbook-2026-07-28.md (本文件)

不动文件 (0 production code 改动铁律):
  app/services/billing/          ← 不动 (W75 C-1 真支付 SDK)
  app/services/license_service.py ← 不动 (W73 B-5)
  web/src/views/commercial/      ← 不动 (W78 C-1)
  alembic/versions/              ← 不动 (W73 B-5 alembic 082)
```

---

*W80 第 1 批 B-2 商业化私有化部署 + 客户支持 runbook — 2026-07-28*
