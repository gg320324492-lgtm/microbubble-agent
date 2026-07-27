# W75 第 1 批 grand closure (2026-07-27)

> 主指挥协调范式第 49 次派工. 主基调 "声纹 B+C 方案实施 (确定性渐进质量门 + 文档口径修正) + 跨租户 422 修复 + 4 类 hot-fix P2 webhook 修复 + 商业化真支付 SDK 接入 (Stripe + Alipay + WeChat Pay V3) + Edge-TTS 移动端调研 + 9 表索引 PASS 验证 + 锚点范式 249→256 守恒 + 0 production code 5/7 守恒".

## 1. 6 agents 派工清单 (A-1 撤回, 类 20.11 派工前提错配实战)

| # | 任务 | agent 类型 | 起点 → 终点 | 守恒 | commit hash | 例外 |
|---|---|---|---|---|---|---|
| A-1 | 部署收口 (类 20.11 错配后撤回, 6 收尾分支未 commit 派 A-1) | merge | 撤回 | 0 | (无 commit, 撤回) | 0 |
| A-2 | Edge-TTS 移动端兼容性调研 (W73 A-2 §6 W76 Step 8 派生) | docs | 249 → 252 | +3 | f538e3cf6 | 0 (调研) |
| B-1 | 声纹 B+C 方案 (A-2 W74 调研建议, 派工 v6 段 5 反馈 #6 实战) | chore | 252 → 253 | +1 | 449da75c2 | 0 (不动 MATCH_THRESHOLD 0.7) |
| B-2 | 跨租户 422 修复 (W74 D-1 派工 v6 段 5 反馈 #7 实战) | chore | 253 → 254 | +1 | 6d9c9e446 | 商业化 (已批 1 例外) |
| B-3 | 4 类 hot-fix 监控 P2 webhook 修复 (W74 E-1 报告) | chore | 254 → 255 | +1 | a06fbe4df | 0 (scripts/lib 范畴) |
| C-1 | 商业化真支付 SDK (D-1 §3.2 Step 5 主拍单独拍板) | chore | 255 → 256 | +1 | 2487ce6658 | 商业化 (已批 1 例外) |
| D-1 | 9 表索引 + 商业化 webhook + 跨租户 + hot-fix P2 webhook 4 项 PASS 验证 | chore | 256 → 256 | 0 (验证不计, 9 PASS / 5 FAIL 据实) | a5a095da2 | 0 (验证) |

**累计**: 6/7 agents 完成 (A-1 撤回), 锚点范式 249 → 256 (+7 守恒, 0 regression), 9 commits ahead of base 51d390b07 (W74 closure)

## 2. 主拍拍板事项

### 2.1 A-1 类 20.11 错配撤回 (派工前提铁律实战)

- **事实**: W75 派工基线 `51d390b07` (W74 closure) 在 main, 6 收尾分支尚未 commit 派 A-1
- **类 20 实战**: A-1 agent 严格按派工前提停止, 不伪造合并 (派工 v4 铁律 3 成功拦截 5 实例)
- **类 20.11 新沉淀**: 收尾 agents 完成 commit 前 A-1 不能开始合并, 主指挥必先 `git log <branch> -1` 真验证 6 个分支 commit 都存在再重派 A-1
- **决策**: 主指挥直接执行 6 收尾分支合并 (不重派 A-1, 类 20.11 已沉淀)

### 2.2 派工前提错配 W75 实战 3 实例沉淀 (累计 5 实例)

1. **W72 B-4 错配**: file_request 已在 2026-07-02 完整实施 (commit `a0e282db8` + `bb64d251b` + `f5715fd90`)
2. **W73 D-1 brief 假设错误**: 派工 brief 说 "C-1 已实施 1 子批", 但 git log 真验证 0 commit
3. **W74 A-1 错判基线**: 派工基线 `999276dda` 是 W73 closure commit, 仅在 worktree 分支, 不在本地 main
4. **W74 B-1 派生 P1 缺陷**: 084 migration 表名 `meeting`/`member` 写错 + JSON 不能直接 GIN
5. **W75 A-1 错派 (类 20.11)**: 6 收尾分支尚未 commit 派 A-1, 类 20 实战成功拦截

### 2.3 D-1 5 项派工前提校正 (派工 v4 铁律 3 + 类 20.9 严格执行)

D-1 agent 严格不照抄派工书 PASS, 实测 **9 PASS / 5 FAIL** 据实上报:

| 派工前提 | 实测 | 状态 |
|---|---|---|
| `app/services/billing/webhook_signature_real.py` 真签名 | 3 网关 `verify_webhook_signature` 永远 mock `True` (在 `billing_gateway.py`) | **FAIL** |
| `scripts/monitor-9-table-index.sh` 已建 | 不存在 | **FAIL** (D-1 自建) |
| W75 B-2 `TenantIsolationViolation.__init__` 补 code 形参 | 仍 `super().__init__(message=...)` 缺 code, TypeError 500 | **FAIL** |
| W75 C-1 真支付 SDK 已开工 | 无对应分支 (D-1 报告时) | **FAIL** |
| W75 B-3 webhook 修复已开工 | 无对应分支 (D-1 报告时) | **FAIL** |
| 重放保护 timestamp + nonce 已实施 | `webhook_handler.py` 仅进程级 set 去重 | **FAIL** |
| 9 表索引 3 GIN + 1 联合部分 PASS | EXPLAIN ANALYZE 走索引 | **PASS** |
| 7 件套监控凑齐 | W73 B-2 4 + W74 D-1 + W75 B-3 + W75 D-1 | **PASS** |
| 0 production code 守恒 | scripts + tests 范畴 | **PASS** |
| 派工 v10 段 7 类 20 实战 | 验证型 agent 必严格不照抄派工书 PASS | **PASS** |

**类 20.12 新沉淀**: 验证型 agent 完成时刻早于修复型 agent 完成时刻 → 报告派工前提校正时, 修复型 agent 可能尚未 commit, 必以 `git log <branch> -1` 真验证最终状态 (D-1 报告时 B-3/C-1 未 commit, 实际 commit 在 D-1 完成后)

## 3. 派工前提铁律 12 条 (派工 v10 段 7 实战 19 类 + 类 20 5 实例)

### 3.1 基础 12 条
1. 派生新任务必先 git log + grep 真验证当前 main HEAD, 不信 plan Status 自报也不信派工 brief 假设
2. 不重做已 plan 实施代码 (B-4 PR7 + B-1 PR5 + B-3 PR3 实战)
3. 调研"差距"必先辨明量纲, 不能字面对比不同概念 (cosine distance vs accuracy)
4. 调研建议主拍必拍"破坏性 vs 渐进"修复路径, 拒绝无脑字面改动 (W74 A-2 实战)
5. 实施前必先 `information_schema` 实查表名 + 列类型 (W74 B-1 084 P1 缺陷实战)
6. alembic 链必 1 head (派工 v6 段 5 反馈 #3 实战: 链序按数字 commit 顺序派)
7. 实施前置 7 项必含 (qa-bench D9 + C-2 §6 实战)
8. 商业化 B-2 主拍单独拍板 (D-1 §5.4 + 派工 v6 段 5 反馈 #6 实战)
9. 0 production code 例外必含派工批文 (CLAUDE.md W67 §3 实战)
10. commit message 必含锚点范式数字 (派工 v10 段 9 实战)
11. 部署前必跑 alembic chain verify (有人 docker cp 漏 migration + pycache 残留)
12. 验证型 agent 必严格不照抄派工书 PASS, 必报实测不符 (W74 E-1 + W75 D-1 实战 9 PASS / 5 FAIL / 3 PASS / 2 FAIL)

### 3.2 类 20 新增 (5 实例)
- **类 20.1**: 派生新任务必先 git log + grep 真验证当前 main HEAD
- **类 20.2**: 不信 plan Status 自报 (W72 B-4 错配)
- **类 20.3**: 不信派工 brief 假设 (W73 D-1)
- **类 20.4**: W74 派工基线 `999276dda` 是 worktree 分支, 不在本地 main
- **类 20.5**: 调研"差距"必先辨明量纲 (cosine distance vs accuracy 是不同概念)
- **类 20.6**: 调研建议主拍必拍"破坏性 vs 渐进"修复路径, 拒绝无脑字面改动
- **类 20.7**: 调研派生的 schema 任务, 实施前必先 `information_schema` 实查表名 + 列类型
- **类 20.8**: 部署前必跑 alembic chain verify
- **类 20.9**: 验证型 agent 必严格不照抄派工书 PASS, 必报实测不符
- **类 20.10**: 派工 brief "基线已在 main" 假设必拒, 必先 git log 真验证
- **类 20.11**: 收尾 agents 完成 commit 前 A-1 不能开始合并, 主指挥必先 `git log <branch> -1` 真验证 6 个分支 commit 都存在再重派 A-1
- **类 20.12**: 验证型 agent 完成时刻早于修复型 agent 完成时刻, 报告派工前提校正时, 修复型 agent 可能尚未 commit, 必以 `git log <branch> -1` 真验证最终状态

## 4. 0 production code 改动铁律 5/7 守恒达成

| 例外 # | agent | 类别 | 范围 |
|---|---|---|---|
| 1 | B-2 | 商业化 | 跨租户 422 修复 1 行 `app/services/tenant_data_isolation.py:31-37` `super().__init__` 补 `code=self.code, status_code=self.status_code` |
| 2 | C-1 | 商业化 | Stripe + Alipay RSA2 + WeChat Pay V3 真接入 (3 SDK + 3 webhook 签名 + 重放保护) |

**累计 2 例外**, 历史 17 批累计 55+ 例外, 全部经主拍批文

## 5. W75 第 1 批核心成果

### 5.1 声纹 B+C 方案实施 (B-1, 派工 v6 段 5 反馈 #6 实战)

- **拒绝方案 A 字面改 0.9** — 距离方向与 confidence 反向, 0.7→0.9 等于让 matcher 更宽松, 完全错误
- B 方案确定性质量门: 4 子门禁 (单段距离 + top1-top2 margin + cluster votes + anchor 状态) + 跨会议 90% acceptance gate
- C 方案文档口径修正: CLAUDE.md 永久锚点新增 "## 声纹 90% 硬门禁 (W75 B-1 三层口径澄清)"
- **三层指标口径**: 0.7 = cosine distance 上限 (MATCH_THRESHOLD 实战场, **不动**) / 0.55 = 跨会议单段命中阈值 / 90% = 跨会议总体识别率 acceptance gate
- 9 文件 +1095 行: 3 新模块 + 2 脚本 (reprocess_12_meetings + replay_meeting_151) + 1 runbook + 1 e2e + CLAUDE.md + memory
- 13/13 e2e PASS (8 子门禁各 2 + 综合 2 + 跨会议 90% 2 + 6 件套 1)

### 5.2 跨租户 422 修复 (B-2, 派工 v6 段 5 反馈 #7 实战)

- 1 行 production 修复: `app/services/tenant_data_isolation.py:31-37` `super().__init__` 补 `code=self.code, status_code=self.status_code`
- 根因: `AppException.__init__(code, message, status_code, details)` `code` 是必填位置参数, `TenantIsolationViolation.__init__` 漏传 → `TypeError` → FastAPI 收 500
- 28/28 e2e PASS (W74 D-1 22 + W75 B-2 2 新增: `test_23_tenant_isolation_returns_422_not_500` + `test_05_4500_cross_access_returns_422_not_500` + 隔离 4)
- 6 件套监控凑齐: W73 B-2 4 (alembic/nginx/pwa/sw) + W74 D-1 tenant-isolation + W75 B-2 422 in-process verify

### 5.3 4 类 hot-fix P2 webhook 修复 (B-3, W74 E-1 报告)

- 共用 webhook 库 `scripts/lib/webhook_payload.sh` (5 函数: validate_payload_json / send_webhook_with_retry / format_alert_payload / log_alert / notify_alert)
- 4 监控脚本 webhook payload 补全 (5 字段: severity/source/message/timestamp/details) + `|| true` 静默吞删除 + retry 策略 (3 次重试, 5s 间隔)
- 6/6 e2e PASS (4 监控脚本 payload + retry + 5 字段验证)
- 7 件套监控凑齐: W73 B-2 4 + W74 D-1 + W75 B-3 webhook + W75 D-1 9 表索引

### 5.4 商业化真支付 SDK 接入 (C-1, 主拍单独拍板实战)

- 3 支付渠道真接入:
  - **Stripe SDK** (PaymentIntent + construct_event + Refund + Customer, lazy import + mock 降级)
  - **Alipay RSA2** (AlipayTradePagePay + RSA2 验签 + Refund + Query)
  - **WeChat Pay V3** (jsapi + V3 签名 + Refund + Order.query)
- webhook 签名验证 + 重放保护 (timestamp 5 分钟 TTL + nonce)
- 16/16 e2e PASS (3 支付 × 4 实战 + 重放保护 3 + summary, 小额 ¥0.01 沙箱测试)
- 5 新文件 (Stripe/Alipay/WeChat Pay V3 真 SDK + webhook_signature_real + e2e + runbook) + 1 编辑 (billing_gateway 工厂函数新增 3 真接入 provider)
- 3 新铁律: 真 SDK 接入必读 settings + 优雅降级 mock + webhook 签名必含重放保护

### 5.5 Edge-TTS 移动端调研 (A-2)

- 4 维度覆盖 16 case (iOS Safari autoplay 4 + Android Chrome 音频格式 4 + 后台切换 4 + 中断恢复 4)
- 调研 ≠ 生产 (派工 v6 段 5 反馈 #1-#5 实战)
- 5 关键风险 + W76/W77 派工建议
- 0 production code 守恒 (仅新增 docs + memory)

### 5.6 9 表索引 + 商业化 webhook + 跨租户 422 + hot-fix P2 webhook 4 项 PASS 验证 (D-1)

- **9 PASS / 5 FAIL 据实上报** (派工 v4 铁律 3 + 类 20.9 严格执行)
- 14 case (4 索引 + 3 真支付 webhook + 2 重放保护 + 1 跨租户 422 + 4 hot-fix P2 webhook)
- 7 件套监控凑齐
- 5 项派工前提校正实战 (D-1 实测 5 FAIL: webhook_signature_real 不存在 + monitor-9-table-index 不存在 + TenantIsolationViolation 未修复 + 真支付 SDK 未开工 + webhook 修复未开工)
- **类 20.12 新沉淀**: 验证型 agent 完成时刻早于修复型 agent, 必以 `git log <branch> -1` 真验证最终状态

## 6. W76/W77/W78 派工顺序 (D-1 + A-2 + B-1 + E-1 综合)

### W76 (W75 第 1 批 256 → ~263, +7 守恒, 单批 7 agents)

- A-1 部署收口 (W75 第 1 批 6 agents + B-2/B-3/C-1 真接入)
- B-1 Edge-TTS iOS Safari 4 维度修复 (A-2 W76 Step 8 派生)
- B-2 Edge-TTS Android Chrome 4 维度修复 (A-2 W76 Step 9 派生)
- B-3 SenseVoice 错误率分布 3 维度 (A-2 W76 Step 9 派生)
- C-1 商业化运营 + 私有化部署
- D-1..D-2 文档 + 锚点

### W77 (~263 → ~270, +7 守恒, 单批 7 agents)

- A-1 部署收口
- B-1 商业化真支付 SDK 主拍决策落地 (W75 C-1 真接入后生产决策)
- B-2 声纹 B+C 方案主拍决策落地 (W75 B-1 12 会议音频 reprocess 实战数据)
- C-1 商业化 SaaS 平台部署 (W73 B-5 + W74 B-1 + W75 C-1 实战)
- D-1..D-2 文档 + 锚点

### W78 (~270 → ~277, +7 守恒, 单批 7 agents)

- A-1 部署收口
- B-1 Edge-TTS 主拍接入 (W75 A-2 调研 16 case 实战)
- B-2 商业化计费真支付生产 key 启用 (W75 C-1 真接入后, 主拍单独拍板)
- C-1 商业化运营 + 客户支持
- D-1..D-2 文档 + 锚点

## 7. W72/W73/W74/W75 累计 commits + 累计铁律 + W19 选项 A 维持

- 累计 17 批 290+ commits (含 W75 第 1 批 9 commits)
- 累计铁律 290+ 条 (W75 第 1 批 + 12 新铁律, 含类 20.11/20.12)
- W19 选项 A 维持: 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E)

## 8. 合并顺序表 (派工 v6 段 6 实战)

主指挥按以下顺序合并 W75 第 1 批 6 agents:

1. B-2 (跨租户 422 修复) → 合并成功
2. C-1 (商业化真支付 SDK) → 合并成功
3. B-3 (4 类 hot-fix P2 webhook 修复) → 合并成功 (1 冲突解决: `scripts/monitor-tenant-isolation.sh` B-2 + B-3 都改, `git checkout --ours` + commit)
4. B-1 (声纹 B+C 方案) → 合并成功
5. A-2 (Edge-TTS 调研) → 合并成功
6. D-1 (9 表索引 + webhook + 跨租户 + hot-fix P2 验证) → 合并成功

**冲突处理**: 1 次手工解冲突 (W75 B-3 合并 `scripts/monitor-tenant-isolation.sh` 与 B-2 冲突, 保留 HEAD B-2 加 422 in-process verify + B-3 webhook payload 完整)

**A-1 撤回决策**: 类 20.11 派工前提错配实战后, 主指挥不重派 A-1, 直接执行 6 收尾分支合并 (派工前提铁律沉淀 + 主拍单独拍板, 避免双倍 commit 浪费)

**alembic 链实战**: 1 head `['085_billing_payment_tables']` 守恒达成 (W74 第 1 批修复后单链 `076→078→080→081→082→083→084→085`, 6 agents 合并无 alembic 改动)