# W72 Phase 8 商业化起步 (锚点范式第 220 守恒, 2026-07-27)

> **W72 第 2 批 B-5 商业化基础起步** — Docker base 商业化版 + SaaS 平台骨架 + 计费系统骨架. 0 production code 改动铁律 1 已批 (B-5 商业化, 例同 Drive v2/Mobile UX).

## 1. 派工依据

- W72 第 1 批 C-2 commit `a78967661` 商业化 24 人月季度排期 (锚点范式第 217 守恒)
- W72 第 1 批 A-3 派生新任务 5: 商业化 Q1 起步 3 大件 (Docker base + SaaS 平台 + 计费)
- W68 D-4 商业化基础 `docs/w71-final-decision-2026-07-24.md` (807 行, commit `e4d73278a`)

## 2. 商业化 4 层架构 (不破坏老路径)

| 层 | 路径 | 性质 |
|----|------|------|
| 1. 镜像层 | `docker/Dockerfile.commercial` | 新增, 商业化 watermark + License 服务端校验 + 非 root + read-only fs + seccomp |
| 2. SaaS 平台层 | `commercial/saas-platform/` | 独立目录, 4 脚本 (tenant-manager / usage-tracker / billing-gateway / audit-export) |
| 3. 计费服务层 | `app/services/billing_service.py` + `app/models/billing.py` + `app/schemas/billing.py` + `app/api/v1/billing.py` | 新增, ORM/Schema/API/service 闭环 |
| 4. 前端层 | `web/src/views/commercial/BillingView.vue` + `PlanSelector.vue` | 新增, 独立路由 |

## 3. alembic 串单链

- 新增 `alembic/versions/082_commercial_billing_tables.py`
- `down_revision = '081_drive_share_enhancements'` (派工预设)
- 6 张表: `subscriptions` / `invoices` / `usage_records` / `plans` / `licenses` / `tenants`

## 4. 测试覆盖

`tests/test_commercial_phase8_smoke.py` — 13 case:
- 商业化镜像构建 smoke (5min)
- 多租户注册/隔离 4 case
- 用量统计 3 case
- 计费网关 mock 支付 3 case
- 审计导出 2 case
- alembic 串单链 1 head verify

## 5. 0 production code 例外 1

- B-5 商业化 (已批, 例同 Drive v2/Mobile UX)
- 不破坏老路径: `app/services/task_service.py` / `meeting_service.py` / `chat_engine.py` 等不动
- 新增路径严格限制: `app/services/billing_*` + `commercial/` + `web/src/views/commercial/` + `alembic/versions/082_*`

## 6. 后续 W72-W76 商业化 Q1 路径

- W73: 商业化镜像 CI 测试 + 部署文档
- W74: 商业化 License 服务端校验 + 7 天离线宽限
- W75: 商业化 SaaS 多组织分库 (单组织 → 6 组织并发)
- W76: 商业化计费接入 mock 支付 + 实物 1 笔走通
- W77: Phase 8 实时语音 + W78 Phase 2 SaaS 主拍拍板

## 7. 锚点范式

- W72 第 1 批 220 → W72 第 2 批 B-5 ~229 守恒 (+9)
- 锚点拆解: 商业化 Dockerfile (1) + SaaS 平台 4 脚本 (4) + 计费 service/model/schema/api/alembic (4) = 9
