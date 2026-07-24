# Drive v2 PR10 部署运行手册

> 适用范围：协同编辑 WebSocket、Redis pub/sub、Celery 文档 flush、pycrdt、Web Push。
> 本手册只在 PR10 及其依赖迁移全部合并到 `main` 后执行。

## 0. 风险警告

PR10 的复杂度是 PR9 的数倍。一次部署同时改变 WebSocket endpoint、Redis pub/sub channel、Celery flush 任务、pycrdt 二进制文档状态和 Push subscription。任何一步失败都可能表现为“页面能打开但协同编辑不更新”或“刷新后内容回退”。禁止只执行 `git pull && restart`。

上线前必须确认：

- PR10 分支已合入主线，064/065/066/067 迁移文件在同一提交集合中。
- pycrdt 版本在应用和 worker 中一致；不要让 worker 使用旧 wheel。
- Redis channel 命名与代码完全一致，不能手工猜 channel。
- 至少用两个浏览器窗口验证同一文件的编辑广播，并验证断线重连。
- 首次上线保留 Redis、PostgreSQL、Celery 日志窗口，观察 15 分钟。

## 1. SSH 部署（18 步）

在跳板机登录部署用户后执行。变量按环境替换：

```bash
export APP_DIR=/opt/microbubble-agent
export APP= microbubble-agent-app-1   # 去掉等号后的空格后使用
export APP= microbubble-agent-app-1
export DB=microbubble-agent-postgres-1
export BASE=https://example.invalid
export FILE_ID=1
cd "$APP_DIR"
```

1. 拉取主线并合入 PR10 分支（如 PR10 尚未合入，停止部署）：

```bash
git fetch origin --prune
git checkout main
git pull --ff-only origin main
git merge --no-ff origin/feat/drive-v2-pr10-collab-crud
```

2. 将 064、065、066、067 迁移复制到容器（文件不存在时停止）：

```bash
for f in alembic/versions/064_*.py alembic/versions/065_*.py alembic/versions/066_*.py alembic/versions/067_*.py; do
  test -f "$f" || { echo "missing $f"; exit 1; }
  docker cp "$f" "$APP:/app/alembic/versions/"
done
```

3. 清理 Python migration 缓存：

```bash
docker exec -e SKIP_DB_SETUP=1 "$APP" rm -rf /app/alembic/versions/__pycache__
```

4. 升级数据库并确认只有一个 head：

```bash
docker exec "$APP" alembic upgrade head
docker exec "$APP" alembic heads
# 期望：067_push_subscriptions（单 head）
```

5. 在 app 和 celery worker 安装兼容依赖（生产镜像更推荐在镜像构建阶段固定）：

```bash
docker exec "$APP" pip install 'pycrdt>=0.10' 'pywebpush>=0.14.1'
docker exec microbubble-agent-celery-worker-1 pip install 'pycrdt>=0.10' 'pywebpush>=0.14.1'
```

6. 重启应用和 worker：

```bash
docker compose restart app celery-worker
```

7. 验证快照 API 返回 200：

```bash
curl -fsS -o /tmp/snapshot.json -w '%{http_code}\n' "$BASE/api/v1/drive/files/$FILE_ID/snapshot"
```

8. 验证 WebSocket 连通（先安装 wscat）：

```bash
npx --yes wscat -c "wss://${BASE#https://}/api/v1/drive/files/$FILE_ID/collab"
```

应完成握手；未认证环境用部署测试 JWT，禁止把真实 token 写入 shell 历史。

9. 验证 VAPID 公钥：

```bash
curl -fsS "$BASE/api/v1/push/vapid-public-key" | python -m json.tool
```

响应必须包含非空公钥。

10. 用管理员测试 endpoint 发送一条 push（仅测试用户/设备）：

```bash
curl -fsS -X POST "$BASE/api/v1/admin/push/test" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"user_id":1,"title":"PR10 deployment test","body":"discard me"}'
```

11. 验证 Celery flush：在两个窗口编辑文件，等待至少 30 秒，然后检查 `drive_documents.ydoc_state` 非空且时间戳更新：

```bash
docker exec "$DB" psql -U postgres -d microbubble -c \
  "select id, length(ydoc_state), updated_at from drive_documents where id=$FILE_ID;"
```

12. 执行基线检查：期望 71 PASS、7 SKIP、0 FAIL：

```bash
bash scripts/verify_drive_v2_pr9_deployment.sh
bash scripts/verify_w68_5th_batch_deployment.sh
python scripts/verify_pr10_collab_ws.py
```

13. 浏览器验证桌面端和移动端：登录、打开同一文件、双窗口输入、刷新恢复、断网重连；在 Android Chrome 和 iOS Safari 检查 PWA install 与通知权限。

14. 观察 app/worker/Redis 日志 15 分钟，确认没有 serialization、channel、410 或 migration 错误。

15. 检查 Redis pub/sub 订阅数和无异常堆积：

```bash
docker exec microbubble-agent-redis-1 redis-cli PUBSUB CHANNELS 'drive:*'
```

16. 检查 worker flush 任务成功率和 Celery 队列长度：

```bash
docker exec microbubble-agent-redis-1 redis-cli LLEN celery
```

17. 保存部署证据（commit、alembic heads、API/WS 输出、基线结果），不保存 token 或文档内容。

18. 通知用户 PR10 已上线、验证窗口和回滚联系人；若任一步失败，立即停止并按第 5 节回滚。

## 2. Alembic 链风险

PR10 的 `064_drive_documents` 必须先于 `065_push_subscriptions`。066、067 继续接在其后。合并顺序必须是 064 → 065 → 066 → 067；不能让两个分支都声明同一个 `down_revision`。

主指挥合并 PR10 时必须手动检查并在必要时修改：

```python
down_revision = "063_previous_revision"  # 064
# 065 必须是 064 的 revision id
down_revision = "<064 revision>"
# 066 必须接 065；067 必须接 066
```

合并后立即运行：

```bash
python - <<'PY'
from alembic.config import Config
from alembic.script import ScriptDirectory
c=Config(); c.set_main_option('script_location','alembic')
print(ScriptDirectory.from_config(c).get_heads())
PY
```

只允许一个 head，且应为 `067_push_subscriptions` 对应 revision。不要用 `alembic upgrade heads` 掩盖分叉。

## 3. 验证脚本

### 3.1 PR9 基线

`scripts/verify_drive_v2_pr9_deployment.sh` 检查 Drive v2 API、迁移与基础配置。先在仓库根目录执行；它是回归基线，不替代 WS 测试。

### 3.2 W68 第五批

`scripts/verify_w68_5th_batch_deployment.sh` 检查第五批部署约束和测试基线。执行前确认脚本在当前主线存在并具有执行权限。

### 3.3 PR10 协同 WS

`scripts/verify_pr10_collab_ws.py` 默认 dry-run，只检查表、服务方法和路由注册，不建立真实连接：

```bash
python scripts/verify_pr10_collab_ws.py --base-url "$BASE" --file-id "$FILE_ID"
```

只有维护窗口中才使用：

```bash
python scripts/verify_pr10_collab_ws.py --apply --base-url "$BASE" --file-id "$FILE_ID" --token "$TEST_TOKEN"
```

脚本兼容 Linux/Windows，`websockets` 不可用时会明确报告安装提示，不会误报成功。

## 4. 已知问题与 FAQ

1. **为什么快照 404？** 文件可能没有对应 `drive_documents` 行；先确认迁移和文件 ID，不要直接重试 WS。
2. **WS 握手 401/403？** 使用测试 JWT，并确认反向代理允许 Upgrade/Connection 头；不要关闭鉴权。
3. **两个窗口不广播？** 检查 Redis channel 前缀、订阅日志和 worker/app 是否使用同一 Redis DB。
4. **刷新后内容丢失？** 检查 `ydoc_state` 长度、flush 任务和 pycrdt 版本；二进制状态不可用文本编码转换。
5. **push 返回 410/404？** 设备订阅已过期或 endpoint 被撤销；清理订阅后重新授权，VAPID 私钥不可更换。
6. **alembic multiple heads？** 停止部署，按第 2 节修正 `down_revision` 后重新合并；不要执行 `upgrade heads`。

## 5. 回滚方案

回滚前通知在线编辑用户并暂停新编辑。先恢复应用代码到上一个已知 commit，再按链反向降级：

```bash
docker exec "$APP" alembic downgrade -1   # 067
# 需要完整移除 PR10 时继续：
docker exec "$APP" alembic downgrade -2   # 066、067
# 仍需移除 push/PR10：
docker exec "$APP" alembic downgrade -3   # 065、066、067（按实际链确认）
```

不要在未知数据状态下删除 `drive_documents`。先备份表和 `ydoc_state`。清理临时 pub/sub channel（不会删除持久化数据）：

```bash
docker exec microbubble-agent-redis-1 redis-cli --scan --pattern 'drive:collab:*' | while read k; do redis-cli -h microbubble-agent-redis-1 DEL "$k"; done
```

停止或清空尚未执行的 flush 任务前需确认队列中没有其他业务任务：

```bash
docker exec microbubble-agent-celery-worker-1 celery -A app.celery_app purge -f
```

最后重启 app/worker，确认 PR9 快照与文件下载恢复，再向用户发布回滚通知。所有降级命令、数据备份路径和观测结果必须写入变更记录。
