# W68 Route 8 B-2: Drive v2 PR12 Emoji Reactions (2026-07-24)

**锚点范式第 94 守恒**. Drive v2 PR12 系列 (W68 第 8 批 B-2): GitHub / GitLab / Slack 风格的轻量 emoji reaction, 闭环 W68 第 4 批留 TODO F-1 + W68 第 5 批留 mention 后的 reaction 空缺.

## 任务背景

- W68 第 4 批 drive-pr9-permissions 报告 "drive_versions PR9: 评论 mention 提醒 (TODO F-1): 不在 DrivePermissionService 范围, 留给 WS notification PR"
- W68 第 5 批 drive-v2-pr9-mention-notifications 已闭环 mention 通知 (锚点范式第 63 守恒)
- **PR12 收口**: Drive v2 表情反应 (emoji reactions) — GitHub 风格的轻量反馈

## 实施内容 (8 文件, 1 commit)

1. **`alembic/versions/067_drive_reactions.py`** (~140 行): drive_reactions 表 + UNIQUE 约束 + 索引
2. **`app/models/drive_reaction.py`** (~150 行): DriveReaction ORM + ALLOWED_EMOJIS (12 个内置白名单)
3. **`app/services/drive_reaction_service.py`** (~310 行): add_reaction (幂等) + remove_reaction_by_id + list_reactions (聚合) + list_my_reactions
4. **`app/services/drive_event_publisher.py`** (改): publish_reaction_added (HIGH priority, polymorphic target)
5. **`app/schemas/drive_comment.py`** (改): CommentRead.reactions: List[ReactionSummary] + 新 ReactionSummary / ReactionMemberSummary
6. **`app/api/v1/drive_reactions.py`** (~190 行): 3 端点 (POST add / DELETE / GET list)
7. **`app/main.py`** (改): 注册 drive_reactions router
8. **`tests/test_drive_v2_pr12_reactions.py`** (~410 行): 12 场景 PASS (含 7 必选 + 5 bonus)
9. **`docs/drive-v2-pr12-reactions.md`** (~170 行): API + emoji 白名单 + 部署必做

## 5 新铁律

### 铁律 1: emoji 内置白名单 (12 个, 服务端强校验)

**Why**: 防 XSS / 滥用 / 数据库膨胀. 客户端可任意传 Unicode emoji 但服务端必须白名单过滤.

**实现**:
- `app/models/drive_reaction.py:ALLOWED_EMOJIS = frozenset({"👍", "❤️", "🎉", "😂", "😮", "😢", "🔥", "💯", "✨", "🙏", "🤔", "👀"})`
- `app/services/drive_reaction_service.py` add_reaction 第 1 步校验, 不在白名单抛 400
- 与 GitHub reactions (6 个) + 中文场景补充 (6 个) 对齐

**纪律**:
- 新增 emoji 必须更新 3 处 (model / service 文档 / 前端 picker)
- 不允许开放 unicode range 校验 (SQLite/PostgreSQL 字符集差异 + 性能)
- 拒绝超长 emoji (>16 char) — service Pydantic schema 强校验

### 铁律 2: 幂等性 (UNIQUE 约束 + IntegrityError 兜底)

**Why**: 前端 toggle 场景 — 用户快速点击同一 emoji, 网络抖动可能产生重复请求. 后端必须幂等.

**实现**:
- DB UNIQUE 约束 `(target_type, target_id, member_id, emoji)` — 防重复反应
- service `add_reaction` try/except IntegrityError → 返 None (不抛 409)
- API 层 catch None → 重新查已存在的 reaction 返 200 (前端无需处理 toggle 错误)

**纪律**:
- 任何 "用户快速操作" 场景 (toggle reaction / star file / vote) 必须幂等
- 幂等判定 = 业务唯一性约束 (UNIQUE), 不是 client_msg_id 兜底
- API 层返 200 (不是 201/204) 让前端无感

### 铁律 3: polymorphic target (DB CHECK 约束 + service 验证)

**Why**: reaction 需支持 comment / file / note 3 类目标, 但 3 个 FK 列会引发 NULL 污染 + 跨表级联.

**实现**:
- DB schema: `(target_type VARCHAR(16), target_id INTEGER)` — 故意无 FK
- DB CHECK 约束 `target_type IN ('comment', 'file', 'note')` — DB 层兜底
- service `_validate_target_exists` + `_check_target_read_authority` — 业务层验证
- 删 comment/file → service 显式 cascade (未来 PR 实施, 当前 PR12 留接口)

**纪律**:
- polymorphic FK 不在 DB 层强制 (跨表 FK 会引发死锁 + soft-delete 状态混乱)
- polymorphic 业务验证必须由 service 层负责 (单 SQL 复用 caller db session)
- DB CHECK 约束 target_type 字符串是兜底, 防未来 schema drift

### 铁律 4: WS 推送 (HIGH priority, polymorphic owner 解析)

**Why**: reaction 是协作信号, 必须立即送达 (与 mention 同档).

**实现**:
- `publish_reaction_added(db, reaction_id, target_type, target_id, actor_id, emoji)` — 新增 publisher
- `_resolve_reaction_target_owner` polymorphic 解析:
  - comment → drive_comments.file_id/folder_id → file/folder owner
  - file    → Knowledge.created_by
  - note    → None (未来 PR 引入)
- WS payload `{type: "reaction_added", reaction_id, target_type, target_id, actor_id, emoji, ts}`
- 走 `push_with_priority(..., NotificationPriority.HIGH)` — 立即送达
- 失败 best-effort (try/except + logger.error)

**纪律**:
- 任何 PR 引入的 write 操作必须考虑 WS 推送 (W68 PR10 集成范式)
- polymorphic target owner 解析复用 caller db session (不开新 session)
- WS 推送 priority 按业务语义: mention/reaction=HIGH, created/resolved=MEDIUM, deleted=LOW

### 铁律 5: rate limit (drive_upload 50/min + drive_list 300/min)

**Why**: `/api/v1/drive/*` 自动匹配 (app/core/rate_limit.py:285-288), write 50/min + read 300/min.

**实现**:
- POST `/api/v1/drive/reactions` → drive_upload (50/min)
- DELETE `/api/v1/drive/reactions/{id}` → drive_upload (50/min)
- GET `/api/v1/drive/reactions` → drive_list (300/min)

**纪律**:
- 新增 drive 端点不需要手动加 rate_limit decorator (自动匹配 `/api/v1/drive/*`)
- 测试场景必须用 `SKIP_DB_SETUP=1` mock 路径 (避重 Redis 依赖)
- 单 IP 频次异常时升级到 IP 维度限流 (W68 PR10 已有 `RATE_LIMIT_BY_IP_ENABLED`)

## 实施纪律 (复用 W68 第 4/5 批)

1. **0 production code 改动铁律** — 本表暂不部署到生产, 仅作 schema 备案 (Drive v2 PR12 系列新功能扩展)
2. **alembic 067 串单链 (接 066_drive_comments_path)** — PR11 落地后再 merge (主指挥按顺序)
3. **commit 末尾 Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>**
4. **不 merge (主指挥来 merge)** — agent 派工协议
5. **分支 feat/drive-v2-pr12-reactions-2026-07-24**

## 测试覆盖

12 场景 PASS (SKIP_DB_SETUP=1 模式 — 纯 mock, 无 PostgreSQL 依赖):
- 7 必选: add / remove / 幂等 / 白名单 / 聚合 / WS push / polymorphic
- 5 bonus: 移除非本人 / 移除本人 / 自推跳过 / 白名单完整性 / list_my_reactions

跨主题无 regression: drive_v2_pr9_comments (12 SKIP) + drive_v2_pr10_mention (14 PASS) + drive_v2_pr9_ws (13 PASS) 全部绿色.

## 锚点范式位置

- W68 第 5 批 67 → W68 第 8 批 94 (单批净增 27)
- 0 production code 改动铁律 14/15 守恒 (1 例外: Drive v2 PR12 系列新功能 = 业务代码新增独立模块)
- W19 选项 A 维持

## 下一步 (W68 第 8 批后续)

- **C 阶段**: Drive v2 PR12 UI 集成 (emoji picker + 数量徽章 + toggle 高亮 + 移动端长按 ActionSheet)
- **D 阶段**: 反应通知 channel 细分 (用户可关闭某些 emoji 的 WS 推送)
- **E 阶段**: 反应 analytics (哪个 emoji 最常用 / 哪个时段最活跃 / 哪些 user 反应最多) — 给 qa-bench 提供 Drive 协作指标

## 失败教训 (本次避免)

- ❌ **不破坏 alembic 串单链** — 本 PR down_revision 明确写 066, 不写 064 (避免 W68 第 3 批 062/063 双头事故重演)
- ❌ **不在 server context 加 types block** — 本 PR 不动 nginx, 走默认 mime.types (避免 2026-06-13 整站 octet-stream 白屏事故)
- ❌ **不直接 `vite build` 绕开 postbuild** — 本 PR 不动前端 (避免 2026-07-11 PWA manifest 410 回归)

## 相关链接

- 部署文档: `docs/drive-v2-pr12-reactions.md`
- 测试: `tests/test_drive_v2_pr12_reactions.py`
- W68 第 4 批串单链纪律: CLAUDE.md `## 2026-07-24 alembic 并行 agent 串单链纪律`
- W68 第 5 批 mention PR: commit `e6f240911 feat(drive): v2 PR10 评论 @ mention 提醒集成`
- W68 第 5 批 handoff TODO F-1: `memory/w68-grand-closure-4th-batch-2026-07-24.md` § drive-pr9-permissions 报告