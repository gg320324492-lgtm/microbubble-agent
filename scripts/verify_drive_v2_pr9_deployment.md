# Drive v2 PR9 部署验证脚本 (2026-07-24, W68 第 4 批 H-2)

> **配套脚本**: `scripts/verify_drive_v2_pr9_deployment.sh`
> **配套文档**: `docs/drive-v2-pr9-deployment.md` (W68 第 3 批 H-1)
> **适用版本**: Drive v2 PR9 (F-1 评论 + F-2 版本 + F-3 移动端 UI)
> **锚点范式**: 第 57 守恒

---

## 1. 用途

主指挥 SSH 部署完代码 + alembic 迁移 + 容器重启后, 一键跑本脚本自动验证:

- ✅ alembic 落点 = `063_drive_file_versions`
- ✅ 4 张 Drive v2 表全部存在 (`drive_comments` / `drive_file_versions` + PR7 `drive_folder_*`)
- ✅ 6 个 Drive v2 PR9 endpoint 可达 + 鉴权生效
- ✅ WebSocket `/api/v1/ws/notifications` 可连 (curl Upgrade 探测 101)
- ✅ XOR 校验 + 无 token 401 负例
- ❌ 任意失败 → exit 1, 主指挥**不要**通知团队上线

**替代**: 之前靠主指挥手动跑 6 条 `curl` (易漏、易复制粘贴错). 现在一键 10 个点全跑.

---

## 2. 用法

### 2.1 最简用法 (本地 PC, 默认值)

```bash
bash scripts/verify_drive_v2_pr9_deployment.sh
```

默认 `BASE_URL=https://localhost` (经 FRP 暴露). 无 TOKEN 时只跑 401 负例, 其余 SKIP.

### 2.2 标准用法 (推荐, 含 JWT)

```bash
# 1. 拿 JWT (登录)
TOKEN=$(curl -s -X POST https://your.domain/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"xxx"}' | jq -r .access_token)

# 2. 找测试用 drive 文件 ID (任意一个 knowledge entry)
FILE_ID=$(docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -t -c "SELECT id FROM knowledge WHERE deleted_at IS NULL LIMIT 1;" | tr -d ' \n')

# 3. 跑验证
BASE_URL=https://your.domain TOKEN="$TOKEN" FILE_ID="$FILE_ID" \
  bash scripts/verify_drive_v2_pr9_deployment.sh
```

### 2.3 DRY_RUN 模式 (本地测试脚本本身)

```bash
DRY_RUN=1 bash scripts/verify_drive_v2_pr9_deployment.sh
```

只打印 curl 命令不真发请求, 用于脚本调试 / CI smoke.

---

## 3. 输出示例

### 3.1 全部 PASS (期望)

```
== Drive v2 PR9 部署验证 (W68 第 4 批 H-2) ==
  ·      BASE_URL = https://your.domain
  ·      FILE_ID  = 42
  ·      TOKEN    = <已设置>
  ·      DRY_RUN  = 0
  ✓ PASS  curl 已安装 (curl 8.x)

== Drive v2 PR9 端点验证 (6 点) ==
  ✓ PASS  评论列表返回 200 + 标准分页结构
  ✓ PASS  创建评论成功 (id=187)
  ✓ PASS  XOR 校验生效 (返 400)
  ✓ PASS  版本列表返回 200 + 数组结构
  ✓ PASS  版本下载返 200 (version_id=12)
  ✓ PASS  无鉴权请求返 401 (符合预期)

== WebSocket 探测 ==
  ✓ PASS  WebSocket 101 Switching Protocols (连接成功)

== 数据库 schema 验证 (alembic + 4 张表) ==
  ✓ PASS  alembic 落点 = 063_drive_file_versions
  ✓ PASS  表 drive_comments 存在
  ✓ PASS  表 drive_file_versions 存在
  ✓ PASS  表 drive_folder_members 存在
  ✓ PASS  表 drive_folder_shares 存在

== 总结 ==
  总计: 14  通过: 14  失败: 0  跳过: 0

✅ Drive v2 PR9 部署验证全部通过
```

退出码 = 0.

### 3.2 部分 FAIL (排错示例)

```
== Drive v2 PR9 端点验证 (6 点) ==
  ✗ FAIL  评论列表未返 200
         原因: HTTP_CODE=500, body={"error":{"code":"RESOURCE_NOT_FOUND"}}

== 数据库 schema 验证 (alembic + 4 张表) ==
  ✗ FAIL  alembic 落点不是 063_drive_file_versions
  ✗ FAIL  表 drive_file_versions 缺失

== 总结 ==
  总计: 14  通过: 11  失败: 3  跳过: 0

❌ Drive v2 PR9 部署验证有 3 项失败
```

退出码 = 1. 立即按 FAIL 详情排错, **不要**继续通知团队.

---

## 4. 排错速查

| FAIL 信息 | 根因 | 修复 |
|----------|------|------|
| `alembic 落点不是 063_drive_file_versions` | 没按解法 A 改 063 `down_revision` (应=062 而非 061), 或迁移没跑 | 改 `alembic/versions/063_drive_file_versions.py` 第 4 行 `down_revision` + docker cp + 清 pycache + `alembic upgrade head` (见 [docs §1.2](drive-v2-pr9-deployment.md#12-迁移步骤-claudemd-752-行铁律标准-3-步)) |
| `表 drive_comments 缺失` | 062 迁移没跑成功 | docker cp 062 文件 + 清 pycache + 重跑 alembic |
| `表 drive_file_versions 缺失` | 063 迁移没跑成功 | 同上, 换 063 文件 |
| `评论列表未返 200` (HTTP 500) | 迁移跑了但 app 容器没 restart, ORM 元数据陈旧 | `docker compose restart app celery-worker` (CLAUDE.md 752 行铁律) |
| `评论列表未返 200` (HTTP 404) | router 没注册 | 检查 `app/main.py` 是否 include `drive_comments.router` |
| `创建评论返 201 但 body 无 id 字段` | API 响应 schema 变更 | 跑 `pytest tests/api/test_drive_comments.py -x` 验证 schema |
| `版本下载未返 200` | MinIO 对象缺失 (历史版本上传后被删) | 见 [docs §4.3](drive-v2-pr9-deployment.md#43-数据保留说明) — `mc ls` 检查 MinIO bucket |
| `无鉴权未返 401` | router 没接入 `get_current_user` | **严重安全问题**, 立即修 router 装饰器 |
| `WebSocket 返 000 (超时)` | curl 默认不支持长连接 | 用浏览器 DevTools → `new WebSocket(...)` 验证 |
| `WebSocket 返 401/403` | token 失效或 ws 端点鉴权错 | 用浏览器 DevTools → Network → WS 帧查看连接握手 |

---

## 5. 回滚提示

如果验证失败无法快速修复, **不要**带病上线. 立即按 [docs §4 回滚方案](drive-v2-pr9-deployment.md#4-第-4-节-回滚方案):

```bash
# 1. alembic 降级 (解法 A 单链)
docker exec microbubble-agent-app-1 alembic downgrade -1   # 卸 063
docker exec microbubble-agent-app-1 alembic downgrade -1   # 卸 062

# 2. 代码回滚 (merge commit 用 -m 1)
git revert -m 1 <F-1 merge hash>
git revert -m 1 <F-2 merge hash>
git revert -m 1 <F-3 merge hash>   # 前端需重跑 npm run build + force-add dist
git push origin main

# 3. 重启后端 (任何回滚后必须 restart)
docker compose restart app celery-worker

# 4. 验证回滚干净 (期望只剩 061 两张表)
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\dt drive_*"
```

回滚决策应在 < 5 分钟内完成 (对齐 chat_engine_legacy 收官的回滚 SLA).

---

## 6. 集成进部署流水线 (可选)

`scripts/deploy-auto.sh` 第 2 阶段 (后端 restart 后) 加一行:

```bash
log "Step 2.5: 跑 Drive v2 PR9 端到端验证"
if ! bash scripts/verify_drive_v2_pr9_deployment.sh; then
    log "ERROR: Drive v2 PR9 验证失败, 中止部署"
    exit 1
fi
```

这样部署脚本自带健康门禁, 任何 PR9 endpoint 异常自动拦下后续 webhook 推送. (W68 第 5 批可考虑加, 当前 PR 不动 `deploy-auto.sh`).

---

*文档: W68 第 4 批 H-2 (2026-07-24). 详细 API 见 `docs/drive-v2-pr9-comments.md` + `docs/drive-v2-pr9-versions.md`. 部署流程见 `docs/drive-v2-pr9-deployment.md`. memory 沉淀见 `memory/w68-route-drive-pr9-deploy-verify-2026-07-24.md`.*