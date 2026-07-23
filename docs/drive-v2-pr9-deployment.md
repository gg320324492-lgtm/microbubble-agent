# Drive v2 PR9 部署文档 (2026-07-24)

> **范围**: Drive v2 PR9 三个特性分支的生产部署流程
> - **F-1 评论 thread 后端** — branch `feat/drive-v2-pr9-comments-2026-07-24` (commit `0bfe36751`), alembic `062_drive_comments.py`
> - **F-2 文件版本历史** — branch `feat/drive-v2-pr9-versions-2026-07-24` (commit `04e06f6fd`), alembic `063_drive_file_versions.py`
> - **F-3 移动端评论 UI** — branch `feat/mobile-drive-comments-ui-2026-07-24` (commit `a6f183511`), 纯前端无迁移
>
> **前置条件**: PR7 alembic `061_drive_folder_share.py` 已在生产跑过 (`drive_folder_shares` + `drive_folder_members` 两表已存在)。
>
> **部署位置**: 主指挥本地 PC (Docker 8 services)。云服务器只跑 Nginx + FRP, **不跑 docker 迁移命令**。
>
> **0 production code 改动铁律**: PR9 是 Drive v2 新功能 (新表 + 新 router + 新组件), 不动 v1 老路径。

---

## 0. ⚠️ 部署前必读: alembic 双头 (multi-head) 问题

**现状**: 062 和 063 **都**声明 `down_revision = "061_drive_folder_share"`:

```python
# alembic/versions/062_drive_comments.py
revision: str = "062_drive_comments"
down_revision: Union[str, None] = "061_drive_folder_share"

# alembic/versions/063_drive_file_versions.py
revision: str = "063_drive_file_versions"
down_revision: Union[str, None] = "061_drive_folder_share"
```

两个分支各自独立开发, merge 进 main 后 alembic 链在 061 处分叉成**两个 head**。此时 `alembic upgrade head` 会报错:

```
FAILED: Multiple head revisions are present for given argument 'head';
please specify a specific target revision, '<branchname>@head' to narrow
to a specific head, or 'heads' for all heads
```

**两种解法 (二选一, 主指挥拍板)**:

### 解法 A (推荐): merge 时改 063 的 down_revision 串成单链

merge 两个分支进 main 后, 改一行:

```python
# alembic/versions/063_drive_file_versions.py
down_revision: Union[str, None] = "062_drive_comments"   # 原为 061_drive_folder_share
```

链变为 `061 → 062 → 063` 单链, 后续 `alembic upgrade head` / `downgrade -1` 语义全部恢复正常。**这是本项目 053/054/055/056 四连 CI unique 迁移用过的模式** (每张迁移严格单链)。

### 解法 B (不推荐): 保持双头, 用 `upgrade heads`

```bash
docker exec microbubble-agent-app-1 alembic upgrade heads   # 注意是复数 heads
```

两表都会建, 但 `alembic current` 会显示两个 revision, `downgrade -1` 语义歧义 (需要 `alembic downgrade 062_drive_comments@-1` 这种分支限定语法), 给未来 064 接链留坑 (064 需要 `alembic merge`)。**除非紧急上线来不及改代码, 否则不用**。

> 下文所有命令按 **解法 A (单链 061 → 062 → 063)** 书写。

---

## 1. 第 1 节: alembic 升级 (062 + 063 两张新表)

### 1.1 两张新表概览

| 迁移文件 | 新表 | 用途 | 关键约束 |
|----------|------|------|----------|
| `062_drive_comments.py` | `drive_comments` | 文件/文件夹评论 thread (GitHub PR review 风格) | `file_id`/`folder_id` XOR CHECK; `parent_id` 自引用嵌套不限深度; `author_id` NOT NULL CASCADE; `resolved_at`/`resolved_by` 已解决状态; 7 索引 |
| `063_drive_file_versions.py` | `drive_file_versions` | 文件版本仓库 (Google Drive 版本历史风格) | `file_id` → knowledge.id CASCADE; `(file_id, version_number)` 复合索引; `(file_id, is_current)` 复合索引 (每 file 只 1 行 is_current=1); `minio_object_key` 指向历史版本 MinIO 对象 |

FK 依赖 (部署顺序敏感): 两表都依赖 `knowledge` / `folders` / `members` 表 — 生产早已存在, 无需额外处理。062/063 互不依赖 (062 不引用 063, 反之亦然)。

### 1.2 迁移步骤 (CLAUDE.md 752 行铁律标准 3 步)

```bash
# ============ Step 1: 拷贝迁移文件进容器 ============
docker cp alembic/versions/062_drive_comments.py \
  microbubble-agent-app-1:/app/alembic/versions/
docker cp alembic/versions/063_drive_file_versions.py \
  microbubble-agent-app-1:/app/alembic/versions/

# ============ Step 2: 清 __pycache__ (铁律: 缓存掩盖新迁移) ============
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  rm -rf /app/alembic/versions/__pycache__

# ============ Step 3: 跑迁移 ============
# 先看当前位置 (期望输出 061_drive_folder_share)
docker exec microbubble-agent-app-1 alembic current

# 升级 (解法 A 单链后)
docker exec microbubble-agent-app-1 alembic upgrade head

# 期望输出:
#   INFO  [alembic.runtime.migration] Running upgrade 061_drive_folder_share -> 062_drive_comments
#   INFO  [alembic.runtime.migration] Running upgrade 062_drive_comments -> 063_drive_file_versions

# 再验证落点
docker exec microbubble-agent-app-1 alembic current
# 期望: 063_drive_file_versions (head)
```

### 1.3 常见失败与处理

| 报错 | 根因 | 处理 |
|------|------|------|
| `Multiple head revisions are present` | 未按解法 A 改 063 down_revision | 见第 0 节; 改完重新 docker cp + 清 pycache 重跑 |
| `Can't locate revision identified by '062_drive_comments'` | Step 2 pycache 没清 / cp 漏了一个文件 | 重跑 Step 1 + Step 2 |
| `relation "drive_comments" already exists` | 之前跑过一半 (建表成功但 alembic_version 没更新) | `docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "DROP TABLE drive_comments CASCADE;"` 后重跑; 或 `alembic stamp 062_drive_comments` 跳过 (确认表结构一致时) |
| `column ... does not exist` 500 (部署后) | 迁移跑了但 app 进程没重启, ORM 元数据陈旧 | 第 2 节 restart 步骤没做, 补 `docker compose restart app celery-worker` |

---

## 2. 第 2 节: 主指挥 SSH 部署流程

> 完整流程: 本地 PC 拉代码 → docker cp 迁移 → alembic upgrade → 重启后端 → 前端 build + push (F-3) → 云端 webhook 自动发布。

### 2.1 后端 (F-1 评论 + F-2 版本)

```bash
# ---- 在主指挥本地 PC (Docker 宿主机) ----
cd /e/microbubble-agent   # 或 E:\microbubble-agent

# 1. 确认 main 已含三个 PR9 merge (主指挥 merge 后)
git fetch origin && git log --oneline -5 origin/main
git checkout main && git pull

# 2. 同步代码进容器 (compose volume 挂载则跳过; 镜像内置代码则需 rebuild)
#    本项目 app 容器为 volume 挂载 /app, git pull 后容器内代码即最新。
#    若 docker compose config 显示无挂载, 改用:
#    docker compose build app celery-worker

# 3. alembic 迁移 (第 1 节 3 步完整执行)
docker cp alembic/versions/062_drive_comments.py microbubble-agent-app-1:/app/alembic/versions/
docker cp alembic/versions/063_drive_file_versions.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head

# 4. 重启后端 (铁律: 迁移后必须重启 Python 进程)
docker compose restart app celery-worker

# 5. 看启动日志确认 router 注册无异常
docker compose logs app --tail 50 | grep -iE "error|traceback|drive"
```

### 2.2 前端 (F-3 移动端评论 UI)

```bash
cd web

# ⚠️ 铁律 (CLAUDE.md 2026-07-11): npm run build 是唯一合法 build 命令
#    严禁 vite build 直跑 (manifest unhashed → nginx 410 → PWA install 失败)
npm run build

# commit 前 grep dist (铁律 3): 期望空输出
git diff --cached -- web/dist/ | grep -E '"url":\s*"manifest\.webmanifest"'

# 新增 hashed manifest 文件必须 force-add (.gitignore 拦截)
git add -f web/dist/manifest.*.webmanifest

git add -A && git commit -m "build(dist): Drive v2 PR9 F-3 mobile comments UI"
git push origin main
# → 云端 webhook 30s 内自动发布 dist
```

### 2.3 云端验证 (SSH 到云服务器, 仅验证不部署)

```bash
# 云服务器只跑 nginx + frp, 无 docker。仅 curl 验证:
curl -sk -o /dev/null -w "%{http_code} %{content_type}\n" https://<域名>/index.html
curl -sk -o /dev/null -w "%{http_code}\n" "https://<域名>/api/v1/drive/comments?file_id=1" \
  -H "Authorization: Bearer <token>"
```

---

## 3. 第 3 节: 验证清单

### 3.1 psql 验证 4 张 Drive v2 新表 (061 两张 + 062/063 各一张)

```bash
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\dt drive_*"
```

期望输出包含 4 张表:

```
 public | drive_comments       | table | postgres    ← 062 (PR9 F-1)
 public | drive_file_versions  | table | postgres    ← 063 (PR9 F-2)
 public | drive_folder_members | table | postgres    ← 061 (PR7, 前置)
 public | drive_folder_shares  | table | postgres    ← 061 (PR7, 前置)
```

结构抽查:

```bash
# drive_comments: 确认 XOR CHECK 约束 + resolved 列
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\d drive_comments"
# 期望: file_id/folder_id 均 nullable + Check constraints 含 file/folder 二选一 + resolved_at/resolved_by

# drive_file_versions: 确认复合索引
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\d drive_file_versions"
# 期望索引: (file_id, version_number) + (file_id, is_current) + uploader_id

# alembic 落点
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "SELECT version_num FROM alembic_version;"
# 期望: 063_drive_file_versions (解法 A 单链)
```

### 3.2 6 点 curl 验证 (CLAUDE.md 2026-06-13 铁律 ⑤ 模式)

```bash
TOKEN="<JWT>"   # 登录拿 token: curl -s -X POST https://<域名>/api/v1/auth/login -d '...'
BASE="https://<域名>/api/v1"

# ① 评论列表 (F-1): 期望 200 + {"items": [], "total": 0}
curl -sk "$BASE/drive/comments?file_id=<drive文件id>" -H "Authorization: Bearer $TOKEN"

# ② 创建评论 (F-1): 期望 201 + id 返回
curl -sk -X POST "$BASE/drive/comments" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"file_id": <drive文件id>, "content": "PR9 部署验证评论"}'

# ③ XOR 校验 (F-1 负例): file_id + folder_id 同传, 期望 400 VALIDATION_ERROR
curl -sk -X POST "$BASE/drive/comments" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"file_id": 1, "folder_id": 1, "content": "x"}'

# ④ 版本列表 (F-2): 期望 200 (空历史返回 [] 或含 initial version)
curl -sk "$BASE/versions/files/<drive文件id>/versions" -H "Authorization: Bearer $TOKEN"

# ⑤ 上传新版本 (F-2): 期望 201 + version_number 递增
curl -sk -X POST "$BASE/versions/files/<drive文件id>/versions" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@./test.txt" -F "comment=部署验证版本"

# ⑥ 无鉴权负例: 不带 token, 期望 401 (确认 get_current_user 全接入)
curl -sk -o /dev/null -w "%{http_code}\n" "$BASE/drive/comments?file_id=1"
```

任一点不符预期 → 停止发布用户通知, 按第 4 节回滚或排错。

### 3.3 移动端 UI 验证 (F-3)

1. 手机 (或 DevTools mobile viewport 375×812) 打开网盘 → 任一文件 → 评论入口
2. 路由 `drive/file/:id/comments` 渲染 `MobileFileCommentsView` (mobileOnly, 桌面端访问自动回退)
3. 发一条评论 → 列表即时出现; 长按评论 → ActionSheet (回复/编辑/删除, 带 `navigator.vibrate(10)` 触觉)
4. dark mode 切换 → 评论卡片/输入框跟随 (非 scoped 块铁律)
5. vitest / Playwright: `web/tests/e2e/mobile_drive_comments.spec.js` 全 PASS

### 3.4 回归基线

```bash
# 后端: 87+ 基线不回归
docker exec microbubble-agent-app-1 pytest tests/ -x -q 2>&1 | tail -3
# 前端
cd web && npx vitest run 2>&1 | tail -3
# Lint CSS 基线守恒: 71 PASS + 7 SKIP (W68 第 32 守恒基线)
```

---

## 4. 第 4 节: 回滚方案

### 4.1 alembic 降级 (解法 A 单链下)

```bash
# 只回滚 063 (drive_file_versions):
docker exec microbubble-agent-app-1 alembic downgrade -1
# 期望: Running downgrade 063_drive_file_versions -> 062_drive_comments
#       (DROP TABLE drive_file_versions, 无外部 FK 引用, 安全)

# 连 062 一起回滚 (drive_comments):
docker exec microbubble-agent-app-1 alembic downgrade -1
# 或一步到位:
docker exec microbubble-agent-app-1 alembic downgrade 061_drive_folder_share
# 期望: DROP TABLE drive_comments (自引用 FK 内部 CASCADE, 无外部依赖, 安全)
```

> **解法 B 双头下的回滚** (仅当没按解法 A 改链): `downgrade -1` 歧义, 必须分支限定:
> `alembic downgrade 063_drive_file_versions@-1` / `alembic downgrade 062_drive_comments@-1`。

### 4.2 代码回滚 + 重启

```bash
# git 层: 主指挥 revert 对应 merge commit (merge commit 需 -m 1)
git revert -m 1 <F-1 merge hash>
git revert -m 1 <F-2 merge hash>
git revert -m 1 <F-3 merge hash>   # 前端需重跑 npm run build + force-add dist
git push origin main

# Docker 层: 重启后端 (铁律: 任何代码/迁移回滚后必须 restart)
docker compose restart app celery-worker

# 验证回滚干净
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\dt drive_*"
# 期望只剩 061 两张表
curl -sk -o /dev/null -w "%{http_code}\n" "$BASE/drive/comments?file_id=1" -H "Authorization: Bearer $TOKEN"
# 期望 404 (router 已摘除)
```

### 4.3 数据保留说明

- `drive_comments` DROP 后评论数据**不可恢复** — 回滚前若已有真实用户评论, 先备份:
  ```bash
  docker exec microbubble-agent-postgres-1 pg_dump -U postgres -d microbubble \
    -t drive_comments -t drive_file_versions > /tmp/pr9_backup_$(date +%Y%m%d).sql
  ```
- `drive_file_versions` DROP 只删版本**索引记录**, MinIO 历史对象 (`uploads/drive/{owner_id}/v{n}_...`) 不会被删 — 成为孤儿对象, 留待 PR6-P10 `backup_before_delete`/cleanup 体系或手动 `mc rm` 清理。
- 回滚决策 < 5 分钟可完成 (对齐 chat_engine_legacy 收官的回滚 SLA)。

---

## 5. 附录: 端点速查

| 特性 | 方法 + 路径 | 说明 |
|------|-------------|------|
| F-1 | `POST /api/v1/drive/comments` | 创建评论 (file_id/folder_id XOR) |
| F-1 | `GET /api/v1/drive/comments` | 列表 (顶层分页 + 嵌套树) |
| F-1 | `GET /api/v1/drive/comments/{id}` | 单条 + 直接子回复 |
| F-1 | `PATCH /api/v1/drive/comments/{id}` | 编辑 (仅 author) |
| F-1 | `DELETE /api/v1/drive/comments/{id}` | 删除 (仅 author, 子评论 CASCADE) |
| F-1 | `POST /api/v1/drive/comments/{id}/resolve` | 标记已解决 (author/owner/admin) |
| F-1 | `POST /api/v1/drive/comments/{id}/unresolve` | 取消已解决 |
| F-2 | `GET /api/v1/versions/files/{file_id}/versions` | 版本列表 (desc) |
| F-2 | `POST /api/v1/versions/files/{file_id}/versions` | 上传新版本 (multipart) |
| F-2 | `GET /api/v1/versions/versions/{version_id}/download` | 下载指定版本 |
| F-2 | `POST /api/v1/versions/files/{file_id}/versions/{version_id}/rollback` | 回滚 = 创建新版本 |
| F-2 | `DELETE /api/v1/versions/versions/{version_id}` | 删版本 (禁删中间版) |
| F-3 | 前端路由 `drive/file/:id/comments` | `MobileFileCommentsView` (mobileOnly) |

限流: 评论走 write tier (30/min), 版本上传走 drive_upload tier (50/min), 版本列表走 drive_list/read tier — 均由 rate_limit 路径匹配自动覆盖 (CLAUDE.md v31.2.6, 无需额外配置)。

---

*文档: W68 路线 H-1 (2026-07-24). 详细 API 见 `docs/drive-v2-pr9-comments.md` (F-1 branch 内) + `docs/drive-v2-pr9-versions.md` (F-2 branch 内)。用户教程见 `docs/drive-v2-pr9-user-guide.md`。部署检查表见 `docs/drive-v2-pr9-rollout-checklist.md`。*
