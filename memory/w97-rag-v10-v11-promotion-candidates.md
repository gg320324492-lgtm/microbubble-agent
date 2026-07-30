# W97 RAG 大改造派工 v10 → v10.1 / v11 → v11.1 升级候选沉淀（2026-07-30）

> **任务**: 沉淀 RAG 大改造 10 PR + DERIVE 实战中暴露的 v10/v11 补丁候选
> **纪律**: E45 铁律 —— **不擅自升级为正文**，仅沉淀 candidates 待主拍签字逐项升级
> **来源**: 派工 brief + 11 PR full/closure memory + DERIVE-08/09/10/11/12/13/18/19 系列沉淀
> **位置**: `memory/w97-rag-v10-v11-promotion-candidates.md` —— 沉淀后由主拍决策升级为 `docs/w72-prompt-paradigm-v10.1.md` + `docs/w72-prompt-paradigm-v11.1.md`

---

## §1 v10 → v10.1 升级候选

### 候选 1.1: 件 4 双门控（件 4a + 件 4b）

**实战来源**: DERIVE-08 / DERIVE-09 / DERIVE-16 实战 4/4 PASS

| 子项 | 内容 | 实战次数 |
|------|------|----------|
| **件 4a 老核心 unchanged grep** | `git diff main -- app/services/{knowledge_service,hybrid_retriever,embedding_service,bm25_service,text_splitter,rag_evaluator}.py \| grep -cE "^[+-]def"` = 0 | 10 PR 全部通过（grep 全 0）|
| **件 4b 派工 brief 授权范围 grep** | `git diff main --stat` 仅含派工 brief 显式列出的文件路径（不在派工 brief 内的文件 0 改）| DERIVE-08/09/16 实战 4/4 PASS |

**晋升条件**: 主拍验证派工 brief 文件清单准确性 + 派生 1 条派生铁律（"件 4a 老核心 + 件 4b 派工 brief 授权范围" 双门控）

**沉淀铁律 (如升级)**:
- 件 4 双门控是派工 brief 与实测对账的物理保证
- 件 4a 必查 `^[+-]def ` 守恒（语义 def 级别，不被 import/comment 干扰）
- 件 4b 必查派工 brief 文件清单全 diff 守恒（无擅自扩/缩）

### 候选 1.2: 件 3 PWA 三档（frontend=是/否/子集）

**实战来源**: DERIVE-10 落地 + HOTFIX-01 PR5 Play 修复 + PR8 commit `f220c0cc6` frontend=否 O 改验证

| 子档 | 必查 | 实战次数 |
|------|------|----------|
| **frontend=是** | `cd web && npm run build` 必 PASS（无 roldown panic / import 错） | PR5 + HOTFIX-01 |
| **frontend=否** | `git diff --stat main -- web/` 应为空输出（无老路径 frontend 改动） | PR8 + 8 个 RAG backend-only PR |
| **frontend=子集** | 仅 `web/src/views/<特定>/` 子目录新增，`web/dist/` + `web/index.html` + `web/src/views/Desktop*/` 0 diff | N/A（RAG 系列无子集派工） |

**晋升条件**: 主拍签字 PR 系列"frontend 三档"标签必带 + 派生 1 条铁律（"件 3 PWA build 三档分类"）

**沉淀铁律 (如升级)**:
- 件 3 PWA build 必按 frontend 三档分流验证
- frontend=是 → 必 PASS（产线部署必通）
- frontend=否 → 必查 web/ 0 diff（确认派工严守"backend-only"）
- frontend=子集 → 必查子目录 diff（拒绝顺手改 desktop/mobile 共享组件）

---

## §2 v11 → v11.1 升级候选

### 候选 2.1: 段 9 锚点前缀规则（已实战 6 次）

**实战来源**: DERIVE-11 落地 + PR1/2/3/4/5/8 commit message 全 grep `[PR[0-9] W[8-9][0-9] +N]` 前缀一致

| 实战 commit | 前缀格式 | 守卫字段 |
|------------|---------|---------|
| `[PR1 W88 +0..+7]` | `[PR1 W88 +N]` 8 commits | N ∈ {0,1,2,3,4,5,6,7} |
| `[PR2 W88 +8..+21]` | `[PR2 W88 +N]` 14 commits | N ∈ {8,...,21} |
| `[PR3 W89 +0..+12]` + `[PR3 W89 +12..+15]` | `[PR3 W89 +N]` 14 commits（含 `#28` 据实）| N ∈ {0,...,15} |
| `[PR4 W90 +0..+14]` | `[PR4 W90 +N]` 15 commits | N ∈ {0,...,14} |
| `[PR5 W91 +0..+13]` | `[PR5 W91 +N]` 14 commits | N ∈ {0,...,13} |
| `[PR8 W94 +0..+20]` | `[PR8 W94 +N]` 17 commits | N ∈ {0,...,20} |
| `[grand-closure W97 +0]` | 本任务 +1 | N = 0 |

**晋升条件**: 主拍签字将"锚点前缀规则"从 v11 §10 提升为 v11 §9 段独立段（现 v11 §10 与派工纪要合并），派生 1 条铁律

**沉淀铁律 (如升级)**:
- 锚点前缀强制必带 `[<type> W<batch> +N]` 格式（type ∈ {PR, merge, HOTFIX, DERIVE, grand-closure}）
- 数字 N ∈ [0, batch_size] 与 commit 实际工作量对应，禁止凑数
- PR 跨批次（如 PR3 W89 +12..+15）必合并为单 commit 在合并时补 commit message grep 校对

### 候选 2.2: §13 仓库实情真查（DERIVE-18 + DERIVE-19 reconcile）

**实战来源**: DERIVE-18 + DERIVE-19 实战 + 派工 brief "类 20 累计 34 实例" 据实对账（实际 29 + 5 候选 = 34，brief 与实测一致）

| 子节 | 内容 | 实战 |
|------|------|------|
| §13.1 brief vs 实测对账 | 派工 brief 数字（baseline head / collected 数 / 锚点起点 / 文件行号）与实测不符时 4 处置 | DERIVE-19 reconcile 实战 |
| §13.2 派生铁律沉淀 | brief 数字与实测对账 → 派生 v11 段 10 新增 5/6 项 | DERIVE-13 + DERIVE-19 |
| §13.3 据实不擅自扩 | 派工 brief 列出文件清单外 0 改（件 4b 双门控） | DERIVE-08/09/16 |
| §13.4 据实不擅自缩 | 派工 brief 数字差值必报（不擅自改 brief baseline） | DERIVE-19 |
| §13.5 阻塞性错配立即报主拍 | "锚点被占用" 等阻塞错配必须立即回报主拍，禁止脑补继续 | W74 A-1 锚点错判 + W75 A-1 错派 |

**晋升条件**: 主拍拍板"§10 类 20 累计" 与 "§13 仓库实情真查" 合并为 v11 §10 子节 + 派生 1 条铁律

### 候选 2.3: §10 类 20 累计（已实战 19 实例）

**实战来源**: DERIVE-13 落地 + DERIVE-19 reconcile 校准

| 计数 | 来源 |
|------|------|
| 15 实例 | 历史 W72-W85 累计（见 plan §14 + MEMORY.md §9） |
| +14 实例 | W89-W96 RAG 系列（PR1-10 + DERIVE） |
| = 29 实例 | 实战沉淀（brief "34" = 29 + 5 候选 = 34 据实） |
| + 5 候选 | W96 类 20 候选 A/B/C + W94 类 20 #34-#36 |

**晋升条件**: 主拍拍板"§10 类 20 累计数" 修正为 "**29 实战 + 5 候选 = 34 doctrine**"（不模糊 34，而是拆明）

### 候选 2.4: CHECKLIST §F verify_*.sh fallback 条款

**实战来源**: DERIVE-12 落地（`scripts/rag/check_*.sh` 超时 fallback 实测命令）

| 子项 | 内容 | 实战 |
|------|------|------|
| §F.1 fallback 实测命令 | verify_*.sh 超时 2min 时 fallback 到 `importlib.import_module` 真测 | DERIVE-12 + PR8 §9 据实 |
| §F.2 等价验证替代 | 实测命令 + 实测命令含义等价于 verify_*.sh 完整断言 | DERIVE-12 |
| §F.3 fallback 报告必标 | fallback 触发时主拍必报"实测命令而非 verify_*.sh" | DERIVE-12 |

**晋升条件**: 主拍拍板 `docs/rag/CHECKLIST.md` §F 段独立化

---

## §3 综合候选清单（6 项）

| # | 候选 | 来源 | 实战次数 | 主拍优先级 |
|---|------|------|---------|----------|
| 1 | v10 件 4 双门控 | DERIVE-08/09/16 | 4/4 PASS | P1 (W98 派工落地) |
| 2 | v10 件 3 PWA 三档 | DERIVE-10 + HOTFIX-01 + PR8 | 3/3 | P1 (W98 派工落地) |
| 3 | v11 段 9 锚点前缀规则 | DERIVE-11 + 6 PR 实战 | 6/6 | P0 (已在 v11 §10，本任务提议升 §9 独立段) |
| 4 | v11 §13 仓库实情真查 | DERIVE-18 + DERIVE-19 reconcile | 2/2 | P1 (W98 派工落地为 §13 独立段) |
| 5 | v11 §10 类 20 累计 | DERIVE-13 + DERIVE-19 校准 | 5 候选 + 14 实例 | P1 (W98 派工落 "29 实战 + 5 候选 = 34") |
| 6 | v11 CHECKLIST §F fallback | DERIVE-12 落地 | 1 | P2 (W99 派工，scope 较窄) |

---

## §4 主拍签字决策表（待填）

| # | 候选 | 决策（升/不升/推迟）| 升哪个版本号 | 签字 |
|---|------|--------------------|-------------|------|
| 1 | v10 件 4 双门控 | _______ | v10.1 P1 | _______ |
| 2 | v10 件 3 PWA 三档 | _______ | v10.1 P1 | _______ |
| 3 | v11 段 9 锚点前缀规则 | _______ | v11 §9 升段 | _______ |
| 4 | v11 §13 仓库实情真查 | _______ | v11 §10 升级 | _______ |
| 5 | v11 §10 类 20 累计 | _______ | v11 §10 升段 | _______ |
| 6 | v11 CHECKLIST §F fallback | _______ | v11 §F 升段 | _______ |

---

## §5 据实上报（brief vs 实测）

1. **brief 派工的"v10.1/v11.1 升级在主拍签字后逐项升级为正文"含义**: 本任务严格执行此约束，仅沉淀 candidates，不擅自升级为正文。
2. **brief 派工的"v10 已落地 + v11 已落地"含义**: 实测确认：
   - `docs/w72-prompt-paradigm-v10-2026-07-27.md` 已存在 ✓
   - `docs/w72-prompt-paradigm-v11-2027-04.md` 已存在（PR10 W96 已落库）✓
   - **候选清单与 v10/v11 已有内容不重叠**：6 项候选均为新增子项（v10 件 4 双门控细分 / v10 件 3 PWA 三档 / v11 段 9 升段 / v11 §13 新段 / v11 §10 升段 / v11 §F 升级）

---

## §6 升级实施指南（主拍决策后）

### 6.1 v10.1 升级实施（候选 1 + 2 合并）

```bash
# 1. 备份 v10
cp docs/w72-prompt-paradigm-v10-2026-07-27.md docs/w72-prompt-paradigm-v10.1-2026-07-30.md

# 2. 新增 §13 件 4 双门控 (候选 1)
# 3. 新增 §14 件 3 PWA 三档 (候选 2)
# 4. 主拍签字后 commit:
git add docs/w72-prompt-paradigm-v10.1-2026-07-30.md
git commit -m "[grand-closure W97 +1] docs(prompt): v10.1 件 4 + 件 3 升级 (6 候选 2 升)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

### 6.2 v11.1 升级实施（候选 3 + 4 + 5 + 6 合并）

```bash
# 1. 备份 v11
cp docs/w72-prompt-paradigm-v11-2027-04.md docs/w72-prompt-paradigm-v11.1-2026-07-30.md

# 2. 升级段 9 锚点前缀规则 (候选 3)
# 3. 新增 §13 仓库实情真查 (候选 4)
# 4. §10 类 20 累计升段 (候选 5)
# 5. §F fallback 升级 (候选 6)
# 6. commit:
git add docs/w72-prompt-paradigm-v11.1-2026-07-30.md
git commit -m "[grand-closure W97 +1] docs(prompt): v11.1 4 项升级 (6 候选 4 升)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

### 6.3 升级后 commit 落档

升级后 2 commit 落档 → W97 +1 +1 (total +2 anchors: 478 → 480)。但本任务 5 件产出 commit 仅 +1（478），如主拍批准 4 候选升级，总锚点 478 + 2 (升级 +2 commits) + 1 (HOTFIX-01 merge) = 481。

---

## §7 沉淀总结

- 6 项候选沉淀完成
- 主拍决策表 §4 待签
- 升级实施指南 §6 准备就绪
- 不擅自升级为正文（E45 铁律守恒）
- 沉淀文件落 `memory/w97-rag-v10-v11-promotion-candidates.md`（80+ 行）

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
