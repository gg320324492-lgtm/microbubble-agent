# MicroBubble Auth API Contract (Phase 1 冻结)

> **目的**: Desktop 客户端消费的 7 个 auth endpoint 完整契约，**所有改动自此冻结**。
> 任何后端 schema 改动（`app/api/v1/auth.py` + `app/schemas/auth.py`）必须同步更新本文件。
>
> **来源**: `app/api/v1/auth.py` + `app/schemas/auth.py` + `app/core/security.py` 实际代码 (2026-08-21 只读确认)。
>
> **消费者**: Desktop 客户端 `main/services/auth.service.ts` + `main/services/api/auth-api.service.ts`。

---

## 1. 端点清单

| Method | Path | 鉴权 | 用途 |
|--------|------|------|------|
| `POST` | `/api/v1/auth/login` | 否 | 用户名密码登录 |
| `POST` | `/api/v1/auth/refresh` | 否 (凭 refresh_token) | 续签 access_token |
| `GET` | `/api/v1/auth/me` | 是 (Bearer) | 当前用户档案 |
| `PUT` | `/api/v1/auth/profile` | 是 | 更新 profile 部分字段 |
| `POST` | `/api/v1/auth/change-password` | 是 | 修改自己的密码 |
| `POST` | `/api/v1/auth/reset-password` | 是 (admin) | 管理员重置他人密码 |
| `POST` | `/api/v1/auth/init-password` | 是 | 无密码用户首次设置 |

Base URL: `https://agent.mnb-lab.cn/api/v1`

---

## 2. 通用约定

### 2.1 鉴权 header

所有受保护 endpoint 都需:
```
Authorization: Bearer <access_token>
```

### 2.2 错误约定

FastAPI 风格，body 形如 `{ "detail": "..." }` 或 `[{ "loc": [...], "msg": "...", "type": "..." }]`。

| HTTP | 含义 | 业务 code |
|------|------|-----------|
| 400 | 校验失败（bad request） | `INVALID_INPUT` |
| 401 | 未认证 / 凭据错 / refresh 失效 | `INVALID_CREDENTIALS` / `TOKEN_EXPIRED` |
| 403 | 用户被禁用 / 非管理员 | `USER_DISABLED` / `FORBIDDEN` |
| 404 | 用户不存在 | `NOT_FOUND` |
| 429 | 限流（login 5/5min, 全部端点 5/min auth tier） | `RATE_LIMITED` |
| 5xx | 服务端异常 | `SERVER_ERROR` |
| 0 (network) | 网络层失败 | `NETWORK_ERROR` |

### 2.3 限流

| Endpoint | 限制 |
|----------|------|
| `POST /auth/login` | 每 IP 5 次 / 5 分钟（Redis ZSET, 跨 worker 共享, v31.2.6） |
| `/auth/me` `/auth/profile` ... | 全站 `auth` tier: 5/分钟 |
| `POST /auth/refresh` | 全站 `write` tier: 30/分钟 |

触发 429 时响应头自动带 `Retry-After: 300` (login) 或 `Retry-After: 60` (auth)。

---

## 3. 字段对齐: Desktop `UserInfo` ↔ Backend `UserInfo`

> ⚠️ **关键**: Phase 1-Impl-1 的 `UserProfile` 是 web 端 stale schema，不匹配后端。Phase 1-Impl-2 修。

| Field | Backend | Desktop (修后) | 说明 |
|-------|---------|--------------|------|
| `id` | `int` | `int` | 数据库主键 |
| `name` | `str` | `str` | 显示名（用户登录后 Profile 卡的标题） |
| `role` | `str` | `str` | 角色字符串: `"admin"` / `"member"` / ... 后端约定; 不复用 web 端的 `is_admin` 布尔 |
| `grade` | `str \| None` | `string \| null` | 研究生级别: `"professor"` / `"postdoc"` / `"phd"` / `"msc"` |
| `research_area` | `str \| None` | `string \| null` | 研究方向 |
| `email` | `str \| None` | `string \| null` | 邮箱 |
| `phone` | `str \| None` | `string \| null` | 电话 |
| `bio` | `str \| None` | `string \| null` | 简介 |
| `avatar` | `str \| None` | `string \| null` | 公网 URL（已通过 Nginx /minio/ 解析） |
| `is_active` | `bool` | `boolean` | 是否启用 |

**Desktop 不存**:
- ❌ `username` (登录用，登录后丢弃)
- ❌ `id_admin` (改为 `role === 'admin'` 派生)
- ❌ `avatar_url` (后端字段名是 `avatar`，不存别名)

---

## 4. LoginResponse schema (Phase 1-Impl-2 真实口径)

```ts
// 来自 app/schemas/auth.py LoginResponse
interface LoginResponse {
  access_token: string
  refresh_token: string  // 与 LoginResponse 同层，与 web 端 LoginResponse 形状不同
  token_type: 'bearer'
  user: UserInfo
}
```

**重要**: 与 web 端 schema 不同:
- web 端 `LoginResponse` (web src/api/auth.js 或类似): `{access_token, token_type, ...}`
- 后端 `LoginResponse` (实际): `{access_token, refresh_token, token_type, user}`

Phase 1-Impl-1 的 `TokenPair` 错误地自创 `expires_in`。**Phase 1-Impl-2 改用真实 TTL**（在 client 通过 JWT `exp` claim 计算）。

---

## 5. RefreshTokenResponse schema

```ts
// 来自 app/schemas/auth.py RefreshTokenResponse
interface RefreshTokenResponse {
  access_token: string
  token_type: 'bearer'
}
```

**关键 invariant**: refresh_token **不轮换**。
- 当前 access_token 过期 → POST /auth/refresh（旧 refresh_token 还在）
- 后端用同一 refresh_token 颁发新 access_token，旧 access_token 立即失效
- refresh_token 仍然 7-30 天（看 `REFRESH_TOKEN_EXPIRE_DAYS` setting），不轮换

Desktop 行为：refresh 成功后 keep 旧 refresh_token，**继续在 safeStorage 中加密存放**；只有 /auth/login（重新登录）才会拿到新 refresh_token。

---

## 6. Token 生命周期

| 阶段 | 内容 |
|------|------|
| **登录** | POST /auth/login → 后端 `create_access_token` (TTL = `ACCESS_TOKEN_EXPIRE_MINUTES`) + `create_refresh_token` (TTL = `REFRESH_TOKEN_EXPIRE_DAYS`) |
| **JWT payload** | `{"sub": str(user.id), "exp": <UTC>, "type": "access"\|"refresh"}` |
| **access_token 在 main 进程内存** | `currentAccessToken: string \| null` |
| **refresh_token 在 OS vault** | safeStorage.encryptString → base64 → electron-store `refresh_token_cipher` |
| **access 过期** | 客户端读到 `exp` 时间戳后, expiresAt 比对；过期 → 单飞 refresh |
| **access 401** | 任意业务请求 catch 401 → 触发单飞 refresh |
| **refresh 失效 (401/403)** | 清 vault + 当前 access → renderer 跳 /login |
| **登出** | main 清 currentAccessToken + vaultClear → renderer 跳 /login |

### 6.1 真实 TTL 数值（取决于 settings，不写死）

```python
# app/core/security.py
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS
```

> Desktop 不可知确切分钟数；通过 JWT `exp` claim 动态计算。

---

## 7. 单飞 Refresh 设计 (Phase 1-Impl-2 实施)

```
请求 N1 触发 401
       ↓
   是否有 in-flight refresh?
       ├─ No → 创建 refreshing = new Promise (refresh call to /auth/refresh)
       │           ↓
       │      成功？ → 更新 currentAccessToken → 排队 waiters resolve
       │      失败？ → 排队 waiters reject → 整个 session 强制 re-login
       └─ Yes → 把当前请求加到 waiters 列表 → 等 refreshing 完成 → 用新 token 重试
```

代码：`main/services/api/api.service.ts` 内的 `authRefresher` 单例。

---

## 8. 跨进程 token 流向（铁律）

```
  Backend FastAPI                   Main Process            Preload         Renderer
       │                                │                      │                │
       │── access_token + refresh_token ──→│── safeStorage       │                │
       │                                │   encryptString      │                │
       │                                │   + electron-store   │                │
       │                                │                      │                │
       │                                │── expiresIn (新形状) ──via IPC────────→│ Pinia auth
       │                                │── user: UserInfo    ──via IPC────────→│ Pinia user
       │                                │                      │                │
       │   后续业务请求:                  │                      │                │
       │◄── /api/v1/tasks ──── Bearer <access_token>            │                │
       │       │                  ▲ injected                  │                │
       │       │                  │                          │                │
       │       └─ 主进程 api.service.request(method, url, body) │                │
       │           ▲                                            │                │
       │           └── window.api.request(method, url, body) ───┘                │
       │                  ▲                                                     │
       │                  └── renderer 业务模块 (禁止 axios 直连后端) ────────────┘
```

**核心约束**（详见 docs/desktop-conversion/security.md §Token 未来存储原则）:
- refresh_token **永不进 renderer 内存**
- access_token 也**永不进 renderer 内存**（renderer 不直接调业务 endpoint）
- 所有鉴权请求 → window.api.request → main api.service → 注入 access_token → fetch 后端
- localStorage / sessionStorage / IndexedDB 永不含 token

---

## 9. 已知 desktop ↔ backend 兼容性项

| 兼容点 | Desktop 处理 |
|--------|-------------|
| 后端 `LoginResponse.user` 嵌套 vs web 端扁平 | 重写 desktop 端 LoginResponse 解析路径 |
| `id: int` vs web 端 `id: string` | 渲染端不做 ID 拼接比较 |
| `role: str` vs web 端 `is_admin: bool` | UI 用 `profile.role === 'admin'` 派生 |
| refresh 不轮换 | vault 永不变更 refresh_token（除非用户重登） |
| 无 `expires_in` 字段 | desktop 解析 JWT `exp` claim 算 expiresAt |
| avatar 是公网 URL（已通过 Nginx /minio/ 代理） | UI 直接 `<img :src="profile.avatar" />` |

---

## Status (2026-08-21 Phase 1-Impl-2 落地)

- ✅ 7 endpoint schema 确认
- ✅ Desktop UserInfo 字段对齐
- ✅ 单飞 refresh 设计 freeze
- ⏳ Phase 2+ 业务 endpoint 按需补 doc

---

📌 **维护规则**:
- 后端 schema 改动 → 必须先改本 doc，再实现 desktop
- Desktop 若发现后端字段差异 → PR 同时改本 doc
- 任何 token 相关调整 → 必须有 security.md + plan-v1.md 同步
