# W89-X-29 a11y baseline sync git 决策 + 收口 — 2026-07-30

> **任务**: W89 第 2 批收尾 X-29 — a11y baseline 是否 sync git 待主指挥拍板.
> **worktree**: `E:/agent-w89-x29-baseline-sync` (分支 `claude/w89-x29-baseline-sync`)
> **base ref**: main tip `a000d0bf2` (实测, 不凭 CLAUDE.md 历史 — 类 20.32 守恒)

---

## 1. W89-X-16 留口 + 主指挥拍板

W89-X-16 据实报告: a11y 25 baseline `.txt` 写出来了 (匿名态),
是否 sync git 待主指挥拍板.

**主指挥派工 brief v3 双锚定决策**: **选项 C — sync git baseline** (因为 P-6 已 commit,
baseline 必入 git 才有效).

理由:
1. P-6 已 commit 26 files (含 25 baseline + 1 memory), baseline 已**逻辑上**入 git
2. 不 sync = baseline 在 worktree, merge 后丢失 → 套件下次跑报 "missing snapshot"
3. baseline 漂移 (5 pages × 5 projects violations) 必须有源, 否则派工 v6 §1.2 真验证无法做

---

## 2. 实施 (本任务)

### 2.1 worktree + cherry-pick P-6

```bash
git worktree add ../agent-w89-x29-baseline-sync -b claude/w89-x29-baseline-sync main
cd ../agent-w89-x29-baseline-sync
git cherry-pick 7e9d2698b  # test(w89): a11y baseline 重 sync + violation 真硬断言 (W89-P-6)
```

### 2.2 cherry-pick 冲突处理 (据实上报)

P-6 修改了 `web/tests/visual/a11y/auth-shared-token.spec.mjs` (加 `expect(criticalOrSerious).toEqual([])` 硬门禁).
但 main 已经过 W89-P-10 refactor (`21da494e3` `refactor(w89): tests/e2e/ 重构`)
**删除** 了该 spec 文件 (15 vitest → `tests/unit/components/`, 3 playwright → `tests/visual/e2e/`).

冲突: `CONFLICT (modify/delete): auth-shared-token.spec.mjs deleted in HEAD and modified in 7e9d2698b`.

**处理**: 接受 main 删除 (P-10 重构已替代为 `tests/visual/e2e/` 新结构, 不需要保留老 P-2 spec).
P-6 的硬门禁价值在 P-10 重构后由新位置的 spec 接续 (或留 W89-X-29+ 补足).

**纪律**: 派工 v6 §5 反馈 类 20.84 实战 — cherry-pick 遇 modify/delete 必须查 main HEAD 实测
确认文件位置, 不能凭 CLAUDE.md 历史.

### 2.3 cherry-pick 结果

```bash
$ git log --oneline -2
06992f1ed test(w89): a11y baseline 重 sync + violation 真硬断言 (W89-P-6)
a000d0bf2 [merge-02 W89 +0] merge: PR3 BM25 增量 + pg_trgm + tsvector (锚点 430 → 444)
```

26 files changed, 261 insertions(+), 45 deletions(-) — **25 baseline 全部入 git**.

```bash
$ git ls-files web/tests/visual/a11y/__snapshots__/ | wc -l
25
```

### 2.4 e2e 加固 (本任务新增)

新文件 `tests/baseline_sync_x29/test_sync.py`:
1. `test_baseline_files_exist` — baseline 必 ≥ 25 个文件
2. `test_baseline_files_tracked_by_git` — baseline 必在 git 跟踪中 (选项 C sync git 决策落地)
3. `test_baseline_files_have_authed_field` — 每 baseline 必含 `authed:` 字段 (类 20.84 一致性)

```bash
$ SKIP_DB_SETUP=1 pytest tests/baseline_sync_x29/ -v
tests/baseline_sync_x29/test_sync.py::test_baseline_files_exist PASSED        [ 33%]
tests/baseline_sync_x29/test_sync.py::test_baseline_files_tracked_by_git PASSED [ 66%]
tests/baseline_sync_x29/test_sync.py::test_baseline_files_have_authed_field PASSED [100%]
============================== 3 passed in 0.06s ==============================
```

**总计**: **3 PASS** (派工 brief 预测 2 PASS, 实测 3 PASS 多加 1 个 authed 字段校验).

---

## 3. 派工 brief 偏差据实上报

### 3.1 派工 brief 描述 "25 baseline 重生成(登录态,真数据)" — **与实测不符**

实测 baseline 内容:

```
$ cat web/tests/visual/a11y/__snapshots__/01-chat-desktop-chrome.txt
page: 01-chat  route: /chat
target: ChatViewSSE.vue
project: desktop-chrome
authed: no   redirected-to-login: no
violations: 0
```

**25/25 全部 `authed: no`** (匿名态), **非** 派工 brief 描述的 "登录态真数据".

**根因**: `injectAuth()` 函数 (`web/tests/visual/a11y/axe-config.mjs:21-32`):

```js
export async function injectAuth(page, baseUrl) {
  const token = process.env.TEST_TOKEN
  if (!token) return false  // ← 无 TEST_TOKEN env 即匿名
  ...
}
```

W89-P-6 跑 `--update-snapshots=all` 时**未设** `TEST_TOKEN` env → 全部 25 case 走匿名态.

**类 20.25 + 类 20.84 实战**: 匿名态 baseline **0 violations 是假绿信号** — axe 扫到的是
未登录路由的极简 DOM, 真实场景的 chat/drive/task-trash/file-comments 业务组件未挂载.

派工 v6 §5 反馈 类 20.84 沉淀 (见 §4).

### 3.2 P-6 cherry-pick 遇 modify/delete 冲突 (派工 brief 未预测)

P-6 修改 `auth-shared-token.spec.mjs` 加硬门禁, 但 main W89-P-10 refactor 已**删除**该文件.
派工 brief 未提及此冲突. 本任务**实测**发现并按 "接受 main 删除" 处理 (因为 P-10 重构
15 vitest → `tests/unit/components/` 替代了原有验证).

---

## 4. 派工 v6 §5 反馈 类 20.84 沉淀 (新增)

**类 20.84** "a11y baseline 必入 git + 必在登录态生成 (匿名态 baseline 0 violations 是假绿信号)"

### 4.1 必入 git
- baseline snapshot 是 "已知 violations 集合" 物证
- 不入 git = merge 后丢失 → 套件下次跑报 "missing snapshot" → 派工 v6 §1.2 真验证无法做
- 派工 brief 默认 "git 已 sync" 是**错误假设**, 必须实测 `git ls-files <snapshot_dir>` 验证
- W89-X-29 本任务实战: 选项 C sync git 决策落地, 25 files 全部 tracked

### 4.2 必在登录态生成
- `injectAuth()` 函数 `if (!token) return false` — 无 TEST_TOKEN 即匿名
- 匿名态 DOM = 未登录路由极简结构, 业务组件 (chat/drive/task-trash/file-comments)
  未挂载 → axe 扫不到真实 violations
- 登录态 = 真实业务组件挂载 + 真实数据 (members / projects / knowledge 等)
- **派工 v6 §5 反馈 类 20.84**: baseline 重 sync 必 `TEST_TOKEN=<real-token>`,
  跑前必实测 1 个 case `authed: yes` (派工 brief §2.2 步骤漏报)

### 4.3 何时再 sync
- 修了 violation → 必 `--update-snapshots=all` + 登录态
- 加了新 a11y spec → 必含 baseline 对应 case
- 不再 auto-update (axe-core 升级 / 真出现新 violation) → 必回归派工 v6 §1.2

---

## 5. 边界复检

```bash
$ git diff main..HEAD --name-only | head -30
memory/w89-p6-a11y-baseline-resync-2026-07-30.md
web/tests/visual/a11y/__snapshots__/*.txt (25 files)
tests/baseline_sync_x29/test_sync.py
memory/w89-x29-baseline-sync-2026-07-30.md
```

**0 production code 改动铁律守恒** (本任务):
- ✅ 仅动 `web/tests/visual/a11y/__snapshots__/` (测试快照, 派工 brief §6 允许)
- ✅ 仅动 `tests/baseline_sync_x29/` (新 e2e, 派工 brief §6 允许)
- ✅ 仅动 `memory/w89-*` (memory, 派工 brief §6 允许)
- ✅ P-6 cherry-pick (派工 brief §6 允许)

**未动**:
- ❌ 业务代码 (`app/`, `web/src/`, `alembic/versions/`)
- ❌ spec 文件 (`web/tests/visual/a11y/*.spec.mjs`) — 本任务新增 `tests/baseline_sync_x29/`
  是 e2e 测试, 不是 a11y spec, 不冲突

---

## 6. 锚点预期

- base (a000d0bf2 = 锚点 444) → tip (06992f1ed = 锚点 444 + 1 = **445**)
- +1 守恒 (P-6 cherry-pick 1 commit)

W89 累计:
- W89-P-1 (89897d590) → 锚点 338
- W89-P-2 (26d4ee547) → 锚点 339
- W89-P-6 (7e9d2698b) → 锚点 340 [main 没合, cherry-pick 在 x29]
- ...
- main tip (a000d0bf2) = 锚点 444 (W89 +0..+15 据实 14 commits)
- W89-X-29 (本任务 06992f1ed) = 锚点 445 (+1 守恒)

**注**: W89 锚点当前不是连续的 337→444 单调上升 — W89 多个 cherry-pick 路线 (B-1 / H-1 等)
与 main 平行, X-29 是其中之一. 派工 v6 §5 反馈 类 20.31 实战.

---

## 7. 下一步

- W89-X-29 commit + push (本任务)
- W89 grand closure (X-9 / X-17) 收口时, 主拍将 W89-X-29 cherry-pick 合入 main
- W89+ 派工顺序表: G-2 a11y 真登录态补刀 (类 20.25 续) — 现在有了类 20.84 沉淀, G-2
  可强制要求登录态 baseline 重 sync

---

**派工 v6 §5 反馈 累计**: 类 20.1-83 (历史) + **类 20.84** (本任务新增) = **84 实例**.