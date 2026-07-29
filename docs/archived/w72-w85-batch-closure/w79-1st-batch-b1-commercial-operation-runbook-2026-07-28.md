# docs/w79-1st-batch-b1-commercial-operation-runbook-2026-07-28.md
# W79 第 1 批 B-1 商业化运营主决策落地 runbook (锚点范式 W78 第 1 批 276 → W79 第 1 批 B-1 280 守恒 +1)
#
# 依据: W78 A-2 commit 35ac5ced5 §5.4 阶段 5 商业化运营主决策落地 + W78 C-1 commit 4ce9dd5d3 SaaS 部署 + W78 B-1 commit cb00397b7 Edge-TTS + W78 B-2 commit 41c879726 真支付生产 key + W78 D-1 commit 05c9dca2b R10 灰度 + 派工 v6 段 5 反馈 #6 实战 (商业化主拍单独拍板)
#
# 0 production code 改动铁律例外 1 已批 (商业化运营 monitoring/alerts 实施, 仅新增 scripts/commercial_operation_monitor.py)

## 0. 调研边界 (必先明示)

- ✅ **调研/实施范围**: 5 阶段运营落地实战 + 8 件套监控实时接入 + Phase 8 收官时间表 + 商业化运营 monitoring/alerts 实战 + 12 e2e PASS
- ❌ **不实施**: 不动 `app/services/billing_service.py` + `app/api/v1/billing.py` + `app/voice/tts.py` (110 行 Edge-TTS) + `app/services/audio_processor.py` (195 行 VAD) + `app/agent/qa_bench.py` + `alembic/versions/085_*.py` + `web/src/views/billing/*` + `web/src/composables/chat/useChatStream.ts` 老路径
- 🚫 **不拍主拍决策**: Edge-TTS B+D 渐进式主拍启用 / 接真生产 key / D-1 R10 weights_v4 灰度 / 商业化 SaaS 平台部署 / 7 维评分商业化改造 — 5 阶段已分别拍板 (W78 B-1 + W78 B-2 + W78 C-1 + W78 D-1), 本任务只落地商业化运营 monitoring/alerts 主决策 (派工 v6 段 5 反馈 #6 实战)
- 📚 **派生输出**: `docs/w79-1st-batch-b1-commercial-operation-runbook-2026-07-28.md` (本文) + `memory/w79-1st-batch-b1-commercial-operation-2026-07-28.md` (本任务沉淀) + `scripts/commercial_operation_monitor.py` (新增) + `tests/test_w79_commercial_operation_e2e.py` (新增)

## 1. 派工 v4 铁律 3 真验证 (派工前提必先 3 步实战)

### 1.1 Step 1: W78 A-2 §5.4 阶段 5 商业化运营主决策落地

**W78 A-2 commit `35ac5ced5` §5.4 阶段 5** (派工 v6 段 5 反馈 #6 实战 + 类 20.13 真生产 key 单独拍板):

| 阶段 | 任务 | 主拍决策 | 起点 → 终点 | 守恒 |
|------|------|----------|-------------|------|
| 阶段 1 | 运营监控 (8 件套监控实时 + Edge-TTS 实战) | W78 C-1 + W78 B-1 | 274 → 276 | +2 |
| 阶段 2 | 客户支持 (SaaS 部署 + 4 层架构实战) | W78 C-1 | 276 → 277 | +1 |
| 阶段 3 | 财务结算 (真支付生产 key 启用 + 3 支付渠道) | W78 B-2 | 275 → 276 | +1 |
| 阶段 4 | 商业化迭代 (R10 weights_v4 灰度 + 7 维评分商业化改造) | W78 D-1 | 276 → 277 | +1 |
| 阶段 5 | 24 人月 Q1 收官 (W79 商业化运营主决策落地 + W80/W81 后续) | W79 B-1 (本文) | 276 → 280 | +1 |

**W79 B-1 (本文) 实施边界**: 仅阶段 5 — 商业化运营主决策落地 = 5 阶段运营落地实战 + 8 件套监控实时接入 + Phase 8 收官时间表 + monitoring/alerts 实施

### 1.2 Step 2: W78 C-1 商业化 SaaS 部署 + W78 B-1 Edge-TTS 实战

**W78 C-1 commit `4ce9dd5d3` 11/11 e2e PASS**:
- 4 层架构实战 (镜像 + SaaS 平台 + 计费服务 + 前端, W73 B-5 基础)
- 6 商业化表实战 (commercial_plans/tenants/subscriptions/invoices/usage_records/licenses)
- multi-tenant 隔离实战 (W73 B-5 + W74 D-1 + W75 B-2 422 修复 + W76 B-2 实战)
- 0 production code 例外 4 已批 (商业化 SaaS 平台部署)

**W78 B-1 commit `cb00397b7` 45/45 e2e PASS**:
- tts_mainplay_pipeline.py B+D 组合渐进式 (5 阶段: Edge-TTS 渐进式 + Web Speech API 降级 + pre-synthesize 缓存)
- Web Speech API 浏览器原生兜底
- pre-synthesize cache hit rate ≥ 60%

### 1.3 Step 3: W78 B-2 真支付生产 key + W78 D-1 R10 灰度实战

**W78 B-2 commit `41c879726` 5/5 e2e PASS** (B-3 W77 主拍决策落地, 类 20.13 实战):
- `.env.production.example` 3 支付渠道真生产 key 占位符
- `billing_gateway.py` 优雅降级实战 (沙箱模式 + 真生产 key 自动切换 stripe_real/alipay_real/wechat_pay_real)
- 重放保护实战 (timestamp 5min + nonce + Webhook 签名验证, W75 C-1 16/16 + W76 E-1 PASS verify)

**W78 D-1 commit `05c9dca2b` 22/22 e2e PASS** (R10 weights_v4 灰度迁移实战):
- 12 子维度 + 6 检测器 + 200→240 题 + 7 项前置 + 4 周 5/10/25/100% 灰度

## 2. 5 阶段运营落地实战

### 2.1 阶段 1: 运营监控 (W78 C-1 8 件套监控 + W78 B-1 Edge-TTS 实战)

**8 件套监控实时接入**:
- monitor-alembic-heads.sh (W73 B-2) — alembic 双头检测
- monitor-pwa-manifest.sh (W73 B-2) — PWA manifest 410 检测
- monitor-nginx-mime.sh (W73 B-2) — nginx octet-stream 整站白屏检测
- monitor-sw-cache.sh (W73 B-2) — SW 缓存污染检测 (8 char hex + 双 head)
- monitor-tenant-isolation.sh (W74 D-1) — 多租户隔离 422 检测
- monitor-billing-webhook.sh (W75 B-3) — 计费 webhook 重放保护检测
- monitor-billing-real-key.sh (W77 B-3 + W78 B-2) — 真生产 key 自动切换
- monitor-9-table-index.sh (W78 D-1) — 9 表索引 + R10 灰度索引

**集成入口**: `scripts/commercial_operation_monitor.py run --dry-run` 一次性跑 8 件套监控 (兼容 worktree 与生产部署, 60s timeout)

**报警阈值 + 通知渠道分级**:
| severity | notify_channels | ack_minutes | 说明 |
|----------|-----------------|-------------|------|
| critical | webhook + on_call_pager + email | 5 | 服务不可用 / 真支付链路异常 |
| error | webhook + email | 30 | 功能降级但不影响主链路 |
| warn | email | 240 | 预警但无业务影响 |
| info | log | 1440 | 日常状态报告 |

### 2.2 阶段 2: 客户支持 (W78 C-1 SaaS 部署 + 4 层架构实战)

**4 层架构监控** (`commercial_operation_monitor.py saas`):
- 镜像层: `docker/Dockerfile.commercial` + `docker/commercial/license-check.py` 4 模式 (online/offline_grace/expired/revoked)
- SaaS 平台层: `commercial/saas-platform/deploy.sh` + set -euo pipefail + bash 语法 OK
- 计费服务层: `app/services/billing_gateway.py` + `.env.production.example`
- 前端层: `web/src/views/billing/BillingView.vue` + `web/src/components/billing/PlanSelector.vue`

**SLA 监控**: 商业化 SaaS 服务可用性 ≥ 99.5% (4 层架构任一异常 → critical 报警)

**工单系统集成**: 复用 W75 B-3 webhook 库 + 派工 v6 段 5 反馈 #6 实战 — 失败主动 exit 1 不静默

### 2.3 阶段 3: 财务结算 (W78 B-2 真支付生产 key + 3 支付渠道)

**月度账单生成**: `app/services/billing_service.py` (W73 B-5 + W74 B-1 + W75 C-1 基础, 不动)
- 6 商业化表: commercial_plans/tenants/subscriptions/invoices/usage_records/licenses

**交易费** (W78 A-2 成本模型):
- Stripe 0.5% (sk_live_* 真生产)
- Alipay 0.6% (RSA2 真应用)
- WeChat Pay 0.6% (V3 真商户号)
- Edge-TTS 7.2.8 免费 + Web Speech API 浏览器原生 → 接近 0 成本

**重放保护实战** (派工 v6 段 5 反馈 #6 实战):
- timestamp 5min TTL + nonce + Webhook 签名验证 (W75 C-1 16/16 PASS + W76 E-1 PASS verify)
- 监控: `monitor-billing-webhook.sh` + `monitor-billing-real-key.sh` 双保险

### 2.4 阶段 4: 商业化迭代 (W78 D-1 R10 weights_v4 灰度)

**12 子维度 + 6 检测器**:
- 锚定 W73 C-1 commit `6e65b32d5` 7 维评分商业化改造
- W74 C-1 commit `8033618d` 240 题灰度 20/20 e2e PASS
- W76 D-1 commit `cbdab60e6` SenseVoice 3 维度 17/17 e2e PASS

**4 周 5/10/25/100% 灰度时间表**:
- 第 1 周 5% (W78 D-1 实战)
- 第 2 周 10% (W79 D-1 重派)
- 第 3 周 25% (W80 D-1 重派)
- 第 4 周 100% (W81 收官)

### 2.5 阶段 5: 24 人月 Q1 收官 (W79 商业化运营 + W80/W81/W82+)

**24 人月 Q1 落地里程碑** (W78 A-2 §5.4):
- W78 (3 个月) — 5 阶段起步已收口 (A-2 + B-1 + B-2 + C-1 + D-1)
- W79 (3 个月) — 商业化运营主决策落地 (本文) + 私有化部署调研
- W80 (3 个月) — 7 维评分商业化改造 + D-1 R10 weights_v4 灰度实施
- W81+ (15 个月) — Phase 9 课题组知识图谱可视化 + Phase 11 智能实验记录本 + Phase 12 科研协作工作流

## 3. 8 件套监控实时接入 (W73 B-2 + W74 D-1 + W75 B-3 + W77 B-3 + W78 C-1 + W78 B-1 + W78 D-1)

### 3.1 监控集成入口

```bash
# 列出 8 件套监控清单
python scripts/commercial_operation_monitor.py list

# 列出 4 级 severity 报警阈值 + 通知渠道 + ack SLA
python scripts/commercial_operation_monitor.py thresholds

# 列出 5 类 on-call runbook
python scripts/commercial_operation_monitor.py oncall

# 验证 SaaS 4 层架构关键文件存在
python scripts/commercial_operation_monitor.py saas

# 烟雾测试 alert payload 字段完整
python scripts/commercial_operation_monitor.py alert-smoke

# 实际跑 8 件套监控 (worktree / 生产环境)
python scripts/commercial_operation_monitor.py run            # 真实执行
python scripts/commercial_operation_monitor.py run --dry-run  # 仅检测脚本是否存在
```

### 3.2 监控时间表 (cron 推荐)

| 监控 | 推荐 cron | 实战来源 |
|------|----------|----------|
| monitor-alembic-heads.sh | `0 * * * *` (每小时) | W73 B-2 |
| monitor-pwa-manifest.sh | `0 * * * *` (每小时) | W73 B-2 |
| monitor-nginx-mime.sh | `0 * * * *` (每小时) | W73 B-2 |
| monitor-sw-cache.sh | `0 * * * *` (每小时) | W73 B-2 |
| monitor-tenant-isolation.sh | `*/30 * * * *` (30 分钟) | W74 D-1 |
| monitor-billing-webhook.sh | `*/15 * * * *` (15 分钟) | W75 B-3 |
| monitor-billing-real-key.sh | `*/30 * * * *` (30 分钟) | W77 B-3 + W78 B-2 |
| monitor-9-table-index.sh | `0 * * * *` (每小时) | W78 D-1 |

### 3.3 on-call 实战 (5 类故障 → 主拍立即拍板)

| 故障类型 | first_action | remediation | severity |
|----------|--------------|-------------|----------|
| alembic 双头 | verify alembic chain (python -c import ScriptDirectory) | merge 顺序按 down_revision + clear __pycache__ | critical |
| PWA manifest 410 | curl /manifest.{hash}.webmanifest 看 200 | npm run build 唯一合法 (vite build 直跑必坏, 59187ce8 教训) | error |
| nginx octet-stream | curl / 看 text/html (非 octet-stream) | rollback types {} block (W68 第 5 批 f148d96 教训) | critical |
| 计费 webhook 重放 | verify timestamp 5min TTL + nonce + 签名 | rotate webhook secret + W75 C-1 16/16 e2e PASS | critical |
| Edge-TTS 主拍降级 | curl Edge-TTS endpoint + Web Speech API 兜底 | B+D 渐进式 + pre-synthesize cache (W78 B-1) | warn |

## 4. Phase 8 收官实战 (W79 + W80 + W81 + W82+)

| 批次 | 月份 | 任务 | 起点 → 终点 |
|------|------|------|-------------|
| **W79** | 当前 (2026-07-28) | 商业化运营主决策落地 (本文) + 私有化部署调研 + D-1 重派 | 276 → 280 |
| **W80** | 2026-10 | 7 维评分商业化改造 + 商业化运营深化 + D-1 R10 25% 灰度 | 280 → ~290 |
| **W81** | 2027-01 | Phase 8 收官 + 24 人月 Q1 落地收官 + D-1 R10 100% 灰度 | ~290 → ~300 |
| **W82+** | 2027-04 起 | Phase 9 课题组知识图谱可视化 + Phase 11 智能实验记录本 + Phase 12 科研协作工作流 | 持续 |

## 5. 商业化运营 monitoring/alerts 实战

### 5.1 新增脚本

- `scripts/commercial_operation_monitor.py` 新建 — 5 子命令: run / list / thresholds / oncall / saas + alert-smoke
- 集成 W78 C-1 SaaS 部署 + W78 B-1 Edge-TTS + W78 B-2 真支付生产 key + W78 D-1 R10 灰度实战
- 共用 W75 B-3 webhook 库 (5 字段 payload 规范)

### 5.2 新增 e2e (12 case)

- `tests/test_w79_commercial_operation_e2e.py` 新建 — 12/12 PASS
- 必含: 5 阶段运营 + 8 件套监控实时 + Phase 8 收官 + 24 人月 Q1 落地

## 6. 0 production code 改动铁律

**W79 第 1 批 B-1 例外 1 已批**:
- 商业化运营 monitoring/alerts 实施 (`scripts/commercial_operation_monitor.py` 新增)
- 沿用 W78 已批 4 例外基础上新增 1 例外 (C-1 SaaS 部署 + B-1 Edge-TTS + B-2 真支付 + D-1 R10 灰度 = 4 例外已批 + B-1 商业化运营 = 5 例外累计)
- 不动老 `app/` + `web/src/` + `alembic/versions/` 老路径
- 不动老 TTS/billing/QA 链路 (派工 v6 段 5 反馈 #6 渐进式实战)

## 7. 派工前提铁律 12 + 类 20 (含本次新增)

### 7.1 类 20.14 商业化运营主决策落地实战 (本次新增)

**根因**: 商业化 SaaS 平台部署 + Edge-TTS + 真支付 + R10 灰度实战需要商业化运营 monitoring/alerts 闭环, 否则主拍决策落地后无监控兜底

**实战**: W79 B-1 商业化运营主决策落地 = 5 阶段运营 + 8 件套监控 + Phase 8 收官时间表 + monitoring/alerts + 12 e2e

**纪律**:
1. **商业化运营 monitoring/alerts 是主拍决策落地的前提** — 不实施 monitoring/alerts, 主拍决策无法持久化运营
2. **8 件套监控实时接入必含全部 8 项** — 不能只接入部分, 派工 v4 铁律 3 真验证
3. **Phase 8 收官时间表必含 W79 + W80 + W81 + W82+ 4 阶段** — 不能仅含当前批次

### 7.2 复用既有铁律

- 类 20.13 真生产 key 单独拍板 (W78 B-2 实战)
- 类 20.12 调研完成 ≠ 主拍验收 (W78 A-2 实战)
- 类 20.11.1 6 收尾 branches 未 commit 派 A-1 拦截 (W77 实战)
- 派工前提铁律 12 条 (派工 v4 实战)
- 派工 v6 段 5 反馈 #6 渐进式实战
- W73 B-2 4 类监控 + W74 D-1 + W75 B-3 + W77 B-3 + W78 C-1 + W78 B-1 + W78 D-1 8 件套监控

## 8. 部署必做 (主拍决策落地后)

```bash
# 1. 部署 commercial_operation_monitor.py (无需重启后端)
scp scripts/commercial_operation_monitor.py root@server:/opt/microbubble-agent/scripts/

# 2. 配置 cron (复用既有 8 件套监控 cron)
# 编辑 crontab -e 加:
#   0 * * * * python /opt/microbubble-agent/scripts/commercial_operation_monitor.py run 2>&1 | tee -a /var/log/microbubble-agent/commercial-operation.log
#   */30 * * * * python /opt/microbubble-agent/scripts/commercial_operation_monitor.py saas 2>&1 | tee -a /var/log/microbubble-agent/saas-layer.log

# 3. 验证
python scripts/commercial_operation_monitor.py list
python scripts/commercial_operation_monitor.py thresholds
python scripts/commercial_operation_monitor.py oncall
python scripts/commercial_operation_monitor.py saas
python scripts/commercial_operation_monitor.py alert-smoke

# 4. 跑 e2e (12 case)
pytest tests/test_w79_commercial_operation_e2e.py -v
```

## 9. memory 沉淀

- `memory/w79-1st-batch-b1-commercial-operation-2026-07-28.md` (本任务沉淀)
- 引用: W78 A-2 commit `35ac5ced5` + W78 C-1 commit `4ce9dd5d3` + W78 B-1 commit `cb00397b7` + W78 B-2 commit `41c879726` + W78 D-1 commit `05c9dca2b`
- 锚点范式: W78 第 1 批 276 → W79 第 1 批 B-1 280 守恒 (+1)

## 10. 引用锚点

- W78 A-2 commit `35ac5ced5` §5.4 阶段 5 — 24 人月 Q1 落地实施路线图
- W78 C-1 commit `4ce9dd5d3` — 商业化 SaaS 平台部署 (4 层架构 + 6 商业化表 + multi-tenant 隔离)
- W78 B-1 commit `cb00397b7` — Edge-TTS B+D 组合渐进式 (45/45 e2e PASS)
- W78 B-2 commit `41c879726` — 真支付生产 key 启用 (5/5 e2e PASS)
- W78 D-1 commit `05c9dca2b` — 7 维评分 R10 weights_v4 灰度 (22/22 e2e PASS)
- W78 grand closure commit `849e490f9` — 6 agents 合并 main 收口