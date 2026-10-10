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
| **D2** | `desktop-conversion/` 合并主仓 | **调研中** | 独立 git 仓（193 commits + 私有远端），主仓已公开 → 先查凭据泄露再定 |
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
| **6** | `observability/` → `docker/` | 🟢 | 是 | ⬜ 待执行 |
| **7** | 全链路验收 | 🟢 | 否 | ⬜ 待执行 |

**刻意不存在的高风险批次**：`web/` `apps/` `tunnel/` 合并 `commercial/` 归位 —— 受类 20.133 构建确定性约束，收益小风险大，留给未来专门立项。

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

### 批次 6：`observability/` → `docker/` ⬜（可否决）

零风险但收益也低。

---

### 批次 7：全链路验收 ⬜

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