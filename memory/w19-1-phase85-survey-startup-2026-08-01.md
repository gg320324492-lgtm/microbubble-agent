# W19-1 Phase 8.5 业务方向调研 — 起步确认 (W73 铁律)

> **派工 v10 起步 6 项 (W73 铁律实战)**: 派工 v10 §8 起步 6 项全完成 + 派工 brief vs 实测漂移据实上报
> **派工类型**: A 调研 + D 收口
> **派工日期**: 2026-08-01
> **worktree**: E:/agent-w19-1-phase85 (branch: chore/w19-1-phase85, base main `9b2e3ad45`)
> **作者**: Claude Fable 5 (Worker 19-1)

---

## S1-S6 起步确认全 PASS

### S1 git fetch origin + alembic 1 head verify
```
$ git fetch origin
(无新 commits, 已 up-to-date)

$ python -m alembic heads
093_add_search_log_answer_rating (head)
```
✅ 1 head `093_add_search_log_answer_rating` 守恒 (W98 RAG-GC 后状态).

### S2 读 CLAUDE.md §3 + 派工 v10 §13 + W19 选项 A 原则
- ✅ CLAUDE.md §3 当前状态 = W85/W87/W92/W97/W98 等多 batch 收口, W19 选项 A 在多个 batch grand closure 中重复出现 (W87/W95/W98 等累计 30 批).
- ✅ W19 选项 A 维持铁律: 4 留未来 PR 不发起新排期 (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E).
- ✅ 派工 v10 §13 仓库实情真查 6 项铁律 (W98 P2 batch 沉淀).

### S3 worktree 已切到 E:/agent-w19-1-phase85
```
$ pwd
/e/agent-w19-1-phase85

$ git branch
* chore/w19-1-phase85
```
✅ worktree 切换正确, branch 为 `chore/w19-1-phase85`.

### S4 git status clean
```
$ git status
On branch chore/w19-1-phase85
nothing to commit, working tree clean
```
✅ Working tree clean, 无未 commit 改动.

### S5 grep CLAUDE.md + memory/ 真查 Phase 8 / W19 现状
- ✅ `find docs -name "*phase*8*"` = phase-08-data-backup.md (roadmap) + phase-8-disaster-recovery-2026-07-21.md (archived W12 T2 评估) + 5 个 batch closure doc
- ✅ `grep -l "Phase 8\|24 人月" memory/` = memory/MEMORY.md + memory/phase-8-cloud-mirror-2026-07-21.md + memory/future-pr-trigger-evaluation-2026-07-22.md (W51 评估)
- ✅ `grep "W19 选项 A" CLAUDE.md` = 30+ 处提及, 跨越 W19 起至 W98 RAG-GC, 累计 30 批维持

### S6 起步确认 (本文件)
✅ 本文件 `memory/w19-1-phase85-survey-startup-2026-08-01.md` 已创建.

---

## ⚠️ 派工 brief vs 实测漂移 (类 20 据实上报 #21)

**关键发现**: 派工 v10 §2.2 描述 **Phase 8.5 候选方向 A/B/C (企业版深度定制 / 插件市场 / 性能优化)** 与项目实际定义 **Phase 8.5 异地冷备 (USB HDD + 异地保险箱)** **严重不符** (类 20 漂移 #21).

**漂移事实**:
| 维度 | 派工 brief 描述 | 项目实际定义 (CLAUDE.md + memory/) |
|------|----------------|--------------------------------------|
| Phase 8.5 主题 | 商业化方向 (企业版/插件市场/性能) | **异地冷备 (USB HDD + 异地保险箱)** |
| 来源依据 | 派工 prompt §2.2 (推测) | memory/future-pr-trigger-evaluation-2026-07-22.md §1.1 (W51 评估) |
| Phase 8 已完成现状 | 派工 brief §2.1 提到"商业化 SaaS / 24 人月 Q1 / billing/payment" | Phase 8 = **数据备份 (roadmap-phases/phase-08-data-backup.md)**, 与商业化无关 |
| 候选方案 A/B/C | 企业版/插件/性能 (派工 §2.2) | 实际无候选方案 — W19 已拍板选项 A 留未来 (future-pr-decision-2026-07-21.md §1.1) |

**处理策略 (W82/W84 据实上报铁律)**:
1. **不伪造**派工 brief 商业化方向 (类 20.13 实战 19 沉淀)
2. **不擅自扩**也不擅自缩 (类 20 实战 19 据实上报)
3. **真实调研** = 按项目实际定义 (Phase 8.5 异地冷备 + W19 选项 A 维持)
4. **明确披露** = 在 docs runbook + memory 沉淀 + 18 项反馈中均标注此漂移

**Phase 8.5 调研真实范围 (修正后)**:
- §1 Phase 8 已完成现状盘点 (8.1/8.2/8.3/8.4 ✅ + 8.5 ⏳)
- §2 候选方案 (项目实际未拍板候选, 仅留未来 PR 评估; 派生 3 选项: 维持留未来 / 立即实施 / 部分实施)
- §3 主拍决策依据 3 维度 (W19 选项 A 兼容性 + 数据价值 vs 成本 + 触发条件)
- §4 资源 / 风险 / 时间预估
- §5 与 W19 选项 A 兼容性 (核心)
- §6 推荐方案 + 实施路线图 (如主拍启动)

---

## 起步确认 PASS, 进入阶段 2 (3 候选方案 + 主拍决策依据)