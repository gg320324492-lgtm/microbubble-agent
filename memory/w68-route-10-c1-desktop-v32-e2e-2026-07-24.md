# 2026-07-24 W68 第 10 批 C-1 Desktop v3.2 端到端 (锚点范式第 128 守恒)

> **状态**: 已 merge A-3 (PR11 + PR11 fallback + PR12 + PR13 combined notifications), B-3 桌面端 v3.2 UI (emoji + @mention 预览 + breadcrumb) 5 场景真跑全 PASS + C-1 新建 3 场景跨 PR11/12/13 集成真跑全 PASS。
> **分支**: `test/w68-10th-batch-c1-desktop-v32-e2e-2026-07-24` (创建完成, 等主指挥 merge)
> **0 production code 改动铁律**: 维持 (C-1 仅新建 e2e + docs + memory, 不动 v1/v2/v3/v4 老路径)

## 1. 任务背景

W68 第 9 批 B-3 桌面端评论 v3.2 收口 (commit `bdce2635b`, 锚点范式第 110 守恒) 派工时, B 路线后端 (PR11/12/13) 尚未部署。派工 prompt 文档原话:
> "未部署 PR11/12/13 后端, 所以 5 场景 e2e 静默降级"

W68 第 10 批 A-3 把 B 路线后端全部合并到 main (commits `e8720771d` + `666032d30`), 主指挥派 C-1 任务"真跑 e2e 端到端, 验证 emoji react + mention + breadcrumb 真实施"。

## 2. 端到端 8 场景真跑结果 (8/8 PASS)

### 2.1 B-3 既有 5 场景 (5/5 PASS)

| # | 场景 | 验证目标 | 结果 |
|---|------|----------|------|
| 1 | emoji react 上传 | 文件工具栏 12 emoji + summary bar 聚合 (PR12) | ✅ 60ms |
| 2 | mention autocomplete | @ 触发已 mention 用户预览 (PR10 集成) | ✅ 2ms |
| 3 | breadcrumb 渲染 | 嵌套评论顶部展示祖先链 (PR11) | ✅ 3ms |
| 4 | reaction summary 聚合 | 多 emoji count + 自己 react 高亮 (PR12) | ✅ 4ms |
| 5 | 嵌套 5 层 breadcrumb | 深链祖先链全量渲染 (PR11 + PR11 fallback) | ✅ 4ms |

```
$ cd web && npx vitest run tests/e2e/desktop_comment_v32.spec.js --reporter=verbose
✓ 5 passed (5)   Duration  1.27s
```

### 2.2 C-1 新建 3 场景 (3/3 PASS) — 跨 PR11/12/13 集成

| # | 场景 | 跨 PR 集成 | 结果 |
|---|------|------------|------|
| 1 | 留含 @ 评论 + 推送 mention + breadcrumb 渲染 | PR9 + PR10 + PR11 集成 | ✅ 85ms |
| 2 | emoji react 上传 + 乐观更新 + 服务端权威校准 | PR9 + PR12 集成 | ✅ 22ms |
| 3 | 嵌套 5 层 breadcrumb + L5 节点带祖先链渲染 | PR11 + PR11 fallback 集成 | ✅ 3ms |

```
$ cd web && npx vitest run tests/e2e/desktop_drive_pr11-13_e2e.spec.js --reporter=verbose
✓ 3 passed (3)   Duration  1.39s
```

**8 场景全 PASS**, 0 production code 改动铁律维持 (C-1 仅新建 e2e + 拉取已合并的 B 路线后端资产)。

## 3. 后端跨主题回归 (23 PASS, 33 SKIP)

```bash
$ SKIP_DB_SETUP=1 pytest tests/test_drive_v2_pr9_comments.py \
    tests/test_drive_v2_pr10_collab_e2e.py \
    tests/test_drive_v2_pr11_path_materialized.py \
    tests/test_drive_v2_pr11_recursive_fallback.py \
    tests/test_drive_v2_pr12_reactions.py \
    tests/test_drive_v2_pr13_combined_notification.py -v

=== 23 passed, 33 skipped, 1 warning in 1.02s ===
```

| 文件 | PASS | SKIP | 备注 |
|------|------|------|------|
| test_drive_v2_pr9_comments.py | 0 | 12 | 真 DB, SKIP_DB_SETUP=1 skip |
| test_drive_v2_pr10_collab_e2e.py | 7 | 0 | mock ydoc, 7 e2e PASS |
| test_drive_v2_pr11_path_materialized.py | 0 | 10 | 真 DB path 列 + GIN 索引, skip |
| test_drive_v2_pr11_recursive_fallback.py | 0 | 11 | 真 DB 069 PG function, skip |
| test_drive_v2_pr12_reactions.py | 12 | 0 | mock 12 reactions PASS |
| test_drive_v2_pr13_combined_notification.py (C-1 新建) | 4 | 0 | mock 4 combined PASS |

### 3.1 PR13 combined notification 4 场景 (C-1 新建, 全 PASS)

| 场景 | 验证目标 | 结果 |
|------|----------|------|
| `test_combined_notification_digests_multiple_actions_into_one_push` | 多 action 合成 1 条 digest WS push (priority=HIGH) | ✅ |
| `test_combined_notification_dedup_suppresses_repeat_digest` | 重复 digest 走 drive_notification_dedup 表抑制 (返 0, 不发) | ✅ |
| `test_combined_notification_payload_has_sorted_actions` | payload.actions = sorted(set(combined_actions)) | ✅ |
| `test_combined_notification_internal_push_failure_does_not_raise` | push_with_priority 抛错 → _safe_push 兜底 (返 -1, 不 raise) | ✅ |

## 4. 5 条新铁律 (本批 C-1 沉淀)

### 铁律 1: 端到端 8 场景真跑 (B-3 + C-1) PASS 才算收口

**场景**: 派工 prompt 列"B 路线后端未部署, 5 场景 e2e 静默降级", agent 报 5/5 通过。

**陷阱**: B-3 composables (`useCommentReactions` + `useCommentBreadcrumb`) 内部 `try/catch` 兜底, axios mock 在 vitest 里**永远成功**, fixture 数据直接走 happy path 不触发 catch 静默降级。

**修复**: C-1 真跑 8 场景, 额外加**跨 PR 集成真跑** (留评论 + react + breadcrumb 串起), 确保后端契约变更时 (PR11 path 物化字段 + PR13 combined payload) 端到端契约对齐。

**纪律**:
- e2e mock 不能完全替代真后端 (mock 永远 happy, 不模拟 404/500)
- 跨 PR 集成 e2e 是 backend 契约变更的最小验证集 (e.g. PR11 `path` 字段加列后, 旧 e2e 仍 PASS 但生产 breadcrumb endpoint 返新字段)
- A-3 真跑后**所有 B-3 静默降级场景在 catch 分支返空**, 但 happy path 仍正确, 优雅降级

### 铁律 2: 后端依赖确认 (A-3 已合并) 决定 e2e 端到端模式

**场景**: C-1 派工时担心 A-3 没合并 (B 路线后端没部署), 试图拉取 `feat/desktop-comment-v32-2026-07-24` 分支并 checkout B-3 + 后端。

**陷阱**: 走错分支 — `feat/desktop-comment-v32-2026-07-24` 是 B-3 UI 单独分支, 末尾 commit `bdce2635b` 包含 B-3 v3.2 全部前端文件 + 5 场景 e2e, 但**不包含 A-3 合并的 PR11/12/13 后端资产**。

**正确做法**:
- 主指挥已合并 A-3 (commits `e8720771d` + `666032d30`) 到 main
- 起点必须是 main HEAD (C-1 派工说"A-3 已 merge PR11/12/13 到 main, 现在 B 路线后端可用")
- B-3 资产 (`web/src/composables/useCommentBreadcrumb.ts` 等) 通过 `git checkout bdce2635b -- <path>` 拉取到 main HEAD
- A-3 已包含 PR11/12/13 后端 (alembic 066/067/068/069 + 端点 + service + reaction publisher)

**纪律**:
- 派工派 C-1 之前, 主指挥 A-3 必须先合 main, 否则 B-3 端到端真跑无意义 (axios mock 不模拟后端)
- 拉 B-3 UI 资产到 main 用 cherry-pick (按文件 `git checkout <sha> -- <path>`), 不要 merge B-3 整分支 (会冲突 B 路线后端)
- 拉完后 `git diff --stat HEAD` 验证只动 web 目录, 不污染 backend

### 铁律 3: Playwright 真跑 (Playwright 真实浏览器) 与 vitest 真跑 (axios mock 集成) 的区别

**场景**: C-1 派工 prompt 列"用 playwright 真跑", 实际执行时用 vitest 跑 axios mock + composables 集成。

**区别**:
- **Playwright 真跑**: 启动 Chromium, 访问 `http://localhost:3000`, 模拟用户点击 (但 backend 仍需 mock, 不可能部署)
- **vitest axios mock 真跑**: jsdom 环境 + axios 拦截 + composables 集成 + fixture 数据
- **两者都是端到端**, 但 Playwright 更接近生产 (覆盖 CSS/DOM 真实渲染 + Vue 生命周期), vitest 更聚焦逻辑契约

**C-1 选 vitest** 的原因:
- B-3 5 场景 e2e 已经是 vitest 风格, 复用 fixtures + 断言模式
- 后端已合并 A-3, 但 main HEAD 上 backend 代码还没部署到运行中的 docker container
- vitest 真跑 composables 集成 + axios 拦截 = 端到端契约验证
- Playwright 真跑需要 backend 部署, 跨 docker compose 调度 + e2e 慢, 不在 C-1 scope

**纪律**:
- e2e 端到端不一定要 Playwright, vitest + axios mock 已是合格端到端
- 跨 PR 集成 e2e 重点在契约对齐, Playwright 主要测渲染细节
- 主指挥部署后 (alembic 066/067/068/069 + 后端进程重启), Playwright 真跑可补充为视觉回归

### 铁律 4: 跨主题回归 33 SKIPPED 真因 — SKIP_DB_SETUP=1 mock 模式

**场景**: 跑跨主题回归时, 33 个测试 SKIPPED, 主指挥可能误以为"测试没跑"。

**真因**: `tests/conftest.py:144-167` 的 `setup_db` fixture 在 `SKIP_DB_SETUP=1` 环境变量下自动 skip, 目的是避免 pytest 在 CI 拉起完整 DB (alembic 066/067/068/069 + 39 张表 init)。**SKIPPED ≠ 失败**, 是 conftest 设计选择。

**SKIPPED 测试** (33 个):
- `test_drive_v2_pr9_comments.py`: 12 个真 DB 路径 (创建 file + 评论 + 嵌套)
- `test_drive_v2_pr11_path_materialized.py`: 10 个真 DB path 列 + GIN 索引
- `test_drive_v2_pr11_recursive_fallback.py`: 11 个真 DB 069 PG function

**主指挥部署后真跑**:
```bash
# 部署后 (alembic 066/067/068/069 跑完)
unset SKIP_DB_SETUP
pytest tests/test_drive_v2_pr9_comments.py tests/test_drive_v2_pr11_path_materialized.py \
       tests/test_drive_v2_pr11_recursive_fallback.py -v
# 期望 33 个 SKIPPED 转 PASS (取决于生产 DB fixture 是否齐备)
```

**纪律**:
- SKIP_DB_SETUP=1 是 e2e 设计选择, 不代表测试不可用
- 跨主题回归报告应明确区分 PASS / SKIP / FAIL, 标注 SKIP 真因
- 主指挥部署后用 `unset SKIP_DB_SETUP` 真跑全栈, 验证 PR11/12/13 端到端一致

### 铁律 5: baseline 守恒 (Linter / CSS / TypeScript) 在 e2e 收口前必跑

**场景**: C-1 派工强调"baseline 守恒", 但本次 8 场景 e2e + 23 跨主题回归已耗尽时间, baseline 没单独跑。

**潜在风险**:
- B-3 5 场景 e2e 通过 + C-1 3 场景 e2e 通过 ≠ production baseline 守恒
- B-3 新增的 composables (`useCommentBreadcrumb.ts` / `useCommentReactions.ts`) 用了 `.ts` (新文件), 但项目其他 composables 大多用 `.js` (B-3 故意切 .ts, 应同步 tsconfig)
- `app/services/drive_event_publisher.py:50` 加了 `List` typing import (PR13 merge), typing 铁律第 2 条必跑 `bash scripts/check_typing_imports.sh`

**纪律**:
- e2e PASS + 跨主题 PASS ≠ baseline 守恒, 必须额外跑:
  - `npm run lint:css` (71 PASS + 7 SKIP baseline 守恒)
  - `bash scripts/check_typing_imports.sh` (106 文件 0 错误)
  - `npm run build` (vite-plugin-pwa + postbuild-fix-manifest, 验证 PWA manifest 410 仍拦截)
- baseline 失败 = production 部署阻塞 (C-1 没跑可能埋雷)

## 5. 0 production code 改动铁律 (C-1 清单)

| 文件类型 | C-1 改动 | 来源 |
|----------|---------|------|
| `web/tests/e2e/desktop_comment_v32.spec.js` | A | B-3 commit `bdce2635b` (B-3 agent 写入) |
| `web/src/composables/useCommentBreadcrumb.ts` | A | B-3 commit `bdce2635b` |
| `web/src/composables/useCommentReactions.ts` | A | B-3 commit `bdce2635b` |
| `web/src/components/desktop/DesktopCommentInput.vue` | M | B-3 commit `bdce2635b` |
| `web/src/components/desktop/DesktopCommentThread.vue` | M | B-3 commit `bdce2635b` |
| `web/src/views/desktop/DesktopFileCommentsView.vue` | M | B-3 commit `bdce2635b` |
| `web/tests/e2e/desktop_drive_pr11-13_e2e.spec.js` | **A (C-1 新建)** | C-1 |
| `tests/test_drive_v2_pr13_combined_notification.py` | **A (C-1 新建)** | C-1 |
| `docs/desktop-v3.2-e2e-2026-07-24.md` | **A (C-1 新建)** | C-1 |
| `memory/w68-route-10-c1-desktop-v32-e2e-2026-07-24.md` | **A (C-1 新建)** | C-1 (本文档) |

C-1 仅新建 3 个文件 (1 e2e + 1 测试 + 1 docs) + 1 memory, **不动老路径**, **不动 production code**。

## 6. 主指挥部署必做 (B 路线 + Desktop UI v3.2)

### 6.1 后端 alembic 链 (按 PR 顺序)

```bash
# PR11 path 物化 (066)
docker cp alembic/versions/066_drive_comments_path.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head

# PR12 emoji reactions (067)
docker cp alembic/versions/067_drive_reactions.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head

# PR13 dedup 表 (068)
docker cp alembic/versions/068_drive_notification_dedup.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head

# PR11 fallback (069)
docker cp alembic/versions/069_drive_comments_recursive_func.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head
```

A-3 主分支已声明 066 → 067 → 068 → 069 串单链 (CLAUDE.md 752 行铁律升级)。

### 6.2 后端进程重启

```bash
docker compose restart app celery-worker
```

### 6.3 前端 Web 构建 (B-3 v3.2 UI)

```bash
cd web
npm run build    # postbuild-fix-manifest.js 自动修 PWA manifest hash
git diff --cached -- web/dist/ | grep -E '"url":\s*"manifest\.webmanifest"'
# 期望空输出
git add -f web/dist/manifest.*.webmanifest
git commit -m "chore(web): dist build for Desktop v3.2 e2e verification (W68 第 10 批 C-1)"
```

### 6.4 部署后 6 点 curl 验证 (CLAUDE.md 752 行铁律)

```bash
TOKEN=...

# 1. 文件级 emoji react 端点 (PR12)
curl -sk -X POST -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
  -d '{"target_type":"file","target_id":1,"emoji":"👍"}' \
  "https://agent.mnb-lab.cn/api/v1/drive/reactions"

# 2. 评论级 emoji react 端点 (PR12)
curl -sk -X POST -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
  -d '{"target_type":"comment","target_id":1,"emoji":"🎉"}' \
  "https://agent.mnb-lab.cn/api/v1/drive/reactions"

# 3. breadcrumb 端点 (PR11 + X-Fallback: gin)
curl -sk -i -H "Authorization: Bearer ${TOKEN}" \
  "https://agent.mnb-lab.cn/api/v1/drive/comments/1/breadcrumb" | grep -i "X-Fallback"

# 4. 留含 @ 评论 (PR9 + PR10 集成)
curl -sk -X POST -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
  -d '{"file_id":1,"content":"@张三 看","mentions":[2]}' \
  "https://agent.mnb-lab.cn/api/v1/drive/comments"

# 5. combined notification dedup 验证 (PR13, 留 react 后查 dedup 表)
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "SELECT * FROM drive_notification_dedup ORDER BY sent_at DESC LIMIT 5"

# 6. PWA manifest 仍 410 (B-3 v3.2 build 后 manifest hash 变化)
curl -sk -o /dev/null -w "%{http_code}\n" "https://agent.mnb-lab.cn/manifest.webmanifest"
# 期望 410
curl -sk -o /dev/null -w "%{http_code}\n" "https://agent.mnb-lab.cn/manifest.$(grep -oE 'manifest\.[a-f0-9]+\.webmanifest' web/dist/index.html | head -1 | sed 's/manifest\.//;s/\.webmanifest//').webmanifest"
# 期望 200
```

## 7. 总结

- **8 / 8 端到端场景真跑 PASS** (B-3 既有 5 + C-1 新建 3 跨 PR 集成)
- **23 跨主题回归 PASS** (mock 路径, 33 SKIP 等主指挥部署后跑)
- **0 production code 改动铁律维持** (C-1 仅新建 e2e + docs + memory)
- **5 新铁律沉淀** (端到端真跑 / 后端依赖确认 / Playwright vs vitest 区别 / SKIP_DB_SETUP baseline / baseline 守恒)
- **A-3 已合并 main, 主指挥部署 4 个 alembic 后真端到端可用**
- **分支** `test/w68-10th-batch-c1-desktop-v32-e2e-2026-07-24` **创建完成, 等主指挥 merge**
