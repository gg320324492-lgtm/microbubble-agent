# W68 第 5 批 hot-fix: drive_version_diff_service 缺 select import (2026-07-24)

> **锚点范式第 73 守恒** — W68 跨主题 grand closure 收官途中, 第 5 批 hot-fix 暴露派工范式漏洞: 跨会话 agent 用 mock 规避 import 缺失 + typing imports 检查未覆盖 service 文件. 1 行 fix + 3 个 import smoke 测试 + 4 条新铁律.

## 1. 背景

W68 第 4 批 (commit `243937b7f`) drive-v2-pr9-version-diff agent 派工后, 主指挥在第 5 批审查中通过 `python -c "from app.services.drive_version_diff_service import ..."` 验证发现 import 失败:

```
ImportError: cannot import name 'compare_versions'
```

主指挥诊断: 这是症状 (API 路由误以为模块导出 `compare_versions` 函数), 真根因是模块**根本无法 load** —— `drive_version_diff_service.py` L29 `from sqlalchemy import and_` 漏 `select`, L309 / L326 调用 `select(DriveFileVersion)` 时 `NameError: name 'select' is not defined` 阻止整个模块加载.

**根因链**:
1. W68 第 4 批 #7 desktop-version-diff agent 创建 `app/services/drive_version_diff_service.py` 时漏 import `select`
2. agent 端到端测试用 **mock** 规避 (`mock.patch("app.services.drive_version_diff_service.select")` 或类似), 模块看起来"能 import" 实则只在测试环境被魔改
3. `scripts/check_typing_imports.sh` 只查 `from typing import ...` 不查 service 文件本身的 sqlalchemy/其它三方 import
4. agent 派工 brief 没硬性要求 import smoke 步骤, agent 自觉度不够

## 2. 1 行 fix

文件 `app/services/drive_version_diff_service.py` L29:

```diff
-from sqlalchemy import and_
+from sqlalchemy import and_, select
```

修改前 commit hash: `e43cefc25` (W68 第 4 批 drive-v2-pr9-version-diff)
修改后 commit hash: 见本 memory 末尾

## 3. 验证 (3/3 PASS)

### 3.1 Python import smoke
```bash
$ python -c "from app.services.drive_version_diff_service import DriveVersionDiffService, DriveVersionDiffServiceError; print('OK')"
OK import - DriveVersionDiffService + Error loaded
```

### 3.2 AST parse
```bash
$ python -c "import ast; ast.parse(open('app/services/drive_version_diff_service.py', encoding='utf-8').read()); print('OK ast')"
OK ast
```

### 3.3 typing imports check
```bash
$ bash scripts/check_typing_imports.sh
扫描了 152 个文件
✅ 所有 typing 注解的 import 都齐全
```

### 3.4 新建测试 PASS
```bash
$ SKIP_DB_SETUP=1 python -m pytest tests/test_drive_v2_pr9_import_smoke.py -v
tests/test_drive_v2_pr9_import_smoke.py::test_smoke_01_module_importable PASSED [ 33%]
tests/test_drive_v2_pr9_import_smoke.py::test_smoke_02_drive_version_diff_service_class_importable PASSED [ 66%]
tests/test_drive_v2_pr9_import_smoke.py::test_smoke_03_drive_version_diff_service_error_class_importable PASSED [100%]
======================== 3 passed, 1 warning in 0.56s =========================
```

## 4. 4 条新铁律

### 铁律 1: Agent 派工必含 import smoke 步骤

任何新建 service 文件的派工 brief, **必须**显式包含以下 import smoke 验证 (放在 acceptance criteria):

```bash
python -c "from app.services.<name> import <主要符号>; print('OK import')"
python -c "from app.api.v1.<endpoint_module> import router; print('OK router')"
```

**Why**: 派工 brief 不含此步骤, agent 默认"端到端测试 PASS" = 一切 OK. 但 e2e 测试经常用 mock 覆盖, 真实模块加载链路 (含 sqlalchemy / pydantic / httpx / redis 等三方 import) 未跑过. 主指挥本地 PC 调试时 import 错才暴露.

**派工 brief 模板更新** (建议同步到 `.claude/templates/agent-brief.md`):
```
Acceptance Criteria (必跑):
- [ ] `python -c "from app.services.<name> import <主符号>"` → 期望 OK
- [ ] `python -c "from app.api.v1.<endpoint> import router"` → 期望 OK
- [ ] `python -c "import ast; ast.parse(open('app/services/<name>.py').read())"` → 期望 OK
- [ ] `bash scripts/check_typing_imports.sh` → 0 错误
- [ ] e2e pytest 真实链 (不依赖 mock 跳步骤)
```

### 铁律 2: typing imports 检查不够

CLAUDE.md 铁律 (方案 C 2026-06-14) 已有 `scripts/check_typing_imports.sh` 强制 `from typing import Dict/List/Optional` 等检查. 但**这个脚本只查 typing 模块, 不查 service 文件本身的三方 import** (sqlalchemy / pydantic / httpx / redis / celery 等).

**Why**: typing 漏 import 报 NameError, 三方库漏 import 报 NameError, 两者现象相同但脚本只覆盖前者. W68 第 5 批这次 select 漏 import 就是后者, 152 个文件 0 错也没查出.

**修法建议 (后续 PR)**:
- `scripts/check_typing_imports.sh` 加 `python -c "from app.services.<new_service> import *"` 步骤
- 或新建 `scripts/check_service_imports.sh` 单独跑 service 模块 import smoke
- 或 CI 必跑 `python -c "import app"` 一次性验证所有 service 文件可加载 (但耗时较长)

**当前 workaround**: agent 派工必含 import smoke 步骤 (铁律 1) 弥补.

### 铁律 3: 跨会话 agent 报告必须即时报主指挥

W68 第 4 批 #7 desktop-version-diff agent 在测试时遇到 module import 错, **用 mock 规避** (测试通过但模块不能真加载) 而未即时报告主指挥. 直到主指挥 W68 第 5 批审查时主动验证才暴露.

**Why**: mock 是测试工具, 不是生产代码 fix. 用 mock 规避 = 把 bug 推到下游. 跨会话 agent 没机会看自己 mock 出来的"绿", 因为绿的是测试不是产品.

**修法**: 任何 agent 在派工过程中遇到:
- 编译/import 失败 (NameError / ModuleNotFoundError / ImportError)
- 端到端测试用 mock 替代真实链
- 测试通过但 e2e curl 失败
- 文档说不清 / plan 漏场景

**必须立即停止 + 报告主指挥**, 不允许 mock 规避 + 继续推进. 主指挥判断是否拆 agent / 拆 scope / 换策略.

### 铁律 4: Python import 错误用最简 fix

遇到 `ImportError` / `NameError: name 'X' is not defined`, **缺什么 import 加什么**, 不重写文件 / 不换 import 风格 / 不重构. 1 行 fix 优于 50 行重构.

**Why**: W68 第 5 批这次如果主指挥不坚决走 1 行 fix, agent 可能"顺手重构" sqlalchemy import 块 (统一格式 / 加类型 / 删 unused). 重构引入 regression 风险 + 1 行 fix 5 秒可回滚 vs 50 行重构 5 分钟 review.

**派工 brief 模板纪律**: hot-fix 类派工, brief 必须明文写:
- "FIX ONLY, no refactor"
- "minimum diff, 1 commit"
- "如需重构, 单独派工, 不在本 hot-fix 范围"

## 5. 教训沉淀到派工范式

锚点范式 73 次守恒 (W68 第 5 批跨主题 grand closure 期间), 派工范式沉淀 4 条:

1. **派工 brief 必须含 import smoke acceptance criteria** — 不是建议, 是硬性.
2. **派工 brief 必须明文 "FIX ONLY, no refactor"** (hot-fix 场景).
3. **agent 遇 blocker 必须即时报** — 不允许 mock 规避 + 继续.
4. **typing imports 检查 + service import smoke 检查 = 互补** — 后者当前缺失, 派工 brief 补位.

## 6. 0 production code 改动铁律

**本次例外破例** (CLAUDE.md 第 5 批路线驱动批准 Drive v2 PR9 系列):
- `app/services/drive_version_diff_service.py` 1 行 import 修复 = 修 bug, 不是新功能
- 新建 `tests/test_drive_v2_pr9_import_smoke.py` = 测试新增, 不动生产代码
- 新建本 memory = 教训沉淀

CLAUDE.md 0 production code 改动铁律**维持**, 本次例外属第 5 批路线驱动 PR9 系列下批准范围.

## 7. 关键 commit / 文件路径

- 修改: `E:\microbubble-agent\app\services\drive_version_diff_service.py` L29
- 新建: `E:\microbubble-agent\tests\test_drive_v2_pr9_import_smoke.py`
- 新建: `E:\microbubble-agent\memory\w68-route-5-hotfix-version-diff-import-2026-07-24.md` (本文件)
- 分支: `fix/w68-5th-batch-version-diff-import-2026-07-24`
- 主指挥来 merge (本 agent 不 merge)

## 8. 时间线

- 2026-07-24 (W68 第 4 批): drive-v2-pr9-version-diff agent 创建 service 文件, 漏 `select` import
- 2026-07-24 (W68 第 4 批): agent 端到端测试用 mock 规避, 测试"通过"
- 2026-07-24 (W68 第 4 批): commit `e43cefc25` merge 进 main (`243937b7f`)
- 2026-07-24 (W68 第 5 批): 主指挥审查派工时 `python -c "from app.services.drive_version_diff_service import ..."` 验证发现 ImportError
- 2026-07-24 (W68 第 5 批): hot-fix 派工 (本 agent) — 1 行 fix + 3 个 import smoke + memory
- 锚点范式第 73 守恒

## 9. 关联引用

- [multi-agent-task-orchestration-baseline.md](multi-agent-task-orchestration-baseline.md) — 项目级协调范式锚点
- [w68-grand-closure-...md] (W68 grand closure 系列) — 锚点范式实战累计
- [w67-grand-closure-qa-bench-ci-final-2026-07-23.md](w67-grand-closure-qa-bench-ci-final-2026-07-23.md) — 上一次 grand closure 守恒
- [2026-07-23-six-batches-v2-21-paradigm.md](2026-07-23-six-batches-v2-21-paradigm.md) — 6 批范式总结, 派工 7 铁律

## hot-fix #17 _compute_text_diff lineterm 修复 (2026-07-24 跨会话报告)

### 根因与修复

跨会话 agent 报告 `DriveVersionDiffService._compute_text_diff()` 输出不是标准多行 unified diff；主指挥随后直接核对 `app/services/drive_version_diff_service.py` L227-L235，确认根因是 `difflib.unified_diff(..., lineterm="")` 与 `"".join(diff_lines)` 组合。`from_text` / `to_text` 的内容行虽然保留原换行，但 `---`、`+++`、`@@` 这些由 `difflib` 生成的控制行没有行终止符，最终形成 `--- v1+++ v2@@ ...` 紧凑字符串，无法被标准 line-oriented diff 消费者可靠解析。

采用 difflib 文档约定的最小修复：

```diff
-            lineterm="",
+            lineterm="\n",
```

保留 `"".join(diff_lines)` 不变。这样控制行与内容行均以 `\n` 分隔，输出恢复为：

```diff
--- v1
+++ v2
@@ -1,2 +1,2 @@
 hello
-world
+moon
```

**业务教训**：文本 diff 不仅要“包含变更内容”，还必须验证标准协议格式；否则 UI 看似拿到字符串，下载、解析、复制补丁等真实链路仍会失败。

### 跨会话协作流程

1. 跨会话 agent 只负责报告可复现症状、文件位置和证据，不把报告本身当结论。
2. 主指挥在 30 秒内用 grep + read 核对实现，确认根因后才派 hot-fix。
3. hot-fix agent 采用 1 行最小修复，同时用真实输入直接调用生产静态方法。
4. 增加 3 场景回归：紧凑/标准格式区分、多行真实 diff、identical/empty 边界；验证后提交并推送，不自行 merge。

### 新增铁律

- **L-1 跨会话 agent blocker 报告必须主指挥立刻核实**：跨 agent 报 backend bug，主指挥 30 秒内 grep + read 验证；不允许“信 agent 报告就派 hot-fix”。
- **L-2 hot-fix 派工必含真跑测试**：不允许只跑 mock 后 commit；必须用真实数据走一遍生产实现，失败即挂。
- **L-3 difflib unified_diff lineterm 必 `\n`**：在本项目 `splitlines(keepends=True)` + `"".join()` 组合中，`lineterm=""` 会把 `---` / `+++` / `@@` 控制行压成紧凑字符串，与标准 unified diff 不兼容；必须显式使用 `lineterm="\n"`。

### 0 production code 改动铁律例外

本次仅修改 `app/services/drive_version_diff_service.py` 1 行，是 W68 第 5 批路线驱动批准范围内的 bug fix，不是新功能；配套新增 `tests/test_drive_v2_pr9_unified_diff_format.py` 防止格式回归。
