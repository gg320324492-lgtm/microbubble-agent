# 交接：`.env` 里 7 行 LLM 模型名修复**只存在于本机**

> **交接时间**：2026-10-14
> **交接方**：microbubble-agent 仓会话（已修复并验证，**改动不在 git 里**）
> **接手方**：换机 / 重建 `.env` / 交接环境的任何人
> **性质**：**环境配置问题，代码无缺陷** —— 但不改会导致对话功能整体不可用

---

## 零、一句话

`.env` 里 7 个 `AGENT_*_MODEL` 的值原本是 **Ollama 的模型名**，而
`LLM_BACKEND` 指向的是 **MiniMax** ⇒ 小气助手**完全无法对话**。

**修复只改了 `.env`（未入库），代码没动一行。**

---

## 一、故障现象与根因

### 现象

前端报 `Error code: 400 — invalid params, unknown model 'qwen3.8:27b' (2013)`。

### 根因：后端与模型名是**两个独立维度**，当时只对了一半

```bash
LLM_BACKEND=openai_compat                    # ← 实际后端 = MiniMax
LLM_OPENAI_COMPAT_BASE_URL=https://api.minimaxi.com/v1
LLM_OPENAI_COMPAT_MODEL=MiniMax-Text-01     # ← 这行是对的

AGENT_THINKING_MODE_BALANCED_MODEL=qwen3.8:27b   # ← 错：这是 Ollama 的模型名
AGENT_SYNTHESIS_MODEL=qwen3.8:27b                # ← 错
... 共 7 行
```

请求带着 `qwen3.8:27b` 打到 MiniMax，它不认识 ⇒ 400。

### 为什么拖了这么久：三层叠加

修完模型名后**又浮出两层**，逐层修好才看得见下一层：

| 层 | 报错 | 根因 |
|---|---|---|
| 1 | `unknown model 'qwen3.8:27b'` | 后端与模型名不匹配（本文档主题） |
| 2 | `tool result's tool id(plan_00_...) not found` | 系统代查结果冒充模型 tool_call（代码缺陷，commit `33490d7ea`） |
| 3 | CI `value too long for VARCHAR(32)` | alembic revision id 起成 33 字符（commit `1fb9c0ab1`） |

**只改 `.env` 而没有第 2 层的代码修复，对话仍然是坏的。**

---

## 二、要改什么（7 行）

把这 7 行的值从 `qwen3.8:27b` 改成 `MiniMax-Text-01`：

```
AGENT_COMPRESSOR_MODEL=MiniMax-Text-01
AGENT_REFLECTION_MODEL=MiniMax-Text-01
AGENT_SYNTHESIS_MODEL=MiniMax-Text-01
AGENT_INTENT_MODEL=MiniMax-Text-01
AGENT_THINKING_MODE_FAST_MODEL=MiniMax-Text-01
AGENT_THINKING_MODE_BALANCED_MODEL=MiniMax-Text-01
AGENT_THINKING_MODE_DEEP_MODEL=MiniMax-Text-01
```

### ⚠️ 这两行**故意不改**

```
OLLAMA_MODEL=qwen3.8:27b          # 保留
OLLAMA_FALLBACK_MODEL=qwen3.8:27b # 保留
```

它们是**回切路径**（`LLM_BACKEND=ollama` 时用）。本机 ollama 容器健康、
`qwen3.8:27b`（17 GB）已拉好，是有意保留的可切换后端。

---

## 三、改完必须 force-recreate，restart 无效

```bash
docker compose up -d --force-recreate app celery-worker
```

`docker compose restart` **不会刷新 env**（容器环境变量在创建时固定）。
实测踩过：改完 `.env` 后 restart，请求仍带旧模型名。

---

## 四、验收（判据是打真实请求，不是看配置对不对）

```bash
# 1) 确认运行中容器真的拿到新值（不是只改了文件）
docker exec microbubble-agent-app-1 sh -c \
  'echo $AGENT_THINKING_MODE_BALANCED_MODEL; echo $LLM_BACKEND'
# 期望: MiniMax-Text-01 / openai_compat

# 2) 打真实对话请求，确认三档 thinking_mode 都通
POST https://agent.mnb-lab.cn/api/v1/chat
{"message":"用一句话介绍微纳米气泡","thinking_mode":"balanced"}
# 期望 HTTP 200，且响应含 tool_trace（≥1 项）——证明工具真被调了
```

⚠️ **不要只看 HTTP 200**：`AGENT_*_MODEL` 若换成另一个**不支持 tools** 的模型，
每轮 `tool_calls=0`，agent 会**凭记忆编造**检索结果而**不报任何错**
（2026-09-09 事故，见 [[llm-backend-tool-call-failure-2026-09-09]]）。
**必须确认 `tool_trace` 非空。**

---

## 五、想改后端时先做这个实测

**后端和模型名是两个独立维度，改一个极易漏另一个。** 判断"该往哪边修"的唯一办法是
**同一模型名分别打两个后端各测一发**：

| 组合 | 结果 |
|---|---|
| `MiniMax-Text-01` @ MiniMax | **HTTP 200** ✅ |
| `qwen3.8:27b` @ MiniMax | `unknown model` ❌ |
| `qwen3.8:27b` @ Ollama | HTTP 200（但 **content 为空**，需再看 tools） |

⇒ 本次结论：**后端是好的，错的是模型名**。

---

## 六、关联

- **CLAUDE.md 类 20.227** —— 同一事故的永久铁律（含"docstring 声称的动作要逐条对代码"）
- **commit `33490d7ea`** —— 第 2 层代码修复（系统代查结果不再冒充 tool_call）
- **commit `1fb9c0ab1`** —— 第 3 层 revision id 改名
- **memory** `llm-backend-model-name-and-tool-protocol-2026-10-14`
- **memory** `llm-backend-tool-call-failure-2026-09-09` —— 同一条根因链的第一次发作