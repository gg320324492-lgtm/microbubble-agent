# 31 endpoint × 5 tier 矩阵

> **配套文档**：[`docs/rate-limit.md`](rate-limit.md) 介绍 5 tier 配置 / 响应头 / Redis 存储。本文档列出全站 31+ endpoint 各自命中的 tier + 客户端维度 + 备注豁免规则。

## TL;DR

| Tier | 限制 | endpoint 数 | 主要路径 |
|------|------|------------|----------|
| `auth` | 20/min | 5 | `/api/v1/auth/login`、`/refresh`、`/change-password`、`/reset-password`、`/init-password` |
| `write` | 30/min | 70+ | 任务/会议/项目/知识/成员/聊天历史等所有默认 POST/PUT/PATCH/DELETE |
| `read` | 200/min | 60+ | 所有默认 GET + `/auth/me` 等只读 |
| `upload` | 10/min | 4 | `/upload`、`/upload/meeting/{id}`、`/upload/{object_name}` |
| `sse` | 10/min | 1 | `/api/v1/chat/stream` |
| `chunked_upload` | 60/min | 1 | `PUT /meetings/{id}/audio-chunk` |
| `drive_upload` | 50/min | 14 | `/drive/files/{upload,init,chunk,complete,abort}` + `/upload/multipart/{init,complete,abort}` + 写操作 |
| `drive_list` | 300/min | 8 | `GET /drive/files`、`/starred`、`/trash`、`/storage-stats` 等 |
| `unlimited` (豁免) | ∞ | 5 | `/api/v1/auth/me` + 4 个 analytics 写 |

> **判定逻辑**：见 [`app/core/rate_limit.py:_get_rate_limit_type`](../app/core/rate_limit.py#L194-L264)。优先级：`unlimited` (whitelist) > `sse` regex > `chunked_upload` regex > `drive_*` 路径 > `analytics` regex > `/auth/` 细分 > `/upload` 子串 > method (POST/PUT/PATCH/DELETE = write, else read)。

---

## /api/v1/auth/* (7 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/auth/login` | POST | `auth` (20/min) | IP | 密码错 5 次额外触发 `login_limiter` (5/300s) |
| `/auth/refresh` | POST | `auth` (20/min) | user_id (refresh_token 解析) | |
| `/auth/change-password` | POST | `auth` (20/min) | user_id | |
| `/auth/reset-password` | POST | `auth` (20/min) | IP | |
| `/auth/init-password` | POST | `auth` (20/min) | IP | |
| `/auth/me` | GET | **unlimited** | — | v31.2.3 豁免，JWT 鉴权已防滥用 |
| `/auth/profile` | PUT | `write` (30/min) | user_id | |

> `_AUTH_SENSITIVE_PATHS` 白名单 5 个：login/refresh/change-password/reset-password/init-password → `auth` tier。
> `_AUTH_UNLIMITED_PATHS` 白名单 1 个：`/auth/me` → 完全豁免。

---

## /api/v1/tasks/* (12 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/tasks` | POST | `write` (30/min) | user_id | |
| `/tasks` | GET | `read` (200/min) | user_id | 列表查询，分页 |
| `/tasks/{task_id}` | GET | `read` (200/min) | user_id | |
| `/tasks/{task_id}` | PUT | `write` (30/min) | user_id | |
| `/tasks/{task_id}` | DELETE | `write` (30/min) | user_id | 软删除（30 天恢复期） |
| `/tasks/{task_id}/restore` | POST | `write` (30/min) | user_id | |
| `/tasks/{task_id}/permanent` | DELETE | `write` (30/min) | user_id | 永久删除 |
| `/tasks/batch-permanent-delete` | POST | `write` (30/min) | user_id | |
| `/tasks/stats/overview` | GET | `read` (200/min) | user_id | |
| `/dashboard/stats` | GET | `read` (200/min) | user_id | |
| `/reminders/pending-count` | GET | `read` (200/min) | user_id | |
| `/reminders/mark-read` | POST | `write` (30/min) | user_id | |
| `/reminders` | GET | `read` (200/min) | user_id | |
| `/debug/wechat-notify/{member_name}` | GET | `read` (200/min) | IP | 仅 debug |
| `/debug/sync-wechat-ids` | POST | `write` (30/min) | user_id | 仅 debug |

---

## /api/v1/meetings/* (16 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/meetings` | POST | `write` (30/min) | user_id | |
| `/meetings` | GET | `read` (200/min) | user_id | |
| `/meetings/detect-speakers` | POST | `write` (30/min) | user_id | 声纹检测 |
| `/meetings/analyze-text` | POST | `write` (30/min) | user_id | |
| `/meetings/{meeting_id}` | GET | `read` (200/min) | user_id | |
| `/meetings/{meeting_id}/minutes` | GET | `read` (200/min) | user_id | |
| `/meetings/{meeting_id}/generate-minutes` | POST | `write` (30/min) | user_id | |
| `/meetings/{meeting_id}/analyze` | POST | `write` (30/min) | user_id | |
| `/meetings/{meeting_id}` | PUT | `write` (30/min) | user_id | |
| `/meetings/{meeting_id}` | DELETE | `write` (30/min) | user_id | |
| `/meetings/{meeting_id}/speaker-map` | POST | `write` (30/min) | user_id | |
| `/meetings/{meeting_id}/polish-text` | POST | `write` (30/min) | user_id | |
| `/meetings/{meeting_id}/polish-text-batch` | POST | `write` (30/min) | user_id | |
| `/meetings/{meeting_id}/transcript-speaker` | PATCH | `write` (30/min) | user_id | |
| `/meetings/{meeting_id}/analytics` | GET | `read` (200/min) | user_id | |
| `/meetings/{meeting_id}/end-call` | POST | `write` (30/min) | user_id | 腾讯会议结束 |
| `/meetings/{meeting_id}/related` | GET | `read` (200/min) | user_id | |
| `/meetings/{meeting_id}/related` | POST | `write` (30/min) | user_id | |
| `/meetings/{meeting_id}/agenda` | PATCH | `write` (30/min) | user_id | |
| `/meetings/{meeting_id}/progress` | GET | `read` (200/min) | user_id | |

---

## /api/v1/meetings/* 录音子路径 (8 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/meetings/start-recording` | POST | `write` (30/min) | user_id | |
| `/meetings/{meeting_id}/upload-audio` | POST | `upload` (10/min) | user_id | 整文件上传 |
| `/meetings/{meeting_id}/audio-chunk` | PUT | **`chunked_upload` (60/min)** | user_id | **MediaRecorder 1s/片**，60/min = 1分钟录音 |
| `/meetings/{meeting_id}/merge-chunks` | POST | `write` (30/min) | user_id | |
| `/meetings/{meeting_id}/upload-status` | GET | `read` (200/min) | user_id | |
| `/meetings/{meeting_id}/stop-recording` | POST | `write` (30/min) | user_id | |
| `/meetings/{meeting_id}/audio` | GET | `read` (200/min) | user_id | 音频回放 |
| `/meetings/{meeting_id}/cancel-recording` | POST | `write` (30/min) | user_id | |

> ⚠️ **chunked_upload tier 关键**：`_CHUNKED_UPLOAD_PATH_RE` 精确匹配 `PUT /api/v1/meetings/{int}/audio-chunk`。未来加其他分片上传端点（如视频分片）需扩展 regex。

---

## /api/v1/projects/* (7 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/projects` | POST | `write` (30/min) | user_id | |
| `/projects` | GET | `read` (200/min) | user_id | |
| `/projects/{project_id}` | GET | `read` (200/min) | user_id | |
| `/projects/{project_id}` | PUT | `write` (30/min) | user_id | |
| `/projects/{project_id}` | DELETE | `write` (30/min) | user_id | |
| `/projects/{project_id}/milestones` | POST | `write` (30/min) | user_id | |
| `/projects/{project_id}/milestones` | GET | `read` (200/min) | user_id | |

---

## /api/v1/knowledge/* (35+ endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/knowledge` | POST | `write` (30/min) | user_id | |
| `/knowledge` | GET | `read` (200/min) | user_id | |
| `/knowledge/stats` | GET | `read` (200/min) | user_id | |
| `/knowledge/auto-intake-summary` | GET | `read` (200/min) | user_id | |
| `/knowledge/categories` | GET | `read` (200/min) | user_id | |
| `/knowledge/tags` | GET | `read` (200/min) | user_id | |
| `/knowledge/graph` | GET | `read` (200/min) | user_id | |
| `/knowledge/entities/graph` | GET | `read` (200/min) | user_id | |
| `/knowledge/{knowledge_id}/graph` | GET | `read` (200/min) | user_id | |
| `/knowledge/stats/rich` | GET | `read` (200/min) | user_id | |
| `/knowledge/{knowledge_id}/related` | GET | `read` (200/min) | user_id | |
| `/knowledge/search/semantic` | GET | `read` (200/min) | user_id | |
| `/knowledge/upload` | POST | `upload` (10/min) | user_id | 含文件 |
| `/knowledge/from-chat` | POST | `write` (30/min) | user_id | |
| `/knowledge/entities` | GET | `read` (200/min) | user_id | |
| `/knowledge/entities/{entity_id}` | GET | `read` (200/min) | user_id | |
| `/knowledge/formulas` | GET | `read` (200/min) | user_id | |
| `/knowledge/formulas/domains` | GET | `read` (200/min) | user_id | |
| `/knowledge/formulas/calculate` | POST | `write` (30/min) | user_id | |
| `/knowledge/formulas/categories` | GET | `read` (200/min) | user_id | |
| `/knowledge/hypotheses` | POST | `write` (30/min) | user_id | |
| `/knowledge/hypotheses` | GET | `read` (200/min) | user_id | |
| `/knowledge/hypotheses/{hypothesis_id}` | GET | `read` (200/min) | user_id | |
| `/knowledge/hypotheses/{hypothesis_id}/validate` | POST | `write` (30/min) | user_id | |
| `/knowledge/review-queue` | GET | `read` (200/min) | user_id | |
| `/knowledge/{knowledge_id}` | GET | `read` (200/min) | user_id | |
| `/knowledge/{knowledge_id}` | PUT | `write` (30/min) | user_id | |
| `/knowledge/{knowledge_id}` | DELETE | `write` (30/min) | user_id | |
| `/knowledge/{knowledge_id}/download` | GET | `read` (200/min) | user_id | |
| `/knowledge/taxonomy/emerging` | GET | `read` (200/min) | user_id | |
| `/knowledge/taxonomy/network` | GET | `read` (200/min) | user_id | |
| `/knowledge/qa` | POST | `write` (30/min) | user_id | RAG 问答 |
| `/knowledge/research` | POST | `write` (30/min) | user_id | 自主研究 |
| `/knowledge/research/gaps` | POST | `write` (30/min) | user_id | |
| `/knowledge/health/contradictions` | GET | `read` (200/min) | user_id | |
| `/knowledge/health/duplicates` | GET | `read` (200/min) | user_id | |
| `/knowledge/health/staleness` | GET | `read` (200/min) | user_id | |
| `/knowledge/{knowledge_id}/reanalyze` | POST | `write` (30/min) | user_id | |
| `/knowledge/{knowledge_id}/reformat` | POST | `write` (30/min) | user_id | |
| `/knowledge/{knowledge_id}/scan-layout` | POST | `write` (30/min) | user_id | |
| `/knowledge/{knowledge_id}/layout` | GET | `read` (200/min) | user_id | |
| `/knowledge/reason` | POST | `write` (30/min) | user_id | |
| `/knowledge/{knowledge_id}/review` | POST | `write` (30/min) | user_id | |
| `/knowledge/{knowledge_id}/images` | GET | `read` (200/min) | user_id | 多模态 |
| `/knowledge/{knowledge_id}/extractions` | GET | `read` (200/min) | user_id | 多模态 |
| `/knowledge/{knowledge_id}/extract-multimodal` | POST | `write` (30/min) | user_id | 多模态 |
| `/knowledge/reprocess-status/{task_id}` | GET | `read` (200/min) | user_id | |

---

## /api/v1/chat/* (5 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/chat` | POST | `write` (30/min) | user_id | 非流式 |
| `/chat/image` | POST | `write` (30/min) | user_id | |
| `/chat/file` | POST | `write` (30/min) | user_id | |
| `/chat/stream` | POST | **`sse` (10/min)** | user_id | **SSE 长连接**，独立 tier |
| `/chat/history/{session_id}` | GET | `read` (200/min) | user_id | 历史查询（chat_history 已迁移至 chat/sessions） |

> `/chat/stream` 是核心 SSE 端点：`_SSE_PATH_RE` 精确匹配 → `sse` tier 10/min。前端 `X-RateLimit-Policy: sse` 可识别并降级到非流式 chat。

---

## /api/v1/chat/sessions/* + /chat/sync + /chat/shares/* (13 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/chat/sessions` | GET | `read` (200/min) | user_id | 会话列表 |
| `/chat/sessions` | POST | `write` (30/min) | user_id | |
| `/chat/sessions/search` | GET | `read` (200/min) | user_id | |
| `/chat/sessions/{session_id}` | GET | `read` (200/min) | user_id | |
| `/chat/sessions/{session_id}` | PATCH | `write` (30/min) | user_id | |
| `/chat/sessions/{session_id}` | DELETE | `write` (30/min) | user_id | 软删除（30 天保留） |
| `/chat/sessions/{session_id}/messages` | GET | `read` (200/min) | user_id | |
| `/chat/sessions/{session_id}/messages` | POST | `write` (30/min) | user_id | |
| `/chat/sessions/{session_id}/export` | GET | `read` (200/min) | user_id | |
| `/chat/sessions/{session_id}/share` | POST | `write` (30/min) | user_id | 创建分享链接 |
| `/chat/sessions/{session_id}/shares` | GET | `read` (200/min) | user_id | |
| `/chat/sessions/{session_id}/shares/{share_id}` | DELETE | `write` (30/min) | user_id | |
| `/chat/sync` | POST | `write` (30/min) | user_id | localStorage 迁移 |
| `/chat/shares/{token}` | GET | `read` (200/min) | IP (公开链接) | |

---

## /api/v1/members/* (7 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/members` | POST | `write` (30/min) | user_id | 管理员 |
| `/members` | GET | `read` (200/min) | user_id | |
| `/members/{member_id}` | GET | `read` (200/min) | user_id | |
| `/members/{member_id}` | PUT | `write` (30/min) | user_id | |
| `/members/{member_id}` | DELETE | `write` (30/min) | user_id | |
| `/members/me/notification-preferences` | GET | `read` (200/min) | user_id | |
| `/members/me/notification-preferences` | PUT | `write` (30/min) | user_id | |

---

## /api/v1/voice/* (4 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/voice/asr` | POST | `write` (30/min) | user_id | 语音识别 |
| `/voice/tts` | POST | `write` (30/min) | user_id | |
| `/voice/chat` | POST | `write` (30/min) | user_id | |
| `/voice/voices` | GET | `read` (200/min) | user_id | |

---

## /api/v1/voiceprint/* (6 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/voiceprint/enroll/{member_id}` | POST | `write` (30/min) | user_id | 声纹录入 |
| `/voiceprint/enrolled` | GET | `read` (200/min) | user_id | |
| `/voiceprint/fingerprints` | GET | `read` (200/min) | user_id | |
| `/voiceprint/{member_id}/history` | GET | `read` (200/min) | user_id | |
| `/voiceprint/search` | GET | `read` (200/min) | user_id | |
| `/voiceprint/test` | POST | `write` (30/min) | user_id | |

---

## /api/v1/upload/* (3 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/upload` | POST | `upload` (10/min) | user_id | |
| `/upload/meeting/{meeting_id}` | POST | `upload` (10/min) | user_id | |
| `/upload/{object_name}` | DELETE | `write` (30/min) | user_id | |

---

## /api/v1/upload/multipart/* (3 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/upload/multipart/init` | POST | **`drive_upload` (50/min)** | user_id | |
| `/upload/multipart/complete` | POST | **`drive_upload` (50/min)** | user_id | |
| `/upload/multipart/abort` | POST | **`drive_upload` (50/min)** | user_id | |

> 路径含 `/api/v1/upload/` 触发 `drive_upload` tier (50/min，比标准 `upload` 10/min 宽松，批量友好)。

---

## /api/v1/drive/folders/* (10 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/drive/folders` | POST | **`drive_upload` (50/min)** | user_id | |
| `/drive/folders` | GET | **`drive_list` (300/min)** | user_id | |
| `/drive/folders/tree` | GET | **`drive_list` (300/min)** | user_id | |
| `/drive/folders/{folder_id}/children-stats` | GET | **`drive_list` (300/min)** | user_id | |
| `/drive/folders/{folder_id}` | GET | **`drive_list` (300/min)** | user_id | |
| `/drive/folders/{folder_id}` | PUT | **`drive_upload` (50/min)** | user_id | |
| `/drive/folders/{folder_id}` | DELETE | **`drive_upload` (50/min)** | user_id | |
| `/drive/folders/{folder_id}/restore` | POST | **`drive_upload` (50/min)** | user_id | |
| `/drive/folders/trash/list` | GET | **`drive_list` (300/min)** | user_id | |

---

## /api/v1/drive/files/* (24 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/drive/files/upload` | POST | **`drive_upload` (50/min)** | user_id | |
| `/drive/files` | GET | **`drive_list` (300/min)** | user_id | |
| `/drive/files/{file_id}` | GET | **`drive_list` (300/min)** | user_id | |
| `/drive/files/{file_id}` | PUT | **`drive_upload` (50/min)** | user_id | |
| `/drive/files/{file_id}` | DELETE | **`drive_upload` (50/min)** | user_id | |
| `/drive/files/{file_id}/restore` | POST | **`drive_upload` (50/min)** | user_id | |
| `/drive/files/{file_id}/extract-to-kb` | POST | **`drive_upload` (50/min)** | user_id | |
| `/drive/files/{file_id}/toggle-star` | POST | **`drive_upload` (50/min)** | user_id | |
| `/drive/starred` | GET | **`drive_list` (300/min)** | user_id | |
| `/drive/trash` | GET | **`drive_list` (300/min)** | user_id | |
| `/drive/trash/permanent-delete` | POST | **`drive_upload` (50/min)** | user_id | |
| `/drive/files/batch-soft-delete` | POST | **`drive_upload` (50/min)** | user_id | |
| `/drive/files/batch-restore` | POST | **`drive_upload` (50/min)** | user_id | |
| `/drive/files/batch-move` | POST | **`drive_upload` (50/min)** | user_id | |
| `/drive/files/batch-update-visibility` | POST | **`drive_upload` (50/min)** | user_id | |
| `/drive/storage-stats` | GET | **`drive_list` (300/min)** | user_id | |
| `/drive/files/{file_id}/download` | GET | **`drive_list` (300/min)** | user_id | |
| `/drive/files/batch-download` | POST | **`drive_upload` (50/min)** | user_id | |
| `/drive/files/{file_id}/share-link` | POST | **`drive_upload` (50/min)** | user_id | |
| `/drive/files/{file_id}/share-link` | DELETE | **`drive_upload` (50/min)** | user_id | |
| `/drive/files/{file_id}/visibility` | PUT | **`drive_upload` (50/min)** | user_id | |
| `/drive/files/instant-upload` | POST | **`drive_upload` (50/min)** | user_id | |
| `/drive/files/{file_id}/versions` | GET | **`drive_list` (300/min)** | user_id | |
| `/drive/files/{file_id}/versions/{version_id}/restore` | POST | **`drive_upload` (50/min)** | user_id | |
| `/drive/storage-quota` | GET | **`drive_list` (300/min)** | user_id | |
| `/drive/files/upload/init` | POST | **`drive_upload` (50/min)** | user_id | chunked upload init |
| `/drive/files/upload/{upload_id}/chunk/{chunk_index}` | PUT | **`drive_upload` (50/min)** | user_id | chunked upload chunk |
| `/drive/files/upload/{upload_id}` | GET | **`drive_list` (300/min)** | user_id | chunked upload status |
| `/drive/files/upload/{upload_id}/complete` | POST | **`drive_upload` (50/min)** | user_id | chunked upload complete |
| `/drive/files/upload/{upload_id}/abort` | POST | **`drive_upload` (50/min)** | user_id | chunked upload abort |
| `/drive/files/{file_id}/thumbnail` | GET | **`drive_list` (300/min)** | user_id | |
| `/drive/mobile-feed` | GET | **`drive_list` (300/min)** | user_id | |

---

## /api/v1/file-requests/* (5 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/file-requests` | POST | `write` (30/min) | user_id | |
| `/file-requests/my` | GET | `read` (200/min) | user_id | |
| `/file-requests/{request_id}/deactivate` | POST | `write` (30/min) | user_id | |
| `/file-requests/{token}/info` | GET | `read` (200/min) | IP (公开链接) | |
| `/file-requests/{token}/submit` | POST | `write` (30/min) | IP (公开链接) | |

---

## /api/v1/notifications/* (4 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/notifications` | GET | `read` (200/min) | user_id | |
| `/notifications/unread-count` | GET | `read` (200/min) | user_id | 高频 polling |
| `/notifications/{mention_id}/read` | POST | `write` (30/min) | user_id | |
| `/notifications/read-all` | POST | `write` (30/min) | user_id | |

> ⚠️ `/notifications/unread-count` 是高频 polling（顶栏铃铛每 10s 拉一次），走 `read` tier 200/min = ~3.3 RPS 足够。如果前端频繁 429，可考虑加 unlimited 白名单（参考 `/auth/me` 模式）。

---

## /api/v1/dashboard/* (3 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/dashboard/project-stats` | GET | `read` (200/min) | user_id | |
| `/dashboard/refresh-stats` | POST | `write` (30/min) | user_id | |
| `/dashboard/summary` | GET | `read` (200/min) | user_id | |

---

## /api/v1/translation/* (1 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/translate` | POST | `write` (30/min) | user_id | |

---

## /api/v1/tencent-meeting/* (7 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/tencent-meeting/create` | POST | `write` (30/min) | user_id | |
| `/tencent-meeting/create-and-link` | POST | `write` (30/min) | user_id | |
| `/tencent-meeting/list` | GET | `read` (200/min) | user_id | |
| `/tencent-meeting/{meeting_id}/info` | GET | `read` (200/min) | user_id | |
| `/tencent-meeting/{meeting_id}/cancel` | POST | `write` (30/min) | user_id | |
| `/tencent-meeting/{meeting_id}/end` | POST | `write` (30/min) | user_id | |
| `/tencent-meeting/webhook` | POST | `write` (30/min) | IP (腾讯回调) | |

---

## /api/v1/memories/* (3 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/memories` | GET | `read` (200/min) | user_id | |
| `/memories/{memory_id}` | PUT | `write` (30/min) | user_id | |
| `/memories/{memory_id}` | DELETE | `write` (30/min) | user_id | |

---

## /api/v1/mobile/* (3 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/mobile/dashboard` | GET | `read` (200/min) | user_id | 移动端聚合 |
| `/mobile/feed` | GET | `read` (200/min) | user_id | 移动端 feed |
| `/mobile/album-auto-backup` | POST/GET | `write`/`read` (30/200/min) | user_id | 移动端相册备份 |

---

## /api/v1/admin/* + /api/v1/admin/audit/* (4 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/admin/agent-traces` | GET | `read` (200/min) | user_id | 仅管理员 |
| `/admin/agent-traces/{trace_id}` | GET | `read` (200/min) | user_id | |
| `/admin/audit` | GET | `read` (200/min) | user_id | |
| `/admin/audit/summary` | GET | `read` (200/min) | user_id | |

---

## /api/v1/analytics/* (4 endpoint) — 部分豁免

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/analytics/search-event` | POST | **unlimited** | user_id | v31.2.2 豁免，前端每次搜索 2 次埋点 |
| `/analytics/search-event/{event_id}/click` | PATCH | **unlimited** | user_id | event_id 必须 int |
| `/analytics/stats` | GET | `read` (200/min) | user_id | |
| `/analytics/logs` | GET | `read` (200/min) | user_id | |

> `_ANALYTICS_PATH_RE` 精确匹配 4 个端点：POST/PATCH 写完全豁免，GET 走 `read` tier 200/min 防滥用。

---

## /api/v1/wechat/* (4 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/wechat/callback` | GET | `read` (200/min) | IP (微信回调) | 微信验证 |
| `/wechat/callback` | POST | `write` (30/min) | IP (微信回调) | |
| `/wechat/kf/callback` | GET | `read` (200/min) | IP (微信客服回调) | |
| `/wechat/kf/callback` | POST | `write` (30/min) | IP (微信客服回调) | |

---

## /api/v1/ws/notifications (1 endpoint)

| Endpoint | Method | Tier | 客户端维度 | 备注 |
|----------|--------|------|------------|------|
| `/ws/notifications` | WebSocket | **不限流** | — | FastAPI middleware 不作用于 WebSocket upgrade |

---

## 系统端点（豁免）

| Endpoint | Method | Tier | 备注 |
|----------|--------|------|------|
| `/health` | GET | **不限流** | Kubernetes liveness probe |
| `/docs` | GET | **不限流** | Swagger UI |
| `/openapi.json` | GET | **不限流** | OpenAPI schema |

---

## 引用

- [`app/core/rate_limit.py`](../app/core/rate_limit.py) — 核心 middleware + tier 实例 + 判定逻辑
- [`docs/rate-limit.md`](rate-limit.md) — 5 tier 文档（配置 / 响应头 / Redis / FAQ）
- [`memory/rate-limit-redis-2026-06-26.md`](../memory/rate-limit-redis-2026-06-26.md) — v31.2.5 收官沉淀

---

**最后更新**：2026-07-23（Agent 6: 全站分级限流文档化 PR）