# W68 第 7 批 15 commits + 3 hot-fix SSH 部署 Runbook (2026-07-24)

> **范围**: 主指挥本地 PC (Docker 8 services 宿主机) 部署 W68 第 7 批 15 commits (A1→A5 + B1→B3 + C1→C3 + D1→D3 + grand closure) + W68 第 5 批 3 hot-fix (#16/#17/#18) 的**流程化操作手册**。
>
> **配套文档**:
> - Drive v2 PR9 迁移 + alembic 链风险 (单链 061→062→063) → [docs/drive-v2-pr9-deployment.md](docs/drive-v2-pr9-deployment.md)
> - Drive v2 PR9 部署 12 步 → [docs/drive-v2-pr9-deployment-runbook.md](docs/drive-v2-pr9-deployment-runbook.md)
> - W68 第 5 批 + 3 hot-fix 部署 → [docs/w68-5th-batch-deployment-runbook.md](docs/w68-5th-batch-deployment-runbook.md)
> - Drive v2 PR10 协同编辑设计 (W68 第 7 批 B-1) → [docs/drive-v2-pr10-collab-editing-design.md](docs/drive-v2-pr10-collab-editing-design.md)
> - Mobile v3.2 PWA Push Backend (W68 第 7 批 B-3) → 文档见 `memory/w68-route-7-b3-mobile-v32-push-2026-07-24.md`
> - 端到端验证 (含 W68 第 7 批 13 段检查 + 3 hot-fix + alembic 065 + baseline) → [scripts/verify_w68_7th_batch_deployment.sh](../scripts/verify_w68_7th_batch_deployment.sh) [714 行]
> - Drive v2 PR9 12 endpoint HTTP 主脚本 → [scripts/verify_drive_v2_pr9_deployment.sh](../scripts/verify_drive_v2_pr9_deployment.sh) [489 行]
> - W68 第 5 批轻量 verify → [scripts/verify_w68_5th_batch_deployment.sh](../scripts/verify_w68_5th_batch_deployment.sh) [344 行]
> - 锚点范式沉淀 → [memory/w68-route-8-a3-7th-batch-deploy-2026-07-24.md](../memory/w68-route-8-a3-7th-batch-deploy-2026-07-24.md)
>
> **约束**: 0 production code 改动铁律维持 — 本 runbook 只描述部署流程, 不修改 alembic / 路由 / ORM。

---

## 0. 部署前必读 (含 066/067/068/069 顺序)

1. **部署顺序 1**: 先拉取包含 066/067/068/069 的最新 main，禁止从任一中间迁移开始。
2. **部署顺序 2**: 严格 copy `066 → 067 → 068 → 069`，然后一次清空容器 `__pycache__`。
3. **部署顺序 3**: 先验证唯一 head=`069_drive_comments_recursive_func`，再执行 `alembic upgrade head`。
4. **部署顺序 4**: 重启 app/celery-worker 后先验 DR endpoint/PG function，最后跑 13 段脚本与 baseline。

5. **主指挥本地 PC**: Docker 8 services 宿主机 (`/e/microbubble-agent` 或 `E:\microbubble-agent`)。
2. **云服务器**: 只跑 Nginx + FRP, **不跑 alembic / 不重建容器** — 部署命令全部在本机。
3. **alembic 065 链**: 已按 W68 第 3 批纪律**串单链** `064 → 065` (`down_revision="064_drive_documents"`)。若 git log 看 main 还没合并 `065_push_subscriptions.py`, **不要**先跑 `alembic upgrade head`, 否则会报 `Multiple head revisions` 阻塞。
4. **重要铁律**: 部署迁移前必须先 `cd /e/microbubble-agent && git pull`, 否则 alembic 文件不是最新。
5. **PR10 协同编辑边界**: W68 第 7 批 B-1 已完整实施 CRDT 协同编辑 (WS /drive/files/{id}/collab + snapshot + op HTTP), 不是空骨架。生产侧 alembic 064 跑完后 `drive_documents` + `drive_doc_op_logs` 2 表可用。
6. **PWA Push Backend 边界**: W68 第 7 批 B-3 已实施 Web Push RFC 8030+8291+8292 全栈 (VAPID JWT + ECDH 加密 + 3 表 + Celery 异步发推)。`/api/v1/push/vapid-public-key` 是公开 endpoint。

---

## 1. SSH 部署 24 步 (主指挥流程化操作)

主指挥在本机终端跑下列命令, 每步按 §6 退出码判断 PASS/FAIL。

### 1.1 拉最新 main (必须)

```bash
cd /e/microbubble-agent  # 或 E:\microbubble-agent
git checkout main
git pull origin main
git log --oneline -1   # 期望: W68 第 7 批 grand closure merge commit
```

### 1.2 检查 W68 第 7 批 15 commits 都已 merge 进 main

```bash
git log --oneline -50 | grep -cE "w68-7th-batch"   # 期望: ≥ 14 (grand closure 不带 w68-7th-batch 前缀)
git log --oneline -50 | grep -E "w68-7th-batch" | head -20   # 看 15 commit 都在
```

期望至少出现:
- `w68-7th-batch-a1-cached-giggling-pebble` / `-a2-cheerful-anchor-scripts` / `-a3-qa-bench-isolation`
- `w68-7th-batch-d5-kb-monitor` / `silly-gliding-dahl`
- `drive-v2-pr10.*协同编辑 WS` / `qa-bench D6 Phase 2` / `mobile-v3.2-push`
- `w68-7th-batch-c1-plans-status` / `-c2-plans-archive` / `-c3-verified-plans`
- `w68-7th-batch-d1-5th-batch-deploy` / `verify_pr10_collab_ws` / `-d3-claude-code-voice-alert`
- `w68-7th-batch.*grand closure` (锚点范式第 87 守恒)

### 1.3 检查 alembic 065 文件已 merge

```bash
ls -la alembic/versions/065_push_subscriptions.py
# 期望: 文件存在 (300+ 字节, 含 push_subscriptions + push_topics + push_topic_subscriptions 3 张表定义)

grep "down_revision" alembic/versions/065_push_subscriptions.py | head -2
# 期望: down_revision: Union[str, None] = "064_drive_documents"
```

### 1.4 copy alembic 065 文件到容器 + 清理 `__pycache__` (CLAUDE.md 752 行铁律)

```bash
docker cp alembic/versions/065_push_subscriptions.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
```

**为什么清 `__pycache__`**: 容器里若残留老 `065_*` 的 `.pyc`, Python 优先加载缓存, 会让新的 `down_revision="064_drive_documents"` 不生效, 双头假修复。

### 1.5 跑 alembic upgrade head

```bash
docker exec microbubble-agent-app-1 alembic upgrade head
# 期望: Running upgrade 064_drive_documents -> 065_push_subscriptions
# 期望: 无 "Multiple head revisions" 报错
```

### 1.6 验证 alembic 落点 = 065

```bash
docker exec microbubble-agent-app-1 alembic current
# 期望: 065_push_subscriptions (head)
```

### 1.7 验证 alembic 单 head (无双头)

```bash
docker exec microbubble-agent-app-1 python -c "
from alembic.config import Config
from alembic.script import ScriptDirectory
c = Config()
c.set_main_option('script_location','alembic')
s = ScriptDirectory.from_config(c)
print(','.join(s.get_heads()))
"
# 期望: 065_push_subscriptions (单 head, 无逗号)
```

### 1.8 重启后端 2 服务 (CLAUDE.md 752 行铁律)

```bash
docker compose restart app celery-worker
# 期望: app-1 + celery-worker-1 都 RUNNING
```

### 1.9 等 5-8s 让 uvicorn 完全启动

```bash
sleep 8 && docker compose logs app --tail 30 | grep -i "started\|application startup\|uvicorn"
# 期望: "Uvicorn running on http://0.0.0.0:8000" 或 "Application startup complete"
```

### 1.10 验证 hot-fix #16 (select import)

```bash
docker exec microbubble-agent-app-1 python -c "from app.services.drive_version_diff_service import DriveVersionDiffService, compare_versions; print('OK')"
# 期望: OK (无 ImportError 或 NameError)
```

### 1.11 验证 hot-fix #17 (lineterm="\n") 真跑

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

### 1.12 验证 hot-fix #18 (uploader_id → created_by)

```bash
grep -c "uploader_id" app/services/drive_comment_service.py
# 期望: 0 (完全迁移到 created_by)
```

### 1.13 验证 VAPID 密钥生成 (B-3 启动钩子)

```bash
docker exec microbubble-agent-app-1 python -c "from app.services.push_service import generate_vapid_keys; print(generate_vapid_keys())" 2>&1 | head -5
# 期望: 输出含 'BEGIN PUBLIC KEY' 或 jwt-style token
# 或检查文件: docker exec microbubble-agent-app-1 ls -la /data/push/
```

### 1.14 验证 Drive v2 PR10 协同 WS endpoint 可连

```bash
# 用 wscat 或浏览器 DevTools
wscat -c "wss://your.domain/api/v1/drive/files/1/collab?token=$JWT"
# 期望: Connected (101 Switching Protocols)
```

### 1.15 验证 VAPID public key HTTP endpoint

```bash
curl -sk https://your.domain/api/v1/push/vapid-public-key | head -c 200
# 期望: {"publicKey": "..."} 或含 BEGIN PUBLIC KEY
```

### 1.16 验证 push_subscriptions / push_topics / push_topic_subscriptions 表已建

```bash
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\dt push*"
# 期望: 3 张表都在
```

### 1.17 跑 W68 第 7 批 verify 脚本 (13 段检查)

```bash
BASE_URL=https://your.domain TOKEN=$JWT bash scripts/verify_w68_7th_batch_deployment.sh
# 期望: §1-§13 全 PASS
```

### 1.18 跑 Drive v2 PR9 主脚本 (12 endpoint HTTP + 3 hot-fix + alembic + 6 表)

```bash
BASE_URL=https://your.domain TOKEN=$JWT bash scripts/verify_drive_v2_pr9_deployment.sh
# 期望: 全 PASS (PR9 endpoint + alembic + 6 表 + 3 hot-fix + baseline)
```

### 1.19 跑 baseline 71 PASS + 7 SKIP 守恒

```bash
SKIP_DB_SETUP=1 pytest tests/test_baseline_audit.py -v
# 期望: 71 PASS, 7 SKIP, 0 FAIL
```

### 1.20 通知团队

```bash
echo "W68 第 7 批 15 commits + 3 hot-fix + Drive v2 PR10 协同 + PWA Push Backend 已部署完成" \
  | docker compose exec -T app python -c "import sys; from app.services.notification_service import notify_slack; notify_slack(sys.stdin.read())"
# 或手发团队群
```

### 1.21 copy alembic 066（PR11 path）
```bash
docker cp alembic/versions/066_drive_comments_path.py microbubble-agent-app-1:/app/alembic/versions/
```

### 1.22 copy alembic 067（PR12 reactions）
```bash
docker cp alembic/versions/067_drive_reactions.py microbubble-agent-app-1:/app/alembic/versions/
```

### 1.23 copy alembic 068 + 069，并升级唯一 head
```bash
docker cp alembic/versions/068_drive_notification_dedup.py microbubble-agent-app-1:/app/alembic/versions/
docker cp alembic/versions/069_drive_comments_recursive_func.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head
docker exec microbubble-agent-app-1 alembic current  # 期望 069
```

### 1.24 DR endpoint + 069 真跑 + 13 段验收
```bash
curl -sk -H "Authorization: Bearer $JWT" "https://your.domain/api/v1/drive/comments/1/breadcrumb"
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "SELECT * FROM get_comment_ancestors_recursive(1);"
BASE_URL=https://your.domain TOKEN=$JWT bash scripts/verify_w68_7th_batch_deployment.sh
# 期望 §1-§13 无 FAIL；baseline 71 PASS + 7 SKIP
```

---

## 2. verify 脚本 3 用法 + 6 FAQ

### 2.1 三脚本对比

| 脚本 | 行数 | 跑啥 | 适用场景 |
|------|------|------|----------|
| `scripts/verify_drive_v2_pr9_deployment.sh` | 489 | Drive v2 PR9 **12 endpoint HTTP** + WS + alembic + 6 表 + **3 hot-fix 真跑** + baseline | 完整部署验收 (主脚本) |
| `scripts/verify_w68_5th_batch_deployment.sh` | 344 | W68 第 5 批 **18 commit 链** + PR10 文档 + **3 hot-fix 真跑** + alembic 064 + baseline | W68 第 5 批专项验证 (轻量, 无 HTTP) |
| `scripts/verify_w68_7th_batch_deployment.sh` | 714 | W68 第 7 批 **15 commit 链** + alembic 065 + **3 hot-fix 真跑** + PR9 endpoint + **PR10 WS** + **PWA push** + uploader_id 守卫 + baseline | W68 第 7 批专项验证 (13 段检查) |

### 2.2 第 7 批脚本环境变量

```bash
BASE_URL=https://your.domain \  # 默认 https://localhost
TOKEN=eyJ...                   # 默认空 (跑 401 负例)
FILE_ID=42                     # 默认 1
DRY_RUN=1                      # 默认 0
BASE_DIR=/e/microbubble-agent  # 默认 $(pwd)
bash scripts/verify_w68_7th_batch_deployment.sh
```

### 2.3 13 段检查清单

| 段 | 检查项 | 期望 |
|----|--------|------|
| §1 | W68 第 7 批 15 commits 在 main | 全 PASS |
| §2 | alembic 065 单 head + 位置 6/7/8/9/10 | 单头 + 范围内 |
| §3 | 3 hot-fix 真跑 (#16/#17/#18) | 全 PASS |
| §4 | Knowledge uploader_id 跨服务守卫 | drive_comment_service.py = 0 命中 |
| §5 | Drive v2 PR9 endpoint 完整 | 7 文件在 main + 评论列表/版本列表返 200 |
| §6 | Drive v2 PR10 协同 WS endpoint | WS 101/401 + snapshot HTTP 200/401 |
| §7 | Mobile PWA Push Backend | 3 文件在 main + 3 表存在 + vapid-public-key 返 200 |
| §8 | baseline 71 PASS + 7 SKIP 守恒 | pytest ≥ 71/7 |

### 2.4 退出码约定

| 退出码 | 含义 |
|--------|------|
| 0 | 全部 PASS |
| 1 | 任一 FAIL (修复后重跑) |
| 2 | curl/docker/git 缺失或非 git 仓库 |

### 2.5 DRY_RUN 行为

- `DRY_RUN=1` 时, 任何会发 HTTP 请求 / 跑 `pytest` / 跑 `docker exec` 的步骤**只打印命令**, 标记 SKIP
- 主指挥可用 `DRY_RUN=1` 先 sanity-check 脚本本身能不能跑通 (避免线上跑挂)

### 2.6 加新 check 的标准

1. 找对应章节, 加 `log_info` + `log_pass/log_fail/log_skip` 三元组
2. fail 必有第 2 参数 (原因), 便于排查
3. 不要新增对生产代码的依赖 (verify 脚本是 0 production code 改动铁律的范例)
4. grep -c 输出必须 `| tr -d '\n'` 防 bash 变量意外包含换行 (本脚本 §3.3/§4 都用了)
5. 跨 worktree 运行必须支持 `.git` 文件指针 (worktree 模式)

---

## 3. alembic 串单链验证 (062 → 063 → 064 → 065 → 066 → 067 → 068 → 069)

### 3.1 当前链状态 (W68 第 7 批收官后)

```
061_drive_folder_share
    ↓ (down_revision="061")
062_drive_comments
    ↓ (down_revision="062")
063_drive_file_versions
    ↓ (down_revision="063")
064_drive_documents
    ↓ (down_revision="064")
065_push_subscriptions
    ↓
066_drive_comments_path
    ↓
067_drive_reactions
    ↓
068_drive_notification_dedup
    ↓
069_drive_comments_recursive_func  ← 唯一 head
```

### 3.2 4 张 Drive v2 表 + 3 张 Push 表 (DB 期望)

```sql
-- Drive v2 PR9 + PR10 (W68 第 5/7 批)
drive_comments          -- 062
drive_file_versions     -- 063
drive_documents         -- 064 (PR10 协同)
drive_doc_op_logs       -- 064 (PR10 协同审计)

-- Mobile v3.2 Push (W68 第 7 批 B-3)
push_subscriptions      -- 065 (1 用户多端 endpoint)
push_topics             -- 065 (静态主题)
push_topic_subscriptions -- 065 (M:N 关联)
```

### 3.3 主指挥拍板决策: 是否合并 alembic 065 到生产

**选项 A (推荐)**: 合并 + 跑 `alembic upgrade head`
- ✅ PWA Push Backend 全栈落地 (VAPID + 3 表 + Celery 异步发推)
- ✅ 浏览器推送通知可用 (用户在 PWA 内订阅 → 跨设备 push)
- ⚠️ 表是空的, 不影响业务
- ⚠️ 首次启动会生成 VAPID 密钥 (持久化到 `/data/push/`)

**选项 B**: 不合并 / 暂留 main 但不跑迁移
- ⏸ 等真实 PWA 用户测试后再启用
- ⏸ 当前 PR9/W68 第 7 批部署**不**需要这 3 张表 (frontend 离线模式可用)

**选项 C (不推荐)**: alembic downgrade -1 永久删除 065
- ❌ 调研 + 实施成果丢失
- ❌ W69 派工时又要重新创建

**主指挥建议**: 选项 A (合并 + 跑迁移), 因为表是空的, 即使后续调整也是 `alembic downgrade -1` 一行命令。

### 3.4 串单链纪律 (CLAUDE.md 2026-07-24 升级)

派工时**必须**明确 down_revision 接续关系, merge 后**必须** verify 单 head:

```bash
python -c "
from alembic.config import Config
from alembic.script import ScriptDirectory
c = Config()
c.set_main_option('script_location','alembic')
s = ScriptDirectory.from_config(c)
heads = s.get_heads()
print('HEADS:', heads)
print('COUNT:', len(heads))
print('SINGLE:', len(heads) == 1)
"
# 期望: HEADS: ['065_push_subscriptions']  COUNT: 1  SINGLE: True
```

### 3.5 跨 PR 部署 alembic 必须 cp + clear cache

(参考 CLAUDE.md 2026-07-24 alembic 并行 agent 串单链纪律 #5):

```bash
docker cp alembic/versions/065_push_subscriptions.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
# 否则 __pycache__ 残留会让老 down_revision 继续生效, 双头假修复
```

---

## 4. 6 个常见问题 FAQ

### Q1: `alembic upgrade head` 报 `Multiple head revisions`

**A**: main 上有**两个**head。常见根因:
1. 065 的 `down_revision` 没改对 (必须 = `"064_drive_documents"`)
2. 你跑的 alembic 文件不是最新 — `git pull` 后没清理 `__pycache__`

**修复**:
```bash
git pull origin main
docker cp alembic/versions/065_push_subscriptions.py microbubble-agent-app-1:/app/alembic/versions/
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

### Q4: W68 第 7 批 verify 脚本 `grep -c` 输出 "0\n0" 显示异常

**A**: bash 变量捕获陷阱 — `grep -c` 在 0 命中时返回 exit code 1, 触发 `|| echo 0` 输出额外 0。

**修复**: 本脚本 §3.3/§4 已用 `tr -d '\n'` 处理 (`HF3_HITS=$(grep -c ... | tr -d '\n')`)。如果发现老脚本还有这问题, 加 `| tr -d '\n'` 即可。

### Q5: Drive v2 PR10 WS endpoint 探测超时 (curl 不支持长连接)

**A**: curl 默认探测 Upgrade 协议**可能**正常返 101, 但**也可能**因 keepalive 超时返 000。这是 curl 限制不是端点问题。

**修复**: 用 wscat / websocat / 浏览器 DevTools 真连一次:
```bash
wscat -c "wss://your.domain/api/v1/drive/files/1/collab?token=$JWT"
# 或
websocat "wss://your.domain/api/v1/drive/files/1/collab?token=$JWT"
```

### Q6: VAPID public key endpoint 返 200 但 body 不是 JSON

**A**: VAPID 启动钩子未跑完。检查 lifespan 日志:
```bash
docker compose logs app --tail 30 | grep -i "vapid\|push"
```

若未生成, 手动 init:
```bash
docker exec microbubble-agent-app-1 python -c "
from app.services.push_service import generate_vapid_keys, get_vapid_public_key_b64
keys = generate_vapid_keys()
print('PUBLIC:', keys['public_b64_urlsafe'])
print('FROM_FILE:', get_vapid_public_key_b64())
"
```

### Q7: baseline `tests/test_baseline_audit.py` 跑只有 0 PASS

**A**: pytest collect 失败, 不是业务失败。
1. 跑 `pytest tests/test_baseline_audit.py --collect-only` 看错误
2. 99% 是文件路径不存在 (CLAUDE.md W62 baseline 9 files 教训)
3. 修法: 确认 `tests/scripts/` 子目录在 pytest testpaths 里 (默认应在)

---

## 5. 回滚方案 (4 步)

### 5.1 alembic downgrade -1 (回 Push 库, 保留 PR9 + PR10)

```bash
docker exec microbubble-agent-app-1 alembic downgrade -1
# 期望: 065_push_subscriptions → 064_drive_documents (回滚成功, push_subscriptions + push_topics + push_topic_subscriptions 3 表删除)
```

只回滚 Push 库, PR9 + PR10 协同编辑功能**保留**。

### 5.2 alembic downgrade -2 (回 Push + PR10 协同, 保留 PR9)

```bash
docker exec microbubble-agent-app-1 alembic downgrade -2
# 期望: 065 → 064 → 063 (回滚成功, drive_documents + drive_doc_op_logs 也删除)
```

PR9 评论/版本功能**保留**。

### 5.3 整体回滚 (commit revert)

```bash
cd /e/microbubble-agent
git revert --no-edit <W68-第-7-批-grand-closure-commit>
# 视情况 revert W68 第 7 批其他 agent commit
git push origin main  # webhook 触发 30s 自动部署
```

回滚约 3-5 分钟, 不需要 DB 回滚 (W68 第 7 批主要是新功能独立模块, 不动老路径)。

### 5.4 docker 全栈重启 (终极回滚)

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
| alembic 065 表不存 | 未跑迁移 | `docker exec microbubble-agent-app-1 alembic upgrade head` |
| WebSocket 探测超时 | curl 不支持长连接 | 改用 wscat 或浏览器 DevTools |
| VAPID 公钥缺失 | lifespan 未跑完 | `docker compose logs app --tail 30 \| grep -i vapid` |
| push 表都缺失 | alembic 065 未跑 | 同 alembic 065 表不存 |
| verify 脚本 §4.1 fail | drive_comment_service.py 还有 uploader_id | `grep -c uploader_id app/services/drive_comment_service.py` |
| verify 脚本 §6 全 fail | PR10 文件未 merge | `git log --oneline \| grep 'drive-v2-pr10.*协同编辑'` |

---

## 7. 参考链接

- **CLAUDE.md 锚点范式**: 当前 W68 第 7 批 87 → 本 runbook 帮助守住 第 92 守恒
- **CLAUDE.md 2026-07-24 alembic 串单链纪律**: §"alembic 并行 agent 串单链纪律" (commit 1852468a6 沉淀)
- **memory/w68-alembic-chain-discipline-2026-07-24.md**: alembic 单链铁律 + commit 链
- **memory/w68-route-7-d1-5th-batch-deploy-2026-07-24.md**: 锚点范式第 85 守恒 + 3 新铁律 (W68 第 5 批 verify)
- **memory/w68-route-8-a3-7th-batch-deploy-2026-07-24.md**: 锚点范式第 92 守恒 + 3 新铁律 (W68 第 7 批 verify, 本 runbook)
- **docs/drive-v2-pr10-collab-editing.md**: PR10 协同编辑设计
- **docs/drive-v2-pr10-collab-editing-design.md**: PR10 协同编辑实现细节

---

**Runbook 维护者**: W68 第 8 批 A-3 agent
**最后更新**: 2026-07-24
**锚点范式**: 第 92 守恒 (W68 第 7 批 87 → 第 8 批 92)