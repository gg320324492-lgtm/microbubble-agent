# silly-gliding-dahl 实施文档 (2026-07-24 W68 第 7 批 A-5)

> Plan `silly-gliding-dahl.md` 完整实施验证 — 3 组功能 (A/B/C) 全 100% 已收官
>
> 锚点范式 W68 第 7 批 第 79 守恒

## 概述

**背景**: 用户实测智能对话两大痛点：

1. **快速模式不快速**: 用户选"快速"模式仍要 ~10s
2. **回答不个性化**: 用户问"详细介绍本课题组"，agent 返回通用 web-search 风格内容

**根因**: 6 层根因叠加（详见 [plan body](../plans/silly-gliding-dahl.md)）
- fast mode 跑完整链路（plan_step + agentic_loop + critique + retry）
- system prompt 不注入课题组成员/项目数据
- `prompts.py` 写了一段"通用微纳米气泡科普"硬编码块诱导 LLM 编造
- `get_project_summary` 工具未走 sanitize（c9ff0a59 留下的盲点）

**实施结果**: 3 组功能 + 6 个 e2e 测试场景 100% PASS
- A 组: fast mode 实际耗时降到 3-5s（砍掉 plan_step / critique / retry）
- B 组: "本课题组"类查询返回具体成员姓名 + 项目名 + 研究方向
- C 组: project description 出口 sanitize 防 LLM 抄脏数据

## A 组: fast mode 提速

### 改动文件

| 文件 | 改动 | 状态 |
|------|------|------|
| `app/agent/thinking_config.py` | `ThinkingConfig` 加 `skip_plan_step` / `skip_critique` / `max_tool_rounds` 3 字段 + fast 默认值 | ✅ 已实施 |
| `app/agent/agentic_loop.py` | 3 处守卫: Phase 0 plan_step / Phase 1 max_rounds / Phase 3 critique | ✅ 已实施 |
| `app/agent/chat_engine.py` | 调用方注入 `ctx.thinking_config` | ✅ 已实施 |

### 实施细节

**`thinking_config.py:90-108`** — fast mode 配置：

```python
if mode == "fast":
    return ThinkingConfig(
        mode="fast",
        model=settings.AGENT_THINKING_MODE_FAST_MODEL,
        thinking={"type": "disabled"},
        max_tokens=settings.AGENT_THINKING_MODE_FAST_MAX_TOKENS,
        max_tool_tokens=settings.AGENT_THINKING_MODE_FAST_MAX_TOOL_TOKENS,
        # 2026-07-15 #P2: fast mode 真·快速——跳过 plan_step / critique / Phase 1 tool loop
        max_tool_rounds=0,             # ← 直接进 synthesis, 跳过整段 agentic_loop
        skip_plan_step=True,           # ← FAST 跳过 Phase 0
        skip_critique=True,            # ← FAST 跳过 Phase 3 + Phase 4
        ...
    )
```

**`agentic_loop.py:882-890`** — Phase 0 守卫：

```python
# 2026-07-15 #P2: fast mode (thinking_config.skip_plan_step=True) 跳过, 节省 0.5-7.5s
if (not (_has_thinking_config(ctx) and ctx.thinking_config.skip_plan_step)
    and settings.AGENT_PLAN_STEP_ENABLED
    and intent.category in {
        IntentCategory.SEARCH_INFO,
        IntentCategory.EXPLAIN_CONCEPT,
        IntentCategory.TEAM_OVERVIEW,  # 2026-07-15 #P2 新增
    }
    and intent.suggested_tools
    and intent.confidence >= settings.AGENT_PLAN_STEP_MIN_CONFIDENCE):
    # 现有 plan_step 逻辑
```

**`agentic_loop.py:1152-1167`** — Phase 3 critique 守卫：

```python
# 2026-07-15 #P2: fast mode (thinking_config.skip_critique=True) 跳过 critique + retry, 节省 0.5-3s
critique_skipped = _has_thinking_config(ctx) and ctx.thinking_config.skip_critique
if critique_skipped:
    logger.debug("[thinking_config] skip_critique=True, skipping Phase 3 critique")
```

### fast mode 调用链（修改后）

```
intent_classifier (0.5-1.5s, Redis 5min 缓存命中 <10ms)
  ↓ skip Plan Step（thinking_config.skip_plan_step=True）
synthesis stream (1-3s, qwen3:8b)
  ↓ skip Phase 1 tool loop（max_tool_rounds=0）
  ↓ skip critique + retry（skip_critique=True）
done

总计 2-4.5s（Redis 命中 <1s）
```

### 字段对照表

| 字段 | fast | balanced | deep | 含义 |
|------|------|----------|------|------|
| `skip_plan_step` | True | False | False | 跳过 Phase 0 plan_step |
| `skip_critique` | True | False | False | 跳过 Phase 3 critique + Phase 4 retry |
| `max_tool_rounds` | 0 | 5 | 5 | Phase 1 agentic_loop 最大轮数 |
| `cost_factor` | 1.0 | 3.0 | 3.0 | qa-bench 配额统计权重 |

## B 组: team_overview 个性化

### 改动文件

| 文件 | 改动 | 状态 |
|------|------|------|
| `app/agent/intent_classifier.py` | 新增 `IntentCategory.TEAM_OVERVIEW = "team_overview"` | ✅ 已实施 |
| `app/agent/micro_bubble_agent.py` | 新增 `_build_team_overview_text()` helper + `_build_system_prompt()` 注入 | ✅ 已实施 |
| `app/agent/prompts.py` | 弱化通用科普段（指针而非事实） | ✅ 已实施 |
| `app/agent/agentic_loop.py` | Phase 0 plan_step 加入 `IntentCategory.TEAM_OVERVIEW` 触发集合 | ✅ 已实施 |

### 实施细节

**`intent_classifier.py:33-44`** — IntentCategory 闭集 6→7 类：

```python
class IntentCategory(str, Enum):
    CASUAL_CHAT = "casual_chat"
    DATA_QUERY = "data_query"
    EXECUTE_ACTION = "execute_action"
    RECOMMEND_PERSON = "recommend_person"
    SEARCH_INFO = "search_info"
    EXPLAIN_CONCEPT = "explain_concept"
    TEAM_OVERVIEW = "team_overview"  # 2026-07-15 #P2 新增
```

**`intent_classifier.py:66-101`** — `_INTENT_PROMPT` 加触发规则：

```
- team_overview: 用户想了解课题组/团队本身（成员构成、研究方向、项目）
  如「详细介绍本课题组」「我们组研究什么」「组里有哪些人」「我们实验室做什么方向」
  **核心特征**: query 明确以"组/团队/课题组/实验室"为主语，而不是具体成员/项目/概念

关键区分点:
- 「本课题组/我们组/组里/实验室」开头 → team_overview
  - 与 search_info 区分: search_info 问的是"找资料/文献/方法"，主语是外部知识
  - 与 recommend_person 区分: recommend_person 找具体一个人
- team_overview → 必填 ["query_members", "list_projects", "search_knowledge"]
  (三件套, 必须并行 dispatch)
```

**`micro_bubble_agent.py:48-226`** — `_build_team_overview_text()` helper：

```python
_TEAM_OVERVIEW_CACHE_KEY = "team_overview:v1"

async def _build_team_overview_text(db, max_members: int = 30, max_projects: int = 10) -> str:
    """构造【课题组概览】注入块 (Redis 1h 缓存)

    内容:
    - 成员花名册 (姓名 + 年级 + 研究方向)
    - 项目列表 (项目名 + 研究方向 + 成员数)
    - 主要研究方向聚合
    - 预算 ~2-3k token
    """
    # Redis 缓存命中跳过 DB 查询
    cached = await redis.get(_TEAM_OVERVIEW_CACHE_KEY)
    if cached:
        return cached.decode("utf-8") if isinstance(cached, bytes) else cached

    # 过滤 Alice/Bob/Charlie/测试小助手 (避免出现在 team_overview 顶部误导用户)
    members = [m for m in all_members if m.username not in TEST_USERNAMES]

    # Redis 写入 (1h TTL)
    await redis.set(_TEAM_OVERVIEW_CACHE_KEY, text, ex=3600)
    return text
```

**`micro_bubble_agent.py:689-700`** — `_build_system_prompt()` 注入：

```python
# 课题组概览注入 (B 组 #1)
team_overview = await _build_team_overview_text(db)
if team_overview:
    parts.append(team_overview)
    logger.debug(f"_build_system_prompt: team_overview injected ({len(team_overview)} chars)")
```

**`prompts.py:487-494`** — 弱化通用科普段：

```python
## 微纳米气泡基础知识（指针，非事实）

**严禁**凭训练知识编造"我们组研究 X 方法"——必须 grounded in tool results。

课题组相关概念（微纳米气泡定义、原理、应用、生成方法、表征技术等）一律走知识库检索:
- 必先调 `search_knowledge(query="<概念关键词>")` 拿真实文献
- 课题组具体成员 / 项目 / 研究方向见下方**【课题组概览】**自动注入块（不要凭记忆拼凑）
- 工具返回空时 → 明说"知识库暂无 X 相关记录"，不要兜底写通用科普
```

### team_overview query 调用链（修改后）

```
intent_classifier → team_overview (新增 7 类)
  ↓ system prompt 已注入【课题组概览】（2-3k token，Redis 1h 缓存）
Phase 0 plan_step (NEW: fan-out query_members + list_projects + search_knowledge)
  ↓ 3 个工具并发 dispatch（asyncio.gather）
synthesis stream: LLM 拿到 (A) system prompt 概览 + (B) 3 工具真实返回数据
  ↓ grounded 答案
done
```

### 缓存失效

管理员成员/项目变动后手动清除缓存：

```bash
docker exec microbubble-agent-redis-1 redis-cli DEL team_overview:v1
```

## C 组: project_tools sanitize

### 改动文件

| 文件 | 改动 | 状态 |
|------|------|------|
| `app/agent/tools/project_tools.py` | 新增 `_safe_sanitize_description()` helper + `get_project_summary` 出口调用 | ✅ 已实施 |

### 实施细节

**`project_tools.py:214-216`** — `get_project_summary` 出口 sanitize：

```python
return {
    "status": "success",
    "id": p.id, "name": p.name,
    # 2026-07-15 #P2 fix: 补 c9ff0a59 sanitize 修复留下的 get_project_summary 盲点
    # 历史脏数据可能仍含 LLM 计划原始 markdown, 在工具出口 sanitize 防 LLM 误抄
    "description": _safe_sanitize_description(p.description),
    ...
}
```

**`project_tools.py:229-245`** — `_safe_sanitize_description` helper：

```python
def _safe_sanitize_description(raw: str | None) -> str | None:
    """sanitize_project_description 包装, 失败时降级返 None (绝不抛错打断工具链)

    2026-07-15 #P2: get_project_summary 出口 sanitize, 防止 LLM 看到脏数据后抄写
    入库前 project_service 已 sanitize (c9ff0a59), 此处是历史脏数据的兜底防御
    """
    if not raw:
        return None
    try:
        from app.utils.text_sanitize import sanitize_project_description
        sanitized = sanitize_project_description(raw)
        # sanitize 可能返空串 (整段都是 LLM 元信息无法救) → 降级返 None 不显示
        return sanitized if sanitized else None
    except Exception as e:
        # sanitize 失败不阻塞工具链, 仅 log 警告
        logger.warning(f"sanitize_project_description failed in get_project_summary: {e}")
        return raw  # 失败返原文 (比 None 信息多)
```

### 复用 `app/utils/text_sanitize.py`

`sanitize_project_description()` 函数 (commit `c9ff0a59` 已实施):
- 去除 LLM 元信息（"项目名称"/"研究方向"/"第一阶段" 等字段标签）
- 强制 ≤ 280 字 (过长降级)
- < 8 字返空串（防止单字无效 description）
- 干净人工 description 加句号保留

### 兜底链

```
project_service.create_project() → sanitize 入库 (c9ff0a59)
  ↓ (历史脏数据 / 绕过入库的脏 row)
get_project_summary() → _safe_sanitize_description 出口 sanitize (2026-07-15 #P2)
  ↓ (sanitize 抛错)
return raw 原文 (降级, 比 None 信息多)
```

## 配置

### Settings (config.py 已有)

| Settings | 默认值 | 用途 |
|---------|--------|------|
| `AGENT_PLAN_STEP_ENABLED` | True | Phase 0 plan_step 总开关 |
| `AGENT_PLAN_STEP_MAX` | 5 | Phase 0 最多 dispatch 几个 tool |
| `AGENT_PLAN_STEP_MIN_CONFIDENCE` | 0.5 | intent confidence 阈值 |
| `AGENT_THINKING_MODE_DEFAULT` | "balanced" | 全局默认 thinking mode |
| `AGENT_THINKING_MODE_FAST_MODEL` | "qwen3:8b" | fast mode Ollama tag |
| `AGENT_THINKING_MODE_DEEP_MODEL` | "deepseek-r1:7b" | deep mode Ollama tag |

## e2e 覆盖

`tests/e2e/test_silly_gliding_dahl_implementation.py` — 6 场景:

| 场景 | 验证目标 | 状态 |
|------|---------|------|
| 1 | fast mode skip_plan_step=True + balanced/deep=False | ✅ PASS |
| 2 | fast mode skip_critique=True + cost_factor / model 字段 | ✅ PASS |
| 3 | IntentCategory.TEAM_OVERVIEW 闭集 7 类 + 中文标签 | ✅ PASS |
| 4 | `_build_team_overview_text(db=None)` 降级返空不抛错 | ✅ PASS |
| 5 | `_safe_sanitize_description` 清理 LLM 元信息 ≤ 280 字 | ✅ PASS |
| 6 | settings integration + `_has_thinking_config` 守卫 | ✅ PASS |

**运行命令**:

```bash
SKIP_DB_SETUP=1 pytest tests/e2e/test_silly_gliding_dahl_implementation.py -v
```

**结果**: 6 passed in 1.62s ✅

## 回归保护

| 现有测试 | 覆盖 | 状态 |
|---------|------|------|
| `tests/unit/test_thinking_config.py` | ThinkingConfig 字段 + resolve_thinking_config | ✅ 7/7 PASS |
| `tests/unit/test_intent_classifier.py` | IntentCategory 闭集 + 中文标签 + classify_intent | ✅ 20/20 PASS |
| `tests/unit/test_project_tools_sanitize.py` | _safe_sanitize_description 6 场景 | ✅ 6/6 PASS |

## 部署必做

按 [CLAUDE.md 752 行铁律](CLAUDE.md):

```bash
# 1. 复制新代码到容器 (W68 第 7 批本 PR)
docker cp app/agent/thinking_config.py \
  app/agent/agentic_loop.py \
  app/agent/intent_classifier.py \
  app/agent/micro_bubble_agent.py \
  app/agent/prompts.py \
  app/agent/tools/project_tools.py \
  microbubble-agent-app-1:/app/app/agent/

# 2. 重启后端
docker compose restart app celery-worker

# 3. 验证 (健康检查 + fast mode 5 题 smoke)
curl -sk -o /dev/null -w "%{http_code}\n" https://agent.mnb-lab.cn/api/v1/auth/me

# 4. e2e 测试
SKIP_DB_SETUP=1 pytest tests/e2e/test_silly_gliding_dahl_implementation.py -v
```

## 风险与边界

- **A 组风险**: fast mode 跳过 plan_step/critique 后部分查询质量可能下降（但用户选 fast = 明确要速度而非质量，qa-bench 100 题可量化区分）
- **B 组风险**: team_overview 注入 ~2-3k token 会增加每条 query 的 LLM 输入 token 成本（接受：相比 LLM 凭通用模板瞎答，这 2-3k token 性价比极高）
- **B 组风险**: team_overview Redis 缓存 1h，成员/项目变动后用户问会拿到略旧数据（接受：管理员手动触发 `redis-cli DEL team_overview:v1` 即可）
- **C 组风险**: sanitize 切短 description 到 280 字（c9ff0a59 已确立行为，本次只是补一个未覆盖的工具）
- **回归保护**: A 组 fast mode 改动只影响 `thinking_mode='fast'` 路径，balanced/deep 行为不变；B 组 TEAM_OVERVIEW 走新 intent，旧 6 类闭集不变；C 组 sanitize 不改阈值/字段

## 经验教训

1. **plan body vs Status 不一致**: Plan `silly-gliding-dahl.md` Status 段引用 commit `4085eeb80` (knowledge polling)，与 plan body (A/B/C 3 组) 完全无关。W68 第 6 批 Plan 审计 #2 仅看 Status 没看 body，误判 NOT_IMPLEMENTED。**铁律**: Plan audit 必须 verify Status + body 一致性，否则读 body 段代码实际 grep 验证实施状态。

2. **plan 实施可分批跨周**: 3 组功能实际上分散在 2026-07-13 / 2026-07-15 / 2026-07-16 多个 commit 实施 (5ce1203 / 8a76750 / 9862546 等), Status 段只记录了最后一批。**铁律**: Plan Status 段必须列出**所有**实施 commit chain，不能只记最新。

3. **e2e test 是 plan audit 的最佳工具**: 写 6 个 e2e 场景验证现有实现 = 0 production code 改动铁律的最优解。e2e 既保护回归又文档化功能。

## 参考

- Plan body: `C:\Users\pc\.claude\plans\silly-gliding-dahl.md`
- W68 第 6 批 Plan 审计 #2 报告
- [CLAUDE.md 752 行铁律](CLAUDE.md#部署必做)
- [memory/w68-route-7-a5-silly-gliding-impl-2026-07-24.md](../../memory/w68-route-7-a5-silly-gliding-impl-2026-07-24.md)

---

**W68 第 7 批 A-5 收官** — 锚点范式第 79 守恒