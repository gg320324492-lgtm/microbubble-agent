# W89 DERIVE-14: .dockerignore 修 celery build 慢 (2026-07-30)

> **主基调**: DERIVE-14 P2 hotfix agent 派工. **根因不是 .claude/worktrees/** (已被 .claude/ 排除), **而是根目录残留的 agent-w89-* worktree + .ollama/ 14G 模型缓存 + backups/ 112M**.
> **修复方案**: 选项 A (广覆盖) — .dockerignore append 12 行排除.
> **实测效果**: docker build context **1.41GB → 36.57MB** (97.4% 减少), transfer time **73.8s → 1.5s** (98% 减少).

---

## DERIVE-02 据实上报 (vs 真实根因)

- **DERIVE-02 claim**: `agent-w89-p2-mobile-comments/` worktree 494M untracked 在 repo root
- **DERIVE-02 claim**: 每次 docker build 都 ship, celery build > 20min
- **真实根因** (DERIVE-14 实测):
  - **agent-w89-p2-mobile-comments/** 494M (root, **不在 .claude/worktrees/ 下**)
  - agent-w89-p7-visual-debug/ 46M (root)
  - agent-w89-p8-visual-sweep/ 560M (root)
  - backups/ 112M (root)
  - .ollama/ 14G (root, 模型缓存)
  - **总计 1.41GB shipped context**

## 选项 A 修复 (推荐, 已实施)

`.dockerignore` append (commit `ec637d0ad`):
```diff
+# 2026-07-30 DERIVE-14: 排除根目录残留 worktree 与本地缓存 (W89-P2 hotfix)
+# 根因: 每次 docker build ship ~1.4GB context (celery build > 20min)
+# 覆盖范围: W系所有 worktree + 其他意外创建目录
+agent-w*/
+agent-w*/*
+.worktrees/
+.ollama/
+.ollama/cache/
+backups/
+.pytest_cache/
+.coverage
+.coverage.*
+htmlcov/
+.tox/
+.mypy_cache/
+.ruff_cache/
+.wal/
```

## 实测对比 (修前 vs 修后)

| 指标 | 修前 | 修后 | 改进 |
|------|------|------|------|
| docker build context | 1.41GB | 36.57MB | **-97.4%** |
| context transfer time | 73.8s | 1.5s | **-98%** |
| celery-worker build | ~20min | ~15min (实测) | -25% |
| 主 pip install 耗时 | ~685s | ~685s | 不变 (本任务不解决) |

注: celery build 慢主要瓶颈在 pip install (PyTorch CUDA 依赖, 685s), 不是 docker context. DERIVE-14 修的是 context, 让 docker daemon 不必 ship 1.4GB.

## 5 件套守恒验证

1. **alembic 1 head** ✅ `['087_add_knowledge_original_parent_id']` 守恒
2. **pytest baseline** ✅ 未触动 (DERIVE-03 + DERIVE-04 已修)
3. **PWA build** ✅ N/A (dockerignore 改动不影响)
4. **0 production code** ✅ 仅 `.dockerignore` +18 行 (1 file changed)
5. **commit 含锚点范式** ✅ "锚点 338 → 339 +1 守恒" + W89 锚定

## 派工前提铁律 12 第 5 条实战: 实施前必先 Read 真文件

DERIVE-02 报告与实测不符的真实根因查找:
1. 读 `.dockerignore` → 看到 `.claude/` 已存在, 但 build context 仍 1.41GB
2. `du -sh */` → 发现 agent-w89-p2-mobile-comments/ 494M 在 **根目录** (不是 .claude/worktrees/)
3. 进一步发现: .ollama/ 14G + backups/ 112M + 多个 agent-w89-* 根目录残留
4. **教训**: 报告说 "agent-w89-p2-mobile-comments 在 worktrees" 是命名误导, 真实在根目录. **必先 du + ls 真验证**.

## 5 条新铁律 (W89 DERIVE-14 沉淀)

1. **.dockerignore 默认含 .claude/ 但不覆盖根目录残留** — 用户/agent 在根目录 mkdir agent-w*/ 后, 不在 .claude/worktrees/ 下, **逃过 .dockerignore**.
2. **agent-* 是危险前缀** — 派工 + manual 实验都可能在根目录 mkdir agent-wXX-YYY, 必加 `agent-*/` + `agent-*/*` 排除.
3. **docker build context 大小 ≠ pip install 耗时** — 修 context 只是 1 个杠杆, pip install 仍可能 10+ min. 完整优化需另算 (mount pip cache, sccache 等).
4. **派工 brief 实测前必先 du + ls 真验证根目录** — DERIVE-02 报 "agent-w89-p2-mobile-comments 494M 在 worktrees" 实测在根目录, 完全错配.
5. **alembic head + main HEAD 锚点范式必查** — 派工 commit message 引用锚点必须从 git log 拿, 不能记忆 (W86 → 337, W87 → 338, W89 → 339).

## 相关文件

- worktree: `E:\microbubble-agent\.claude\worktrees\rag-dockerignore`
- branch: `chore/w89-rag-dockerignore-2026-07-30`
- commit: `ec637d0adbe0e0ae4442623012e4630d135aa38d`
- 1 file changed, 18 insertions(+): `.dockerignore`
- pushed: origin/chore/w89-rag-dockerignore-2026-07-30
- main HEAD: `3a1ab24b3` (W86 mini-16 docs update)
- anchor paradigm: W86 325 → W87 336 → W86 mini-16 338 → **W89 dockerignore 339 +1** 守恒