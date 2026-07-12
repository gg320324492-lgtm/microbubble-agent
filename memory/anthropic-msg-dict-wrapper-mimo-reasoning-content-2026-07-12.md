---
name: anthropic-msg-dict-wrapper-mimo-reasoning-content-2026-07-12
description: "P0-#1.5 — wrapper 返回 plain dict 让 12 caller (intent_classifier / critic / self_rag / result_compressor 等) 全 AttributeError, 改 _AnthropicMsgDict (dict 子类 + __getattr__) 修; 同时 wrapper 加 reasoning_content → thinking block + intent_classifier max_tokens 300→2048; 14/14 测试 PASS"
metadata: 
  node_type: memory
  type: project
  originSessionId: 987866fd-9014-4a38-b9fe-7f536684352d
---

**触发 (2026-07-12)**: 用户切回 `LLM_BACKEND=openai_compat` (P0-#1 已修) 后 curl SSE 流正常,但 `intent_detected` event `reasoning="intent classification failed: 'dict' object has no attribute 'content', falling back to search_info"`,还有"LLM 返回空文本"等类似错误。

**3 重复合根因**:
1. **wrapper shape 与 caller 期望不兼容 (主因)** — `tool_call_converter.py` `openai_response_to_anthropic_message` (line 156) docstring 写"LLMClient 调用方代码使用 .content / .stop_reason / .usage.input_tokens 属性访问"实际返 plain dict —— 12 caller 全用 `resp.content` / `block.text` 属性访问 → AttributeError 'dict' object has no attribute 'content'
2. **wrapper 不处理 mimo reasoning_content** — mimo-v2.5 OpenAI 协议把思考过程放 `reasoning_content` 字段而非 `content`, `finish_reason="length"` 时 content="" → caller 拿不到任何 block → 空文本 fallback
3. **intent_classifier max_tokens=300 不够** — mimo reasoning_content 占满 300 tokens, finish_reason=length, content 永远是空

**修法 (3 重复合)**:
1. 加 `_AnthropicMsgDict` 类 (dict 子类 + `__getattr__`) — 让 `resp.content` 和 `resp["content"]` 双访问都 work, **后向兼容**所有现有测试 (`ant_msg["role"]` 不破)
2. wrapper 加 reasoning_content → `{type:thinking, thinking:...}` block — Anthropic SDK 标准格式让 `extract_text_from_response` 等工具自动生效
3. intent_classifier `max_tokens=300→2048` + fallback 到 thinking block 提取

**端到端验证** (curl 实测):
- `intent_detected reasoning="用户询问'dutonghe是谁'，属于查找人员信息，因此归类为search_info"` (真分类生效)
- `label="🧠 意图：找资料 (置信度 95%)"` (vs 旧 0%)
- 完整流 0 errors / 1 message_persisted ×2 + 1 intent + 1 synthesis + text_delta + critique + done
- 测试: **14/14 PASS** (12 旧 + 2 新 Case 13/14)

**4 文件改动** (+263 / -6):
- `app/core/tool_call_converter.py`: 新 `_AnthropicMsgDict` (dict subclass + __getattr__) + `_wrap_as_anthropic()` 递归 helper + wrapper 返 `_wrap_as_anthropic({...})` + reasoning_content → thinking block 转换
- `app/agent/intent_classifier.py`: max_tokens 300→2048 + fallback 到 thinking block 提取
- `tests/unit/test_tool_call_converter.py`: 新增 Case 13 (wrapper attr+dict 双访问 + 嵌套 attr + 工具调用 block) + Case 14 (reasoning_content → thinking block 含只有 reasoning/两者都有/Pydantic-like input)

**Why**:
1. **wrapper shape 与 caller 期望必须对齐** — docstring 说"使用 .content 属性访问"实现却返 plain dict 是设计漏洞, 用 `_AnthropicMsgDict` (dict 子类 + __getattr__) 而非替换返回类型,**后向兼容 12 caller + 现有 dict 风格测试同时生效**
2. **OpenAI thinking 模型的 reasoning_content 必须 wrap 为 thinking block** — 否则 thinking-only 响应丢内容,纯文本 caller 全瞎
3. **mimo-v2.5 thinking 模型 max_tokens 至少 2048** — 300 被 reasoning 占满 finish_reason=length → content='' → 后续 fallback
4. **thinking 参数在 openai_compat 路径下 _complete_openai_compat 不传递** — Anthropic 专属字段, openai_compat 实际走 OpenAI reasoning_effort (此处不能改), 需 max_tokens 兜底
5. **`for block in resp.content` 是 anthropic backend 假设** — backend dispatch 后必须 wrapper shape 同步, 12 处 caller 全靠 wrapper 改一次全修

**How to apply (同类 bug 自查)**:
- 用户报"intent/critic/compressor/self_rag 失效" → 立即 `grep -nE "for\s+\w+\s+in\s+\w+\.content" app/ --include="*.py"` 看有多少 caller 受影响
- 检查 wrapper 是不是返 plain dict → 改 _AnthropicMsgDict (dict subclass)
- 检查 mimo 等 OpenAI thinking 模型的响应是不是有 `reasoning_content` 字段,是则 wrap 成 `{type:thinking, thinking:...}`
- 检查 max_tokens 是否 ≥ 2048 (mimo reasoning 起步 1000+ token)
- 测试必须 cover attr+dict 双访问 (防止 Pydantic vs dict 兼容性回归)

**Where to fix (12 受影响 caller)**:
- `app/agent/intent_classifier.py:152-160` (已修)
- `app/agent/critic.py:133-136` (wrapper 改后自动生效)
- `app/agent/result_compressor.py:162+` (wrapper 改后自动生效)
- `app/core/llm.py:189-196` (已有 `extract_text_from_response` helper 同时支持 text+thinking)
- `app/services/meeting_analysis_service.py:529+` (wrapper 改后自动生效)
- `app/services/paper_layout_service.py:179+` (wrapper 改后自动生效)
- `app/services/rag_evaluator.py:100,129,158,188` (wrapper 改后自动生效, 但 rag_evaluator 是测试用具,可能不直接影响生产)
- `app/services/self_rag.py:81,163` (wrapper 改后自动生效, 但 #009 Self-RAG 已 fallback 至 flag-off, 但代码已就绪待 flag-on)

**踩坑教训**:
- 第一次想"只改 intent_classifier 用 _block_get helper, 跟 agentic_loop 一样" → 但只改 1 个 caller 还有 11 个隐性 bug 留着
- **正确改法**: 改 wrapper,让 12 caller 同时生效, **1 处改 12 处修**(实际案例)
- 双访问 (attr + dict) 是关键:`_AnthropicMsgDict(dict)` 子类加 `__getattr__` 让测试 `ant_msg["role"]` 和 caller `ant_msg.content` 都 work
- max_tokens 兜底必须 — Anthropic thinking=disabled 字段在 openai_compat 路径无效,实际靠 max_tokens 给够 reasoning 空间

**Why not just 1-line fix**:
- 用 Pydantic BaseModel 替代 dict → 12 caller 用 `resp.content` attr 都 work, 但破坏测试 (`ant_msg["role"]` 不 work)
- 用 SimpleNamespace → 同上
- **用 dict 子类 + __getattr__ 双访问**: 完美兼容测试 + caller 双方

**和 P0-#1 的关系**:
- P0-#1 改 .env LLM_BACKEND=ollama → openai_compat 让 SSE 不再 Connection error
- P0-#1.5 是 P0-#1 修复后**浮出的副 bug**,原因和 P0-#1 无关但路径重叠 (openai_compat backend → wrapper shape 不兼容)
- 这两条 commit 链: P0-#1 (1 commit) → P0-#1.5 (1 commit) = 完整生产可用

**完整 memory chain**:
1. `llm-backend-ollama-residual-connection-error-2026-07-12.md` (P0-#1)
2. `anthropic-msg-dict-wrapper-mimo-reasoning-content-2026-07-12.md` (P0-#1.5 本文件)
