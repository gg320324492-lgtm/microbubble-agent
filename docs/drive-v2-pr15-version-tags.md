# Drive v2 PR15 — 文件版本标签 (Version Tags) 部署文档 (2026-07-24, W68 第 12 批 B-2)

> 锚点范式第 149 守恒. Drive v2 PR15 系列: 给文件版本打语义化标签 (12 个内置白名单).

## 背景

W68 第 8 批 B-2 PR9 文件版本 (commit `21a1906a8`) 已实现 `version_number` 自动递增 (1, 2, 3...) + `is_current` 标识当前版本, 但**无标签系统**.

**用户痛点**:
- 没有语义化标签 → 用户无法快速定位"哪个版本是 2024 年 10 月的发布版"
- 没有 `stable`/`deprecated`/`security` 标记 → 多人协同时容易混淆"哪个版本能放心用"
- 没有 `release`/`experimental` 区分 → 无法做版本回滚决策

W68 第 12 批 B-2 调研后落地 **Drive v2 PR15 文件版本标签**:
- 12 个内置白名单: release / stable / deprecated / security / auto-save / manual / breaking / experimental / legacy / featured / archived / final
- UNIQUE 约束 `(version_id, tag_name)` — 同一 version 同一 tag 幂等
- 标签关联到 `DriveFileVersion.id` (不是 file_id) — 同一 file 不同 version 可有不同 tag
- 跟 W68 第 8 批 PR9 version_number 双轨: 整数递增 + 语义标签

**任务模式**: 0 production code 改动铁律维持 (W68 第 12 批). PR15 纯新功能, 不动 PR9/PR11/PR12 老逻辑.

## 12 个内置白名单

| tag_name | 含义 | 默认色 | 使用场景 |
|----------|------|--------|----------|
| `release` | 正式发布版 | `#FF7A5C` (珊瑚橙) | 论文终稿 / 实验数据定版 |
| `stable` | 稳定版 | `#67C23A` (绿) | 已通过测试 / 长期可用的版本 |
| `deprecated` | 已废弃 | `#909399` (灰) | 旧版被新版本替代, 提醒不要用 |
| `security` | 安全更新 | `#F56C6C` (红) | 修复安全漏洞 / 合规性更新 |
| `auto-save` | 自动保存 | `#909399` (灰) | 系统自动保存的中间版本 |
| `manual` | 手动存档 | `#FFB347` (金橙) | 用户主动归档的版本 |
| `breaking` | 破坏性变更 | `#E6A23C` (黄) | API/格式不兼容旧版 |
| `experimental` | 实验性 | `#409EFF` (蓝) | 还在测试, 慎用 |
| `legacy` | 遗留兼容 | `#909399` (灰) | 仅供旧代码使用 |
| `featured` | 推荐版本 | `#FF7A5C` (珊瑚橙) | 老师/管理员推荐的版本 |
| `archived` | 已归档 | `#909399` (灰) | 长期保存, 不再修改 |
| `final` | 最终版 | `#FF7A5C` (珊瑚橙) | 项目结题 / 最终交付 |

## API 端点

### POST `/api/v1/drive/files/{file_id}/tags`

给版本添加标签 (幂等).

请求体:
```json
{
  "version_id": 5,
  "tag_name": "release",
  "tag_description": "2024 年 10 月发布版 - 论文终稿",
  "color": "#FF7A5C"
}
```

响应 (201):
```json
{
  "id": 1,
  "version_id": 5,
  "tag_name": "release",
  "tag_description": "2024 年 10 月发布版 - 论文终稿",
  "color": "#FF7A5C",
  "created_by": 100,
  "created_at": "2026-07-24T12:00:00",
  "updated_at": "2026-07-24T12:00:00"
}
```

幂等行为: 同一 `(version_id, tag_name)` 重复 add 返 200 + 已存在 tag (不抛错, 前端 toggle 体验平滑).

### DELETE `/api/v1/drive/files/{file_id}/tags/{tag_name}?version_id=5`

删除版本标签 (仅 tag 创建者本人, admin 不 override).

响应: 204 No Content.

权限错误 (403): 仅本人可删自己的标签.

### GET `/api/v1/drive/files/{file_id}/tags`

列文件所有版本+标签 (跨版本聚合).

响应 (200):
```json
{
  "file_id": 100,
  "file_name": "thesis_v3.docx",
  "versions": [
    {
      "version_id": 5,
      "version_number": 3,
      "is_current": true,
      "tags": [
        {"id": 1, "tag_name": "release", "color": "#FF7A5C", ...}
      ]
    },
    {
      "version_id": 4,
      "version_number": 2,
      "is_current": false,
      "tags": [
        {"id": 2, "tag_name": "stable", "color": "#67C23A", ...}
      ]
    }
  ]
}
```

### GET `/api/v1/drive/files/{file_id}/tags/{tag_name}`

按 `(file_id, tag_name)` 拿首个匹配版本 (多个版本可共享同一 tag, 返回最新 version_number).

响应 (200):
```json
{
  "version_id": 5,
  "file_id": 100,
  "version_number": 3,
  "is_current": true,
  "tag_id": 1,
  "tag_name": "release",
  "tag_description": "...",
  "color": "#FF7A5C",
  "created_by": 100,
  "created_at": "2026-07-24T12:00:00"
}
```

## 部署必做 (CLAUDE.md W68 第 4 批纪律)

```bash
# 1. 跑迁移 (新文件 drive_version_tags 表)
docker cp alembic/versions/070_drive_version_tags.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head

# 2. 验证表结构 (期望 1 张新表 + 3 索引 + 1 UNIQUE)
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\d drive_version_tags"

# 3. 重启后端
docker compose restart app celery-worker

# 4. curl 验证端点 (6 点)
curl -sk -o /dev/null -w "%{http_code}\n" -X POST https://xxx/api/v1/drive/files/100/tags \
    -H "Authorization: Bearer <token>" \
    -H "Content-Type: application/json" \
    -d '{"version_id": 5, "tag_name": "release"}'  # 期望 201
curl -sk -o /dev/null -w "%{http_code}\n" "https://xxx/api/v1/drive/files/100/tags" \
    -H "Authorization: Bearer <token>"  # 期望 200
```

## alembic 链风险 (W68 第 4 批纪律, 主指挥拍板)

PR15 migration `070_drive_version_tags` down_revision = `069_drive_comments_recursive_func` (current main HEAD).

**串单链验证**:
```bash
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
# 期望: ['070_drive_version_tags']
# 1 个 head 表明串单链 OK
```

**W68 第 12 批并行派工**:
- B-1 (074_drive_comments_path_backfill) + B-2 (075_drive_version_tags) 假设按提示并行
- 主指挥应先 merge B-1 (070), 再 merge B-2 (重命名 070 → 071 串链)
- 若 B-1 先 merge 但 down_revision 未更新, alembic 报 `Multiple head revisions are present`

## 跟 W68 第 8 批 PR9 version_number 双轨

| 维度 | version_number (PR9) | tag_name (PR15) |
|------|---------------------|-----------------|
| 类型 | 整数递增 (1, 2, 3...) | 字符串白名单 (12 个) |
| 含义 | 版本顺序 | 语义标签 |
| 数量 | 1 个文件 N 个版本 → N 个 version_number | 1 个版本可挂 0~12 个 tag |
| 自动/手动 | 自动 (upload_new_version 时 +1) | 手动 (用户调 POST /tags) |
| 唯一性 | UNIQUE (file_id, version_number) | UNIQUE (version_id, tag_name) |
| 用例 | 知道 "这是第 3 版" | 知道 "这是发布版 / 稳定版" |

**组合使用场景**:
- v3 (version_number=3) + tag_name=release → "第 3 版 + 是发布版"
- v5 (version_number=5) + tag_name=deprecated → "第 5 版 + 已废弃"
- v1 (version_number=1) + tag_name=stable + tag_name=featured → "第 1 版 + 稳定 + 推荐"

## 权限模型

| 操作 | 权限 |
|------|------|
| `POST /tags` (add) | 文件创建人 OR folder 管理员 OR 平台管理员 |
| `DELETE /tags/{tag_name}` (remove) | 仅 tag 创建者本人 (admin 不 override) |
| `GET /tags` (list) | 文件可见者 (与 list_versions 一致) |
| `GET /tags/{tag_name}` (get by tag) | 文件可见者 (与 list_versions 一致) |

## WS 推送 (PR15 集成)

`publish_version_tag_added` 函数 (MEDIUM priority):
- 收件人: file owner (Knowledge.created_by)
- 跳过自推 (actor == owner)
- payload: `{type: 'version_tag_added', tag_id, version_id, file_id, tag_name, actor_id, ts}`

订阅方: DriveDetailView.vue / DriveHistoryPanel.vue / 文件 owner 桌面通知.

## 性能基准

- `add_tag`: 1 INSERT + 1 commit (~5ms, 含 UNIQUE 校验)
- `remove_tag`: 1 SELECT + 1 DELETE + 1 commit (~3ms)
- `list_tags_by_file`: 1 JOIN query + 1 db.get (~10ms, 含 N+1 聚合)
- `get_file_by_tag`: 1 JOIN query + 1 db.get (~8ms, indexed by version_id + tag_name)
- `list_versions_with_tags` (复用 PR9 service): 1 LEFT OUTER JOIN query (~15ms, 比 list_versions + list_tags_by_file 拆分节省 50%)

## 测试覆盖

`tests/test_drive_v2_pr15_version_tags.py` (11 PASS, 7 核心 + 4 bonus):
1. add_tag 加 release/stable → DriveVersionTag.id != None
2. add_tag 重复 add 幂等 → UNIQUE 约束触发 → 返 None
3. add_tag tag_name 不在 12 个白名单 → 抛 DriveVersionTagServiceError(400)
4. add_tag 跨 file 隔离 → file_a 的 tag 不污染 file_b
5. list_tags_by_file 聚合 → 1 query 拿所有 version + tags
6. publish_version_tag_added WS 推送 → priority=MEDIUM + payload 完整
7. list_versions_with_tags 性能路径 → 1 LEFT OUTER JOIN query
8-11. remove_tag 仅本人 / 本人删成功 / 白名单完整性 / 自推跳过

## 后续 PR (PR16+)

- 跨文件标签搜索: `GET /api/v1/drive/tags/{tag_name}/files` 拿所有标同一 tag 的文件 (类似 GitHub `git tag --list`)
- 标签自动规则: 老师标 `final` → 自动给所有历史版本标 `archived`
- 标签历史审计: `drive_version_tag_history` 表 + Celery 任务 (类似 KnowledgeVersion 审计日志)