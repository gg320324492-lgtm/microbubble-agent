# Drive v2 PR9 SSH 部署 Runbook (2026-07-24)

> **范围**: 主指挥本地 PC (Docker 8 services 宿主机) 部署 Drive v2 PR9 (评论 thread + 文件版本历史 + 移动端评论 UI) 的**流程化 12 步操作手册**。
>
> **配套文档**:
> - 详细迁移说明 + alembic 链风险 + 回滚方案 → [docs/drive-v2-pr9-deployment.md](docs/drive-v2-pr9-deployment.md)
> - 部署前检查表 (含 alembic 链路 verify) → [docs/drive-v2-pr9-rollout-checklist.md](docs/drive-v2-pr9-rollout-checklist.md)
> - 用户教程 → [docs/drive-v2-pr9-user-guide.md](docs/drive-v2-pr9-user-guide.md)
> - 端到端验证脚本 → [scripts/verify_drive_v2_pr9_deployment.sh](../scripts/verify_drive_v2_pr9_deployment.sh)
>
> **约束**: 0 production code 改动铁律维持 — 本 runbook 只描述**已有文档的部署流程**, 不修改 alembic / 路由 / ORM。

---

## 0. ⚠️ 部署前必读

1. **主指挥本地 PC**: Docker 8 services 宿主机 (`/e/microbubble-agent` 或 `E:\microbubble-agent`)。
2. **云服务器**: 只跑 Nginx + FRP, **不跑 alembic / 不重建容器** — 部署命令全部在本机。
3. **PR9 alembic 链**: 已按 H-1 agent 单链 `061 → 062 → 063` 串好 (commit `1852468a6`)。若 git log 看 main 还没合并此 commit, 先 merge, 否则 §1.3 步骤会报 `Multiple head revisions`。
4. **重要铁律**: 部署迁移前必须先 `cd /e/microbubble-agent && git pull`, 否则 alembic 文件不是最新。

---

## 1. SSH 部署 12 步 (主指挥流程化操作)

### Step 1 — 进入主指挥本地仓库

```bash
cd /e/microbubble-agent   # 或 E:\microbubble-agent
git fetch origin && git checkout main && git pull
git log --oneline -3   # 期望看到 PR9 三个 merge + 串单链修复 1852468a6
```

**期望**: 工作树干净, HEAD 含 `1852468a6` (alembic 串单链)。

### Step 2 — verify alembic chain 只 1 个 head

```bash
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; \
  c=Config(); c.set_main_option('script_location','alembic'); \
  s=ScriptDirectory.from_config(c); print('heads:', s.get_heads())"
```

**期望输出** (单 head):
```
heads: ['063_drive_file_versions']
```

若仍输出 2 个 heads (`['062_drive_comments', '063_drive_file_versions']`), 即第 0 节注意事项失败, 停止部署, 先 merge commit `1852468a6`。

### Step 3 — 拷贝 alembic 062+063 进 app 容器

```bash
docker cp alembic/versions/062_drive_comments.py \
  microbubble-agent-app-1:/app/alembic/versions/
docker cp alembic/versions/063_drive_file_versions.py \
  microbubble-agent-app-1:/app/alembic/versions/
```

**纪律 (W68 第 3 批 5 铁律第 5 条)**: 必须 `docker cp` 而非仅依靠 volume 挂载 — 本项目 app 容器在 deploy 模式下代码由镜像固化, 必须 cp 才能让 alembic 命令看到新文件。

### Step 4 — 清 alembic `__pycache__` (铁律 §1.3)

```bash
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  rm -rf /app/alembic/versions/__pycache__
```

**为何必须**: Python 缓存 `__pycache__/*.pyc` 会让老 `down_revision` 继续生效, 双头假修复。CLAUDE.md 752 行铁律升级版。

### Step 5 — 验证 alembic 当前落点

```bash
docker exec microbubble-agent-app-1 alembic current
```

**期望**:
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl
INFO  [alembic.runtime.migration] Will assume transactional DDL.
061_drive_folder_share (head)
```

若显示别的 revision, 与 production 不一致, 排查是否还有未跑迁移。

### Step 6 — 跑 alembic 升级

```bash
docker exec microbubble-agent-app-1 alembic upgrade head
```

**期望输出** (解法 A 单链后):
```
INFO  [alembic.runtime.migration] Running upgrade 061_drive_folder_share -> 062_drive_comments
INFO  [alembic.runtime.migration] Running upgrade 062_drive_comments -> 063_drive_file_versions
```

### Step 7 — 验证 alembic 落点 = 063

```bash
docker exec microbubble-agent-app-1 alembic current
```

**期望**: `063_drive_file_versions (head)` — 单一 head, 与 Step 2 一致。

### Step 8 — 重启 app + celery-worker

```bash
docker compose restart app celery-worker
```

**铁律**: 任何迁移后必须重启 Python 进程, 否则 ORM 元数据陈旧 → 报 `column does not exist` 500 (CLAUDE.md 752 行)。

### Step 9 — 看启动日志 (5 分钟超时)

```bash
docker compose logs app --tail 50 | grep -iE "error|traceback|drive"
```

**期望**: 仅看到 router 注册日志, 无 traceback / error / missing column。

**若看到 `ModuleNotFoundError`**: 第 3 步 cp 漏文件 / 镜像没 rebuild, 回到 Step 3。

### Step 10 — (仅 F-3) 前端 build + push

```bash
cd web
npm run build   # ⚠️ 唯一合法 build 命令 (CLAUDE.md 2026-07-11 铁律)
git diff --cached -- web/dist/ | grep -E '"url":\s*"manifest\.webmanifest"'   # 期望空
git add -f web/dist/manifest.*.webmanifest   # .gitignore 拦了必须 -f
git add -A && git commit -m "build(dist): Drive v2 PR9 F-3 mobile comments UI"
git push origin main
```

**期望**: webhook 30s 内自动发布 dist 到云服务器。

### Step 11 — 跑端到端验证脚本 (主指挥一键)

```bash
BASE_URL=https://<域名> TOKEN="<JWT>" \
  bash scripts/verify_drive_v2_pr9_deployment.sh
```

**期望**: §3 总结 `总 N  通过 N  失败 0  跳过 M` — 所有 Drive v2 PR9 endpoint + alembic 落点 + 4 张表 + WebSocket 全 PASS。

### Step 12 — 团队通知 + 监控

```bash
docker compose logs app --tail 100 -f | grep -i 'drive'
```

记录到 release notes: comments + versions endpoint 上线时间。发群通知 "Drive v2 PR9 已上线"。

---

## 2. 6 点 curl 验证 (与验证脚本对齐)

> **用途**: Step 11 验证脚本的 "手工版" — 适合调试 / 验证脚本失败时分点排查时手动跑。
>
> **对齐**: 全部 6 点与 `scripts/verify_drive_v2_pr9_deployment.sh` §3 一一对应。

```bash
TOKEN="<JWT>"   # 登录拿 token: curl -s -X POST https://<域名>/api/v1/auth/login -d '...'
BASE="https://<域名>/api/v1"
FILE_ID="<真实 drive file id>"   # psql 找一个: SELECT id FROM knowledge WHERE drive_folder_id IS NOT NULL LIMIT 1;
```

### ① 评论列表 (F-1) — 期望 200 + 标准分页

```bash
curl -sk -o /dev/null -w "%{http_code}\n" \
  "$BASE/drive/comments?file_id=$FILE_ID" \
  -H "Authorization: Bearer $TOKEN"
```

期望 HTTP 200, body 含 `"items"|"total"|"comments"`。无评论时返回 `{"items": [], "total": 0}`。

### ② 创建评论 (F-1) — 期望 201 + id 字段

```bash
curl -sk -X POST "$BASE/drive/comments" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"file_id\": $FILE_ID, \"content\": \"PR9 部署验证评论 @$(date +%H:%M:%S)\"}"
```

期望 HTTP 201 + JSON body 含 `"id": <int>`。记录 id 备用 (后续可看是否列表出现)。

### ③ XOR 校验负例 (F-1) — 期望 400

```bash
curl -sk -o /dev/null -w "%{http_code}\n" -X POST "$BASE/drive/comments" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"file_id": 1, "folder_id": 1, "content": "x"}'
```

期望 HTTP 400 (Pydantic 校验, file_id/folder_id 互斥)。

### ④ 版本列表 (F-2) — 期望 200 + 数组结构

```bash
curl -sk -o /dev/null -w "%{http_code}\n" \
  "$BASE/versions/files/$FILE_ID/versions" \
  -H "Authorization: Bearer $TOKEN"
```

期望 HTTP 200, body 为数组 (`[]` 或含 initial version)。

### ⑤ 版本上传 + 下载 (F-2) — 期望 201 + 200

```bash
# 上传新版本 (multipart)
echo "PR9 deploy test" > /tmp/test_pr9.txt
UPLOAD_RESP=$(curl -sk -X POST "$BASE/versions/files/$FILE_ID/versions" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/test_pr9.txt" -F "comment=部署验证版本")
NEW_VERSION_ID=$(echo "$UPLOAD_RESP" | grep -oE '"id":\s*[0-9]+' | head -1 | grep -oE '[0-9]+')
echo "上传成功, version_id=${NEW_VERSION_ID}"

# 下载该版本
curl -sk -o /dev/null -w "%{http_code}\n" \
  "$BASE/versions/versions/${NEW_VERSION_ID}/download" \
  -H "Authorization: Bearer $TOKEN"
```

期望 HTTP 201 (上传) → HTTP 200 (下载), MinIO 回流正确。

### ⑥ 无鉴权负例 — 期望 401

```bash
curl -sk -o /dev/null -w "%{http_code}\n" \
  "$BASE/drive/comments?file_id=1"
```

期望 HTTP 401 (确认 get_current_user 全接入 — 严重安全检查)。

---

## 3. 验证脚本用法

### 3.1 一键跑

```bash
bash scripts/verify_drive_v2_pr9_deployment.sh
```

**默认**: `BASE_URL=https://localhost`, 无 TOKEN (仅跑 401 负例)。

### 3.2 生产环境跑 (需 token)

```bash
BASE_URL=https://babble.math.edu   TOKEN="eyJhbGciOi..." \
  bash scripts/verify_drive_v2_pr9_deployment.sh
```

### 3.3 DRY_RUN (不真发请求)

```bash
DRY_RUN=1 BASE_URL=https://staging.example.com \
  bash scripts/verify_drive_v2_pr9_deployment.sh
```

仅打印 curl 命令 + SKIP body 检查, 用于 dry-run。

### 3.4 自定义 FILE_ID

```bash
FILE_ID=42 TOKEN="$JWT" \
  bash scripts/verify_drive_v2_pr9_deployment.sh
```

适合已有真实 drive 文件时列表 / 版本验证更准。

### 3.5 退出码

- `0`: 全部 PASS
- `1`: 任一 FAIL (修复后重跑)
- `2`: 缺依赖 (curl / docker / python3)

---

## 4. alembic 链风险 (W68 第 3 批教训)

> **教训来源**: commit `1852468a6` (W68 第 3 批 5 铁律锚点范式第 46 守恒)。

### 4.1 双头风险

PR9 F-1 (062 drive_comments) 与 F-2 (063 drive_file_versions) **并行**开发时, 派工 prompt 未明确 down_revision 接续关系 → 两个 agent 都声明 `down_revision="061_drive_folder_share"` → merge 进 main 后 alembic 链在 061 分叉成**两个 head** → `alembic upgrade head` 报:

```
FAILED: Multiple head revisions are present for given argument 'head';
please specify a specific target revision, '<branchname>@head' to narrow
to a specific head, or 'heads' for all heads
```

### 4.2 正确解法 (解法 A 单链)

主指挥 merge F-1 (062) 后, 改 1 行:

```python
# alembic/versions/063_drive_file_versions.py
down_revision: Union[str, None] = "062_drive_comments"   # 原为 "061_drive_folder_share"
```

链变为 `061 → 062 → 063` 单链, **本项目 053/054/055/056 四连 CI unique 迁移用过的模式**。

### 4.3 不可走的捷径 (解法 B 保持双头)

```bash
docker exec microbubble-agent-app-1 alembic upgrade heads   # 复数
```

`alembic current` 会显示 2 个 revision, `downgrade -1` 语义歧义, 064 接链需要额外 `alembic merge` — 给未来部署留坑。

### 4.4 5 铁律 (主指挥下次派工必带)

1. **并行 alembic migration agent 必须明确接续关系** — 派工 prompt 写清 `down_revision 接 X`。
2. **merge 顺序必须按 alembic 链** — 先 merge 上游 migration, 再 merge 下游。
3. **merge 后立即 verify** — `python -c "..."` §Step 2 命令, 期望只 1 个 head。
4. **部署文档第 0 节必含 alembic chain 风险** — 提示主指挥 merge 顺序。
5. **跨 PR 部署 alembic 必须 cp + clear cache** — `__pycache__` 残留会让老 down_revision 继续生效。

---

## 5. 回滚方案

### 5.1 alembic 降级 (解法 A 单链下)

```bash
# 只回滚 063 (drive_file_versions):
docker exec microbubble-agent-app-1 alembic downgrade -1
# 期望: Running downgrade 063_drive_file_versions -> 062_drive_comments
# DROP TABLE drive_file_versions, 无外部 FK 引用, 安全

# 连 062 一起回滚 (drive_comments):
docker exec microbubble-agent-app-1 alembic downgrade -1
# 或一步到位:
docker exec microbubble-agent-app-1 alembic downgrade 061_drive_folder_share
# 期望: DROP TABLE drive_comments (自引用 FK 内部 CASCADE, 无外部依赖)
```

### 5.2 代码回滚 + 重启

```bash
# git 层: 主指挥 revert 对应 merge commit
git revert -m 1 <F-1 merge hash>
git revert -m 1 <F-2 merge hash>
git revert -m 1 <F-3 merge hash>
git push origin main
docker compose restart app celery-worker

# 验证回滚干净
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\dt drive_*"
# 期望只剩 061 两张表 (drive_folder_shares / drive_folder_members)
curl -sk -o /dev/null -w "%{http_code}\n" \
  "$BASE/drive/comments?file_id=1" -H "Authorization: Bearer $TOKEN"
# 期望 404 (router 已摘除)
```

### 5.3 数据保留

回滚前**强烈建议**先备份 (评论 DROP 不可恢复):

```bash
docker exec microbubble-agent-postgres-1 pg_dump -U postgres -d microbubble \
  -t drive_comments -t drive_file_versions > /tmp/pr9_backup_$(date +%Y%m%d).sql
```

**回滚 SLA < 5 分钟** (对齐 chat_engine_legacy 收官 SLA, commit `817f1ffa`)。

---

## 6. 已知问题 + FAQ

### Q1: 报 `Multiple head revisions are present`

**根因**: §4.1 双头风险, commit `1852468a6` 未合并。

**解决**:
1. `cd /e/microbubble-agent && git log --oneline -3` — 看 main 是否含 `1852468a6`。
2. 若没有, 主指挥先 merge H-1 fix 分支。
3. 再回跑 §1 Step 2 verify, 期望 `heads: ['063_drive_file_versions']`。

### Q2: 报 `Can't locate revision identified by '062_drive_comments'`

**根因**: §1 Step 3 cp 漏了 062 文件 / Step 4 `__pycache__` 没清。

**解决**:
```bash
docker cp alembic/versions/062_drive_comments.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head
```

### Q3: 报 `relation "drive_comments" already exists`

**根因**: 之前跑过一半 — 表建成功但 alembic_version 没更新。

**解决 (二选一)**:
```bash
# A: 删表重来
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "DROP TABLE drive_comments CASCADE;"
docker exec microbubble-agent-app-1 alembic upgrade head

# B: stamp 跳过 (确认表结构已对齐 062 migration 才用)
docker exec microbubble-agent-app-1 alembic stamp 062_drive_comments
docker exec microbubble-agent-app-1 alembic upgrade head
```

### Q4: 部署后报 `column ... does not exist` 500

**根因**: §1 Step 8 重启没做 — alembic 跑了但 app 进程 ORM 元数据陈旧。

**解决**:
```bash
docker compose restart app celery-worker
docker compose logs app --tail 50 | grep -iE "error|traceback"
```

### Q5: WebSocket 探测超时 (curl 默认不支持长连接)

**根因**: curl 探测 `wss://` 8s 超时, 不是端点错误。

**解决**: 用浏览器验证更可靠:
1. DevTools → Console → `new WebSocket('wss://<域名>/api/v1/ws/notifications?token=<JWT>')`
2. 期望返回 `WebSocket { readyState: 1, ... }` (OPEN 状态)

或登录后让浏览器 F12 → Network → WS 标签看连接。

### Q6: §3 验证脚本全 SKIP + 0 PASS

**根因**: 缺环境变量 — 未设 `BASE_URL` / `TOKEN`。

**解决**: 见 §3.2 示例, 设全两个 env var 重跑。

### Q7: F-3 前端 build 后 commit dist, 浏览器 PWA install 失败

**根因**: `vite build` 直跑绕开 postbuild → manifest unhashed → 服务器 410 → install 失败 (CLAUDE.md 2026-07-11 铁律)。

**解决**: 重跑 `npm run build` (唯一合法 build 命令) + `git add -f web/dist/manifest.*.webmanifest`, 浏览器硬刷。

---

*文档: W68 路线 H-1 (2026-07-24). 与 [docs/drive-v2-pr9-deployment.md](docs/drive-v2-pr9-deployment.md) 配套 — 流程化手册 / 详细迁移说明分工明确。*
