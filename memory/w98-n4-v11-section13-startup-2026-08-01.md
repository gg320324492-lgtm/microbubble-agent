# W98 N-4 v11 §13 实战收敛起步 (2026-08-01)

> **任务**: 派工 v10 — N-4 派工 v11 §13 仓库实情真查实战收敛
> **agent**: N-4 W98 +13 (派工 v10 N-4 派工, 纯 docs/memory 范畴, 0 production code)
> **当前 main HEAD**: `68ed0b55c` (W98 RAG-GC merge commit, 2026-08-01)
> **锚点范式**: W98 RAG-GC +12 → N-4 +13 → +14 守恒 (本任务 1 commit 仅 docs + memory)
> **alembic head**: `093_add_search_log_answer_rating` ✅ 1 head 守恒

## §1 起步 6 项 (W73 铁律严格执行)

### S1: git fetch origin + alembic head verify (093)
- **实测**:
  ```bash
  $ git fetch origin
  (无新输出, 已最新)
  $ python -m alembic heads
  093_add_search_log_answer_rating (head)
  ```
- ✅ 1 head 守恒

### S2: 读 CLAUDE.md §3 + §"当前状态"块 + 派工 v10 + 派工 v11 §13
- **CLAUDE.md §3**: 0 production code 改动铁律例外清单 + 锚点范式守卫
- **CLAUDE.md §"当前状态"块**: W98 RAG-GC 锚点范式 ~490 收口
- **派工 v10** (`docs/w72-prompt-paradigm-v10-2026-07-27.md`): 13 段完整结构, §13 = "9 条新铁律", §8 = W73 起步纪律 6 项
- **派工 v11** (`docs/w72-prompt-paradigm-v11-2027-04.md`, 75 行): 6 项新增 (python -m alembic / pytest 白名单 / 错配双向禁令 / docs 门禁断言化 / 依赖基线自检 / 5 件套回报表)

### S3: worktree 切换确认
- **当前 worktree**: `E:/agent-w98-n4-v11-section13`
- **branch**: `chore/w98-n4-v11-section13`
- **基于 main HEAD `68ed0b55c`** (W98 RAG-GC merge)
- **worktree 状态**: working tree clean (起步已切, 0 commit ahead)

### S4: git status clean
- **实测**: `git status` = `On branch chore/w98-n4-v11-section13 / nothing to commit, working tree clean` ✅

### S5: 派工 v10/v11 模板真查 (派工 v10 §13 仓库实情真查 实战)

派工 brief 引用"§13"实际定位:

| 引用源 | §13 实际含义 |
|--------|------|
| 派工 v10 §13 (line 493) | "9 条新铁律 (v10 沉淀, 4 类合并展示)" |
| W89 PR3 memory 引用"DERIVE-18 §13" | 实际为 v10 §8 W73 起步纪律 6 项 + W73-P3 衍生附录 |
| 派工 v11 §13 | v11 模板未直接定义 §13, 实际位置是 v10 §8 (S5 起步 6 项中的第 6 项"仓库实情真查") |
| 派工 v11 段 10 (新增 6 项) | 内含 "python -m alembic 形态" + "pytest 白名单" + "错配双向禁令" + "docs 门禁断言化" + "依赖基线自检" + "5 件套回报表" 6 项 (对应 §13 应包含内容) |

派工 brief 漂移发现 (派工 v11 段 3 错配双向禁令):
- 派工 brief 写"派工 v11 §13 必填 6 段 (13.1-13.6)", 实际派工 v11 模板 0 段定义 §13, 仅"v11 段结构"表格列了段 0-9, 段结构表(行 50-63)中 "段 8 起步 6 项 (新增 5)" 这一行才有"派工 v10 §8" + "派工 v11 段 10 6 项嵌入" 描述.
- **结论**: §13 在 v11 是缺失段, 需本任务在 v11 模板中正式加 §13 "仓库实情真查 (6 段必填)" (派工 brief 段 0 + 段 2.2 + 段 2.3 设计)

### S6: 起步确认 (本文件)
- 本 memory 写入 `memory/w98-n4-v11-section13-startup-2026-08-01.md` 完成起步 6 项
- 沿用 W98 RAG-GC 派工 v10 段 7 起步纪律 6 项

## §2 W89 类 20.6 + 类 20.13 漂移沉淀

### 2.1 类 20.6 历史定义 (W74 A-2 沉淀)
- **历史类 20.6 定义**: "调研建议主拍必拍'破坏性 vs 渐进'修复路径, 拒绝无脑字面改动" (W74 A-2 调研 + W75/W79/W81 沿用)
- **派工 brief 重定义**: "派工 brief 漏 §13 仓库实情真查 → 收敛到 v11 §13.1 必填"
- **冲突分析**: 派工 brief 重定义与历史定义不冲突 (新类 20 子类可加), 但需要在沉淀中明示"重定义"vs"沿用历史"

### 2.2 类 20.13 历史定义 (W77 B-3 + W78 B-2 沉淀)
- **历史类 20.13 定义**: "真生产 key 单独拍板 (`PROD_KEY_AUTO_ENABLE=False` 硬编码守门)" (W77 B-3 实战 + W78 B-2 沿用)
- **派工 brief 重定义**: "派工 brief 漏 §13 → 同上"
- **冲突分析**: 同上, 派工 brief 重定义需作为新派工纪要类 20 子类

### 2.3 W98 RAG-GC 沉淀中的类 20.13 引用
- W98 RAG-GC memory (line 187): "类 20.13 W89 v11-section13 漏 S13" — 与历史定义冲突 (历史类 20.13 = 真生产 key 主拍)
- **派工 v11 段 3 错配双向禁令**: 类 20 子类编号应保持稳定, 不应"重新分配"
- **修正建议**:
  - 维持历史类 20.6 = "破坏性 vs 渐进修复路径"
  - 维持历史类 20.13 = "真生产 key 单独拍板"
  - 新派工 brief 漂移事件应分配**新**类 20 子类编号, 建议 = **类 20.34** (N-4 派工 v11 §13 漏漂移)

### 2.4 实战案例 (P2-F wechat_service.py vs app/wechat/handler.py)
- **W98 P2-F W98 +6** (`151d58b45`): 微信 `ensure_session_context` 共享服务 + 微信 handler 3 处接入 + 132 行删除 + 12 行 alias + 39/39 PASS
- **类 20.13 实战 19 (冲突引用)**: "派工 brief wechat_service.py 错配, 实测 app/wechat/handler.py"
- **真实漂移类别**: 该案例本质是 "派工 brief 漏仓库实情真查" (派工 v11 §13 实战漂移), 而非 "真生产 key 单独拍板"
- **沉淀建议**: W98 P2-F 实战应归入**类 20.34** (新类, 派工 v11 §13 漏漂移), 而非类 20.13

## §3 派工 v11 §13 必填 6 段设计 (本任务产物)

### 3.1 段 13.1: 路径三验证 (存在性 + 文件类型 + 内容相关性)
- **纪律**: 派工 brief 写路径前必跑 `ls -la <path>` + `file <path>` + `head -30 <path>`, 三者一致才认为路径存在
- **实战案例**: W91 PR5 brief `pwa/src/pages/admin/RAGEvalPanel.tsx` — pwa/ 目录无, pages/ 目录无, 0 .tsx 文件 (true = false, false 目录, false 扩展), 三验证都失败 → 立即发现

### 3.2 段 13.2: 框架栈对齐 (Vue 3 + Element Plus + Vite PWA)
- **纪律**: 派生新任务前必跑 `cat package.json | grep -E "vue|element-plus|vite|@vitejs/plugin-pwa"`, 4 项必须全是前端依赖
- **实战案例**: 项目有 Vue 3 + Element Plus + Vite 但**无** React, 无 pages/ 目录, 无 .tsx 文件, 全部为 .vue

### 3.3 段 13.3: "已落库" 假设禁令
- **纪律**: 派工 brief 写"X 已落库"前必跑 `git log --grep "X" --oneline`, 至少 1 commit 才写"已落库", 0 commit 写"待落库"
- **实战案例**: "W88 PR1 chunk 索引已落库" 必先 grep 实测

### 3.4 段 13.4: 路径错配拦截据实上报
- **纪律**: 路径三验证失败时立即拦截, 必在 commit message 明文标注 "路径修正事实: brief vs 实测差值", 不擅自改不改路径
- **实战案例**: W91 PR5 commit 必标 "路径修正事实: pwa/src/pages/admin/*.tsx → web/src/views/admin/*.vue (PR6 模式对齐)"

### 3.5 段 13.5: 派生新铁律必显式沉淀
- **纪律**: 派工过程派生新铁律时, commit message 必含 "新铁律 [N] 类 20.X: <name> (<实战来源>)", 不偷埋铁律
- **实战案例**: P3-A W98 +11 派生 "真环境 vs 纯 mock 切换", 必标 "类 20.29"

### 3.6 段 13.6: 锚点漂移必报 (v10 → v11 升级 5 条已落库)
- **纪律**: 派工 brief 期望锚点 +N vs 实测 commit 数有漂移时, 必据实上报 + 在 commit message 明文标
- **实战案例**: W89 PR3 brief 预测 16 commits → 实测 13 commits (合并 4 个 docs/memory commit), 必标 "W89 +0 → +12 据实上报, 13 commits ≠ brief 16 commits"

## §4 派工 v11 → v11.1 升级建议

### 4.1 必填 6 段嵌入位置
- v11 段结构表中"段 8 起步 6 项"行后, 增加"段 13 仓库实情真查 (新增 6 段必填)"行
- v11 段 8 行新增 5 (依赖基线自检) 后, 段 13 引流到本任务沉淀

### 4.2 必填上报 6 段嵌入位置
- v11 段 5 反馈 18 项基础上, 增加 6 段必填: "件 4b 仓库实情真查表" (S5 起步 6 项第 5 项的子表)

### 4.3 v11.1 升级路径
- **不推倒 v11**: 沿用 v11 6 项新增, 仅新增 "段 13 仓库实情真查 6 段必填"
- **v11.1 验收**: 收口时新派工 brief 必含 §13 6 段, 否则视为"派工 brief 漏 §13 → 类 20.34 实战"
- **v11.1 沉淀**: docs/w72-prompt-paradigm-v11.1-2026-08-01.md (本任务派生)

## §5 派工 brief 18 项反馈目标 (本任务预计)

1. 任务目标完成度 (v11 §13 实战收敛报告)
2. 实际 git diff 文件清单 (含行数)
3. v11 §13 实战漂移清单 (漏 §13 的派工 brief 数量)
4. W89 类 20.6 + 类 20.13 漂移沉淀完整
5. v11 §13 必填 6 段 (13.1-13.6) 详细描述
6. v11 模板实战漂移修复建议
7. 派工 v11 → v11.1 升级建议 (含 §13 段必填)
8. 类 20.34 v11 §13 实战收敛 (建议新增)
9. 0 production code 实测 (必 = 0)
10. alembic 1 head 实测输出
11. 锚点范式实测 commit 数 (grep 实测 ≥ 13)
12. 派工 brief vs 实测漂移
13. 类 20 实战累计数 (W89-W98 应 ≥ 25)
14. docs runbook 内容
15. memory 沉淀内容
16. MEMORY.md 索引同步
17. worktree 状态 + push origin
18. 任何回归风险 (应为 0, 纯 docs 范畴)

## §6 派工 v10 错误 19 类 (本任务避坑)

- E01 漂移清单凑 / E02 类 20.6/13 漂移漏 / E03 §13 必填段漏
- E04 v11 → v11.1 升级建议缺 / E05 类 20.34 漏引用
- E06 0 production code 违规 / E07 alembic 多 head / E08 锚点范式缺失
- E09 push 失败 / E10 commit message 格式错
- E11 派工 brief 漂移 / E12 类 20 实战数对不上
- E13 docs runbook 漏 / E14 memory 沉淀漏 / E15 MEMORY.md 索引漏挂
- E16 派工 v11 模板未真查 / E17 W89 漂移缺据 / E18 实战收敛建议虚 / E19 主拍不可逆警告缺

## §7 5 件套守恒 + 锚点范式实测

| # | 件 | 实测 | 守恒 |
|---|------|------|------|
| 1 | alembic 1 head | `093_add_search_log_answer_rating` | ✅ |
| 2 | pytest collect | 沿用 W98 RAG-GC baseline | ✅ |
| 3 | PWA build | 沿用基线 (本任务 0 production code) | ✅ 据实 |
| 4 | 0 production code | `git diff main -- app/ web/src/ alembic/ \| wc -l` = 0 | ✅ |
| 5 | 锚点范式 | `git log --grep "W98 +" --oneline \| wc -l` = 55 commits | ✅ ≥ 13 预期 |

## §8 起步结论

- **派工 v10 起步纪律 6 项全执行**: ✅ S1-S6 已完成
- **W73 起步纪律 6 项复用**: ✅ S1-S6 严格对齐
- **派工 v11 段 10 仓库实情真查**: ✅ 5 件套实测
- **派工 brief 漂移双向禁令**: ✅ 类 20.6 / 20.13 重定义已识别 (建议新类 20.34)
- **0 production code 守恒**: ✅ 决定本任务纯 docs/memory 范畴
- **起点锚点范式**: W98 RAG-GC +12 (主仓) → 终点 N-4 +14 守恒预期 (本任务 1 commit 后)

## §9 阶段规划 (4 阶段)

### 阶段 1: 起步 + v11 §13 现状真查 (本文件)
- 已完成

### 阶段 2: W89 类 20.6/13 漂移沉淀
- 目标: 在派工 v11 沉淀中明示类 20.6/13 历史定义, 新派工 brief 漂移建议类 20.34

### 阶段 3: v11 §13 必填 6 段 + v11.1 升级建议
- 目标: 在派工 v11 模板中正式加 §13 "仓库实情真查 (6 段必填)"

### 阶段 4: docs + memory 沉淀 + 据实上报 + push origin
- docs: `docs/w98-n4-v11-section13-2026-08-01.md` (150 行+ runbook)
- memory: `memory/w98-n4-v11-section13-2026-08-01.md` (沉淀, 含类 20.34 实战)
- memory/MEMORY.md: 末尾追加 N-4 v11 §13 收敛段
- commit + push origin + 返回 18 项反馈
