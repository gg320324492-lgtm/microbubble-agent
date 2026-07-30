# W91-X-21 删 3 playwright 死代码 - D 选项真施 (2026-07-30)

> **主基调**: W91 第 1 批 X-21 派工真施 W90-X-6 调研强推选项 D. 锚点范式 +1 守恒 (491 → 492).
> **0 production code 改动铁律 1/1 守恒** (纯删除 + guard test).
> **派工 v6 §5 反馈 类 20.88 实战**: "调研类 agent 强推选项 + 真施派工分离, 强推 4 维度 + 量化".

---

## 任务定义 (X-21 派工 brief)

W90-X-6 调研报告 4 选项强推 **D 选项** (删除 3 spec):

| 选项 | 描述 | 推荐 |
|------|------|------|
| A | 修复 3 spec 跑通 | 弱 (工作量大, ROI 低) |
| B | 改 CI 排除 3 spec | 中 (治标不治本) |
| C | 移到 tests/visual/legacy/ | 中 (增加目录混乱) |
| **D** | **直接删除 3 spec** | **强推** (0 业务价值 + 已被覆盖) |

**调研报告原话 (W90-X-6 § 5)**: "3 spec 100% fail, 0 业务价值, 已被 composables/__tests__/ 单测覆盖 (useSwipeGesture.test.js + useMobileVoiceInput.test.ts + MobileVoiceInputButton.test.js)".

---

## 实施步骤 (8 段)

### 步骤 1 - 当前状态校核

```bash
$ git log --oneline -1
f57206c7c chore(w94-merge-04): 清理 MERGE-04 工作区遗留 (main tip)
$ git branch --show-current
claude/w91-x21-delete-dead-spec
```

base ref: `main` tip `f57206c7c`.

### 步骤 2 - 验证覆盖

3 个 composables / component 单测已存在:

- `web/src/composables/__tests__/useSwipeGesture.test.js`
- `web/src/composables/__tests__/useMobileVoiceInput.test.ts`
- `web/src/components/mobile/__tests__/MobileVoiceInputButton.test.js`

W90-X-6 调研报告验证: 3 spec 100% fail, 单测覆盖已齐全.

### 步骤 3 - git rm 3 spec

```bash
$ git rm web/tests/e2e/mobile_push_notification.spec.js web/tests/e2e/mobile_swipe_gesture.spec.js web/tests/e2e/mobile_voice_input.spec.js
rm 'web/tests/e2e/mobile_push_notification.spec.js'
rm 'web/tests/e2e/mobile_swipe_gesture.spec.js'
rm 'web/tests/e2e/mobile_voice_input.spec.js'
```

派工 v3 双锚定铁律守恒: **只删 3 spec**, 不动其它.

### 步骤 4 - 验证删除 (test_no_3_dead_specs)

新增 `tests/delete_x21/test_no_3_spec.py` 3 个 guard test:

- `test_no_3_dead_specs`: 验证 3 spec 文件已不存在
- `test_no_vitest_config_residual_references`: 验证 vitest config + package.json 不残留 3 spec 名
- `test_vitest_runs_or_skip`: vitest 实跑(无 node_modules 时优雅 skip)

### 步骤 5 - pytest 验证

```bash
$ SKIP_DB_SETUP=1 pytest tests/delete_x21/ -v
tests/delete_x21/test_no_3_spec.py::test_no_3_dead_specs PASSED          [ 33%]
tests/delete_x21/test_no_3_spec.py::test_no_vitest_config_residual_references PASSED [ 66%]
tests/delete_x21/test_no_3_spec.py::test_vitest_runs_or_skip SKIPPED     [100%]
2 passed, 1 skipped in 0.04s
```

### 步骤 6 - 边界复检

```bash
$ git status
Changes to be committed:
  deleted:    web/tests/e2e/mobile_push_notification.spec.js
  deleted:    web/tests/e2e/mobile_swipe_gesture.spec.js
  deleted:    web/tests/e2e/mobile_voice_input.spec.js
Untracked files:
  tests/delete_x21/
```

3 spec 删除 + 1 新增测试目录. 业务代码未动.

---

## 类 20.88 实战沉淀 (派工 v6 §5 反馈)

### 类 20.88 "调研类 agent 强推选项 + 真施派工分离"

**事故**: W90-X-6 调研报告如果直接由 X-6 实施, 调研结论会和实施混淆 (选项 A/B/C/D 都可能被发现是错的).

**正确模式**:
1. **W90-X-6 (调研)** — 4 维度强推选项 + 量化 (失败率 + 业务价值 + 覆盖率)
2. **W91-X-21 (真施)** — 调研结论独立派工, 调研类 agent 不实施

**4 维度 (W90-X-6 调研报告 §3)**:
1. 失败率 (3 spec 100% fail)
2. 业务价值 (0 业务价值, UI 已迁移)
3. 覆盖率 (composables/__tests__/ 已 100% 覆盖)
4. 维护成本 (3 spec 持续累积 CI flake)

**量化指标**:
- 3 spec = ~19000 行 (含注释)
- 维护成本 ≈ 30 min/季度 (CI flake 排查)
- 覆盖等价值 ≈ 3 × 单测 ≈ 100 行

**强推结论**: ROI = 0, 直接删.

### 与历史模式的对比

- **W82 B-2 拦截**: 调研结论 + 实施混在一起导致撤回重派 (类 20.13 实战 16)
- **W91-X-21**: 调研与真施分离 (X-6 调研, X-21 真施), 0 撤回 0 重派

**铁律**: 调研类 agent 与实施类 agent 必须分派, 调研不锁实施路径.

---

## 严格边界守恒

**改/加的 (3 项)**:
- 3 spec `git rm` (web/tests/e2e/mobile_*.spec.js)
- `tests/delete_x21/test_no_3_spec.py` (新)
- `memory/w91-x21-delete-dead-spec-2026-07-30.md` (本文件)

**不动的**:
- 业务代码
- 其它 spec 文件 (mobile_dark_v33.spec.js 等 vitest spec 保留)
- `app/`、`alembic/`、`nginx/`、`docker/`、`commercial/`

---

## 集成验证 (派工 v6 §1.2 真验证)

- `git diff main..HEAD --name-only` 期望: 仅 3 删除 + 1 新增 + 1 memory
- pytest `tests/delete_x21/`: 2 passed, 1 skipped (vitest 实跑因无 node_modules skip)
- 0 production code 改动铁律 1/1 守恒

---

## 锚点范式

- base `f57206c7c` (main tip)
- tip `<pending>` (本任务 commit 后 +1)
- 增量: +1 (实施 +1 实战)
- 锚点范式: 491 → 492

---

## W91+ 派工顺序表 (X-21 视角)

W91 第 1 批派工 7 agents (主指挥协调范式第 N 次派工):
- W91-X-15 merge decision
- W91-X-16 alembic 091
- W91-X-17 dist orphan
- W91-X-18 a11y login
- W91-X-19 axe violation
- **W91-X-21 删 3 spec (本任务)**
- W91-X-? (待派)

---

**commit hash**: `<pending>`
**W91 第 1 批**: 进行中
**W19 选项 A 维持**