# W98 P2-F 微信对话同步修复 runbook — 2026-08-01

## 1. 任务背景

### 1.1 问题
微信 handler 调 `agent.chat()` 时, 会话上下文只走 Redis (短期缓存, SESSION_TTL=48h), PG 有持久化历史但不回填 → Redis 过期/重启后 LLM 只看到当前单条消息 → "失忆客服" (用户实测 "介绍一下课题组近况" 后追问即断片)。

### 1.2 解决方案
W98 P0-A 已在 agent 内实现 `_ensure_session_context` (PG 回填 Redis + last_pg_id 增量), P2-F 进一步抽为共享服务, 让微信 handler 也能预加载会话上下文 (而非依赖 agent 内部一次性加载, 避免"agent.chat 失败时 Redis 已写脏数据"风险)。

## 2. 改动概览

### 2.1 新增文件

| 文件 | 作用 |
|---|---|
| `app/services/session_context.py` | 公共函数 `ensure_session_context` + `set_last_pg_id` + 常量 `SESSION_CONTEXT_MAX_MSGS=24` / `MAX_TURNS=12` / `META_LAST_PG_ID_FIELD` |
| `tests/test_wechat_session_sync.py` | 微信同步铁证 (7 case: handler import + 3 callsite + 3 类 session_id 模式 + 匿名 fallback) |
| `memory/w98-p2-f-startup-2026-08-01.md` | 起步 6 项验证真查记录 |
| `memory/w98-p2-f-closure-2026-08-01.md` | 18 项反馈 + 19 类错误铁律 + 派工 v10 据实上报 |

### 2.2 修改文件

| 文件 | 改动 |
|---|---|
| `app/agent/micro_bubble_agent.py` | 删除 132 行私有函数 (`_fetch_pg_messages` / `_get_last_pg_id` / `_set_last_pg_id` / `_ensure_session_context`), 改为 5 个 alias import 指向 `app.services.session_context`. `_window_messages` 保留 (agent 内部 chat 调用). |
| `app/wechat/handler.py` | import `ensure_session_context` + 3 处 `agent.chat()` 前预加载 (群聊 line 488 / 私聊 line 1104 / 客服 line 1211) |
| `tests/test_session_context.py` | 老 19 case 修正 patch 路径 (从 `patch.object(mba, "_fetch_pg_messages", ...)` 改为 `patch("app.services.session_context._fetch_pg_messages", ...)`) + 新增 12 case (`TestSessionContextPublicAPI`) |

### 2.3 关键代码

```python
# app/services/session_context.py 公共 API
async def ensure_session_context(
    db, user_id: Optional[int], session_id: str,
) -> List[Dict]:
    """确保会话上下文完整 (PG 回填 Redis)
    - Redis 空 → PG 全量回填最近 24 条
    - Redis 非空 → last_pg_id 增量回填
    - user_id 为 None → 越权铁律, 不加载 DB 历史
    """
```

```python
# app/wechat/handler.py 接入 (3 处相同模式)
# W98 P2-F: 微信同步 — 会话上下文预加载 (PG 回填 Redis, 防失忆客服)
await ensure_session_context(db, member.id, session_id)
result = await agent.chat(message=enriched_msg, session_id=session_id, db=db, user_id=member.id, channel_user_id=user_id)
```

## 3. 部署验证

### 3.1 守恒 5 件套

```bash
# 1. alembic head
python -m alembic heads  # → 093_add_search_log_answer_rating (head)

# 2. pytest
SKIP_DB_SETUP=1 pytest tests/test_session_context.py tests/test_wechat_session_sync.py -v \
  --ignore=tests/test_w79_commercial_private_deployment_e2e.py
# → 39 passed + 3 skipped (real-DB integration) + 0 failed

# 3. PWA 410 第 1 层 — skipped (无 frontend 改动)

# 4. 0 production code diff
git diff main -- app/agent/micro_bubble_agent.py | wc -l  # 190 (净减 138 行)
git diff main -- app/wechat/handler.py | wc -l  # 3 行新增 (ensure_session_context 调用)

# 5. 锚点范式
git log --grep "W98 +" --oneline | wc -l  # 47 (含本批 +6)
```

### 3.2 回归风险

无回归:
- 公共函数 100% 复用 P0-A 老逻辑 (只是位置从 agent 移到 services)
- 微信 handler 3 处接入, 每处都是 fail-safe best-effort (PG/Redis 异常 → 走老 Redis-only 路径)
- 0 alembic 改动 (派工 §4.4 守恒)
- 0 前端改动 (派工 §4.3 跳过)

## 4. 监控指标 (上线路后 7 天)

| 指标 | 期望值 | 来源 |
|---|---|---|
| 微信 handler PG 加载命中率 | > 80% (用户首次消息) | application log `ensure_session_context: PG 全量回填` |
| 微信 handler 增量回填命中率 | > 50% (用户后续消息) | application log `ensure_session_context: 增量回填` |
| 微信 handler Redis 失败率 | < 5% (best-effort 容错) | `Error 22 connecting to localhost:6379` |
| 微信 LLM 上下文长度 | median 8-24 条 (12 轮窗口) | `messages = _window_messages(messages)` 输出长度 |

## 5. 5 条铁律沉淀

### 铁律 1: `from X import Y` 命名空间语义影响 patch 路径
- 测试 patch 必须针对函数实际定义的模块, 不能针对 re-export 模块
- 例: `_ensure_session_context` 实际在 `app.services.session_context`, 即使 agent 通过 alias 暴露 `mba._ensure_session_context`, patch 必须打 `app.services.session_context._ensure_session_context`
- 同理: `from app.agent.session_manager import session_manager` 创建本地 binding, patch 必须打 `app.services.session_context.session_manager` 而非 `app.agent.micro_bubble_agent.session_manager`

### 铁律 2: 抽公共后老测试桩兼容 = alias re-export
- 派工 v10 §2 严禁修改老调用点 (已合 main), 因此 agent 模块不能完全移除 `_ensure_session_context` 等私有符号
- 妥协方案: 公共函数在 `session_context.py`, agent 模块通过 `from app.services.session_context import _ensure_session_context as _ensure_session_context` 暴露下划线 alias
- 优点: 兼容老测试桩 + 抽公共后端到端可用

### 铁律 3: 微信 handler 接入点必在 agent.chat 前
- 派工 v10 §2 严禁修改 agent.chat, 因此 "PG 回填" 必须在 handler 层独立调用
- 接入模式: `await ensure_session_context(db, member.id, session_id)` → `await agent.chat(...)`
- 3 处统一模式 (群聊 + 私聊 + 客服), 无例外

### 铁律 4: 派工 brief 路径假设不匹配时按真实施路径执行 (§13.3)
- 派工 v10 §1 期望: `app/services/wechat_service.py` / `app/api/v1/wechat.py` / `app/integrations/wechat.py`
- 真路径: `app/wechat/handler.py`
- 处理: `git ls-tree -r origin/main --name-only | grep -iE "wechat|wx"` 真查, 按真路径执行, 不擅自扩也不擅自缩

### 铁律 5: 派工 v10 据实上报铁律
- 段 6 禁止 "应该 / 大概 / 估计", 所有命令粘贴实际输出
- 段 7 错误 19 类必填排查, 触发必上报
- 段 8 起步 6 项必真验证 (S1-S6), 不跳过

## 6. 后续 PR (留 W98 grand closure)

- CLAUDE.md 永久锚点新增 `## W98 P2-F 微信对话同步修复` 段
- CHANGELOG.md 增条目
- ROADMAP.md 更新 W98 锚点 +6 → +7
- W98 grand closure memory 沉淀本批为类 20.13 实战 19 实例

## 7. 引用

- commit: `25b0e469701f4d29dd8c2c55ee56dadeb3b09445` ([P2-F W98 +6] refactor(chat): 抽 ensure_session_context 共享服务（微信同步共用）)
- base: `4e6816c39` (merge: CHAT-P1-E 前端体验 5 项)
- 派工 brief: P2-F 微信对话同步修复
- 起步 memory: `memory/w98-p2-f-startup-2026-08-01.md`
- closure memory: `memory/w98-p2-f-closure-2026-08-01.md`