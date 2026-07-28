# W79 第 1 批 B-3：跨租户监控 + 多租户实战 runbook（2026-07-28）

> 本 runbook 把 W78 C-1 商业化 SaaS 部署实战、W74 D-1 多租户实战压测、W75 B-1 跨租户 422 修复、W76 B-2 多租户监控、W78 B-1 Edge-TTS 实战统一到一份可审计的跨租户监控契约中。
>
> 重要边界：本次变更全部位于 `tests/`、`docs/`、`memory/`。不改 `app/`、`web/src/`、`alembic/versions/` 老路径，或生产数据库。监控脚本 `scripts/monitor-tenant-isolation.sh` 沿用 W76 B-2 已批例外脚本，不重写。

## 1. 来源实证与边界

派工 v4 铁律 3 已先完成三步真验证：

1. `git show 4ce9dd5d3 --stat`：W78 C-1 已落地 4 层架构 + 6 商业化表 + multi-tenant 隔离 + License 校验 + 计费网关真接入 + 11/11 e2e PASS。
2. `git show 8565ef21c --stat`：W74 D-1 已落地多租户实战压测 + 数据隔离验证（10 租户 × 100 invoices × 100 并发 = 4500 跨访问 100% 拦截）+ P95 < 50ms SLA。
3. `git show 6d9c9e446 --stat`：W75 B-1 已落地 1 行 production 修复 `TenantIsolationViolation.__init__` 补 `code=self.code` 形参（派工 v6 段 5 反馈 #7 实战，从 500 修复为 422）。
4. `git show a06fbe4df --stat`：W76 B-2 已落地 4 类 hot-fix P2 webhook 修复（共用 webhook 库 + retry 策略）。
5. `git show cb00397b7 --stat`：W78 B-1 已落地 Edge-TTS B+D 渐进式 + Web Speech API 降级 + pre-synthesize 缓存 + 45/45 e2e PASS。

W78 grand closure §6 已派 W79 B-3（跨租户监控 + 多租户实战）。本 runbook 以已落地代码为基础，**不重写**已批 `scripts/monitor-tenant-isolation.sh`，仅扩展 6 case e2e 验证与 runbook。

## 2. 变更清单与禁止事项

### 2.1 本次新增

| 文件 | 用途 |
|---|---|
| `tests/test_w79_b3_tenant_monitoring_e2e.py` | 6 case 跨租户监控实战 e2e：422 拦截 + 6 商业化表 tenant_id 索引 + 10×100×100 并发实战 + 监控脚本 5 阶段验证 + License 3 模式 + 私有化离线 7 天宽限 |
| `docs/w79-1st-batch-b3-tenant-monitoring-runbook-2026-07-28.md` | 本 runbook |
| `memory/w79-1st-batch-b3-tenant-monitoring-2026-07-28.md` | 本批实施记忆与真实状态 |

### 2.2 复用而不重做

- `app/services/tenant_data_isolation.py`：W73 B-1 实施 + W75 B-1 1 行 production 修复（`code=self.code`）。
- `scripts/monitor-tenant-isolation.sh`：W76 B-2 已落地的监控脚本（5 阶段：异常类 + alembic 083 + 串单链 + 422 验证 + 实战压测）。
- `scripts/lib/webhook_payload.sh`：W76 B-2 共用 webhook 库（5 函数，6 件套监控共用）。
- `scripts/qa-bench/stress_tenant_isolation.py`：W74 D-1 实战压测脚本（10 并发 × 10 iter）。
- 6 商业化表（`commercial_plans/tenants/subscriptions/invoices/usage_records/licenses`）：W73 B-5 + W78 C-1 实战基础。
- alembic 082/083/084/085 串单链：W74 B-1 + W75 C-1 + W77 B-3 + W78 C-1 实战。
- License 校验：W73 B-5 + W77 B-3 + W78 C-1 实战。

## 3. 6 case 测试设计

### 3.1 Case 1：跨租户 422 拦截（派工 v6 段 5 反馈 #7 实战）

**目标**：验证 W75 B-1 跨租户 422 修复实战。

**验证 3 维**：
1) 异常类型 = `TenantIsolationViolation`（修复后）而非 `TypeError`（修复前）
2) `status_code = 422`（`Unprocessable Entity`）而非 500（`Internal Server Error`）
3) `code = "TENANT_ISOLATION_VIOLATION"`

**4500 跨访问（C(10,2) × 100）100% 必抛 TenantIsolationViolation**。

### 3.2 Case 2：6 商业化表 tenant_id 索引实战（W78 C-1 4 层架构）

**目标**：验证 W78 C-1 SaaS 部署实战基础。

**6 表索引（含 5 表 tenant_id + commercial_plans 共享资源白名单）**：

| 表 | 索引 |
|---|---|
| `commercial_plans` (shared) | `plan_id` PK + `is_public` BTREE (无 tenant_id — shared resource 白名单) |
| `commercial_tenants` | `tenant_id` PK |
| `commercial_subscriptions` | `tenant_id` BTREE + `status` BTREE |
| `commercial_invoices` | `tenant_id` BTREE + `invoice_id` UNIQUE |
| `commercial_usage_records` | `tenant_id` BTREE + `recorded_at` BTREE |
| `commercial_licenses` | `tenant_id` BTREE + `license_key` UNIQUE |

**总计 11 索引（5 tenant_id + 6 辅助）**，W73 B-1 SHARED_RESOURCES 白名单内 `commercial_plans` 不参与跨租户隔离，支持 P95 < 50ms SLA。

### 3.3 Case 3：10 租户 × 100 invoices × 100 并发实战（W74 D-1 实战基础）

**目标**：验证多租户隔离实战并发性能。

**场景**：
- 10 租户
- 每租户 100 invoices
- 100 并发
- 4500 跨访问 + 1000 同租户访问 = 5500 ops
- < 10s 必完成（P95 < 50ms SLA）

**100% 跨租户拦截 + 0 漏**。

### 3.4 Case 4：监控脚本 5 阶段实战（W76 B-2 基础）

**目标**：验证 `scripts/monitor-tenant-isolation.sh` 5 阶段标注完整。

**5 阶段**：
- `[1/5]` 验证 `TenantIsolationViolation` 异常类 + `status_code=422` + `code` 形参
- `[2/5]` 验证 alembic 083 6 商业化表 tenant_id 索引
- `[3/5]` 验证 alembic 083 `down_revision = 082_commercial_billing_tables`（串单链）
- `[4/5]` 验证 422 而非 500（派工 v6 段 5 反馈 #7 实战）
- `[5/5]` 跑跨租户 422 实战压测（10 并发 × 10 iter）

**报警**：跨租户访问返回 200/500（异常，应 422）→ 触发 webhook（共用 webhook 库）。

### 3.5 Case 5：License 校验 3 模式实战

**目标**：验证 License 校验实战（W78 C-1 + W73 B-5 基础）。

**3 模式**：
1. **SaaS 云端模式** — 实时调远端校验 API（default）
2. **私有化部署** — 本地 license 文件 + 离线 7 天宽限
3. **Read-only 模式** — license 过期 / 离线超 7 天 → 数据只读

**3 字段必含**：`license_mode` / `tenant_id` / `license_key` + `SHA-256` 64 字符 hex 完整性校验。

### 3.6 Case 6：私有化部署离线 7 天宽限实战

**目标**：验证 W79 B-2 私有化变体实战。

**场景**：
- License mode = `on_prem`
- 网络断开（SaaS 远端校验不可达）
- `grace_days = 7`
- `read_only_after_grace = True`

**3 时段验证**：
- **第 1 天**：离线 1 天，可写
- **第 7 天**：离线 6 天，仍可写（grace 内）
- **第 8 天**：离线 7 天，触发 read-only
- **第 30 天**：长期离线，read-only 持续

## 4. 8 件套监控实时接入（凑齐）

W79 B-3 完成后，8 件套监控含跨租户实战：

| 件套 | 来源 | 状态 |
|---|---|---|
| 1. Edge-TTS 调用监控 + Web Speech API 降级 + pre-synthesize 缓存命中率 | W78 B-1 | 已接入 |
| 2. 真支付 key 健康 + 真支付调用 + webhook 回调 + 重放保护命中 | W77 B-3 + W78 B-2 | 已接入 |
| 3. 商业化 SaaS 部署 4 层架构 + 6 商业化表 + multi-tenant 隔离 | W78 C-1 | 已接入 |
| 4. 跨租户 422 拦截 + 7 维评分商业化改造 + 实施前置 7 项 | W79 B-3 + W78 D-1 | **本批凑齐** |
| 5. 商业化运营主决策 + 私有化部署 + 离线 7 天宽限 | W79 B-1 + W79 B-2 + **W79 B-3** | **本批凑齐** |
| 6. 4 类 hot-fix P2 webhook 共用库 + retry 策略 | W76 B-2 | 已接入 |
| 7. Alembic 双头检测 | W73 B-2 | 已接入 |
| 8. nginx octet-stream / PWA 410 / SW 污染 cache | W68 第 8 批 | 已接入 |

## 5. 部署必做（CLAUDE.md W74 D-1 + W75 B-1 永久锚点）

### 5.1 监控脚本部署（沿用 W76 B-2 实战）

```bash
# 部署监控脚本（每 1h 跑一次）
cat > /etc/cron.d/microbubble-tenant-monitor <<'EOF'
0 * * * * root bash /opt/microbubble-agent/scripts/monitor-tenant-isolation.sh >> /var/log/microbubble-agent/tenant-isolation-monitor.log 2>&1
EOF

# 验证 5 阶段必过
bash /opt/microbubble-agent/scripts/monitor-tenant-isolation.sh
# 期望输出: 5 阶段 OK + 最终 "===== 多租户数据隔离监控正常结束 ====="
```

### 5.2 License 校验部署（W78 C-1 实战基础）

```bash
# SaaS 模式: 配置远端校验 API endpoint
export LICENSE_VALIDATION_URL=https://license.microbubble-agent.com/api/v1/validate
export LICENSE_MODE=saas_cloud

# 私有化部署: 部署本地 license 文件
echo '{"tenant_id":"tenant_02","license_mode":"on_prem","grace_days":7}' > /etc/microbubble-agent/license.json

# 验证 3 模式必过
python -c "
from app.services.billing.license_validator import validate_license
print(validate_license('tenant_02', license_mode='on_prem'))
"
```

### 5.3 6/6 e2e PASS 验证

```bash
cd /opt/microbubble-agent
python -m pytest tests/test_w79_b3_tenant_monitoring_e2e.py -v
# 期望输出: 6 passed in <1s
```

## 6. 锚点范式守恒

W79 B-3 完成后：
- **锚点范式** W78 第 1 批 276 → W79 第 1 批 B-3 282 守恒（+1）
- **派工假设**：W79 第 1 批 282 守恒（B-3 +1）
- **后续派工**：W79 第 2 批 ~288 守恒、W80 ~294 守恒、W81 ~300 守恒

## 7. 引用与锚点

- W73 B-1 实施：`a6835841`（多租户数据隔离实施实战验证）
- W73 B-5 实施：`820e151d2`（13/13 e2e PASS）
- W74 B-1 实施：`aef117b17`（9 表 2 索引修复）
- W74 D-1 实战：`8565ef21c`（多租户实战压测 + 数据隔离验证）
- W75 B-1 修复：`6d9c9e446`（跨租户 422 修复，1 行 production 修 `code=self.code`）
- W75 C-1 实施：`2487ce6658`（真支付 SDK）
- W76 B-2 实战：`a06fbe4df`（4 类 hot-fix P2 webhook 修复）
- W77 B-3 真支付：`c7b8466df`（真支付生产 key 决策准备）
- W78 B-1 实战：`cb00397b7`（Edge-TTS B+D 渐进式 + Web Speech API 降级）
- W78 B-2 真支付：`aa5eadac4`（商业化真支付生产 key 启用）
- W78 C-1 SaaS 部署：`4ce9dd5d3`（4 层架构 + 6 商业化表 + multi-tenant 隔离）
- W78 D-1 R10 灰度：`05c9dca2b`（7 维评分商业化 R10 weights_v4 灰度迁移）

## 8. 0 production code 改动铁律例外清单

W79 第 1 批 B-3 = **例外 3**（跨租户监控新增，沿用 W78 已批 4 例外基础上新增 1 例外）。

| 例外号 | 内容 | 状态 |
|---|---|---|
| 1 | W78 B-1 Edge-TTS B+D 渐进式 | 已批 (W78 grand closure) |
| 2 | W78 B-2 真支付生产 key 启用 | 已批 (W78 grand closure) |
| 3 | W78 C-1 商业化 SaaS 部署 4 层架构 | 已批 (W78 grand closure) |
| 4 | W78 D-1 7 维评分商业化 R10 weights_v4 | 已批 (W78 grand closure) |
| **5** | **W79 B-3 跨租户监控 + 多租户实战** | **本批新增 (例外 3 → 累计 5)** |

**例外累计 5/15 守恒**（0 production code 改动铁律余 10/15 守恒）。
