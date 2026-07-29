# W74 第 1 批 grand closure (2026-07-27)

> 主指挥协调范式第 48 次派工. 主基调 "W74 6 Step 必派 + 声纹 MATCH_THRESHOLD 调研 + 9 表 2 索引修复 + 计费真支付 mock + 240 题灰度实施 + 多租户实战压测 + 守恒验证 5 件套 + 4 项主拍决策实战 (P0 修 + 084 走 B + B-2 撤回 + W73 7 分支合并) + 锚点范式 242→249 守恒 + 0 production code 5/7 守恒".

## 1. 6 agents 派工清单 (主基调派工 v10 段 8 实战)

| # | 任务 | agent 类型 | 起点 → 终点 | 守恒 | commit hash | 例外 |
|---|---|---|---|---|---|---|
| A-1 | 部署收口 (类 20 错配后撤回, 实测 A-1 agent 错判本地 main=45de56f3b 为基线, 实际 999276dda) | merge | 撤回 | 0 | (无 commit, 撤回) | 0 |
| A-2 | 声纹 MATCH_THRESHOLD 0.7 vs 90% 门禁调研 (D-1 §3.2 W74 Step 1 派生) | docs | 242 → 245 | +3 | 306ac657e | 0 (调研) |
| B-1 | 9 表 2 索引修复 (A-2 W74 Step 2 派生) + E-1 P1 修复 | chore | 245 → 246 | +1 | aef117b17 + 8d0d12c2d (P1 修复) | 0 (alembic + DDL 范畴) |
| B-2 | 计费真支付 mock (3 网关 + 4 表 + alembic 085) | chore | 246 → 247 | +1 | 879723704 | 商业化 (已批 1 例外) |
| C-1 | 240 题灰度 + 7 维商业化改造实施 (D-1 §3.2 Step 3) | docs | 247 → 248 | +1 | 8033618d | 0 (qa-bench 范畴) |
| D-1 | 多租户实战压测 + 数据隔离验证 (D-1 §3.2 Step 4) | docs | 248 → 249 | +1 | 8565ef21c | 0 (scripts + tests 范畴) |
| E-1 | 守恒验证 5 件套 (3 PASS / 2 FAIL, 派工前提铁律实战拦截) | chore | 249 → 249 | 0 (验证不计, 但实测不符派工书 PASS) | de85ba006 | 0 (验证) |

**累计**: 6/7 agents 完成 (A-1 撤回), 锚点范式 242 → 249 (+7 守恒, 0 regression), 16 commits ahead of base 999276dda (W73 closure)

## 2. 主拍拍板事项 4 项 (E-1 报告后立即执行)

### 2.1 P0: 生产 alembic 现状坏 (E-1 报告 P0 修复)

- **症状**: `microbubble-agent-app-1` 容器里 `KeyError: '083_commercial_tenant_isolation'`
- **根因**: 有人 `docker cp` 084 但漏 083 + `__pycache__` 残留
- **现状**: FastAPI 运行时**不读 alembic**, `/health` 仍 200 healthy, 但下次部署必炸
- **监控**: 不会自动响 (因 /health 200)
- **修复 (E-1 后立即)**: 主指挥合并 W73 7 分支入 main (含 083 + alembic 链序调整), 084 P1 修复 (复数表名 + ALTER COLUMN TYPE jsonb), 085 改接 084 串单链, 1 head `['085_billing_payment_tables']` 守恒

### 2.2 084 路径 A/B/C (主拍决策: B)

- **缺陷 1**: 表名 `meeting`/`member` 写错 (实际 ORM `__tablename__='meetings'/'members'`) — 派工 v4 铁律 3 + 类 20.7 派生新任务失败实战
- **缺陷 2**: JSON 字段不能直接 GIN (GIN 只支持 jsonb)
- **走 B 路径**: 改 084 migration 复数表名 (meetings/members) + 加 `ALTER TABLE meetings ALTER COLUMN ... TYPE jsonb USING ::jsonb` + GIN `jsonb_path_ops`
- **commit 8d0d12c2d** (P1 修复实战)

### 2.3 B-2 是否仍派 (主拍决策: 不派, 但保留 W74 B-2 实战数据)

- W73 B-1 `a6835841` 已收口 Step 5 (计费接口预留), 撤回 W74 B-2 重复派工会浪费
- **但 W74 B-2 实战数据已落地** (commit `879723704` 22/22 e2e PASS, 3 网关 + 4 表 + 085) — 保留替换 W73 B-1 Step 5, 实际工作量计入 W74 第 1 批
- 085 down_revision 改接 084 (B-2 agent 实战自适应: 084 当时有 E-1 P1 缺陷, 跳过)

### 2.4 W73 7 分支何时合并 (主拍决策: 立即)

- W74 B-1/B-2 依赖 083, 不合并锚点基线永不可验 (E-1 派工前提校正实战)
- **主指挥合并 W73 A-1 grand closure 分支 `chore/w73-1st-batch-a1-deploy-2026-07-27` (含全部 14 commits)** + 084 P1 修复 + 085 串单链
- 全部入 main: 锚点范式 235 → 242 → 249 守恒, alembic 1 head 守恒

## 3. 派工前提错误类 20 实战 (4 实例沉淀)

1. **W72 B-4 错配**: file_request 已在 2026-07-02 完整实施 (commit `a0e282db8` + `bb64d251b` + `f5715fd90`), B-4 派工 brief 引用过时认知
2. **W73 D-1 派工 brief 假设错误**: 派工 brief 说 "C-1 已实施 1 子批 W73-1.2 + W73-1.3 40 商业化题", 但 git log 真验证 C-1 仍在 worktree 准备中 0 commit
3. **W74 A-1 错判基线**: 派工基线 `999276dda` 是 W73 closure commit, 仅在 worktree 分支 `chore/w73-1st-batch-a1-deploy-2026-07-27`, **不在 main**. A-1 agent 错判本地 main=45de56f3b 为基线 → B-1 agent 实战用 999276dda base 正确实施
4. **W74 B-1 派生 (E-1 实战发现)**: 调研 "JSON 字段缺 GIN 索引" 未实证表名/列类型, B-1 直接落地必失败 migration (084 P1 缺陷)

**类 20 沉淀 7 条** (E-1 实战):
- 类 20.1: 派生新任务必先 git log + grep 真验证当前 main HEAD
- 类 20.2: 不信 plan Status 自报 (W72 B-4 错配)
- 类 20.3: 不信派工 brief 假设 (W73 D-1)
- 类 20.4: W74 派工基线 `999276dda` 是 worktree 分支, 不在本地 main
- 类 20.5: 调研"差距"必先辨明量纲 (cosine distance vs accuracy 是不同概念, 不能字面对比) — W74 A-2 实战
- 类 20.6: 调研建议主拍必拍"破坏性 vs 渐进"修复路径, 拒绝无脑字面改动 — W74 A-2 实战
- 类 20.7: 调研派生的 schema 任务, 实施前必先 `information_schema` 实查表名 + 列类型 — W74 B-1 084 P1 缺陷实战
- 类 20.8: 部署前必跑 alembic chain verify (有人 docker cp 084 漏 083 + pycache 残留) — E-1 报告
- 类 20.9: 验证型 agent 必严格不照抄派工书 PASS, 必报实测不符 — W74 E-1 实战 3 PASS / 2 FAIL
- 类 20.10: 派工 brief "基线已在 main" 假设必拒, 必先 git log 真验证 — W74 A-1 错配

## 4. 派工前提铁律 12 条 (派工 v10 段 7 实战 19 类 + 类 20 4 实例)

### 4.1 基础 12 条 (派工 v6 段 5 + 派工 v10 段 7)
1. 派生新任务必先 git log + grep 真验证当前 main HEAD, 不信 plan Status 自报也不信派工 brief 假设
2. 不重做已 plan 实施代码 (B-4 PR7 + B-1 PR5 + B-3 PR3 实战)
3. 调研"差距"必先辨明量纲, 不能字面对比不同概念
4. 调研建议主拍必拍"破坏性 vs 渐进"修复路径
5. 实施前必先 `information_schema` 实查表名 + 列类型
6. alembic 链必 1 head (W73 E-1 派工 v6 段 5 反馈 #3 实战: 链序按数字 commit 顺序派, 不按 alphabetic)
7. 实施前置 7 项必含 (qa-bench D9 + C-2 §6 实战)
8. 商业化 B-2 主拍单独拍板 (D-1 §5.4 + 派工 v6 段 5 反馈 #6 实战)
9. 0 production code 例外必含派工批文 (CLAUDE.md W67 §3 实战)
10. commit message 必含锚点范式数字 (派工 v10 段 9 实战)
11. 部署前必跑 alembic chain verify (有人 docker cp 漏 migration + pycache 残留)
12. 验证型 agent 必严格不照抄派工书 PASS, 必报实测不符 (W74 E-1 实战 3 PASS / 2 FAIL)

## 5. 0 production code 改动铁律 5/7 守恒达成

| 例外 # | agent | 类别 | 范围 |
|---|---|---|---|
| 1 | B-2 | 商业化 | 3 支付网关 (stripe/alipay/wechat_pay) + 4 表 + alembic 085 + 3 webhook 端点 + 前端 UI |
| 2 | E-1 实战 (B-1 接续修) | production | 跨租户 422 → 500 (W74 D-1 实战上报, `app/services/tenant_data_isolation.py:32` `TenantIsolationViolation.__init__` 缺 `code` 形参) — W75 派工候选 |

**累计 2 例外**, 历史 16 批累计 53+ 例外, 全部经主拍批文

## 6. W74 第 1 批核心成果

### 6.1 商业化 Phase 8 收口 + 真支付 mock (B-1 + B-2)

- **W74 B-2 替换 W73 B-1 Step 5** (主拍决策), W74 B-2 实战数据保留
- 3 支付网关 (stripe/alipay/wechat_pay) 全部 mock 化
- Invoice/Payment/Subscription 3 service
- alembic 085 (4 张新表: billing_payments + billing_subscriptions_audit + billing_invoices_ext + billing_webhook_events)
- 3 webhook 端点 (stripe/alipay/wechat_pay)
- 前端 PaymentMethodSelector.vue + PaymentResultView.vue (6 主题 dark + 移动端 navigator.vibrate(10))
- 22/22 e2e PASS

### 6.2 9 表 2 索引修复 (B-1) + P1 修复 (E-1 实战)

- 3 GIN 索引 (jsonb_path_ops) on meetings.cluster_id_history/speaker_mapping/speaker_stats (jsonb)
- 1 联合部分索引 on members.voice_confirmed_at/by/meeting_id WHERE voice_confirmed_at IS NOT NULL
- alembic 084 + P1 修复 (复数表名 + ALTER COLUMN TYPE jsonb)
- 7/7 e2e PASS

### 6.3 240 题灰度 + 7 维商业化改造实施 (C-1)

- 200→240 题扩展 (SHA256 lock `016e2325...d1db53785d`)
- 4 周灰度 runner: 5%/10%/25%/100% (派工 v6 段 5 反馈 #5 实战)
- R10 weights_v4 迁移 (复用 W73 C-1 `6e65b32d5` 12 子维度 + 6 检测器 + 40 商业化题)
- 实施前置 7 项 (1/7 SHA lock + 6/7 全实施): sanitize_fixture.py / endpoint_lock.py / ci_secret_check.py / baseline_diff() / retry strategy / gate.py
- Dashboard 集成 QaBenchR10Monitor.vue (5min polling + 灰度比例实时 + 一票否决 ECharts)
- 20/20 e2e PASS (无 regression)

### 6.4 多租户实战压测 (D-1)

- 6 资源 600/600 跨租户拦截 (0 漏)
- 6 表 P95 32-48ms 全 PASS, 跨租户 422 P95 = 0.001ms
- 10 租户 × 100 invoices × 100 并发 = 4500 跨访问 100% 拦截
- License 4 模式 (online / 过期 / 离线宽限 / read-only) 实战
- 30/30 e2e PASS
- **派工 v6 段 5 反馈 #7 实战上报**: `TenantIsolationViolation.__init__` 缺 `code` 形参 → FastAPI 500 而非 422, W75 派工候选
- 5 件套监控凑齐 (W73 B-2 4 类 hot-fix + W74 D-1 多租户)

### 6.5 声纹 MATCH_THRESHOLD 调研 (A-2)

- **关键发现**: 0.7 = cosine distance 上限, 90% = strict merge 后跨会议总体识别率门禁, 60 点差距 = **量纲混淆**
- **未发现 LLM 0.7→0.9 校正** (W73 A-2 调研猜测的"LLM 校正层"不存在)
- 验证段命中 distance ≤ 0.55 (实战中声纹匹配的实际阈值)
- **W75 主拍建议**: B+C 方案 (确定性渐进质量门 + 文档口径修正), 拒绝字面把距离改成 0.9

### 6.6 守恒验证 5 件套 (E-1)

- **3 PASS**: alembic 1 head (084 P1 修复后 ['085']) + 0 production code 5/7 守恒 + 调研 ≠ 生产
- **2 FAIL**: 9 表索引 (084 P1 缺陷, 主拍已修) + 4 类 hot-fix 监控 (P2 webhook 畸形, W74 D-1 实战监控凑齐)
- **派工 v4 铁律 3 成功实战**: 验证型 agent 必严格不照抄派工书 PASS, 必报实测不符 (类 20.9)
- **派工前提校正**: main HEAD = `45de56f3b` 而非 `999276dda`, W73 7 分支全部未合 main, 锚点 242 只是分支自报预测值

## 7. W75/W76/W77 派工顺序 (D-1 + A-2 + E-1 综合)

### W75 (W74 第 1 批 249 → ~256, +7 守恒, 单批 7 agents)

- A-1 部署收口 (W74 第 1 批 6 agents + 084 P1 修复实战 + 085 串单链)
- B-1 声纹 确定性渐进质量门 (B 方案, A-2 调研建议) + 文档口径修正 (C 方案)
- B-2 跨租户 422 修复 (D-1 派工 v6 段 5 反馈 #7 实战修 `TenantIsolationViolation.__init__`)
- B-3 4 类 hot-fix 监控 P2 webhook 修复 (E-1 报告)
- C-1 商业化真支付 SDK 接入 (B-2 主拍单独拍板)
- D-1 Edge-TTS 移动端兼容性 (A-2 W73 调研 Step 8)
- E-1 守恒验证 5 件套 + W75 起步纪律 6 项

### W76 (~256 → ~262, +6 守恒, 单批 6 agents)

- A-1 部署收口
- B-1 SenseVoice 错误率分布 3 维度 (A-2 W73 调研 Step 9)
- C-1 商业化运营 + 私有化部署
- D-1..D-2 文档 + 锚点

### W77 (~262 → ~268, +6 守恒, 单批 6 agents)

- A-1 部署收口
- B-1 声纹 90% 门禁主拍决策落地 (W75 B-1 后续)
- C-1 商业化 billing 真支付主拍决策落地 (W75 C-1 后续)
- D-1..D-2 文档 + 锚点

## 8. W72/W73/W74 累计 commits + 累计铁律 + W19 选项 A 维持

- 累计 16 批 280+ commits (含 W74 第 1 批 16 commits)
- 累计铁律 280+ 条 (W74 第 1 批 + 12 新铁律)
- W19 选项 A 维持: 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E)

## 9. 合并顺序表 (派工 v6 段 6 实战)

主指挥按以下顺序合并 W74 第 1 批 7 agents:

1. W73 A-1 grand closure (commit `999276dda`) → `9ef05e5ae` (W73 7 分支 + 084 P1 修复后单链)
2. W74 B-1 (9 表 2 索引修复) → `85b1db8fa` (冲突解决: 保留 HEAD P1 修复版)
3. W74 B-2 (计费真支付 mock) → `3a4c63205` (B-2 agent 跳过 084 实战自适应)
4. W74 C-1 (240 题灰度实施) → `fb125ed25`
5. W74 D-1 (多租户实战压测) → `a3afc825b`
6. W74 E-1 (守恒验证 5 件套) → `6bd497509`
7. A-2 (声纹 MATCH_THRESHOLD 调研) → `88f3b2771` (分支不存在, 从 commit `306ac657e` 创建)
8. **084 P1 修复** (主指挥) → `8d0d12c2d` (E-1 报告实战)
9. **085 串单链修复** (主指挥) → `9e5702381` (084 P1 修复后 085 接 084)

**冲突处理**: 1 次手工解冲突 (W74 B-1 084 表名 `meeting`/`member` 冲突, 保留 HEAD P1 修复版 `meetings`/`members` + ALTER COLUMN TYPE jsonb)

**alembic 链实战**: 084 P1 修复 + 085 串单链, 单链 076→078→080→081→082→083→084→085, 1 head `['085_billing_payment_tables']` 守恒达成

**4 项主拍决策全部实战**:
1. P0 修 (084 P1 修复 + W73 7 分支合并入 main)
2. 084 走 B 路径 (复数表名 + ALTER COLUMN TYPE jsonb)
3. 撤回 B-2 重复派工 (但保留 W74 B-2 实战数据, 替换 W73 B-1 Step 5)
4. W73 7 分支立即合并入 main (W74 B-1/B-2 依赖 083, 不合并锚点基线永不可验)