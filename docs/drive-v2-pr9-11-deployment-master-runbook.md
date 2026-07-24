# Drive v2 PR9 + PR10 + PR11 部署 Master Runbook (2026-07-24)

> **总入口**: 主指挥本地 PC 部署 Drive v2 PR9 (评论 thread + 文件版本) + PR10 (协同编辑 WebSocket + Push) 的**唯一权威 runbook**。本文件整合 W68 第 5 批 H-1 (PR9) + W68 第 7 批 D-1/D-2 (PR10) + W68 第 8 批 A-2 (本文件) 文档, 提供 18 步 SSH 部署主流程 + alembic 链风险 + 验证脚本 + FAQ。
>
> **配套文档** (按需查阅, **不重复内容**):
> - PR9 详细迁移说明 + alembic 链风险 + 回滚 → [docs/drive-v2-pr9-deployment.md](drive-v2-pr9-deployment.md)
> - PR9 SSH 12 步流程 → [docs/drive-v2-pr9-deployment-runbook.md](drive-v2-pr9-deployment-runbook.md)
> - PR10 协同编辑设计 → [docs/drive-v2-pr10-collab-editing-design.md](drive-v2-pr10-collab-editing.md) + [docs/drive-v2-pr10-collab-editing.md](drive-v2-pr10-collab-editing.md)
> - PR9 部署前检查表 → [docs/drive-v2-pr9-rollout-checklist.md](drive-v2-pr9-rollout-checklist.md)
> - PR9 用户教程 → [docs/drive-v2-pr9-user-guide.md](drive-v2-pr9-user-guide.md)
> - 故障 FAQ → [docs/drive-v2-deployment-troubleshooting-faq.md](drive-v2-deployment-troubleshooting-faq.md)
> - PR10 部署运行手册 (W68 第 7 批 D-2 单 PR 参考) → 保留作为 PR10 单 PR 参考

---

## 0. 总览: PR9 → PR10 → PR11 部署顺序

| PR | 范围 | alembic | 验证脚本 | 部署状态 |
|----|------|---------|----------|---------|
| **PR9** | 评论 thread + 文件版本 + 移动端评论 UI | 062 (drive_comments) + 063 (drive_file_versions) | `verify_drive_v2_pr9_deployment.sh` | 已部署 (W68 第 5 批) |
| **PR10** | 协同编辑 WebSocket (pycrdt) + Redis pub/sub + Web Push (pywebpush) | 064 (drive_documents + drive_doc_op_logs) + 065 (push_subscriptions) | `verify_w68_5th_batch_deployment.sh` + `verify_pr10_collab_ws.py` | 已部署 (W68 第 7 批) |
| **PR11** | 离线缓存 + 编辑器集成 + 桌面端 review UI 优化 | 待定 (066+) | 待定 | 待开发 (W69+) |

**部署顺序铁律 (锚点范式第 91 守恒)**:
1. PR9 必须先部署 (评论 + 版本是 PR10 编辑功能的前置数据流)。
2. PR10 在 PR9 之上叠加 (协同编辑依赖 drive_file_versions 做版本号追溯, 依赖 drive_comments 做评论批注)。
3. PR11 在 PR10 之上叠加 (离线缓存要序列化 ydoc_state)。
4. **绝对不可跳级** — 直接上 PR10 而没上 PR9 → 评论/版本 endpoint 404 → WS 协同时无法关联评论。

---

## 1. SSH 部署 18 步 (主指挥流程化操作, PR9 + PR10 综合)

> **位置**: 主指挥本地 PC (Docker 8 services 宿主机, `/e/microbubble-agent` 或 `E:\microbubble-agent`)。
>
> **云服务器**: 只跑 Nginx + FRP, **不跑 alembic / 不重建容器** — 部署命令全部在本机。

### Step 1 — git pull main + worktree merge W68 第 7 批

```bash
cd /e/microbubble-agent
git fetch origin && git checkout main && git pull --ff-only
git log --oneline -10   # 期望看到 PR9 + PR10 全部 merge + 串单链修复 1852468a6
```

**期望**: 工作树干净, HEAD 含 PR9 + PR10 的所有 merge commit。

### Step 2 — verify alembic chain 只 1 个 head (锚点范式第 46 守恒)

```bash
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; \
  c=Config(); c.set_main_option('script_location','alembic'); \
  s=ScriptDirectory.from_config(c); print('heads:', s.get_heads())"
```

**期望输出** (单 head, PR9 + PR10 合并后):
```
heads: ['065_push_subscriptions']
```

若仍输出多个 heads, 停止部署, 按第 2 节 alembic 链风险排查。

### Step 3 — 拷贝 alembic 062+063+064+065 进 app 容器

```bash
# PR9 (评论 + 版本)
docker cp alembic/versions/062_drive_comments.py \
  microbubble-agent-app-1:/app/alembic/versions/
docker cp alembic/versions/063_drive_file_versions.py \
  microbubble-agent-app-1:/app/alembic/versions/

# PR10 (协同 + Push)
docker cp alembic/versions/064_drive_documents.py \
  microbubble-agent-app-1:/app/alembic/versions/
docker cp alembic/versions/065_push_subscriptions.py \
  microbubble-agent-app-1:/app/alembic/versions/
```

**纪律 (W68 第 3 批 5 铁律第 5 条)**: 必须 `docker cp` 而非仅依靠 volume 挂载 — 本项目 app 容器在 deploy 模式下代码由镜像固化, 必须 cp 才能让 alembic 命令看到新文件。

### Step 4 — 清 alembic `__pycache__` (铁律)

```bash
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  rm -rf /app/alembic/versions/__pycache__
```

**为何必须**: Python 缓存 `__pycache__/*.pyc` 会让老 `down_revision` 继续生效, 双头假修复。CLAUDE.md 752 行铁律升级版。

### Step 5 — 跑 alembic 升级 (期望落点 065)

```bash
docker exec microbubble-agent-app-1 alembic upgrade head
docker exec microbubble-agent-app-1 alembic current
```

**期望输出**:
```
INFO  [alembic.runtime.migration] Running upgrade 061_drive_folder_share -> 062_drive_comments
INFO  [alembic.runtime.migration] Running upgrade 062_drive_comments -> 063_drive_file_versions
INFO  [alembic.runtime.migration] Running upgrade 063_drive_file_versions -> 064_drive_documents
INFO  [alembic.runtime.migration] Running upgrade 064_drive_documents -> 065_push_subscriptions
065_push_subscriptions (head)
```

### Step 6 — 安装 pycrdt + pywebpush 依赖 (PR10 协同 + Push)

```bash
docker exec microbubble-agent-app-1 pip install 'pycrdt>=0.10' 'pywebpush>=0.14.1'
docker exec microbubble-agent-celery-worker-1 pip install 'pycrdt>=0.10' 'pywebpush>=0.14.1'
```

**纪律**: app + celery-worker 两边都要装, 否则 worker 跑协同 flush 任务时 `pycrdt.Doc` 解码失败 → Celery task crash → 协同编辑丢失 ydoc_state 快照。

### Step 7 — 重启 app + celery-worker

```bash
docker compose restart app celery-worker
```

**铁律**: 任何迁移后必须重启 Python 进程, 否则 ORM 元数据陈旧 → 报 `column does not exist` 500 (CLAUDE.md 752 行)。

### Step 8 — 看启动日志 (5 分钟超时)

```bash
docker compose logs app --tail 50 | grep -iE "error|traceback|drive|push|collab"
docker compose logs celery-worker --tail 50 | grep -iE "error|traceback|push|collab"
```

**期望**: 仅看到 router 注册日志 + Celery task 发现日志, 无 traceback / error / missing column / pycrdt import error。

**若看到 `ModuleNotFoundError: No module named 'pycrdt'`**: 第 6 步 pip install 漏装 / 镜像没 rebuild, 回到 Step 6。

### Step 9 — PR9 端到端验证 (评论 + 版本)

```bash
BASE_URL=https://<域名> TOKEN="<JWT>" \
  bash scripts/verify_drive_v2_pr9_deployment.sh
```

**期望**: 12 个 endpoint + alembic 落点 + 4 张表 + WebSocket 全 PASS。失败 fail-loud (exit 1)。

### Step 10 — PR10 端到端验证 (协同 + Push)

```bash
BASE_URL=https://<域名> TOKEN="<JWT>" \
  bash scripts/verify_w68_5th_batch_deployment.sh

python scripts/verify_pr10_collab_ws.py --base-url ws://<域名> --file-id <FILE_ID> --token "<JWT>" --apply
```

**期望**:
- `verify_w68_5th_batch_deployment.sh`: 4 张 PR10 新表 + VAPID 公钥 endpoint + push subscription endpoint + WS snapshot endpoint 全 PASS。
- `verify_pr10_collab_ws.py --apply`: WS 连接成功 + 发送 `{"type": "ping"}` 后服务端正常回包。

### Step 11 — 前端 build + push (PR9 F-3 + PR10 desktop/mobile)

```bash
cd web
npm run build   # 唯一合法 build 命令 (CLAUDE.md 2026-07-11 铁律)
git diff --cached -- web/dist/ | grep -E '"url":\s*"manifest\.webmanifest"'   # 期望空
git add -f web/dist/manifest.*.webmanifest   # .gitignore 拦了必须 -f
git add -A && git commit -m "build(dist): Drive v2 PR9 + PR10 dist"
git push origin main
```

**期望**: webhook 30s 内自动发布 dist 到云服务器。

### Step 12 — baseline 71 PASS + 7 SKIP (W68 第 32 守恒)

```bash
# 后端: 87+ 基线不回归
docker exec microbubble-agent-app-1 pytest tests/ -x -q 2>&1 | tail -3
# 前端
cd web && npx vitest run 2>&1 | tail -3
# Lint CSS
npx stylelint 'web/src/**/*.{vue,css}' 2>&1 | tail -3
```

**期望**:
- pytest: 全 PASS (无 regression)
- vitest: 全 PASS (无 regression)
- stylelint: 71 PASS + 7 SKIP (W68 第 32 守恒基线, 0 PASS 下降 / 0 FAIL 上升)

### Step 13 — 桌面端 PWA install + push 权限验证

1. Chrome / Edge 打开 https://\<域名\> → DevTools → Application → Manifest → 期望 `name: "小气"` + icons 全 200
2. URL 栏右侧出现安装图标 → 安装到桌面 → 启动 PWA 模式
3. PWA 窗口内 → 设置 → 通知权限 → 浏览器弹窗 → 允许
4. 后端日志看到 `push_subscription` 插入记录 (含 endpoint / p256dh / auth 加密字段)

**期望**: 桌面端 PWA install 成功 + push 订阅落库。

### Step 14 — 移动端 PWA install + push 权限验证

1. Android Chrome / iOS Safari 打开 https://\<域名\> → 分享 → 添加到主屏幕
2. 主屏幕图标启动 → PWA 模式 (iOS Safari 全屏 + 隐藏 URL 栏)
3. iOS Settings → PWA → 通知 → 允许
4. 后端日志看到移动端 `push_subscription` 记录 (user_agent 区分 mobile/desktop)

**期望**: 移动端 PWA install 成功 + push 订阅落库 (user_agent 含 `Mobile` / `iPhone` / `Android`)。

### Step 15 — WS 协同编辑真跑 (两浏览器窗口同步)

1. 桌面 Chrome 窗口 A: 登录账号 X → 打开 drive file id=1 → 进入编辑器
2. 桌面 Chrome 窗口 B (无痕模式): 登录账号 X → 打开同一文件 → 进入编辑器
3. 窗口 A 输入 "hello" → 窗口 B 应**实时**看到 "hello" 字符级同步 (< 200ms)
4. 窗口 B 改 "hello" 为 "world" → 窗口 A 应看到 "world"
5. 关闭窗口 B → 窗口 A 编辑继续 → Celery 30s 后 `drive_documents.ydoc_state` 更新

**期望**:
- WS 双向同步延迟 < 200ms (本地 LAN)
- ydoc_state 30s 内落库 (active_users + ops_count + version_number 递增)

### Step 16 — Push 通知真跑 (桌面 + 移动双端)

1. 桌面 PWA + 移动 PWA 同时登录同一账号
2. 另一账号在 file id=1 写评论 @ 该账号
3. 桌面 PWA: 系统通知弹出 "评论: @你的内容..."
4. 移动 PWA: 系统通知弹出 (iOS Safari 横幅 + Android Chrome 通知栏)
5. 点击通知 → 跳转 drive file id=1 → 评论 thread 高亮

**期望**: 双端 push 通知 5s 内送达, 点击跳转正确。

### Step 17 — Redis pub/sub + Celery flush 健康检查

```bash
# Redis pub/sub channel 活跃度
docker exec microbubble-agent-redis-1 redis-cli PUBSUB CHANNELS 'drive:*'
# 期望: 至少 1 个 channel (当前活跃协同房间)

# Celery 队列长度
docker exec microbubble-agent-redis-1 redis-cli LLEN celery
# 期望: < 100 (无堆积)

# drive_documents flush 记录
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c \
  "SELECT id, file_id, length(ydoc_state), ops_count, version_number, active_users, updated_at \
   FROM drive_documents ORDER BY updated_at DESC LIMIT 5;"
# 期望: 最近 5 分钟内有 updated_at 更新
```

### Step 18 — 通知用户 + 监控 15 分钟

```bash
docker compose logs app --tail 100 -f | grep -iE 'drive|push|collab|comment'
```

记录到 release notes:
- Drive v2 PR9 评论 thread + 文件版本上线时间
- Drive v2 PR10 协同编辑 + Web Push 上线时间
- 验证窗口 (15 分钟) 期间无异常

发群通知 "Drive v2 PR9 + PR10 已上线, 桌面 + 移动 PWA push 通知已启用"。

---

## 2. alembic 链风险 (复用 W68 第 3 批纪律)

### 2.1 单链结构

PR9 + PR10 部署后, alembic 链结构:

```
061_drive_folder_share (PR7, 前置)
  ↓
062_drive_comments (PR9 F-1, 评论 thread)
  ↓
063_drive_file_versions (PR9 F-2, 文件版本)
  ↓
064_drive_documents (PR10 协同, Yjs CRDT)
  ↓
065_push_subscriptions (PR10 Push, Web Push API)
```

**单链纪律 (锚点范式第 46 守恒)**:
1. **并行 alembic migration agent 必须明确接续关系** — 派工 prompt 写清 `down_revision 接 X`。W68 第 5 批 + 第 7 批 agent 派工已遵守 (B-1 agent 接 063 写 064, B-3 agent 接 064 写 065)。
2. **merge 顺序必须按 alembic 链** — 先 merge 062 + 063 (PR9), 再 merge 064 (PR10), 最后 merge 065 (PR10 Push)。不能并行 merge 有依赖关系的 migration。
3. **merge 后立即 verify** — `python -c "..."` §Step 2 命令, 期望只 1 个 head `['065_push_subscriptions']`。
4. **部署文档第 0 节必含 alembic chain 风险** — 本文件 §2 即此作用。
5. **跨 PR 部署 alembic 必须 cp + clear cache** — `__pycache__` 残留会让老 down_revision 继续生效, 双头假修复。

### 2.2 064 / 065 不冲突 (B-1 / B-3 agent 已串好)

W68 第 7 批 B-1 (064 drive_documents) 与 B-3 (065 push_subscriptions) **串行**开发:
- B-1 派工 prompt 明确 `down_revision = "063_drive_file_versions"`
- B-3 派工 prompt 明确 `down_revision = "064_drive_documents"`

merge 后链路 `063 → 064 → 065` 自然串成单链, **无 W68 第 3 批 062/063 双头事故风险**。

### 2.3 解法 A 单链 vs 解法 B 双头 (历史教训)

**解法 A (推荐, 本项目所有 PR 走此模式)**:

```python
# alembic/versions/065_push_subscriptions.py
down_revision: Union[str, None] = "064_drive_documents"   # 串成单链
```

链 `061 → 062 → 063 → 064 → 065` 单链, `alembic upgrade head` / `downgrade -1` 语义全部正常。

**解法 B (不可走, 历史 PR9 教训)**:

```bash
docker exec microbubble-agent-app-1 alembic upgrade heads   # 复数
```

`alembic current` 显示 2 个 revision, `downgrade -1` 语义歧义, 066 接链需要额外 `alembic merge` — 给未来部署留坑。

---

## 3. 验证脚本 4 用法

### 3.1 `verify_drive_v2_pr9_deployment.sh` (W68 第 5 批 #13, PR9)

```bash
# 默认 (无 token, 仅 401 负例)
bash scripts/verify_drive_v2_pr9_deployment.sh

# 生产环境 (需 token)
BASE_URL=https://<域名> TOKEN="<JWT>" \
  bash scripts/verify_drive_v2_pr9_deployment.sh

# DRY_RUN (不真发请求)
DRY_RUN=1 BASE_URL=https://staging.example.com \
  bash scripts/verify_drive_v2_pr9_deployment.sh

# 自定义 FILE_ID (生产前 psql 找真实 drive 文件)
FILE_ID=42 TOKEN="$JWT" \
  bash scripts/verify_drive_v2_pr9_deployment.sh
```

**退出码**:
- `0`: 全部 PASS
- `1`: 任一 FAIL (修复后重跑)
- `2`: 缺依赖 (curl / docker / python3)

### 3.2 `verify_w68_5th_batch_deployment.sh` (W68 第 7 批 D-1, PR10)

```bash
BASE_URL=https://<域名> TOKEN="<JWT>" \
  bash scripts/verify_w68_5th_batch_deployment.sh
```

验证 4 张 PR10 新表 (`drive_documents` / `drive_doc_op_logs` / `push_subscriptions` / `push_delivery_log`) + VAPID 公钥 endpoint + push subscription endpoint + WS snapshot endpoint。

### 3.3 `verify_pr10_collab_ws.py` (W68 第 7 批 D-2, PR10 WS 真连)

```bash
# dry-run (静态检查, 不发 WS 帧)
python scripts/verify_pr10_collab_ws.py

# 真发 WS (维护窗口使用)
python scripts/verify_pr10_collab_ws.py \
  --base-url ws://<域名> \
  --file-id <FILE_ID> \
  --token "<JWT>" \
  --apply
```

**依赖**: `--apply` 需 `pip install websockets`。

### 3.4 组合跑 (Step 9 + Step 10 合并)

```bash
# PR9 + PR10 全部验证 (主指挥部署后一键)
BASE_URL=https://<域名> TOKEN="<JWT>" \
  bash scripts/verify_drive_v2_pr9_deployment.sh && \
BASE_URL=https://<域名> TOKEN="<JWT>" \
  bash scripts/verify_w68_5th_batch_deployment.sh && \
python scripts/verify_pr10_collab_ws.py \
  --base-url ws://<域名> \
  --file-id <FILE_ID> \
  --token "<JWT>" \
  --apply
```

---

## 4. 6 个常见问题 FAQ (完整 FAQ 见独立文档)

### Q1: alembic `Multiple head revisions` (PR9 + PR10 合并后)

**根因**: 主指挥 merge 时, 064/065 中某 agent 未明确 down_revision, 形成多链分叉。

**解决**:
1. `git log --oneline -10` 看是否有 064 / 065 串单链修复 commit。
2. 若没有, 主指挥手动改 `alembic/versions/065_push_subscriptions.py` 的 `down_revision = "064_drive_documents"`。
3. 重跑 §Step 2 verify, 期望 `heads: ['065_push_subscriptions']`。

### Q2: `Can't locate revision identified by '064_drive_documents'`

**根因**: §Step 3 cp 漏文件 / §Step 4 `__pycache__` 没清。

**解决**: 重跑 §Step 3 + §Step 4, 再 §Step 5 alembic upgrade。

### Q3: `column ... does not exist` 500 (部署后)

**根因**: §Step 7 重启没做 — alembic 跑了但 app 进程 ORM 元数据陈旧。

**解决**: `docker compose restart app celery-worker`, 重启后 `docker compose logs app --tail 50 | grep -iE "error|traceback"` 看是否还有 error。

### Q4: WebSocket 探测超时 (`curl` 默认不支持长连接)

**根因**: `curl` 探测 `wss://` 8s 超时, 不是端点错误。

**解决**: 用 `verify_pr10_collab_ws.py --apply` 或浏览器 DevTools → Network → WS 标签看连接。

### Q5: pycrdt import error (`ModuleNotFoundError: No module named 'pycrdt'`)

**根因**: §Step 6 pip install 漏装 / app 与 worker 不一致。

**解决**:
```bash
docker exec microbubble-agent-app-1 pip install 'pycrdt>=0.10' 'pywebpush>=0.14.1'
docker exec microbubble-agent-celery-worker-1 pip install 'pycrdt>=0.10' 'pywebpush>=0.14.1'
docker compose restart app celery-worker
```

### Q6: Push 失败 410 (订阅自动清理)

**根因**: 浏览器 / 系统清理了过期 push 订阅 (典型: 用户清缓存 / 重装浏览器 / Chrome 90 天未访问清理)。

**解决**: 前端在 SW 收到 410 响应时自动调用 `push_subscriptions.delete` API 清理 (Drive v2 PR10 已实现), 用户无感知。后端无需手动处理。

---

## 5. 回滚方案 (alembic downgrade + docker restart)

### 5.1 alembic 降级 (单链下 `downgrade -1` 语义清晰)

```bash
# 只回滚 065 (push_subscriptions):
docker exec microbubble-agent-app-1 alembic downgrade -1
# 期望: Running downgrade 065_push_subscriptions -> 064_drive_documents
# DROP TABLE push_subscriptions + push_delivery_log

# 连 064 一起回滚 (drive_documents + drive_doc_op_logs):
docker exec microbubble-agent-app-1 alembic downgrade -1
# 或一步到位:
docker exec microbubble-agent-app-1 alembic downgrade 063_drive_file_versions
```

依次 `downgrade -1` / `-1` / `-1` / `-1` 可回到 061, 即回到 PR7 状态 (无 Drive v2 PR9 + PR10)。

### 5.2 代码回滚 + 重启

```bash
# git 层: 主指挥 revert 对应 merge commit
git revert -m 1 <PR9 F-1 merge hash>
git revert -m 1 <PR9 F-2 merge hash>
git revert -m 1 <PR9 F-3 merge hash>
git revert -m 1 <PR10 merge hash>
git push origin main

# Docker 层: 重启后端 (铁律: 任何代码/迁移回滚后必须 restart)
docker compose restart app celery-worker

# 验证回滚干净
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\dt drive_* push_*"
# 期望只剩 061 两张表 (drive_folder_shares / drive_folder_members)
```

### 5.3 数据保留

回滚前**强烈建议**先备份 (评论 + 协同 ydoc_state DROP 不可恢复):

```bash
docker exec microbubble-agent-postgres-1 pg_dump -U postgres -d microbubble \
  -t drive_comments -t drive_file_versions \
  -t drive_documents -t drive_doc_op_logs \
  -t push_subscriptions -t push_delivery_log \
  > /tmp/pr9_pr10_backup_$(date +%Y%m%d).sql
```

**回滚 SLA < 5 分钟** (对齐 chat_engine_legacy 收官 SLA, commit `817f1ffa`)。

---

## 6. 文档索引

| 文档 | 范围 | 适用场景 |
|------|------|---------|
| **本文件 (drive-v2-pr9-11-deployment-master-runbook.md)** | PR9 + PR10 + PR11 总入口 | 主指挥部署前查总览 |
| [drive-v2-pr9-deployment.md](drive-v2-pr9-deployment.md) | PR9 详细迁移说明 + alembic 链风险 + 回滚 | PR9 单 PR 部署 / debug |
| [drive-v2-pr9-deployment-runbook.md](drive-v2-pr9-deployment-runbook.md) | PR9 SSH 12 步流程 | PR9 单 PR 流程化操作 |
| [drive-v2-pr10-collab-editing-design.md](drive-v2-pr10-collab-editing-design.md) | PR10 协同编辑架构设计 | PR10 架构理解 |
| [drive-v2-pr10-collab-editing.md](drive-v2-pr10-collab-editing.md) | PR10 协同编辑实施 | PR10 单 PR 流程 |
| [drive-v2-deployment-troubleshooting-faq.md](drive-v2-deployment-troubleshooting-faq.md) | 8 个常见问题 FAQ | 部署失败排错 |
| [drive-v2-pr9-rollout-checklist.md](drive-v2-pr9-rollout-checklist.md) | PR9 部署前检查表 | PR9 上线前 verify |
| [drive-v2-pr9-user-guide.md](drive-v2-pr9-user-guide.md) | PR9 用户教程 | 用户培训 |

---

*文档: W68 路线 8 A-2 (2026-07-24). 锚点范式第 91 守恒 — master runbook 统一索引 PR9 + PR10 + PR11 部署, 不重复 PR9 / PR10 单 PR runbook 内容。后续 PR11 (W69+) 上线时, 在本文件 §0 总览表追加一行 + 在 §1 SSH 18 步基础上扩到 24 步 (W69 PR11 待开发)。*