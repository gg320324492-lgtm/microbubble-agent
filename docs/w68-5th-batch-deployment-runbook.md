# W68 第 5 批 + 3 hot-fix SSH 部署 Runbook (2026-07-24)

> **范围**: 主指挥本地 PC (Docker 8 services 宿主机) 部署 W68 第 5 批 18 commits (15 agent + 3 hot-fix) + Drive v2 PR10 骨架表 (alembic 064) 的**流程化操作手册**。
>
> **配套文档**:
> - Drive v2 PR9 迁移 + alembic 链风险 (单链 061→062→063) → [docs/drive-v2-pr9-deployment.md](docs/drive-v2-pr9-deployment.md)
> - Drive v2 PR9 部署 12 步 → [docs/drive-v2-pr9-deployment-runbook.md](docs/drive-v2-pr9-deployment-runbook.md)
> - Drive v2 PR10 协同编辑调研 (W68 第 5 批 #2) → [docs/drive-v2-pr10-collab-editing.md](docs/drive-v2-pr10-collab-editing.md)
> - Drive v2 PR10 设计细节 → [docs/drive-v2-pr10-collab-editing-design.md](docs/drive-v2-pr10-collab-editing-design.md)
> - 端到端验证 (含 3 hot-fix + alembic 064 + baseline) → [scripts/verify_drive_v2_pr9_deployment.sh](../scripts/verify_drive_v2_pr9_deployment.sh) [489 行]
> - W68 第 5 批轻量 verify (~150 行) → [scripts/verify_w68_5th_batch_deployment.sh](../scripts/verify_w68_5th_batch_deployment.sh)
> - 锚点范式沉淀 → [memory/w68-route-7-d1-5th-batch-deploy-2026-07-24.md](../memory/w68-route-7-d1-5th-batch-deploy-2026-07-24.md)
>
> **约束**: 0 production code 改动铁律维持 — 本 runbook 只描述部署流程, 不修改 alembic / 路由 / ORM。

---

## 0. ⚠️ 部署前必读 (3 个硬约束)

1. **主指挥本地 PC**: Docker 8 services 宿主机 (`/e/microbubble-agent` 或 `E:\microbubble-agent`)。
2. **云服务器**: 只跑 Nginx + FRP, **不跑 alembic / 不重建容器** — 部署命令全部在本机。
3. **alembic 064 链**: 已按 W68 第 5 批 D-2 单链 `063 → 064` 串好 (`down_revision="063_drive_file_versions"`)。若 git log 看 main 还没合并 `064_drive_documents.py`, **不要**先跑 `alembic upgrade head`, 否则会报 `Multiple head revisions` 阻塞。
4. **重要铁律**: 部署迁移前必须先 `cd /e/microbubble-agent && git pull`, 否则 alembic 文件不是最新。
5. **PR10 调研边界**: W68 第 5 批 #2 agent 只产出调研文档 + 空骨架表 (`drive_documents` + `drive_doc_op_logs`), **未实施** WS 协同编辑端点。生产侧 alembic 064 跑完后表是空的, 这是预期行为。WS 实现需 W69 单独派工。

---

## 1. SSH 部署 15 步 (主指挥流程化操作)

主指挥在本机终端跑下列命令, 每步按 §6 退出码判断 PASS/FAIL。

### 1.1 拉最新 main (必须)

```bash
cd /e/microbubble-agent  # 或 E:\microbubble-agent
git checkout main
git pull origin main
git log --oneline -1   # 期望: 05c60e68d merge: w68-5th-batch-version-diff-lineterm-2026-07-24 (W68 第 5 批 hot-fix)
```

### 1.2 检查 alembic 064 文件已 merge

```bash
ls -la alembic/versions/064_drive_documents.py
# 期望: 文件存在 (300+ 字节, 含 drive_documents + drive_doc_op_logs 2 张表定义)

grep "down_revision" alembic/versions/064_drive_documents.py | head -2
# 期望: down_revision: Union[str, None] = "063_drive_file_versions"
```

### 1.3 copy alembic 064 文件到容器 + 清理 `__pycache__` (CLAUDE.md 752 行铁律)

```bash
docker cp alembic/versions/064_drive_documents.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
```

**为什么清 `__pycache__`**: 容器里若残留老 `064_*` 的 `.pyc`, Python 优先加载缓存, 会让新的 `down_revision="063_drive_file_versions"` 不生效, 双头假修复。

### 1.4 跑 alembic upgrade head

```bash
docker exec microbubble-agent-app-1 alembic upgrade head
# 期望: Running upgrade 063_drive_file_versions -> 064_drive_documents
# 期望: 无 "Multiple head revisions" 报错
```

### 1.5 验证 alembic 落点 = 064

```bash
docker exec microbubble-agent-app-1 alembic current
# 期望: 064_drive_documents (head)
```

### 1.6 重启后端 2 服务 (CLAUDE.md 752 行铁律)

```bash
docker compose restart app celery-worker
# 期望: app-1 + celery-worker-1 都 RUNNING
```

### 1.7 等 5-8s 让 uvicorn 完全启动

```bash
sleep 8 && docker compose logs app --tail 30 | grep -i "started\|application startup\|uvicorn"
# 期望: "Uvicorn running on http://0.0.0.0:8000" 或 "Application startup complete"
```

### 1.8 验证 hot-fix #18 (uploader_id → created_by)

```bash
grep -c "uploader_id" app/services/drive_comment_service.py
# 期望: 0 (或 <= 2, 仅注释里出现的提示文字)
```

### 1.9 验证 hot-fix #16 (select import)

```bash
docker exec microbubble-agent-app-1 python -c "from app.services.drive_version_diff_service import DriveVersionDiffService; print('OK')"
# 期望: OK (无 ImportError 或 NameError)
```

### 1.10 验证 hot-fix #17 (lineterm="\n") 真跑

```bash
docker exec microbubble-agent-app-1 python -c "
from app.services.drive_version_diff_service import DriveVersionDiffService
u, cl, adds, dels = DriveVersionDiffService._compute_text_diff(
    from_text='hello\nworld\n', to_text='hello\nmoon\n',
    from_label='v1', to_label='v2')
print('UNIFIED_LEN=' + str(len(u)), 'HAS_HUNK=' + ('Y' if '@@' in u else 'N'))
"
# 期望: UNIFIED_LEN=非零数  HAS_HUNK=Y
```

### 1.11 跑 Drive v2 PR9 + W68 第 5 批 verify (主脚本)

```bash
BASE_URL=https://your.domain TOKEN=$JWT bash scripts/verify_drive_v2_pr9_deployment.sh
# 期望: Drive v2 PR9 + W68 第 5 批 + 3 hot-fix + alembic 064 + baseline 验证全部通过
```

### 1.12 跑 W68 第 5 批专用 verify (轻量)

```bash
bash scripts/verify_w68_5th_batch_deployment.sh
# 期望: W68 第 5 批 + 3 hot-fix 部署验证全部通过
```

### 1.13 跑 baseline 71 PASS + 7 SKIP 守恒

```bash
SKIP_DB_SETUP=1 pytest tests/test_baseline_audit.py -v
# 期望: 71 PASS, 7 SKIP, 0 FAIL
```

### 1.14 验证 PR10 文档 merge (不依赖 alembic)

```bash
ls docs/drive-v2-pr10-*.md
# 期望: drive-v2-pr10-collab-editing.md + drive-v2-pr10-collab-editing-design.md 都在
```

### 1.15 通知团队

```bash
echo "W68 第 5 批 15 agents + 3 hot-fix + Drive v2 PR10 骨架表已部署完成" \
  | docker compose exec -T app python -c "import sys; from app.services.notification_service import notify_slack; notify_slack(sys.stdin.read())"
# 或手发团队群
```

---

## 2. verify 脚本用法对比 (6 用法)

| 脚本 | 行数 | 跑啥 | 适用场景 |
|------|------|------|----------|
| `scripts/verify_drive_v2_pr9_deployment.sh` | 489 | Drive v2 PR9 **12 endpoint HTTP** + WS + alembic + 6 表 + **3 hot-fix 真跑** + baseline | 完整部署验收 (主脚本) |
| `scripts/verify_w68_5th_batch_deployment.sh` | 344 | W68 第 5 批 **18 commit 链** + PR10 文档 + **3 hot-fix 真跑** + alembic 064 + baseline | W68 第 5 批专项验证 (轻量, 无 HTTP) |

### 2.1 主脚本环境变量

```bash
BASE_URL=https://your.domain \  # 默认 https://localhost
TOKEN=eyJ...                   # 默认空 (跑 401 负例)
FILE_ID=42                     # 默认 1
DRY_RUN=1                      # 默认 0
bash scripts/verify_drive_v2_pr9_deployment.sh
```

### 2.2 轻量脚本环境变量

```bash
BASE_DIR=/e/microbubble-agent  # 默认 $(pwd)
DRY_RUN=1                      # 默认 0
bash scripts/verify_w68_5th_batch_deployment.sh
```

### 2.3 退出码约定

| 退出码 | 主脚本含义 | 轻量脚本含义 |
|--------|-----------|--------------|
| 0 | 全部 PASS | 全部 PASS |
| 1 | 任一 FAIL | 任一 FAIL |
| 2 | curl 缺失 / docker 未起 / git 仓库无效 | 配置文件缺失 / docker 未起 |

### 2.4 DRY_RUN 行为

- `DRY_RUN=1` 时, 任何会发 HTTP 请求 / 跑 `pytest` / 跑 `docker exec` 的步骤**只打印命令**, 标记 SKIP
- 主指挥可用 `DRY_RUN=1` 先 sanity-check 脚本本身能不能跑通 (避免线上跑挂)

### 2.5 skip vs fail 区分

- **skip** = 工具缺失 (curl/docker) 或测试环境不具备 (无 TOKEN) → **不阻塞**部署
- **fail** = 验证逻辑**真**不通过 (如 alembic 落点 ≠ 064) → **必须**修复

### 2.6 加新 check 的标准

1. 找对应章节, 加 `log_info` + `log_pass/log_fail/log_skip` 三元组
2. fail 必有第 2 参数 (原因), 便于排查
3. 不要新增对生产代码的依赖 (verify 脚本是 0 production code 改动铁律的范例)

---

## 3. alembic 064 状态 (主指挥拍板决策点)

### 3.1 当前状态 (W68 第 5 批收官后)

| 项 | 状态 | 备注 |
|----|------|------|
| `alembic/versions/064_drive_documents.py` | ✅ 已 merge 到 main | commit 由 W68 第 5 批 #2 调查 agent 提交 |
| `down_revision="063_drive_file_versions"` | ✅ 严格单链 | 接 PR9 最后一节 (commit 1852468a6 教训遵守) |
| DRIVE v2 PR10 文档 | ✅ 已 merge | `drive-v2-pr10-collab-editing.md` + `...-design.md` |
| PR10 WS 协同编辑端点 | ⏸ **未实施** | W69 单独派工 |
| PR10 frontend UI | ⏸ **未实施** | W70+ 派工 |
| Yjs / pycrdt 依赖 | ❌ **未引入** | 待 W69 调研后决定 |

### 3.2 主指挥拍板决策: 是否合并 alembic 064 到生产

**选项 A (推荐)**: 合并 + 跑 `alembic upgrade head`
- ✅ PR10 调研成果落地 (`drive_documents` + `drive_doc_op_logs` 表已建)
- ✅ 桌面端/移动端后续 PR10 实施时不用再跑迁移
- ⚠️ 表是空的, 不影响业务
- ⚠️ 若 W69 调研决定改 Yjs, 表结构可能需变更 → `alembic downgrade -1` 回滚

**选项 B**: 不合并 / 暂留 main 但不跑迁移
- ⏸ 等 W69 调研确定最终技术栈后再合并
- ⏸ 当前 PR9/W68 第 5 批部署**不**需要这张表

**选项 C (不推荐)**: alembic downgrade -1 永久删除 064
- ❌ 调研成果丢失
- ❌ W69 派工时又要重新创建

**主指挥建议**: 选项 A (合并 + 跑迁移), 因为表是空的, 即使后续调整也是 `alembic downgrade -1` 一行命令。

### 3.3 PR10 表 schema 说明 (只读)

```sql
-- drive_documents (1:1 与 Knowledge)
CREATE TABLE drive_documents (
    id SERIAL PRIMARY KEY,
    file_id INTEGER NOT NULL UNIQUE REFERENCES knowledge(id),
    ydoc_state BYTEA,              -- Y.Doc 字节快照
    ops_count INTEGER DEFAULT 0,
    version_number INTEGER DEFAULT 0,
    active_users INTEGER DEFAULT 0,
    updated_at TIMESTAMP
);

-- drive_doc_op_logs (1:N 审计)
CREATE TABLE drive_doc_op_logs (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES drive_documents(id),
    op BYTEA,                       -- Yjs update 字节
    client_id BIGINT,
    user_id INTEGER REFERENCES members(id),
    created_at TIMESTAMP
);
```

7 天后由 Celery `compress_op_logs_task` 合并到 `ydoc_state` 后删除 (待 W69 实施)。

---

## 4. 已知问题 + FAQ (5 个常见问题)

### Q1: `alembic upgrade head` 报 `Multiple head revisions`

**A**: main 上有**两个**head。常见根因:
1. 064 的 `down_revision` 没改对 (必须 = `"063_drive_file_versions"`)
2. 你跑的 alembic 文件不是最新 — `git pull` 后没清理 `__pycache__`

**修复**:
```bash
git pull origin main
docker cp alembic/versions/064_drive_documents.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head
```

参考: CLAUDE.md 2026-07-24 "alembic 并行 agent 串单链纪律" + `memory/w68-alembic-chain-discipline-2026-07-24.md`。

### Q2: hot-fix #16 跑 `from app.services.drive_version_diff_service import ...` 报 `NameError: name 'select' is not defined`

**A**: 这是 hot-fix #16 想修的 bug。docker 镜像里是老代码 (commit 2ca86e05e 之前的)。

**修复**:
```bash
cd /e/microbubble-agent && git pull origin main
docker compose build app --no-cache
docker compose up -d app celery-worker
```

### Q3: hot-fix #17 真跑后 `HAS_HUNK=N`

**A**: lineterm 没传对。检查 `app/services/drive_version_diff_service.py:232`:
```python
difflib.unified_diff(..., lineterm="\n", ...)
```
若发现 `lineterm=""` 或无此参数, 说明 hot-fix #17 没生效。同 Q2 修复。

### Q4: baseline `tests/test_baseline_audit.py` 跑只有 0 PASS

**A**: pytest collect 失败, 不是业务失败。
1. 跑 `pytest tests/test_baseline_audit.py --collect-only` 看错误
2. 99% 是文件路径不存在 (CLAUDE.md W62 baseline 9 files 教训)
3. 修法: 确认 `tests/scripts/` 子目录在 pytest testpaths 里 (默认应在)

### Q5: Drive v2 PR9 verify 跑 endpoint 全返 502 / 504

**A**: FRP 隧道或 Nginx 上游问题, **不是**代码问题。
- 检查 FRP 客户端是否在本地 PC 跑: `frpc status` 或 `ps aux | grep frpc`
- 检查 Nginx upstream: `curl http://localhost:8000/api/v1/health` 应返 200
- 检查云 server FRP 端口监听: 云 server `netstat -anp | grep 7000`

---

## 5. 回滚方案 (3 步)

### 5.1 alembic downgrade -1 (回 PR10, 保留 PR9)

```bash
docker exec microbubble-agent-app-1 alembic downgrade -1
# 期望: 064_drive_documents → 063_drive_file_versions (回滚成功, drive_documents + drive_doc_op_logs 2 表删除)
```

只回滚 PR10 骨架, PR9 评论/版本功能**保留**。

### 5.2 整体回滚 (commit revert)

```bash
cd /e/microbubble-agent
git revert --no-edit 05c60e68d  # hot-fix #17
git revert --no-edit f44957e33  # hot-fix #18
git revert --no-edit 2ca86e05e  # hot-fix #16
# + 视情况 revert W68 第 5 批其他 agent commit
git push origin main  # webhook 触发 30s 自动部署
```

回滚全部 3 hot-fix 约 3 分钟, 不需要 DB 回滚 (hot-fix #16/#17 是 service 文件改动, hot-fix #18 是 ORM 字段名修正)。

### 5.3 docker 全栈重启 (终极回滚)

```bash
docker compose down
docker compose build app --no-cache
docker compose up -d
# 期望: 全部 8 services RUNNING
```

约 2-5 分钟重建, 适用代码 hot-fix 改坏了 alembic 状态的情况。

---

## 6. 常见失败快速排查表

| 症状 | 根因 | 排查命令 |
|------|------|----------|
| `alembic current` 显示旧版 | `__pycache__` 残留 | `docker exec microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__` |
| uvicorn 起不来 | 模块 import 报错 | `docker compose logs app --tail 50` |
| Drive v2 verify 全 401 | TOKEN 过期 | 重登录拿新 TOKEN |
| baseline 0 PASS | pytest collect 失败 | `pytest tests/test_baseline_audit.py --collect-only` |
| hot-fix #17 没生效 | docker 镜像是旧的 | `docker compose build app --no-cache` |
| alembic 064 表不存 | 未跑迁移 | `docker exec microbubble-agent-app-1 alembic upgrade head` |
| WebSocket 探测超时 | curl 不支持长连接 | 改用 wscat 或浏览器 DevTools |

---

## 7. 参考链接

- **CLAUDE.md 锚点范式**: 当前 W68 第 5 批 67 → 本 runbook 帮助守住 第 85 守恒
- **CLAUDE.md 2026-07-24 alembic 串单链纪律**: §"alembic 并行 agent 串单链纪律" (commit 1852468a6 沉淀)
- **memory/w68-alembic-chain-discipline-2026-07-24.md**: alembic 单链铁律 + commit 链
- **memory/w68-route-7-d1-5th-batch-deploy-2026-07-24.md**: 锚点范式第 85 守恒 + 3 新铁律沉淀
- **docs/drive-v2-pr10-collab-editing.md**: PR10 调研 (W68 第 5 批 #2)
- **docs/drive-v2-pr10-collab-editing-design.md**: PR10 设计细节

---

**Runbook 维护者**: W68 第 7 批 D-1 agent
**最后更新**: 2026-07-24
**锚点范式**: 第 85 守恒 (W68 第 5 批扩展 67 → 85)
