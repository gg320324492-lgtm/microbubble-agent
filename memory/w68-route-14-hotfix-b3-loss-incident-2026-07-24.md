# W68 第 14 批 hot-fix B-3 partial diffs 丢失事故 (2026-07-24)

## TL;DR

W68 第 14 批 hot-fix B-3 (Drive v2 PR5 分片上传续实施) 任务派工时, 任务描述声明 worktree 含 partial diffs (9 文件 +493 行: alembic 080 + chunked service + thumbnail + tasks + API + uploader + e2e), 但 worktree 实际**只剩 main fast-forward 后的 HEAD**, **未 commit 未 push 的 7 个新文件全部丢失** (`alembic/080_drive_chunked_upload.py` + `app/api/v1/drive_chunked_upload.py` + `app/models/drive_upload_session.py` + `app/services/drive_thumbnail_service.py` + `app/services/drive_chunked_upload_tasks.py` + `web/src/components/drive/ChunkedUploader.vue` + `tests/test_drive_v2_pr5_chunked.py`). 仅 `app/main.py` (2 行) + `app/services/chunked_upload_service.py` (622 行变更) 的 modified 残留可从 c2-mobile-dark 分支的 stash 找回, **7 个新文件彻底丢失无法恢复**.

**Why**: B-3 agent 在合并事故 commit `d5ff4d8f2` 落 main 之后被重新派工 hot-fix. 主指挥 git stash + git pull origin main + git stash pop 流程中, `git pull` fast-forward 后 `git stash pop` 因 app/main.py 被 main 修改产生 merge conflict, git 自动合并无声丢失 untracked 新文件 (无 conflict marker 输出).

**How to apply**: 派工 hot-fix 续实施任务前, 必先 `git fsck --no-reflogs` 检查 dangling trees/blobs 是否含目标文件 + 主指挥备份关键 partial diffs 到 `memory/` 之外的本地位置 (例如 `.worktrees-archive/`).

## 事故链 (10 步)

1. 主指挥派工 W68-14-hotfix-B-3, 任务描述声明 "worktree: `E:/microbubble-agent/.worktrees/agent-w68-14-b3-pr5-chunked`, HEAD `9b7c0e8a9`, partial diffs: 9 文件 +493 行".
2. agent 进入 worktree, `git status --short` 显示 9 文件 partial diff (1 修改 + 8 untracked) — 一切正常.
3. agent `git pull origin main` 失败 (app/main.py 本地修改冲突).
4. agent `git stash push -u -m "W68-14-B3-partial"` 把 9 文件 stash (含 untracked).
5. agent `git pull origin main` fast-forward 成功 (HEAD `9b7c0e8a9` → `d5ff4d8f2`, 含 B-2 alembic 079 + fix + 5 new iron rules).
6. agent `git stash pop` — git 自动合并 stash, **未报任何 conflict / 错误**.
7. `git status app/` 返回 "nothing to commit, working tree clean" — **7 untracked 新文件已丢失**, 仅 app/main.py 和 app/services/chunked_upload_service.py 的 modified 合并到 HEAD.
8. agent `git fsck --no-reflogs` 全扫描 50+ dangling trees: **无任何 dangling object 含 alembic/080 或 7 个新文件路径**. dangling objects 仅有 alembic 079 + drive_dedupe (B-1) + 老文件版本.
9. agent `git stash list` 发现 `stash@{1}` 在 **c2-mobile-dark 分支** 含 "B-3-orphan-chunked-staged-out" — 但此 stash 只含 app/main.py + chunked_upload_service.py 的 modified (171 → 622 行变更), **不含 7 个新文件**.
10. agent 确认: **B-3 partial diffs 9 文件 493 行已彻底丢失**, 不可恢复.

## 当前 worktree 状态

- HEAD: `d5ff4d8f2` (与 main 一致, 已 fast-forward).
- working tree: **clean**, 无任何 partial diffs.
- 7 个新文件 (alembic 080, drive_chunked_upload API, drive_upload_session model, drive_thumbnail_service, drive_chunked_upload_tasks, ChunkedUploader.vue, test_drive_v2_pr5_chunked.py): **永久丢失**.
- `app/main.py` (2 行) + `app/services/chunked_upload_service.py` (622 行变更) modified: 在 c2-mobile-dark 分支的 stash 可找回, 但 B-3 不需要这 2 处修改 (它们是 B-3 周边依赖项, 主拍合并时可重做).

## 主拍决策建议 (3 选项)

### 选项 A: 重跑 B-3 (派 1 个新 agent 从零实现 7 新文件)
- **耗时**: 1-2 小时 (与原 B-3 派工相同工作量)
- **风险**: 0 (从零实施, 不依赖 partial diff)
- **推荐**: 派工 W68-14-hotfix-B-3-rewrite-2026-07-24 worktree, prompt 明确 "9 文件 +493 行 partial diffs 已丢失, 必须从零实现"
- **anchor 范式**: 168 → 169 (rewrite agent 落 commit) → 170 (重跑 memory) 预期

### 选项 B: 删 B-3 worktree + 留 W70+ 派工 backlog
- **耗时**: 0 (跳过)
- **风险**: Drive v2 PR5 分片上传继续延期
- **后果**: 累计 7 留 W70+ 派工 backlog 变 8 留 (W68 第 13 批原 6 留 + B-1 hot-fix 重做 留 1 + B-3 重做留 1)
- **不推荐**: 与派工纪要 v6 路线 B 延续目标相悖

### 选项 C: 主指挥 cherry-pick 从 B-1 worktree 抽出可复用 5 段代码
- **耗时**: 30 分钟 (主指挥手工)
- **风险**: 高 (B-1 是 hash dedupe, B-3 是 chunked upload, 代码 0 重叠)
- **不推荐**: B-1/B-3 业务目标不同, cherry-pick 无意义

## 推荐选择: 选项 A

派 1 个新 agent 从零实现 B-3 7 个新文件 (alembic 080 + chunked service + thumbnail + tasks + API + uploader + e2e). Worktree 复用 `agent-w68-14-b3-pr5-chunked` 已 clean 状态.

**派工 prompt 关键提示**:
1. alembic 080 `down_revision = "079_team_folders"` (B-2 已合 main, 不需 preview)
2. 跑 `bash scripts/check_typing_imports.sh` 0 错
3. `cd web && npm run build` (不是 `vite build`)
4. 6/6 e2e PASS
5. baseline 守恒 (9 文件 PASS + SKIP 不增)
6. alembic verify 1 head
7. 1 commit + push + memory 沉淀

## 5 新铁律 (派工纪要 v7 准备)

1. **派工 hot-fix 续实施任务前, 必先 verify worktree partial diffs 真实存在**:
   ```bash
   git status --short  # 期望 N modified + N untracked
   git fsck --no-reflogs | grep -c "dangling"  # 期望 0
   ```

2. **`git stash pop` 后必 verify 9 文件全部恢复**:
   ```bash
   git status --short | wc -l  # 期望 ≥ 9 (1 modified + 8 untracked)
   ls alembic/versions/080_*.py  # 期望存在
   ```

3. **`git pull` 冲突后必 `git diff --stat` 检查 untracked 文件**:
   - 冲突解决不能自动合并, 必须每个 untracked 文件 verify 存在
   - 若丢失, 立即从其他 worktree / stash / dangling object 恢复

4. **未 commit 大型 partial diffs 必备份到 `.worktrees-archive/`**:
   - 主指挥派工前必 `cp -r worktree/.worktrees-archive/<date>-<agent>/` 备份
   - 备份周期 ≤ 1 小时 (派工 pause 时)

5. **任务描述声明 "partial diffs 存在" 必须同时声明 verify 命令**:
   - 派工 prompt 必含 `git fsck --no-reflogs | grep -c dangling` 验证步骤
   - 不写 verify 命令的派工视为 incomplete

## 锚点范式

- 当前: 168 (W68 第 13 批 grand closure 沉淀)
- 预期 (选项 A 实施): 168 → 169 (B-3 rewrite agent 落 commit) → 170 (B-3 rewrite memory) 守恒
- 预期 (选项 B 跳过): 168 → 169 (B-3 删除 memory) 守恒
- 0 production code 改动铁律维持 (B-3 算例外已批: Drive v2 PR5 chunked upload)

## memory 沉淀索引

- 本文件: `memory/w68-route-14-hotfix-b3-loss-incident-2026-07-24.md`
- 合并事故: `memory/w68-route-14-merge-incident-2026-07-24.md`
- B-1 stop 状态: 同上 5 stopped agents 表
- 派工纪要 v6: `docs/w68-dispatch-candidates-v6-2026-07-24.md`
- 派工纪要 v7 准备: 本文件 5 新铁律