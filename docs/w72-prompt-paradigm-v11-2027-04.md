# W72 派工纪要：Prompt Template v11（RAG PR10 落库版）

> 版本：v11（2027-04 计划版, 2026-07-30 PR10 W96 提前落库）
> 适用：主指挥、并行 agent、RAG 大改造 PR 系列派工、文档/调研/迁移/SubAgent 编排派工
> 沿用：v10 12 段全部（`docs/w72-prompt-paradigm-v10-2026-07-27.md`）**不推倒**，v11 = v10 + 6 项新增
> 原则：先验证、再派工；先串链、再合并；据实上报、禁止凑数；命令输出粘贴、禁止脑补。

## TL;DR（v10 → v11 升级理由）

RAG 大改造系列（plan `rag-quirky-otter.md` v1.1, PR1-PR10, W88-W97）+ W82-W96 据实上报实战暴露 v10 六层缺口，v11 补齐：

### v11 新增 1：`python -m alembic` 命令形态铁律

- **实战**: Windows Git Bash 直跑 `alembic heads` 报 `Permission denied`（plan v1.1 基线修正实测）。
- **纪律**: 所有派工 prompt 段 1/段 4/段 8 中 alembic 命令一律写 `python -m alembic <cmd>`；件 1 验证脚本同步改用 `python -m alembic`。agent 报"alembic 跑不了"先自查命令形态再报阻塞。

### v11 新增 2：pytest collection error 白名单必显式

- **实战**: `tests/test_w79_commercial_private_deployment_e2e.py` collection error（plan v1.1）+ W96 实测 `tests/trivy/test_dockerfile_pinning.py` 与 `tests/sentry/` 同 basename import mismatch。
- **纪律**: 派工 prompt 段 4 必列 pytest 白名单（`--ignore=...` 完整清单）+ baseline collected 数字；agent 实测 collected 数与 brief 不符时**据实上报差值**，不擅自扩白名单也不假装全绿。同 basename 测试文件为禁止项（新建测试文件必查 `find tests -name "<basename>"` 唯一性）。

### v11 新增 3：派工 brief 与实测不符必据实上报（错配双向禁令）

- **实战**: W84 据实上报 3 实例（A-2/C-1/C-2 brief 与实测不符）+ W85 B-2 useTask 0 hit 跳过不实施 + W96 PR10 实测 pytest baseline 2860 collected ≠ plan v1.1 的 2701。
- **纪律**: brief 数字（基线 head / collected 数 / 锚点起点 / 文件行号）与实测不符时: (1) 不擅自扩范围 (2) 不擅自缩范围 (3) 报差值 + 证据输出 (4) 阻塞性错配（如锚点被占用）立即回报主指挥禁止脑补继续。锚点 +N 按真 commit 数报，验证型 0 增量不凑 +1。

### v11 新增 4：docs-only PR 量化门禁必数字化 + e2e 断言化

- **实战**: PR10 门禁 "README ≥ 12 节 / 7 件套 schema / v11 落库 / 5 件套守恒 100%" 全部落进 `tests/rag/test_pr10_docs_e2e.py` 自动断言（章节数 grep `^## ` + 关键词存在性 + git diff 0 行 subprocess 实测）。
- **纪律**: 任何 C/D 类 docs 派工必须把量化门禁写成 pytest 断言（文件存在性 + 节数 + 关键词 + 主仓链接），禁止"文档写完了"自由文本自报。docs e2e 必须纯标准库可本机跑（无 DB/无重型依赖，必要时局部 conftest no-op 覆盖 autouse DB fixture 并注明原因）。

### v11 新增 5：worktree 依赖基线必先自检（node_modules / 重型依赖不随 worktree）

- **实战**: W96 PR10 worktree 内 `web/node_modules` 不存在导致 `npm run build` 直接失败（`'vite' 不是内部或外部命令`）；主仓 build 又暴露 `@sentry/vue` 未装 + rolldown panic。`sentence_transformers` 未装则 import embedding_service 即崩（plan §3.7）。
- **纪律**: 段 8 起步必含"依赖基线自检"：worktree 建立后先 `ls web/node_modules` / `python -c "import <重依赖>"`；缺依赖时**在主仓等价验证 + 据实上报**（本任务 0 web 改动时主仓 build 基线等价），不得静默 SKIP 也不得在 worktree 里 `npm install` 污染。build 基线红（与本 PR 无关的预存故障）必据实上报为 pre-existing，不算本 PR FAIL，也不得顺手修（0 production code）。

### v11 新增 6：5 件套守恒命令输出全文粘贴（据实上报升级版）

- **实战**: W82/W84 据实上报铁律 + W96 PR10 收口。v10 只要求"真实执行粘贴输出"，v11 升级为**结构化 5 件套回报表**。
- **纪律**: 收口回报必含下表（命令 + 实测输出原文 + PASS/FAIL 判定），任何一格空缺或写"应该/大概/估计"即视为纸面 PASS 打回：

| 件 | 命令 | 实测输出（原文粘贴） | 判定 |
|----|------|---------------------|------|
| 1 | `python -m alembic heads` | — | 1 head? |
| 2 | `pytest <本 PR e2e> -q` | — | N/N PASS? |
| 3 | `cd web && npm run build` | — | OK / pre-existing FAIL? |
| 4 | `git diff main -- app/ \| wc -l` | — | 0? |
| 5 | `git log --grep "<锚点>" --oneline \| wc -l` | — | ≥ 目标? |

## v11 段结构（v10 12 段全沿用 + 上述 6 项嵌入位置）

| 段 | 内容 | v11 增量 |
|----|------|---------|
| 段 0 | 目标/边界/派工类型/锚点区间 | 锚点起点必实测（新增 3） |
| 段 1 | alembic down_revision | `python -m alembic` 形态（新增 1） |
| 段 2 | 文件改动清单 + 严禁修改 | docs-only 门禁断言化（新增 4） |
| 段 3 | 单测/e2e 目标 | importorskip + 局部 conftest 说明（新增 4） |
| 段 4 | 5 件套守恒 | pytest 白名单显式（新增 2）+ 回报表（新增 6） |
| 段 5 | 反馈 18 项 | 沿用 v10 |
| 段 6 | 据实上报铁律 | 错配双向禁令（新增 3） |
| 段 7 | 错误 19 类 | +E20/E21 已入 v1.1, 沿用 |
| 段 8 | 起步 6 项 | 依赖基线自检（新增 5） |
| 段 9 | commit message 锚点范式 | 沿用 v10 强制约束 |

## v11 生效范围

- RAG 系列 PR 后续维护派工 + W97+ batch 派工默认 v11。
- v10 prompt 已发出且在跑的任务不回改，收口时按 v11 新增 6 回报表补报。
- 派工 v11 检查单速查版见 `docs/rag/CHECKLIST.md`。

---

**版本 v11，2026-07-30 PR10 W96 +9 落库，主指挥合并后正式生效。**

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
