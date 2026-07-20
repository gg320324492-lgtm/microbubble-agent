# Drive 跨分支冲突矩阵分析报告

**日期**：2026-07-20  
**分析基准**：本地 `main=af29e04f`，当前工作分支 `fix/office-preview-sandbox=f5715fd9`  
**范围**：6 个 active branch（不 checkout、不 merge、不 rebase）  
**分析目标**：确认 Drive/录音/前端 dist 相关分支的真实重叠、冲突风险和推荐收敛路径。

> 本报告只做只读分析。生成报告时没有切换分支、没有执行 `git merge` 或 `git rebase`，也没有修改现有未提交的 Self-RAG/agent 工作树改动。

---

## 1. Executive summary

### 1.1 结论

1. `fix/office-preview-sandbox` 是现成的 fan-in 汇总分支，已经通过三个 merge commit 吸收：
   - `fix/voiceprint-and-schema-cleanup`
   - `fix/code-todo-and-dist-cachebust`
   - `fix/drive-cleanup-and-mime-patch`
2. `fix/drive-selected-folder-ref` 相对当前 `main` **零差异**，无需再次合并。
3. `feature/product-expansion-planning` 只新增 [`ROADMAP.md`](../ROADMAP.md) 149 行，与 Drive/录音代码无文件重叠。
4. 按“同一文件被多个 branch 改动”统计，存在 **6 个高风险矩阵 pair-cell**：B/C、B/E、B/F、C/E、C/F、E/F。它们全部来自 B/C/F/E 四个功能分支之间的共享录音/Drive 文件和 tracked `web/dist/**`。
5. 15 组两两 `git merge-tree --write-tree` 全部返回成功，**实际 Git 文本冲突数为 0**。因此“高风险”表示人工合并/重复 cherry-pick 易出错，不表示当前 Git 一定会产生 conflict marker。
6. 推荐路径是：**只将 `fix/office-preview-sandbox` 作为功能汇总分支合入 `main`，不要再单独合 B/C/F；跳过 D；最后独立合入 A 的 ROADMAP**。若 `main` 未前进，E 可直接 `--ff-only`；A 建议单独 cherry-pick `069fa5c0` 或最后做一次仅含 ROADMAP 的合并。

### 1.2 冲突计数口径

| 指标 | 数量 | 说明 |
|---|---:|---|
| 分析 branch | 6 | A-F，均相对 `main` 分析 |
| 两两矩阵 pair-cell | 15 | 6 个 branch 的无序组合 |
| 有共享变更路径的 pair-cell | 6 | B/C/F/E 四个功能分支之间 |
| 高风险 pair-cell | **6** | 共享源文件和/或 tracked dist 文件 |
| 实际 `merge-tree` 冲突 | **0** | 15 组全部成功，无 `CONFLICT`/冲突标记 |
| E 相对 `main` 的 changed paths | 215 | 48 个非 dist 源路径 + 167 个 dist 路径 |
| E 相对 `main` 的非 dist changed paths | 48 | 已包含 B/C/F 的最终代码 |
| D 相对 `main` 的 changed paths | 0 | D 已经是 `main` 的祖先 |
| A 相对 `main` 的 changed paths | 1 | 仅 `ROADMAP.md` |

> **“冲突点总数”**按 pair-cell 口径为 **6**；其中高风险 **6**。按真实 Git merge 口径为 **0**。报告同时保留两种口径，避免把 dist 重叠误报成已经发生的文本冲突。

---

## 2. Branch 编号和相对 main 范围

| 编号 | Branch | Tip | `main..branch` 独有 commit 数 | 相对 `main` changed paths | 非 dist paths | dist paths | 风险摘要 |
|---|---|---|---:|---:|---:|---:|---|
| **A** | `feature/product-expansion-planning` | `069fa5c0` | 1 | 1 | 1 | 0 | 低：仅 ROADMAP |
| **B** | `fix/code-todo-and-dist-cachebust` | `ed1e03e8` | 9 | 207 | 41 | 166 | 高：W3 TODO + 录音链 + 大量 dist |
| **C** | `fix/drive-cleanup-and-mime-patch` | `badfdd08` | 8 | 121 | 27 | 94 | 高：Drive 留尾 + MIME + 录音链 |
| **D** | `fix/drive-selected-folder-ref` | `1d946f27` | 0 | 0 | 0 | 0 | 低：已在 main |
| **E** | `fix/office-preview-sandbox` | `f5715fd9` | 17 | 215 | 48 | 167 | 汇总：包含 B/C/F + Office preview |
| **F** | `fix/voiceprint-and-schema-cleanup` | `e40bd8ab` | 6 | 118 | 24 | 94 | 中/高：schema + 录音链 |

### 2.1 各 branch 相对 main 的提交范围

#### A — `feature/product-expansion-planning`

```text
069fa5c0 docs(roadmap): 追加产品扩展规划章节（前置 P0 + 6 阶段）
```

相对 `main` 只有 `ROADMAP.md`：149 additions / 0 deletions。与其他五个 branch 没有共享 changed path。

#### B — `fix/code-todo-and-dist-cachebust`

```text
ed1e03e8 chore(dist): vite 加 build timestamp 全局常量便于 cache miss 诊断
44e063e2 feat(file-request): QR code 扫码预览
708dd2e7 feat(paper): 翻译 API 全链路 + ParagraphActions 3 TODO 实装
a04993cb feat(embedding): query prompt 实装 + 2 单测
2aeae1ed fix(meeting): polish dispatch 走 LLMClient + cancel-recording 清 audio_url 字段 + 孤儿 audio_url 清理
9f9d1a25 fix(recording): 前端 recorder 全链路
ebe6726e fix(recording): post_meeting NameError + reminder scheduler + orphan cleanup 扩展
623e36c7 fix(recording): meeting recording 全链路
19b37be5 fix(drive): 修复 Office 在线预览 sandbox 黑屏
```

非 dist 重点：translation API/service、embedding prompt/service、paper actions、file-request QR、录音全链路、Office preview、`alembic/versions/060_meeting_user_agent.py`，以及对应 Vitest/Playwright 测试。

#### C — `fix/drive-cleanup-and-mime-patch`

```text
badfdd08 feat(deploy): nginx mime.types 加 6 PWA MIME
35b549f1 feat(drive): v77 P2.6-G.3 缩略图 fallback + 空态 CTA
25ee858e feat(drive): 批量下载/分享 stub 实装
2aeae1ed fix(meeting): polish dispatch 走 LLMClient + cancel-recording 清 audio_url 字段 + 孤儿 audio_url 清理
9f9d1a25 fix(recording): 前端 recorder 全链路
ebe6726e fix(recording): post_meeting NameError + reminder scheduler + orphan cleanup 扩展
623e36c7 fix(recording): meeting recording 全链路
19b37be5 fix(drive): 修复 Office 在线预览 sandbox 黑屏
```

非 dist 重点：`FileCard.vue`、`FilePreviewDialog.vue`、`useDriveFiles.js`、`DesktopDriveView.vue`、批量下载测试、缩略图/空态 CTA、`scripts/deploy-auto.sh` MIME 注入，以及与 B/F 共用的录音链。

#### D — `fix/drive-selected-folder-ref`

当前 `main` 已包含其完整历史（`git merge-base --is-ancestor D main` 成功），所以 `git diff main...D` 为空。该 branch 不应再次合并或 cherry-pick。

#### E — `fix/office-preview-sandbox`

E 是汇总分支，包含三个关键 merge commit：

```text
ad15e1d3 merge: PR6-P17 schema 留尾 + voiceprint_relaxed 决策归档
  parents: 2aeae1ed + e40bd8ab

f2c7bd7a merge: 代码 TODO 实装 (embedding/paper/file-request/dist)
  parents: ad15e1d3 + ed1e03e8

e5d9ba5c merge: Drive 留尾 (批量 + 缩略图 + 空态 CTA + nginx MIME)
  parents: f2c7bd7a + badfdd08

f5715fd9 fix(dist): 重新 build 含 qrcode 包 + 同步 W3 paper/file-request 未 build 资源
```

E 相对 `main` 的 215 个路径包括 48 个非 dist 路径和 167 个 tracked dist 路径。它是当前最接近“可直接送审/合 main”的统一产物。

#### F — `fix/voiceprint-and-schema-cleanup`

```text
e40bd8ab fix(schema): PR6-P17 wechat_id Optional → required 与 DB NOT NULL 对齐
2aeae1ed fix(meeting): polish dispatch 走 LLMClient + cancel-recording 清 audio_url 字段 + 孤儿 audio_url 清理
9f9d1a25 fix(recording): 前端 recorder 全链路
ebe6726e fix(recording): post_meeting NameError + reminder scheduler + orphan cleanup 扩展
623e36c7 fix(recording): meeting recording 全链路
19b37be5 fix(drive): 修复 Office 在线预览 sandbox 黑屏
```

非 dist 重点：`app/schemas/member.py`、成员 NOT NULL 回归测试、录音全链路和 Office preview。其录音相关提交已被 E 的 `ad15e1d3` 吸收。

---

## 3. 6×6 冲突矩阵

### 3.1 标记说明

- **H* / 高**：多个 branch 改动同一路径，尤其包含 tracked `web/dist/**`；人工合并或 cherry-pick 有高概率留下旧 hash、重复产物或错误优先级。
- **M / 中**：同一业务逻辑由多个 branch 触及，但当前最终 blob 相同，或共享提交来自同一条祖先链；不代表当前会产生文本 conflict。
- **L / 低**：无共享 changed path，或一方已是另一方/`main` 的祖先。
- 矩阵按“原始 branch diff 重叠”标风险；实际 `merge-tree` 结果另列在 3.3。

### 3.2 矩阵

|  | A 产品规划 | B TODO/cache | C Drive/MIME | D selected-folder | E Office 汇总 | F schema |
|---|---|---|---|---|---|---|
| **A 产品规划** | — | L：0 overlap | L：0 overlap | L：0 overlap | L：0 overlap | L：0 overlap |
| **B TODO/cache** | L | — | **H***：26 shared paths，22 non-dist；3 个 dist blob 不同 | L：0 overlap | **H***：115 shared paths，41 non-dist；61 个 dist blob 不同 | **H***：26 shared paths，22 non-dist；3 个 dist blob 不同 |
| **C Drive/MIME** | L | **H*** | — | L：0 overlap | **H***：31 shared paths，27 non-dist；3 个 dist blob 不同 | **H***：116 shared paths，22 non-dist；1 个 dist blob 不同 |
| **D selected-folder** | L | L：D 已在 main | L：D 已在 main | — | L：D 已在 E/main | L：D 已在 main |
| **E Office 汇总** | L | **H***：E 已包含 B | **H***：E 已包含 C | L：D 已在 E/main | — | **H***：E 已包含 F |
| **F schema** | L | **H*** | **H*** | L | **H*** | — |

### 3.3 实际 merge-tree 结果

对 15 组 pair 执行：

```bash
git merge-tree --write-tree <branch-a> <branch-b>
```

结果全部返回 `0`，未出现 `CONFLICT`、`<<<<<<<` 或其他未合并状态。结论：

- **实际文本 conflict：0**。
- H* 是人工合并风险，不是 Git 已经无法自动合并。
- E 之所以可以作为汇总分支，核心原因是它已经在历史中通过 merge commit 记录了 B/C/F 的整合结果。

---

## 4. 冲突点详细 trace

### 4.1 录音/Office 共用逻辑簇（B/C/E/F）

以下路径被 B/C/E/F 同时带入，但最终 blob 均一致，主要源于共同祖先提交链，而不是四个 branch 独立改出四种实现：

- `alembic/versions/060_meeting_user_agent.py`
- `app/api/v1/meeting_recording.py`
- `app/config.py`
- `app/models/meeting.py`
- `app/services/meeting_ai_polish.py`
- `app/services/orphan_meeting_cleanup.py`
- `app/services/post_meeting_tasks.py`
- `app/services/reminder_service.py`
- `scripts/cleanup_orphan_meeting_audio.py`
- `web/src/components/AudioRecorder.vue`
- `web/src/composables/useGlobalRecorder.js`
- `web/src/components/drive/FilePreviewDialog.vue`
- `web/playwright.config.js` 及录音/Office regression specs

风险不是内容选择，而是如果将 B/C/F 的共同祖先提交再次逐个 cherry-pick 到已经含有该链的分支，会产生 empty cherry-pick、重复提交或误以为需要手工解决。

### 4.2 Drive 功能簇（C → E）

C 的 Drive 留尾包括：

- `FileCard.vue`：thumbnail fallback / 通用文件 icon / 空态行为关联
- `useDriveFiles.js`：批量下载及视图参数链
- `DesktopDriveView.vue`：批量分享/下载、拖拽空态 CTA
- `useDriveFiles.batch-download.test.js`
- `scripts/deploy-auto.sh`：6 类 MIME 的 `ensure_mime()`

E 的 `e5d9ba5c` 明确以 C 为第二 parent，将这些改动纳入汇总分支。不要再将 C 独立合入 E 或最终 main。

### 4.3 W3 TODO / paper / file-request 簇（B → E）

B 的功能包括：

- translation API/service
- embedding prompt/service
- `ParagraphActions.vue` / `TranslationPanel.vue`
- QR Code 与 file-request 预览
- `web/vite.config.js`、package lock 和 build timestamp

E 的 `f2c7bd7a` 以 B 的 `ed1e03e8` 为第二 parent，已完成吸收。再次 cherry-pick B 会重复 migration、测试和 dist 产物。

### 4.4 schema 簇（F → E）

F 的核心是：

- `app/schemas/member.py` 的 `wechat_id` required 对齐
- `tests/test_member_wechat_id_not_null.py`
- 与录音链共享的 060 migration 和测试基础设施

E 的 `ad15e1d3` 已将 F 与共同录音链合并。`060_meeting_user_agent.py` 在 B/C/E/F 中 blob hash 相同；只能在最终部署路径执行一次，不要因四个 branch 都列出该文件而生成四份迁移。

### 4.5 tracked dist 簇（B/C/E/F）

相对 `main` 的 dist 数量：

- B：166
- C：94
- F：94
- E：167

不同 branch 的 Vite hash 产物会表现为“旧文件删除 + 新 hash 文件新增”，即使源逻辑完全相同，也会制造大面积 diff。E 的 `f5715fd9` 是最后一次 qrcode/paper/file-request 同步 build，建议把它视为最终 dist 来源。

必须遵守：

```bash
cd web && npm run build
```

不要直接运行 `vite build`，也不要把 dist 单独提交。若最终 build 产生变化，应与对应源改动同一提交并按仓库规则 `git add -f web/dist/`。

---

## 5. 推荐合并顺序

### 推荐的一句话

> **先将 `fix/office-preview-sandbox` 作为已完成 fan-in 的唯一功能分支合入 `main`，跳过已包含的 B/C/F 和已在 main 的 D，最后独立合入 A 的 `ROADMAP.md`。**

### 具体顺序

1. **先清理/隔离当前工作树**：当前 `fix/office-preview-sandbox` 工作树存在 Self-RAG 删除、agent、测试数据和 dist 相关未提交改动；在主指挥决定如何处理前，不要对 `main` 做 merge。
2. **E → main**：确认 `main` 未新增提交后优先尝试 `git merge --ff-only fix/office-preview-sandbox`；若 main 已前进，使用一次受审查的 merge commit，不要拆成 B/C/F 多次合并。
3. **跳过 B/C/F**：它们已由 E 的 `ad15e1d3`、`f2c7bd7a`、`e5d9ba5c` 吸收。再次合并只会放大 dist 和共同录音文件的重复风险。
4. **跳过 D**：`fix/drive-selected-folder-ref` 相对 `main` 为零差异。
5. **A → final main**：对 `feature/product-expansion-planning` 只合入 `069fa5c0` 的 `ROADMAP.md`；推荐在 E 合入后单独 cherry-pick，避免旧分支历史拖入最终合并图。
6. **最终只 build 一次**：在最终整合后的代码上执行 `cd web && npm run build`，检查 hashed manifest、`index.html` asset 引用和 `sw.js` 不含 unhashed manifest。

### 不推荐顺序

- B → C → F → E：会重复合并 E 已包含的 ancestors。
- C → main 后再 E：会让 E 的 fan-in merge 变成重复内容处理。
- 逐个 cherry-pick 19b37be5、623e36c7、ebe6726e、9f9d1a25、2aeae1ed：这条共同录音链已存在于各分支，容易产生 empty commit/重复变更。
- 对每个 branch 单独重新 build 并提交 dist：会造成 hash 产物互相覆盖，无法判断哪个是最终 bundle。

---

## 6. 风险评估

### P0 / 高风险

1. **tracked dist 误合并**：167 个 E dist 路径是最大 diff 面积；旧 hash 被保留、新 hash 缺失会造成部署后 404/白屏。缓解：以 E 的最终 build 为唯一来源，最终只 build 一次，部署前做 dist 健全性检查。
2. **重复合并已吸收 branch**：将 B/C/F 再合入 E/main 会重复处理同一录音和 Drive 路径，人工 resolve 时可能选错 parent 版本。缓解：只合 E。
3. **当前工作树不干净**：当前分支有未提交 Self-RAG/agent/测试数据/前端改动，不能把它们混入 Drive 汇总 commit。缓解：主指挥先决定独立提交、stash 或另开 worktree；本任务不操作这些改动。

### P1 / 中风险

1. **同一 060 migration 在四分支出现**：blob 相同，不是四次迁移；部署/回滚只按一次 migration 处理。
2. **`FilePreviewDialog.vue` 的 Drive/Office 改动重叠**：C/F/B 都携带该文件，E 已确定最终 blob；继续 cherry-pick 时要避免把旧 sandbox 属性恢复。
3. **`scripts/deploy-auto.sh` MIME 逻辑**：C/E 共享该文件；最终应保留 E 的 MIME 逻辑，禁止在 server context 增加覆盖型 `types {}`。
4. **前后端录音链必须成套验证**：MIME fallback、5 秒 getUserMedia timeout、cancel endpoint、UA 落库、orphan cleanup、post-meeting task 不能只挑一个 branch 合入。

### P2 / 低风险

1. A 的 ROADMAP 只触及文档，可独立处理。
2. D 已在 main，重合并没有收益。
3. 共享源文件多数最终 blob 完全相同，正常使用 E 的 merge history 不会产生文本 conflict。

---

## 7. 用户/主指挥需要立即决策的阻塞点

1. **当前 dirty worktree 如何隔离**：Self-RAG 删除和 agent/benchmark 改动是否先单独 commit、stash，还是保留在当前分支直到另开 worktree？在此决定前不应把当前工作树直接送进 main。
2. **dist 最终来源**：是否确认以 E/f5715fd9 的最新 `npm run build` 产物作为唯一发布版本？推荐“确认”，拒绝逐 branch 拼接 dist。
3. **合并粒度**：是否确认只合 E，不再单独合 B/C/F？推荐“确认”；这是避免重复 conflict 的关键决策。
4. **A 的产品规划文档时机**：是否与 E 同一个 release，还是在 E 合入后独立 cherry-pick `069fa5c0`？两者无代码风险，推荐独立 cherry-pick，便于回滚。

---

## 8. 回归测试建议

### 8.1 合并前静态门禁

```bash
git diff --check
git grep -n -E '<<<<<<<|=======|>>>>>>>' -- app web scripts tests
git merge-tree --write-tree main fix/office-preview-sandbox
bash -n scripts/deploy-auto.sh
```

### 8.2 Drive/Office 定向测试

```bash
cd web
npx vitest run src/components/drive/__tests__/FilePreviewDialog.test.js
npx vitest run src/composables/__tests__/useDriveFiles.batch-download.test.js
npx vitest run src/components/drive/__tests__
```

当前已知基线：`FilePreviewDialog.test.js` 17/17、batch-download 3/3；`useDriveFiles.test.js` 中仍有 5 个测试按旧 axios mock 断言，而实现已使用 `fetch + URLSearchParams`，不要为通过旧测试回退线上修复。

### 8.3 录音/Schema/W3 回归

```bash
# 具体容器名按当前部署环境替换
docker exec <app> pytest \
  tests/test_member_wechat_id_not_null.py \
  tests/unit/test_embedding_service.py \
  tests/unit/test_translation_service.py -q

cd web
npx vitest run src/components/__tests__/AudioRecorder.test.js
npx playwright test \
  tests/visual/desktop/office-preview-sandbox-regression.spec.mjs \
  tests/visual/desktop/recording-cancel-rollback.spec.mjs \
  tests/visual/desktop/recording-harmonyos-ua.spec.mjs \
  tests/visual/desktop/recording-mime-fallback.spec.mjs
```

### 8.4 最终 build/PWA 门禁

```bash
cd web && npm run build

grep -oE 'assets/index-[A-Za-z0-9_-]+\.js' dist/index.html
find dist/assets -maxdepth 1 -name 'index-*.js' -print
test -n "$(find dist -maxdepth 1 -name 'manifest.*.webmanifest' -print -quit)"
! grep -qE '"url":"manifest\.webmanifest"' dist/sw.js
```

完整前端 Vitest 当前还有既有失败（`useDriveFiles` 旧 mock、`useNetworkStatus`、recorder timeout rejection），合并验收时应将这些单独修测试或在 release gate 中明确 baseline，不要将其误判为 branch merge conflict。

---

## 9. 最终报告摘要

1. **报告路径**：`docs/branch-merge-analysis-2026-07-20.md`
2. **冲突点总数**：按 pair-cell 口径 **6**；其中高风险 **6**。按真实 Git merge-tree 口径 **0 个实际 conflict**。
3. **推荐合并顺序**：`fix/office-preview-sandbox` → `main`；跳过 B/C/F 和已在 main 的 D；最后独立合入 A 的 ROADMAP。
4. **立即阻塞决策**：先确定当前 dirty worktree 的隔离方式、确认 E 的 dist 为唯一来源，并确认不再重复合 B/C/F。
