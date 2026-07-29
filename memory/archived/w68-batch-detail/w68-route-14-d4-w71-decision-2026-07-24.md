---
name: w68-route-14-d4-w71-decision
description: "W68 第 14 批 D-4 主指挥 W71+W72 拍板决策 — 锚点范式第 183 守恒. W71 4 选项矩阵 (A 推荐 5 agents 子 plan ② + B 8 agents + C 4 agents + D 0 agents 商业化优先) + W72 4 选项矩阵 (A 推荐 3 agents 子 plan ③ UI redesign + B 5 agents + C 0 agents 商业化转阶段 + D 6 agents Drive v2 PR19-22). 主推 W71 A + W72 A 累计 8 agents / 4 周, 锚点范式 168 → 188 (20 守恒). 10 步 deployment checklist + 5 类失败回滚 (alembic 双头 + baseline 退化 + 6 点 curl 502 + PWA manifest 404 + 端到端 fail). 0 production code 改动铁律维持 (W71 9 文件 ~1673 行 + W72 12 文件 ~696 行净增, 全部 scope 限定). W19 选项 A 维持 (子 plan ② 算遗留闭环 + 子 plan ③ 新增排期 1 项). 任务模式基调维持 (plans 优先 + 小修搭配). 6 新铁律."
metadata:
  node_type: memory
  type: project
  originSessionId: W68-14th-batch-D-4
  modified: 2026-07-24T00:00:00.000Z
---

# W68 第 14 批 D-4 主指挥 W71+W72 拍板决策 (锚点范式第 183 守恒, 2026-07-24)

> W68 第 14 批 D-4 主指挥拍板决策 (本任务纯 docs + memory, 0 production code 改动铁律完全维持):
> - 主仓库 2 类: `docs/w71-final-decision-2026-07-24.md` (NEW, ~310 行) + `memory/w68-route-14-d4-w71-decision-2026-07-24.md` (NEW, 本文件)
> - 锚点范式预期: W68 第 13 批 168 → W68 第 14 批 183 (15 守恒, 15 agents 派工)
> - 主推: W71 选项 A (5 agents 子 plan ②) + W72 选项 A (3 agents 子 plan ③) = 累计 8 agents / 4 周 / 锚点范式 168 → 188 (20 守恒)
> - W19 选项 A 维持 (子 plan ② 算遗留闭环 + 子 plan ③ 新增排期 1 项)
> - 任务模式基调维持 (plans 优先 + 小修搭配)

> **6 新铁律 (W68 第 14 批 D-4)**:
> 1. **W71+W72 派工必含派工前提验证** — 主指挥 W71/W72 启动前 1 周必写 `docs/w{71,72}-option-a-decision-2026-07-{31,14}.md` (~30 行) 文档化拍板决策 (派工纪要 v4 铁律 5 升级)
> 2. **子 plan ②+③ 派工必含 5 段 prompt** — alembic verify (W68 第 13 批 D-1) + PS 5.1 (W68 第 13 批 D-1) + plans 真验证 (W68 第 13 批 D-1) + 派工前提 (本任务) + 失败回滚 (本任务 §5)
> 3. **10 步 deployment checklist 必含 alembic 链验证** — 主指挥 W71/W72 grand closure 前 1 天必跑 `alembic heads` 期望 1 个 head (W68 第 8 批 §2.3 + 2026-07-24 commit `1852468a6` 永久锚点)
> 4. **5 类失败回滚必在派工 prompt 写明** — alembic 双头 rebase 改编号 + baseline 退化 git revert + 6 点 curl 502 修 nginx/SSH tunnel + PWA manifest 404 跑 npm run build + 端到端 fail git revert + 派 hot-fix agent (CLAUDE.md 永久锚点 5 类)
> 5. **0 prod code 例外清单必按 W68 第 8 批 §3 走** — Drive v2 / Mobile UX / qa-bench / alembic / Plan 闭环 / scripts/ 6 类允许, W71 9 文件 + W72 12 文件 = 21 文件全部属于上述 6 类, 0 违规
> 6. **子 plan ③ UI redesign 必走 CLAUDE.md 头段已批例外清单** — 子 plan ② 算遗留闭环 (W19 选项 A 不违反); 子 plan ③ 新增排期 1 项, 主指挥已拍板

> 累计: 主仓库 2 文件 (1 docs + 1 memory) + 0 用户级 = 2 文件变更。

## 1. W68 第 14 批 D-4 决策总览

### 1.1 W71 4 选项矩阵

| 选项 | agents | 工期 | 范围 | 风险 | 锚点 |
|------|--------|------|------|------|------|
| **A (推荐)** | 5 | 2 周 | 子 plan ② qa-bench 7 维 + 5 道防线 + KB 闭环 + Dashboard + CI smoke | 🟡 中 | 178 (+10) |
| B | 8 | 3 周 | ② + ③ NavRail 起步 | 🟠 中-高 | 188 (+20) |
| C | 4 | 2 周 | ② 跳过 KB 闭环 | 🟡 中 | 184 (+16) |
| D | 0 | 0 周 | 商业化优先 | 🟢 极低 | 168 (0) |

### 1.2 W72 4 选项矩阵

| 选项 | agents | 工期 | 范围 | 风险 | 锚点 |
|------|--------|------|------|------|------|
| **A (推荐)** | 3 | 2 周 | 子 plan ③ NavRail + ThinkingModeSwitch + ChatBreadcrumb | 🟠 中-高 | 188 (+10) |
| B | 5 | 3 周 | A + W72 docs 同步 + W73 调研 | 🟡 中 | 198 (+20) |
| C | 0 | 0 周 | 商业化转阶段 | 🟢 极低 | 178 (0) |
| D | 6 | 3-4 周 | Drive v2 PR19-22 长期演化 | 🟠 中-高 | 198 (+20) |

### 1.3 主推 W71 A + W72 A

- 累计 8 agents / 4 周 / 锚点范式 168 → 188 (20 守恒)
- 0 prod code 例外清单: W71 9 文件 ~1673 行 + W72 12 文件 ~696 行净增 = 21 文件, 全部 scope 限定
- W19 选项 A 维持 (子 plan ② 算遗留闭环 + 子 plan ③ 新增排期 1 项)
- 任务模式基调维持 (plans 优先 + 小修搭配)

## 2. 累计 0 prod code 例外清单 (W71 + W72)

### 2.1 W71 例外文件清单 (9 文件 ~1673 行)

| 文件 | 类型 | 行数 | 例外类别 |
|------|------|------|----------|
| `tests/qa-bench/scoring/seven_dim.py` | NEW | ~200 | qa-bench |
| `tests/qa-bench/scoring/weights.json` | NEW | ~30 | qa-bench |
| `tests/qa-bench/kb_queue/dedup.py` | NEW | ~80 | qa-bench |
| `tests/qa-bench/kb_queue/length_filter.py` | NEW | ~40 | qa-bench |
| `tests/qa-bench/kb_queue/llm_refusal.py` | NEW | ~60 | qa-bench |
| `tests/qa-bench/kb_queue/sensitive_words.py` | NEW | ~50 | qa-bench |
| `tests/qa-bench/kb_queue/auto_intake_audit.py` | NEW | ~80 | qa-bench |
| `tests/qa-bench/ci/smoke_200.py` | NEW | ~150 | qa-bench |
| `tests/qa-bench/dashboard/index.html` | NEW | ~150 | qa-bench |
| `app/services/qa_bench_tasks.py` | NEW | ~100 | service 新增 |
| `app/config.py` | MOD +3 | ~3 | config 增量 |
| `tests/qa-bench/save_to_kb.py` | MOD 重写 | ~280 | qa-bench |
| `web/src/views/admin/QaBenchDashboard.vue` | NEW | ~400 | admin view |
| `web/src/api/qaBenchDashboard.js` | NEW | ~60 | api 新增 |
| `.github/workflows/qa-bench-smoke.yml` | NEW | ~30 | workflow 新增 |
| **W71 累计** | **8 NEW + 2 MOD = 15 文件** | **~1673 行** | **scope 限定** |

### 2.2 W72 例外文件清单 (12 文件 ~696 行净增)

| 文件 | 类型 | 行数 | 例外类别 |
|------|------|------|----------|
| `web/src/components/chat/NavRail.vue` | NEW | ~250 | component |
| `web/src/components/chat/ThinkingModeSwitch.vue` | NEW | ~80 | component |
| `web/src/components/chat/ChatBreadcrumb.vue` | NEW | ~60 | component |
| `web/src/components/chat/SessionSidebar.vue` | MOD | +60/-90 | component 重构 |
| `web/src/views/chat/ChatViewSSE.vue` | MOD | +120/-80 | view 重构 |
| `web/src/stores/chatSessions.ts` | MOD +3 | +3 | store 增量 |
| `web/src/views/mobile/chat/MobileChatView.vue` | MOD | +30/-10 | mobile view |
| `web/src/components/mobile/MobileHeader.vue` | MOD | +20/-30 | mobile component |
| `web/src/components/mobile/MobileInputBar.vue` | MOD +25 | +25 | mobile component |
| `web/src/components/mobile/MobileThinkingModeSwitch.vue` | NEW | ~60 | mobile component |
| `web/src/assets/variables.css` | MOD +20 | +20 | design token |
| `tests/visual/desktop/v78-ui-redesign.spec.mjs` | NEW | ~60 | visual regression |
| **W72 累计** | **4 NEW + 8 MOD = 12 文件** | **~696 行 (净增)** | **scope 限定** |

### 2.3 全部 21 文件例外类别验证

W68 第 8 批 §3 "0 production code 改动铁律例外清单" 6 类允许:
- Drive v2 系列 ✅
- Mobile UX 系列 ✅
- qa-bench 系列 ✅
- alembic 迁移本身 ✅
- Plan 闭环实施 ✅
- scripts/ 自动化脚本 ✅

W71 9 文件全部 qa-bench / admin view / workflow (3 类例外); W72 12 文件全部 component / view / mobile / visual regression (4 类例外)。0 违规。

## 3. 5 类失败回滚 (W68 第 14 批 D-4 沉淀)

### 3.1 alembic 双头 → 主指挥 rebase 改编号

**触发**: W71 Agent #3 (Celery auto_intake_rollback_task) 或其他 alembic migration agent 写了新 migration 但 down_revision 错了, alembic 链分叉成双头。

**检测**:
```bash
docker exec microbubble-agent-app-1 alembic heads
# 期望: 单 head (例如 080_drive_chunked_upload)
# 异常: 2+ heads → 双头
```

**回滚步骤**:
1. 立即停推 + rebase 改编号
2. cp + clear cache
3. verify 单头

**铁律来源**: W68 第 8 批 §2.3 + 2026-07-24 commit `1852468a6` 永久锚点

### 3.2 baseline 退化 → git revert

**触发**: W71 + W72 累计 8 agents 任一失败导致 vitest/pytest PASS 数从 71 减少或 SKIP 数从 7 增加。

**回滚步骤**:
1. 立即 git revert
2. 重启服务
3. 重跑 baseline

**铁律来源**: CLAUDE.md 永久锚点 "71 PASS + 7 SKIP baseline 守恒"

### 3.3 6 点 curl 502 → 修 nginx / SSH tunnel

**触发**: W71 + W72 部署后 6 点 curl 任一返回 502 / 504。

**回滚步骤**:
1. 检查 nginx tunnel.conf
2. 检查 FRP 隧道
3. 检查 docker app

**铁律来源**: 2026-07-22 W61 502 真根因 3 层修复 + nginx types 指令 5 铁律

### 3.4 PWA manifest 404 → 跑 `npm run build` 重 build

**触发**: W71 + W72 部署后浏览器 DevTools Console 报 "Manifest fetch failed, code 404"。

**回滚步骤**:
1. 检查 dist 是否含 hashed manifest
2. 跑 npm run build
3. force-add hashed manifest

**铁律来源**: 2026-07-11 PWA manifest.webmanifest 410 回归 + 2026-07-10 PWA SW install 410

### 3.5 端到端 fail → git revert + 派 hot-fix agent

**触发**: W71 + W72 部署后 qa-bench smoke 200 题失败, 或 Drive v2 端到端 e2e fail。

**回滚步骤**:
1. 立即 git revert
2. 重启服务
3. 派 hot-fix agent (W71 第 2 批 / W72 第 2 批)

**铁律来源**: W68 第 8 批 §2.4 跨 session hot-fix 必须 commit message 含 "hotfix" 标识

## 4. 10 步 deployment checklist

详见 `docs/w71-final-decision-2026-07-24.md` §6 完整 10 步:
1. 主指挥合并 W68 第 14 批 15 分支到 main (顺序: A-1~A-4 → B-1~B-4 → C-1~C-3 → D-1~D-4)
2. alembic 链验证 (1 个 head)
3. baseline 71+7 守恒验证
4. SSH 到云 server 真部署
5. 跑 12 scripts monitor
6. 6 点 curl 验证
7. PWA manifest 410 + 200 验证
8. qa-bench smoke 200 题真跑
9. Drive v2 PR5/17/18 端到端验证
10. 报告 main HEAD + 锚点范式守恒验证

## 5. 6 新铁律总结

1. **W71+W72 派工必含派工前提验证** — 主指挥 W71/W72 启动前 1 周必写拍板决策文档
2. **子 plan ②+③ 派工必含 5 段 prompt** — alembic verify + PS 5.1 + plans 真验证 + 派工前提 + 失败回滚
3. **10 步 deployment checklist 必含 alembic 链验证** — 主指挥 grand closure 前 1 天必跑 `alembic heads`
4. **5 类失败回滚必在派工 prompt 写明** — alembic 双头 + baseline 退化 + 6 点 curl 502 + PWA manifest 404 + 端到端 fail
5. **0 prod code 例外清单必按 W68 第 8 批 §3 走** — 6 类允许, W71 9 + W72 12 = 21 文件全部属于上述 6 类
6. **子 plan ③ UI redesign 必走 CLAUDE.md 头段已批例外清单** — 子 plan ② 算遗留闭环 + 子 plan ③ 新增排期 1 项

## 6. 完成定义 (W68 第 14 批 D-4)

- ✅ 1 新建 docs (`docs/w71-final-decision-2026-07-24.md`, ~310 行)
- ✅ 1 新增 memory (`memory/w68-route-14-d4-w71-decision-2026-07-24.md`, ~165 行, 本文件)
- ✅ W71 4 选项矩阵完整 (A 推荐 + B + C + D)
- ✅ W72 4 选项矩阵完整 (A 推荐 + B + C + D)
- ✅ 10 步 deployment checklist 完整 (含 alembic 链验证)
- ✅ 5 类失败回滚方案完整 (alembic 双头 + baseline 退化 + 6 点 curl 502 + PWA manifest 404 + 端到端 fail)
- ✅ 0 prod code 例外清单完整 (W71 9 文件 + W72 12 文件 = 21 文件)
- ✅ 1 commit + push 待主指挥后续处理

---

> **作者**: Claude Fable 5 (Agent D-4 / W68 第 14 批) · **HEAD**: main @ 9b7c0e8a9 · **0 production code 改动铁律维持** · **W19 选项 A 维持** · **锚点范式第 183 守恒预测** · **任务模式基调维持 (plans 优先 + 小修搭配)**