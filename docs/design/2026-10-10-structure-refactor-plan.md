# 结构重构执行规划（2026-10-10）

> **状态**：待执行（每批完成后在本文件勾选 ✅ 并记录实测数字）
> **设计依据**：[`2026-10-10-target-structure.md`](2026-10-10-target-structure.md)（660 行）
> **测绘依据**：[`2026-10-10-structure-mapping.md`](../audit/2026-10-10-structure-mapping.md)（430 行）
> **核心原则**：**按"是否有活接线"分层，不按"用途"分层** —— 本项目 4617 commits，很多"分类不理想"的目录被生产接线撑着，动不了。

---

## 零、先看这三条硬约束（决定方案形状）

| # | 约束 | 证据 | 含义 |
|---|---|---|---|
| **H1** | **CI 动态分片** | `.github/workflows/server-tests-baseline.yml:107` = `find tests -name "test_*.py" \| awk 'NR%8'` | 改 `tests/` 子目录名**不会红**；但 3 处写死路径例外（见 §五） |
| **H2** | **`parents[2]` 反推根目录** | 33 个测试文件用了 `Path(__file__).parents[2]`（9 个真依赖 `web/src`、`alembic`、`package.json`） | **`tests/` 必须保持两层深度**：`tests/分类/文件.py`。实测 `tests/legacy/a11y_x/f.py` 的 `parents[2]` 变成 `tests/` → 33 文件全错位 |
| **H3** | **4 个开机自启计划任务 + compose 39 处 volume** | `backup_scheduler.bat:44`、`install-auto-recovery.bat:32`、`_register-task.ps1:8`、`start_gpu_asr_daemon.bat` | 这批脚本**原地冻结**，改名必须同步重注册任务 |

---

## 一、已完成的准备（阶段 0）

| # | 事项 | 状态 | 证据 |
|---|---|---|---|
| 0.1 | 全项目测绘 | ✅ | `docs/audit/2026-10-10-structure-mapping.md` |
| 0.2 | 目标结构设计 | ✅ | `docs/design/2026-10-10-target-structure.md` |
| 0.3 | 修 `restart_gpu_workers.bat` 死路径 | ✅ | commit `431ec7443`，旧路径 `.workbuddy\vibevoice-test` 不存在 |

### 决策点已裁定

| ID | 事项 | 裁定 | 依据 |
|---|---|---|---|
| **D1** | `config/intent_routing.yaml` | **删除** | 文件头自述"**本任务未接**"，是刻意留的 ops 参考文档；实际权重硬编码在 `app/rag/intent_router.py:42 DEFAULT_INTENT_WEIGHTS`。零代码/CI 引用 |
| **D2** | `desktop-conversion/` 合并主仓 | **调研中** | 独立 git 仓（193 commits + 私有远端），主仓已公开 → **必须先查子仓历史有无凭据泄露**，再定合并方案（submodule / subtree / 只搬文件）。产出见 `docs/audit/2026-10-10-desktop-conversion-merge-feasibility.md` |
| **D3** | `tests/eval/rag_prompt_meta.test.py` | **删除**（非修复） | 见下方专项 |

### D3 专项：这是"假绿"测试，删比修好

**实测三层失效**：

```
① pytest.ini: python_files = test_*.py  →  *.test.py 不匹配 → 收集 0 个
② 即使指定路径强制运行 → ModuleNotFoundError: No module named 'rag_prompt_meta'
   （点号文件名破坏 pytest 的 import 机制；作者留了注释
    "pytest file discovery compatibility for dotted test filename" 但未解决）
③ 直接 exec_module 跑通 3 个断言 → 全 PASS
```

**但 ③ 的"全 PASS"是假绿**：
```python
QUERIES = [f"微纳米气泡评估问题 {i}" for i in range(20)]
SAMPLES = ["结论如下。[1] 相关实验结果见文献。[2]"] * 20   # 硬编码常量 ×20
# 断言: "数据来源:" 出现在 SAMPLES 的比例 < 5%
```
**零个 `from app...` 导入** —— 它断言的是自己写死的字符串常量，**与真实系统无关**。即使改对 `python_files` 让它跑起来，也只是在验证 `"结论如下。[1]..."` 里没有"数据来源:"四个字。

**结论**：这是"看起来有回归测试、实际什么都没测"的典型（类 20.220 同族）。**改名救不了它，唯一有价值的处置是删除**，让后人重写真实的 prompt 回归测试。

---

## 二、执行批次总表

| 批 | 目标 | 风险 | 可否决 | 状态 |
|---|---|---|---|---|
| **1** | `tests/` 9 个 `_xNN` 归位 | 🟢 | 否 | ⬜ 待执行 |
| **2** | 3 处打平（消除唯一深度 3 违规） | 🟡 | 否 | ⬜ 待执行 |
| **3** | 删 D1 + D3 死文件 | 🟢 | 是 | ⬜ 待执行 |
| **4** | 修坏引用 + 2 份索引文档 | 🟢 | 否 | ⬜ 待执行 |
| **5** | 15 个 `aXX_*` 清理 | 🟡⚠️ | 否 | ⬜ 待执行 |
| **6** | 4 个边界目录补 README（R1-R4） | 🟢 | 是 | ⬜ 待执行 |
| **7** | `desktop-conversion/` 合并入主仓（方案 C） | 🟡 | 是 | ⬜ 待执行 |
| **8** | 全链路验收 | 🟢 | 否 | ⬜ 待执行 |

### 高风险批次翻案结论（主指挥 2026-10-12 裁定：选项 1）

原设计**刻意回避**的 4 项，深度调研（`docs/design/2026-10-12-high-risk-feasibility.md`）+ 主指挥复验后结论一致：**不是"不敢做"，而是"做了对结构没好处"**。

| 项 | 深度调研结论 | 复验证据 | 处置 |
|---|---|---|---|
| **R3** `tunnel/` vs `scripts/tunnel/` | **职责互补不是重复** | `tunnel/`=隧道本体（ps1/vbs/log/pid）；`scripts/tunnel/`=守护器（guard/install/uninstall）。一个建隧道，一个守隧道 | **两边各补 README**（批次 6），不合并 |
| **R4** `observability/` | **外部工具按约定消费的资产**，非孤儿 | 7 个 Grafana provisioning + 6 个查询 SQL；compose 零引用是因为 Grafana 容器按约定路径挂载 | **补 README**（批次 6） |
| **R1** `apps/` `web/` `packages/` | **pnpm workspace 约定** | `pnpm-workspace.yaml` 声明 `apps/*` + `packages/*`；`packages/` 仅 `design-tokens` 2 文件 | **原地不动**，补边界说明 |
| **R2** `commercial/` | **零 import，移动=纯 diff 无收益** | 7 处引用全是字符串路径/注释（`prefix="/commercial/billing"` / `__tablename__ = "commercial_plans"`），**零真 import** | **补 README**（批次 6） |

**为什么"补文档"才是这些项的"彻底"形态**：设计原则第 4 条明确"**不制造'为了分类而分类'**"。把零引用的 `commercial/` 从顶层搬到 `app/` 下，新结构并不更清晰——**只是换了个地方没人引用的目录**，只增加 diff 成本与将来 grep 时的困惑。

真正的收益是**让边界可被验证**：任何人（含未来 agent）看一眼就知道这些目录**为什么在顶层、职责是什么、为什么不能动**。这比搬动目录更能防止结构随规模增长而变乱。

### 批次 6 边界文档清单

| 目录 | README 要写清 |
|---|---|
| `tunnel/` | "隧道**本体**（启动/密钥/日志）；守护器在 `scripts/tunnel/`。勿合并——职责互补" |
| `scripts/tunnel/` | "隧道**守护器**（guard/install/uninstall）；本体在 `tunnel/`。被 `MicroBubble-SSH-Tunnel-Guard` 计划任务引用，**勿改名**" |
| `commercial/` | "商业化代码，与主仓**零 import** 是刻意设计；引用只是 URL 路径字符串。别试图接线或搬移" |
| `observability/` | "Grafana **按约定路径**消费（provisioning + queries）；compose 不挂载是正常的，不是孤儿" |
| `apps/desktop/` vs `desktop-conversion/` | 合并后的交叉引用表（解决"`git ls-files` 驱动的脚本会静默跳过独立子仓"） |

---

## 三、批次详情

### 批次 1：`tests/` 9 个会话编号目录归位 ⬜

**为什么第一批**：零编辑、零文档债、消灭 100% 会话命名债、做完立刻能验证。

**9 个源目录 → 目标**（保持两层深度，遵守 H2）：

| 源 | 目标 | 理由 |
|---|---|---|
| `tests/a11y_login_x18/` | `tests/a11y/` | 与 `a11y_violation_x2` 同主题合并 |
| `tests/a11y_violation_x2/` | `tests/a11y/` | 同上 |
| `tests/axe_violation_x19/` | `tests/a11y/` | 同属无障碍/axe 检查 |
| `tests/baseline_sync_x29/` | `tests/precommit/` | 基线同步属 pre-commit 语义 |
| `tests/brief_v41_x6/` | `tests/precommit/` | 文档存在性检查，pre-commit 类 |
| `tests/ci_real_x29/` | `tests/ci/` | CI 部署检查 |
| `tests/inject_auth_x4/` | `tests/security/` | 认证注入检查 |
| `tests/icon_wr1/` | `tests/visual/` | 图标检查，视觉类 |
| `tests/src_tests_x5/` | `tests/frontend/` | 前端源码检查 |

**⚠️ basename 冲突预警**：目标目录合并后可能出现同名 `test_*.py`。实测全库已有 1 组三重复 `test_intent_classifier.py`（靠 18 个 `__init__.py` 化解）。**合并前必须逐个查同名冲突**，冲突则加子目录或改名。

**验证**：
```bash
# 1. 收集数不变（最关键：证明没丢测试）
pytest tests/ --collect-only -q | tail -3      # 前后对比 collected 总数
# 2. CI 分片模拟
find tests -name "test_*.py" | wc -l            # 前后应完全相同
# 3. 会话命名清零
grep -rn "_x[0-9]\{1,3\}$" tests/ --include="*.py" | wc -l   # 期望 0
# 4. parents[2] 语义不变（抽查 9 个被合并的文件）
```

**回滚**：`git revert <commit>`

**风险**：🟢 低。H1 保证 CI 不受影响；H2 保证 `parents[2]` 不受影响。

---

### 批次 2：3 处打平 ⬜

消除唯一违反两层深度的地方。详见设计文档 §批次2。

**验证**：逐目录跑 pytest + `parents[2]` 语义检查

---

### 批次 3：删 D1 + D3 死文件 ⬜（可否决）

| 删除项 | 依据 |
|---|---|
| `config/intent_routing.yaml` | 文件头自述"本任务未接"，零引用，实际权重硬编码在代码里 |
| `tests/eval/rag_prompt_meta.test.py` | 三层失效 + 断言硬编码常量的假绿测试 |

**连带**：`config/` 目录删空后是否一并删除？→ 若删则 `docs/rag/W100-RAG-3-intent.md:24` 的引用需同步修改

**验证**：`grep -rn "intent_routing" --include="*.py" --include="*.yml"` → 期望仅剩历史文档

---

### 批次 4：修坏引用 + 索引文档 ⬜

| 坏引用 | 状态 |
|---|---|
| `scripts/register_avatar_defenses.ps1:36` → 不存在的 `check_orphan_avatars.py` | ⬜ 待处理 |
| `data/vibevoice-test/*.py` 5 个脚本仍指旧路径 | ⬜ 待处理（gitignore，不影响重构） |

**索引文档**：`docs/README.md` + `CLAUDE.md` 的路径表需同步。

---

### 批次 5：15 个 `aXX_*` 脚本清理 ⚠️ 最高风险

**这是唯一移动"活链路"文件的批次**：`a46_pptx_page_pipeline.py` 是 CLAUDE.md 记载的已投喂链路执行体，README:238 正教用户调用。

**且这 15 个脚本零 CI 引用 = 零回归网** —— 移错不会变红，只在下次人工使用时炸（静默失败）。

**必须拆两堆**：
- **活链路** → `scripts/ppt_pages/`
- **探针/临时** → `scripts/_archive/`

---

### 批次 7：`desktop-conversion/` 合并入主仓（方案 C）⬜（可否决）

**主指挥 2026-10-12 已裁定 5 项**：

| # | 事项 | 裁定 |
|---|---|---|
| 1 | 丢失 193 commits 明细 | ✅ **接受**（文档仓，历史结论已沉淀） |
| 2 | 私有远端处置 | ✅ **留作归档不删**（实测在用：所有 commit 已同步，且有 5 个 untracked 在途工作目录） |
| 3 | `ci-workflow.test.ts:82` forbidden 断言 | ✅ **删** |
| 4 | 子仓 README | ✅ **合并展示**（与主仓 README 同名冲突） |
| 5 | 4 条 gitleaks allowlist | ✅ **采纳**（先补 allowlist 再合并） |

**子仓画像**（主指挥复验）：**193 commits / 168 文件**（124 个 `.md` / 16 png / 13 json / 7 mjs），**零 Python**，时间跨度仅 24 天（2026-09-16 → 10-09）。

**凭据风险：低**。193 commits 全历史扫私钥 / `sk-` / `ghp_` / `AKIA` / `xox` → **零命中**；gitleaks 报 4 条 `generic-api-key` 均为一次性测试 fixture（3 个临时探针账号 + 1 个已撤销 token）。

**重叠**：仅 2 处同名（`README.md` / `.gitignore`），语义不同；其余全在 `docs/` 下零重叠。主仓 **21 个文件**引用 `desktop-conversion/` 路径 —— 合并后**自动从悬空变仓内路径**（额外收益）。

**执行步骤**：
1. 先补 4 条 gitleaks allowlist（否则合并后 secret-scan 阻断 pre-commit）
2. `git checkout main` → 复制子仓工作树（含 5 个 untracked）到主仓
3. 删 `apps/desktop/tests/unit/ci-workflow.test.ts:82` 的 forbidden 断言
4. 子仓 README 内容并入主仓对应文档
5. 一次 commit 提交
6. **私有远端保持不动**

**验证**：`gitleaks detect` 零阻塞 + 主仓 CI 8 片全绿 + 抽查 3 处 `desktop-conversion/` 路径引用是否变成仓内相对路径

**风险**：🟡 中。唯一实质代价是丢失 193 commits 明细（已接受）。

**依据**：`docs/audit/2026-10-10-desktop-conversion-merge-feasibility.md`

---

### 批次 8：全链路验收 ⬜

8 项清单：CI 绿灯 / 全量 pytest 收集数不变 / 生产路径 curl / compose 完整 / 计划任务仍触发 / 死路径清零 / 文档引用同步 / 新目录可预测性。

---

## 四、执行原则（主指挥纪律）

1. **一批一验证**：每批做完立刻跑该批验证命令，确认通过再进下一批。**不许攒着一起验**。
2. **每批一个 commit**：便于 `git revert` 精确回滚。
3. **不碰生产接线**：H3 列的 4 个计划任务脚本全程冻结。
4. **不在部署时改路径**：路径改完要重启容器才生效的，分开做。
5. **CI 绿灯为准**：每批推送后必须确认 `server-tests-baseline.yml` 8 片全绿。

---

## 五、CI 写死路径例外（改这些必红）

| 路径 | 写死位置 |
|---|---|
| `tests/rag_framework/` | `.github/workflows/rag-framework-ci.yml:120` |
| `tests/visual/` | `.github/workflows/playwright.yml`（3 处） |
| `tests/qa-bench/` | smoke（5 处 wd）+ baseline（3 处） |

**守门测试**：`("e2e", "test_anchor_scripts_smoke.py")` 用 `rel.parts` 匹配 ALLOWLIST —— **移动该文件会让守门测试把合法例外判成违规**。已列禁动区。

---

## 六、进度记录（执行时填写）

| 批次 | 执行日期 | commit | 验证结果 | 备注 |
|---|---|---|---|---|
| 1 | 2026-10-10 | `d209683d0` | 收集数 400→400 / 9 目录全 R 重命名 / ARCHIVED.md DANGLING 0 | ✅ |
| 2 | 2026-10-10 | `358862c4a` | 深度 3 违规 7→5（论证后保留 5 个：qa-bench 冻结 / e2e×rag 交叉） | ✅ |
| 3 | 2026-10-10 | `358862c4a` | 收集数 400→400 / 活引用清零 | ✅ |
| 4 | 2026-10-10 | `96aa77b6b` | 死引用 3 类清理 / 3 份索引文档同步（CLAUDE.md 补 400 文件 4133 函数 + 复现命令） | ✅ |
| 5 | 2026-10-10 | `02d929406` + `47b99df8f` | 顶层 aXX_ 15→0 / ppt_pages 5 + _archive 10 / 15 全 R / 旧路径悬空 0 | ✅ |
| 6 | 2026-10-10 | `9f9d485a6` | 5 份边界 README（4 新建 + 1 扩充 52 行零删除） | ✅ |
| 7 | 2026-10-11 | `ba7b3a429` | 176 文件 / **gitlink 0** / 子仓 .git 备份为 .git.subrepo-backup / gitleaks 命中 0 | ✅ |
| 8 | 2026-10-11 | 见下 | 10 项验收全过（见 §八） | ✅ |

### 批次 5 的一个教训（已修）

首次提交只入库了新位置的文件，**漏了 15 条旧路径删除记录** —— 因 `scripts/_archive/` 被
`.gitignore:170` 忽略，`git add scripts/_archive/` 未把对应的删除一并 stage，
导致 **git 索引里同时存在新旧两个路径**。复验时发现，补 `47b99df8f` 修正。

> **纪律**：往被 gitignore 的目录里做移动时，`git add <新目录>` **不会**带上
> 旧路径的删除。必须 `git add -A <父目录>` 或逐个 `git rm` 旧路径，
> 提交前用 `git ls-files | grep <旧路径模式>` 确认索引已清零。

### 批次 7 的三个关键处置

1. **`.git` 必须移走**：git 见到含 `.git` 的目录会当 nested repo 并 stage 成
   **gitlink（mode 160000）**而非文件。子仓 `.git` 已**重命名**为
   `.git.subrepo-backup`（**备份非删除**，回滚只需 `mv`）。实测 gitlink = 0。
2. **gitleaks 用文件级不用目录级**：目录级经 canary 实测会**静默放行**
   （在 `assets/` 内种同形状假密钥 → 不报警；放目录外 → 报警）。改为
   4 条 `$` 锚定精确路径，canary 复测确认目录内新文件**仍被拦**。
3. **保留 `desktop-conversion/` 目录而非合进 `docs/`**：后者会产生
   `docs/desktop-conversion/docs/...` 并打断 22 处现有引用。

---

## 七、P0：CI 长期全红（2026-10-12 插队，优先于批次 5/7）

### 7.1 审计发现的三条硬事实

审计报告：`docs/audit/2026-10-12-workflow-audit.md`

| # | 事实 | 证据 |
|---|---|---|
| **F1** | **`main` 分支完全没有保护** | `gh api branches/main/protection` → **404 Branch not protected**；`rulesets` → **`[]`**。**无任何 required check** |
| **F2** | **`server-tests-baseline` 连续 9+ 次全红**（10-09 至 10-10 从未转绿） | `gh run list --workflow=server-tests-baseline.yml`：10-10 三次、10-09 至少六次，全部 `failure`。CLAUDE.md「829 红灯收敛归零 / 2926 passed」**已失真** |
| **F3** | **唯一真硬门长期全红 = 门禁形同虚设** | `server-tests-baseline.yml:15-18` 注释白纸黑字写"任一片失败即红，**阻塞合并**"，但 F1 证明**红叉不挡任何 push** |

**F1 + F3 合起来是类 20.220 的教科书案例**：注释宣称"阻塞合并"、配置摘掉了 `continue-on-error` 看起来像硬门，**实际从未阻塞过任何东西**。

### 7.2 根因（已实测取证）

```
requirements.txt:66   numpy==1.26.2            ← 项目写死
pyarrow                ← 传递依赖，requirements.txt 根本没声明，要求 numpy >= 2.0
  ↓ 版本冲突
app.services.embedding_service import 失败
  ↓
"module 'app.services' has no attribute 'embedding_service'"
  ↓
连锁打挂 test_recall_fallback / test_rag_query_cache_e2e /
       test_wp3_resync_indexes / test_embedding_timeout_cancel
```

**CI 装依赖是纯 `pip install -r requirements.txt`（`server-tests-baseline.yml:88`），不约束传递依赖版本** ⇒ 冲突长期存在。

**⚠️ 该错误非 2026-10-10 改动引入**：`gh run view 37903655731`（**10-09** 的 run）`--log-failed | grep -icE "pyarrow|numpy"` = **137 处命中**，早于当日全部改动。10-10 的 embedding executor 改动只是让 `embedding_service` 被更多测试 import，从而**暴露**了既存冲突。**不需回滚 10-10 的改动**。

### 7.3 修法（主指挥倾向方案 A）

| 方案 | 内容 | 判定 |
|---|---|---|
| **A** | 让 `pyarrow` 不进 `embedding_service` 的 import 链（惰性 import / try-except 降级） | ✅ **采纳** —— `embedding_service` 是纯向量计算模块，不该因可选 DataFrame 库版本冲突而整体 import 失败 |
| B | 升级 numpy 到 2.x | ❌ numpy 2.0 有 ABI 破坏，scipy/sklearn/pandas 全需跟进，连锁风险远大于收益 |
| C | 显式钉住兼容的 pyarrow 版本 | 备选，若 A 不可行 |

### 7.4 执行顺序（**顺序错会锁死**）

```
① 修 CI 红灯 ──► ② 确认连续 N 次全绿 ──► ③ 给 main 开分支保护
```

**⚠️ 绝对不能先开保护再修红灯** —— 那样每次 push 都被挡住，寸步难行。

**主指挥 2026-10-12 明确裁定：全绿之后再开分支保护。**

### 7.5 workflow 判定分布

| 判定 | 数量 | 明细 |
|---|---|---|
| 保留 | 5 | `secret-scan` / `desktop-release` / `lint-css` / `build-image` / `playwright` |
| 可疑 | 5 | `upload-download-page` / `server-tests-baseline` / `qa-bench-baseline` / `rag-framework-ci` / `qa-bench-smoke` |
| 建议删 | 1 | **`image-scan`** —— 连续 5 周定时全红 + 5 次手动全红，每次烧 8-120 分钟 Actions 额度，**硬路径从未绿过** |

**唯一的真重复**：`rag-framework-ci` 的 pytest 段已被全量 400 文件扫描覆盖，但它**独占 alembic 单 head 守卫** ⇒ 建议**只删 pytest 段、留守卫**。

**职责正交不该合**：`build-image`/`image-scan` = 制品生产 vs 审计；`qa-bench-smoke`/`qa-bench-baseline` = 端到端探针 vs 离线守恒。

**CI 修复结果**：`35ab14c9e` 一次推送即转绿（**8 片全 ✓ / 4150 用例通过**，耗时 13m45s）。连续 9+ 次全红终结。

---

## 八、批次 8 全链路验收（2026-10-11，10 项全过）

| # | 验收项 | 判据 | 结果 |
|---|---|---|---|
| 1 | **测试收集数** | `find tests -name "test_*.py" -not -path "*__pycache__*"` | ✅ **400**，与重构前基准完全一致（一批测试都没丢） |
| 2 | **会话编号清零** | `git ls-files` 匹配 `^scripts/a[0-9][0-9]_` | ✅ **0** |
| 3 | **死路径清零** | `git grep` 代码类文件（`.py/.bat/.ps1/.sh`） | ✅ 无命中（仅存迁移史注释，豁免） |
| 4 | **gitlink 污染** | `git ls-files -s \| awk '$1=="160000"'` | ✅ **0** |
| 5 | **ARCHIVED.md 悬空** | 87 条登记路径逐个 `-f` 存在性检查 | ✅ **0 DANGLING** |
| 6 | **旧路径引用** | 全仓 grep 排除 `docs/audit` `docs/design` | ✅ 活引用 0；4 处命中**全是历史点时记录**（`CHANGELOG.md` "X-29 ci real" / `CLAUDE-history.md` / `memory/w91-*.md` §4 守卫 e2e），按档案铁律**保持原样** |
| 7 | **生产链路**（类 20.213） | `curl https://agent.mnb-lab.cn/health` + 首页 | ✅ **200 / 200**（打生产域名，非本机端口） |
| 8 | **容器健康** | `docker ps` app + nginx | ✅ 全 healthy |
| 9 | **计划任务指向的文件**（H3 冻结区） | 6 个被 `schtasks` 引用的脚本逐个存在性检查 | ✅ **6/6 全在位** |
| 10 | **gitleaks** | `gitleaks detect --config .gitleaks.toml` | ✅ **desktop-conversion 命中 0**（743 条是既存 bench 数据里的 embedding 向量误判，`tests/` 365 + `results/` 336，早于本次变更；CI 只扫 PR commit 区间故仍绿） |

**第 1 项与第 9 项是本轮最重要的两条**：前者证明 11 个批次、上百次移动/重命名**零丢失**；
后者是类 20.212 的核心防线（看着像普通脚本、实为生产接线）。

---

## 九、收口结论

### 9.1 完成了什么

| 类别 | 内容 |
|---|---|
| **测绘** | 顶层 53 项 / tests 33 子目录 / scripts 247 文件 / 高危引用图（`docs/audit/2026-10-10-structure-mapping.md`） |
| **设计** | 目标结构 + 7 批方案（`docs/design/2026-10-10-target-structure.md`） |
| **执行** | **8 个批次全部完成**，11 个 commit |
| **CI** | 连续 9+ 次全红 → **一次修复转绿**（`35ab14c9e`），并另存 workflow 审计报告 |
| **验收** | 10 项全过，测试收集数 400 一路未变 |

### 9.2 高风险项的最终处理（与初始"回避"相反）

| 项 | 初始评级 | 最终处理 |
|---|---|---|
| `tests/` 9 个会话目录 | 🟢 | ✅ 真归位（消灭 100% 命名债） |
| `tests/api/v1/` | 🟡 | ✅ 打平（论证：测试树无 v1 轴，44 个同族文件平铺在根） |
| 15 个 `aXX_*` 脚本 | 🔴 最高风险 | ✅ 拆两堆（活链路 `ppt_pages/` / 探针 `_archive/`） |
| `desktop-conversion/` | 🟡 不可逆 | ✅ 方案 C 合并，**gitlink 0**，文件级 allowlist |
| `commercial/` `observability/` `tunnel/` `apps+packages` | 🔴 刻意回避 | ✅ **转为边界 README**（主指挥裁定选项 1）—— 深度调研证明"做了对结构没好处"，补文档让边界**可被验证**比搬目录更能防将来变乱 |
| CI 长期全红 | — | ✅ 4 类根因定位并修复 |

### 9.3 沉淀的新纪律

1. **`tests/` 必须两层深度** —— 33 个测试用 `parents[2]` 反推仓库根，加层即全错位。
   实测 `tests/legacy/a11y_login/f.py` 的 `parents[2]` 变成 `tests/` 而非仓库根。
2. **往被 gitignore 的目录做移动，`git add <新目录>` 不会带上旧路径的删除** ——
   必须在提交前用 `git ls-files | grep <旧路径>` 确认索引清零。
3. **gitleaks allowlist 作用域应恰好等于已知误报集合** —— 目录级是刀切（canary 实测
   会静默放行同形状密钥）；文件级 `$` 锚定才能既豁免已知误报又不给未来留免检区。
4. **含 `.git` 的目录并入主仓会被 stage 成 gitlink** —— 必须先移走或重命名 `.git`。
5. **"注释宣称阻塞合并"≠ 真的阻塞** —— `server-tests-baseline.yml` 注释写"任一片失败即
   阻塞合并"，实际 `main` 分支**零保护、无 required check**，红叉从未挡过任何 push
   （类 20.220 的教科书案例，见 §七 F1+F3）。

### 9.4 尚未做（明确留给下一阶段）

| 项 | 原因 |
|---|---|
| **开 `main` 分支保护** | 主指挥裁定**全绿后再开**。当前 1/3 绿，巡检累计中。⚠️ 本仓是**直推 main** 工作流，开 required checks 会挡住直推，需同步决定是否改走 PR |
| 删 `image-scan` workflow | 审计建议（5 周定时全红 + 5 次手动全红，硬路径从未绿过）。**待 CI 稳定后处理** |
| `rag-framework-ci` 删 pytest 段 | 该段已被全量扫描覆盖，但**独占 alembic 单 head 守卫**只能删段不能删文件 |
| `upload-download-page` 根因 | 唯一那次运行即红，日志已过 90 天保留期，**根因无法取证** |
| `datasets` 钉版本 | 现只钉了 `pyarrow`。`datasets` 仍是裸声明，下次它升级可能再触发同类冲突 |
| 全历史 743 条 gitleaks | 既存（bench 数据里的 embedding 向量误判），CI 只扫 PR 区间故不阻塞。清理需人工甄别是否误伤 |