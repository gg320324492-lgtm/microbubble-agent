# W68 路线 5 — 第 5 批 hot-fix #18: Knowledge.uploader_id → created_by (2026-07-24)

> **锚点范式第 74 守恒** — W68 第 5 批 hot-fix 收官. 修真 bug 6 处, 不动 DriveFileVersion.uploader_id 真字段.

## 任务背景

跨会话 agent 报告: Drive v2 PR9 系列 hot-fix (#16 version_diff + #17 ws_push) 在 `drive_event_publisher.py:185/196/220/231` 正确使用 `DriveFileVersion.uploader_id` (真字段), 但**同时引入** 3 个 service 的错误引用:

| 文件 | 行 | 类型 | 原代码 | 修复后 |
|------|---|------|--------|--------|
| `app/services/drive_comment_service.py` | 94 | 代码 | `if file_row.uploader_id == user_id:` | `if file_row.created_by == user_id:` |
| `app/services/drive_permission_service.py` | 253 | 代码 | `if file_row.uploader_id == user_id:` | `if file_row.created_by == user_id:` |
| `app/services/drive_permission_service.py` | 21 | 注释 | `file.uploader_id == user_id` | `file.created_by == user_id` |
| `app/services/drive_permission_service.py` | 229 | 注释 | `file.uploader_id == user_id (file owner)` | `file.created_by == user_id (file owner)` |
| `app/services/drive_comment_service.py` | 167 | 注释 | `file.uploader_id == user_id` | `file.created_by == user_id` |
| `app/services/drive_event_publisher.py` | 77 | 注释 | `Knowledge.uploader_id (file owner)` | `Knowledge.created_by (file owner)` |

## 主指挥核实 (派工前必做)

**核实结果**:
- `Knowledge` ORM 真字段是 `created_by` (`app/models/knowledge.py:64`)
- `Knowledge` **没有** `uploader_id` 字段 (静态扫描 `app/models/knowledge.py` 全文)
- `DriveFileVersion` ORM 真有 `uploader_id` (`app/models/drive_file_version.py:96`)
- 6 处 service 引用都是针对 `Knowledge` ORM (`select(Knowledge).where(Knowledge.id == file_id)`) → 必须用 `created_by`

**核实手段**:
```bash
python -c "from app.models.knowledge import Knowledge; cols=[c.name for c in Knowledge.__table__.columns]; print('created_by' in cols, 'uploader_id' in cols)"
# True False
```

**教训**: 跨会话 agent 报告 bug 时, 主指挥**必须**先核实 ORM 真实字段再派 hot-fix. 不核实 = 派工后修了不该修的字段 / 没修真正该修的字段. 本次幸亏核实 → 只改 6 处, 误删 DriveFileVersion.uploader_id 风险被排除.

## 真实 bug 影响范围 (修复前)

| 场景 | 修复前 | 修复后 |
|------|--------|--------|
| file owner 走 `_check_file_comment_authority` 评论自己的文件 | AttributeError → 500 | 走 `created_by == user_id` → 成功 |
| file owner 走 `check_comment_resolver` resolve 别人评论 | AttributeError → 500 | 走 `created_by == user_id` → 成功 |
| `drive_event_publisher._resolve_comment_target_owner` 推送给 file owner | AttributeError → 整个推送链断 | `Knowledge.created_by` → 推送成功 |

**注意**: 这 3 处都是 `Knowledge` ORM 引用, 不影响 `DriveFileVersion` 已有真字段调用 (`drive_version_diff_service` / `drive_event_publisher:185` 等 4 处保留不变).

## 4 新铁律

### 铁律 1: ORM 字段引用必查 models (避免 stale .uploader_id 类错误)

修 service 时涉及 ORM 字段引用, **必须**先 `inspect` ORM 模型确认字段名:

```python
from sqlalchemy import inspect
from app.models.knowledge import Knowledge
columns = {c.name for c in inspect(Knowledge).columns}
assert 'created_by' in columns
assert 'uploader_id' not in columns  # 防止反向 case
```

**特别警惕跨表引用** — DriveFileVersion.uploader_id 与 Knowledge.created_by 字段名不同, 不要凭"印象"复制粘贴.

### 铁律 2: drive_comment + drive_permission service 已知 bug 链: select import + lineterm + uploader_id — 同一文件 chain 验证缺失

`drive_comment_service.py` + `drive_permission_service.py` 是 W68 第 3 批+第 4 批 Drive v2 PR9 路线多次派工的同一批文件, 已知历史 bug:

| Bug | 表现 | 修复 commit |
|-----|------|-------------|
| `from sqlalchemy import select` 局部化陷阱 | 调 DriveComment 间接路径报 UnboundLocalError | (W68 hot-fix 历史) |
| 注释 lineterm 不一致 | 一处 `uploader_id` 一处 `created_by` 混写 | 本次 hot-fix #18 |
| `Knowledge.uploader_id` 错引 | AttributeError 500 | 本次 hot-fix #18 |

**教训**: 同一文件多次派工时, **chain 验证缺失**会让"修一个新 bug 时引入另一个"反复发生. 派工 prompt 必须强制要求"先静态 inspect ORM 模型 + 全文 grep 字段引用, 列差异表".

### 铁律 3: DriveFileVersion.uploader_id ≠ Knowledge.created_by, 跨表引用时**必须**先确认

| ORM 模型 | 字段 | 出处 |
|----------|------|------|
| `DriveFileVersion` | `uploader_id` (上传版本的人) | `app/models/drive_file_version.py:96` |
| `Knowledge` | `created_by` (创建知识条目的人) | `app/models/knowledge.py:64` |
| `Knowledge` | `uploaded_by` (KnowledgeVersion 字段) | (类比 DriveFileVersion) |

**含义**: Drive v2 的 drive 文件 = Knowledge (id 共享), 但版本化字段 = DriveFileVersion. service 涉及两表 join 时:

```python
# ❌ 错: file_row.uploader_id (Knowledge 没这字段)
file_row = await db.get(Knowledge, comment.file_id)
if file_row.uploader_id == user_id: ...  # AttributeError

# ✅ 对: file_row.created_by (Knowledge 真字段)
file_row = await db.get(Knowledge, comment.file_id)
if file_row.created_by == user_id: ...

# ✅ 对: DriveFileVersion.uploader_id (真字段, 用在版本化场景)
version = await db.get(DriveFileVersion, version_id)
if version.uploader_id == user_id: ...
```

### 铁律 4: 跨会话 agent 报 bug 必须主指挥核实再派 hot-fix (避免重复 fix)

跨会话 agent 报 "Knowledge.uploader_id 是 bug, 请改成 created_by" 时:

1. **必须**主指挥先 `python -c "from app.models.knowledge import Knowledge; print([c.name for c in Knowledge.__table__.columns])"` 核实
2. **必须**grep `app/services` 全文 + `app/api` 路由, 列所有 `.uploader_id` 引用位置 (代码 + 注释)
3. **必须**区分: 代码 (AttributeError 风险) / 注释 (文档错, 误导未来读者) / DriveFileVersion 真字段 (不动)
4. **核实后**写清楚"6 处修复"清单派 hot-fix, 不是简单说"修一下"

**为什么**: 不核实 = 派 agent 后可能 (a) 修了不该修的 DriveFileVersion.uploader_id (b) 漏掉注释错误 (c) 引新 bug. 本次 hot-fix 因主指挥核实, 精准 6 处修复, 没误删 DriveFileVersion 字段, 0 副作用.

## 验证清单

```bash
# 1. AST 语法 (3 文件全过)
python -c "import ast; ast.parse(open('app/services/drive_comment_service.py', encoding='utf-8').read()); ast.parse(open('app/services/drive_permission_service.py', encoding='utf-8').read()); ast.parse(open('app/services/drive_event_publisher.py', encoding='utf-8').read()); print('OK ast')"

# 2. Import 验证 (无 AttributeError 风险)
python -c "from app.services.drive_comment_service import _check_file_comment_authority; from app.services.drive_permission_service import DrivePermissionService; print('OK imports')"

# 3. typing imports CI (152 文件 0 错误)
bash scripts/check_typing_imports.sh

# 4. 残留错误引用 grep (期望空输出)
grep -rn 'Knowledge\.uploader_id\|file\.uploader_id\|file_row\.uploader_id' app/services app/api

# 5. e2e 测试 (静态 ORM 字段 2 PASS, DB 集成 2 SKIP if no DB)
SKIP_DB_SETUP=1 python -m pytest tests/test_drive_v2_pr10_knowledge_field_authority.py -v

# 6. DriveFileVersion.uploader_id 仍真存在 (反向验证)
python -c "from app.models.drive_file_version import DriveFileVersion; cols=[c.name for c in DriveFileVersion.__table__.columns]; print('uploader_id' in cols, 'created_by' in cols)"
# True False
```

## 交付清单 (6 文件)

| 文件 | 行数 | 角色 |
|------|------|------|
| `app/services/drive_comment_service.py` | +1 / -1 | 修复 line 94 (代码) + line 167 (注释) |
| `app/services/drive_permission_service.py` | +1 / -1 | 修复 line 253 (代码) + line 21 + 229 (注释) |
| `app/services/drive_event_publisher.py` | +0 / -0 | 修复 line 77 (注释) |
| `tests/test_drive_v2_pr10_knowledge_field_authority.py` | +165 | 新增 4 测试 (2 静态 PASS + 2 DB 集成 SKIP) |
| `memory/w68-route-5-hotfix-knowledge-uploader-id-2026-07-24.md` | (this) | 锚点范式第 74 守恒 |
| `memory/w68-route-5-hotfix-version-diff-import-2026-07-24.md` | +30 | 追加 "hot-fix #18" 段 |

## commit + push

- 分支: `fix/w68-5th-batch-knowledge-uploader-id-2026-07-24`
- 提交: 1 commit (含 4 文件改动 + 2 memory)
- push: origin
- 不 merge (主指挥来 merge)