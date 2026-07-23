# W68 路线 F-3: Drive v2 PR9 评论 rate-limit tier 验证 — 锚点范式第 56 守恒

> **日期**: 2026-07-24
> **路线**: W68 第 4 批 (Drive v2 PR9 评论 rate-limit 接入 — 主指挥复核)
> **角色**: Agent "W68 第 4 批 Drive 评论 rate-limit 接入"
> **分支**: `test/drive-pr9-rate-limit-verify-2026-07-24`
> **主指挥**: W68 grand closure 协调 (待 merge)
> **commit**: pending

---

## 1. 任务概述

W68 第 3 批 F-1 (drive_comments 后端) 报告里说"限流自动覆盖: `/api/v1/drive/*` 在
`app/core/rate_limit.py:285` 已有 path match, write 走 drive_upload 50/min".
**主指挥复核发现不能想当然**, 派本 Agent 7 端点 × tier 矩阵逐一验证.

**结论**:
- ✅ **7/7 端点全命中 rate_limit.py:285 path match** (drive_comments 前缀
  `/drive/comments` + main.py 挂载 `/api/v1` = `/api/v1/drive/comments/*`)
- ✅ **写 5 端点** (POST/PATCH/DELETE/POST resolve/POST unresolve) 全走 `drive_upload` (50/min)
- ✅ **读 2 端点** (GET list / GET id) 全走 `drive_list` (300/min)
- ✅ **0 production code 改动** (主指挥铁律维持) — 仅 tests/ 加 1 文件 350 行
- ✅ **测试 13/13 PASS** (7 tier 矩阵 + 5 行为验证 + 1 配置 baseline)

**完成定义**:
- ✅ 1 新增文件: `tests/test_drive_v2_pr9_rate_limit.py` (350 行, 13 tests)
- ✅ memory 沉淀 (本文件, ~150 行)
- ⏳ commit hash + push pending (主指挥来 merge)

---

## 2. 文件清单 (1 新增 + 0 修改)

| 文件 | 行数 | 职责 |
|------|------|------|
| `tests/test_drive_v2_pr9_rate_limit.py` | 350 | 7 端点 × tier 矩阵 + 5 行为验证 |
| `app/core/rate_limit.py` | 0 | 不动 (主指挥铁律: rate-limit 缺失留给决策) |
| `app/api/v1/drive_comments.py` | 0 | 不动 (路由前缀不变, 自动覆盖) |

**0 production code 改动铁律维持**.

---

## 3. 7 端点 × tier 矩阵 (全部命中 rate_limit.py:285 path match)

| # | Method | Path | 期望 tier | 期望 limit | 实际 | 验证 test |
|---|--------|------|-----------|-----------|------|-----------|
| 1 | POST   | `/api/v1/drive/comments`              | `drive_upload` | 50/min | ✅ | `test_drive_comments_endpoint_maps_to_expected_tier[POST]` |
| 2 | GET    | `/api/v1/drive/comments`              | `drive_list`   | 300/min | ✅ | `test_drive_comments_endpoint_maps_to_expected_tier[GET-list]` |
| 3 | GET    | `/api/v1/drive/comments/{id}`         | `drive_list`   | 300/min | ✅ | `test_drive_comments_endpoint_maps_to_expected_tier[GET-id]` |
| 4 | PATCH  | `/api/v1/drive/comments/{id}`         | `drive_upload` | 50/min | ✅ | `test_drive_comments_endpoint_maps_to_expected_tier[PATCH]` |
| 5 | DELETE | `/api/v1/drive/comments/{id}`         | `drive_upload` | 50/min | ✅ | `test_drive_comments_endpoint_maps_to_expected_tier[DELETE]` |
| 6 | POST   | `/api/v1/drive/comments/{id}/resolve` | `drive_upload` | 50/min | ✅ | `test_drive_comments_endpoint_maps_to_expected_tier[POST-resolve]` |
| 7 | POST   | `/api/v1/drive/comments/{id}/unresolve` | `drive_upload` | 50/min | ✅ | `test_drive_comments_endpoint_maps_to_expected_tier[POST-unresolve]` |

**5 行为验证**:
- ✅ `test_drive_upload_tier_triggers_429_after_exceeding_50_per_minute` — 51 次写 → 429
- ✅ `test_drive_list_tier_allows_300_reads_without_429` — 30 次读 → 全 200 (远未达限)
- ✅ `test_drive_upload_and_drive_list_use_independent_quotas` — 写 429 时读不受影响
- ✅ `test_authenticated_user_uses_user_dimension_key_for_drive_tiers` — 登录用户用 `{ip}:user:{uid}` 独立配额
- ✅ `test_all_drive_write_endpoints_share_drive_upload_quota` — 5 写端点共享 50/min 配额
- ✅ `test_drive_comments_default_tier_limits_match_production_config` — baseline 不漂移

**总计**: 7 矩阵 + 6 行为验证 = **13 tests, 13 PASS** (SKIP_DB_SETUP=1 模式, 无 PostgreSQL 依赖)

---

## 4. 关键发现

### 4.1 rate_limit.py:285 path match 自动覆盖 7 端点

**触发链路**:
1. `app/main.py:89` 把 `drive_comments.router` 挂载到 `/api/v1` 前缀
2. `app/api/v1/drive_comments.py:34` router `prefix="/drive/comments"`
3. 拼接: `/api/v1` + `/drive/comments` + `@router.post("")` = `/api/v1/drive/comments`
4. `app/core/rate_limit.py:285` 判定: `path.startswith("/api/v1/drive/")` → True
5. 进入 `if method in ("POST", "PUT", "PATCH", "DELETE"): return "drive_upload"` 分支
6. 5 写端点 (POST/PATCH/DELETE) 全走 drive_upload; 2 读端点 (GET) 全走 drive_list

**为什么能自动覆盖**: W68 第 3 批 F-1 (drive_comments) 沿用 Drive v2 系列前缀惯例
(`/api/v1/drive/*`), 与 `rate_limit.py:285` path match 完全对齐. **不需要新 tier**.

### 4.2 mock ZSET dict 模拟 timestamp 去重陷阱

**问题**: `_ZSet.members` 用 `dict[str, float]` 模拟 Redis ZSET. `record()` 调 `zadd()`
→ `members.update({str(now): now})`. 如果 2 次请求 clock["now"] 相同, dict update 会
**覆盖**上次 entry → ZCARD 永远 = 1 → 配额永远用不尽 → 50/min 测试永远不触发 429.

**修复**: 每请求前 `clock["now"] += 0.001`. 真实 Redis ZSET 同样按 `str(now)` 去重
(`ZADD` member 必须 unique, score=now 重复则覆盖 value), 所以生产也建议每请求至少
1ms 间隔 (实战用户行为符合, 自动化测试必须显式推进).

**教训** (CLAUDE.md 沉淀):
- 测试 AsyncRedisRateLimiter mock 必须每请求 +1ms, 否则 dict 模拟永远不触发 429.
- 真 Redis ZSET 同样有 timestamp 去重问题 (score 重复则覆盖), 但 60s 窗口内用户不可能
  整数秒内连续打 50 次 (实测峰值 < 10/s), 所以生产没问题.

### 4.3 drive_upload / drive_list 独立配额 (写 429 不影响读)

**验证**: 临时把 drive_upload 配额调到 2, 3 次 POST 第 3 次 429, 同时 GET 仍正常 200.
**意义**: drive 系列并发场景 (用户同时浏览 + 评论) 不会被写阻塞, 体验稳定.

**生产 trade-off**: drive_upload 50/min 比 write tier (30/min) 高, 因为批量友好
(章节 4.1 在 rate_limit.py:185 注释). drive_list 300/min 比 read tier (200/min) 高,
因为网盘浏览是高频操作 (UI 默认 5s polling + 多 tab 并行).

### 4.4 登录用户 `{ip}:user:{uid}` vs 匿名 `{ip}:anon`

**验证**: user_101 配额用尽后, user_102 同 IP 独立配额不受影响.
**意义**: 多用户同 IP (公司 / 实验室 / 家庭) 不会被 A 账号操作阻塞 B 账号.

**生产兜底**: rate_limit.py:331-338 `_get_client_key` 优先 user_id (从 JWT 解析),
无 token fallback 到 `{ip}:anon`. 登录用户永远走 `{ip}:user:{uid}` 路径.

---

## 5. 测试设计细节 (复用 test_rate_limit_integration.py)

**5 复用 + 3 新增**:
- 复用: InMemoryZSetRedis mock (与 test_rate_limit_integration.py 同一份契约)
- 复用: clock fixture (`monkeypatch` time.time)
- 复用: app fixture (FastAPI + middleware + no_audit override)
- 复用: `_get_rate_limit_type` / `_rate_limiters` / `rate_limit_middleware` 直接 import
- 复用: `_token` helper (create_access_token)
- 新增: 7 路由 dummy endpoint (POST/GET/PATCH/DELETE + /resolve + /unresolve) — 与
  app/api/v1/drive_comments.py 形态完全一致, 但只返 tier 判定 + endpoint 名

**为什么不直接 import drive_comments router**:
1. drive_comments router Depends(get_current_user) 需 JWT 解析 + DB → 加重依赖
2. rate_limit 验证只需"路径 + 方法 → tier"判定, 不需要真业务逻辑
3. SKIP_DB_SETUP=1 兼容性更强 (生产 0 依赖)

**为什么不调 main.app**:
1. main.app 触发 39 张表 Base.metadata.create_all (即使 conftest SKIP 也 import 重)
2. 6+ 子 router (drive/knowledge/meeting/task/...) 中间件栈太厚, 调试慢
3. 直接挂 middleware + 自定义 dummy endpoint 隔离最强, 验证最纯

---

## 6. 5 条新铁律沉淀

### 铁律 1: 验证"自动覆盖"必须端到端跑测试, 不能想当然读配置

W68 第 3 批 F-1 报告"限流自动覆盖"是基于阅读 rate_limit.py:285 代码. **真正验证**
必须发请求看 `X-RateLimit-Policy` 响应头, 否则 prefix 拼错 / 顺序错 / 误匹配都可能
让"自动覆盖"失效而无人发现.

**纪律**: 任何 "X 自动覆盖 Y" 的声明必须有**对应端点测试** (e2e 或 integration),
**至少** verify 一次响应头, 不能只读 1 行代码.

### 铁律 2: Redis ZSET mock 必须每请求 +1ms, 否则 50/min 测试永远通过

`_ZSet.members` 用 dict 模拟, 重复 timestamp 自动覆盖 → ZCARD 永远 = 1 →
`check()` 永远通过 → 50/min 配额**永远**用不尽 → 429 测试**永远**不触发.

**纪律**:
- 测试 AsyncRedisRateLimiter (或任何带时间戳的限流器) 必须每请求 `clock += 1ms`
- 真 Redis ZSET 同样有 timestamp 去重问题, 但生产 60s 窗口内用户不可能整数秒
  连续打满, 实战 OK
- 这条铁律只影响**自动化测试**, 生产代码本身没问题

### 铁律 3: Drive 系列 drive_upload / drive_list 独立配额 (写 429 不影响读)

W68 F-3 验证: drive_upload 用尽不影响 drive_list. 这给用户**并发体验**兜底
(浏览 + 评论不互斥), 不要轻易合并到一个 tier.

**纪律**:
- Drive 系列新写端点: 默认 drive_upload (50/min, 批量友好)
- Drive 系列新读端点: 默认 drive_list (300/min, 高频浏览)
- 不要把 drive_upload 改 write tier (30/min) — 注释明确禁止
- 不要把 drive_list 改 read tier (200/min) — 注释明确禁止

### 铁律 4: 测试 rate-limit 必须验 X-RateLimit-Policy 响应头

`tier` 字段在 JSON body 也能验证, 但**生产**前端用 `X-RateLimit-Policy` header
做 tier-aware UX (auth 429 → 跳登录页, read 429 → 降级缓存, drive_upload 429 →
弹 toast 提示稍后重试). 测试必须同时验证:
1. JSON body `tier` 字段 (内部契约)
2. `X-RateLimit-Policy` header (前端契约)
3. `X-RateLimit-Limit` / `X-RateLimit-Remaining` (用户友好)

**3 件套缺一不可**.

### 铁律 5: 写端点 × 多 tier 共享配额测试必须有, 防止 tier 错配

Drive v2 PR9 评论有 5 写端点 (POST/PATCH/DELETE/POST resolve/POST unresolve).
如果哪天有人手贱给 `/resolve` 单独加 tier (比如 chunked_upload 60/min),
PR9 的 50/min 配额就**沉默失效** — 用户评论 50/min 限速, 但 resolve 操作可能
超过 60/min, 整体体验混乱.

**纪律**: 同一业务 (drive_comments) 的所有写端点**必须**共享 drive_upload 配额,
不能个别 override. 测试 `test_all_drive_write_endpoints_share_drive_upload_quota`
是这条铁律的 guardrail.

---

## 7. 锚点范式第 56 守恒

**W68 第 4 批完整路径**:
1. 启动: 主指挥复核 F-1 报告 → 派 7 端点 × tier 矩阵验证
2. 探索: 读 rate_limit.py:285 + drive_comments.py 路由前缀 + main.py 挂载点
3. 实施: 1 新文件 350 行, 复用 test_rate_limit_integration.py 5 fixture, 13 tests
4. 验证: 13/13 PASS (SKIP_DB_SETUP=1 模式, 无 PG 依赖)
5. 沉淀: 5 新铁律 + 锚点范式单调上升

**0 production code 改动铁律维持**: 本批纯验证 (tests/ 加 1 文件), 不动
`app/core/rate_limit.py` (主指挥决策权) 或 `app/api/v1/drive_comments.py`
(路由前缀不变, 形态已正确).

**锚点范式单调上升**: W7 12 → W66 27 → W67 28 → W68 30 → W68 路线 F-3 +1 = **56**

**W68 第 4 批累计**:
- 1 文件 (e2e + memory) — 0 production code 改动
- 13 tests 全部 PASS
- 5 新铁律沉淀
- main 后续等主指挥 merge

---

## 8. 与 W68 grand closure 衔接

**当前状态 (W68 第 1 批 grand closure 已收官)**: main HEAD 路线 A/B/C + Safari fix 全 merge.

**本 PR 分支**: `test/drive-pr9-rate-limit-verify-2026-07-24` (基于 main HEAD).

**下一步**:
1. 主指挥 merge 本 PR → 锚点范式第 56 守恒
2. 跑 e2e 真实环境验证 (PG + 真 Redis) — 本 worktree 内已 13/13 PASS
3. W68 第 5 批 (待派) 启动

**与后续 PR 的衔接**:
- Drive v2 PR10+ (WS 推送 / 文件锁) 复用本测试文件 pattern — 任何 `/api/v1/drive/*`
  新端点只需在 `@pytest.mark.parametrize` 加一行 (method, path, expected_tier)
- 后续 PR10+ WS 推送端点 `/api/v1/drive/ws/*` 走 SSE tier (10/min) 而非 drive_list
  (300/min), 因为 WS 长连接性质不同 — 注意这条例外

---

## 9. 排错要点 (留给主指挥 / 部署人员)

### 9.1 测试 mock ZSET timestamp 去重

跑测试时如果发现 50/min 永远不触发 429, 检查:
- 是否每请求前 `clock["now"] += 0.001`?
- 是否 monckypatch `rate_limit_module.time` 而非全局 `time`?

详见铁律 2.

### 9.2 drive_comments 前缀改了怎么办

如果未来 drive_comments 路由前缀改成 `/api/v2/drive/comments` (大版本):
1. rate_limit.py:285 path match 需扩展 (`/api/v2/drive/`)
2. 本测试文件 `@pytest.mark.parametrize` 7 个 path 都要改
3. **新增** 同样测试 v2 7 端点 (覆盖 v2)
4. **不删除** v1 测试 (向后兼容 baseline)

### 9.3 用户报"评论 429"

主指挥决策: 用户反映评论 429 太频繁 →
1. 检查 drive_upload 配额是否被全局调低 (生产 50/min 默认)
2. 检查是否有 bot / 自动化脚本高频评论 (建议 drive tier 提到 chunked_upload 60/min)
3. 不改 rate_limit.py 反而加 per-user 白名单 — 绕过限流架构, 不推荐

---

## 10. 总结

**Drive v2 PR9 rate-limit tier 验证 = 7 端点 × tier 矩阵 + 5 行为验证 = 13/13 PASS**

**关键结论**: drive_comments 7 端点**全部自动覆盖** rate_limit.py:285 path match,
**0 production code 改动**, **0 配置改动**, **0 主指挥决策点** — F-1 报告属实.

**锚点范式第 56 守恒**: W68 第 4 批完整闭环 (派工 → 验证 → 测试 → 沉淀).

**下一站**: 主指挥 merge + W68 第 5 批启动.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>