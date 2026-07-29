# 派工 Brief 模板 v3 (W87-X-5 沉淀, 类 20.31 + 20.32 双锚定)

> **W87-X-5 据实教训**: W87 第 1 批派工时, 2/3 的 subagent 因 EnterWorktree 阻断 fallback 到 `git worktree add`, 导致:
> 1. **分支名错位**: `worktree-agent-<id>` 而非预期的 `claude/w{XX}-*` (类 20.31)
> 2. **base ref 漂移**: brief 给的 base 是 `1a3ebbea5`, 但 main 已演进到 `ee2f8cec6` (类 20.32)
>
> 主指挥合并时, 3 件大事暴露:
> - 期望的 `origin/claude/w87-1st-batch-e1-k6` / `g1-a11y` 分支不存在
> - 实际在 `origin/worktree-agent-<id>` 嵌套路径
> - 主指挥合并必须从 commit hash cherry-pick, 而非 merge 整个分支

## 派工 brief v3 头部必含 5 段 (沿用 v2 模板 + 新增)

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

## 派工 v6 §1.2 真验证必含 (沿用)

```yaml
# 6. 真验证 (派工 v6 §1.2)
真验证_必含:
  - git_show: "git show <commit_hash> --stat"
  - grep: "grep -rn <feature_keyword> app/ web/ --include='*.py' --include='*.vue' --include='*.ts'"
  - 集成_e2e: "SKIP_DB_SETUP=1 pytest tests/{所有套件}/ -v"
  - 边界复检: "git diff <base>..HEAD --name-only"
  - commit_hash_报告: "agent 必须 report 真实 commit hash, 不可凭 Status 段"
```

## 派工 v6 §7 实战派工 19 类 (沿用)

```yaml
# 7. 派工 v6 §7 实战派工 19 类
实战派工_必含:
  - 5 段 prompt 模板 (alembic verify + PS 5.1 + plans 真验证 + cherry-pick by hash + ls-remote origin)
  - 类 20 沉淀必查 (memory/anchor-paradigm-21-day-validation-2026-07-22.md)
  - 据实报告 (commit hash 必真, 不偷懒)
  - 集成 e2e (跨 suite 必跑)
  - 边界复检 (允许清单 vs 禁止清单)
```

---

## 主指挥合并流程 v3 (W87-X-5 更新)

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

---

## 派工 v6 §5 反馈累计 36 实例

### W86 第 1 批 (4 实例)
- **20.21** hook 测 hook 不测合规 (D-1)
- **20.22** 不照抄建议版本 (C-1)
- **20.23** e2e 必含负向对照 (C-1)
- **20.24** 并行 agent 各自 PASS 集成 e2e 红于隐藏假设 (X-1/X-2)

### W87 第 1 批 (8 实例)
- **20.25** a11y 测试必先 baseline + 全绿是可疑信号 (G-1)
- **20.26** 压测脚本必含阈值门禁 + baseline 留口 (E-1)
- **20.27** Sentry 默认 off + env guard (B-1)
- **20.28** contextvars 必双栈 + middleware LIFO (H-1)
- **20.29** alembic head 数必须实测 (X-1)
- **20.30** alembic hook 必分离 stdout/stderr + e2e 精确 returncode (X-3)
- **20.31** subagent EnterWorktree 阻断 → 嵌套 worktree-agent-<id> 分支名 (X-3)
- **20.32** 协调 base 必实测 ls-remote origin (X-3)

### W87 第 1 批收尾 (4 实例)
- **20.33** pytest timeout 必 ≥ 脚本实测时间 × 2 (X-4a)
- **20.34** 并行 cherry-pick 引入新 image, 测试计数必随之 (X-4b)
- **20.35** npm audit 必须 high/critical 门禁, moderate 留 overrides (X-4c)
- **20.36** cherry-pick 改 deps 必重跑 npm run build (X-2)

---

## 派工 brief v3 实战示例 (W87 第 2 批 G-2)

```yaml
派工 G-2 a11y 真登录态补刀:
  双锚定:
    base_ref: <W87-X-5 commit hash, 7 位>
    base_ref_alternative: <W87 第 2 批主协调 base, e.g. ee2f8cec6>
    期望分支名: claude/w87-2nd-batch-g2-a11y-login
    期望分支名_alternative: worktree-agent-g2-{subagent_id}
    派工前实测: |
      git fetch origin --no-tags
      git log origin/claude/w87-2nd-batch-g2-a11y-login --oneline -3 || \
        git log origin/worktree-agent-g2-XXXX --oneline -3
    commit_hash_期望: <W87-X-5 后 main HEAD 7 位>
    cherry_pick_mode: true
  subagent_worktree_fallback:
    if_EnterWorktree_blocked:
      fallback_command: "git worktree add ../agent-g2/.claude/worktrees/g2-a11y-login {base_ref}"
      期望远端分支: "worktree-agent-g2-{subagent_id}"
      主指挥合并策略: cherry_pick_by_hash
  集成_e2e_一致性:
    跨_suite_验证: true
    example: "a11y 真登录态 + wcag2a/2aa + axe-core rules 全套"
  类_20_沉淀必查:
    路径: "memory/anchor-paradigm-21-day-validation-2026-07-22.md"
    累计: 36 实例
    本次派工_new_类_预期: "类 20.37 a11y 真登录态必含 token/角色 渲染快照"
  真验证_必含:
    - git_show: "git show <commit_hash> --stat"
    - grep: "grep -rn 'a11y-baseline\\|axe-core\\|wcag2aa' web/tests/visual/a11y/"
    - 集成_e2e: "cd web && npx playwright test -c tests/visual/a11y/playwright.a11y.config.mjs"
    - 边界复检: "git diff <base>..HEAD --name-only"
```

---

## 派工 brief v3 模板历史 (W68-W87)

- **v1**: W68 第 12 批 (派工 v3 段 3 alembic verify)
- **v2**: W68 第 13 批 (5 段 prompt 升级: alembic verify + PS 5.1 + plans 真验证)
- **v3**: W87 第 1 批 (W87-X-5 沉淀: 类 20.31/32 双锚定 + subagent fallback 路径 + base ref 实测 + 集成 e2e 一致性 + 类 20 沉淀必查)

详见:
- `docs/w68-13th-batch-prompt-template-v4.md` (v1/v2 历史)
- `docs/w72-prompt-paradigm-v10-2026-07-27.md` (派工协调范式 v10)
- `memory/anchor-paradigm-21-day-validation-2026-07-22.md` (类 20 沉淀起点)