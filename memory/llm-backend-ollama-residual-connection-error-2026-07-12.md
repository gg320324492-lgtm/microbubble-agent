---
name: llm-backend-ollama-residual-connection-error-2026-07-12
description: "P0-#1 修复 — `.env` 残留 LLM_BACKEND=ollama (2026-07-02 Ollama 本地测试未回滚) 导致云端 chat 全 Connection error; 改回 openai_compat + curl 验证 SSE 正常流 text_delta; 浮出副 bug intent_classifier 'dict' object has no attribute 'content' (后续)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 987866fd-9014-4a38-b9fe-7f536684352d
---

**触发 (2026-07-12)**: 用户报告连续两条"你好"消息 UI 都显示 "⚠️ Connection error." (2.9s/2.6s 耗时)。

**根因 (3 层)**:
1. `.env` 第 86 行 `LLM_BACKEND=ollama` + `OLLAMA_BASE_URL=http://host.docker.internal:11434/v1` — 2026-07-02 Ollama 本地测试残留, **从未回滚到生产 openai_compat** (CLAUDE.md 2026-07-02 决策: "生产保持 openai_compat, 8b 作 offline fallback")
2. **本地 PC Ollama 未在跑** (WinError 10061 connection refused; container 视角 host.docker.internal:11434 也连不上)
3. 每次 chat → intent_classifier + agentic_loop + synthesize_stream 3 处都调 LLM → OpenAI SDK `APIConnectionError` → `str(e) == 'Connection error.'` (OpenAI SDK 1.x 和 anthropic SDK 0.39+ 的 str 都是这个值, 区分不了)

**排查路径 (sseFetch 渲染链路)**:
- 前端 `useChatStream.ts:411 catch (e)` → `targetAssistant.error = e.message || '发送失败'` → `<div v-if="msg.error">⚠️ {{ msg.error }}</div>` 渲染 (ChatViewSSE.vue:456)
- 前端 sse.ts 自身抛的错只有 `HTTP XXX: text` 和 `响应无 body`, 都不是 "Connection error."
- **所以 "Connection error." 必然来自服务端** = 后端 `v2_agent.chat_stream` yiled `type=error` 事件, message 由后端填
- `curl -N POST /api/v1/chat/stream` 实测返 3 个 error + reasoning "intent classification failed: Connection error." → 锁定 LLM 调不通

**修复 (commit 待 push)**:
1. `.env` 改 `LLM_BACKEND=ollama` → `LLM_BACKEND=openai_compat` (保留 OLLAMA_* 作 offline fallback)
2. ⚠️ **docker compose `restart` 不重读 env_file** — 这是关键陷阱, 必须 `docker compose up -d --force-recreate app celery-worker` 才能让 LLM_BACKEND 切换生效
3. `printenv` 验证容器中 `LLM_BACKEND=openai_compat` 后 curl SSE 看到 `text_delta: "你好！很高兴收到你的消息 🙋‍♂️..."` ✅

**端到端验证**:
- curl /api/v1/chat/stream → 不再返 error 事件 → 正常 text_delta 流 → SSE [DONE]
- 前端 UI 同一会话多次"你好"应当不再 Connection error

**Why**:
1. **`.env` 不在 git 里 (gitignored), 改完一定要 docker compose up -d --force-recreate 才能让 env_file 重读** — restart 只重启 container 用已缓存的 env, 大坑 (CLAUDE.md 752 行已存铁律 4 "docker compose restart 不重读 env_file", 但用户/我今天再次验证: 还是踩了)
2. **OpenAI SDK 1.x 和 anthropic SDK 0.39+ 的 APIConnectionError str 都是 'Connection error.'** — 仅看 `e.message` 没法区分是 anthropic 还是 openai 链, 要看 traceback 路径 / printenv LLM_BACKEND 才能定位 backend
3. **测试残留配置必须有 deployment rollback plan** — 2026-07-02 Ollama 测试完后只切 ollama, 没切回 openai_compat. 推荐: `.env.template.production` 模板 + 测试后 git diff .env 看出测试改动

**How to apply (同类 bug 自查清单)**:
- 用户报 "Connection error." 连续多条, **第一查 printenv LLM_BACKEND** 而不是看代码
- 若 LLM_BACKEND=ollama → curl `localhost:11434` 或 `host.docker.internal:11434` 验证 Ollama 是否真在跑
- 若 Ollama 不在跑 → 改 env → `docker compose up -d --force-recreate` (不是 restart!) → curl 验证

**副 bug (本会话发现, 留后续 PR)**:
- `intent_classifier.py:152-155` 用 `hasattr(block, "text") and block.text` 假设响应是 Anthropic Message (有 `.content` 属性 list of blocks)
- OpenAI 响应是 dict (`resp.choices[0].message.content` 字符串)
- _complete_openai_compat 调用方 wrapper 把 dict 包成 Anthropic Message 形状, 但 intent_classifier 仍走 `resp.content` → 报 `'dict' object has no attribute 'content'`
- 当前 fallback 走 search_info + confidence=0, **不影响主流程**, 主 chat 仍能跑
- 修法: intent_classifier 改用统一 `resp.text` 提取 (类似 synthesize_stream 用 anthropic wrapper), 或加 try/except block.text → dict fallback

**Where to fix (副 bug)**:
- `app/agent/intent_classifier.py:140-156` — intent classifier LLM 调 (改 resp.content 提取模式兼容 OpenAI dict)
- 或 `app/core/llm.py:_AnthropicMessageWrapper` — 已包成 wrapper, 但 intent_classifier 用了 `for block in resp.content` 没走 wrapper (这是设计漏洞)
- 推荐: 改 intent_classifier 用 anthropic SDK 调用方式直接 (`block.text` 已 wrapper 适配), 不破坏 OpenAI 兼容

**踩坑教训**:
- 同会话已经踩过 "docker compose restart 不重读 env_file", 本次还是踩 — 必须固化到 pre-commit hook 或 CI 检查:
  ```bash
  # hooks: 改 .env 后必须 force-recreate
  if grep -q 'docker compose restart' latest_diff.txt; then
    echo "WARN: env_file 改动不能用 restart, 用 up -d --force-recreate"
  fi
  ```
- **修复错误的修复**: 第一次用 `docker compose restart app` 看起来跑成功了, 但 printenv 仍显 ollama, 浪费一轮; 改 `up -d --force-recreate` 才真正生效

**3 新铁律 (沉淀 CLAUDE.md)**:
1. **`.env` 改完 docker compose restart 不会重读 env_file** — 必须 `up -d --force-recreate` (CLAUDE.md 2026-07-02 P0-#1 教训第 N 次强化)
2. **OpenAI SDK 1.x APIConnectionError str 和 anthropic SDK 0.39+ 一样都是 'Connection error.'** — 仅看 e.message 无法区分 backend, 看 traceback 或 env
3. **测试残留配置不留** — 任何 `LLM_BACKEND=*` / `OLLAMA_*` 临时测试改 `.env` 后, 完成测试 24h 内必须 git diff 检查 + revert (本次 11 天未回滚)
