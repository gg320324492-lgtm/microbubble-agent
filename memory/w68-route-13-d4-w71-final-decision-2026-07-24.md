# W68 路线 13 D-4：W71 最终决策

日期：2026-07-24  
关联文档：`docs/w71-final-decision-2026-07-24.md`  
范围：W68 第 13 批完工、W71/W72 选项、Q4 商业化路线

## 1. 结论摘要

W68 第 13 批完成 15 agents 协调、8 plans 闭环和 4 项真调研。本 D-4 严格维持 0 production code 改动，仅新增决策文档与本 memory。主指挥默认拍板选项 A：不启动 W71 agents，先将 W68 第 5–13 批部署到云 server，并用真实环境证据决定后续路线。

本轮锚点范式为**第 171 守恒**。守恒对象不是“继续派工”，而是把批次事实、部署命令、质量门禁、回滚 RTO 和季度资源决策放入一个可复现闭环。

## 2. 批次事实

- 15 agents：覆盖部署、qa-bench、Drive v2、移动端、文档、计划核验和调研。
- 8 plans：以代码、测试、提交和文档证据核对完成状态。
- 4 真调研：形成选项输入，不将调研误记为实现。
- 0 production code：本 D-4 仅 docs + memory。
- 规模口径：主仓库约 230 commits；决策范围 12 批累计 215 commits，必须在报告中区分两种统计。

## 3. W71 四选项矩阵

| 选项 | 决策 |
|---|---|
| A（推荐） | 0 agents；主指挥部署 W68 第 5–13 批；12 批 215 commits + 12 monitor scripts；120–180 min |
| B | 4–6 agents、1–2 周；notify v2 仓库模板、dazzling Ollama、5 个真未实施 plans backlog |
| C | B + W72；8–10 agents、2–3 周；Drive v2 PR16 retention + alembic rebase 后续 |
| D | Q4 商业化打包；24 人月 |

默认顺序是 A → 证据评审 → 必要时 B/C；D 单独进行季度商业评审。没有部署日志和 monitor 证据，不得仅凭 backlog 启动新批次。

## 4. 十步 checklist 守恒

1. SSH 部署 W68 第 5–13 批。
2. `bash scripts/setup_vapid_persistence.sh`。
3. `bash scripts/verify_w68_7th_batch_deployment.sh`。
4. `bash scripts/w68_7th_batch_cleanup_plan.sh --apply`。
5. `bash tests/qa-bench/run_d5_dry.py --full --per-intent --gate-threshold 90`。
6. Desktop v3.2 端到端。
7. `npm run build`，禁止裸 `vite build`。
8. `bash tests/test_baseline_audit.py`。
9. 3 个 monitor：VAPID、Phase 2、部署。
10. `git status` + `git log --oneline -5`。

10 项必须保留输出；D5 gate 目标 90；E2E/build 无阻塞；monitor 无 critical；版本和工作树可复核。

## 5. Q4 商业化资源

Q4 总计 24 人月：Phase 8 实时语音 4、Phase 2 SaaS 6、Phase 3 EXE 4、Phase 4 APP 6、预留 4。入口条件是稳定部署、SLA、权限审计、真实试点和可测成本；未满足条件时仅保留规划，不承诺交付。

## 6. 五类失败回滚

1. SSH/版本不一致：停脚本、保存日志、回上一已验证 commit；RTO 15 分钟。
2. 迁移失败/多 head：恢复备份、修 down_revision、staging 重跑；RTO 30 分钟。
3. VAPID/SW/PWA 回归：恢复旧 dist/SW，重新合法 build；RTO 20 分钟。
4. D5 或 Desktop E2E 失败：标记未通过、保留样本、回滚应用；RTO 30 分钟。
5. cleanup 误删/数据异常：停 cleanup/celery、从备份恢复、复核范围后再运行；RTO 60 分钟，数据恢复另计。

## 7. 五条新铁律

1. **四选项矩阵铁律**：W71 先写 A/B/C/D 和入口条件，再决定是否派工；不得由 backlog 自动触发 agents。
2. **十步 checklist 铁律**：部署完成必须有 10 项命令输出；部分完成只能标记 partial。
3. **商业化 24 人月铁律**：Q4 资源按实时语音/SaaS/EXE/APP/预留固定口径，不把技术 sprint 当商业承诺。
4. **五类失败回滚铁律**：每次部署必须同时记录场景、路径和 RTO，不能只写“可回滚”。
5. **季度拍板铁律**：A 部署和连续观测后再评估 B/C；D 必须进入独立季度商业评审。

## 8. 后续

主指挥在本分支 push 后负责 merge。合并前不修改 production code；部署时引用决策文档并将实际输出回填到部署记录。若 A 通过，再按入口条件选择 W71 子项；若失败，执行对应回滚，不启动 W72。
