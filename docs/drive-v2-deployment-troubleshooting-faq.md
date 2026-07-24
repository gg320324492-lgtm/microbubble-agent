# Drive v2 部署 Troubleshooting FAQ (2026-07-24)

> **范围**: Drive v2 PR9 (评论 thread + 文件版本) + PR10 (协同编辑 WebSocket + Web Push) 部署失败 / 异常时的常见问题与解决路径。
>
> **配套文档**:
> - 总入口 runbook → [docs/drive-v2-pr9-11-deployment-master-runbook.md](drive-v2-pr9-11-deployment-master-runbook.md)
> - PR9 详细迁移说明 → [docs/drive-v2-pr9-deployment.md](drive-v2-pr9-deployment.md)
> - PR9 SSH 12 步流程 → [docs/drive-v2-pr9-deployment-runbook.md](drive-v2-pr9-deployment-runbook.md)
>
> **纪律**: 0 production code 改动铁律维持 — 本 FAQ 仅汇总已有 runbook 的故障处理路径, 不修改 alembic / 路由 / ORM。

---

## Q1: alembic `Multiple head revisions are present`

### 症状

`docker exec microbubble-agent-app-1 alembic upgrade head` 报错:

```
FAILED: Multiple head revisions are present for given argument 'head';
please specify a specific target revision, '<branchname>@head' to narrow
to a specific head, or 'heads' for all heads
```

### 根因

主指挥 merge 062/063 (PR9) 或 064/065 (PR10) 时, 多个 agent **并行**派工但派工 prompt 没明确 down_revision 接续关系 → 每个 agent 都声明 `down_revision = <同一个上游>` → merge 进 main 后 alembic 链在该上游分叉成**两个 head**。

**历史案例**:
- W68 第 3 批 062 + 063 双头 (commit `1852468a6` 修复)
- 064 + 065 未发生 (B-1 / B-3 agent 派工 prompt 已明确接续关系)

### 解决路径

#### 步骤 1: verify 当前 head 数

```bash
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; \
  c=Config(); c.set_main_option('script_location','alembic'); \
  s=ScriptDirectory.from_config(c); print('heads:', s.get_heads())"
```

若输出 `['062_drive_comments', '063_drive_file_versions']` 或 `['064_drive_documents', '065_push_subscriptions']`, 确认双头。

#### 步骤 2: 手动改 down_revision 串单链

```bash
# 改 063 (PR9 F-2):
sed -i 's/down_revision: Union\[str, None\] = "061_drive_folder_share"/down_revision: Union[str, None] = "062_drive_comments"/' \
  alembic/versions/063_drive_file_versions.py

# 改 065 (PR10 Push):
sed -i 's/down_revision: Union\[str, None\] = "064_drive_documents"/down_revision: Union[str, None] = "064_drive_documents"/' \
  alembic/versions/065_push_subscriptions.py  # 如已正确, 跳过
```

#### 步骤 3: 重新 verify

```bash
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; \
  c=Config(); c.set_main_option('script_location','alembic'); \
  s=ScriptDirectory.from_config(c); print('heads:', s.get_heads())"
```

期望输出 `heads: ['065_push_subscriptions']` (单 head)。

#### 步骤 4: commit 串单链修复 + push

```bash
git add alembic/versions/063_drive_file_versions.py
git commit -m "fix(alembic): PR9 串单链 063 -> 062 (W68 第 3 批纪律)"
git push origin main
```

### 预防

- 派工 prompt **必须**写明 `down_revision 接 X`
- merge 顺序必须按 alembic 链 (上游 → 下游)
- merge 后立即 verify 只 1 个 head

详细纪律: [CLAUDE.md "2026-07-24 alembic 并行 agent 串单链纪律"](../CLAUDE.md)

---

## Q2: `Can't locate revision identified by '062/063/064/065'`

### 症状

```bash
docker exec microbubble-agent-app-1 alembic upgrade head
# ERROR: Can't locate revision identified by '064_drive_documents'
```

### 根因

两种情况:
1. **cp 漏文件**: `docker cp` 没把所有 4 个迁移文件拷进容器
2. **pycache 没清**: `__pycache__/*.pyc` 让老 down_revision 继续生效 (W68 第 3 批铁律第 5 条)

### 解决路径

#### 步骤 1: 重新 cp 全套迁移文件

```bash
docker cp alembic/versions/062_drive_comments.py microbubble-agent-app-1:/app/alembic/versions/
docker cp alembic/versions/063_drive_file_versions.py microbubble-agent-app-1:/app/alembic/versions/
docker cp alembic/versions/064_drive_documents.py microbubble-agent-app-1:/app/alembic/versions/
docker cp alembic/versions/065_push_subscriptions.py microbubble-agent-app-1:/app/alembic/versions/
```

#### 步骤 2: 清 `__pycache__` (CLAUDE.md 752 行铁律升级)

```bash
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  rm -rf /app/alembic/versions/__pycache__
```

#### 步骤 3: 重跑 alembic

```bash
docker exec microbubble-agent-app-1 alembic upgrade head
docker exec microbubble-agent-app-1 alembic current
# 期望: 065_push_subscriptions (head)
```

---

## Q3: `relation "drive_comments" already exists` (重复迁移)

### 症状

```bash
docker exec microbubble-agent-app-1 alembic upgrade head
# ERROR: relation "drive_comments" already exists
```

### 根因

之前跑过一半 — 表建成功但 `alembic_version` 没更新 (典型场景: 迁移中途网络中断 / 容器 OOM kill / 主指挥手动回滚 alembic 命令)。

### 解决路径

#### 方案 A: 删表重来 (干净起点)

```bash
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "DROP TABLE drive_comments CASCADE;"
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "DROP TABLE drive_file_versions CASCADE;"
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "DROP TABLE drive_documents CASCADE;"
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "DROP TABLE drive_doc_op_logs CASCADE;"
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "DROP TABLE push_subscriptions CASCADE;"
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "DROP TABLE push_delivery_log CASCADE;"
docker exec microbubble-agent-app-1 alembic upgrade head
```

**警告**: DROP 会清空所有数据, 先备份!

#### 方案 B: stamp 跳过 (确认表结构已对齐)

```bash
# 已知表结构与 migration 完全一致时, 用 stamp 标记跳过
docker exec microbubble-agent-app-1 alembic stamp 062_drive_comments
docker exec microbubble-agent-app-1 alembic stamp 063_drive_file_versions
docker exec microbubble-agent-app-1 alembic stamp 064_drive_documents
docker exec microbubble-agent-app-1 alembic stamp 065_push_subscriptions
```

仅在 `psql \d <table>` 输出与 migration 文件 `op.create_table()` 列定义完全一致时使用。

### 预防

迁移前**必须**先备份 (见 [master runbook §5.3 数据保留](drive-v2-pr9-11-deployment-master-runbook.md#5-回滚方案-alembic-downgrade--docker-restart))。

---

## Q4: `column ... does not exist` 500 (部署后)

### 症状

部署 + alembic upgrade 后, 浏览器访问 drive 文件详情页报 500:

```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedColumn) column drive_comments.file_id does not exist
```

### 根因

迁移跑了但 **app 进程没重启** — ORM 元数据陈旧, 还在用老 schema (CLAUDE.md 752 行铁律)。

### 解决路径

#### 步骤 1: 重启后端

```bash
docker compose restart app celery-worker
```

#### 步骤 2: 看启动日志确认 router 注册无异常

```bash
docker compose logs app --tail 50 | grep -iE "error|traceback|drive|push|collab"
```

**期望**: 仅看到 router 注册日志, 无 `column does not exist` / `relation does not exist` 错误。

#### 步骤 3: 验证 endpoint

```bash
curl -sk -o /dev/null -w "%{http_code}\n" \
  "https://<域名>/api/v1/drive/comments?file_id=1" \
  -H "Authorization: Bearer $TOKEN"
# 期望: 200 (有评论) 或 200 空列表 (无评论) 或 401 (无 token)
```

### 预防

**任何 alembic migration 之后必重启** (CLAUDE.md 752 行铁律)。建议加 `scripts/deploy-auto.sh` 自动化检查: alembic 升级后立即 restart。

---

## Q5: WebSocket 超时 (WS 路由 4401/4403)

### 症状

```bash
curl -i wss://<域名>/api/v1/drive/files/1/collab
# curl: (52) Empty reply from server
# 或: HTTP/1.1 4401 Unauthorized / 4403 Forbidden
```

### 根因

1. **4401 Unauthorized**: WS 升级时缺 JWT token (PR10 WS 路由用 query param `?token=<JWT>` 鉴权, 不是 header)
2. **4403 Forbidden**: token 过期 / 用户无权限 / file 不存在
3. **Empty reply**: nginx 没配置 WebSocket Upgrade (`proxy_set_header Upgrade $http_upgrade;` + `proxy_set_header Connection "upgrade";`)

### 解决路径

#### 场景 4401 / 4403

```bash
# 正确格式 (query param, 不是 Authorization header)
python scripts/verify_pr10_collab_ws.py \
  --base-url ws://<域名> \
  --file-id <FILE_ID> \
  --token "<JWT>" \
  --apply
```

或浏览器 DevTools → Console:

```javascript
const ws = new WebSocket('wss://<域名>/api/v1/drive/files/1/collab?token=<JWT>')
ws.onopen = () => console.log('OPEN', ws.readyState)
ws.onerror = (e) => console.error('ERR', e)
```

#### 场景 Empty reply (nginx 配置问题)

SSH 到云服务器, 检查 nginx 配置:

```bash
grep -A 5 "location /api/v1/drive/files" /etc/nginx/conf.d/tunnel.conf
# 期望: 包含 proxy_set_header Upgrade $http_upgrade;
#                  proxy_set_header Connection "upgrade";
```

若缺失, 加 `proxy_set_header Connection "upgrade";` + `proxy_http_version 1.1;` 后 `nginx -s reload`。

### 预防

部署后**必须**用 `verify_pr10_collab_ws.py --apply` 真连一次 (而不是仅 dry-run 静态检查)。

---

## Q6: pycrdt import error (`ModuleNotFoundError: No module named 'pycrdt'`)

### 症状

```bash
docker compose logs app --tail 50
# ModuleNotFoundError: No module named 'pycrdt'
# 或: ImportError: cannot import name 'Doc' from 'pycrdt'
```

### 根因

§Step 6 pip install 漏装 / app 与 celery-worker 装的版本不一致 / 镜像没 rebuild。

### 解决路径

#### 步骤 1: 在 app 和 worker 两边都装

```bash
docker exec microbubble-agent-app-1 pip install 'pycrdt>=0.10' 'pywebpush>=0.14.1'
docker exec microbubble-agent-celery-worker-1 pip install 'pycrdt>=0.10' 'pywebpush>=0.14.1'
```

#### 步骤 2: 验证两边版本一致

```bash
docker exec microbubble-agent-app-1 pip show pycrdt | grep Version
docker exec microbubble-agent-celery-worker-1 pip show pycrdt | grep Version
# 期望: 两边输出版本号完全一致 (如 0.10.5)
```

#### 步骤 3: 重启后端

```bash
docker compose restart app celery-worker
docker compose logs app --tail 50 | grep -iE "error|traceback"
```

**期望**: 无 `ModuleNotFoundError` / `ImportError`。

### 预防

**生产镜像应在 Dockerfile 固定 `pycrdt` + `pywebpush` 版本**, 而不是每次部署临时 `pip install` (避免 app/worker 版本漂移)。

建议: `Dockerfile` 加:

```dockerfile
RUN pip install 'pycrdt==0.10.5' 'pywebpush==0.14.1'
```

---

## Q7: Push 失败 410 (订阅自动清理)

### 症状

后端日志:

```
[ERROR] Push delivery failed: 410 Gone
  endpoint: https://fcm.googleapis.com/fcm/send/...
  user_id: 5
```

### 根因

浏览器 / 系统清理了过期 push 订阅 (典型场景):
- 用户清浏览器缓存 / Cookie
- 用户重装 Chrome / Edge
- Chrome 90 天未访问清理 (Google 策略)
- iOS Safari 关闭 PWA 通知权限
- Android 系统设置关闭通知

### 解决路径

#### 前端自动处理 (Drive v2 PR10 已实现)

PR10 前端 SW 在收到 410 响应时自动调 `DELETE /api/v1/push/subscriptions/{id}` 清理, 用户无感知。

#### 后端手动清理 (兜底)

若前端 SW 未触发 (用户离线 / 浏览器已卸载), 后端定期清理 (建议加 Celery task):

```python
# app/services/push_service.py (建议添加)
async def cleanup_expired_push_subscriptions(db: AsyncSession):
    """删除 90 天未更新的 push_subscriptions"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    stmt = delete(PushSubscription).where(
        PushSubscription.last_seen_at < cutoff
    )
    await db.execute(stmt)
    await db.commit()
```

### 用户操作

用户重新开启 PWA 通知权限 → 前端自动重建订阅:

1. 浏览器打开 https://\<域名\> → 设置 → 通知 → 允许
2. 前端 SW 自动调 `POST /api/v1/push/subscriptions` 插入新记录

---

## Q8: VAPID 密钥丢失 (deployment 提示重启后订阅失效)

### 症状

部署后所有 push 通知发不出去:

```
[ERROR] WebPushException: NoSuchAuthKeyError
  或: pywebpush 报 "missing applicationServerKey"
```

### 根因

服务端 VAPID 密钥 (公钥 + 私钥对) 在容器重启 / 镜像 rebuild 后丢失, 但客户端 push_subscriptions 仍用老的公钥订阅 → 服务端用新私钥签名 → 客户端验证失败 → 410 Gone。

### 解决路径

#### 步骤 1: 检查 VAPID 密钥配置

```bash
docker exec microbubble-agent-app-1 python -c "
from app.config import settings
print('VAPID_PUBLIC_KEY:', settings.VAPID_PUBLIC_KEY[:20] + '...' if settings.VAPID_PUBLIC_KEY else 'EMPTY')
print('VAPID_PRIVATE_KEY:', settings.VAPID_PRIVATE_KEY[:20] + '...' if settings.VAPID_PRIVATE_KEY else 'EMPTY')
"
```

若任一为 `EMPTY`, 服务端未配置 VAPID。

#### 步骤 2: 生成新 VAPID 密钥 (持久化到 .env)

```bash
# 在主指挥本地 PC 生成 (不要在容器内生成, 否则容器重启丢失)
python -c "
from py_vapid import Vapid
v = Vapid()
v.generate_keys()
print('VAPID_PUBLIC_KEY:', b64url_encode(v.public_key.public_bytes()))
print('VAPID_PRIVATE_KEY:', b64url_encode(v.private_key.private_bytes()))
"
```

把输出写入 `E:\microbubble-agent\.env`:

```bash
VAPID_PUBLIC_KEY=<生成的公钥>
VAPID_PRIVATE_KEY=<生成的私钥>
VAPID_SUBJECT=mailto:admin@example.com
```

#### 步骤 3: 重建容器 / restart app

```bash
docker compose up -d app   # 强制用新 .env
docker compose restart app celery-worker
```

#### 步骤 4: 清空老订阅 (强制用户重新订阅)

```bash
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "DELETE FROM push_subscriptions;"
```

#### 步骤 5: 通知用户重新允许通知

发群通知: "VAPID 密钥已更新, 请在浏览器重新开启 PWA 通知权限"。

### 预防

**VAPID 密钥必须**:
1. 持久化到 `.env` (不进 git, .gitignore 已拦)
2. 跨容器 / 跨服务器共享 (建议放云端 secrets manager, 本地用 .env)
3. **永不**容器内生成 (容器重启丢失)
4. **永不**每次部署轮换 (除非密钥泄漏, 否则保持稳定)

---

## 总结表

| Q | 问题 | 解决路径 | 预防 |
|---|------|---------|------|
| Q1 | alembic 双头 | 改 down_revision 串单链 + verify + commit | 派工 prompt 明确接续 |
| Q2 | Can't locate revision | 重 cp + 清 pycache | cp 后必清 pycache |
| Q3 | relation already exists | DROP TABLE 重跑 或 alembic stamp | 迁移前必备份 |
| Q4 | column does not exist 500 | docker compose restart | 迁移后必 restart |
| Q5 | WS 4401/4403/Empty | 用 query param token / nginx upgrade 配置 | 部署后真连验证 |
| Q6 | pycrdt import error | app + worker 两边装 + 版本一致 | Dockerfile 固定版本 |
| Q7 | Push 410 | 前端 SW 自动清理 + 后端兜底 Celery | 前端 SW 监听 410 |
| Q8 | VAPID 密钥丢失 | .env 持久化 + 清空订阅 + 通知用户 | VAPID 永不轮换 |

---

*文档: W68 路线 8 A-2 (2026-07-24). 锚点范式第 91 守恒 — 故障 FAQ 集中化避免散落在多份 runbook, 主指挥排错时一查就够。*