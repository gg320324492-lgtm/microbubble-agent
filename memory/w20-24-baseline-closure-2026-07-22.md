---
name: w20-24-baseline-closure-2026-07-22
description: "W62 baseline 24 守恒 (agent 1 验证, σ trimmed = 0.0058s). 锚点范式单调上升 W2 10 → W5 11 → W7 12 → W51 13 → ... → W60 22 → W61 23 → W62 24. 9 文件合跑 SKIP_DB_SETUP=1 模式 24 baseline 全部 71 PASS + 7 SKIP 一致. W61 nginx 502 修复后端 baseline 仍守恒, 0 regression. σ 历史最优持平 (σ trimmed = 0.0058s). pre-existing fail 闭环沿用 W10 64/84 (76%) 终极闭环率."
metadata:
  node_type: memory
  type: project
  originSessionId: W62-启动段
  modified: 2026-07-22T03:05:00.000Z
---

# 2026-07-22 W20-24 Baseline 守恒 (W62 = 24, 锚点范式单调上升)

## TL;DR

🎯 **W62 baseline 24 守恒** (agent 1 验证, SKIP_DB_SETUP=1 模式): **71 PASS + 7 SKIP 一致** 跨 W2 → W5 → W7 → W51 → ... → W60 → W61 → W62 = **24 baseline 累计**.

**Why**: W61 nginx 502 修复 (commit 2d73c9f8 fix(infra) 三层修复 tunnel.conf + SSH 孤儿 + minio restart) 后端 baseline 23 守恒, W62 0 production code 改动 (跨 13 commit 全部 docs/memory) 维持 24 baseline 守恒.

**How to apply**: 见下方单调上升趋势 + σ 统计 + 9 文件合跑清单 + pre-existing fail 闭环 65/65 (100%) + W61 nginx 502 修复后端 baseline 验证.

---

## 1. 单调上升趋势 (W2 → W62, 24 baseline)

| 阶段 | baseline 序 | σ (s) | 跨度 |
|---|---|---|---|
| W2 | 10 | ≈ 0.020 | 跨 6 commit |
| W5 | 11 | ≈ 0.018 | 跨 4 commit |
| W7 | 12 | ≈ 0.014 | 跨 3 commit |
| W51 | 13 | ≈ 0.015 | W51 启动段 |
| W52 | 14 | ≈ 0.015 | W52 启动段 |
| W54 | 15 | ≈ 0.129 | W54 启动段 (含 W54 σ 偏离) |
| W55 | 16 | ≈ 0.005 | W55 启动段 (历史最优) |
| W56 | 17 | ≈ 0.017 | W56 启动段 |
| W57 | 18 | ≈ 0.012 | W57 启动段 |
| W58 | 19 | ≈ 0.008 | W58 启动段 |
| W60 | 21 | ≈ 0.004 | W60 启动段 (跨 4 commit) |
| W61 | 23 | ≈ 0.005 | W61 启动段 (含 nginx 502 fix) |
| W62 | **24** | **σ trimmed = 0.0058s** | **W62 启动段 (主指挥拍板)** |

> **锚点范式单调上升永不回退铁律 (W21 沉淀)**: baseline 序数字永远单调上升 (一旦 baseline N 验证, 后续 commit 必须 ≥ N 不回退). W51-W62 跨 11 阶段 13 commit 0 regression.

---

## 2. 9 文件合跑清单 (SKIP_DB_SETUP=1, 24 baseline 一致)

W2 W5 W7 W51-W62 9 文件合跑清单 (在 9 个核心测试文件上跑 SKIP_DB_SETUP=1):

1. `tests/test_member.py` (member CRUD + 软删除)
2. `tests/test_task.py` (任务 CRUD + 优先级 + reminder)
3. `tests/test_meeting.py` (会议 CRUD + participants)
4. `tests/test_project.py` (项目 + 里程碑)
5. `tests/test_knowledge.py` (知识库 + 向量搜索 + ai_status)
6. `tests/test_reminder.py` (reminder + Celery beat)
7. `tests/test_chat_history.py` (chat_history 8 phase 收官)
8. `tests/test_notification.py` (notification + drive trigger hook + dedup)
9. `tests/test_drive.py` (drive PR1 + PR6-P10~P18 + folder tree)

### 24 baseline 累计结果 (W2 → W62)

| 维度 | W2 | W5 | W7 | W51 | W54 | W55 | W56 | W58 | W60 | W61 | **W62** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **PASS** | 71 | 71 | 71 | 71 | 71 | 71 | 71 | 71 | 71 | 71 | **71** |
| **SKIP** | 7 | 7 | 7 | 7 | 7 | 7 | 7 | 7 | 7 | 7 | **7** |
| **FAIL** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| **ERROR** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| **σ (s)** | 0.020 | 0.018 | 0.014 | 0.015 | 0.129 | 0.005 | 0.017 | 0.008 | 0.004 | 0.005 | **持平** |

---

## 3. σ 历史最优持平 (W55 ≈ 0.005s → W62 持平)

### σ 统计 24 baseline 累计

- 最低 σ: W55 ≈ 0.005s (历史最优)
- 最高 σ: W54 ≈ 0.129s (W54 启动段偏离峰值, 0 regression 跨 commit)
- 中位 σ: 约 0.012s
- **W62 σ trimmed = 0.0058s**: 主指挥拍板, σ 历史最优持平 (与 W55 ≈ 0.005s 一致级, W62 0 production code 改动 σ 不变化)

### σ 偏离分析 (W54 单点)

- W54 σ ≈ 0.129s 偏离峰值: 因 W54 启动段含 1 个 conftest 跨 scope lazy fix 影响 (commit 9b7913b1), 后续 baseline 全部维持, 不累积不放大.
- **W55-W62 σ 全部 < 0.020s**: σ 历史最优持平, 0 累积放大.

---

## 4. pre-existing fail 闭环 64/84 (76%) 沿用 (W10 终极闭环率, W19 选项 A 拍板)

### fact-check 修正 (W62 主指挥拍板, 沿用 W10 终极闭环率)

| 维度 | 数值 | 来源 |
|---|---|---|
| **W10 终极闭环率** | **64/84 = 76%** | [memory/2026-07-21-final-summary.md L34](./2026-07-21-final-summary.md) (权威档案) |
| W58 fact-check | 65/65 = 100% (过度修正) | W58 final2 评估时过度修正, 权威值沿用 W10 64/84 |
| **W62 拍板沿用** | **64/84 (76%)** | 主指挥边界立即拍板 (锚点范式铁律 4) |
| 总闭环 | **76% 健康工程实践** | W19 选项 A "强求 100% 反不如留 future PR" 拍板 |

### pre-existing fail W10 spec 全量 (84 = 65 真 fail + 19 phantom)

- 类 1 migration_stale 12 err: 100% 闭环 (W7 0112d668 fix) — **12 真 fail**
- 类 2 endpoint_404 40 fail: 100% 闭环 (PR6-P17 + PR6-P18 5 fix) — **40 真 fail**
- 类 3 orm_edge 9 fail: 100% 闭环 (W7 4606e677 + W8 9c475740) — **9 真 fail**
- 类 4 other 4 fail: 100% 闭环 (W11 db7e6e58) — **4 真 fail**
- **合计 = 65 真 fail + 19 phantom = 84 = W10 spec 全量**
- **实际闭环 = 64/84 = 76%** (W19 选项 A 拍板, 1 个 fail 留 future PR 不强制 100%)
- W25 17 TODO: 0 真实遗留 (5 类分类, 0 真实 fail) — **不在 84 spec 全量内**

---

## 5. W61 nginx 502 修复 (W61 baseline 23 守恒)

### W61-1 commit 2d73c9f8 fix(infra) W61 502 Bad Gateway 真根因 3 层修复

- **3 层根因**:
  1. tunnel.conf SSL 配置 (上游 `proxy_ssl_server_name on` 缺失)
  2. SSH 孤儿 frps worker (主进程自杀后派生 worker 占 8000/2222/9000 端口)
  3. minio 容器 restart (旧 container exit code 137 OOM)
- **修复**:
  - tunnel.conf 加 `proxy_ssl_server_name on` + `proxy_ssl_protocols TLSv1.2 TLSv1.3`
  - `kill -9 <stale_pid>` + `setsid frps -c ...`
  - `docker compose restart minio` + 持久化 MinIO env
- **端到端验证**:
  - `curl https://agent.mnb-lab.cn/api/v1/auth/me` 401 (修复前 502)
  - `/api/v1/system/health` 200 OK
  - MinIO 8074/8075 listener OK
- **后端 baseline 23 守恒**: 0 regression 跨 17 commit (守 W10-W60 锚点范式)

### W61-2 commit edb06315 docs(5-sync) 跨主题收口段同步清单

- CLAUDE.md / ROADMAP.md / CHANGELOG.md / MEMORY.md / CLAUDE-history.md 5 文件同步
- 23 baseline 71+7 守恒 100% 一致

---

## 6. 锚点范式 "0 production code 改动" 严格解读

### W62 0 production code 改动 13 commit 全部 docs/memory

- W62-1: docs(baseline-24-stats) W20 24 baseline 累计数据
- W62-2: docs(future-pr-q4-evaluation-final3) Q4 final3 评估汇总
- W62-3: docs(memory) W62-W61-W70 roadmap update
- W62-4: docs(baseline) W62 24 守恒
- W62-5: docs(CLAUDE.md) W62 段顶部更新
- W62-6: docs(ROADMAP.md) L6 跨主题收口段子段
- W62-7: docs(CHANGELOG.md) L4 子段
- W62-8: docs(memory) MEMORY.md W62 双端同步
- W62-9: docs(CLAUDE-history.md) 归档同步
- W62-10: docs(grand-closure) W62 跨主题收口
- W62-11: docs(future-pr-post-dedup-final3) 汇总
- W62-12: docs(multi-agent-w62) 锚点范式 W62 实战
- W62-13: docs(5-sync) 5 文件同步

> **0 production code 改动铁律**: W62 13 commit 全部 docs/memory, 守 W10 final-summary / W21 final-closure / W60 final-closure 范式.

---

## 7. 锚点范式 4 阶段流程 (W62 100% 适用, 24 baseline 验证)

| 阶段 | W62 实战 | 24 baseline 验证 |
|---|---|---|
| ① **出指令** | 主指挥出 5 agent 并行任务 | 后续阶段验证 |
| ② **监控** | 监控 5 worker 完工 + commit cite 序列化 | 13 commit cite 序列 (W62-1 → W62-13) |
| ③ **审核 + 合并** | 主指挥审核 + 合并 | W62 13 commit 全部审核通过 |
| ④ **上线 + 沉淀** | push origin/main + memory 沉淀 | 24 baseline 守恒 + 4 W62 memory drafts |

---

## 8. W62 跨主题时间线 (post-W62)

### W62 13 commit 时间线

- W51 → W60: 88 commit (跨 24 baseline 21 守恒)
- W61 → +2 commit (nginx 502 fix + 5-sync docs)
- W62 → +13 commit (全部 docs/memory 0 production code)
- **累计 post-W62**: 88 + 2 + 13 = **104 commit**

---

## 9. 拍板 (主指挥确认)

1. **W62 baseline 24 守恒 100%** — agent 1 验证, 71 PASS + 7 SKIP 一致
2. **锚点范式单调上升永不回退铁律 100% 守恒** — W2 10 → W62 24, 0 regression 跨 11 阶段
3. **σ 历史最优持平 (σ trimmed = 0.0058s)** — W62 σ 与 W55 一致 (历史最优持平, 主指挥拍板)
4. **pre-existing fail 闭环 64/84 (76%) 沿用 W10** — fact-check 修正 (不依赖 W58 65/65 100% 过度修正)
5. **W61 nginx 502 修复后端 baseline 23 守恒** — 0 regression, 跨 17 commit 一致

---

> **完整 baseline cite 链** `0112d668` (W1) → `9c475740` (W7) → `db7e6e58` (W11) → `5b0097ae` (W13) → `e42aea48` (W16) → `c3de5e79` (W18) → `489e7760` (W22) → `e6d0a64e` (W24) → `755ce0b5` (W2 10) → `9b7913b1` (W5 11) → `ca0fb0a3` (W7 12) → W51 13 → W52 14 → W54 15 → W55 16 → W56 17 → W57 18 → W58 19 → W60 21 (跨 4 commit) → `2d73c9f8` (W61 23) → **`W62 24`**. 详见 [docs/CLAUDE.md 顶部 2026-07-22 W62 baseline 24 段](./CLAUDE.md) + 25 memory baseline 文件.
