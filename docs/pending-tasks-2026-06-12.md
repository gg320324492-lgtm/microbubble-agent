# 待做清单 — 2026-06-12 v4 收官遗留

> 本文档记录 2026-06-12 v2/v3/v4 全栈重构后所有未完成项 / 部署后待办 / 后续优化方向。
> 维护人: @gg320324492-lgtm

---

## 🚨 部署后必做（阻塞 v4 真实落地）

### D1. 跑真实 LLM-as-judge baseline
**优先级**：🔴 最高
**依赖**：`docker compose restart app` + 真实 LLM API key

```bash
cd /opt/microbubble-agent
docker compose restart app
python scripts/run_llm_judge.py
# → 生成 data/quality_report.json + quality_report_baseline.json
# 验收阈值: avg_faithfulness ≥ 0.7 / avg_overall ≥ 4.0/5
```

**验收**：
- [ ] 报告文件存在
- [ ] 4 指标均值 ≥ 阈值
- [ ] baseline JSON 提交到 git

### D2. 跑真实 RAG 召回率评估
**优先级**：🔴 最高
**依赖**：`build_eval_ground_truth.py` 1h 人工标注

```bash
cd /opt/microbubble-agent
python scripts/build_eval_ground_truth.py  # 1h 人工筛
python scripts/run_rag_eval.py             # 5 种消融
# → 生成 data/rag_recall_report.json
# 验收阈值: recall@5 ≥ 0.8
```

**验收**：
- [ ] 20 问标注 IDs 修正为真实（替换占位 1-200）
- [ ] recall@5 ≥ 0.8
- [ ] 5 种消融对比有数据

### D3. 跑真实性能基线（perf 测试需 DB + LLM）
**优先级**：🟠 高
**依赖**：D1/D2 跑过的真实环境

```bash
cd /opt/microbubble-agent
SKIP_DB_SETUP=0 pytest tests/perf/ -v
# brief P95 < 3s / SSE < 1s / tool < 5ms
# 首次跑取实测 P95 + 30% buffer 作为基线
```

**验收**：
- [ ] 4 个 perf 测试文件全过
- [ ] 阈值在 conftest.py 调整
- [ ] 失败时给出明确诊断

---

## 🔧 代码层面未做（小优化）

### C1. core.py 兜底逻辑（虽清 794 行 if/elif，仍有冗余）
**现状**：`app/agent/core.py` 仍保留兼容壳（约 14 行），旧 `from app.agent.core import MicroBubbleAgent` 仍可工作。
**后续**：若确认无外部依赖，可删除 `core.py` / `tools.py` 整个文件，仅留 `micro_bubble_agent.py`。

### C2. agent_traces Celery 任务失败重试日志
**现状**：`persist_trace_task` max_retries=2，但失败时无结构化错误上报。
**后续**：加 `app/agent/tracing.py` 收集失败到独立 `agent_traces_errors` 表（可选）。

### C3. dispatch_legacy 兜底清理
**现状**：`app/agent/tool_registry.py:dispatch_legacy` 仍保留 fallback 到 `MicroBubbleAgent._execute_tool`。
**后续**：所有 34 工具确认走装饰器后，删除 dispatch_legacy。

### C4. 22 工具迁移后的真正删除
**现状**：core.py 20 个 elif 已删除（Day 24），但 `MicroBubbleAgent` 类（chat/chat_stream/clear_session）仍保留。
**后续**：v2 主类 `micro_bubble_agent.MicroBubbleAgent` 已切换，旧类可标记 `@deprecated` 后 1-2 月删除。

---

## 🎨 前端未做（UX 增强）

### F1. highlight.js 主题切换优化
**现状**：当前 dark mode 用 CSS 变量覆盖 `.hljs` 类，效果基础。
**后续**：
- 浅色：默认 `github.css`
- 深色：`atom-one-dark.css` 主题文件
- 用户偏好持久化（顶栏切换主题时同步切换 highlight 主题）

### F2. TTS 播放缓存
**现状**：`playTTS(text)` 每次都调后端，无缓存。
**后续**：用 IndexedDB / localStorage 缓存 `text → audio blob URL`，避免重复请求。

### F3. ASR 错误重试 + 静音检测
**现状**：`onRecordStop(blob)` 若 ASR 返回空文本只 toast 警告。
**后续**：
- 自动重试 1 次
- 静音检测（blob.size < 1KB → 提示"没听到声音"）

### F4. RichContent 卡片折叠/展开记忆
**现状**：每个 Rich Block 组件各自管理折叠状态（如 TranscriptBlock）。
**后续**：用户偏好（默认折叠/展开）持久化到 localStorage。

### F5. ChatViewSSE 拆组件
**现状**：`ChatViewSSE.vue` 仍 ~400 行（拆后比原 565 行小，但仍有 input/messages/voice 三关注）。
**后续**：拆为 `ChatContainer.vue` + `MessageList.vue` + `InputBar.vue` + `VoicePanel.vue`。

---

## 📊 评估体系未做

### E1. 标注集 50 问扩展
**现状**：20 问覆盖微纳米气泡基础。
**后续**：扩到 50 问（覆盖：项目/会议/任务/成员/假设/公式 6 域 × 各 5-10 问）。

### E2. LLM-as-judge baseline CI 接入
**现状**：`scripts/run_llm_judge.py` 跑通但无 CI 自动跑。
**后续**：
- GitHub Actions 跑评估（每 PR 触发）
- 失败时 `assert avg_overall >= baseline * 0.9`
- 防止质量回归

### E3. RAG 检索消融矩阵完整化
**现状**：`scripts/run_rag_eval.py` 跑 5 种消融（all_paths / vector_only / bm25_only / no_graph / no_rerank）。
**后续**：补全 16 种消融（2^4 = 16 种 enable_* 组合），更细粒度找最佳配置。

### E4. Per-query 错误分析
**现状**：`quality_report.json` 有 details 但无错误分类。
**后续**：自动分析每问失败原因（context 不相关？答案不忠实？query 不清晰？），输出改进建议。

---

## 🏗️ 部署 / 运维未做

### O1. Alembic 迁移 agent_traces 表
**现状**：`agent_traces` 表通过 `Base.metadata.create_all()` 自动创建（无需 alembic 干预）。
**后续**：若启用 alembic，加 `alembic/versions/xxx_add_agent_traces.py` 迁移。

### O2. agent_traces 表清理策略
**现状**：表会无限增长。
**后续**：加 Celery beat 每日清理 30 天前 trace（与 reminder 任务同模式）：
```python
# app/services/agent_trace_tasks.py
@celery_app.task(name="purge_old_traces")
def purge_old_traces(days=30):
    """清理 30 天前 trace 防止表爆炸"""
```

### O3. Trace 失败告警（Slack/微信）
**现状**：trace 写入失败时只 logger.warning。
**后续**：3 次重试仍失败时，发 Slack/微信告警到 admin。

### O4. perf 基线波动监控
**现状**：`tests/perf/` 阈值固定。
**后续**：
- 每天跑一次 perf（GitHub Actions cron）
- 记录 P50/P95/P99 到 `data/perf_history.jsonl`
- 超过历史均值 +30% 告警

### O5. Webhook 部署脚本优化
**现状**：deploy-auto.sh 不重启 Python 后端（MEMORY 教训）。
**后续**：在脚本中加 `docker compose restart app`（避免手动）。

---

## 🧪 测试未做

### T1. 前端 Rich Block 组件测试
**现状**：73 个前端测试，Rich Block 组件测试仅 5 个（chatSSE.spec.js）。
**后续**：补 10 个 Rich Block 组件的 snapshot + 交互测试。

### T2. Playwright 端到端测试
**现状**：0 个 Playwright 测试。
**后续**：
- `web/tests/e2e/chat.spec.ts` — Playwright 走完整 10 问冒烟
- 跑 `npm run test:e2e`（新增脚本）

### T3. 性能测试扩展
**现状**：6 个 perf 测试（brief/SSE/tool）。
**后续**：
- `test_concurrent_chat.py` — 10 并发 chat P95 < 5s
- `test_long_conversation.py` — 50 轮上下文窗口
- `test_rag_recall.py` — 集成 RAG 召回率（≥ 80%）

### T4. 视觉回归测试
**现状**：0 个快照测试。
**后续**：用 Percy / Playwright snapshot 验证 Rich Block 样式不回归。

### T5. 安全测试
**现状**：0 个安全测试。
**后续**：
- 限流（30次/分/user）— `tests/security/test_rate_limit.py`
- 越权（普通用户访问 `/admin/agent-traces` 403）— `tests/security/test_permissions.py`
- SQL 注入（search_knowledge 输入 `' OR 1=1 --`）— `tests/security/test_injection.py`

---

## 📚 文档未做

### D4. API 文档自动生成
**现状**：OpenAPI 自动生成但无中文注释。
**后续**：在 `app/api/v1/*.py` 加 `description=` 参数，Swagger UI 显示中文。

### D5. 架构图（draw.io / Mermaid）
**现状**：文字描述，无图。
**后续**：
- `docs/architecture.mmd` — Mermaid 图（chat 流 / 工具调度 / Trace 持久化）
- 嵌入 README

### D6. 用户手册
**现状**：无用户向文档。
**后续**：`docs/user-guide.md` — 小气助手怎么用、哪些场景、FAQ。

### D7. 开发者 onboarding
**现状**：`CLAUDE.md` 项目上下文较简。
**后续**：`docs/dev-onboarding.md` — 怎么加新工具、怎么加新 Rich Block、怎么跑测试。

---

## 🔮 长期 roadmap（不紧急）

### R1. 多模态 Agent
**目标**：支持图片/视频/音频直接进 Agent（当前只支持图片+文字）。
**关键改动**：
- 加 `web/src/components/chat/MediaUploader.vue`
- 后端 `app/agent/micro_bubble_agent.py` 多模态消息处理
- 工具 `analyze_image` / `transcribe_video`

### R2. 主动 Agent（Proactive Agent）
**目标**：小气助手主动给用户推送（如"今天有 2 个任务到期"），不需用户问。
**关键改动**：
- Celery beat 每日 9:00 扫描到期任务
- 微信通知 + Agent 生成简短的"今日提醒"

### R3. 多 Agent 协同
**目标**：任务 Agent / 研究 Agent / 写作 Agent 分工协作。
**关键改动**：
- LangGraph 或自研 DAG
- Agent 间共享 message bus

### R4. Web 端可视化工作流
**目标**：用户能看到 Agent 思考过程的 DAG 视图（不仅是 tool_trace 列表）。
**关键改动**：
- 前端 ECharts DAG 可视化
- 后端 `AgentTrace` 增 `parent_trace_id` 字段

### R5. RAG 增强：HyDE / Multi-hop / Re-ranking
**目标**：recall@5 从 0.8 → 0.95。
**关键改动**：
- HyDE（假设性文档嵌入）—— query → LLM 生成假设答案 → embedding → 检索
- Multi-hop：图谱 2-3 跳遍历（已实现，但未默认开）
- Re-ranking：cross-encoder 模型精排

---

## 进度跟踪

| 类别 | 总数 | 已完成 | 进行中 | 待做 |
|---|---|---|---|---|
| 部署后必做 | 3 | 0 | 0 | 3 |
| 代码层未做 | 4 | 0 | 0 | 4 |
| 前端 UX | 5 | 0 | 0 | 5 |
| 评估体系 | 4 | 0 | 0 | 4 |
| 部署运维 | 5 | 0 | 0 | 5 |
| 测试 | 5 | 0 | 0 | 5 |
| 文档 | 4 | 0 | 0 | 4 |
| 长期 roadmap | 5 | 0 | 0 | 5 |
| **合计** | **35** | **0** | **0** | **35** |

## 复盘

### 2026-06-12 v4 全栈重构完成情况
- ✅ 后端 Agent 架构重构（v2）
- ✅ 多会话 + dark mode + 12 类 Rich Block + agent_traces（v3）
- ✅ 34 工具 @tool 装饰器 + ASR 语音 + 代码高亮（v4 主体）
- ✅ 性能基线 + LLM-as-judge 评估体系 + 20 问标注
- ✅ core.py 清理（1469 → 689 行，-53%）
- ✅ 87 后端 + 73 前端 = **160 测试全过**
- ✅ 17 commits 推送

### 仍待部署后验证
- 真实 LLM-as-judge baseline（需 DB + LLM）
- 真实 RAG 召回率（需 DB + 人工标真实 ID）
- 真实性能基线（需 DB）

### 不阻塞但建议未来做
- 前端拆组件（F5）
- Alembic 迁移（O1）
- Playwright e2e（T2）
- 架构图 + 用户手册（D5/D6）
