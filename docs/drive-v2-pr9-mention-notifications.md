# Drive v2 PR10 — 评论 @ Mention 提醒 (2026-07-24)

> **背景**: Drive v2 PR9 评论 thread (W68 第 3 批, commits `0bfe36751` + `04e06f6fd`)
> 已建 `drive_comments` 表 + 5 个 REST 端点. PR9 报告明示 "WS mention 推送不强制每 PR
> 集成, 留给 PR10". 本 PR10 (W68 第 5 批, 锚点范式第 63 守恒) 补齐:
>
> 1. **`app/services/mention_parser.py`** (新建, ~150 行) — @username 解析器
> 2. **`app/services/drive_event_publisher.py`** 新增 `publish_comment_mention()` —
>    每个 mentioned user 1 条 HIGH priority WS push
> 3. **`app/services/drive_comment_service.py` `create_comment()`** — caller 显式传
>    `mentions` 字段空时, 自动从 `content` 解析并触发 WS push

## 1. API 层 (无新增 REST 端点)

PR10 **不增 REST 端点** — 复用 PR9 的 `POST /api/v1/drive/comments` 即可.

caller 行为变化:
- **OLD (PR9)**: `mentions` 字段由 caller 显式传 (前端 markdown 解析)
- **NEW (PR10)**: `mentions` 字段可选; 不传或传空时, **后端 service 自动解析 content
  中的 `@username`**, 同样触发 WS push 通路

```http
POST /api/v1/drive/comments
Authorization: Bearer <token>
Content-Type: application/json

{
  "file_id": 42,
  "content": "@张三 @李四 看一下这个文件",
  "parent_id": null
  // mentions 字段可选 — 留空时自动解析
}
```

## 2. mention 解析规则

**regex**: `@([一-龥A-Za-z0-9_.\-]{1,32})` — 与 PR6 comment_service 完全一致的
`_MENTION_PATTERN`, 与前端 markdown 提取保持单源.

**3 路匹配** (大小写不敏感, 用 PostgreSQL `lower()` 函数):
1. `username` (例: `@du_tonghe` → `members.username = 'du_tonghe'` lower 比较)
2. `wechat_id` (例: `@WangTianZhi` → `members.wechat_id = 'WangTianZhi'` lower 比较)
3. `name` (例: `@张三` → `members.name = '张三'` 精确比较, 中文名特殊)

**优先级**: `username > wechat_id > name` (与 PR6 一致, 避免 1 个 @ 触发多个 user).

**去重**: 
- 同一文本出现多次 `@张三` → mentions 列表中只 1 个 entry
- caller 显式传 `mentions: [3, 3, 3]` → 服务端去重后写 `[3]`

**自 @ 排除**:
- author 自己 `@自己` → 自动从 mentions 列表移除 (避免自推)
- e.g. user 3 发 comment `"@张三 看一下"` (且 user 3 的 name=`张三`) → service 自动去掉

**不存在的用户**:
- `@GhostUser` 在 members 表无匹配 → 静默跳过 (不打日志噪音, 不抛错)
- 解析失败 (DB query 异常) → 防御性 `logger.warning + 返 []` (与 PR6 防御性一致)

## 3. WS 推送格式

每个 **mentioned user** 触发 **1 条独立** WS push (不批量合并 — 立即送达):

```json
{
  "type": "comment_mention",
  "comment_id": 42,
  "file_id": 10,
  "folder_id": null,
  "parent_id": null,
  "author_id": 100,
  "actor_id": 100,
  "mentioned_by": 100,
  "mentioned_user_id": 3,
  "snippet": "@张三 @李四 看一下这个文件",
  "priority": "high",
  "ts": "2026-07-24T10:00:00.123456+00:00"
}
```

**`payload` 字段**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | str | 固定 `"comment_mention"` (前端 switch case 路由) |
| `comment_id` | int | DriveComment.id (前端跳转链接用) |
| `file_id` | int? | 绑定的 file (与 PR9 同源字段) |
| `folder_id` | int? | 绑定的 folder (与 PR9 同源字段) |
| `parent_id` | int? | 嵌套回复的父评论 (None=顶层) |
| `author_id` | int | comment 作者 (= mentioned_by 通常) |
| `actor_id` | int | @ 的发起者 |
| `mentioned_by` | int | 与 actor_id 冗余 (前端 NotificationBell 卡片显示 "杜同贺 提到了你") |
| `mentioned_user_id` | int | 被 @ 的 user (这条 push 的接收者) |
| `snippet` | str | comment content 摘要 (≤80 char, 折行折叠) |
| `priority` | str | `"high"` (HIGH 是 W68 PR8d 优先级 3 档之一) |
| `ts` | str | ISO 8601 UTC timestamp |

**`snippet` 截断规则** (`extract_snippet()`):
1. `re.sub(r"\s+", " ", text.strip())` — 多空白折叠
2. `len ≤ max_chars` (默认 80) → 原样返回
3. `len > max_chars` → 截断 + `...`

**`priority=HIGH` 含义** (W68 PR8d 通知优先级 3 档):
- **HIGH**: 立即推送 (mention / @ 提醒) — 不允许合并
- **MEDIUM**: 普通活动 (文件上传 / 评论) — 可批量合并
- **LOW**: 系统提示 (清理 / 巡检) — 仅离线队列

`push_with_priority(HIGH)` 行为:
- 在线 → 立即 WS push
- 离线 → 入 Redis HIGH 队列 (`ws_notify:offline_queue:{user_id}:high`, FIFO, 7 天 TTL)
- reconnect 时 drain 队列, 让用户看到积压的 @ 提醒

## 4. 与 PR9 `comment_created` 推送的区别

| 维度 | `comment_created` (PR9) | `comment_mention` (PR10, 本次) |
|------|--------------------|-----------------------------|
| 收件人 | file/folder owner | **mentioned user** (每个 mentioned 独立 1 条) |
| 优先级 | MEDIUM | **HIGH** |
| 数量 | 1 条 / comment | N 条 / comment (N = mentions 列表长度) |
| 触发条件 | 任意评论 | 内容里有 `@username` |
| payload 关键字段 | `author_id`, `mentions` | `mentioned_user_id`, `mentioned_by`, `snippet` |

**并存**: 同一个 `create_comment()` 调用会触发 1 条 `comment_created` + N 条
`comment_mention`. 文件 owner 收到 1 条普通协作通知, 每个被 @ 的用户收到 1 条
@ 提醒.

## 5. 失败 best-effort 设计

任何 1 条 push 失败不影响其他, 不阻塞 caller:

```python
# drive_comment_service.py:create_comment() 片段
if resolved_mentions:
    try:
        from app.services.drive_event_publisher import publish_comment_mention
        from app.services.mention_parser import extract_snippet
        snippet = extract_snippet(content, max_chars=80)
        for uid in resolved_mentions:
            try:
                await publish_comment_mention(
                    self.db, comment,
                    actor_id=author_id,
                    mentioned_user_id=uid,
                    snippet=snippet,
                )
            except Exception as e:
                logger.warning(
                    f"[DriveCommentService.create_comment] mention 推送失败 "
                    f"uid={uid} (非阻塞): {e!r}"
                )
    except Exception as e:
        logger.warning(
            f"[DriveCommentService.create_comment] mention 推送整体失败 (非阻塞): {e!r}",
            exc_info=True,
        )
```

3 层防御:
1. **外层 try/except**: 任何 1 条 mention push 抛错, 不影响后续 user 推送
2. **内层每条 try/except**: 单条失败 log warning, 跳到下一条
3. **publisher 内层 try/except**: `push_with_priority` 抛错时 `_safe_push` 已捕获

## 6. 测试覆盖

`tests/test_drive_v2_pr10_mention.py` (新建, 14 个测试, 全过):

| # | 测试名 | 验证 |
|---|--------|------|
| 1 | `test_mention_single_user_payload_and_priority` | @ 单个用户 → 1 条 push + HIGH + payload 字段正确 |
| 2 | `test_mention_multiple_users_independent_pushes` | @ 多个用户 → N 条独立 push |
| 3 | `test_parse_mentions_three_way_match` | parse_mentions 3 路匹配 (username/wechat_id/name) |
| 4 | `test_parse_mentions_excludes_nonexistent_user` | @ 不存在用户 → 静默跳过 |
| 5 | `test_parse_mentions_excludes_self_mention` | @ 自己 → exclude_user_id 过滤 |
| 6 | `test_parse_mentions_dedup_repeat` | @ 重复 → 1 个 entry |
| 7 | `test_mention_priority_is_high_not_medium` | 优先级 = HIGH (非 MEDIUM) |
| 8 | `test_mention_push_failure_is_best_effort` | push 失败不阻塞 caller |
| 9 | `test_mention_self_mention_skipped` | publisher 跳过自推 |
| 10 | `test_extract_snippet_short_text` | 短文本原样 |
| 11 | `test_extract_snippet_long_text` | 长文本截断 |
| 12 | `test_extract_snippet_whitespace_folded` | 多余空白折叠 |
| 13 | `test_mention_and_created_are_independent_payloads` | comment_created ≠ comment_mention payload schema |
| 14 | `test_mention_ws_payload_passes_through_priority` | WS push priority=HIGH 正确传递 |

无 PostgreSQL 依赖 (`SKIP_DB_SETUP=1` + 全 mock), 与 W68 WS 测试一致.

## 7. 部署

**无需 alembic migration** (无 schema 改动).
**无需 Docker restart** (新代码是 service + publisher 模块, 静态 import).

```bash
# 仅本地测试验证:
cd /e/microbubble-agent/.claude/worktrees/agent-ac47fa639806e8775
SKIP_DB_SETUP=1 python -m pytest tests/test_drive_v2_pr10_mention.py -v
# Expected: 14 passed
```

**前端集成** (留给前端 PR):
- 监听 `ws.on('comment_mention', ...)` (与 `comment_created` 同 WS channel)
- NotificationBell 卡片: type=`comment_mention` 时高亮 + snippet + "查看文件" 跳转链接

## 8. 边界与限制

1. **post-comment edit 不重新触发 mention push** — `_to_schema()` 编辑时 `mentions` 字段
   重新检测的逻辑不在 PR10 范围 (PR9 设计的 author 主权意味着 edit content 不重新提
   mention). 如未来需要, 在 `update_comment()` 加同样的解析调用即可.
2. **mention 列表没去 `@all`** — 课题组 < 20 人, 暂不需要 @全员. 如未来需要, 改
   `parse_mentions()` 加 special token 即可.
3. **Snippet 用纯文本折叠, 不 strip markdown** — `**张三**` 也会保留星号. 推送卡片
   用纯文本显示, 前端渲染时再 strip (留待前端 PR).
4. **不持久化 `FileMention` 表** — PR10 走 push_with_priority HS+offline queue, 不
   走 PR6 的 `notification_service.create_bulk_mentions` (那条路径是 PR6 FileComment
   老表的持久化路径). 老 KB 评论的 mention 提醒仍走 PR6 路径.

---

## 9. 相关 PR 链接

- **PR9** (前置): Drive v2 PR9 — 文件/文件夹 评论 thread + WS 推送闭环
  (`docs/drive-v2-pr9-comments.md` + `docs/drive-v2-pr9-deployment.md`)
- **PR8d** (前置): 通知优先级 + 离线消息队列 (W68 a-1, commit `f5a4b2586`)
- **PR6-P4** (借鉴): 3 路匹配 username/wechat_id/name (与 PR10 mention_parser 一致)
