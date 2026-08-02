---
name: auto-deploy-sh-step3-grep-pipefail-abort-2026-08-02
metadata:
  node_type: memory
  type: project
---

# auto-deploy.sh Step 3 grep+pipefail 中止 bug + 修复（2026-08-02）

## 症状

`scripts/auto-deploy.sh`（顶部 `set -euo pipefail`）在 **Step 3 "Git commit (web/dist force-add)"** 后中止 - 跑到 `git add -f -A web/dist/` 成功 stage 完所有 dist 文件后，脚本悄悄退出（退出码 1），没打印后续 commit/push 结果。导致每次成功部署都卡在 Step 3，需手动 commit + push 才能继续。

## 根因

```bash
# scripts/auto-deploy.sh line 198
UNTRACKED_DIST=$(git status --porcelain web/dist/ 2>/dev/null | grep "^??" | head -3)
```

`grep "^??"` 无匹配返回 **exit 1**。在 `set -euo pipefail` 下：
- 管道 `git status | grep | head` 经 pipefail 返回 grep 的 1
- `UNTRACKED_DIST=$(...)` 命令替换，set -e 触发
- 脚本中止

**这正是成功场景触发**：`git add -f -A` 已 stage 所有 dist 文件 -> `git status --porcelain` 无 untracked 输出 -> grep 无匹配。

## 修复（commit `d6ee1532c`）

2 处加兜底：
- **line 198 关键**: `UNTRACKED_DIST=$(... | grep "^??" | head -3 || true)`
- **line 174 latent**: `HEADS=$(python -m alembic heads 2>&1 | grep -E "^[0-9a-z]+_" | wc -l || echo "0")`（alembic 失败/无 head 时 grep 无匹配）
- line 260 已有 `|| echo "0"`（作者知道这坑，漏了 198/174）

## 验证

```bash
# 复现
bash -c 'set -euo pipefail
UNTRACKED_DIST=$(git status --porcelain web/dist/ | grep "^??" | head -3)
echo reached'
# -> 退出码 1, 不打印 reached

# 修复后
bash -c 'set -euo pipefail
UNTRACKED_DIST=$(git status --porcelain web/dist/ | grep "^??" | head -3 || true)
echo reached'
# -> 退出码 0, 打印 reached, UNTRACKED_DIST 空

# 端到端
bash scripts/auto-deploy.sh  # 走完 5 步到"部署链完成" ✅
```

## 教训（永久铁律）

- **`set -euo pipefail` + grep 无匹配 = 隐蔽 trap**：任何 `$(... | grep PATTERN ...)` 命令替换，若 grep 可能无匹配，必须 `|| true` 或 `|| echo ""` 兜底。`grep` 返回 0（命中）/ 1（无命中），不是 True/False。`if grep -q` 安全（if 上下文 set -e 失效），但命令替换不安全。
- **审计 `set -e` 脚本时专查 `$(... | grep | head/wc)` 模式** - 这是高发陷阱。line 198/174/260 三连坑说明同一作者反复踩。
- **post-commit 自动 push 钩子**（项目已配置）会解释"git push 显示 Everything up-to-date"之谜 - 钩子已先推过。手工 push 在钩子已推后是 no-op。
- **部署脚本中断时**别只信 `tail -60` 输出（长 build log 会把 Step 3-5 结果挤出去），直接 `git log --oneline` + `git status` 看 commit/push 是否落地。

## 顺带清理

- `app/app/` 8.7M 残留目录（2026-08-02 清理）：docker cp 方向反了把容器内 `/app/app/` 拷回仓库根。git 未跟踪，安全 rm -rf。教训：docker cp 方向必查（`container:src host:dst` vs `host:src container:dst`）。

## 关联

- `scripts/auto-deploy.sh`（已修复，commit `d6ee1532c` on main, 已 push origin）
- CLAUDE.md 2026-06-13 PWA manifest 410 纪律（部署脚本铁律沿用）