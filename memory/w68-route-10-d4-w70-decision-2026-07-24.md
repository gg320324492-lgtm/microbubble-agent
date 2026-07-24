# W68 第 10 批 D-4：W70 决策沉淀

**日期**：2026-07-24  
**范围**：W68 第 10 批完工盘点、W70 选项矩阵、部署验收与 Q4 商业化路线  
**变更纪律**：本次仅新增 docs + memory，不修改 production code。  
**锚点范式**：第 **134** 守恒。

## 1. 结论

W68 第 10 批完成 15 agents、5 个 hot-fix，并完成路线 B/C/D/E 的实跑或验收入口准备。当前正确状态是“开发侧完成，部署侧待主指挥验收”，不是继续无条件扩大派工。

主指挥建议优先选择 **选项 A**：0 agents、0 周新增开发，先把 W68 第 5—10 批部署到云 server，完成 Phase 2 1000 题、VAPID 持久化 verify、部署 verify、Desktop v3.2 e2e 和 baseline audit。真实证据出来后，再决定是否启动 W69。

选项 B（4—6 agents，1—2 周）仅用于真实验收后已定位的 chatgpt 子 plan ② 与 6 plans 小修；选项 C（6—8 agents，2—3 周）须等待数据支持后再同时推进子 plan ②③ 与 Drive v2 PR；选项 D（0 agents）用于部署窗口或资源不可用时接受现状并转入 Q4 排期。

## 2. 本批交付事实

- 15 agents 形成清晰的单一验收目标。
- 5 个 hot-fix 将代码状态提升为可执行部署验证状态。
- 路线 B 覆盖 Drive v2 连续迁移与部署边界。
- 路线 C 覆盖 Desktop/Mobile v3.2 真实浏览器路径。
- 路线 D 覆盖 qa-bench D5/D6 真跑入口与质量矩阵。
- 路线 E 覆盖部署脚本、清理计划、文档和守恒审计。
- 本批仍维持 0 production code 改动铁律。

## 3. 主指挥八步 checklist

1. SSH 部署 W68 第 5+7+8+9+10 批（main 含 15+4 commits）。
2. 执行 `bash scripts/setup_vapid_persistence.sh` 一次。
3. 执行 `bash scripts/verify_w68_7th_batch_deployment.sh`。
4. 执行 `bash scripts/w68_7th_batch_cleanup_plan.sh --apply`，预期清理 15 worktree + 16 分支。
5. 执行 `bash tests/qa-bench/run_d5_dry.py --full --per-intent --gate-threshold 90`，真跑 1000 题。
6. 执行 `bash scripts/setup_vapid_persistence.sh --verify`，确认重启后密钥稳定。
7. 执行 Desktop v3.2 端到端 e2e，保存浏览器和网络证据。
8. 执行 `bash tests/test_baseline_audit.py`，预期 71 PASS + 7 SKIP。

预计耗时 90—150 分钟。任何失败都要保存证据并进入回滚流程，不能跳过后宣称全量通过。

## 4. 五项新铁律

### 铁律 1：四选项矩阵先于派工

W70 的决策必须显式比较 A/B/C/D：先部署取证、有限小修、扩展路线、接受现状。没有矩阵就直接派 agent，会把不确定性转化为无边界开发。

### 铁律 2：八步 checklist 是部署完成定义

“代码已合并”不等于“批次已完成”。部署、VAPID、verify、清理、1000 题、e2e 和 baseline 八步必须分别留证；任何一项失败都不能用其他步骤抵消。

### 铁律 3：商业化路线按 24 人月资源池规划

Phase 8 实时语音科研助手 4 人月、多组织 SaaS 4 人月、桌面 EXE 4 人月、多平台原生 APP 6 人月，功能估算合计 18 人月；考虑协调、测试、产品和上线缓冲，Q4 应预留约 24 人月资源池，不能把 18 人月直接承诺为交付工期。

### 铁律 4：失败先回滚，后讨论扩展

部署、迁移、VAPID、Phase 2、Desktop e2e、baseline 或清理任一失败时，先保留证据并恢复稳定版本。禁止在失败状态继续扩大 W69/W70 范围；只有根因明确且可控，才进入选项 B 评估。

### 铁律 5：季度拍板必须基于上一季度证据

W69/W70 不得仅凭 agents 数量、commit 数量或主观完成感启动商业化路线。每季度拍板应读取上一阶段的部署结果、质量分数、e2e、用户反馈、资源和回滚记录，再决定继续、收缩或暂停。

## 5. 长期路线建议

Q4 2026 建议按以下顺序评估：

1. 多组织 SaaS：先建立 tenant、权限、配额和审计边界。
2. Phase 8 实时语音：强化科研会议和实验现场差异化。
3. 桌面 EXE：降低 Docker/GPU/FRP 部署及支持成本。
4. 多平台原生 APP：在推送、离线同步和组织模型稳定后扩大触达。

该顺序是决策输入，不是未经资源确认的承诺。实时语音与 SaaS 可并行预研，但正式开发必须通过独立季度拍板。

## 6. 失败回滚摘要

- 部署失败：恢复上一稳定镜像/commit，确认首页、登录和核心 API。
- Alembic 失败：停止升级，不用 `upgrade heads` 绕过，恢复 revision 后在 staging 重放。
- VAPID 失败：不覆盖旧密钥，恢复原挂载和环境变量，确认旧公钥可读。
- 1000 题/e2e 失败：保存报告和日志，先分类环境、数据或代码根因。
- Baseline/清理失败：停止清理，使用 reflog、远端分支和 commit hash 恢复，禁止删除测试掩盖回归。

## 7. 可追溯记录

完整矩阵、命令、结果记录页、Q4 资源说明和回滚细节见：

- `docs/w70-decision-2026-07-24.md`

本 memory 的职责是沉淀锚点范式与五项纪律；实际部署结果须由主指挥在 decision 文档附录记录。