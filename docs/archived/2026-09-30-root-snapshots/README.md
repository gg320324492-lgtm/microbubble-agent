# 2026-09-30 根目录散落文档归档

## 这是什么

2026-09-30 文档收敛时，从 `docs/` **根目录**迁入的一次性产物快照（45 个）。

这些文件的共同特征：**记录某一次派工/某一天的状态，任务完成后使命即结束**。
典型如 `w98-n4-v11-section13-2026-08-01.md`、`w-n-fill-impl-2026-08-06.md`、
`deploy-status-2026-08-05.md` —— 它们在写的当天有用，一个月后只会让人误以为是现状。

## 为什么不用 git mv + 保留链接

因为它们**本来就不该被引用**。归档前逐个 `git grep` 核实：

- **45 个**：零引用，或仅被其他已归档文件互引 → 安全迁出
- **9 个被活跃文件引用**（`CHANGELOG.md` / `README.md` / `CLAUDE.md` /
  `scripts/restart-recovery-after-gui-restart.sh` 注释里）→ **留在根目录不动**，
  改动它们会连带改活跃文件，风险大于收益

留在根目录的 9 个（活引用锚点）：
`CHANGELOG-history-2026-07-23.md`、`reprocess-meeting.md`、
`w100-meeting-pipeline-restart-2026-08-04.md`、`w72-prompt-paradigm-v11-2027-04.md`、
`w98-p2-d2-consistency-2026-08-01.md`、`w98-p2-f-wechat-sync-2026-08-01.md`、
`w98-p2-gate-2026-08-01.md`、`w98-p2-grand-closure-2026-08-01.md`、
`w99-n6-ui-impl-2026-08-01.md`

## 纪律（止住增量）

新增文档前先回答：这条信息 **30 天后还有人需要吗**？

- **会**（runbook、架构决策、现行规范）→ 放 `docs/` 根目录或对应子目录，并登记进 `docs/README.md`
- **不会**（批次报告、当天状态、一次性排查）→ 任务完成即归档到本目录或 `docs/archived/` 对应批次目录

判断口径与 CLAUDE.md 那边一致：**现状只写 CLAUDE.md，本目录只放档案**。