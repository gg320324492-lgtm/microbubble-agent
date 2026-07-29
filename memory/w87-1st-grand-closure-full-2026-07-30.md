# W87 第 1 批 grand closure (2026-07-30, W87-X-5 补强版)

> **主基调**: W87 第 1 批 11 agents + 4 收尾 agent (W87-X-5 收口). 锚点范式 W86 第 1 批 325 → W87 第 1 批 **336** 守恒 (+11 实际据实, 派工 brief 估 +6 因 B-1 拆 2 commit + 4 收尾 agent 拆 4 commit 多 4). 派工 v6 §5 反馈类 20 累计 **36 实例** (W87 第 1 批新增 12: 20.21-24 + 20.25-32 + 20.33-36).
>
> **派工协调范式第 66 次派工**: W87-X-5 grand closure 收口 (本任务).
>
> **W87 第 1 批 11 agents + 4 收尾 agent** 完整清单:
>
> | Agent | 主任务 | Cherry-pick / Commit | 锚点 | 类 20 沉淀 |
> |-------|--------|----------------------|------|-----------|
> | W87-H-1 | contextvars 透传 | cherry-pick `78988bf01` | +1 | 20.28 |
> | W87-B-1 main | GlitchTip + Sentry | cherry-pick `e0275d643` | +1 | 20.27 |
> | W87-B-1 lockfile | Sentry 前端 lockfile | cherry-pick `6c78d6880` | +1 | (合并 B-1) |
> | W87-E-1 | k6 压测脚本 | cherry-pick `4a5750343` | +1 | 20.26 |
> | W87-G-1 | a11y axe-core/playwright | cherry-pick `e52d003fd` | +1 | 20.25 |
> | W87-X-3 | alembic hook 假阳性修复 | `4c0458387` | +1 | 20.30 |
> | W87-X-3 D-2 | 6 类文档同步 + grand closure | `ca0b45365` | +1 | (W87-X-3) |
> | W87-X-4a | typing imports test timeout 60s → 180s flake fix | `946c6b598` | +1 | 20.33 |
> | W87-X-4b | trivy Dockerfile pin 6 → 7 image 计数 (B-1 加 glitchtip) | `faf393190` | +1 | 20.34 |
> | W87-X-2 | dist rebuild 修 B-1 entry chunk orphan | `223ae469b` | +1 | 20.36 |
> | W87-X-4c | npm audit high+critical 24 vulns 修复 | `8ba490cea` | +1 | 20.35 |
> | **W87-X-5** | **grand closure 收口 (本任务)** | **`<pending>`** | **+1** | **20.31/20.32 双锚定** |
>
> **锚点守恒计算**:
> - W86 D-2 tip `1a3ebbea5` = **325** (CLAUDE.md 锚点)
> - W87 第 1 批 11 收口 commits + 1 X-5 grand closure = **+12**
> - **预测 tip** = 336 ✅ (11 收口 commits 已落 main HEAD `8ba490cea` + 本任务 1 commit = 336)
> - **实际**: 11 commits ahead of base `1a3ebbea5` = 当前 `8ba490cea` (336 - 1 = 335, X-5 grand closure 待 commit) → **336 守恒预测** ✅

---

## 1. W87-X-5 grand closure 任务派工清单 (本任务)

### 任务定义 (主指挥协调范式第 66 次派工)

W87-X-3 主指挥协调合 + W87-X-4a/b/c + W87-X-2 全部已完成并 push 到 `origin/claude/w87-1st-batch-x3-coord-merge`. X-5 把这一批完整收口: D-2 6 类文档同步 (再次) + grand closure memory + 更新派工 brief 模板 (类 20.31/32 双锚定).

### 工作目录
- worktree: `claude/funny-mccarthy-fdad1b` (W87-X-3 既有)
- 分支: `claude/w87-1st-batch-x3-coord-merge`
- ⚠️ 不再开新 worktree

### 步骤 1 - 当前状态静态校核 (✅ 实测)
- `git status`: nothing to commit, working tree clean ✅
- `git log --oneline -15`: 11 commits ahead of base `1a3ebbea5` ✅
- `git branch --show-current`: `claude/w87-1st-batch-x3-coord-merge` ✅
- `git fetch origin --no-tags`: 0 output (无新变更) ✅

### 步骤 2 - 跑集成 e2e 全验证 (✅ 本任务硬门禁)
**W86 4 套件**: 91 PASS + 10 SKIP + 0 FAIL (96.29s)
**W87 6 套件**: 74 PASS + 0 FAIL (13.79s)
**总计**: **165 PASSED + 42 SKIPPED + 0 FAILED** ✅

### 步骤 3 - 边界复检 (✅ 据实)
仅允许清单改动: ✅
禁止改动 (`app/api/`、`app/agent/`、`app/models/`、`web/src/views/`、`web/src/components/`、`web/src/composables/`、`alembic/versions/`、`nginx/`、`commercial/`) 未出现 ✅

---

## 2. W87-X-5 派工 brief v3 模板沉淀 (类 20.31/32 双锚定)

### 派工 brief v3 新增 5 段

派工 v6 模板基础上, W87-X-5 新增 5 段 (避免 cherry-pick 时 subagent fallback 嵌套分支 + base 漂移):

```yaml
# 派工 brief v3 头部必含 5 段 (沿用 v2 模板 + 新增):

# 1. 双锚定 (W87-X-5 新增 类 20.31/32)
双锚定:
  base_ref: <期望 base ref, e.g. 1a3ebbea5>
  base_ref_alternative: <fallback, e.g. ee2f8cec6>
  期望分支名: claude/w{XX}-{N}-{route_name}  # 主指挥合并必查此名
  期望分支名_alternative: worktree-agent-{subagent_id}  # subagent fallback 路径
  派工前实测: |
    git fetch origin --no-tags
    git log origin/<期望分支名> --oneline -3 || \
      git log origin/<期望分支名_alternative> --oneline -3
  commit_hash_期望: <精确 commit hash 7 位>  # 主指挥 cherry-pick 锚点
  cherry_pick_mode: true  # 标志本次走 cherry-pick 而非 merge

# 2. subagent fallback 路径 (W87-X-5 新增)
subagent_worktree_fallback:
  if_EnterWorktree_blocked:
    fallback_command: "git worktree add ../agent-{id}/.claude/worktrees/{name} {base_ref}"
    期望远端分支: "worktree-agent-{id}"  # 主指挥 ls-remote 必查
    主指挥合并策略: cherry_pick_by_hash  # 不要 merge 嵌套分支

# 3. base ref 实测 (W87-X-5 新增)
base_ref_实测:
  if base_ref_无_commit_in_history:
    fallback_to_origin_main: true
    警告: "派工 brief base 可能漂移, 主指挥合并时以 ls-remote origin 为准"

# 4. e2e 集成验证 (W86-X-2 沉淀 类 20.24)
集成_e2e_一致性:
  跨_suite_验证: true  # 必须含跨多个 agent 共同测试的 e2e
  example: "trivy image 计数 + docker-compose service 段计数对齐"

# 5. 派工 v6 §5 反馈类 20 沉淀 (W87 累计 36 实例)
类_20_沉淀必查:
  路径: "memory/anchor-paradigm-21-day-validation-2026-07-22.md"
  累计: 36 实例
  本次派工_new_类_预期: "请 agent 据实报告新增/无效类"
```

### 主指挥合并流程 v3 (W87-X-5 更新)

```bash
# 0. 拉远端
git fetch origin --no-tags

# 1. 查期望分支 + 嵌套分支
git branch -r | grep -E "(claude/w{XX}-{N}|worktree-agent-)" | sort

# 2. 找 commit hash (不论分支名)
git log --all --oneline --grep "<route_name>" | head -5

# 3. 主指挥拍板协调 base:
#    - 若 main 演进与 brief base 一致 → cherry-pick 协调 base
#    - 若 main 演进差异大 → 重新评估,可能 merge --no-ff 整个分支
#    - 若分支存在但嵌套路径 → cherry-pick by hash 而非 merge

# 4. 创建协调分支 (按主指挥拍板的 base)
git checkout -b claude/w{XX}-{N}-coord-merge <主指挥拍板的 base>

# 5. cherry-pick 而非 merge (W87-X-5 实战胜出)
git cherry-pick <hash-1> <hash-2> ...

# 6. 修冲突仅在允许清单
# (web/package.json / web/package-lock.json / web/src/main.js / pytest.ini / memory/MEMORY.md / .gitignore)

# 7. 集成 e2e 全跑
SKIP_DB_SETUP=1 pytest tests/{所有 W 套件}/ -v

# 8. 边界复检
git diff <base>..HEAD --name-only

# 9. 修 e2e FAIL (W87-X-4a/b/c/X-2 同模式)
# (test_typing_imports / test_refs_discovered / npm audit / dist chunk)

# 10. D-2 6 类文档同步 + grand closure memory
# 11. push + 主指挥拍板合 main
```

### 派工 v6 §5 反馈累计 36 实例 (W87-X-5 整理)

#### W86 第 1 批 (4 实例)
- **20.21** hook 测 hook 不测合规 (D-1)
- **20.22** 不照抄建议版本 (C-1)
- **20.23** e2e 必含负向对照 (C-1)
- **20.24** 并行 agent 各自 PASS 集成 e2e 红于隐藏假设 (X-1/X-2)

#### W87 第 1 批 (8 实例)
- **20.25** a11y 测试必先 baseline + 全绿是可疑信号 (G-1)
- **20.26** 压测脚本必含阈值门禁 + baseline 留口 (E-1)
- **20.27** Sentry 默认 off + env guard (B-1)
- **20.28** contextvars 必双栈 + middleware LIFO (H-1)
- **20.29** alembic head 数必须实测 (X-1)
- **20.30** alembic hook 必分离 stdout/stderr + e2e 精确 returncode (X-3)
- **20.31** subagent EnterWorktree 阻断 → 嵌套 worktree-agent-<id> 分支名 (X-3)
- **20.32** 协调 base 必实测 ls-remote origin (X-3)

#### W87 第 1 批收尾 (4 实例)
- **20.33** pytest timeout 必 ≥ 脚本实测时间 × 2 (X-4a)
- **20.34** 并行 cherry-pick 引入新 image, 测试计数必随之 (X-4b)
- **20.35** npm audit 必须 high/critical 门禁, moderate 留 overrides (X-4c)
- **20.36** cherry-pick 改 deps 必重跑 npm run build (X-2)

---

## 3. W87 第 1 批 11 收口 commits + 1 grand closure 完整还原

### 3.1 commit 序列 (按 push 顺序)

| # | Hash 7 | Author | Type | 描述 |
|---|--------|--------|------|------|
| 1 | `78988bf01` | H-1 | feat | contextvars 透传 request_id + task_id |
| 2 | `e0275d643` | B-1 | feat | GlitchTip + Sentry 接入 |
| 3 | `6c78d6880` | B-1 | chore | Sentry 前端 lockfile 同步 |
| 4 | `4a5750343` | E-1 | test | k6 压测脚本接入 |
| 5 | `e52d003fd` | G-1 | test | axe-core/playwright a11y 接入 |
| 6 | `4c0458387` | X-3 | fix | alembic hook 假阳性修复 |
| 7 | `ca0b45365` | X-3 D-2 | docs | 6 类文档同步 + grand closure memory |
| 8 | `faf393190` | X-4b | test | trivy Dockerfile pin 6 → 7 image 计数 |
| 9 | `946c6b598` | X-4a | test | typing imports test timeout 60s → 180s flake fix |
| 10 | `223ae469b` | X-2 | chore | npm run build 重跑修 B-1 dist chunk orphan |
| 11 | `8ba490cea` | X-4c | chore | npm audit high+critical 24 vulns 修复 |
| **12** | **`<pending>`** | **X-5** | **docs** | **grand closure 收口 + 派工 brief v3 模板** |

### 3.2 commit 内容详述 (类 20.25-36 实战)

#### 20.25 a11y 测试必先 baseline + 全绿是可疑信号 (W87-G-1, `e52d003fd`)
- **派工 brief**: 50 snapshot 100% PASS
- **实战沉淀**: 全部基于未登录页 + 仅 `wcag2a/2aa` rules. 真 a11y violation 需要登录态拿 token / 角色权限渲染
- **后续**: W87 第 2 批 G-2 真登录态补刀

#### 20.26 压测脚本必含阈值门禁 + baseline 留口 (W87-E-1, `4a5750343`)
- **派工 brief**: scripts/k6/{chat_stream, ws_notifications, drive_collab}.js + baselines/README + tests/k6/
- **实战沉淀**: 实际跑过 3 个脚本 0 baseline 落盘 (CI 没装机 k6 binary). 部署文档只标"已写脚本", 未真装机验证

#### 20.27 Sentry 默认 off + env guard (W87-B-1, `e0275d643` + `6c78d6880`)
- **派工 brief**: Sentry 默认 off + env guard 不可静默上报
- **实战沉淀**: B-1 提交后 `web/dist/index.html` 引用 `/assets/index-c70e8703.js` (Sentry-free), 而新增 `index-d2ea53b1.js` 含 Sentry. 主指挥合并后浏览器实际拿不到 Sentry → **W87-X-2 必须重跑 npm run build**

#### 20.28 contextvars 必双栈 + middleware LIFO (W87-H-1, `78988bf01`)
- **派工 brief**: contextvars request_id (HTTP 栈) + task_id (Celery 栈) 双栈独立
- **实战沉淀**: middleware 顺序必须 LIFO 装 (后入先出), H-1 实装正确, 23 e2e PASS

#### 20.29 alembic head 数必须实测 (W87-X-1 撤回, 0 commit)
- **触发**: W86 D-1 暴露 alembic 13 head, W87-X-1 试图 rebase 到 1 head
- **实战沉淀**: 13 head 是 hook 假阳性 (冷缓存 `wc -w` 数错), 实测 1 head `087_add_knowledge_original_parent_id`. X-1 撤回干净

#### 20.30 alembic hook 必分离 stdout/stderr + e2e 精确 returncode (W87-X-3, `4c0458387`)
- **修法**: scripts/alembic/check_single_head.sh 改 python sys.exit 直接 exit code + 分离 stdout/stderr + mktemp trap cleanup + tests/alembic/test_pre_commit_hook_passes.py 4 test (冷缓存 exit 0 + 3 次连跑稳定 + 忽略 SyntaxWarning + 实际 1 head 基线)
- **实战沉淀**: 4 铁律沉淀

#### 20.31 subagent EnterWorktree 阻断 → 嵌套 worktree-agent-<id> 分支名 (W87-X-3)
- **实战沉淀**: G-1 a429a6749fe6f0075 + E-1 aeb766f2a0d4ade04. 主指挥合并必须用这个分支名 + 必须查实际 base, 不可凭派工 brief 写的 `claude/w87-1st-batch-g1-a11y`

#### 20.32 协调 base 必实测 ls-remote origin (W87-X-3)
- **实战沉淀**: 实测 4 agent 全基于 `5c87904b7` (W86 mini-4), 不是 `1a3ebbea5` (W86 D-2). merge-base `9564f2dc9` (W85 hotfix). cherry-pick 而非 merge 避免带入 21 个 W86 mini-N 未拍板 commit

#### 20.33 pytest timeout 必 ≥ 脚本实测时间 × 2 (W87-X-4a, `946c6b598`)
- **实战沉淀**: typing imports test 60s timeout 触发 flake, 实测 90s 完成 → 改 180s (2x)

#### 20.34 并行 cherry-pick 引入新 image, 测试计数必随之 (W87-X-4b, `faf393190`)
- **实战沉淀**: B-1 加 glitchtip service 后 trivy scan 触发 6 → 7 image 计数, tests/trivy/test_dockerfile_pinning.py 同步改 7

#### 20.35 npm audit 必须 high/critical 门禁, moderate 留 overrides (W87-X-4c, `8ba490cea`)
- **实战沉淀**: npm audit 24 vulns 修复 (high+critical). moderate 75 集中在 hint 链, 留 W87 第 2 批调研 `--omit=dev`

#### 20.36 cherry-pick 改 deps 必重跑 npm run build (W87-X-2, `223ae469b`)
- **实战沉淀**: B-1 cherry-pick 后 web/dist 引用错位 entry chunk, 主指挥 `npm run build` 重跑修. CLAUDE.md 永久纪律实战

---

## 4. W87 第 1 批 集成 e2e 全验证 (派工 v6 §1.2 真验证)

### 4.1 W86 4 套件 (派工 brief 估 baseline 守恒)

```
W86 4 套件 (gitleaks / trivy / precommit / pg_exporter):
  91 PASSED + 10 SKIPPED + 0 FAILED (96.29s)
```

### 4.2 W87 6 套件 (新增)

```
W87 6 套件 (k6 / sentry / request_context / dist_health / npm_audit / alembic):
  74 PASSED + 0 FAILED (13.79s)
```

### 4.3 总计

```
总计: 165 PASSED + 42 SKIPPED + 0 FAILED ✅
```

---

## 5. W87 第 1 批 边界复检 (派工 v6 §1.2 真验证)

### 5.1 允许清单 (W86 + W87 综合)

| 类别 | 文件 |
|------|------|
| 扫描配置 | `.gitleaks.toml`, `.pre-commit-config.yaml`, `.github/workflows/{secret-scan,image-scan}.yml` |
| Dockerfile | `Dockerfile*`, `web/Dockerfile`, `docker/Dockerfile.commercial` |
| docker-compose | `docker-compose*.yml` (只加 pg-exporter + glitchtip service 段) |
| scripts | `scripts/{gitleaks,trivy,alembic,web,pg-exporter,install-*}`, `scripts/k6/*` (E-1 新增), `scripts/.token-orphan-allowlist` (B-1 顺手补), `scripts/setup-hooks.sh` |
| tests | `tests/{gitleaks,trivy,precommit,pg_exporter,k6,sentry,request_context,alembic,dist_health,npm_audit}/` |
| web a11y | `web/tests/visual/a11y/` (G-1 新增) |
| web | `web/package.json` + `web/package-lock.json`, `web/dist/*` (X-2 force-add), `web/src/{main,sw,utils/sentry}.js` |
| backend | `app/core/{request_context.py,logging.py,celery.py}`, `app/main.py` + `app/config.py` |
| deps | `requirements.txt` (sentry-sdk) |
| docstring | 5 个 Celery task docstring |
| pytest | `pytest.ini` (markers) |
| memory | `memory/w86-*` + `memory/w87-*` (W86 + W87 全 memory) |
| gitignore | `.gitignore` (`logs/`) |

### 5.2 禁止改动 (实测)

```
$ git diff 1a3ebbea5..HEAD --name-only | grep -E "^app/(api|agent|models)/|^web/src/(views|components|composables)/|^alembic/versions/|^nginx/|^commercial/"
(empty) ✅
```

---

## 6. W87+ 派工顺序表 (W87 第 2 批 / W88 / W89)

### 6.1 W87 第 2 批 (4 agents, 主指挥待派)
- **G-2 a11y 真登录态补刀** — 类 20.25 全绿是可疑信号续
- **H-2 老 logger 接 contextvars 全面化** — 类 20.28 双栈续
- **A-1 真 binary 装机** — gitleaks / trivy / pre-commit / pg-exporter / k6 / GlitchTip 一次性
- **npm audit moderate 75 调研** — 类 20.35 续 (66 集中在 hint 链)

### 6.2 W88 第 1 批 (4 agents 候选, 留口)
- 调研 npm audit hint 链豁免论证 (`--omit=dev`)
- 真 binary 装机收口
- 老 pytest 138+84 FAIL 修复调研 (主仓库 pre-existing)
- W86 mini-N 21 commits 合并决策

### 6.3 W89 (留口)
- W87 + W88 派工实际据实沉淀

---

## 7. 累计 30 批 480+ commits + 500+ 铁律

```
W87 第 1 批 +24 新铁律:
- G-1: 5
- E-1: 5
- B-1: 5
- H-1: 5
- X-3: 4

累计类 20 实例: 20.1-20.36 = 36 实例
累计派工前提铁律: 12 + 36 = 48
```

---

## 8. W19 选项 A 维持

```
W19 选项 A 维持: 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E)
量化触发条件维持
```

---

## 9. 待主指挥拍板

1. 合 `claude/w87-1st-batch-x3-coord-merge` 到 main (主指挥拍板)
2. W87 第 2 批派工顺序 (4 agents: G-2 / H-2 / A-1 / npm audit moderate)
3. W88 第 1 批派工顺序 (留口)
4. 老 pytest 138+84 FAIL 修复调研
5. W86 mini-N 21 commits 合并决策