# 全站分级限流 (5 tier) — 文档

## TL;DR

5 tier 全站 API 限流，通过 [`app/core/rate_limit.py`](../app/core/rate_limit.py) 中间件 (`rate_limit_middleware`) 统一应用。

- **存储后端**：Redis ZSET 滑动窗口（v31.2.5，`AsyncRedisRateLimiter`）
- **持久化**：抗 `docker compose restart`，Redis 默认每分钟 RDB snapshot 保留计数
- **静默降级**：Redis 故障时 `check/record` 内部 `try/except`，不阻断业务请求
- **客户端维度**：登录用户 `{ip}:user:{uid}`，未登录 `{ip}:anon`（[v31.2.2](#v3122-bearer-token-轻量级解析)）
- **完整 endpoint × tier 矩阵**：见 [`docs/rate-limit-endpoint-matrix.md`](rate-limit-endpoint-matrix.md)

> **历史**：限流基建经过 v31.2 → 2.1 → 2.2 → 2.3 → 2.4 → 2.5 → 2.6 共 7 个版本迭代，沉淀于 [memory/rate-limit-redis-2026-06-26.md](../memory/rate-limit-redis-2026-06-26.md) + [app/core/rate_limit.py 源码注释](../app/core/rate_limit.py)。v31.2.6 起 middleware 用 `AsyncRedisRateLimiter` + `login_limiter` 用 Redis ZSET 双轨制。

---

## 5 tier 配置

| Tier | 限制 (max/min) | 窗口 (秒) | 适用场景 | 应用位置 | 关键路径 |
|------|---------------|-----------|----------|----------|----------|
| `auth` | 20 | 60 | 真认证动作（login/refresh/change-password/reset-password/init-password） | `/api/v1/auth/*` 白名单 | [`_AUTH_SENSITIVE_PATHS`](../app/core/rate_limit.py#L133-L140) |
| `write` | 30 | 60 | 写操作（POST/PUT/PATCH/DELETE 默认） | 任务/会议/项目/知识/成员等 | [`_get_rate_limit_type`](../app/core/rate_limit.py#L259-L261) |
| `read` | 200 | 60 | 读操作（GET 默认） | 所有非显式标注的 GET | [`_get_rate_limit_type`](../app/core/rate_limit.py#L262-L264) |
| `upload` | 10 | 60 | 单文件上传 | `/upload`、`/upload/meeting/{id}` 等含 `/upload` 的路径 | [`_get_rate_limit_type`](../app/core/rate_limit.py#L255-L257) |
| `sse` | 10 | 60 | SSE 长连接（chat/stream） | `/api/v1/chat/stream` | [`_SSE_PATH_RE`](../app/core/rate_limit.py#L168-L171) |

> ⚠️ **数值口径**：上表是 **v31.2.6 当前生产配置**（`app/core/rate_limit.py` 第 122-131 行 `_rate_limiters` 字典）。CLAUDE.md "代码质量规范" 段落里出现的 `auth:5次/分, write:30次/分, read:100次/分, upload:10次/分` 是早期 v31.2 设计草案，**不是当前实际值**。以源码为准。

### 扩展 tier（PR2.10 / 2026-07-02）

| Tier | 限制 | 应用 |
|------|------|------|
| `chunked_upload` | 60/min | `PUT /api/v1/meetings/{meeting_id}/audio-chunk`（听会边录边传，1s/片 = 60/min 录音） |
| `drive_upload` | 50/min | `POST/PUT/PATCH/DELETE /api/v1/drive/*` + `/api/v1/upload/*`（课题组网盘写） |
| `drive_list` | 300/min | `GET /api/v1/drive/*` + `/api/v1/upload/*`（高频浏览） |

### `login_limiter`（独立类，不在 middleware 里）

[`app/core/rate_limit.py:397`](../app/core/rate_limit.py#L397-L397) — **5 次/300 秒**，仅登录密码错误触发，与 middleware `auth` tier (20/min) 区别：

- middleware `auth` tier 覆盖所有 `_AUTH_SENSITIVE_PATHS`（5 端点）
- `login_limiter` 更严的 5/300s，**仅**登录密码错误触发（防爆破）

---

## 响应头（HTTP Headers）

每次请求 middleware 在响应上挂 4 个头（v31.2.3 加 `X-RateLimit-Policy`，v31.2.5 从 Redis 读 remaining）：

```http
X-RateLimit-Limit: 30           # 当前 tier 的 max_attempts
X-RateLimit-Remaining: 28       # 滑动窗口内剩余配额
X-RateLimit-Reset: 1700000060   # 窗口结束 epoch 秒
X-RateLimit-Policy: write       # 触发的 tier 名（auth/read/write/upload/sse/chunked_upload/drive_upload/drive_list）
```

**前端可基于 `X-RateLimit-Policy` 区分 tier-aware UX**：

- `auth` 429 → 跳登录页（防爆破）
- `read` 429 → 降级到本地缓存（前端 SW）
- `write` 429 → toast 提示"操作过于频繁，请稍后重试"
- `sse` 429 → 关闭流式连接 + 降级到非流式 chat

---

## 超限响应（429）

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 60

{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "请求过于频繁，请 60 秒后重试"
  }
}
```

- **HTTP 状态码**：`429 Too Many Requests`
- **`Retry-After` 头**：v31.2.6 加入，转发 `AsyncRedisRateLimiter.check()` 抛出的 headers
- **响应体**：JSON envelope `{error: {code, message}}`，与 [`app/core/exceptions.py` RateLimitException](../app/core/exceptions.py#L95-L104) 格式对齐

---

## 存储后端

### Redis ZSET 滑动窗口（v31.2.5 起）

[`AsyncRedisRateLimiter`](../app/core/rate_limit.py#L37-L115) — 真实滑动窗口：

```
ZSET key: "rl:{tier}:{client_key}"
score = timestamp (float)
value = timestamp (str)

check 流程:
  1. ZREMRANGEBYSCORE rkey 0 cutoff    # 清窗口外的旧 timestamp
  2. ZCARD rkey                          # 计数
  3. 若 >= max_attempts → raise 429
  4. 否则 ZADD 新 timestamp + EXPIRE 窗口+1s
```

**优势**：

- 抗 `docker compose restart`（Redis 默认 RDB 每分钟 snapshot）
- 跨实例共享（未来多 worker / 多 pod）
- 真实滑动窗口（vs 内存版 ZADD 后 N 个 timestamp 简单累加）

**劣势**：

- Redis 不可用时需 fallback（不能拒所有请求），`check/record` 内部 `try/except` 静默降级
- 单次 check 多 1 次 Redis round-trip (~1ms)

### `RateLimiter`（内存版，向后兼容保留）

[`app/core/rate_limit.py:9-L34`](../app/core/rate_limit.py#L9-L34) — 滑动窗口 in-memory dict，**当前已无 caller**，保留为向后兼容类。

- 优势：零依赖、快（<1ms check）
- 劣势：`docker compose restart` 全清零，攻击者赶在窗口重置前打满

---

## 配置

**当前实现**：所有 tier 数值**硬编码**在 [`app/core/rate_limit.py` 第 122-131 行 `_rate_limiters` 字典](../app/core/rate_limit.py#L118-L131)，**未**通过 `app/config.py` 的 settings 暴露。

```python
# app/core/rate_limit.py:122-131
_rate_limiters = {
    "auth": AsyncRedisRateLimiter(max_attempts=20, window_seconds=60),
    "write": AsyncRedisRateLimiter(max_attempts=30, window_seconds=60),
    "read": AsyncRedisRateLimiter(max_attempts=200, window_seconds=60),
    "upload": AsyncRedisRateLimiter(max_attempts=10, window_seconds=60),
    "sse": AsyncRedisRateLimiter(max_attempts=10, window_seconds=60),
    "chunked_upload": AsyncRedisRateLimiter(max_attempts=60, window_seconds=60),
    "drive_upload": AsyncRedisRateLimiter(max_attempts=50, window_seconds=60),
    "drive_list": AsyncRedisRateLimiter(max_attempts=300, window_seconds=60),
}
```

### 调整 tier 限制

如需调整限制（修改 → 部署 → 重启 app 即可生效）：

1. 编辑 `app/core/rate_limit.py:122-131`
2. 提交 + 推 PR
3. 部署：`docker compose restart app celery-worker`（CLAUDE.md 752 行铁律）
4. 验证：连续打 21 次 `/api/v1/auth/login`（超 20）→ 应 429

> ⚠️ 没有 `RATE_LIMIT_ENABLED` 总开关。如需临时关闭限流，可注释 `_get_rate_limit_type` 末尾 `return "read"` 改为 `return "unlimited"`（不推荐生产用，仅调试）。

---

## 客户端 IP 判定

[`app/core/rate_limit.py:get_client_ip`](../app/core/rate_limit.py#L400-L419) 按 XFF 优先级回退（v31.2.1 修复空 IP 兜底）：

| 优先级 | 来源 | 适用场景 |
|--------|------|----------|
| 1 | `X-Forwarded-For` header 第一段 | Nginx 反向代理（生产） |
| 2 | `request.client.host` | 直连 / 测试环境 |
| 3 | `"unknown"` 字面量 | 兜底，禁止返回空串 |

**v31.2.1 修复**：XFF 首段为空（如 `", 1.2.3.4"` / `"   "` / `",,,,,"`）时，旧实现 `.split(",")[0].strip()` 返空串 → 多请求共享空 IP key 触发共享配额。现统一兜底 `"unknown"`。

> ⚠️ **Nginx 必须注入 XFF**：`proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;` 否则生产 `request.client.host` 全是 `127.0.0.1` → 限流退化为全站共享 200/min（v31.2 修复）。

### IP 维度 vs User 维度

- **登录用户**：`{ip}:user:{uid}`（[`_get_client_key`](../app/core/rate_limit.py#L267-L278) 优先 user_id）
- **未登录/无效 token**：`{ip}:anon`
- **Token 解析**：[`_try_attach_user_id`](../app/core/rate_limit.py#L281-L312) 轻量级解析 Bearer JWT，**不查 DB**，即使 token 对应的 member 已删仍按 user_id 限流（真鉴权由 `Depends(get_current_user)` 在 endpoint 入口处理）

---

## 监控

### `agent_traces`（Celery 异步写表）

**当前**：限流事件**不**直接写 `agent_traces` 表 —— `rate_limit_middleware` 仅返回 429 + 写 `audit_log`（PR7 集成），**不**落 `agent_traces`。

### `audit_log`（同步落表，PR7 集成）

[`rate_limit_middleware` 第 366-386 行](../app/core/rate_limit.py#L366-L386) 在响应后调用 `app.core.audit_middleware._audit_request()`，**包含**限流通过的请求。**不包含**被 429 拒绝的请求（429 走 `JSONResponse` early return）。

### `rate_limit_blocked` 表

**当前**：**未实现**。每次 429 触发只在 Redis ZSET 留下 timestamp，无独立可观测表。

**TODO**：未来可加 `rate_limit_blocked` 表（`path/method/tier/ip/user_id/ts`）做按日 / 按 tier 维度的滥用检测，参考 admin/audit 现有 admin 端点模式。

### 日志（控制台）

`login_limiter` 触发 429 时不写日志（Redis 端记录）；middleware 触发 429 时 `JSONResponse` 异常路径不写日志（要排查需 grep Redis ZSET 计数）。

---

## 误判案例与修复

### substring 误匹配（v31.2.3 修复）

**症状**：旧代码用 `"/auth/" in path` substring 匹配，误命中 `/api/v1/authentication/...`（不带 `/` 后缀但含 `auth` 子串的路径），导致 authentication 类端点走 `auth` tier (20/min) 而非 `read` (200/min)。

**修复**：[`app/core/rate_limit.py:_is_under_auth`](../app/core/rate_limit.py#L186-L191) 改用 `path == "/api/v1/auth" or path.startswith("/api/v1/auth/")` prefix 匹配，要求路径以 `/api/v1/auth/` 开头或严格等于 `/api/v1/auth`，彻底消除 substring 误匹配风险。

### `/analytics` substring 误匹配（v31.2.2 修复）

**症状**：旧代码用 `substring "/analytics"` 匹配，命中 `/api/v1/auth/analytics/...` 嵌套路径，绕过 `/auth/` 限流。

**修复**：[`_ANALYTICS_PATH_RE`](../app/core/rate_limit.py#L159-L164) 改用 4 个精确路径 regex（`POST /analytics/search-event`、`PATCH /analytics/search-event/{int}/click`、`GET /analytics/stats`、`GET /analytics/logs`），未来加 `/api/v1/auth/analytics/export` 不会命中 regex，自动走下方 `/auth/` 细分。

### `/auth/me` 高频 polling 触发 429（2026-06-18 修复）

**症状**：用户强烈反馈 `/auth/me` 即便 200/min 也被 MainLayout / MeetingView 每次 reactive set value 都触发 `useUserStore` 重新拉，频繁 429。

**修复**：[`_AUTH_UNLIMITED_PATHS = {"/api/v1/auth/me"}`](../app/core/rate_limit.py#L146-L148) 完全豁免限流。理由：`/auth/me` 是只读 GET，需 JWT 鉴权（未带 token 401 直接拒），攻击成本高，无防护必要。

### SSE 长连接误走 `read` tier（v31.2.3 修复）

**症状**：`POST /api/v1/chat/stream` 是 SSE 长连接（一次连接占用几秒到几分钟），按 `read` tier 200/min 只能并发 200 个用户，**太少**。

**修复**：新增独立 `sse` tier (10/min)，[`_SSE_PATH_RE`](../app/core/rate_limit.py#L168-L171) 精确匹配 `/api/v1/chat/stream`。前端可基于 `X-RateLimit-Policy: sse` 区分流式限流 vs 普通读。

### 听会边录边传 30 秒触顶（2026-07-02 修复）

**症状**：`PUT /api/v1/meetings/{meeting_id}/audio-chunk` 是 MediaRecorder 每 1s 触发的分片上传，走 `write` tier 30/min → 30 秒录音就 429 触顶，用户看到"网络断开"误以为是断网。**实际是限流**。

**修复**：新增独立 `chunked_upload` tier (60/min)，[`_CHUNKED_UPLOAD_PATH_RE`](../app/core/rate_limit.py#L182-L184) 精确匹配。60/min = 1 分钟录音足够（单次听会很少超过 60 秒）。

---

## 常见问题（FAQ）

### Q: 测试环境怎么绕过限流？

**A**: 当前**没有**总开关。3 种临时绕法：

1. **改 tier 数值为超大值**（推荐，仅本地）：`app/core/rate_limit.py:122-131` 把 `max_attempts=1000000`
2. **Mock 整个 middleware**（pytest）：`monkeypatch.setattr("app.main.rate_limit_middleware", lambda r, c: c(r))`
3. **改 `_get_rate_limit_type` 返回 `"unlimited"`**（调试用，**不推荐**生产）

### Q: IP 怎么判定？

**A**: 优先 `X-Forwarded-For` header 第一段 → fallback `request.client.host` → 兜底 `"unknown"`。详见 [`get_client_ip`](../app/core/rate_limit.py#L400-L419)。

### Q: User 维度 vs IP 维度？

**A**: 登录用户走 `{ip}:user:{uid}`（按 user_id 独立配额），未登录/无效 token 走 `{ip}:anon`（按 IP 限流）。详见 [`_get_client_key`](../app/core/rate_limit.py#L267-L278) + [`_try_attach_user_id`](../app/core/rate_limit.py#L281-L312)。

### Q: 上传文件能走 `drive_upload` 还是 `upload`？

**A**:

- `/api/v1/drive/files/upload`、`/api/v1/upload/multipart/{init,complete,abort}` → `drive_upload` (50/min，批量友好)
- `/api/v1/upload`、`/api/v1/upload/meeting/{id}`、`/api/v1/drive/files/{id}/toggle-star` 等 → 仍走 `upload` (10/min) 或 `write` (30/min)

判断：路径含 `/api/v1/drive/` 或 `/api/v1/upload/` → `drive_*` tier；其他含 `/upload` → `upload` tier。

### Q: WebSocket 走限流吗？

**A**: **不走**。`/api/v1/ws/notifications` 是 WebSocket 端点，FastAPI middleware 自动跳过 WebSocket upgrade 请求（仅作用于 HTTP）。WS 心跳 / ping-pong 限流如需要应在 WS handler 内部实现（当前未实现）。

### Q: health 检查限流吗？

**A**: **不走**。`/health`、`/docs`、`/openapi.json` 在 [`rate_limit_middleware` 第 326-327 行](../app/core/rate_limit.py#L326-L327) 显式跳过，allow Kubernetes liveness / readiness probe 高频调用。

### Q: 429 后多久能恢复？

**A**: 等同于 `window_seconds`。当前所有 tier 窗口 60 秒 = 1 分钟后自动恢复。`Retry-After` header 返回秒数，前端可直接展示倒计时。

### Q: 不同 tier 配额独立吗？

**A**: **独立**。Redis key 是 `rl:{tier}:{client_key}` —— 不同 tier 用不同 ZSET，不会互相挤占配额。例如用户在 `read` 200/min 用满后仍可写 `write` 30/min。

---

## 部署必做

修改 `app/core/rate_limit.py` 后必须重启进程：

```bash
# CLAUDE.md 752 行铁律：所有 Python 模块改动必须重启
docker compose restart app celery-worker

# 验证限流生效：连续 21 次打 /auth/login → 第 21 次应 429
for i in {1..21}; do
  curl -sk -o /dev/null -w "%{http_code}\n" \
    -X POST https://xxx/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"wrong","password":"wrong"}'
done
# 期望: 前 20 次 401, 第 21 次 429
```

修改限流 tier 数值**不**需要跑 alembic migration（无 DB 改动）。

---

## 引用

- [`app/core/rate_limit.py`](../app/core/rate_limit.py) — 核心 middleware + tier 实例
- [`app/core/exceptions.py:RateLimitException`](../app/core/exceptions.py#L95-L104) — 异常类（429 envelope）
- [`memory/rate-limit-redis-2026-06-26.md`](../memory/rate-limit-redis-2026-06-26.md) — v31.2.5 Redis 持久化收官沉淀
- [`docs/rate-limit-endpoint-matrix.md`](rate-limit-endpoint-matrix.md) — 31 endpoint × 5 tier 完整矩阵
- [`tests/test_rate_limit_integration.py`](../tests/test_rate_limit_integration.py) — middleware 端到端 spec（13 case）
- [CLAUDE.md "代码质量规范" 段落](../CLAUDE.md#代码质量规范2026-06-04-升级) — 早期 v31.2 设计草案（注意数值非当前值）

---

**最后更新**：2026-07-23（Agent 6: 全站分级限流文档化 PR）