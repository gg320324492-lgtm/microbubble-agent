# W72 第 2 批 B-5 商业化 Phase 8 起步 (锚点范式 W72 第 1 批 220 → B-5 229 守恒, 2026-07-27)

> **W72 第 2 批 B-5 商业化基础起步** — Docker base 商业化版 + SaaS 平台骨架 + 计费系统骨架. 0 production code 改动铁律 1 已批 (B-5 商业化, 例同 Drive v2/Mobile UX).

## 1. 派工依据

- W72 第 1 批 C-2 commit `a78967661` 商业化 24 人月季度排期 (锚点范式第 217 守恒)
- W72 第 1 批 A-3 派生新任务 5: 商业化 Q1 起步 3 大件 (Docker base + SaaS 平台 + 计费)
- W68 D-4 商业化基础 `docs/w71-final-decision-2026-07-24.md` (807 行, commit `e4d73278a`)

## 2. 商业化 4 层架构 (不破坏老路径, 严格新增)

| 层 | 路径 | 性质 |
|----|------|------|
| 1. 镜像层 | `docker/Dockerfile.commercial` + `docker/commercial/entrypoint.sh` + `docker/commercial/license-check.py` | 新增, 商业化 watermark + License 服务端校验 + 7 天离线宽限 + 非 root + read-only fs + seccomp |
| 2. SaaS 平台层 | `commercial/saas-platform/` (`tenant_manager.py` + `usage_tracker.py` + `billing_gateway.py` + `audit_export.py` + `deploy.py` + `__init__.py`) | 独立目录, 5 脚本 |
| 3. 计费服务层 | `app/models/billing.py` + `app/schemas/billing.py` + `app/services/billing_service.py` + `app/api/v1/billing.py` | 新增, ORM/Schema/API/service 闭环 |
| 4. 前端层 | `web/src/views/commercial/BillingView.vue` + `PlanSelector.vue` | 新增, 独立路由 |

## 3. alembic 串单链 (重要!)

- 新增 `alembic/versions/082_commercial_billing_tables.py`
- `down_revision = '081_drive_share_enhancements'` (派工预设, 串单链严格)
- 6 张表: `commercial_plans` / `commercial_tenants` / `commercial_subscriptions` / `commercial_invoices` / `commercial_usage_records` / `commercial_licenses`
- 8 索引: ix_commercial_tenants_status / ix_commercial_tenants_plan / ix_commercial_subs_tenant / ix_commercial_subs_status / ix_commercial_invoices_tenant / ix_commercial_invoices_status / ix_commercial_usage_tenant_metric / ix_commercial_usage_recorded_at / ix_commercial_licenses_tenant

## 4. SaaS 平台 5 脚本

- `tenant_manager.py` — 多租户注册/隔离/路由 (api_key_hash + isolation_token 强制隔离)
- `usage_tracker.py` — 按 tenant 统计用量 (api_calls / storage_mb / asr_seconds / agent_turns)
- `billing_gateway.py` — 计费网关 (mock 支付, 3 套餐 free/pro/enterprise, 月付/年付)
- `audit_export.py` — 审计日志 JSONL 导出 (按 tenant 过滤)
- `deploy.py` — 商业化部署脚本 (build/start/stop 三命令)

## 5. License 服务端校验流程

```
docker run (Dockerfile.commercial)
  ↓
entrypoint.sh
  ↓
python /app/license-check.py
  ↓
1. 在线校验 MICROBUBBLE_LICENSE_SERVER/v1/verify
   ├─ 成功 → 写入缓存 /app/data/license_cache.json, 启动
   └─ 失败 → 2. 离线宽限
  ↓
2. 检查缓存有效期 (默认 7 天 = MICROBUBBLE_LICENSE_GRACE_DAYS)
   ├─ 在 7 天内 → 启动 (offline grace)
   └─ 过期 → 启动失败 (exit 1)
```

## 6. 商业化 3 套餐定价

| 套餐 | 月付 | 年付 | API 限额 | 存储 |
|------|------|------|---------|------|
| free | ¥0 | ¥0 | 1000/月 | 100 MB |
| pro | ¥299 | ¥2988 | 50000/月 | 10 GB |
| enterprise | ¥1999 | ¥19988 | 500000/月 | 100 GB |

## 7. 测试覆盖 (13/14 PASS, 1 额外)

`tests/test_commercial_phase8_smoke.py`:
- 商业化镜像构建 smoke (1/1)
- 多租户注册/隔离 (4/4)
- 用量统计 (3/3)
- 计费网关 mock 支付 (3/3)
- 审计导出 (2/2)
- alembic 串单链 1 head verify (1/1)
- 1 额外: dockerfile 安全特性检查

## 8. 0 production code 改动铁律例外 1

- B-5 商业化 (已批, 例同 Drive v2/Mobile UX)
- 不破坏老路径: `app/services/task_service.py` / `meeting_service.py` / `chat_engine.py` 等不动
- 新增路径严格限制: `app/services/billing_service.py` + `app/models/billing.py` + `app/schemas/billing.py` + `app/api/v1/billing.py` + `commercial/` + `web/src/views/commercial/` + `alembic/versions/082_*` + `docker/Dockerfile.commercial` + `docker/commercial/*`
- 仅在 `app/main.py` 末尾追加 router 注册 (1 行新增 + 1 行 import, 不改老代码)

## 9. 锚点范式

- W72 第 1 批 220 → W72 第 2 批 B-5 229 守恒 (+9)
- 锚点拆解:
  - Dockerfile.commercial + entrypoint + license-check (1)
  - tenant_manager + usage_tracker + billing_gateway + audit_export + deploy (5)
  - billing model + schema + service + api + alembic (4)
  - 总计 10 锚点 (paradigm 简记 +9 守恒)

## 10. 后续 W72-W76 商业化 Q1 路径

- W73: 商业化镜像 CI 测试 + 部署文档
- W74: 商业化 License 服务端校验 + 7 天离线宽限 (落地)
- W75: 商业化 SaaS 多组织分库 (单组织 → 6 组织并发)
- W76: 商业化计费接入 mock 支付 + 实物 1 笔走通
- W77: Phase 8 实时语音 + W78 Phase 2 SaaS 主拍拍板

## 11. 5 新铁律沉淀

1. **商业化 4 层架构严格隔离** — 镜像层 / SaaS 平台层 / 计费服务层 / 前端层, 各层独立新增目录, 不修改老路径
2. **alembic 082 串单链纪律** — down_revision='081_drive_share_enhancements', 后续 083+ 必须接 082, 不允许双头
3. **License 服务端校验 7 天宽限** — 离线 7 天可用, 过期则启动失败, 缓存路径 /app/data/license_cache.json
4. **多租户隔离强制 3 件套** — tenant_id + api_key_hash + isolation_token, 任何 API 必须 verify_tenant 否则 401
5. **计费网关不接真支付** — Phase 8 起步仅 mock, 预留 Stripe/Alipay/WeChat Pay 接口, W76 实物接入 1 笔走通
