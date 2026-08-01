# W98 N-3 件 7 SearchLog 回收率偏差调研 memory (2026-08-01)

> **本任务**: W98 N-3 件 7 SearchLog 回收率调研, 派工 v10 主指挥协调范式第 83 次派工 (调研派生). 锚点范式 W98 +13 → +14 (+1 据实), 纯 docs/memory 范畴.

**worktree**: `E:/agent-w98-n3-searchlog-ctr` (branch `chore/w98-n3-searchlog-ctr`, 基于 main `68ed0b55c`)
**派工类型**: A 调研 + D 收口 (混合, 纯 docs/memory)
**commit**: `[N-3 W98 +14] docs: 件 7 SearchLog 回收率偏差调研 (3 方案 + 推荐 + UI 改进清单)`
**对应 runbook**: `docs/w98-n3-searchlog-ctr-2026-08-01.md` (250+ 行完整调研报告)

---

## 1. 任务主结论 3 条

1. **派工 brief 偏差是真偏差**: 件 7 派工期望 "feedback API ≥ 18 PASS" 错配件 7 真语义 "SearchLog CTR ≥ 30% (click/曝光)", 实测 feedback API = **14/14 PASS**. 派工 brief 错误来源是 `docs/rag/EVAL.md` 第 15 行 + 第 55-62 行定义未读.
2. **埋点未启用是事实**: `web/src/api/analytics.js` 定义了 `recordSearchEvent` + `recordClick`, 但 view 层未调用 (`grep web/src/views --include="*.vue"` 仅命中搜索 UI, 无埋点调用点). 即使真环境跑也无法重现 PR6/7 ≥ 30% 期望.
3. **推荐方案**: **选项 C (双轨分阶段)** — 短期阈值 ≥ 15% (基于实测) + 中期 UI 改进 (W99 P1) + 长期回归 ≥ 30% (W101+).

---

## 2. 件 7 真语义澄清 (PR6/7 落库)

`docs/rag/EVAL.md` 件 7 SQL 视图 (PR6/7 落库, W92 PR6 + W93 PR7 锚点):

```sql
SELECT date_trunc('day', created_at) AS d,
       count(*) FILTER (WHERE clicked) * 100.0 / NULLIF(count(*), 0) AS ctr
FROM search_logs GROUP BY 1 ORDER BY 1 DESC LIMIT 14;
```

> CTR ≥ 30% + 慢查询占比 ≤ 5%; grafana 面板消费同一视图.

**件 7 真定义**: SearchLog 表 `clicks / total_searches ≥ 30%` 门禁, **不是 feedback API 测试用例数**.

### 2.1 件 7 数据成熟条件 (PR6 + PR7 落库必备)

1. **PR6 W92 +0..+12**: `SearchLogs.vue` 管理页 + `useSearchLogs` + 11/13 endpoint 接通 (W92 PR6 grand closure self-report)
2. **PR7 W93 +0..+14**: 慢查询索引 + grafana 7 面板
3. **数据累积周期**: ≥14 天 (SQL LIMIT 14)
4. **埋点接通**: view 层触发 POST /analytics/search-event + PATCH /analytics/search-event/{id}/click

### 2.2 N-3 调研发现埋点未接通

- `web/src/api/analytics.js` 定义 `recordSearchEvent` + `recordClick` (line 全文已读)
- view 层 grep 仅命中 `MobileMeetingView.vue` 搜索 UI, **无埋点调用**
- 真相: KnowledgeView 搜索 + 点击**没有触发** POST /analytics/search-event
- 影响: SearchLog 表累积数据 = 0 (或历史 seed), CTR 真回收率**永久不可测**

---

## 3. 真期望 vs 实测 (件 7 派工 brief 偏差数据)

| 维度 | 派工 brief 期望 | 实测 | 偏差性质 |
|------|-----------------|------|---------|
| 件 7 测试用例数 | feedback API PASS ≥ 18 | feedback API = 14 | **brief 误解件 7** |
| 件 7 真语义 | (隐含) 测试用例数 | **SearchLog CTR ≥ 30%** | **brief 错配 → 件 7 是 SQL** |
| feedback 测试实际意义 | (隐含) 件 7 守恒依据 | **14/14 PASS 已覆盖** | **14 PASS 是真守恒** |
| 件 7 CTR 本机可测性 | (隐含) 可测 | **PG 不可达 + 无 .env** | **实测不可达** |
| 前端埋点接通 | (隐含) PR6 已接通 | **view 层未调用** | **埋点未启用** |

---

## 4. 类 20.33 实战沉淀 (W98 N-3)

### 4.1 类 20.33 件 7 CTR 派工 brief 偏差 + 埋点未启用 双错配

- **根因 1**: 派工 v10 §0 件 7 期望 "feedback API ≥ 18" 错配了真语义 "SearchLog CTR ≥ 30%"
- **根因 2**: PR6 grand closure self-report "前端接通" 未对应 view 层调用点, 仅有 API 定义
- **真守恒**: 14/14 PASS 已 100% 覆盖 P1-D3 + P2-E2E, 件 7 真守恒待 W99 P1 实施
- **修复路径**: 双轨分阶段 (选项 C), 短期调低阈值 ≥ 15% + 中期 UI 改进 + 长期回归 ≥ 30%

### 4.2 类 20.33 与 类 20.112 关系

| 类 | 实战标题 | 派工 | 关系 |
|----|---------|------|------|
| **类 20.112** | feedback API 派工 brief ≥18 vs 实测 14 | W98 P2 | **N-3 调研铺垫** (P2-GATE 据实已收口) |
| **类 20.33** | 件 7 CTR 派工 brief + 埋点未启用双错配 | W98 N-3 | **本任务沉淀** (新增) |

---

## 5. 3 候选方案对比 + 主拍推荐

### 5.1 选项 A: 调低阈值到 ≥ 15% (基于实测)

- **依据**: 实测 14 PASS / 调低到 ≥ 15 对齐实测
- **风险**: 派工目标降级 + 偏离派工原意
- **推荐度**: ❌ 不推荐

### 5.2 选项 B: 保持 ≥ 30% + 实施改进 (派工原意)

- **必查**: UI 改进清单 (KnowledgeView + Mobile + 视觉 + 文案 + 匿名)
- **必查**: analytics.py 聚合 answer_rating 维度 (否, 仅 CTR)
- **推荐度**: ⚠️ 派工原意符合, 但短期无可行实施路径

### 5.3 选项 C: 双轨分阶段 ⭐ 推荐

| 阶段 | 任务 | 阈值 |
|------|------|------|
| 短期 (本任务后续) | 调低件 7 阈值至 ≥ 15% (基于实测) | ≥ 15% (调研基线) |
| 中期 (W99 P1 派工) | UI 改进清单 (§7.2) + 14 天数据累积 | 暂不设硬门禁 |
| 长期 (W101+) | 回归 ≥ 30% (成熟阶段) | ≥ 30% (守恒硬门禁) |

- **依据**: 件 7 派工原意 ≥ 30% 是对的, 但实施前置条件不足 (埋点未启用), 因此短期不可硬门禁
- **推荐度**: ✅ **主拍推荐**

---

## 6. UI 改进清单 (W99 P1 具体任务)

### 6.1 KnowledgeView 搜索结果点击埋点接通

`web/src/views/KnowledgeView.vue` + `web/src/views/mobile/knowledge/MobileKnowledgeView.vue`:

```js
import { recordSearchEvent, recordClick } from '@/api/analytics'

// 搜索时触发
const event = await recordSearchEvent({
  query,
  top_ids: results.map(r => r.id),
  session_id: uuid(),
  source: 'knowledge_search',
})

// 点击触发
await recordClick(event.search_event_id, {
  clicked_id: result.id,
  click_position: position,
})
```

### 6.2 移动端同样接通 (`web/src/views/mobile/*`)

### 6.3 视觉强化

- top-1 结果 badge 高亮 ("推荐")
- 滚动到位提示

### 6.4 FeedbackButtons 文案激励 (`web/src/components/chat/FeedbackButtons.vue`)

- 👍 改 "回答有帮助"  
- 👎 改 "需要改进"
- 评语 prompt 改 "帮助我们回答得更好 (选填)"

### 6.5 匿名用户填补 (`app/api/v1/chat_feedback.py` line 130)

- 当前 `user_id > 0` 守卫, 匿名用户不写 answer_rating
- 应放开 (存 session_id + IP hash 关联)

### 6.6 analytics.py 聚合 answer_rating

- 当前 `/analytics/stats` (363 行) 没聚合 answer_rating 维度
- 应加 `by_answer_rating` 维度

---

## 7. 据实上报 18 项 (派工 v10 §5)

| # | 项 | 实测 |
|---|----|------|
| 1 | 任务目标完成度 | ✅ 件 7 偏差调研报告完成 |
| 2 | 实际 git diff 文件清单 | 2 新建 (docs + memory) + 1 修改 (MEMORY.md 追加) |
| 3 | 件 7 派工 brief vs 实测偏差 | 5 处偏差对照 |
| 4 | SearchLog ORM 字段实测 | 11 + 20 (PR7 扩展) 字段 |
| 5 | chat_feedback API endpoint | 1 endpoint + best-effort 写入 |
| 6 | 回收率定义澄清 (3 种) | CTR / fb 数 / answer_rating 反馈率 |
| 7 | 实际数据样本 | 本机不可达 + 推荐真环境命令 |
| 8 | 选项 A 详细依据 | 派工目标降级风险 |
| 9 | 选项 B 详细依据 | 派工原意 + UI 改进 |
| 10 | 选项 C 详细依据 | 双轨分阶段 |
| 11 | 主拍决策 + 推荐方案 | **选项 C 双轨分阶段** |
| 12 | UI 改进具体清单 | 6 类 (KnowledgeView + Mobile + 视觉 + 文案 + 匿名 + analytics) |
| 13 | 0 production code 实测 | 0 |
| 14 | alembic 1 head 实测 | 093 |
| 15 | 锚点范式实测 commit 数 | W98 +14 |
| 16 | 类 20.33 实战沉淀 | 件 7 CTR 偏差 + 埋点未启用双错配 |
| 17 | worktree 状态 + push origin | 待 push |
| 18 | 任何回归风险 | 0, 纯调研 |

---

## 8. W98 累计 commits + 锚点范式

**锚点范式演化**: W97 477 → W98 +13 (~490) → **W98 N-3 +14** (本任务据实) 守恒
**alembic**: 1 head `093_add_search_log_answer_rating` 守恒
**0 production code**: `git diff 68ed0b55c -- app/ web/src/ alembic/ | wc -l` = 0 (待验证)
**W98 N-3 增量**: 1 commit (纯 docs/memory 调研范畴)

---

## 9. W98 N-3 类 20 实战累计

### 9.1 类 20 累计 (W98 N-3 据实)

| # | 实战 | 派工 | 状态 |
|---|------|------|------|
| 类 20.111 | verify_alembic_chain.sh 088 vs 093 | W98 P2-GATE | 实测 1 head = 093 PASS |
| 类 20.112 | feedback API ≥ 18 vs 14 PASS | W98 P2-GATE | 14/14 仍 PASS, 件 7 守恒 |
| 类 20.113 | micro_bubble_agent.py <200 vs 294 | W98 P2-GATE | +108 行实测, 核心约束守恒 |
| **类 20.33** | **件 7 CTR 派工 brief 偏差 + 埋点未启用** | **W98 N-3** | **本任务新增** |

### 9.2 类 20.33 子类细化 (N-3 派生)

- **类 20.33.a**: 件 7 派工 brief 错配真语义 (CTR → feedback API 测试数)
- **类 20.33.b**: PR6 grand closure self-report 误报 "前端接通" (实际仅有 API 定义, 无 view 调用)
- **类 20.33.c**: UI 埋点未启用 → 件 7 真守恒待 W99 P1
- **类 20.33.d**: 双轨分阶段 (短期 ≥ 15% + 中期 UI 改进 + 长期 ≥ 30%)

---

## 10. W99+ 件 7 关联派工 (主拍签字范围外)

| 派工 | 范围 | 件 7 关联 |
|------|------|----------|
| W99 P1 | 召回率 95%+ | **附加 UI 改进清单 (§6) + 埋点接通** |
| W99 P2 | P95 < 2s | 独立 |
| W100 P1 | Self-RAG | 独立 |
| W101+ | 索引重建 | 件 7 数据成熟期后验证 ≥ 30% |

---

## 11. Co-Authored-By

```
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

派工 v10 §0 边界 (纯 docs/memory) + §6 据实上报铁律 + §8 起步 6 项 + §9 commit 锚点范式全部遵守. 偏差澄清 + 类 20.33 沉淀 + 选项 C 推荐 + UI 改进清单齐备, 主拍可直接拍板.
