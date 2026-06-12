# 小气助手 v2/v3 部署文档（2026-06-12 全栈重构）

## 概述

Day 1-8 (v2) 核心架构重构：把 `app/agent/core.py` (1469 行单文件) 拆为 7 个职责清晰的文件，前端 `ChatView.vue` (565 行) 替换为 `ChatViewSSE.vue` (~350 行)，接入真实 SSE 流式 + Rich Block 富文本渲染。

Day 9-14 (v3) 全栈深化：
- 9 个新工具（get_meeting_detail/transcript/member_profile/project_summary/list_formulas/list_hypotheses + 3 个项目域）
- 6 个旧工具迁到 @tool 装饰器（create_task/update_task/search_knowledge/save_memory/search_memory/web_search）
- 5 个新 Rich Block 组件（FormulaBlock/HypothesisBlock/ProjectSummaryBlock/TranscriptBlock/ChartBlock）
- 多会话侧栏（Pinia + IndexedDB 持久化）
- dark mode（CSS 变量化 + 顶栏 toggle）
- agent_traces 可观测性闭环（Celery 持久化 + /admin 端点 + 管理页）

## 部署步骤

### 1. 拉取代码（自动部署已配置 webhook）

```bash
cd /opt/microbubble-agent
git pull
# webhook 会自动触发：npm run build + nginx reload
```

如果 webhook 失败，手动触发：
```bash
cd /opt/microbubble-agent
git pull
cd web && npm run build && git add -f web/dist/ && cd ..
# （commit 已由 push 自动包含 dist）
nginx -s reload
```

### 2. 重启 Python 后端

```bash
# MEMORY 教训：deploy-auto.sh 不重启 Python 后端
# 改 Python 代码后必须手动 docker compose restart
cd /opt/microbubble-agent
docker compose restart app
# 或
docker compose restart celery-worker celery-beat
```

### 3. 验证部署

```bash
# 1. 验证 API 路由
curl -s http://localhost:8000/api/v1/openapi.json | python -c "
import json, sys
d = json.load(sys.stdin)
paths = list(d['paths'].keys())
for p in ['/chat', '/chat/stream', '/chat/image', '/chat/file', '/ws/chat/{user_id}']:
    assert p in paths, f'缺少端点 {p}'
print('✓ 所有 chat 端点已挂载')"

# 2. 验证 SSE 端点
curl -s -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message":"hi","session_id":"deploy_test"}' | head -3

# 3. 验证前端新版本
curl -s http://localhost/ | grep -E 'index-[a-f0-9]+\.js' | head -1
# 应看到新的 hash 文件
```

### 4. 回滚（如出现问题）

**回滚前端到旧版 ChatView.vue**：
```bash
# 编辑 web/src/router/index.js
sed -i "s|@/views/chat/ChatViewSSE.vue|@/views/ChatView.vue|g" web/src/router/index.js
cd web && npm run build
cd .. && git add -f web/dist/ && git commit -m "rollback: restore legacy ChatView"
git push
nginx -s reload
```

**回滚后端到旧版 core.py**：
```bash
# 编辑 app/api/v1/chat.py
sed -i "s|from app.agent.micro_bubble_agent import agent as v2_agent|from app.agent.core import agent as v2_agent|g" app/api/v1/chat.py
docker compose restart app
```

## 架构变化对比

| 维度 | v1 (旧) | v2 (新) |
|---|---|---|
| 后端 Agent 文件 | 1 个 1469 行 | 7 个文件，每个 < 350 行 |
| 工具调度 | 25 个 if/elif | `@tool` 装饰器 + 注册表 + Pydantic 校验 |
| 前端聊天窗口 | 1 个 565 行 | ChatViewSSE.vue ~350 行 + 5 个 Rich Block 组件 |
| 流式 | 伪流式（2s 轮询换全文） | 真实 SSE（`/chat/stream`） |
| 响应结构 | 纯 markdown 文本 | markdown + rich_blocks + tool_trace + usage + duration_ms |
| 工具调用过程 | 不可见 | "🔍 正在查询任务..." / "✓ 100ms" |
| 富文本渲染 | 无 | 会议卡 / 任务列表 / 知识引用 / 成员卡 |

## 兼容性保证

- **后端**：`app/agent/core.py` 保留（旧 26 个 if/elif 工具仍可工作）
- **后端**：`app/agent/tools.py` 文件已删除（Python 优先选 `tools/` 包），但 `from app.agent.tools import TOOLS` 在 `tools/__init__.py` 有 shim，**旧 core.py 仍能 import**
- **前端**：`web/src/views/ChatView.vue` 保留在原位（`router/index.js` 单点切换）
- **API 字段**：`ChatResponse` 加 4 字段（rich_blocks / tool_trace / usage / duration_ms），旧 6 字段不变，前端向后兼容

## 自检命令

```bash
# 后端测试（84 个全过）
cd /opt/microbubble-agent
SKIP_DB_SETUP=1 python -m pytest tests/unit/test_agent_v2_core.py tests/unit/test_agent_v2_main.py tests/unit/test_v2_tools.py tests/integration/test_chat_v2_e2e.py -v

# 前端测试（73 个全过，含 14 个 v2 测试）
cd web
npm run test:unit

# 前端构建（无警告，主 bundle 198.68 kB gzip 76.17 kB）
npm run build
```

## 监控

### Trace 日志

每次 chat 后 `app/agent/tracing.py` 输出结构化日志到 `microbubble.agent.tracing` logger：
```json
{"event":"AgentTrace","user_id":1,"session_id":"user_123",
 "tool_count":2,"rich_block_count":1,
 "tool_names":["query_meetings","get_meeting_detail"],
 "rich_block_types":["meeting"],
 "total_duration_ms":3200,
 "usage":{"input_tokens":1500,"output_tokens":800,"total_tokens":2300}}
```

可用 `grep AgentTrace /var/log/microbubble/app.log` 观察。

### 手动冒烟（10 个真实问句）

1. ✅ "我最近有什么任务？" → `query_tasks` → task_list 卡
2. ✅ "上周的会议结论是什么？" → `get_recent_meeting_conclusions` → meeting 卡（按日期分组）
3. ✅ "项目 zeta 研究的进度如何？" → `get_project_summary` → project 卡
4. ✅ "zeta 电位是什么？" → `search_knowledge` → knowledge_ref 卡
5. ✅ "实验室有哪些研究假设？" → `list_hypotheses` → hypothesis 卡
6. ✅ "查一下微纳米气泡的生成方法" → `search_knowledge` → knowledge_ref 卡
7. ✅ "贾琦的联系方式" → `query_members` → member 卡
8. ✅ "5月28日例会的转录给我看" → `get_meeting_transcript` → transcript 卡
9. ✅ "创建一个新任务：周五前完成XX" → `create_task` → 成功 toast
10. ✅ "XX 会议没有总结，帮我生成" → `analyze_meeting_transcript` → meeting 卡

## 已知限制

- **未迁移 22 个工具**：仍走 `dispatch_legacy` 回退（保留旧 core.py 兼容），后续可逐步迁移
- **未做**：多会话侧栏 / dark mode / 语音输入完整链路 / 代码高亮 / LLM-as-judge
- **性能**：单次 chat brief < 3s, detail < 30s（与旧版持平）

## 关键文件

- 后端核心：`app/agent/{protocol,tool_registry,llm,session_manager,tracing,chat_engine,micro_bubble_agent}.py`
- 工具：`app/agent/tools/{meeting,task,member}_tools.py`
- API：`app/api/v1/chat.py`
- 前端：`web/src/views/chat/ChatViewSSE.vue` + `web/src/components/chat/`
- 测试：`tests/{unit,integration}/test_{agent_v2,v2_tools,chat_v2_e2e}*.py`
- 前端测试：`web/src/__tests__/chatSSE.spec.js`

## 提交记录

| Commit | 内容 | 阶段 |
|---|---|---|
| `8fff43a` | refactor(agent): 拆 core.py 基础设施 | Day 1 |
| `3e81e82` | feat(agent): ChatEngine 双层回复引擎 + v2 主类 | Day 2 |
| `371a4fc` | feat(agent): 迁移 3 工具 + 2 新工具 | Day 3 |
| `1eb9fce` | feat(api): ChatResponse 扩 4 字段 + /chat/stream SSE | Day 4 |
| `2f62d51` | feat(chat): 前端 SSE + 4 Rich Block 组件 | Day 5-6 |
| `463d30b` | feat(agent): 兼容 shim + 18 E2E 集成测试 + 部署文档 | Day 7-8 |
| `c3c139a` | feat(agent): 9 v2 工具 + 6 迁移 + 删 tools.py | Day 9-10 |
| `736a17c` | feat(chat): 5 Rich Block 组件 + 动画 + 网络感知 | Day 11-12 |
| `0737a44` | feat(chat): 多会话侧栏 + dark mode + Pinia | Day 13 |
| `8c65944` | feat(observability): agent_traces 可观测性闭环 | Day 14 |

---

## v3 部署补充（2026-06-12 Day 9-14 增量）

### 新增数据库表：`agent_traces`

Celery 任务 `app.services.agent_trace_tasks.persist_trace_task` 写这张表。重启后端时会自动 `Base.metadata.create_all` 创建，**无需手动迁移**（如 alembic 启用了可能需 alembic upgrade head 一次）。

```sql
-- 自动创建（无 alembic 干预场景）
CREATE TABLE agent_traces (
    id BIGSERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES members(id),
    session_id VARCHAR(64) NOT NULL,
    message TEXT NOT NULL,
    tool_calls JSON DEFAULT '[]',
    rich_blocks JSON DEFAULT '[]',
    brief TEXT,
    detail TEXT,
    input_tokens INT, output_tokens INT, total_tokens INT,
    total_duration_ms INT,
    error TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_traces_user_created ON agent_traces(user_id, created_at);
```

### 新增 API 端点

```
GET  /api/v1/admin/agent-traces       # admin 监控列表（需 admin/leader 权限）
GET  /api/v1/admin/agent-traces/{id}  # 单条详情
```

### 新增 Celery 任务

`app.services.agent_trace_tasks.persist_trace_task` — 每次 chat 后异步写 agent_traces 表。已在 `app/core/celery.py` 注册。**重启 celery worker + beat** 即可生效：

```bash
docker compose restart celery-worker celery-beat
```

### 新增前端路由

- `/admin/agent-traces` — Agent Trace 监控页（表格 + 详情抽屉）
- `/chat` — 路由指向 `ChatViewSSE.vue`（含侧栏 + dark mode + 网络感知）

### 19 个新调度工具（@tool 装饰器）

```
任务: create_task / query_tasks / update_task
会议: query_meetings / get_meeting_detail / get_meeting_transcript / get_recent_meeting_conclusions
项目: query_projects / get_project_summary / generate_project_plan
成员: query_members / get_member_profile
知识: search_knowledge
公式: list_formulas
假设: list_hypotheses
记忆: save_memory / search_memory / forget_memory
搜索: web_search
```

剩 14 个走 `dispatch_legacy` 回退（admin only 或低频）：query_all_member_tasks / get_task_stats / create_meeting / analyze_meeting_transcript / summarize_meeting_transcript / explore_knowledge_graph / find_knowledge_gaps / auto_research / compare_knowledge / summarize_topic / suggest_research / save_conversation_knowledge / set_custom_instructions / enroll_voice / submit_feedback

### 12 类 Rich Block 组件

```
meeting / task_list / knowledge_ref / member          # Day 1-8
formula / hypothesis / project / transcript / chart   # Day 11-12
table (未实现) / fallback                            # 兜底
```

### 多会话侧栏

Pinia store `web/src/stores/chatSessions.ts` 自动持久化到 localStorage：
- 240px 折叠侧栏（顶栏 ☰ 切换）
- 标题自动取首条 user 消息前 30 字
- 兼容 v1 单会话（migrateFromV1）

### dark mode

`web/src/assets/variables.css` 加 `[data-theme="dark"]` 变量块 + 顶栏 🌙/☀️ toggle，localStorage 持久化。

### 监控闭环

1. chat() 完成后 TraceCollector 自动收集 tool_calls / rich_blocks / token / duration
2. 异步通过 Celery `persist_trace_task.delay(dict)` 写 agent_traces 表
3. admin 打开 `/admin/agent-traces` 实时查看
4. Celery 失败时降级到 logger（不阻塞 chat）

