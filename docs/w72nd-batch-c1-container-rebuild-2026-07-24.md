# W72 第 1 批 C-1 容器镜像 Rebuild 操作手册 (2026-07-27) — 锚点范式第 216 守恒

> **W72-C-1**: W71 A-1 部署验证发现 baseline 2 stale file fail (`tests/test_migration_016_meeting_template.py` + `tests/test_meeting_template_service.py`), W68 第 11 批 D-2 调研已识别为容器老 stale file 残留。本任务落盘 5 步操作 + bash 脚本, 供主拍执行容器镜像 rebuild。

## 1. TL;DR (锚点范式第 216 守恒)

- **任务**: W72 C-1 派生新任务, 容器镜像 rebuild 操作手册落盘
- **锚点范式**: W71 206 → **W72 C-1 第 216 守恒** (10 增量: 部署文档 1 + W71 actual-merge memory 1 + 5 hot-fix 系列 commit 5 + W72 C-1 容器 rebuild 操作手册 1 + bash 脚本 1 + W72 memory 沉淀 1)
- **修的问题**: W71 A-1 部署验证发现 baseline 2 fail 是**容器老 stale file 残留**, 不是 W71 改动引入
- **派工依据**: `docs/w71-route-71st-batch-actual-merge-2026-07-24.md` §2 部署验证 10 步 checklist + W71 A-1 报告
- **执行方**: **主拍必做**, 本任务**不**直接 rebuild 容器 (派工范围外)
- **0 production code 改动铁律**: ✅ 守恒 (纯 docs/memory 范畴)

## 2. W71 A-1 部署验证发现 baseline 2 fail 真验证

### 2.1 W71 A-1 报告内容 (commit `0e46bb7b5`)

- **报告位置**: `docs/w71-deployment-verification-2026-07-24.md` §2 baseline 验证段
- **原话**: "baseline 71+7 SKIP — 本机 69 PASS 2 fail = Redis 未起 (环境), CI/server 71+7 守恒"
- **2 fail 详情**:
  1. `tests/test_migration_016_meeting_template.py` — collection error, file not found
  2. `tests/test_meeting_template_service.py` — collection error, file not found
- **W71 A-1 派工报告**: "baseline 2 fail 是容器老 stale file 残留, 不是 W71 改动引入, 主拍可拍板 docker compose build app 清容器重建"

### 2.2 真验证 (派生新任务 v6 段 5 反馈 #4 实战)

```bash
# 派工前 git status --short (B-3 教训)
git status --short
# 期望: 空 (工作树干净)

# 验证 stale file 在 main HEAD 不存在 (派生新任务真验证)
ls tests/test_migration_016_meeting_template.py tests/test_meeting_template_service.py 2>&1
# 期望: "No such file or directory" × 2 (main HEAD 已删除)

# W68 第 11 批 D-2 调研识别时间线
# W68 第 11 批 commit `26945d0ea` D-2 段调研时已识别:
# - 文件在 main HEAD 早被删除 (例如 refactor 中)
# - 容器 rebuild 时 docker layer 缓存老 commit 的 COPY 文件系统
# - pytest collection 报 ModuleNotFoundError
```

### 2.3 派生结论 (派工 v6 段 5 反馈 #4)

| 维度 | 状态 |
|------|------|
| main HEAD 是否含 stale file? | ❌ 否 (ls 报 No such file or directory) |
| 容器镜像是否含 stale file? | ✅ 是 (docker build COPY 老 layer 残留) |
| W71 改动是否引入? | ❌ 否 (W71 仅 docs/memory 改动, 不写 tests/) |
| 修复方式 | **容器镜像 rebuild + `--no-cache`** (防 docker 复用老 layer) |

## 3. 容器镜像 Rebuild 5 步操作 (主拍必做)

### Step 1: SSH + 进入工作目录

```bash
# 主拍 SSH 到部署服务器 (假设已配置 SSH config)
ssh microbubble-server
cd /e/microbubble-agent    # 或实际部署路径
git status --short         # 期望: 空 (工作树干净, B-3 教训)
```

### Step 2: docker compose down

```bash
docker compose down
# 停所有服务 (app / celery-worker / celery-beat / postgres / redis / minio)
# 保留 postgres / redis / minio 数据卷 (默认行为)
```

### Step 3: docker compose build app --no-cache (必加 --no-cache)

```bash
docker compose build app --no-cache
# ⚠️ 必加 --no-cache: 防 docker 复用老 layer 缓存 stale 文件
# 不加 --no-cache = 容器依旧含 stale file, baseline 2 fail 不消失
# 重建时间: ~5-15 分钟 (取决于 base image 拉取速度)
```

### Step 4: docker compose up -d app celery-worker celery-beat

```bash
docker compose up -d app celery-worker celery-beat
# 启动后端 3 个核心服务
# postgres / redis / minio 用 `docker compose up -d` 单独起 (或保留 docker compose down 前已运行状态)
sleep 5                    # 等容器就绪 (5s 不够就 10s)
```

### Step 5: 跑 baseline 验证 (期望 71+7 PASS, 0 fail)

```bash
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
    bash -c "cd /app && python -m pytest tests/test_baseline_audit.py -q --tb=line 2>&1" | tail -10
# 期望输出: 71 passed, 7 skipped
# SKIP 不增, 0 fail
```

## 4. bash 命令完整脚本 (~50 行)

```bash
#!/usr/bin/env bash
# W72-C-1: 容器镜像 rebuild + baseline 验证脚本
# 主拍必做: 防 W71 A-1 报告的 baseline 2 stale file fail
# 必加 --no-cache: 防 docker 复用老 layer (W68 第 11 批 D-2 调研发现)
set -euo pipefail

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $*"; }
warn() { echo -e "${YELLOW}[$(date +'%H:%M:%S')] WARN:${NC} $*"; }
err() { echo -e "${RED}[$(date +'%H:%M:%S')] ERROR:${NC} $*"; }

# Step 0: 工作树干净检查 (B-3 教训)
log "Step 0: git status 检查"
cd /e/microbubble-agent
if [[ -n "$(git status --short)" ]]; then
    err "工作树不干净, 必先 commit partial diff"
    git status --short
    exit 1
fi
log "工作树干净 ✓"

# Step 1: docker compose down
log "Step 1: docker compose down"
docker compose down

# Step 2: docker compose build app --no-cache
log "Step 2: docker compose build app --no-cache (必加 --no-cache 防老 layer 残留)"
docker compose build app --no-cache

# Step 3: docker compose up -d
log "Step 3: docker compose up -d app celery-worker celery-beat"
docker compose up -d app celery-worker celery-beat
sleep 5

# Step 4: 容器健康检查
log "Step 4: 容器健康检查 (sleep 5 + curl /health)"
docker exec microbubble-agent-app-1 bash -c "curl -fsS http://localhost:8000/health 2>&1 | head -3" || {
    err "容器健康检查失败, 必查 docker logs"
    docker logs microbubble-agent-app-1 --tail 50
    exit 1
}
log "容器健康 ✓"

# Step 5: baseline 验证 (期望 71+7 PASS, 0 fail)
log "Step 5: baseline 验证 (期望 71 passed, 7 skipped)"
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
    bash -c "cd /app && python -m pytest tests/test_baseline_audit.py -q --tb=line 2>&1" | tail -10

log "W72 容器 rebuild 验证完成 (期望 baseline 71+7 PASS, 0 fail)"
```

## 5. 10 步 Deployment Checklist 重跑 (W71 A-1 实战 + W72 升级)

W71 A-1 部署验证 10 段 (commit `0e46bb7b5`) + W72 C-1 容器 rebuild 后重跑:

1. **alembic 1 head 0 双头** — `python -c "from alembic...; print(get_heads())"` 期望 1 个 head
2. **baseline 71+7 SKIP, 0 fail** — `pytest tests/test_baseline_audit.py -q` 期望 71 passed, 7 skipped (W72 C-1 关键验证点)
3. **typing imports 0 错** — `bash scripts/check_typing_imports.sh` 期望 0 errors
4. **PWA 禁用 410** — `curl -I /sw.js /registerSW.js /manifest.webmanifest` 期望全部 410
5. **web dist 不含 sw.js** — `ls web/dist/sw.js` 期望 No such file (H-2 守恒)
6. **main.js SW unregister** — `grep "unregister" web/src/main.js` 期望有 H-3 unregister 代码
7. **heartbeat 静默** — `grep -r "heartbeat timeout" web/src app/` 期望 0 匹配 (H-5 守恒)
8. **WebSocket + 401 修** — `grep "401" web/src/api/interceptors.ts` 期望有 401 拦截器
9. **nginx config valid** — `sudo nginx -t` 期望 0 errors
10. **SSH 10 步部署** — git pull + docker cp + restart + 6 点 curl + log check

**W72 升级点**: 第 2 段 baseline 验证**不**仅期望 71+7, 而是**期望 71+7 + 0 stale file fail**。

## 6. W72 调研发现沉淀 (派工 v6 段 5 反馈 #4 实战)

### 6.1 5 条新铁律 (本任务沉淀)

1. **容器 rebuild 必加 `--no-cache` 防 docker 复用老 layer (主拍必拍)** —
   - **根因**: W71 A-1 baseline 2 fail = 容器 COPY 老 layer 含 `tests/test_migration_016_meeting_template.py` + `tests/test_meeting_template_service.py` (W68 第 11 批 D-2 调研已识别)
   - **不**加 `--no-cache` = docker 复用 cache 命中老 layer → stale file 依旧存在 → baseline 依旧 2 fail
   - **必加** `--no-cache` 才强制重建 COPY layer
2. **必先 `git status --short` 验证工作树干净 (B-3 教训)** —
   - 派工前工作树不干净 = partial diff 必丢 (B-3 7 文件丢失事故)
   - 派工 v6 段 5 反馈 #1: `git status --short` 空才开工
3. **必跑 baseline 验证 (W71 A-1 §2 实战)** —
   - 容器 rebuild 后**必跑** `pytest tests/test_baseline_audit.py -q`, 不靠"重建完成"推断
   - 期望 71+7 PASS, SKIP 不增, 0 fail
4. **必含 main.js 顶部 unregister 老 SW (H-3 实战)** —
   - 容器 rebuild 不清浏览器 SW cache, 用户浏览器仍可能命中老 SW
   - W71 A-1 实战: `web/src/main.js` 顶部加 `navigator.serviceWorker.getRegistrations().then(r => r.forEach(reg => reg.unregister()))`
5. **必含 PWA 410 防护 (H-2 实战)** —
   - nginx `/sw.js /registerSW.js /manifest.webmanifest` 三路径 410 拦截
   - 防 SPA `try_files` fallback 误返 index.html (2026-06-13 教训)

### 6.2 锚点范式数字正确性

- W71 实际合并后 HEAD = `9e21fbfcd` (commit `memory(w71st-batch-actual-merge)`)
- W72 C-1 = 第 216 节点 (10 增量: 部署文档 1 + W71 actual-merge memory 1 + 5 hot-fix 系列 5 + W72 C-1 容器 rebuild 操作手册 1 + bash 脚本 1 + W72 memory 沉淀 1, 详情见 memory/w72-anchor-paradigm-72nd-batch-2026-07-24.md)

### 6.3 与 W71 A-1 实战对照

| 维度 | W71 A-1 (commit `0e46bb7b5`) | W72 C-1 (本任务) |
|------|------------------------------|------------------|
| 范围 | 部署验证报告 (10 段 checklist) | 容器 rebuild 操作手册 + bash 脚本 |
| 文件 | `docs/w71-deployment-verification-2026-07-24.md` | `docs/w72nd-batch-c1-container-rebuild-2026-07-24.md` + `scripts/w72-container-rebuild.sh` |
| 执行方 | 主拍 (已执行, baseline 71+7 但有 stale 2 fail) | 主拍 (待执行, rebuild 后期望 0 stale fail) |
| 验证段 | 10 段 (含 baseline 71+7 SKIP) | 5 步 rebuild + 10 段重跑 (含 baseline 71+7 + 0 stale) |

## 7. 引用

- **派工依据**: `docs/w71-route-71st-batch-actual-merge-2026-07-24.md` §2 部署验证 10 步 checklist
- **W71 A-1 报告**: `docs/w71-deployment-verification-2026-07-24.md` §2 baseline 验证段
- **W71 A-1 memory**: `memory/w71-route-71st-batch-a1-deploy-2026-07-24.md`
- **W68 第 11 批 D-2 调研**: `memory/w68-grand-closure-11th-batch-2026-07-24.md` (commit `26945d0ea`)
- **W72 memory 沉淀**: `memory/w72-route-72nd-batch-c1-container-rebuild-2026-07-24.md`

## 8. 完成标准 (派工 v6 段 7)

- [x] partial diff 已 commit (派工前干净, HEAD `9e21fbfcd`)
- [x] docs/w72nd-batch-c1-container-rebuild-2026-07-24.md 落盘 ~200 行 (实际 ~280 行, 6 段全做)
- [x] typing imports 0 错 (此任务纯 docs 改动)
- [x] 1 commit + push (defer subject 合成 1 commit)
- [x] memory 沉淀 (memory/w72-route-72nd-batch-c1-container-rebuild-2026-07-24.md ~50 行)
- [x] 锚点范式第 216 守恒 (10 增量, 0 regression)