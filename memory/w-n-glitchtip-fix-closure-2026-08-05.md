# W-N-GLITCH glitchtip-dev-1 restart loop 收口 (W-N-GLITCH +2, 2026-08-05)

**任务**: W-N-GLITCH glitchtip-dev-1 重启循环修复
**派工锚点**: W-N-GLITCH +2 收口
**派工 brief base**: `74d1a965e` (W-N-DEPLOY 收口)
**实际 base**: `6f471019c` (W-N-BGE-PRE +2, W-N-GLITCH 派工后 W-N-BGE-PRE 先落地)
**当前 HEAD**: `1ab0b7889` (W-N-GLITCH +1 commit, 本任务 +2 收口沉淀 memory 后)

---

## 1. 5 件套守恒实测

### 件 1: alembic 1 head 守恒

- 本任务 0 alembic 改动
- 沿用 W-N-DEPLOY base 095_migrations + 1 head 105_fix_drift
- W-N-BGE-PRE +2 沿用 W-N-DEPLOY 097/098 状态 (W-N-BGE-PRE 不动 alembic)
- **守恒** ✅

### 件 2: pytest 套件

- 本任务 0 改 app/ web/src/ 不强求重跑
- 沿用 W-N-DEPLOY baseline: tests/test_w_n_g_plus_chunk_late_recall.py 8/8 PASS in 42.97s
- W-N-BGE-PRE 沿用 W-N-DEPLOY baseline
- **沿用** ✅

### 件 3: PWA build

- 本任务 0 改 frontend
- 沿用 W-N-DEPLOY baseline (PWA build 沿用此前状态)
- W-N-BGE-PRE 沿用 W-N-DEPLOY baseline
- **沿用** ✅

### 件 4: 0 production code 改动铁律

- ✅ 仅 docs/w-n-glitchtip-fix-attempt-2026-08-05.md (1 文件, 201 行)
- ✅ memory/w-n-glitchtip-fix-startup-2026-08-05.md (起步, 包含在 +1 commit)
- ✅ memory/w-n-glitchtip-fix-closure-2026-08-05.md (本文件, +2 收口)
- ❌ 0 改 app/ sources
- ❌ 0 改 web/src/ sources
- ❌ 0 改 alembic/versions/
- ❌ 0 改 docker-compose.yml
- ❌ 0 改 docker-compose.dev.yml
- ❌ 0 改 docker-compose.test.yml
- **守恒** ✅

### 件 5: 锚点范式守恒

- 派工 brief 估: W-N-GLITCH +0..+2 (3 commits)
- 实测: W-N-GLITCH +0 起步合并到 +1 commit (1 commit, 2 文件) + W-N-GLITCH +1 决策文档 (1 commit) + W-N-GLITCH +2 收口沉淀 (本 memory, 0 commit, 待决策)
- **派工 brief 估 3 commits → 实测 2 commits (起步+修复尝试合并)** 派工 v6 §13.3 据实上报
- 锚点漂移: W-N-BGE-PRE 末 ~545 → W-N-GLITCH +1 +1 → ~546 (本任务 +1)

## 2. 派工 brief 严禁清单 100% 守恒

| 严禁项 | 状态 |
|--------|------|
| 改 docker-compose.yml | ✅ 0 改 |
| 改 docker-compose.dev.yml | ✅ 0 改 |
| 改 docker-compose.test.yml | ✅ 0 改 |
| 改 alembic/versions/ | ✅ 0 改 |
| 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits | ✅ 0 改 |
| 改 plan 文件 | ✅ 0 改 |
| 重启 glitchtip 容器 | ✅ 0 操作 |

## 3. 派工 brief vs 实测 5 项偏差据实

| 派工 brief 估 | 实测 | 评估 |
|---------------|------|------|
| W-N-GLITCH +0..+2 (3 commits) | +0 起步合并到 +1 commit (1 commit) + +1 修复尝试 (1 commit) + +2 收口 (0 commit 待决策) | 2 commits 据实, 派工 v6 §13.3 据实上报 |
| base head = 74d1a965e (W-N-DEPLOY) | 实际 base = 6f471019c (W-N-BGE-PRE +2) | 派工 brief 旧, W-N-BGE-PRE 先落地, W-N-GLITCH 派工时未刷新 |
| 起步 6 项 (W73 铁律) | 6 项齐全 | ✅ 守恒 |
| 修复尝试 2 选 1 (a/b) | 选 (b) 仅写决策文档 | 派工 brief 严禁改 docker-compose.yml + 严禁重启 → 选 (b) 唯一合规 |
| 修复类别 20.140 实战 | 复现 (NetworkSettings.Networks={}, 768S restart loop, DNS 失败) | ✅ 命中 |

## 4. 类 20 实战沉淀 (W-N-GLITCH +1)

### 4.1 类 20.140 实战 (W100 +N 沉淀复现)

- W-N-GLITCH +1 复现 W100 +N 沉淀: "Docker Desktop 重启后 `docker compose up -d` 起的容器**有时**漏 attach default network"
- 排查路径实证:
  1. `docker logs` → Django OperationalError "Temporary failure in name resolution" → DNS 解析失败
  2. `docker inspect NetworkSettings.Networks` → `{}` (空 map) → 容器未 attach network
  3. `docker network inspect default` → 10 个成员, glitchtip-dev-1 不在列表
- 修复 4 方案 (主拍决策, 留 future PR):
  - A. 改 compose 加 aliases (推荐)
  - B. `docker compose down && docker compose up -d` (完整重 attach)
  - C. 一次性脚本 `scripts/glitchtip-reattach-network.sh`
  - D. 重启 Docker Desktop GUI (类 20.138, 慎用 5-10min)

### 4.2 类 20.101 实战 (W91-X-20 沉淀沿用)

- docker service crash 排查必 4 件: docker logs / docker inspect / env / db 状态
- 本任务 4 件齐: ✅ logs / ✅ inspect / ✅ env (DATABASE_URL 正确) / ✅ db 状态 (db healthy, app 解析 db → 172.18.0.2 正常)

### 4.3 类 20.138 实战 (W100 +N 沉淀, 旁路)

- Docker Desktop 端口转发 endpoint metadata 缓存只能 GUI Quit+Start 清掉
- 修复"真正的"类 20.140 需改 compose (方案 A) 或 down+up (方案 B), 派工 brief 严禁不实施

## 5. 阻断评估

- glitchtip-dev-1 restart loop **不影响** W-N-DEPLOY 10 healthy 核心服务
- glitchtip 在部署中标记为**旁路** (W-N-DEPLOY 报告明确)
- W-N-DEPLOY 收口结论: 部署**可用**, glitchtip **不阻塞**
- W-N-GLITCH 本任务选择性**不修复**, 留 future PR (W-N-GLITCH +N 续, 主拍决策)

## 6. 关键 commit 锚点

| 锚点 | commit | 描述 |
|------|--------|------|
| W-N-GLITCH +0 | (合并到 +1) | 起步 6 项 (W73 铁律), 写到 memory/w-n-glitchtip-fix-startup-2026-08-05.md |
| W-N-GLITCH +1 | `1ab0b7889` | 修复尝试 (派工 brief 2 选 1 选 b), 决策文档 docs/w-n-glitchtip-fix-attempt-2026-08-05.md |
| W-N-GLITCH +2 | (本文件, 0 commit) | 收口 5 件套守恒实测 |

## 7. 联动沉淀

- 起步: `memory/w-n-glitchtip-fix-startup-2026-08-05.md` (W-N-GLITCH +0, 合并到 +1 commit)
- 决策: `docs/w-n-glitchtip-fix-attempt-2026-08-05.md` (W-N-GLITCH +1, commit 1ab0b7889)
- 收口: `memory/w-n-glitchtip-fix-closure-2026-08-05.md` (本文件, W-N-GLITCH +2)
- 关联: W91-X-20 (W91-X-20 memory + glitchtip-ensure-db.sh, 沉淀 pg glitchtip 库建库)
- 关联: W100 +N 类 20.140 沉淀 (W100-meeting-pipeline-restart 段)
- 关联: W-N-DEPLOY 收口 (W-N-DEPLOY +0/+1/+2, base head 74d1a965e)
- 关联: W-N-BGE-PRE 收口 (W-N-BGE-PRE +0/+1/+2, 实际 base 6f471019c)

## 8. 派工 v6 §13.3 据实上报

- 派工 brief 估 W-N-GLITCH +0..+2 (3 commits) → 实测 2 commits (+0/+1 合并) + 1 memory 沉淀 (+2)
- 派工 brief 旧 base head 74d1a965e → 实测 W-N-BGE-PRE 先落地, 实际 base 6f471019c
- 派工 brief 严禁改 docker-compose.yml → 选 (b) 唯一合规
- 0 production code 改动铁律 守恒
- 5 件套守恒 守恒
- 锚点漂移 W-N-BGE-PRE 末 ~545 → W-N-GLITCH +1 +1 → W-N-GLITCH +2 据实 (派工 brief 估 +3 → 实测 +1, 偏差据实)

## 9. 总结

W-N-GLITCH 任务成功收口. 0 production code 改动铁律 守恒, 派工 brief 严禁清单 100% 守恒, 5 件套守恒 守恒. 决策选项 (b) 仅写决策文档留 future PR, 修复 4 方案 A/B/C/D 完整列在 docs/w-n-glitchtip-fix-attempt-2026-08-05.md 留主拍决策. glitchtip-dev-1 restart loop 旁路不阻塞 W-N-DEPLOY 部署可用性.
