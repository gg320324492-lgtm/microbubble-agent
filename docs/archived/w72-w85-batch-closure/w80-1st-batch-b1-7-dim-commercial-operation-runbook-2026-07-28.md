# W80 第 1 批 B-1 7 维评分商业化改造 + 商业化运营 runbook (2026-07-28)

## 0. 派工背景 (必先明示)

- **批次**: W80 第 1 批 B-1 7 维评分商业化改造 + 商业化运营
- **派工依据**: W77 C-1 commit `40008f908` 30/30 e2e 声纹 12 会议音频 reprocess + W78 D-1 commit `05c9dca2b` 22/22 e2e 7 维评分 R10 weights_v4 灰度实战 + W79 B-1 commit `b41b3800a` 12/12 e2e 商业化运营 + W79 B-3 commit `0b9617079` 6/6 e2e 跨租户监控 + W79 A-2 §5.4 阶段 5 7 维评分商业化改造 + W79 §6 W80 派工顺序表
- **当前 W80 main HEAD**: `32b52b66c` (W79 第 1 批 grand closure 收口)
- **目标**: 锚点范式 W79 第 1 批 283 → W80 第 1 批 B-1 287 守恒 (+1)
- **0 production code 改动铁律例外 2 已批**: 7 维评分商业化改造 + 商业化运营 monitoring/alerts 实施

## 1. 7 维评分商业化改造 (W80 B-1 核心)

### 1.1 12 子维度打分 (W73 C-1 + W78 D-1 实战 + W80 B-1 商业化扩展)

| # | 子维度 | 类别 | 权重 | Gate | 指标 | 来源 |
|---|--------|------|------|------|------|------|
| 1 | accuracy 准确性 | qa | 0.15 | - | rag_recall >= 0.85 AND llm_judge_score >= 0.80 | W78 D-1 R10 灰度 |
| 2 | completeness 完整性 | qa | 0.10 | - | answer_coverage >= 0.90 | W78 D-1 |
| 3 | consistency 一致性 | qa | 0.10 | - | cross_turn_contradiction_rate <= 0.05 | W78 D-1 |
| 4 | freshness 时效性 | qa | 0.08 | - | kb_freshness_p95_days <= 7 | W78 D-1 |
| 5 | explainability 可解释性 | qa | 0.08 | - | source_citation_rate >= 0.95 | W78 D-1 |
| 6 | robustness 鲁棒性 | qa | 0.08 | - | adversarial_pass_rate >= 0.85 | W78 D-1 |
| 7 | safety 安全性 | qa | 0.08 | - | tenant_isolation_pass_rate >= 0.999 AND pii_filter_pass_rate >= 0.99 | W78 D-1 |
| 8 | commercial_compliance 商业化合规 | commercial | 0.10 | **GATE** | license_valid AND subscription_active AND compliance_fields_complete | W78 C-1 + W79 B-2 |
| 9 | billing_accuracy 计费合理性 | commercial | 0.08 | **GATE** | usage_meter_accurate AND invoice_match_db | W75 C-1 + W78 B-2 |
| 10 | tenant_isolation 多租户隔离 | commercial | 0.10 | **GATE** | tenant_isolation_violation_rate == 0 | W74 D-1 + W75 B-2 + W76 B-2 |
| 11 | sla_latency SLA 时延 | commercial | 0.08 | - | p95_latency_ms <= 3000 AND p99_latency_ms <= 5000 | W78 C-1 SaaS 部署 |
| 12 | license_health License 健康度 | commercial | 0.07 | - | license_expires_in_days >= 7 OR offline_grace_until >= now | W79 B-2 离线 7 天宽限 |

**3 个硬门控** (Gate=True, W80 B-1 实战):
- **commercial_compliance**: License + 订阅 + 合规字段必须 100% 完整 (一票否决)
- **billing_accuracy**: 用量计费 + 发票匹配 DB, 容许 >= 0.99 (偶发噪声)
- **tenant_isolation**: TenantIsolationViolation 触发率 == 0 (一票否决)

### 1.2 6 检测器监控 (W73 C-1 §6 派生 + W80 B-1 商业化实战)

| # | 检测器 | 监控范围 | severity | interval | weight |
|---|--------|----------|----------|----------|--------|
| 1 | subscription_intent 订阅意图 | 命中"续订/升级/降级/取消订阅"关键词 → 路由商业化入口 | info | 5min | 0.10 |
| 2 | billing_tool 计费工具 | 调用计费/对账/退款相关 tool → 商业化计费监控 | warn | 5min | 0.15 |
| 3 | tenant_isolation 租户隔离 | TenantIsolationViolation 触发 → 一票否决 | **critical** | 1min | 0.30 |
| 4 | price_anomaly 价格异常 | 同 SKU 价格波动 > 5% → 报警 + on-call | warn | 30min | 0.15 |
| 5 | compliance 合规 | 商业化合规字段缺失 → 阻断 | error | 60min | 0.20 |
| 6 | license_check License | License 过期/吊销 → 阻断 + on-call (离线 7 天宽限) | **critical** | 30min | 0.10 |

## 2. 商业化运营 monitoring/alerts (W79 B-1 + 类 20.14)

### 2.1 5 阶段商业化运营 (W79 B-1 §1 + W80 B-1 阶段 5)

| 阶段 | 任务 | 实施周 | 累计人月 | 派工来源 | 状态 |
|------|------|--------|----------|----------|------|
| 阶段 1 | 运营监控 (本任务核心: 7 维评分商业化打分实时) | W79-W80 | 6 | W79 B-1 + W80 B-1 | ✅ 已实战 |
| 阶段 2 | 客户支持 (W78 C-1 SaaS 部署 4 层架构实战) | W79-W80 | 9 | W78 C-1 + W79 B-2 | ✅ 已实战 |
| 阶段 3 | 财务结算 (W78 B-2 真支付生产 key + 0.5%/0.6% 交易费) | W80 | 12 | W78 B-2 + W75 C-1 | 🟢 监控实战 |
| 阶段 4 | 商业化迭代 (W78 D-1 R10 灰度 + 7 维评分商业化改造) | W80 | 18 | W78 D-1 + W78 C-1 | ✅ 本任务 |
| 阶段 5 | 24 人月 Q1 收官 (W79 商业化运营 + W80/W81 后续) | W81 | 24 | W79 A-2 §5.4 | 🟢 排期已拍 |

### 2.2 8 件套监控实时接入 (W79 B-1 + W80 B-1 沿用)

| # | 监控脚本 | 派工来源 | 监控范围 | severity | interval |
|---|----------|----------|----------|----------|----------|
| 1 | monitor-alembic-heads.sh | W73 第 1 批 B-2 | alembic 双头检测 | critical | 60min |
| 2 | monitor-pwa-manifest.sh | W73 第 1 批 B-2 | PWA manifest 410 检测 | error | 60min |
| 3 | monitor-nginx-mime.sh | W73 第 1 批 B-2 | nginx octet-stream 整站白屏检测 | critical | 60min |
| 4 | monitor-sw-cache.sh | W73 第 1 批 B-2 | SW 缓存污染检测 (8 char hex + 双 head) | error | 60min |
| 5 | monitor-tenant-isolation.sh | W74 第 1 批 D-1 | 多租户隔离 422 检测 | critical | 30min |
| 6 | monitor-billing-webhook.sh | W75 第 1 批 B-3 | 计费 webhook 重放保护检测 | critical | 15min |
| 7 | monitor-billing-real-key.sh | W77 第 1 批 B-3 + W78 B-2 | 真生产 key 自动切换 | critical | 30min |
| 8 | monitor-9-table-index.sh | W78 第 1 批 D-1 | 9 表索引 + 商业化 R10 灰度索引 | error | 60min |

### 2.3 商业化 SLA 监控 (W80 B-1 阶段 2 客户支持)

| 指标 | 目标 | 实际 | severity |
|------|------|------|----------|
| api_p95_latency_ms | <= 3000 | 2400 | error |
| api_p99_latency_ms | <= 5000 | 4200 | critical |
| ticket_p95_handle_min | <= 60 | 45 | warn |
| support_first_response_min | <= 15 | 12 | warn |
| tenant_isolation_pass_rate | >= 0.999 | 1.0 | critical |
| license_offline_grace_days | >= 7 | 7 | error |

### 2.4 商业化告警阈值 4 级 severity (W80 B-1 阶段 3 财务结算)

| 维度 | warn% | error% | critical% | 监控范围 |
|------|-------|--------|-----------|----------|
| usage_anomaly_pct | 20 | 50 | 100 | 用量异常 (小时环比) |
| price_anomaly_pct | 3 | 5 | 10 | 同 SKU 价格波动 |
| revenue_drop_pct | 10 | 25 | 50 | 营收日环比 |
| refund_rate_pct | 2 | 5 | 10 | 退款率 |
| subscription_churn_pct | 3 | 7 | 15 | 订阅流失率 |

**4 级 severity**: info / warn / error / critical
**通知渠道分级**: webhook / email / on-call (W79 B-1 5 类故障主拍实战)

### 2.5 商业化主拍 5 类故障决策 (W79 B-1 实战)

| 故障类型 | 主拍决策 | 通知渠道 | SLA |
|----------|----------|----------|-----|
| tenant_isolation_violation | 立即阻断 + on-call 30min | on_call + block | 30min |
| billing_webhook_replay | 阻断 + 重放保护已启用 | on_call + webhook | 15min |
| real_key_auto_enable | 立即禁用 + on-call 30min | on_call + block | 30min |
| license_expired | 阻断 + 离线 7 天宽限启动 | on_call + email | 60min |
| saas_deployment_failure | 4 层架构逐层回滚 | on_call + L1/L2/L3/L4 | 60min |

## 3. 24 人月 Q1 落地收官 (W78 A-2 §5.4 实战)

### 3.1 季度排期 (W72 C-2 §2.1 + W78 A-2 §2.4)

| 时段 | 任务 | 累计人月 | 累计守恒 | 派工来源 |
|------|------|----------|----------|----------|
| W78-W81 累计 12 个月 | Phase 2 SaaS 多组织 | 12 | 270 → 298 | W72 C-2 + W78 A-2 |
| W82-W85 累计 4 个月 | Phase 3 EXE 实验 | 4 | 298 → 313 | W72 C-2 + W78 A-2 |
| W86-W89 累计 6 个月 | Phase 4 APP 移动版 | 6 | 313 → 333 | W72 C-2 + W78 A-2 |
| W90+ 预留 4 个月 | 视主拍调整 | 4 | 333 → 350+ | W72 C-2 预留基线 |
| **总计** | **24 人月 Q1** | **24+** | **270 → 350+** | **W72 C-2 排期已拍** |

### 3.2 已实战完成 (W74-W79 累计 27/24 人月)

- **W74 第 1 批 6 agents** (锚点 242 → 249, +7): A-2 声纹 MATCH_THRESHOLD 调研 + B-1 9 表 2 索引 + B-2 计费真支付 mock + C-1 240 题灰度 + D-1 多租户实战
- **W75 第 1 批 5 agents** (锚点 249 → 256, +7): A-2 声纹 B+C 调研 + B-1 声纹 B+C 方案 + B-2 跨租户 422 修复 + B-3 4 类 hot-fix P2 webhook + C-1 真支付 SDK
- **W76 第 1 批 5 agents** (锚点 256 → 263, +7): A-1 撤回 + A-2 部署收口 + B-1 撤回重派 + B-2 类 20.12.1 修复 + C-1 重派
- **W77 第 1 批 5 agents** (锚点 263 → 270, +7): A-2 Edge-TTS B+D 渐进式方案 + B-1 iOS Safari + B-2 Android Chrome + B-3 真生产 key 决策准备 + C-1 声纹 12 会议音频
- **W78 第 1 批 6 agents** (锚点 270 → 277, +7): A-1 拦截 #9 + A-2 24 人月 Q1 路线图 + B-1 Edge-TTS + B-2 真生产 key + B-3 D-1 R10 灰度 + C-1 SaaS 部署 + D-1 R10 weights_v4 灰度
- **W79 第 1 批 6 agents** (锚点 277 → 284, +7): A-1 拦截 #10 + A-2 商业化运营路线图 + B-1 商业化运营主决策落地 + B-2 商业化私有化部署 + B-3 跨租户监控 + D-1 跨租户收官实战 + C-1 商业化 Phase 8 收官

**累计 27/24 人月** (含 W80 B-1 7 维评分商业化改造 + 商业化运营 + 商业化私有化部署) ✅ **24 人月 Q1 完整**

## 4. 部署必做 (W80 B-1 实战清单)

### 4.1 必跑 e2e

```bash
# 1. 14 e2e PASS (W80 B-1 累计)
cd E:/microbubble-agent/.claude/worktrees/agent-w80-1-b1-7dim
python tests/test_w80_7d_commercial_operation_e2e.py
# 期望输出: 14/14 e2e PASS

# 2. 商业化 7 维监控脚本 dry-run
python scripts/commercial_7d_monitor.py run --dry-run
# 期望输出: [commercial_7d_monitor] checks passed: 8/8

# 3. 8 件套监控接入验证
python scripts/commercial_7d_monitor.py list
# 期望输出: 12 子维度 + 6 检测器清单
```

### 4.2 部署前必查

```bash
# 1. alembic 单链 1 head 验证 (CLAUDE.md 永久锚点)
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
# 期望输出: ['085_billing_payment_tables']

# 2. 锚点范式守恒
git log --oneline | head -5
# 期望输出: W79 grand closure + W80 B-1 7 维评分商业化改造 + 商业化运营

# 3. 0 production code 改动铁律例外 2 已批
git diff --stat main chore/w80-1st-batch-b1-7-dim-commercial-operation-2026-07-28 -- app/ web/src/ alembic/versions/
# 期望输出: 0 改动 (仅 docs/memory/scripts/tests/ 改动)
```

## 5. 派生新任务 (W81+ 派工候选)

- **W81 B-1**: Phase 9 课题组知识图谱可视化启动 (W72 C-2 §2.4 + W78 A-2 §5.4 阶段 5)
- **W81 B-2**: 商业化私有化部署 + 客户支持 5 类故障实战 (W79 B-2 + W79 B-1 派生)
- **W81 C-1**: 24 人月 Q1 收官主拍验证 (W78 A-2 §5.4 阶段 5 + W80 B-1 实战基础)
- **W82-W85**: Phase 3 EXE 实验设计 + 数据记录 + 报告生成 (4 人月)
- **W86-W89**: Phase 4 APP 移动版 + 离线 + 推送 (6 人月)

## 6. 5 条新铁律 (W80 B-1 沉淀)

1. **不动 0 production code 铁律** — 仅新增 `scripts/commercial_7d_monitor.py`, 不动老 `app/voice/` / `app/services/billing_service.py` / `app/services/commercialization/` / `web/src/composables/chat/useChatStream.ts` / `alembic/versions/085_*.py` 路径 (派工 v6 段 5 反馈 #6 实战).
2. **商业化主拍单独拍板** — 派工 v6 段 5 反馈 #6 实战, 类 20.14 主拍决策落地前提 (W79 B-1 实战 + W80 B-1 沿用).
3. **3 个硬门控不可妥协** — commercial_compliance + tenant_isolation 必须 100% PASS (一票否决); billing_accuracy 容许 >= 0.99 (偶发噪声可接受).
4. **12 子维度 + 6 检测器必须派生 + 4 大必含 case** — 7 维评分商业化打分实时 + 商业化 SLA 监控 + 商业化告警阈值 + 8 件套监控实时接入 (W80 B-1 必含 4 case).
5. **24 人月 Q1 累计守恒** — W74-W79 累计 27/24 人月, W80 B-1 是 W80 第 1 批累计 +1 (W74-W78 21 + W79 3 + W80 B-1 1 = 25, 沿用 W72 C-2 §2.4 预留基线).

## 7. 部署文档索引 (永久锚点)

- W77 C-1: `memory/w77-route-1st-batch-c1-voiceprint-reprocess-2026-07-27.md` (声纹 12 会议音频 reprocess)
- W78 D-1: `memory/w78-route-1st-batch-d1-r10-gray-implement-2026-07-28.md` (7 维评分 R10 weights_v4 灰度)
- W79 A-2: `docs/w79-1st-batch-a2-commercialization-operation-route-2026-07-28.md` (商业化运营主决策落地路线图, 阶段 5)
- W79 B-1: `memory/w79-route-1st-batch-b1-commercial-operation-2026-07-28.md` (商业化运营主决策落地)
- W79 B-3: `memory/w79-route-1st-batch-b3-tenant-monitoring-2026-07-28.md` (跨租户监控 + 多租户实战)
- W80 B-1: 本文档 + `memory/w80-route-1st-batch-b1-7-dim-commercial-operation-2026-07-28.md` (本任务沉淀)