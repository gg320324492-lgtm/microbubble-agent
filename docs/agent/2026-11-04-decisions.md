# 2026-11-04 决策留档（主指挥弹框拍板）

三条决策及其落地状态。本文只记「当时定了什么、为什么、怎么验」，
不复制实现细节（代码与测试里都有）。

## 一、fast 模式按需放行工具循环 → 已实现

**先纠正一个流传中的错误归因**：此前待办清单写的是
「`agentic_loop.py:930` 对 recommend_person / data_query / execute_action /
casual_chat 跳过 Phase 1」——**这句话是错的**。

| 位置 | 实际是什么 |
|---|---|
| `agentic_loop.py` 的 Phase 0 白名单（旧 930 行） | `AGENT_PLAN_STEP_ENABLED` 控制的**强制预派工具**白名单（SEARCH_INFO / EXPLAIN_CONCEPT / TEAM_OVERVIEW），而且 `skip_plan_step=True` 时这一整段**根本不执行** |
| `thinking_config.resolve_thinking_config("fast")` | `max_tool_rounds=0` |
| `agentic_loop.run()` 里 `min(max_rounds, cfg.max_tool_rounds)` | 真凶：把**所有意图**的 Phase 1 工具循环钳成 0 轮 |

⇒ fast 模式不是「四类意图没工具」，是**任何意图都没有工具**，
只能凭对话历史答，于是「查一下 X」会答「暂未找到」或直接编。
改 Phase 0 白名单既不生效，还会拆掉当年「闲聊不误调」的保护。

**落地**（主指挥选「先做 fast 模式」）：
- 新增 `AGENT_FAST_TOOL_ROUNDS_FOR_DATA_INTENTS`（默认 **2**，设 0 = 完全回退）；
- 只在 `agentic_loop.run()` 里，当 `mode == fast` 且原值 `== 0` 且意图属于
  **只读**集合 `{DATA_QUERY, RECOMMEND_PERSON, SEARCH_INFO}` 时抬到 2 轮；
- **刻意不放行 `EXECUTE_ACTION`**：fast 原本从没有写库能力，放行等于悄悄
  新增一条写路径，超出「让答案有数据」的范围；
- `CASUAL_CHAT / FOLLOW_UP / EXPLAIN_CONCEPT / TEAM_OVERVIEW` 保持 0 轮 ⇒
  保住「闲聊不误调」与 fast 的「快」（2 轮 << balanced 的 5 轮）；
- `ThinkingConfig` frozen dataclass **未改**，balanced / deep 行为零变化。

**验证**：
- `tests/test_fast_mode_tool_rounds.py` **20 passed / 1 skipped**（真值表 8 意图 ×
  fast/balanced/deep、flag=0 回退、上限钳制、3 条 AST 结构守卫）；
  既有的 `test_silly_gliding_dahl_implementation.py` 未打红；
- 确定性副作用探针（`data/tmp/verify_fast_tools.py`）：数 Phase 1 的
  `llm.complete` 调用次数 —— 三个只读意图 ≥1、其余 5 类与 flag=0 全部 0，
  balanced/deep 任何意图都 ≥1；
- 真实 `/chat` 冒烟：fast 下数据查询与闲聊都 HTTP 200 且有内容，
  数据查询那条**返回了带成员档案的答案**（工具确实被调了）。

⚠️ 判据选型的教训：首版探针数 `tool_use` 事件，结果因 mock 环境工具执行
缺 db 而全 0，差点得出「没生效」的错误结论。真正区分 `range(0)` 与
`range(2)` 的确定性副作用是**循环体有没有调 `llm.complete`**（类 20.220）。

## 二、前端「重新排版 / 重新润色」→ **保留，补文档**（代码一行未改）

主指挥选择保留。核实过的现状：

- 前端 `web/src/views/KnowledgeDetailView.vue:643` 在
  `formatted_content` 为空时后台异步 `POST /api/v1/knowledge/{id}/reformat`，
  且 `.catch(() => {})` —— 失败不影响页面，是 best-effort 增益；
- 后端 `app/api/v1/knowledge.py:1136` 的 `reformat_knowledge` 调
  `KnowledgeService.reformat_content`；
- 换 M3.1-Flash **不构成下线理由**：排版是把已有内容结构化（标题/段落/
  表格），不是生成新知识，模型变强不降低它的价值；且它是「没有 formatted
  _content 时才触发」的一次性动作，不是每轮对话的开销。

⚠️ **别把两个开关混为一谈**（曾差点写错）：
- `ENABLE_AI_POLISH`（`app/config.py`，`meeting_ai_polish.py` 消费）管的是
  **会议转录润色**，与知识库排版无关；
- `MEETING_AI_POLISH_ENABLED=False` 是 2026-10-09 实测「68 批耗时 50–60min
  而产物 100% 被回退」后关掉的，不是这次讨论的功能。

⇒ 结论：保留现状，不删入口、不改前端、不重建 `web/dist`。
若将来要下线，属用户可见改动，需单独拍板 + W100 确定性构建。

## 三、`memories` 存量 30 行微信时代记忆 → **不接进召回**（代码一行未改）

主指挥选择不接。事实：

- 30 行全是 2026-05-19~22 的 `entity`(21) / `preference`(9)，
  `source_session` 全为 `wechat_wwd…` —— 企业微信 **2026-09-12 已整体下线**；
- C 档 `recall_memories` 固定查 `memory_type='episode'`，这些行**根本不会被读到**；
- 白名单灰度只对 `user_id=3` 生效，`user_id` 过滤是第二层隔离。

理由：这些是**一年多前、由已下线链路提取**的姓名/方向/偏好，没有复核过。
把它们接进召回 = 把可能过时的断言注入 system，而 `prompts.py:381` 虽然要求
模型「只作参考、必须重新验证」，但那只是软约束，不值得为 30 行未审数据
增加一条幻觉通道（类 20.243 的「锚池质心可能是污染的」同型）。

⇒ 保持不读取。**若将来要接**：先逐行审内容是否过时、确认 `user_id` 归属，
再单独加 `memory_type` 过滤开关 + 回归测试，不在 C 档范围里顺手做。

## 本次未开工（保持不变）

- 真嵌入模型重跑 `backfill_late_embedding.py`（当前是 `MockForward(np.ones)`，
  178 行假向量；全量重嵌 12082 chunks，属独立立项）；
- P2 四项（HNSW >10 万行触发 / 嵌入模型换代 / HyDE 第六臂 / contextual retrieval）；
- image-scan 红：等 trivy 官方修 `get.trivy.dev` 不解析；
- 两个 `web/design-showcase/` 未跟踪目录按约束未提交、未改动。
