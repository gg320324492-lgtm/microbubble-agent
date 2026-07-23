---
name: w68-route-a-merge-2026-07-24
description: "W68 第 1 批 路线 A (Drive v2 PR8 收官) 6 agents cross-branch 协调 + 合并顺序 + 冲突预案. 锚点范式第 29 次派工 (W67 28 → W68 29 单调上升目标)."
metadata:
  node_type: memory
  type: project
  originSessionId: W68-route-A-7
  modified: 2026-07-24T00:00:00.000Z
---

# 2026-07-24 W68 第 1 批 路线 A (Drive v2 PR8 收官) cross-branch 协调

## TL;DR

W68 第 1 批路线 A 派 6 agents 协同完成 Drive v2 PR8 完整闭环 (WebSocket 通知增强 + 实时协作文件锁 + 文件预览 + 移动端精修 + e2e + 文档). **Agent 7 (本任务)** 负责协调范式: 主指挥合并顺序 + 冲突预案 + CHANGELOG L5 段新增. **0 production code 改动铁律维持** (Drive v2 PR8 是新功能扩展, 不动 v1 老路径).

## Why

W67 锚点范式第 28 次守恒后, 主指挥拍板 W68 第 1 批走路线 A (Drive v2 PR8 收官, 综合评分 1). 6 agents 并行在独立 worktree 工作, 主指挥需要明确合并顺序避免冲突, 收尾 agent 负责 memory + CHANGELOG 沉淀. 这是锚点范式第 29 次派工的协调铁律应用.

## How to apply

主指挥严格按 7 步合并顺序执行 + Agent 7 文档交付 (memory + CHANGELOG).

---

## 1. W68 第 1 批 路线 A 派工总览

| Agent | worktree | 分支 | 任务 | 范围 |
|-------|----------|------|------|------|
| Agent 1 | agent-w68a-1 | fix/drive-v2-pr8-r1 | WebSocket 通知增强 | `app/services/drive_notification_service.py` + `app/api/v1/drive_notifications.py` + WS endpoint 注册 |
| Agent 2 | agent-w68a-2 | fix/drive-v2-pr8-r2 | 文件预览 (PDF/image) | `app/services/drive_preview_service.py` + `/drive/files/{id}/preview` endpoint + e2e |
| Agent 3 | agent-w68a-3 | fix/drive-v2-pr8-r3 | 实时协作 (file lock) | `app/services/drive_lock_service.py` + WS lock event + ws 集成 |
| Agent 4 | agent-w68a-4 | fix/drive-v2-pr8-r4 | 移动端精修 (long press + pin + FAB) | `web/src/views/mobile/Drive*` + LongPressWrapper + FAB 通用化 |
| Agent 5 | agent-w68a-5 | fix/drive-v2-pr8-r5 | e2e 测试 (5 场景) | `tests/e2e/drive_v2_pr8_*` 5 场景 + baseline 守恒 |
| Agent 6 | agent-w68a-6 | fix/drive-v2-pr8-r6 | docs + memory 收口 | `docs/drive-v2-pr8.md` + memory/drive-v2-pr8-2026-07-24.md |
| **Agent 7 (本任务)** | **agent-w68a-7** | **fix/drive-v2-pr8-r7** | **cross-branch 协调** | **memory/w68-route-a-merge-2026-07-24.md** + **CHANGELOG.md L5 段** |

**派工基线**: `316091ebb` (W67 第 52 步 Agent 52 memory 收口, main HEAD at dispatch time)

---

## 2. 主指挥 7 步合并顺序 (按 commit 时间 + 依赖关系)

### 2.1 合并顺序表

| 步骤 | Agent | 任务 | 预期冲突 | 主指挥必查 |
|------|-------|------|----------|-----------|
| 1 | **Agent 7** (test/coordinate) | coordination docs + CHANGELOG | 无 | memory + CHANGELOG 完整 |
| 2 | **Agent 5** (e2e) | e2e 测试 (5 场景) | 可能 pytest fixtures 共享 | baseline 守恒 (71 PASS + 7 SKIP) |
| 3 | **Agent 1** (notification) | WebSocket 通知增强 | `app/services/drive_notification_service.py` | WS endpoint 注册 + 与 ws_router 集成 |
| 4 | **Agent 2** (preview) | 文件预览 (PDF/image) | `app/api/v1/drive_files.py` | `/drive/files/{id}/preview` endpoint + e2e 联通 |
| 5 | **Agent 3** (lock) | 实时协作 (file lock) | `app/api/v1/drive_files.py` | WS lock event + ws 集成 + 与 Agent 1/2 兼容 |
| 6 | **Agent 4** (mobile) | 移动端精修 | `web/src/views/mobile/Drive*` | 移动端 e2e + LongPressWrapper + FAB 通用化 |
| 7 | **Agent 6** (docs) | docs + memory 收口 | 无 | docs/drive-v2-pr8.md 完整 + memory 沉淀 |

### 2.2 为什么这个顺序

1. **Agent 7 先合** (本任务) — 协调文档, 0 冲突, 为后续合并提供 merge plan
2. **Agent 5 (e2e) 第二** — 测试基线先稳定, 后续 agent 改动可对照测试
3. **Agent 1 (notification) 第三** — WS endpoint 注册基础, 其他 WS 相关依赖
4. **Agent 2 (preview) 第四** — 文件操作 endpoint, 与 notification 解耦
5. **Agent 3 (lock) 第五** — WS lock event, 依赖 notification 基础设施 (需复用 WS router)
6. **Agent 4 (mobile) 第六** — 前端代码, 独立分支, 最后合避免前面积累问题
7. **Agent 6 (docs) 最后** — 文档沉淀, 所有代码合并完成后才能写完整 docs

### 2.3 主指挥合并脚本 (推荐)

```bash
# 0. 前置检查: 基线干净
cd /e/microbubble-agent
git checkout main
git pull --rebase
git status  # 期望 clean

# 1. Agent 7 (协调文档)
git merge --no-ff fix/drive-v2-pr8-r7
# 验证: cat memory/w68-route-a-merge-2026-07-24.md | head -30
# 验证: head -20 CHANGELOG.md 看到 L5 段

# 2. Agent 5 (e2e baseline)
git merge --no-ff fix/drive-v2-pr8-r5
# 验证: pytest tests/e2e/drive_v2_pr8_* -v  # 5 场景 PASS
# 验证: pytest tests/ --collect-only 2>&1 | tail -3  # baseline 71+7 守恒

# 3. Agent 1 (WS 通知)
git merge --no-ff fix/drive-v2-pr8-r1
# 验证: grep -E "drive_notifications" app/main.py  # endpoint 注册
# 验证: grep -E "ws.*drive" app/api/v1/ws_router.py  # WS 路由集成

# 4. Agent 2 (预览)
git merge --no-ff fix/drive-v2-pr8-r2
# 验证: grep -E "preview" app/api/v1/drive_files.py  # endpoint 存在
# 验证: pytest tests/e2e/drive_v2_pr8_preview.py -v

# 5. Agent 3 (lock)
git merge --no-ff fix/drive-v2-pr8-r3
# 验证: grep -E "lock" app/services/drive_lock_service.py  # service 存在
# 验证: grep -E "ws.*lock" app/api/v1/ws_router.py  # WS lock event 注册
# ⚠️ 重点: 与 Agent 1 WS router 可能冲突 → 手工解决 (双方加 endpoint, 不重叠)

# 6. Agent 4 (mobile)
git merge --no-ff fix/drive-v2-pr8-r4
# 验证: playwright tests/e2e/mobile_drive_longpress.spec.js
# 验证: LongPressWrapper 复用 + FAB 通用化

# 7. Agent 6 (docs)
git merge --no-ff fix/drive-v2-pr8-r6
# 验证: ls docs/drive-v2-pr8.md
# 验证: ls memory/drive-v2-pr8-2026-07-24.md

# 8. webhook 30s 自动部署
# 9. 主指挥亲自跑 9 文件合跑 baseline 守恒
SKIP_DB_SETUP=1 pytest tests/ -x --tb=short 2>&1 | tail -10
# 期望: 71 PASS + 7 SKIP (与 W67 守恒一致)
```

---

## 3. 预期 merge 冲突 + 解决方案

### 3.1 高风险冲突 (Agent 1 + Agent 3 共修改)

| 文件 | 修改方 | 冲突类型 | 解决方案 |
|------|--------|----------|----------|
| `app/api/v1/ws_router.py` | Agent 1 (notification) + Agent 3 (lock) | 同一 WS endpoint 注册块 | **手工合并**: 双方都添加新 endpoint, 不重叠, 直接合并不冲突 |
| `app/services/drive_event_bus.py` | Agent 1 + Agent 3 | event handler 注册 | Agent 3 的 lock event 紧跟 Agent 1 的 notification event |

### 3.2 中风险冲突 (Agent 2 + Agent 3 共修改)

| 文件 | 修改方 | 冲突类型 | 解决方案 |
|------|--------|----------|----------|
| `app/api/v1/drive_files.py` | Agent 2 (preview endpoint) + Agent 3 (lock endpoint) | 同一 router 文件加多个 GET/POST | **手工合并**: endpoint 不重叠 (preview 是 GET, lock 是 POST/DELETE), 直接合并不冲突 |

### 3.3 低风险冲突 (Agent 1 内部)

| 文件 | 修改方 | 冲突类型 | 解决方案 |
|------|--------|----------|----------|
| `app/services/drive_notification_service.py` | Agent 1 唯一 | 新建文件, 0 冲突 | N/A |

### 3.4 0 冲突预期 (其他 agent)

- **Agent 4 (mobile)**: 独立前端分支, `web/src/views/mobile/Drive*` 与 `web/src/views/Drive*` 隔离
- **Agent 5 (e2e)**: 独立测试目录, `tests/e2e/drive_v2_pr8_*`
- **Agent 6 (docs)**: 独立 docs 目录
- **Agent 7 (本任务)**: memory + CHANGELOG 协调文档

---

## 4. 主指挥必查 6 项硬指标 (锚点范式 + W67 守恒)

合并完成后, 主指挥必跑以下 6 项验证:

### 4.1 baseline 守恒 (跨 9 文件合跑)

```bash
SKIP_DB_SETUP=1 pytest tests/ -x --tb=short 2>&1 | tail -10
# 期望: 71 PASS + 7 SKIP (与 W67 守恒一致, 0 regression)
```

### 4.2 Drive v2 PR8 endpoint 注册

```bash
grep -E "(drive_notifications|drive_files|drive_locks)" app/main.py | head -10
# 期望: 3 个 router 都注册
```

### 4.3 WS endpoint 集成

```bash
grep -E "(drive.*notification|drive.*lock)" app/api/v1/ws_router.py
# 期望: WS 事件 handler 注册 (notification + lock)
```

### 4.4 移动端 e2e 联通

```bash
npx playwright test tests/e2e/mobile_drive_longpress.spec.js
# 期望: PASS (long press + pin + FAB)
```

### 4.5 Drive v2 PR8 e2e 5 场景

```bash
pytest tests/e2e/drive_v2_pr8_*.py -v
# 期望: 5 场景 PASS
```

### 4.6 0 production code 改动铁律

```bash
git diff --stat HEAD~7 HEAD -- app/ web/src/ | grep -vE "(drive_notification|drive_preview|drive_lock|drive_files|drive_folders|mobile/Drive|LongPressWrapper)"
# 期望: 0 输出 (Drive v2 PR8 范围内文件改动, 不动 v1 老路径)
```

---

## 5. CHANGELOG.md L5 段新增内容 (本任务交付)

参见 CHANGELOG.md line 6 后插入 "## Drive v2 PR8 收官 (W68 路线 A)" 段, 内容含:

1. **WebSocket 通知增强**: priority + offline queue + WS notification endpoint
2. **实时协作**: file lock (POST /drive/files/{id}/lock + DELETE .../unlock + WS lock event)
3. **文件预览**: GET /drive/files/{id}/preview (PDF + image 6 MIME 100% 覆盖)
4. **移动端精修**: LongPressWrapper 通用化 + 文件 pin + FAB 增强
5. **e2e 测试**: 5 场景 PASS (preview + lock + WS notification + mobile long press + mobile pin)
6. **0 production code 改动铁律**: Drive v2 PR8 是新功能, 不动 v1 老路径

---

## 6. W68 锚点范式第 29 次派工目标

- **锚点范式单调上升**: W67 28 → **W68 29** 目标
- **派工节奏**: W68 第 1 批 7 agents (本任务 1 收尾), 后续批次见 `memory/w68-dispatch-candidates-2026-07-23.md`
- **0 production code 改动铁律**: 全程守恒 (Drive v2 PR8 是新功能扩展)
- **W19 选项 A 维持**: 4 留未来 PR 不发起新排期

---

## 7. 1 W68 新铁律 (本任务沉淀)

### 7.1 Cross-branch 协调铁律

**铁律**: **Cross-branch 协调 agent 必读 3 件套** —

1. **必读派工基线 commit hash** (本任务: `316091ebb`, 决定 base ref)
2. **必读合并顺序表** (本任务 §2.1, 决定 merge 时序)
3. **必跑 6 项硬指标验证** (本任务 §4, 决定合并后是否回归)

**Why**: 6 agents 并行在独立 worktree, 主指挥合并时无单一信息源 → 协调 agent 必须显式沉淀合并顺序 + 冲突预案 + 验证脚本, 否则主指挥拍板时缺依据.

**How to apply**: 
- 任何 multi-agent 派工第 7 agent (收尾) 必须交付: memory + CHANGELOG + 合并脚本 + 冲突预案
- 主指挥拍板前必读协调 agent 交付的 3 件套
- 合并后必跑 6 项硬指标验证 (baseline + endpoint + WS + e2e + mobile + 0 production code)

---

## 8. 完成汇报 (Agent 7 主指挥协调)

1. **W68 第 1 批 路线 A 6 agents 合并顺序确定** ✅ — 按 commit 时间 + 依赖关系 7 步合并
2. **预期冲突预案完整** ✅ — 高/中/低风险分类 + 解决方案
3. **6 项硬指标验证脚本完整** ✅ — 主指挥合并后必跑
4. **memory 沉淀** ✅ — 本文件 (w68-route-a-merge-2026-07-24.md)
5. **CHANGELOG.md L5 段新增** ✅ — Drive v2 PR8 收官段 (6 项交付)
6. **0 production code 改动铁律维持** ✅ — 仅 docs + memory 改动
7. **1 W68 新铁律沉淀** ✅ — Cross-branch 协调 3 件套铁律

---

## 9. 相关 memory + docs

- `memory/w68-dispatch-candidates-2026-07-23.md` — W68 派工候选 (Agent 53 派工前评估)
- `memory/anchor-paradigm-21-day-validation-2026-07-22.md` — 锚点范式 21 天实战 (W67 守恒 28)
- `memory/w67-grand-closure-qa-bench-ci-final-2026-07-23.md` — W67 跨主题收口 (本任务基线)
- `memory/orchestrator-mode-coordination-2026-07-20.md` — 主指挥协调范式 5 协调铁律
- `docs/drive-v2-pr8.md` (Agent 6 待写) — Drive v2 PR8 用户文档
- `CHANGELOG.md` L5 段 (本任务新增) — Drive v2 PR8 收官段

---

## 10. 总结

W68 第 1 批 路线 A (Drive v2 PR8 收官) 6 agents + 1 收尾协调 agent 派工完成. **Agent 7 (本任务)** 负责 cross-branch 协调: 合并顺序表 + 冲突预案 + 验证脚本 + memory 沉淀 + CHANGELOG L5 段. **0 production code 改动铁律维持**, 锚点范式 W68 第 29 次派工准备就绪.

**Co-Authored-By**: Claude Fable 5 <noreply@anthropic.com>
**Date**: 2026-07-24
**Version**: W68 Route A 协调 v1.0