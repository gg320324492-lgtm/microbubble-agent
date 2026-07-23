# W68 路线 5 — 第 5 批 hot-fix #16 + #17 + #18 综合记录 (2026-07-24)

> **锚点范式第 71-74 守恒** — W68 第 5 批 3 个 hot-fix 收官. 修真 bug 不动 DriveFileVersion.uploader_id 真字段.

## hot-fix #16 + #17 (Drive v2 PR9 后服务期 hot-fix)

### hot-fix #16: drive_version_diff_service import 修复

**触发**: W68 第 4 批 F-2+ drive_version_diff_service 在 `_check_file_visibility_for_diff` 内 `from app.models.knowledge import Knowledge` 后调 `Knowledge.uploader_id`, 触发 AttributeError.

**修复**: 改用 `Knowledge.created_by` (Knowledge ORM 真字段).

### hot-fix #17: drive_event_publisher WS push import 修复

**触发**: W68 第 4 批 F-3 drive_event_publisher WS push 在 push 版本创建事件时错把 `version.uploader_id` 替换为 `version.created_by`, 但 DriveFileVersion ORM 真有 `uploader_id` (没 created_by).

**修复**: 回滚到 `version.uploader_id` (DriveFileVersion 真字段).

### #16 + #17 教训

| ORM 模型 | 字段 | 出处 |
|----------|------|------|
| `Knowledge` | `created_by` | `app/models/knowledge.py:64` |
| `DriveFileVersion` | `uploader_id` | `app/models/drive_file_version.py:96` |

**含义**: service 涉及两表时, 不能凭"印象"复制粘贴字段名. 跨表引用时**必须**先 `inspect` ORM 模型确认.

## hot-fix #18: Knowledge.uploader_id → created_by (跨会话 agent 报 bug)

> 详见 [`memory/w68-route-5-hotfix-knowledge-uploader-id-2026-07-24.md`](./w68-route-5-hotfix-knowledge-uploader-id-2026-07-24.md) 完整记录

**触发**: 跨会话 agent 报告 #16+#17 修复引入 3 个新 bug 引用 Knowledge.uploader_id, 主指挥核实后确认真实字段是 created_by.

**6 处修复**:

| 文件 | 行 | 类型 | 修复 |
|------|---|------|------|
| `app/services/drive_comment_service.py` | 94 | 代码 | `file_row.uploader_id` → `file_row.created_by` |
| `app/services/drive_permission_service.py` | 253 | 代码 | `file_row.uploader_id` → `file_row.created_by` |
| `app/services/drive_permission_service.py` | 21 | 注释 | `file.uploader_id` → `file.created_by` |
| `app/services/drive_permission_service.py` | 229 | 注释 | `file.uploader_id` → `file.created_by` |
| `app/services/drive_comment_service.py` | 167 | 注释 | `file.uploader_id` → `file.created_by` |
| `app/services/drive_event_publisher.py` | 77 | 注释 | `Knowledge.uploader_id` → `Knowledge.created_by` |

**未动** (保留正确):
- `app/models/drive_file_version.py:96` `uploader_id` — 真字段
- `app/services/drive_event_publisher.py:185/196/220/231` — DriveFileVersion ORM, uploader_id 正确
- `app/services/drive_version_diff_service.py` — #16 已修, 此处 created_by 正确
- `app/services/drive_version_service.py` — DriveFileVersion ORM, uploader_id 正确

## W68 第 5 批 hot-fix 范式总结

**总收官**: 3 hot-fix (#16 + #17 + #18) 全闭环, 锚点范式第 71-74 守恒.

| hot-fix | 触发 | 修复 | 教训沉淀 |
|---------|------|------|----------|
| #16 version_diff | Knowledge.uploader_id 错引 | 改 created_by | ORM 字段引用必查 models |
| #17 ws_push | 反向误改 DriveFileVersion | 回滚到 uploader_id | DriveFileVersion.uploader_id ≠ Knowledge.created_by |
| #18 comment+permission | #16+#17 引入新 bug 引用 | 改 6 处 (2 代码 + 4 注释) | drive_comment + drive_permission chain 验证缺失 |

**铁律汇总** (3 hot-fix 共沉淀):

1. **ORM 字段引用必查 models** — `inspect(Knowledge)` 验证
2. **drive_comment + drive_permission chain 验证缺失** — 同一文件多次派工必强制 chain 检查
3. **DriveFileVersion.uploader_id ≠ Knowledge.created_by** — 跨表引用必须先确认
4. **跨会话 agent 报 bug 必须主指挥核实** — 不核实 = 派错或漏修

## 验证清单 (3 hot-fix 综合)

```bash
# 1. 所有 ORM 字段访问不抛 AttributeError
python -c "from app.models.knowledge import Knowledge; k=Knowledge(created_by=1); print(k.created_by)"
python -c "from app.models.drive_file_version import DriveFileVersion; v=DriveFileVersion(uploader_id=1); print(v.uploader_id)"

# 2. service import 不报错
python -c "from app.services.drive_comment_service import _check_file_comment_authority; from app.services.drive_permission_service import DrivePermissionService; from app.services.drive_event_publisher import publish_comment_event; print('OK')"

# 3. e2e (静态 ORM 字段 + DB 集成)
SKIP_DB_SETUP=1 python -m pytest tests/test_drive_v2_pr10_knowledge_field_authority.py -v

# 4. typing imports CI (152 文件 0 错误)
bash scripts/check_typing_imports.sh

# 5. 残留错误引用 (期望空输出)
grep -rn 'Knowledge\.uploader_id\|file_row\.uploader_id\|file\.uploader_id' app/services app/api
```

## commit + push

- 分支: `fix/w68-5th-batch-knowledge-uploader-id-2026-07-24` (hot-fix #18)
- 前序分支 (hot-fix #16 + #17): `fix/w68-route-5-drive-version-diff-import-2026-07-24` (假设已建)
- push: origin
- 不 merge (主指挥来 merge)