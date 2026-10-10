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
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |
| 6 | | | | |
| 7 | | | | |
| 8 | | | | |