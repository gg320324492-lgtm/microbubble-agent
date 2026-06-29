# 方案 C Stage 5 收尾 — Runbook（用户必须手动跑的 5 项）

> 本文档列方案 C 收尾后**必须**手动验证的 5 项。本地开发环境无法模拟，需在生产服务器/真实 LLM/真实 PG 上执行。
> 执行完后请在 issue / commit message 里勾选 ✅。

## 1. 🚨 数据库迁移（agent_traces 加 7 列）

**背景**：Stage 3 改了 `app/models/agent_trace.py` 加 7 列（intent_category / intent_confidence / tool_rounds_used / compression_applied_count / critique_score / retry_count / status）。SQL 脚本在 `scripts/alter_agent_traces_stage3.sql`，deploy-auto.sh 已集成自动跑，但首次部署需要手动验证。

**执行**：
```bash
# 1. SSH 到云服务器
ssh agent@agent.mnb-lab.cn

# 2. 手动跑迁移（如果 deploy-auto.sh 没自动跑）
cd /opt/microbubble-agent
git pull
docker exec -i microbubble-agent-postgres-1 psql -U postgres -d microbubble < scripts/alter_agent_traces_stage3.sql

# 3. 验证 7 列已添加
docker exec -it microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "
  SELECT column_name, data_type FROM information_schema.columns
  WHERE table_name = 'agent_traces' AND column_name IN
    ('intent_category','intent_confidence','tool_rounds_used',
     'compression_applied_count','critique_score','retry_count','status')
  ORDER BY column_name;
"

# 期望输出：7 行
```

**回滚**：所有列 `ADD COLUMN IF NOT EXISTS`，重复执行幂等。回滚用 `ALTER TABLE agent_traces DROP COLUMN IF EXISTS <col>;`（一般不需要）

## 2. 🚨 Docker 容器重启（CLAUDE.md 752 行铁律）

**背景**：后端所有改动（chat_engine.py 重写 / tracing.py async context / 4 个新模块 / agentic_loop rich_block 提取）都是 Python 模块改动。Docker volume 挂载只换文件**不重启进程**——Python 进程仍在用旧模块缓存。

**执行**：
```bash
ssh agent@agent.mnb-lab.cn
cd /opt/microbubble-agent

# 重启后端服务（CLAUDE.md 752 铁律）
docker compose restart app celery-worker celery-beat

# 验证：新进程加载了 4 个新模块
docker exec microbubble-agent-app-1 python -c "
from app.agent.intent_classifier import classify_intent
from app.agent.result_compressor import compress_tool_result
from app.agent.critic import critique_response
from app.agent.agentic_loop import AgenticLoop
from app.agent.chat_engine import ChatEngine
print('All 5 modules importable (post-restart)')
"
```

**期望输出**：`All 5 modules importable (post-restart)`。如果不报 `ModuleNotFoundError` 即 OK。

## 3. 🧪 真实 LLM 端到端测试（问"请教谁"）

**背景**：本机 304 个测试全部 mock LLM（`AsyncMock`），没做过真实 Anthropic API 调用。Sonnet 4.6 / Haiku 4.5 真实返回未知。

**前置**：`.env` 含 `CLAUDE_API_KEY` + `CLAUDE_BASE_URL`（代理）。

**执行**：
```bash
ssh agent@agent.mnb-lab.cn

# 1. 浏览器打开
# https://agent.mnb-lab.cn/chat

# 2. 登录后问 3 个真实问题（验证方案 C 实际效果）
```

**3 个必问问题**：

| 问题 | 期望效果 |
|------|----------|
| 「我想学习饮用水相关内容，可以请教谁？」 | 工具调 query_members → Haiku 压缩 27→3 → 主答案推荐 3 人 + 理由 + Rich Block 折叠「👥 推荐 3 人（27→3）」+ 自评 ≥ 7 |
| 「最近有什么会议可以学习？」 | 工具调 query_meetings → 筛 top 3 → 推荐 + Rich Block 折叠「📅 会议 3 场」 |
| 「微纳米气泡的 zeta 电位是多少？」 | 工具调 search_knowledge → 压缩 → 直接回答 + 引用 1-2 条知识，不堆 10 条 |

**逐个验证**：
- [ ] 折叠后默认显示一行摘要（点击展开看完整内容）
- [ ] 思考过程可折叠（点 ✓ 行展开看 intent / plan / tools / critique）
- [ ] 评分 ≥ 7 正常显示
- [ ] 评分 < 7 显示 ⚠️ 警告

## 4. 🧪 流式中断测试（点 ⏹ 立即停止）

**前置**：问题 3 验证通过后做。

**执行**：
```bash
# 浏览器开 https://agent.mnb-lab.cn/chat
# 1. 问 "最近有什么会议可以学习？"
# 2. 流式生成过程中，点 ⏹ 按钮（红色停止按钮）
# 3. 期望：立即停止，UI 显示 "⏹ 已中断"
# 4. 等待 5 秒
# 5. 检查 admin 面板是否立即看到 status=aborted 记录
```

**验证**：
```bash
# 5 秒后查 admin 面板的 abort 记录
docker exec -it microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "
  SELECT id, status, message, created_at FROM agent_traces
  WHERE status = 'aborted' AND created_at > NOW() - INTERVAL '1 hour'
  ORDER BY created_at DESC LIMIT 3;
"
# 期望：至少 1 行（证明铁律 4 同步落库生效）
```

如果没看到 abort 记录 → 同步落库没工作，**回滚路径（2026-06-29 更新）**：
```bash
# 方案 C 30 天回滚窗口已于 2026-06-29 提前结束
# AGENT_NEW_ARCHITECTURE_ENABLED flag 已删除，不能再切到 chat_engine_legacy
# 真回滚路径: git revert <chat_engine_legacy 删除 commit> + 重新部署
git revert <commit-hash> && git push origin main
# 或: 部署上一个 stable 版本的 dist 镜像
# 回滚预期时间: < 5 分钟 (revert + push + webhook 触发 deploy)
```

## 5. 🧪 Playwright 视觉回归测试（可选，5 个 viewport × 2 状态）

**背景**：Stage 4 plan 提到 5 viewport × 2 状态 = 10 个新截图基线（流式中 / 流完成折叠态）。本地无 Playwright 浏览器环境，本地不能跑。

**前置**：
```bash
# 服务器上装 Playwright
cd /opt/microbubble-agent/web
npm install -D @playwright/test
npx playwright install --with-deps chromium
```

**执行**（需在 chat-screenshot.spec.mjs 加用例后）：
```bash
# 启动 dev server
npm run dev &

# 跑视觉回归（5 viewport × 2 状态）
npx playwright test --project=chromium

# 对比基线截图：web/tests/visual/baselines/
```

**期望**：10 个新基线截图通过（不通过 = UI 改动未 commit）

**注意**：本机跑不通没关系，先 commit 代码 + 截图基线到 git，让 CI 跑。
