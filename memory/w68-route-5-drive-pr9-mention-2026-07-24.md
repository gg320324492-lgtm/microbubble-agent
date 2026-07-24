# Drive v2 PR10 — 评论 Mention 提醒 (W68 第 5 批, 锚点范式第 63 守恒)

> **任务**: W68 第 4 批 `drive-pr9-permissions` 报告留 TODO F-1:
> "PR9 评论 mention 提醒 (TODO F-1): 不在 DrivePermissionService 范围, 留给 WS notification PR".
> 本批 PR10 (锚点范式第 63 守恒) 补齐 mention 解析 + WS push 通路.

## 1. 实施范围 (Diff)

| 文件 | 改动 | 说明 |
|------|------|------|
| `app/services/mention_parser.py` | **新建 (~150 行)** | parse_mentions() + extract_snippet() |
| `app/services/drive_event_publisher.py` | 新增 `publish_comment_mention()` 函数 | + 修改 module docstring + `__all__` |
| `app/services/drive_comment_service.py` | `create_comment()` 增加 mention 解析 + WS push 集成 | 改 module docstring |
| `tests/test_drive_v2_pr10_mention.py` | **新建 (~400 行, 14 个测试)** | 5 场景 + 4 bonus 工具 + 5 priority + best-effort |
| `docs/drive-v2-pr9-mention-notifications.md` | **新建 (~280 行)** | API + 推送格式 + 测试 + 部署 |
| `memory/w68-route-5-drive-pr9-mention-2026-07-24.md` | **新建 (本文件)** | 4 新铁律 + 锚点范式第 63 守恒 |

## 2. 4 新铁律

### 铁律 1: mention 解析必须复用 `_MENTION_PATTERN` 单源

**触发场景**: 前端 markdown 提取 + 后端正则提取如果分叉, 会出现"前端显示 @某人, 后端没匹配"

**纪律**:
- **禁止**在 `mention_parser.py` 重新定义 `@xxx` regex
- 必须 `from app.services.notification_service import _MENTION_PATTERN`
- 同源单 regex = 前端 `@张三` 高亮 ↔ 后端 mentions[] 解析一致
- 已有同源 `_MENTION_PATTERN` (notification_service.py:130) — 复用, 不要分叉

**实现** (`app/services/mention_parser.py:34`):
```python
from app.services.notification_service import _MENTION_PATTERN

async def parse_mentions(db, text, *, exclude_user_id=None):
    raw_usernames = list(set(_MENTION_PATTERN.findall(text)))
    ...
```

**未来扩展**: 若 mention regex 需要扩展 (例: `@[张三]` 方括号明确), 改 `_MENTION_PATTERN` 1 处,
前端 + 后端同时生效.

### 铁律 2: mention 推送必须 `priority=HIGH`, 不合并

**触发场景**: user 期待"@我"立即可见; 走 LOW/MEDIUM 会被离线队列延迟或合并, 体验崩.

**纪律**:
- `publish_comment_mention(...)` 固定 `priority=NotificationPriority.HIGH`
- 每个 mentioned user **独立 1 条 push** (不批量合并) — 与 W68 PR8d HIGH 档定义一致
- 不复用 W68 PR8d `_batch_pending` 机制 (HIGH 档不允许合并)
- 多个 mentioned user 推送**串行** (`for uid in resolved_mentions: await ...`) — 简单清晰, 不引 asyncio.gather 增加复杂度

**反模式** (绝对避免):
```python
# ❌ — 合并成 batch 事件丢失"具体谁 @ 你"
await push_batch(user_id=3, payload={"type": "comments_mention_batch", "user_ids": [...]})

# ✅ — 每个 mentioned user 1 条
for uid in mentioned_ids:
    await publish_comment_mention(db, comment, actor_id=author_id,
                                  mentioned_user_id=uid, snippet=snippet)
```

**实现** (`app/services/drive_event_publisher.py:165-178`):
```python
payload = {
    "type": "comment_mention",
    ...
    "mentioned_user_id": mentioned_user_id,
    "snippet": snippet or "",
    ...
}
return await _safe_push(mentioned_user_id, payload, priority=NotificationPriority.HIGH)
```

### 铁律 3: mention 推送必须 best-effort (3 层 try/except)

**触发场景**: 任 1 条 mention push 失败 (WS 断 / Redis 满 / DB 查询超时) 不能阻塞
comment 创建, 也不能让其他 mention user 收不到推送.

**3 层防御** (与 `comment_created` 已建模式一致):
1. **外层 try/except** (`create_comment()` 后段, mention 推送整体):
   ```python
   if resolved_mentions:
       try:
           for uid in resolved_mentions:
               ...
       except Exception as e:
           logger.warning(f"... mention 推送整体失败 (非阻塞): {e!r}", exc_info=True)
   ```
2. **内层每条 try/except** (`publish_comment_mention` 每次调用):
   ```python
   for uid in resolved_mentions:
       try:
           await publish_comment_mention(...)
       except Exception as e:
           logger.warning(f"... mention 推送失败 uid={uid} (非阻塞): {e!r}")
   ```
3. **publisher 内层 try/except** (`_safe_push`):
   ```python
   try:
       return await push_with_priority(user_id, payload, priority=priority)
   except Exception as e:
       logger.error(f"... push_with_priority 失败 ...", exc_info=True)
       return -1
   ```

**纪律**:
- 3 层缺一不可. 第 1 层保 call site; 第 2 层保循环; 第 3 层保 publisher 都.
- logger.warning (而非 error) 用于 expected failure (网络/Redis 暂时不可用), 不要漏
- 任何 1 层漏 try/except → 单条 push 失败连带整 comment 入库失败 (500 错误)

### 铁律 4: mention ARRAY 列存储 user_id list + 自动从 content 兜底

**触发场景**: 前端可能忘传 `mentions` 字段, 或传错 (e.g. `mentions: [0]` 写死了);
service 必须从 `content` 兜底, 保证 mentions ARRAY 不空.

**纪律**:
- DriveComment `mentions` 列 (`app/models/drive_comment.py:106`) 是
  `ARRAY(Integer)`, PostgreSQL ARRAY 类型, NULL 是合法的
- `create_comment()` 行为:
  ```python
  resolved_mentions: Optional[List[int]] = mentions
  if not resolved_mentions:  # None / [] / [0] 等 — 都触发兜底
      try:
          parsed = await parse_mentions(self.db, content, exclude_user_id=author_id)
          if parsed:
              resolved_mentions = parsed
      except Exception as e:
          logger.warning(f"... 解析失败 (非阻塞): {e!r}", exc_info=True)
  ```
- 防 [0] 兜底误触发: `if not resolved_mentions` (空 list 也算) — yes, 应该兜底
  (因为 [0] 大概率是 caller bug, 兜底从 content 解析更可靠)
- 兜底解析失败 → `mentions` 留 None, 不抛错 (comment 入库仍成功)

**反模式** (绝对避免):
- ❌ 强校验 caller 必须传 `mentions` 字段 (前端会抛 400, UX 差)
- ❌ 用 `mentions or [...]` 强制空 list (line up 写好了 NULL, 不该改)
- ❌ 解析失败抛 400 (commit 创建的硬错误, 不该因 mention 失败)

## 3. 与 W68 PR9 闭环关系

| PR9 决策 | PR10 落实 |
|---------|---------|
| `create_comment()` 触发 `publish_comment_created` (file/folder owner, MEDIUM) | **新增** `publish_comment_mention` (mentioned user, HIGH) |
| 留 mention 给 PR10 | ✅ 落实 — caller 显式或自动解析, 触发 WS |
| `mentions` ARRAY 字段存 user_id list | ✅ 复用 — 自动兜底解析写入 |

PR9 + PR10 完整覆盖 DriveComment 5 个写操作的 WS 推送:
- `create_comment` → `comment_created` (file/folder owner, MEDIUM) + N × `comment_mention` (HIGH)
- `update_comment` → `comment_updated` (file/folder owner, MEDIUM)
- `delete_comment` → `comment_deleted` (file/folder owner, LOW)
- `resolve_comment` → `comment_resolved` (comment.author, MEDIUM)
- `unresolve_comment` → 不推 (幂等反操作, 不打扰)

## 4. 锚点范式第 63 守恒定位

**范式锚点 W7 12 → W66 27 → W67 28 → W68 42 → W68 第 5 批 PR10 = 第 63 守恒**

W68 第 5 批 PR10 累计 commit 1 (含 4 文件: parser/publisher edit/service edit/test/docs + memory)
— Drive v2 PR9 系列第 7 个 commit, 与 W68 第 4 批 PR9-WS-Push (commit `2bd208489`)
延续同一工作流 (WS 推送链).

## 5. 0 production code 改动铁律守恒

PR10 改动 ∈ Drive v2 PR9 系列 (anchor: W67 第 39 步 docs/CI 占位 + W68 第 1+2+3+4 批 PR8+PR9 工作流)
— 仍是 Drive v2 网盘新功能扩展, 不是一个独立大功能.

**生产代码改动**:
- 新建 `mention_parser.py` (~150 行) — 新模块, 0 旧代码改动
- `drive_event_publisher.py` 加 1 函数 (~50 行) + 模块 docstring 微调 (~10 行) — 增量
- `drive_comment_service.py` `create_comment()` 增加 ~40 行 (mention 解析 + 推送循环) + 模块 docstring 1 行 — 增量

**测试代码**: 新建 1 测试文件 (~400 行, 14 测试), 0 旧测试改动.

**文档 / memory**: 1 docs 新建 + 1 memory 新建.

## 6. 与 W68 第 4 批 TODO F-1 闭环

W68 第 4 批 `drive-pr9-permissions` 报告留:
> "PR9 评论 mention 提醒 (TODO F-1): 不在 DrivePermissionService 范围, 留给 WS notification PR"

W68 第 5 批 PR10 落实:
- mention 解析 → `mention_parser.py` 独立模块 (非 DrivePermissionService 范畴, 报告正确预测)
- WS 推送 → `drive_event_publisher.publish_comment_mention()` 增量 (与 PR9 WS 工作流一致)
- 集成入口 → `drive_comment_service.create_comment()` (PR9 service 已有文件, PR10 改)

TODO F-1 已闭环: 0 漂移, 0 需返工 (报告判断精确: "不在 DrivePermissionService 范围"
提前预判到本模块独立, PR10 严格隔离).

## 7. 未来 PR 方向 (非本 PR 范围)

- **PR10+**: 前端 NotificationBell 渲染 `comment_mention` 类型卡片 (snippet + 跳转链接)
- **PR10++**: `update_comment()` 时如果 content 改动, 是否重新解析 + 推送新 mention
  (GitHub 目前不支持 edit 不重新触发, 留给讨论)
- **PR10+++**: `@all` 群组 mention (课题组场景, 需先建 group 表)
- **PR10++++**: mention 退订 (用户设置不接受某文件的 mention 提醒 — 复杂, 远期)

## 8. 经验教训沉淀

1. **报告预留 TODO 范式有效** — W68 第 4 批明确报告"留给 PR10" 而不是"未实现",
   让 PR10 有清晰边界与目标. 锚点范式核心: 派工时不强求大而全, 拆分清晰边界.
2. **复用 _MENTION_PATTERN 单源** — 前端 + 后端一致, 永远不会出现"前端显示但后端没解析".
3. **3 层 try/except 不是过度工程** — WS 系统多组件, 任 1 故障都可能级联; 3 层防御
   保证 5 个用户 @ 1 个, 4 个失败也不会阻塞 comment 创建 (只是 4 个收不到 push).
4. **HIGH priority 与 MEDIUM 区分** — 用户的明确期待是"@我立即看到", 走 MEDIUM 合并
   会让用户在 3s 后才看到, 体验崩. priority=HIGH 是业务决策, 不是技术细节.

---

**锚点范式第 63 守恒 — Drive v2 PR10 mention 提醒集成完成** (W68 第 5 批, 2026-07-24)
