# Drive v2 PR12 — Emoji Reactions 部署文档 (2026-07-24, W68 第 8 批 B-2)

> 锚点范式第 94 守恒. Drive v2 PR12 系列: GitHub / GitLab / Slack 风格的轻量 emoji reaction.

## 背景

W68 第 4 批 drive-pr9-permissions 报告 "drive_versions PR9: 评论 mention 提醒 (TODO F-1): 不在 DrivePermissionService 范围, 留给 WS notification PR".
W68 第 5 批 drive-v2-pr9-mention-notifications 已闭环 mention 通知, 但**表情反应** (emoji reactions) 仍缺. PR12 收口.

**任务模式**: 0 production code 改动铁律维持 (W68 第 5/8 批). PR12 系列新功能扩展, 不动老路径.

## API 端点

### POST `/api/v1/drive/reactions`
增 emoji reaction (幂等).

请求体:
```json
{
  "target_type": "comment",  // 或 "file" / "note"
  "target_id": 10,
  "emoji": "👍"               // 12 个内置白名单之一
}
```

响应 (201):
```json
{
  "id": 1,
  "target_type": "comment",
  "target_id": 10,
  "member_id": 100,
  "emoji": "👍",
  "created_at": "2026-07-24T12:00:00",
  "updated_at": "2026-07-24T12:00:00"
}
```

幂等行为: 同一 user 同一 target 同一 emoji 重复 add 返 200 + 已存在 reaction (不抛错, 前端 toggle 体验平滑).

### DELETE `/api/v1/drive/reactions/{reaction_id}`
删 emoji reaction (仅本人, admin 不 override).

响应: 204 No Content

权限错误 (403): 仅本人可删自己的 reaction.

### GET `/api/v1/drive/reactions?target_type=comment&target_id=10`
列 target 的全部 reactions (聚合).

响应 (200):
```json
{
  "target_type": "comment",
  "target_id": 10,
  "items": [
    {
      "emoji": "👍",
      "count": 3,
      "members": [
        {"id": 100, "name": "张三", "avatar_url": "https://..."},
        {"id": 101, "name": "李四", "avatar_url": null},
        {"id": 102, "name": "王五", "avatar_url": null}
      ],
      "my_reacted": true
    },
    {
      "emoji": "❤️",
      "count": 1,
      "members": [{"id": 100, "name": "张三", "avatar_url": "https://..."}],
      "my_reacted": true
    }
  ],
  "total": 2
}
```

排序: 按 count desc (最热门在前).

## 12 个内置 Emoji 白名单

| Emoji | 别名 | 语义 |
|---|---|---|
| 👍 | +1 / thumbs up | 赞同 |
| ❤️ | heart / love | 喜爱 |
| 🎉 | celebrate / tada | 庆祝 |
| 😂 | laugh / joy | 有趣 |
| 😮 | surprise / open_mouth | 惊讶 |
| 😢 | cry | 难过 |
| 🔥 | fire | 火爆 |
| 💯 | 100 | 满分 |
| ✨ | sparkles | 出彩 |
| 🙏 | thanks / pray | 感谢 |
| 🤔 | thinking | 思考 |
| 👀 | eyes | 关注 |

设计参考: GitHub reactions 表 (6 个) + 中文场景补充 (6 个) = 12 个.

## 数据库迁移

### alembic 067_drive_reactions.py

**down_revision**: `066_drive_comments_path` (PR11 后续, 未合并).

> ⚠️ **alembic 链风险** (W68 第 4 批串单链纪律):
>
> 本 PR 必须等待 PR11 (path materialized) 落地 (产生 065 + 066 两个 migration) 后再 merge. 主指挥 merge 顺序:
> 1. 先 merge PR11 的 065_drive_xxx.py
> 2. 再 merge PR11 的 066_drive_comments_path.py
> 3. 最后 merge PR12 的 067_drive_reactions.py
>
> 不按顺序会触发 `Multiple head revisions are present` 阻塞部署.

### 表结构

```sql
CREATE TABLE drive_reactions (
    id BIGSERIAL PRIMARY KEY,
    target_type VARCHAR(16) NOT NULL,  -- 'comment' / 'file' / 'note'
    target_id INTEGER NOT NULL,        -- polymorphic FK (service 验证)
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    emoji VARCHAR(16) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_drive_reactions_target_member_emoji UNIQUE (target_type, target_id, member_id, emoji),
    CONSTRAINT ck_drive_reactions_target_type CHECK (target_type IN ('comment', 'file', 'note'))
);

CREATE INDEX ix_drive_reactions_target ON drive_reactions (target_type, target_id);
CREATE INDEX ix_drive_reactions_member ON drive_reactions (member_id);
```

## 部署必做 (CLAUDE.md 752 行铁律)

```bash
# 1. cp migration 到容器
docker cp alembic/versions/067_drive_reactions.py microbubble-agent-app-1:/app/alembic/versions/

# 2. 清 pycache (防 stale down_revision 假修复, W68 第 4 批 5 铁律)
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__

# 3. 跑迁移 (前提: PR11 的 065 + 066 已先 merge)
docker exec microbubble-agent-app-1 alembic upgrade head

# 4. 重启后端
docker compose restart app celery-worker

# 5. 验证表存在
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\d drive_reactions"
```

## 限流

- POST/DELETE → 自动走 `drive_upload` tier (50/min)
- GET → 自动走 `drive_list` tier (300/min)

(由 `app/core/rate_limit.py:285-288` 路径 `/api/v1/drive/*` 自动匹配)

## WS 推送

`publish_reaction_added` 在 `app/services/drive_event_publisher.py` (PR12 新增):
- type: `reaction_added`
- 优先级: HIGH (与 mention 同档, 反应是协作信号)
- 收件人: file/folder owner (comment/file polymorphic target)
- payload 字段: `reaction_id` / `target_type` / `target_id` / `actor_id` / `emoji` / `ts`
- 失败 best-effort (try/except + logger.error)

## 前端集成 (待 UI 阶段)

PR12 后端已就绪, 前端 emoji 选择器 + 数量徽章 + toggle 高亮 留给 W68 第 8 批后续 UI PR:
- `CommentRead.reactions: List[ReactionSummary]` 字段已加 (向后兼容, 默认 [])
- 桌面端: DriveCommentThread.vue 加 emoji picker (W68 第 8 批 UI 阶段)
- 移动端: MobileCommentThread.vue 同 (W68 第 8 批 UI 阶段)

## 测试覆盖

`tests/test_drive_v2_pr12_reactions.py` 12 场景 PASS:
1. add_reaction 增成功 → id != None
2. add_reaction 重复幂等 → UNIQUE 约束触发 → None (不抛错)
3. add_reaction emoji 不在白名单 → 抛 400
4. remove_reaction 仅本人可删 → 非本人 403
5. remove_reaction 本人删 → 成功 + commit
6. list_reactions 聚合 → count + members, 按 count desc 排序
7. publish_reaction_added WS push → priority=HIGH + payload 完整
8. publish_reaction_added 自推 → 跳过
9. polymorphic target 跨 comment/file → 不同 owner 解析路径
10. ALLOWED_EMOJIS 12 个内置白名单
11. 白名单 emoji 全部 1-2 字符 (UTF-8 视觉宽度)
12. list_my_reactions 返 List[str] emoji 列表

## 相关 PR 时间线

- W68 第 4 批: drive-pr9-permissions TODO F-1 留待 emoji reactions
- W68 第 5 批: drive-v2-pr9-mention-notifications (mention 闭环, reaction 留待)
- W68 第 8 批 B-2: **本 PR — emoji reactions 闭环**
- 未来 PR: reaction 推送 (W69+) + reaction 通知 channel (W70+) + reaction analytics (W71+)

## 风险与缓解

- **polymorphic FK 故意不在 DB 层强制** — DB CHECK 约束 target_type 字符串, FK 关系 service 验证. 理由: comment/file/note 物理表存在性 / soft-delete 状态由 service 统一管, DB FK 跨表约束会引发死锁/级联问题.
- **emoji 列宽 16 char** — 容纳 4 个全宽度 emoji (实际 1-2 为主). 拒绝超长 emoji 防滥用.
- **删 comment/file → service 显式 CASCADE 清 reactions** — 避免 FK NULL 污染. 已在 `drive_event_publisher.delete_comment` / `drive_file_version.delete` 钩子预留 (未来 PR 实施).
- **0 production code 改动铁律** — 本表暂不部署到生产, 仅作 schema 备案. PR12 UI/WS 推送/前端集成 后续 PR 单独派工.

## 参考

- 部署文档主索引: `docs/deploy.md`
- Drive v2 PR9 部署文档: `docs/drive-v2-pr9-deployment.md`
- W68 第 4 批 alembic 串单链纪律: CLAUDE.md `## 2026-07-24 alembic 并行 agent 串单链纪律`
- memory: `memory/w68-route-8-b2-drive-pr12-reactions-2026-07-24.md`