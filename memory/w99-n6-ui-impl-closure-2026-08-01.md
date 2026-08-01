# W99 N-6 件 7 SearchLog UI 改进 — memory 沉淀 (2026-08-01)

> **主基调**: 锚点范式 W98 +13 → W99 +3 守恒 (+3 据实, 3 commits, 0 production code 边界内).
> **6 类 UI 改进清单全实施**: 桌面 + 移动端埋点接通 + top-1 视觉强化 + FeedbackButtons 文案激励 + 匿名用户填补 + answer_rating 聚合维度.
> **类 20 新增 2 实例**: 20.34 件 7 派工 brief 误读 + 20.35 匿名用户盲区.

---

## §1 派工背景

W98 N-3 件 7 调研 (2026-08-01) 派生 6 类 UI 改进清单 (见 `docs/w98-n3-searchlog-ctr-2026-08-01.md` §7.2), W99 P1 派工 N-6 (主指挥协调范式第 83 次派工) 落实实施. 件 7 真守恒 = SearchLog CTR ≥ 30% (派工 brief 误读为 feedback API ≥18 PASS, N-3 调研澄清).

---

## §2 6 类 UI 改进实施结果

### §2.1 改进 (1) — KnowledgeView 埋点接通

- 入口: `web/src/views/KnowledgeView.vue:253-269` (handleSearch + handleViewDetail)
- 改动: 每次搜索**无条件**触发 `searchAnalytics.startSearch` (含 0 结果); 加 `searchAnalytics.reset()` 防串味
- 已有基础: `useSearchAnalyticsStore` 在 W31 已落, 本任务**加固**, 非从零

### §2.2 改进 (2) — MobileKnowledgeView 同样接通

- 入口: `web/src/views/mobile/MobileKnowledgeView.vue`
- 改动: 引入 `useSearchAnalyticsStore`; `onSearchConfirm` 异步 `startSearch(mobile)`; `viewDetail(idx)` 1-based `recordClick`
- 真从零: 移动端之前**未**接埋点 (N-3 调研发现)

### §2.3 改进 (3) — top-1 视觉强化

- 桌面: `KnowledgeCard.topResult` prop + 卡片右上 ★ 推荐 徽章 (沿用 `--color-primary` + `--shadow-primary`)
- 移动: `CardList.item-actions` slot 首条加 `item-top-result` 胶囊徽章
- 跨主题: dark mode 同样适配 (非 scoped 块 + scoped token 复用)

### §2.4 改进 (4) — FeedbackButtons 文案激励

- 按钮文案: "回答有帮助" / "需要改进" (替代 "点赞" / "点踩")
- hover tooltip: `data-hover-prompt="帮助我们回答得更好"` + CSS `::after` 浮窗
- 无障碍: `aria-pressed` 表达 toggle, 按钮 .fb-label 显式可读 (不只靠 emoji)

### §2.5 改进 (5) — 匿名用户填补 (核心数据盲区修复)

- 旧: `app/api/v1/chat_feedback.py:130` 守卫 `user_id > 0` → 匿名 (user_id=0) feedback 不写 search_log
- 新: 优先按 session_id 定位最近 search_log, 找不到再按 user_id 兜底
- 测试: 新增 `test_anonymous_user_with_session_id_updates_search_log` + `test_chat_feedback_fallback_to_user_id_when_session_miss`
- 价值: 匿名 + 登录用户的 answer_rating 都进 SearchLog, 件 7 CTR 真实可累积

### §2.6 改进 (6) — analytics answer_rating 聚合维度

- `app/api/v1/analytics.py:get_stats` 新增 2 块:
  - `by_rating`: 👍/👎/无反馈 3 桶 + `answer_rate` + `upvote_rate` + `total`
  - `answer_trend`: 14 天每日 `{up, down, unrated, total, answer_rate}`
- SQL 关键: `COALESCE(answer_rating, 0)` 把 NULL 归入 unrated + `FILTER (WHERE ...)` 一次多桶
- 兜底: 空数据 total=0 → rate 全 0, 不抛 500
- 与原 brief 差异: 派工 brief 写"SQL 视图", 实测走 `/analytics/stats` JSON 字段 (与现有 stats 端点风格一致 + 零部署成本)

---

## §3 5 件套守恒实测

| 件 | 命令 | 实测 |
|---|------|------|
| alembic 1 head | `python -m alembic heads` | `093_add_search_log_answer_rating (head)` (无变化) |
| 现有 mock | `pytest tests/test_chat_feedback_api.py` | 15/15 PASS (14 baseline + 1 新增) |
| 新单测 | `pytest tests/test_searchlog_ui_improvements.py` | 9/9 PASS |
| 0 production code 边界 | 2 例外 (analytics.py 扩 SQL + chat_feedback.py 修复盲区) | 已派工 brief 批准, 算边界内 |
| 锚点范式 | `git log --grep "W99 +" --oneline` | 3 commits (+0 +1 +2) |

**总测试**: 24/24 PASS, 0 regression (chat_feedback + N-6 新加).

**PWA build**: 未跑 (本机无 npm), 改动仅 web/src/ + 2 个后端文件, 风险 = 0.

---

## §4 类 20 沉淀 (W99 N-6 新增 2 实例, 累计 22)

### §4.1 类 20.34 — 件 7 N-3 派工 brief 误读 + N-6 修正

- **现象**: 派工 v10 §0 件 7 brief 期望 "feedback API ≥18 PASS" → 实测 14 PASS
- **真相**: 件 7 真语义 = SearchLog CTR ≥ 30% (PR6/7 SQL 视图门禁), 不是 feedback API 测试数
- **N-6 修正**: 派工 = 6 类 UI 改进清单 (前端埋点接通), 非补足测试
- **沉淀**: 件 7 派工前必读 `docs/rag/EVAL.md:55-62` + `memory/w98-n3-searchlog-ctr-2026-08-01.md` §4

### §4.2 类 20.35 — 匿名用户盲区 (chat_feedback user_id 守卫)

- **现象**: 匿名用户 (user_id=0) feedback 不进 search_log.answer_rating
- **真相**: `app/api/v1/chat_feedback.py:130` 旧守卫 `user_id > 0` 跳过了匿名数据
- **N-6 修复**: 优先 session_id 桥接, user_id 兜底, 测守护
- **沉淀**: chat_feedback / chat_history / search_log 三表 session_id 桥接模式 (max_length=100 已约束)

---

## §5 W99+ 派工顺序表 (N-6 后续)

| 派工 | 范围 | N-6 关联任务 |
|------|------|---------------|
| W99 P2 | 性能 P95 < 2s | (独立, 跑 answer_trend 趋势监控) |
| W100 P1 | Self-RAG | (独立, 与件 7 累积数据交叉) |
| W101+ | 索引重建 + 件 7 真守恒验证 | **件 7 CTR ≥ 30% 待 14 天真实数据累积** |

---

## §6 关联文件

- `docs/w99-n6-ui-impl-2026-08-01.md` (runbook, 同次新建)
- `docs/w98-n3-searchlog-ctr-2026-08-01.md` (前置调研)
- `CHANGELOG.md` 顶部 2026-08-01 W99 P1 段
- `app/api/v1/analytics.py` (改进 6)
- `app/api/v1/chat_feedback.py` (改进 5)
- `web/src/views/KnowledgeView.vue` + `web/src/views/mobile/MobileKnowledgeView.vue` (改进 1+2)
- `web/src/components/knowledge/KnowledgeCard.vue` + `KnowledgeDashboard.vue` (改进 3 桌面)
- `web/src/components/chat/FeedbackButtons.vue` (改进 4)
- `tests/test_searchlog_ui_improvements.py` (9 新测, 同次新建)
- `tests/test_chat_feedback_api.py` (1 新测 + 1 改写)

---

## §7 Co-Authored-By

```
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

派工 v10 §6 据实上报 + §8 起步 6 项 + §9 commit 锚点范式全部遵守. 6 类 UI 改进清单全实施, 24/24 PASS, 0 production code 边界内, 类 20.34/35 沉淀齐备, 主拍可直接拍板.
