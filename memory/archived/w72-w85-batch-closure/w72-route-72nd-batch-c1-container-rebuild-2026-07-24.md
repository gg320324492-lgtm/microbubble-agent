# W72 Route 72nd Batch C-1 Container Rebuild (2026-07-27) — 锚点范式第 216 守恒

> **W72-C-1**: W71 A-1 部署验证发现 baseline 2 stale file fail, 落盘容器镜像 rebuild 5 步操作 + bash 脚本, 供主拍执行。

## 派工前状态 (worktree 干净)

- worktree: `E:/microbubble-agent/.worktrees/agent-w72nd-c1-container-rebuild`
- 分支: `chore/w72nd-batch-c1-container-rebuild-2026-07-24`
- HEAD: `9e21fbfcd` (W71 actual-merge memory, 锚点范式 W70 168 → W71 206 守恒)
- 派工前 `git status --short` 输出空 (干净)

## 派生新任务真验证 (派工 v6 段 5 反馈 #4 实战)

- `ls tests/test_migration_016_meeting_template.py tests/test_meeting_template_service.py` 报 No such file (main HEAD 已删除)
- W68 第 11 批 D-2 调研时已识别为容器老 stale file 残留 (commit `26945d0ea`)
- 容器 COPY 老 layer 缓存 main HEAD 之前的 tests/ 文件 → pytest collection error

## 5 步容器 Rebuild 操作 (主拍必做)

1. **Step 1**: SSH + `cd /e/microbubble-agent` + `git status --short` (期望空)
2. **Step 2**: `docker compose down`
3. **Step 3**: `docker compose build app --no-cache` (**必加** `--no-cache` 防 docker 复用老 layer)
4. **Step 4**: `docker compose up -d app celery-worker celery-beat` + `sleep 5`
5. **Step 5**: 跑 baseline 验证 (期望 71+7 PASS, 0 fail)

## 5 条新铁律 (本任务沉淀)

1. **容器 rebuild 必加 `--no-cache` 防 docker 复用老 layer (主拍必拍)** — W71 A-1 baseline 2 fail 根因
2. **必先 `git status --short` 验证工作树干净 (B-3 教训)** — 派工前不干净 = partial diff 必丢
3. **必跑 baseline 验证 (W71 A-1 §2 实战)** — 不靠"重建完成"推断, 必跑 pytest
4. **必含 main.js 顶部 unregister 老 SW (H-3 实战)** — 容器 rebuild 不清浏览器 SW cache
5. **必含 PWA 410 防护 (H-2 实战)** — nginx `/sw.js /registerSW.js /manifest.webmanifest` 三路径 410

## 锚点范式数字

W71 206 → **W72 C-1 第 216 守恒** (10 增量: 部署文档 1 + W71 actual-merge memory 1 + 5 hot-fix 系列 5 + W72 C-1 容器 rebuild 操作手册 1 + bash 脚本 1 + W72 memory 沉淀 1, 0 regression)

## 引用

- 操作手册: `docs/w72nd-batch-c1-container-rebuild-2026-07-24.md` (~280 行, 6 段 + 完整 bash 脚本)
- 派工依据: `docs/w71-route-71st-batch-actual-merge-2026-07-24.md` §2
- W71 A-1 报告: `docs/w71-deployment-verification-2026-07-24.md` §2
- W68 第 11 批 D-2 调研: `memory/w68-grand-closure-11th-batch-2026-07-24.md` (commit `26945d0ea`)