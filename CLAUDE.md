# MicroBubble Agent - 项目上下文
> **2026-07-12 当前任务链**: 🆕 **P0-#1 + #1.5 + #1.6 v1+v2 五修收官 (5 commit 全 push origin/main)** = **P0-#1 `.env LLM_BACKEND=ollama 残留 → chat 全 Connection error`** (commit `20621c83`, 仅 `.env`+force-recreate) + **P0-#1.5 wrapper shape 不兼容 + mimo reasoning_content + intent_classifier max_tokens 3 重复合** (commit `9b908f50`, 4 文件 +263/-6) + **P0-#1.6 v1 `ensureSessionLoaded` 加 server fetch fallback 修 session 点击空白** (commit `65d4493b`, 4 文件 +128 + dist force-add) + **P0-#1.6 v2 修 orphan session `localStorage='[]'` 误判 cache hit** (commit `a687cee7`, 3 文件 +121 + dist force-add) + **本 commit (doc 同步)**. **P0-#1.6 v2 详细**: 用户报 `41条仍然看不全` 你好 session list 41 条但主区只看到 1 个欢迎语 + 0 条真实消息 → 根因 v1 修复把`'localStorage 有内容'`等同 cache hit, 但用户在修复前已缓存了 orphan 空数组 `'[]'`, v1 后永远不 fetch → **v2 修法**: 加 `serverFetchedSessions` Set **独立追踪**与 `loadedSessions` 解耦 (loadedSessions 防 SSE 增量覆盖, serverFetchedSessions 防重复 fetch) + cache hit 判定改用 `Array.isArray(parsed) && parsed.length > 0` (区分真实缓存 vs 空数组占位) → 端到端验证: vitest **12/12 PASS** (含 3 v2 回归 case: orphan '[]' 仍 fetch / 二次不重复 fetch / 真实内容不 fetch) + Playwright v2 回归 **`.bubble count: 41`** ✅ 与 server list count=41 完全一致 (修复前 v1 后 v2 前只渲染 38 条). **2 新铁律** (P0-#1.6 v2): ① **localStorage cache hit 判定必须看内容, 不能只看 key 存在** — `'[]'` 是 orphan 占位, 必须用 `Array.isArray(parsed) && parsed.length > 0` 区分; ② **cache hit + server fetch 是不同维度必须独立 Set 追踪** — `serverFetchedSessions` (是否真 fetch 过) 不能用 `loadedSessions` (是否在 messagesBySession 里) 替代, 两者语义完全不同. **完整修复链 v0 (只查 localStorage) → v1 (+fetchSessionFromServer) → v2 (+serverFetchedSessions)**. **memory**: [`memory/ensure-session-loaded-cache-hit-orphan-2026-07-12.md`](./memory/ensure-session-loaded-cache-hit-orphan-2026-07-12.md) (v2) + [`memory/session-load-server-fetch-fallback-2026-07-12.md`](./memory/session-load-server-fetch-fallback-2026-07-12.md) (v1). **完整 commit 链** `20621c83` → `9b908f50` → `65d4493b` (v1) → `a687cee7` (v2) → 当前 doc 同步.
> **2026-07-12 当前任务链 (续) — P0-#2 + 工作树整理**: 🆕 **P0-#2 chat-jump-to-top 按钮点击'来回跳动' v1~v4 五修收官 (5 commit 全 push origin/main)** = **v1 `position: sticky; bottom: 20px`** 修 ↑ 按钮 scrollTop>0 被卷出可见 (commit `494b2917`) + **v2 `&:active { transform: none; }` + `transition: none`** 修点击抖动反馈 (commit `c2b1e50a`) + **v3 60fps 用户视角验证** (4 Playwright spec real-user-flow / button-bouncing / final-verify / jump-to-top) + **v4 `transform: none !important; transition: none !important`** 防御 EP `<el-button>` active transform specificity (commit `da94ce74`) + **audit 收尾** (commit `43383798` 仅留 60fps 用户视角 spec `p0-2-bounce-recv2.spec.mjs` 146 行). **v4 端到端验证**: `p0-2-bounce-recv2.spec.mjs` Test 3 真实 click + mouse.down + 12×16ms = 60fps 采样, **delta = 0px** ✅ 按钮 y 位置完全稳定 (阈值 >4px 报失败). **5 新铁律** (P0-#2): ① **`position: sticky` 优于 `fixed`** (滚动容器内浮动按钮永远用 sticky + 容器布局, 不要 fixed + 视口定位 — 滚动视口变化 fixed 按钮会被卷走); ② **EP `<el-button>` 默认 active transform 必须显式禁用** (用 `transform: none !important; transition: none !important;` 强制覆盖 specificity battle); ③ **60fps 验证优于静态截图** (Playwright spec 必须 mouse.down + 16ms 间隔采样才能捕获瞬间抖动, 静态截图看不出); ④ **`!important` 不是 anti-pattern, 是 specificity battle 工具** (当第三方 UI 库样式 specificity 比你高, `!important` 是唯一可靠手段, 不要为了"代码洁癖"放弃); ⑤ **visual bug 修复必须 audit trail** (每次修复都留 Playwright spec + delta 阈值, 未来回归测试可重跑验证). **memory**: [`memory/p0-2-chat-jump-to-top-bouncing-2026-07-12.md`](./memory/p0-2-chat-jump-to-top-bouncing-2026-07-12.md). 🆕 **Playwright 验证截图清理 + `.gitignore` 永久排除** (commit `c154f5d5`, 1 .gitignore + 54 PNG 删除, 6.1MB) = **删除 54 个 PNG 截图** (7 历史 commit 来源: c2b1e50a / 0c1ed72c / e6b1ed64 / ff30e010 / 1dd92414 / 648b863b / bd00b692) + **`.gitignore` 加 `web/tests/visual/**/screenshots/`** 永久 glob 排除 (含 desktop/ + mobile/ + 未来子目录). **关键判断**: 这些 PNG 都是 `page.screenshot({ path: ... })` 写入临时输出 (不是 baseline 读取, Playwright 真正 visual regression baseline 在 `*-snapshots/` 目录), 删除不影响 spec 执行 — spec 跑时本地重新生成, 不入库. **5 新铁律** (PNG cleanup): ① **Playwright 截图不进 git** (`.gitignore` 永久排除 `web/tests/visual/**/screenshots/`, spec 跑时本地生成, audit 走 git history); ② **真正的 visual regression baseline 走 `*-snapshots/`** (别和临时 audit 截图混在一起); ③ **audit trail 在 commit message, 不在 PNG** (修复细节写在 commit body + memory, PNG 重新生成的成本远低于 git 体积膨胀); ④ **6MB PNG 看着小, 7 commit 累积就是隐患** (任何"先 commit 后面再清"的策略都会被遗忘, `.gitignore` 一开始就要加); ⑤ **`git rm --cached` + `.gitignore` 双管齐下** (只加 `.gitignore` 不删已 tracked 文件没用, 必须 `git rm` + commit 同步). **memory**: [`memory/playwright-screenshot-cleanup-2026-07-12.md`](./memory/playwright-screenshot-cleanup-2026-07-12.md). **完整 commit 链** `0c1ed72c` (test) → `494b2917` (v2 sticky) → `c2b1e50a` (v3 transform) → `da94ce74` (v4 !important) → `43383798` (audit 仅 spec) → `c154f5d5` (PNG cleanup).
> **2026-07-09 当前任务链 (本会话 6 commit 全部 push origin/main)**: 🆕 **Drive 全家桶全面美化收官** = **5 commit 链 (drive-view.css 1089 行 + 5 子组件改写 + 10 dialog 玻璃态 + MobileDriveView 镜像 + chip 化过滤) + 1 测试 commit (15/15 vitest PASS)**. 详见 [`memory/drive-view-beaute-2026-07-09.md`](./memory/drive-view-beaute-2026-07-09.md). 10 新铁律沉淀 (drive-view.css vs scoped 边界 / file_type data-type attr selector / aria-pressed chip 无障碍 / glass dialog 共享 backdrop / mobile 仅镜像不重构 / skeleton 数量列对齐 / 8 类 file-type color 不复用主色 / .drive-page 容器 fade-slide-up token / 单 import 共享样式表 / dark mode 自动跟随 var() token 翻转). Commit hashes: `295848d` (CSS + View) → `782c92b` (FileCard+Grid) → `0788f8b` (FolderTree+Toolbar+chip) → `196cd9e` (10 dialog 玻璃态) → `7d5bfb0` (mobile 镜像) → `04c7fd2` (15 vitest PASS).
> ---
> **2026-07-08 当前任务链 (上 1 班次 30 commit 全部 push origin/main)**: 🆕 **25+ bug 修复收官 + CLAUDE.md 拆分** = **4 P0 必修 (celery worker ImportError / 18 天无备份 / mimo 429 fallback / admin CLI closure bug) + 5 P1 必修 (placeholder 边界 / AudioRecorder title reactive / mention autocomplete 中文名 / 5s dedup+markRead / SSH tunnel onboarding) + 9 P2 必修 (file_mentions 孤儿 / dedup 保留首次 preview / 4 域 fan-out 前移 / dark token 化 / useCommentTree cycle / KB 脚本 / pgvector round-trip / restore PG 17 兼容) + 5 P3 修复 (pre-commit 跨 sh 兼容 / SW Background Sync 排除 SSE / console.warn / webhook query string / webhint / file type 颜色 token 化) + 1 CLAUDE 拆分 (新会话启动 -81% read)**. 详见 [CHANGELOG.md](./CHANGELOG.md) 顶部 [Unreleased] 段 + 总览 [`memory/2026-07-08-25-bug-fix-batch.md`](./memory/2026-07-08-25-bug-fix-batch.md). 13 条新铁律沉淀 (模块级禁止副作用 / async session 必须显式 commit / backend-level fallback 用临时 client / 内层循环不引用外层 closure / filter 字段统一 lowercase / dedup 查询不按 is_read / dedup 区分静态/动态 / tree 必须 cycle 检测 / PG UPSERT 两步法 / sh 脚本 grep 替代 case glob / SW 排除流式 / HTTP path urlsplit / CLAUDE.md < 150KB).
> ---
> **2026-07-03 当前任务链**: 🆕 **活动动态 + 会议模板管理 彻底删除 (commit f66a2120)** = **用户决策"模板管理 + 活动动态都没用", 前后端 100% 清理** — **活动动态 (前端全删, 后端保留 audit)**: ① `web/src/views/desktop/ActivityFeedView.vue` (死代码) ② `/activity` 路由 + NotificationBell `onViewAll` 跳转 + MobileCommandPalette "活动动态" 入口 ③ useNotifications store `activities` state + `fetchActions` + `ws.on('activity')` 4 处删除 ④ `app/api/v1/notifications.py` `GET /api/v1/activities` endpoint 删 ⑤ `activity_service.py` + `activity_events` 表 + 11 处 drive/comment/file_request audit log **保留** (防破坏审计) ⑥ 4 Playwright/Vitest 死代码测试删. **模板管理 (前后端全清)**: ① `TemplatesView.vue` + `TemplatesPanel.vue` + `MeetingTemplateDialog.vue` + `MeetingCreateDialog` 模板选择区 (5 emit + LongPressWrapper + MobileActionSheet + applyTemplate) ② MeetingView 第 2 个 tab + 5 个 handler (onSaveAsTemplate / onDeleteTemplate / onCloneTemplate / onToggleActive / onEditTemplate) + loadTemplates 删 ③ `app/api/v1/meeting_template.py` + schemas + service + model + 2 alembic migrations (016/038) + 2 tests 全删 ④ alembic 链修复: 017 跳到 015, 039 跳到 037 (跳过已删 revision, 现有 DB 升/降级保持一致) ⑤ `app/main.py` meeting_template router 注册删 + `app/models/__init__.py` MeetingTemplate 导入删. **TDZ 修复**: `MeetingCreateDialog` `watch(immediate: true)` 触发 callback 时 `form` ref 未初始化 → ReferenceError, 修法: form 声明移到 watch 之前. **测试**: vitest 530/533 PASS (3 pre-existing useNetworkStatus 与本修复无关, CLAUDE.md 已知). build 0 错误. stylelint 34 pre-existing 错误 (NotificationBell/StorageQuotaBadge/MobileFilePreviewSwipe/FileRequestSubmitView 4 文件 hex 颜色) 与本修复无关. token orphan 45 pre-existing (DesktopDriveView/FileDetailView/Mobile* 4 文件) 与本修复无关. **199 文件改动**: 27 删除 (5 桌面组件 + 2 桌面测试 + 4 后端 + 2 alembic + 2 后端测试 + 4 dist/ 残留 + 8 模板/活动测试) + 12 改 (4 桌面 + 2 alembic + 4 后端 + 2 css). **0 容器镜像重建 + 0 新依赖** (纯前后端清理, 30s webhook 自动 deploy). **6 新铁律**: ① **用户决策"功能没用" → 前后端 100% 删除纪律** (前端留死代码 = 用户每次进站看到残留 navigation 引诱, 后端留 endpoint = 永久死代码腐烂); ② **alembic 跳过已删 revision 必须直接改 down_revision** (不建 merge point, 不引入新 revision, 让链结构 1:1 反映已迁移的 DB 状态); ③ **TDZ 守护: `watch(immediate: true)` 之前必须先声明 ref** (Vue 3 setup 顺序敏感, sync 触发的 callback 不能依赖"下面"的声明); ④ **后端 audit log (activity_service.log) 跟前端 UI 独立** (删除 UI 不动 11 处 drive/comment/file_request audit 调用, 防止破坏 6 类操作的可审计性); ⑤ **通知 5 大同步位点** (Pinia state + WS handler + 后端 endpoint + navigation 引用 + MobileCommandPalette 命令, 任一不删都会留下半截死状态); ⑥ **同一 9 spec 多次出现时 vite-plugin-pwa manifest hash + long-press wrapper dark 覆盖一并清** (依赖项追随被删组件, 不留 orphan).
> ---
> **2026-07-03 当前任务链（次新）**: 🆕 **录音断网误报 4 件套收官 (P0 徽章文案 + P1 会议守卫 + v2.2 stale 容错 + v2.2 IDB 兜底)** = **2 commit 链修复用户截图 "已上传 2 / 2 片 但徽章仍显示网络已断开" 误报** — **链路端到端验证**: 280 chunks 200 OK 链路上传完美通畅 (会议 192 last_chunk_index=279/total_chunks=280). **Commit 1 (df75a9c4) 徽章 stale-chunk 容错**: `UploadStatusBadge.vue` 新增 `allUploaded = totalCount>0 && uploadedCount===totalCount` 事实级信号, `effectiveOnline = props.online || allUploaded.value`. 附带修 P0 隐藏 bug: `badgeClass/iconClass/message` 用 `!props.effectiveOnline` 但 effectiveOnline 是 setup() 局部 const, props 里没这字段 → 永远 undefined → `!undefined = true` → is-offline class 永远显示. 修法: 改用 `!effectiveOnline.value` (computed ref 访问). **Commit 2 (09320e20) IDB 兜底 + catch enqueue**: ① `idbStore.js` 新增 `getAllMeetingsWithPending()` 全表扫 chunks 聚合 meeting_id (O(N) < 10ms, 不升级 DB_VERSION) ② `useChunkedRecorder.handleChunk` catch 块在 5xx/网络错时主动 `uploader.enqueue(mid, [{chunk_index, blob}])` (enqueue 内部去重幂等) ③ `useChunkedUploader.onOnline` 双层扫描: uploadQueue Map 优先 + IDB 兜底 → Set 去重 → 各自 drainQueue. **测试**: 580/583 PASS (3 pre-existing useNetworkStatus 与本修复无关, CLAUDE.md 已知). idbStore.test.js 11→15 (+4), useChunkedUploader.test.js 14→17 (+3), UploadStatusBadge.test.js 新建 10. **5 新铁律**: ① **事实级信号 > 探测级信号** (allUploaded 强于 online, 任何 "展示当前状态" UI 适用); ② **`props.xxx` vs `xxx.value` 必须区分** (defineProps 字段 → props.xxx, setup 局部 ref → xxx.value, 混用导致 undefined 字段被 reactive 静默吞掉, 永远 falsy 触底); ③ **catch 失败必须同时 counter + IDB + queue 三处同步** (只 counter → 用户看到 "待重传" 但无人重传; 只 queue → UI 不知道有 pending); ④ **双层扫描是录音断网兜底必备** (in-memory 优先快 + IDB 兜底防漏网, Set 去重, 任何 "失败重试/同步/恢复" 场景适用); ⑤ **不要为完美牺牲向后兼容** (复合索引 → DB_VERSION 升级 → onupgradeneeded 触发 → 用户数据迁移风险, 当前 O(N) 全表扫 < 10ms 完全可接受, 性能留未来优化). **端到端验证**: 录音 5 秒 + 结束 → 等 30s → 徽章 "✓ 录音已安全保存" 绿色. throttling Slow 3G 录 30s → 切 No throttling → `dispatchEvent('online')` → 控制台 log `[uploader] 会议 X 有 N 片待传`. **6 文件改动**: 1 源码 + 1 测试 (Commit 1), 3 源码 + 2 测试 (Commit 2). **0 容器镜像重建 + 0 DB schema 变更 + 0 新依赖** (纯前端, 30s webhook 自动 deploy). **memory 沉淀**: `C:\Users\pc\.claude\projects\e--microbubble-agent\memory\v2-2-online-retry-idb-2026-07-03.md` (含 5 铁律 + 完整 commit 链 + 部署验证清单).
> ---
> **2026-07-03 当前任务链（次新）**：🆕 **14 行 placeholder 真实填入 (admin 后续手工) 决策记录** = **user 2026-07-03 决策: 'wechat id 其实现在已经不咋用了', placeholder 工具链 PR6-P18 已就绪但 admin 暂缓手工填值** — 业务上下文: `app/wechat/bot.py` 当前主要走 `chat_id` (群聊) + `external_userid` (微信互通外部用户) 路径, `app/wechat/identity.py:79 IdentityResolver.resolve_by_wechat_id()` 用 `Member.personal_wechat_id` 列 (line 83) **不**用 `Member.wechat_id` 列, `comment_service.py` mention 解析走 PR6-P4 三路匹配 wechat_id 优先级最低. 14 行 placeholder 当前**没被任何业务实际触及**, 填值的业务价值低. **admin 3 选项** (留作未来决定, 不阻塞任何功能): ① 不填 placeholder 永久保留; ② 用 `scripts/purge_test_user_data.py` 删 6 个测试账号 (id 59/116/117/118/299/300) → 14→8 行真实成员 admin 后续手工填; ③ 走 PR6-P18 工具链批量填值 (3 步: `--scan` 看清单 → 写 `id,wechat_id` CSV → `--apply --mapping <csv> --confirm`). **PR6-P18 工具链状态**: ✅ `scripts/fill_wechat_id_placeholders.py` (330 行, 6 项安全设计) + ✅ `tests/test_fill_wechat_id_placeholders.py` (20/20 PASS) + ✅ dry-run `--scan` 实测 14 行 placeholder 完整列出 + CSV 模板提示 + DRY RUN 二次确认门 (无 `--confirm` 不写库). **0 行代码改动** (admin 操作 task, 工具链已就绪). **新文件**: `docs/admin-followup-wechat-id-placeholders.md` (132 行, 14 行清单 + 3 步流程 + 6 项安全 + user 决策背景 + admin 3 选项 + 部署检查清单 + future follow-up PR6-P19+).
> ---
> **2026-07-03 历史任务链**：🆕 **v2 网盘 PR6-P18 fill_wechat_id_placeholders admin CLI 收官** = **PR6-P17 后 14 行 placeholder 真实填入工具 (admin 一次性操作, 0.5 天)** — **3 步范式 admin CLI**: ① `--scan` 列出 14 行 placeholder (8 真实成员 + 6 测试账号, id 8/17/22/24/25/26/27/58/59/116/117/118/299/300) + 打印 CSV 模板提示 → ② `--validate <csv>` 验证 CSV 合法性 (4 项检查: id 在 placeholder 列表 / CSV 内部 LOWER 唯一 / DB LOWER 不冲突 / 非空非 placeholder, 复用 PR6-P14 UNIQUE 约束) → ③ `--apply --mapping <csv> --confirm` 实际 UPDATE (单事务包裹 + 防御性 UPDATE WHERE `wechat_id LIKE '__NULL_BACKFILL_%'__` 防 admin 误改非目标成员 + DRY RUN 二次确认门与 migrate_kb_tags.py UX 一致). **14 行成员清单** (2026-07-03 psql): 8 真实 (董昊宇/李锐远/周之超/雒培媛-alumni/孟祥琪/吴怡霏/蒋芦笛/刘子煜) + 6 测试账号 (xiaoqi_testbot/Alice Drive Test/Bob/Charlie/pr1_temp_user/xiaoqi_testbot_2). **安全设计**: ① CSV 格式硬要求 (id,wechat_id 2 列 + 表头) ② id 必须在 placeholder 列表 (CSV 误填非 placeholder → skip) ③ CSV 内部 LOWER 唯一 (防 admin 误填同 wechat_id 两次) ④ DB 已存在 LOWER 冲突 (PR6-P14 UNIQUE INDEX 兜底, 防 CSV 误填与已有成员冲突) ⑤ defensive UPDATE WHERE (即使 id 在 placeholder 列表, UPDATE 0 行 + skip) ⑥ --confirm 二次确认门 (DRY RUN 强制). **结果**: 20/20 pytest PASS (3 scan + 6 parse_csv + 4 validate + 3 apply + 1 placeholder format + 2 argparse + 1 alembic 链同步) + 120 passed, 0 fail 合跑无回归 (PR6-P13 17 + PR6-P14 20 + PR6-P15 23 + PR6-P16 24 + PR6-P17 16 + PR6-P18 20 = 120) + `--scan` dry-run live 实测 14 行 placeholder 完整列出 + CSV 模板提示. **5 新铁律**: ① **admin CLI 工具必须 3 步范式** (scan/validate/apply --confirm, 与项目现有 migrate_kb_*.py 一致 UX, 不可逆写入必有 --confirm 二次确认门); ② **单事务包裹 + 防御性 UPDATE WHERE** (PR6-P14 UNIQUE 冲突 → IntegrityError → 整批 abort 不污染 DB); ③ **placeholder 格式必须 UNIQUE** (`'<PREFIX>_' || <unique_col>::text || '_<SUFFIX>'` 模式, 反例 placeholder='' 14 行 LOWER 重复 → UNIQUE 冲突); ④ **模块级 import 优于函数内 lazy import** (测试 patch `script_module.async_sessionmaker` 永远生效, 反例 lazy import 每次重新解析 SQLAlchemy 让 mock 失效); ⑤ **validate 步骤必须查 DB LOWER 冲突** (与 apply 共享同一 PR6-P14 UNIQUE 约束, 防 apply 时才发现 abort, 提前报告). **2 文件**: `scripts/fill_wechat_id_placeholders.py` (新, 330 行 3 步 CLI + PlaceholderMember/CsvMapping/ApplyReport dataclass + 6 项安全设计) + `tests/test_fill_wechat_id_placeholders.py` (新 350 行, 20 单测). **容器踩坑** (1 项, 沉淀铁律 4): 函数内 lazy import `from sqlalchemy.ext.asyncio import async_sessionmaker` 导致测试 patch `script_module.async_sessionmaker = lambda: async_session` 不生效, 真实 async_sessionmaker 绕过 mock → MagicMock engine 报 `AsyncMethodRequired` 错. 修法: 把 import 都移到模块级. **admin 使用流程**: ① docker exec --scan 看 14 行清单 ② 企业微信后台查 8 个真实 userid, 创建 `id,wechat_id` CSV ③ --validate 验证合法性 ④ --apply --mapping <csv> --confirm 实际写库 ⑤ 重新 --scan 期望 <14 行 (admin 决定填几个).
> ---
> **2026-07-03 历史任务链**：🆕 **v2 网盘 PR6-P17 wechat_id NOT NULL 防 NULL 渗透收官** = **14/35 行原 NULL 业务上不应有 (企业微信成员通常都有) → alembic 057 3 步迁移 (防 NULL 渗透)** — **3 步迁移**: ① backfill UPDATE 14 行 NULL 为唯一 placeholder `__NULL_BACKFILL_<id>__` (id 数字保证唯一性, 避开 PR6-P14 `ix_members_wechat_id_ci` UNIQUE 冲突) → ② ALTER COLUMN SET NOT NULL (PG 11+ 不需 rewrite table) → ③ verify RuntimeError sanity check (防 alembic silent fail). **结果**: 0 NULL / 14 backfilled / 21 real + `\d members` 显示 wechat_id `not null` + DB live 测试 INSERT NULL → `null value in column "wechat_id" ... violates not-null constraint`. **同步改动**: Member 模型 `Column(String(100), nullable=False)` (防 ORM INSERT NULL 提前) + API schema MemberCreate.wechat_id 仍 Optional (DB-only 防御, 业务决定留 PR6-P18). **现有代码 'or' pattern 不破坏**: task.py:90/129/133/188/192 + comment_service.py:116/302 全部 NULL-safe, 未来 14 行 placeholder → admin 真实填值后这些 pattern 仍 work (truthy string). 16/16 pytest PASS (4 alembic + 2 model + 3 backfill + 2 backward compat + 2 schema + 3 code patterns) + 108 passed, 9 skipped, 0 fail 合跑无回归 (PR6-P13 17 + PR6-P14 20 + PR6-P15 23 + PR6-P16 24 + PR6-P17 16 + drive_notification 8 = 108). **5 新铁律**: ① **加 NOT NULL 约束必须 3 步** (backfill UPDATE → ALTER COLUMN SET NOT NULL → verify RuntimeError, 反例直接 SET NOT NULL 报 "column contains null values"); ② **backfill placeholder 必须 UNIQUE** (反例 `UPDATE ... wechat_id=''` 多行 LOWER('') 都相同 → 触发 `ix_members_wechat_id_ci` UNIQUE 报错, 正例 `__PREFIX_<unique_col>::text` 数字列保证唯一); ③ **DB 层 NOT NULL + 模型 nullable=False 必须同步** (防 ORM `Member(wechat_id=None)` INSERT → IntegrityError 500 不明 error); ④ **placeholder 格式必须"语义清晰"** (admin 后续 cleanup 能 `SELECT * WHERE wechat_id LIKE '__NULL_BACKFILL_%'__'` 立即找出); ⑤ **NOT NULL 迁移后必须写 follow-up task** (alembic 文件 docstring 明确记录 "应用层 MemberCreate schema wechat_id: Optional → required (本次范围外, 留给业务决定) + 14 行 placeholder 需要 admin 真实填入 (本次范围外, 留给业务决定)"). **3 文件**: `alembic/versions/057_wechat_id_not_null.py` (新, 75 行 3 步迁移 + 注释 PR6-P17 + 未来 follow-up 列表) + `app/models/member.py` (改 3 行 `nullable=False` + 注释 PR6-P17) + `tests/test_member_wechat_id_not_null.py` (新 280 行, 16 单测). **revision ID `057_wechat_id_not_null` (21 chars, ≤32 VARCHAR 限制通过)**.
> ---
> **2026-07-03 历史任务链**：🆕 **v2 网盘 PR6-P16 external_userid case-insensitive uniqueness 收官** = **PR6-P15 模式复用价值体现 (4 个 identifier column 完整防御)**
> ---
> **2026-07-02 当前任务链**：🆕 **听会 v4 三件套修复收官 (drive_files RFC 5987 + useFolderDropZone native getter + MeetingRoomView AudioRecorder meeting-id)** = **中文文件名下载 + 文件夹拖拽层级 + 录音 chunked path meeting context** — **修复 1**: `app/api/v1/drive_files.py:build_content_disposition` RFC 5987 标准化 — 旧实现 `filename="中文.pptx"; filename*=UTF-8''<encoded>` 双 attribute, `filename=` 部分走 latin-1 codec, Starlette 调 `latin-1 encode` → `UnicodeEncodeError` → 500 (用户实测触发: "组会ppt/冯懿鑫/2025.7.2 研一 冯懿鑫.pptx"); 修复仅输出 `filename*=UTF-8''<encoded>` (RFC 5987 标准化形式), 现代浏览器全支持, 老 IE≤9 不支持但项目目标用户无 IE. 4 处调用点统一 (download_drive_file range + 完整 / batch_download_drive_files zip / public_download_by_token range + 完整). **修复 2**: `web/src/composables/useFolderDropZone.js` 删 `file.webkitRelativePath = relativePath` 错误赋值 — File.webkitRelativePath 是 native read-only getter, 赋值浏览器静默忽略, Firefox 拖拽场景 relativePath 全 undefined 文件夹层级丢失; 修复直接 entries 数组存 relativePath 字段. **修复 3**: `web/src/views/MeetingRoomView.vue` AudioRecorder 显式 `:meeting-id="meetingId"` + `:meeting-title="pageTitle"` — AudioRecorder 内部 lazy meetingId 是 computed, 不传 prop 时读不到值, chunked upload 路径触发后丢失 meeting context; 修复传 prop, chunked_filename 拼接正确. **commit**: `2cde346f fix(drive): 中文文件名 RFC 5987 编码 + useFolderDropZone native getter 修复 + MeetingRoomView AudioRecorder 传 meeting-id (听会 v4 三件套)`.
> ---
> **2026-07-02 当前任务链**：🆕 **v2 网盘 PR6-P14 mention wechat_id case-insensitive uniqueness 收官（已 commit `1c656075`）** = **PR6-P13 通用化, PR6-P4 mention 3 路匹配 wechat_id 优先同样有 map 撞车风险** — **3 层防御**: ① alembic 054 `UNIQUE INDEX ON LOWER(wechat_id)` 兜底真唯一 + ② service 重构 `_assert_username_unique` → `_assert_identifier_unique(column_name, value, exclude_member_id)` 通用 helper (反射 `getattr(Member, column_name)` + `frozenset({"username", "wechat_id"})` 白名单防 SQL 注入) + 旧 wrapper `_assert_username_unique` 向后兼容 (PR6-P13 17 单测无需修改) + ③ API POST/PUT /members 双保险预检查 wechat_id + 实际数据 0 冲突 (psql 验证 21 行非空 wechat_id 全部 case-insensitive 唯一) + 20/20 pytest PASS (7 generic helper + 3 create + 4 update + 1 backward compat + 3 alembic + 2 mention 回归) + 45 passed, 9 skipped, 0 fail 合跑无回归 (PR6-P13 17 + PR6-P14 20 + drive_notification 8 = 45). **5 新铁律**: ① **PR6-P13 通用化反射 + 白名单** (避免两个 helper 重复 90% 代码, 未来加 personal_wechat_id 只改 1 处白名单); ② **column_name 必须白名单, 绝不接受任意列名** (防 SQL 注入 + 防止 password_hash 等敏感列被误用, ValueError); ③ **反射 `getattr(Member, column_name)` 而非硬编码 if-else** (1 行替代, 未来加 column 不用改 helper); ④ **中文 label 走 if 分支 + 错误走 `resource=` 字段** (ConflictException 不支持 details= kwarg, 反例 TypeError 500, 正例塞进 message + resource); ⑤ **PG 函数索引 NULL 不参与 UNIQUE 约束** (无需额外 NULL 检查代码, 直接靠 PG 行为, service 层空值跳过仅省 1 次 SQL). **4 文件**: `alembic/versions/054_member_wechat_id_ci_unique.py` (新, 50 行直接 CREATE UNIQUE INDEX `ix_members_wechat_id_ci ON LOWER(wechat_id)`, 旧版无 wechat_id 索引无需 drop) + `app/models/member.py` (改 1 行注释 PR6-P14) + `app/services/member_service.py` (重构 `_assert_username_unique` → `_assert_identifier_unique` 通用 helper + create/update 检查 wechat_id, 旧 wrapper 保留向后兼容) + `app/api/v1/member.py` (POST/PUT 都改用 `_assert_identifier_unique`) + `tests/test_member_wechat_id_ci_unique.py` (新 20 单测).
> ---
> **2026-07-02 历史任务链**：🆕 **v2 网盘 PR6-P13 mention username case-insensitive uniqueness 收官** = **comment_service mention 解析用 `username.lower()` 防"Alice" vs "alice" 撞 map** — **3 层防御**: ① alembic 053 `UNIQUE INDEX ON LOWER(username)` 兜底真唯一 + ② service `_assert_username_unique` case-insensitive 查询 + ConflictException 409 (排除自己 update) + ③ API POST/PUT /members 双保险预检查 + Member 模型 `unique=True` 摘除 (移交索引) + 实际数据 0 冲突 (psql 验证 24 行种子 + admin 全 lowercase, 迁移无需数据修复) + 17/17 pytest PASS (5 service + 3 create + 3 update + 2 model + 2 alembic + 2 mention 回归保护) + 25/25 无回归 (`test_members.py` 6 SKIPPED 是 SKIP_DB_SETUP 模式, `test_drive_notification_trigger.py` 8 PASS + 3 skipped) + DB live 测试 `INSERT TestCIRestriction + testcirestriction` → `duplicate key value violates unique constraint "ix_members_username_ci"` 验证兜底. **5 新铁律**: ① case-insensitive 查询必须用 PG 函数索引 (`UNIQUE INDEX ON LOWER(username)`), 不能只 query 时 LOWER(); ② **`ConflictException(message, resource=...)` 不接受 `details=` kwarg** (反例 TypeError 500, 修法塞进 message/resource); ③ DB / Service / API 3 层防御, 任 1 层漏另 2 层兜底; ④ update 自己 username 必须 `exclude_member_id` 排除自己 (防"改自己撞自己"假冲突); ⑤ 多 NULL/空 username 必须允许 (PG UNIQUE 默认 NULL 不参与, service 空 username 跳过). **5 文件**: `alembic/versions/053_member_username_case_insensitive_unique.py` (新, 删旧 case-sensitive + 建 `LOWER(username)` 函数索引) + `app/models/member.py` (改 1 行: `unique=True, index=True` → `index=False`) + `app/services/member_service.py` (新 `_assert_username_unique` static method 35 行 + create/update 集成) + `app/api/v1/member.py` (POST/PUT 预检查替换旧 case-sensitive SELECT) + `tests/test_member_username_ci_unique.py` (新 17 单测).
> ---
> **2026-07-02 历史任务链**：🆕 **LLM 3-Way Benchmark (mimo cloud vs qwen3:8b vs qwen3:14b) 收官** = **本地 ollama 部署 + qa-bench 35 题 + 10 题 subset 公平对比** — **结果 (10 题 subset)**: mimo openai_compat (云) **50%** (5/10) = qwen3:8b (本地) **50%** (5/10) ≈ **平局**, 加权综合分 mimo 0.937 > 8b 0.906 (3% 差距, 主要在 tool/content 维度). **35 题完整**: mimo 14.3% > 8b 11.4% (2.9% 差距). **qwen3:14b (9.27GB Q4_K_M, 14.8B params)**: 单题 40-230s (8b 的 5-10×), 80% 题 duration_too_long, 通过率反低 30% — **不适合实时对话, 推荐离线 batch (知识库生成/长文润色)**. **7 维评分对比 (10 题)**: 8b **intent 0.70** > mimo 0.50 (+20%); mimo **tool 1.00** > 8b 0.90 (+10%); mimo content 0.97 vs 8b 0.91 (+6%); perf 0.96 vs 0.88 (+8%); defense/rich/consistency 都 1.00. **mimo 35 题发现 3 大问题**: ① fake_xml_leaked 3/35 (8.6%) `<function=...>` XML 模板泄露给用户 ② duration_too_long 2/35 (5.7%) thinking 超过 60s ③ intent_mismatch 27/35 (77%) prompts.py intent 分类对所有 LLM 都不友好. **8b 优势**: ① defense 1.00 (无 fake XML) ② 不依赖 mimo rate limit ③ 5.2GB VRAM 16GB 显卡可装. **最终决策**: **生产保持 LLM_BACKEND=openai_compat (mimo cloud)**, 8b 作 offline fallback. **7 新铁律**: ① **clash 代理必需** (registry.ollama.ai GFW 阻断 0KB/s, 加 HTTP_PROXY env 后 9MB/s); ② **docker run 路径必须 `MSYS_NO_PATHCONV=1`** (Git Bash 翻译 `E:\` 为 `C:\Program Files\Git\`, bind mount 失败, ollama pull 写到容器内 `/root/.ollama` 5GB 数据丢失); ③ **Ollama `--network host` 在 Docker Desktop Windows bind IPv6 only**, 必须 `-p 11434:11434` IPv4 NAT 转发; ④ **`docker compose restart` 不重读 env_file**, 切 backend 必须 `stop && up -d`; ⑤ **qwen3:8b 是 cloud 备选不是替代品** (速度 ≈ cloud, 通过率平局, 但 tool 维度弱); ⑥ **qwen3:14b 慢 4× 且通过率反低** (thinking 重, 实时不用, 离线 batch 推荐); ⑦ **mimo openai_compat 3 大待修** (fake_xml_leaked / duration_too_long / intent_mismatch, 后端加固 `_strip_fake_tool_calls` + synthesis max_tokens 限制 + prompts.py intent few-shot). **5 文件**: `docs/llm-benchmark-2026-07-02.md` (新, 聚合报告) + `app/core/llm.py` (流式 dispatch `_OAIStreamShim/_OAIEventShim` 之前会话已改) + `app/core/tool_call_converter.py` (qwen3 thinking reasoning 跳过) + `tests/qa-bench/results/{local-ollama-qwen3-8b,cloud-mimo-openai-compat,local-ollama-qwen3-8b-10q,cloud-mimo-openai-compat-10q}-2026-07-02/` (4 个 benchmark 报告) + `memory/llm-benchmark-2026-07-02.md` (新, 7 铁律).
> ---
> **2026-07-02 历史任务链**：🆕 **WebSocket 502 事故根因沉淀 + frps systemd 守护收官（commit `3fbe1b21`）** = **cloud nginx → frps → local FastAPI WebSocket 链断 2h** 排查 + 修复 — **(a) 根因**: frps 主进程自杀 (`client exit success` 日志) → 派生 worker 仍占 8000/2222/9000 (孤儿状态, `lsof` 看像 `sshd` 误诊 30 min) → nginx proxy_pass 给孤儿 worker → worker 转给 cloud localhost:8000 (空) → tcp RST → 502; **`lsof -i :8000` 必须看进程完整 cmdline (frps 派生的 worker 在 `ss` 里显示为 `sshd` 因为是 Go net 包 fork) + 必须看 `/var/log/frps.log` 时间戳确认 frps 还在不在**; **(b) 修复**: `kill -9 <stale_pid>` 释放孤儿端口 + `setsid frps -c ...` 后台启动 + verify `curl /api/v1/auth/me` 返 `401` 不再是 `502`; **(c) 永久守护**: 新增 `scripts/frps.service` systemd unit (Restart=always, RestartSec=5) + `scripts/install-frps-systemd.sh` 一键部署脚本 (kill stale + cp unit + enable --now + verify 7000/7500/8000/2222/9000 listener) — 端到端验证: `systemctl status frps` active + cloud 7000 + 派生 worker 8000 + `curl https://agent.mnb-lab.cn/api/v1/auth/me` 返 401 (backend alive). **5 新铁律**:① **`lsof -i :8000` 看进程是 `sshd` 时 99% 不是真 sshd,是 frps 派生 worker** (frps 用 Go 启 transport listener,`ss`/`lsof` 显示 cmdline "sshd" 是 Go 进程的 fd 标签)— 永远用 `cat /proc/<PID>/cmdline` 验证; ② **frps 必须 systemd 守护, 禁止 `nohup ... &`** (SSH shell 一关 frps 跟着挂, 然后派生 worker 孤儿占端口, 永远不会被自动 reap); ③ **stale tunnel worker 必须 `kill -9`** (普通 SIGTERM 杀不死 Go 协程持有的 fd, 手动 lsof + kill 才释放 listen port); ④ **判断 frp 隧道状态优先看 `/var/log/frps.log` 时间戳** (nginx error log 报 502 时, 第一件事查 frps log, 不是 sshd, 不是 frpc); ⑤ **后续 install-frps-systemd.sh 必须先 kill stale frps 再 enable new unit** (否则 systemd 拒绝 enable: address already in use). **完整 memory**: `frps-systemd-postmortem-2026-07-02.md`.
> ---
> **2026-07-02 历史任务链**：🆕 **v2 网盘 PR6-P12+ drive_service 触发 notification_service (star/share/upload owner) 收官** = **`drive_service` 3 个 hook 点 (create_file upload + toggle_star_file star + create_share_link share) 触发 `notification_service.create_mention`** — 复用 PR6-P8 已存在的 5 context 模板 (`comment`/`reply:N`/`star`/`share`/`mention`) + 0 行 notification_service 改动 + 复用 PR6-P7 dedup (5s) + 复用 PR6-P8 rich title/body. **关键设计**: self-notification skip 守卫 (`if owner_id != uploader_id`) 防噪音 + best-effort try/except (notification 失败不阻塞主流程) + unstar 不通知 (避免取消收藏骚扰) + context 字符串严格匹配 _build_title_body 模板. **当前 PR1 全场景自通知 skip** (created_by == current_user_id 恒等, 3 个 hook 都走 if 守卫), 未来 PR3 "team 协作" 扩展时 (其他用户 star/upload/share) 自动启用跨用户通知. 8/8 pytest PASS (3 skipped 留给 PR3 未来扩展). **5 新铁律**:① notification hook 必须 best-effort try/except + logger.debug (失败不阻塞 drive 操作); ② self-notification 必须 skip (if owner != current_user_id, 避免"您收藏了您的文件"噪音); ③ 复用 notification_service.create_mention static method (不要新写 send 函数, 自动获得 dedup + rich title/body); ④ action 切换型 hook (toggle star/share) 必须仅正向触发 (unstar 不通知); ⑤ context 字符串必须与 _build_title_body 模板一一对应 (`star`/`share`/`mention`, 不用"收藏"等自由文本). **commit**: `51c060a5 feat(drive): v2 PR6-P12+ drive_service 触发 notification_service (star/share/upload owner)`. **完整 memory**: `v2-drive-pr6-p12-notification-trigger-2026-07-02.md`.
> ---
> **2026-07-02 历史任务链**：🆕 **v2 PR6-P12+ drive_cleanup_tasks 拆 service 函数收官**
> ---
> **2026-07-02 历史任务链**：🆕 **v2 PR6-P11+ 增量 restore_from_backup.py --upsert ON CONFLICT DO UPDATE 收官** = **`--upsert` bool flag 切 INSERT ON CONFLICT DO UPDATE 模式** — 行已存在时用 backup 数据覆盖 (而非 DO NOTHING 跳过) + PG `rowcount` 区分 INSERT(1) / UPDATE(2) / SKIP(0) + 主键列不 SET (PG 自动 skip) + `--upsert` 缺 `--columns` ⚠️ 警告 (不强制失败, 全字段恢复场景允许) + `--upsert + --columns` 完美打补丁 (UPSERT partial 语义, 只 UPDATE 指定列) + `--table` + `--upsert` + `--columns` 三连组合 (跨表 + 覆盖 + 部分字段) + `print_scan_summary` 显示 "冲突策略" 行 + `restore_from_backup` 加 `upsert: bool` 参数 + 计数器 `inserted_count / updated_count / skipped_count` 三态区分 + 49/49 pytest PASS (37 旧 + 12 新 TestRestoreUpsert class). 5 场景 sanity check 全过: ① 默认 DO NOTHING 标识 + "即将恢复" ② --upsert 单独 ⚠️ UPSERT + ⚠️ 缺 --columns 警告 + "即将 UPSERT" ③ --upsert + --columns 完美打补丁 (无警告) ④ --upsert + --table + --columns 三连 4 层 ⚠️ 并存 ⑤ --upsert + 缺主键 fail fast. **6 新铁律**:① `--upsert` 是 boolean flag (`store_true`), 不需要参数值 ② PG `rowcount` 在 DO UPDATE vs DO NOTHING 模式下语义不同, 必须分别处理 (UPDATE=2, INSERT=1, SKIP=0) ③ 主键列不 SET (PG 自动 skip), UPDATE SET 可以安全列所有非 PK 列 ④ `--upsert` 缺 `--columns` 时给 ⚠️ 警告但不强制失败 (全字段恢复场景允许) ⑤ `--upsert + --columns` = 完美打补丁语义, 强烈推荐 (只 UPDATE 指定列, 其他列保留 DB 当前值) ⑥ DO NOTHING 是默认行为, 向后兼容 PR6-P10+ (1 改动即破坏向后兼容, 必须显式 flag). **commit**: `4067aee5 feat(restore): v2 PR6-P11+ restore_from_backup.py --upsert ON CONFLICT DO UPDATE`. **完整 memory**: `v2-drive-pr6-p11-upsert-flag-2026-07-02.md`.
> ---
> **2026-07-02 历史任务链**：🆕 **v2 PR6-P10+ 增量 restore_from_backup.py --columns 部分字段 UPSERT 收官** = **`--table` 覆盖 JSON 内 `table_name` 字段** — 4 合法选项 fail fast (`chat_sessions / file_mentions / drive_files / folders`) + mismatch 必打 ⚠️ 警告 + scan summary 显示 "覆盖自 JSON 原始 table_name=..." + `print_scan_summary` 加 `original_table_name: Optional[str]` 参数 + `restore_from_backup` 加 `payload: Optional[dict]` 参数 (避免重 load 丢 in-memory 覆盖) + 26/26 pytest PASS (18 旧 + 8 新 TestRestoreFromBackupTableFlag class). 4 场景 sanity check 全过: ① 默认无 --table ② --table=folders 覆盖 file_mentions ⚠️ ③ --table=invalid_name fail fast 列合法 ④ --table=file_mentions 与 JSON 相同静默. **5 新铁律**:① `--table` 必须在 BACKUP_TABLE_TO_ORM 里, fail fast 列合法选项 ② mismatch 必打 ⚠️ 警告 (不静默, 防静默改目标表导致事故) ③ in-memory 覆盖不写回 JSON 文件 (不污染原备份) ④ `restore_from_backup` 必须接 `payload` 参数 (避免重 load 丢覆盖) ⑤ 跨表恢复 items 字段不匹配时 INSERT 失败, 走 try/except skipped_count (不 panic, 整批不被 1 条异常 abort). **commit**: `15c94645 feat(restore): v2 PR6-P10 增量 restore_from_backup.py --table 显式指定`. **完整 memory**: `v2-drive-pr6-p10-restore-table-override-2026-07-02.md`.
> ---
> **2026-07-02 晚班 收官 历史任务链**：🆕 **qa-bench Smart Filter Round 9 收官** = **3 类数据 bug 修复 + 3 组工具语义等价 + severity=warn/info 不阻塞 verdict** — Round 8 (BGE m3 + openai_compat 200 题) verdict 0 PASS / 1 WARN / 13 FAIL / 186 ERROR, 排查发现 13 FAIL 全是 qa-bench 数据 bug 不是 LLM 真错. **3 类数据 bug**: ① forbid_names ∩ must_contain_any 必然 fail (Step 1 已修 severity=warn) ② forbid 名字在 query 里 (如"王天志的导师是谁?" 必然提王天志, 不是 hallucination) ③ 题型是"列出/所有/多少/谁在做" 答案必然列成员. **3 组工具语义等价**: query_members ↔ get_member_profile / query_tasks ↔ query_member_tasks / search_knowledge ↔ web_search (LLM 经常调更精准的单成员查询, 不应判 missing_tools). **severity 三层**: info 永远不阻塞 verdict + 不计入 7 维 defense 扣分 / warn 不阻塞 verdict (data_bug 标识) / fail 默认阻塞 (真问题). **验证**: 13 FAIL 重评估 → 0 FAIL (-13) + 4 PASS / 10 WARN, 13/13 单测 PASS (4 工具语义 + 5 forbidden 智能 + 1 severity + 3 helper). **3 新铁律**: ① 数据 bug severity=warn/info 永远不阻塞 verdict (qa-bench 是评测工具, 不让数据 bug 污染 LLM 真实能力评估) ② 工具语义等价是双向映射 (LLM 选任何一端都应满足 expect) ③ listing_question 关键词不能太宽 (避免"真引用单成员名"被误判). **commit**: `7e282f00 fix(qa-bench): Round 9 智能过滤`. **完整 memory**: `qa-bench-smart-filter-round9-2026-07-02.md`.
> ---
> **2026-07-02 晚班 收官 历史任务链**：🆕 **qa-bench smoke 30 题 cloud 真实跑 收官** = **Round 9 修复在生产环境验证** — cloud nginx 401 OK (frps systemd postmortem 修好) + SSE 200/29.7s/73330bytes (SSE 流稳定). **smoke 30 真实跑**: raw verdict **3 PASS / 13 WARN / 13 FAIL / 1 ERROR** (10.0% 通过率) + 加 query_all_member_tasks 工具语义等价后重评估 **5 PASS / 15 WARN / 9 FAIL / 1 ERROR** (13 FAIL → 9 FAIL, -4). **关键发现**: ① A 类成员查询 Round 9 修复有效 (6 题 4 PASS/WARN, 2 FAIL 都是 duration/data_bug 已修) ② B 类任务查询发现新工具 `query_all_member_tasks` (Round 9 之前没观测到) → 加 4 个新语义等价 (query_all_member_tasks / query_my_tasks ↔ query_member_tasks ↔ query_tasks) ③ **8 题 LLM 真没调工具 (empty tools_called)**, Round 9 修复无效, 是 LLM 决策问题 (intent_classifier + plan_step 改进方向). **14/14 单测 PASS** (新增 Case 2b). **commit**: `00193881 fix(qa-bench): Round 9 smoke 30 + query_all_member_tasks 语义等价`. **完整 memory**: `qa-bench-smoke-30-2026-07-02.md`.
> ---
> **2026-07-02 早班 历史任务链**：🆕 **v2 PR6-P12+ 守卫交互式 prompt (stdin y/n 确认) 收官** = **友好版 `confirm_retention_param` 从"延迟 + 无条件放行"升级为"延迟 OR [y/N] prompt"** — `settings.GUARD_INTERACTIVE_PROMPT_ENABLED` 默认 False 向后兼容 PR6-P11 + `GUARD_INTERACTIVE_PROMPT_TIMEOUT_SEC=30s` 防无限阻塞 + `_prompt_yes_no` 三层兜底 (isatty 兜底 / select timeout / Windows input() fallback) + `prompt_used` 字段标识路径 + 58/58 pytest PASS (29 旧 + 29 新 5 classes) + 容器后台 stdin 非 tty 永远 fallback sleep, Celery beat `.delay()` 永不阻塞. **5 新铁律**:① isatty() 永远第一行检查 ② select() timeout 是 prompt 超时唯一可靠方式 (Windows 抛 OSError → input() fallback) ③ 三返回值 (True/False/None) 严格区分语义 ④ prompt 路径与 sleep 路径并存, settings 开关控制 ⑤ 用户选择必走 logger.warning 留 audit trace. **commit**: `a7673ca1 feat(cleanup_safety): v2 PR6-P12+ 守卫交互式 prompt`. **完整 memory**: `v2-drive-pr6-p12-interactive-prompt-2026-07-02.md`.
> ---
> **2026-07-02 早班 历史任务链**：🆕 **v2 PR6-P10 backup_before_delete helper + restore_from_backup.py CLI 收官**（7 文件 + 18 单测 / +670 行 / 净 +550 行）= **3 个 Celery cleanup schedule (chat_history/drive_cleanup/file_mention) 全部加 backup 机制 + standalone restore CLI 可单条重 INSERT**。PR6-P9 事故根因修复 (本人误传 retention=0 删 31 条)。**设计**:helper 函数而非装饰器 (3 service SQL 拼装不一致) + 统一签名 `execute_backup_then_delete(db, model, where_clause, table_name, extra_metadata)` + `settings.BACKUP_BEFORE_DELETE_ENABLED=True` 默认开启 + `/tmp/celery_cleanup_<table>_<ts>.json` 备份文件。**restore CLI**: `--scan` 无副作用 + `--apply --confirm` 二次确认门 + `INSERT ON CONFLICT (id) DO NOTHING` 安全恢复。**5 新铁律**:① 任何 DELETE 类操作必有 backup_before_delete 机制 ② 备份失败必须抛异常 (保守策略, 不让无备份的 DELETE 发生) ③ 备份 JSON 必须含完整字段 (datetime ISO + nullable 保留) ④ restore 必须 INSERT ON CONFLICT DO NOTHING (不是 REPLACE, 防止二次事故) ⑤ 备份文件名约定 + docker cp 提示必带。**端到端验证**:pytest 18/18 PASS + 回归 16/16 + celery worker [tasks] 列表含 3 个 cleanup task + 故意造 40 天前 mention → 跑 task → 写 JSON 备份 → restore --apply --confirm 真恢复 id=101 完整字段 → DB 验证。
> ---
> **2026-07-02 早班 历史任务链**：🆕 **v2 PR6-P9 file_mention 30 天清理收官**（5 文件 + 9 单测 / +130 行）= **Celery beat 86400s 调 + NullPool 独立 engine 范式 + 一刀切 created_at 清理**。本人验证时**误传 retention_days=0 误删 31 条生产 file_mentions 数据**,用户决策"接受丢失"。**5 新铁律**:① DELETE 类必须 3 段式 (scan → 人审 → apply + --confirm) + JSON 备份 (本次违反,留 PR6-P10+ 改) ② Celery task retention ≤ 0 必须二次确认或禁用 ③ 容器内 destructive task 验证前必跑 SELECT count ④ 任何批量物理删除必须留 backup_before_delete 机制 (chat_history/drive_cleanup/file_mention 3 个 schedule 全要补) ⑤ Celery beat schedule 名称 + frequency + 备份 owner 必须文档化 (本次 3 schedule 全无备份⚠️)。**端到端验证**:pytest 9/9 PASS + 回归 chat_history 7/7 不破 + celery worker [tasks] 列表确认 `file_mention_tasks.cleanup_old_mentions_task` 加载 + 默认 retention=30 健康 0 删除 + 误传 retention=0 真删 31 条 → 用户接受丢失 → activity_events 表完整不受影响。
> ---
> **2026-07-02 早班 历史任务链**：🆕 **v2 PR6-P8 notification rich title/body 收官**（7 文件 + 36 单测 + +683 行）= **推送服务 metadata 增强 + NotificationBell 卡片化重设计**（comment preview + file_type icon + 操作按钮）。
> **核心改动**:
> ① **`alembic/versions/052_drive_notification_rich.py`** — `file_mentions` 加 3 列: `title` String(200) + `body` Text + `file_type` String(50) 缓存
> ② **`app/services/notification_service.py` `_build_title_body()`** — 5 context 模板 (comment/reply:N/star/share/mention) + 实时拼 + 存 DB + WS payload 同步带 metadata + repeated_count > 1 时 title 加 `(xN)`
> ③ **`app/services/notification_service.py` `_simplify_file_type(mime, file_name)`** — MIME/扩展名 → 9 分类 (pdf/doc/excel/ppt/image/audio/video/text/archive/other), 前端友好值
> ④ **`app/services/notification_service.py` `_lookup_rich_metadata()`** — 拼 file_name + file_type + comment_preview (comment/reply:N 两种 query 模式 + cross-file 防御)
> ⑤ **`app/api/v1/notifications.py` NotificationItem** — schema 加 `title`/`body`/`file_type` Optional 字段 + list endpoint 透传
> ⑥ **`web/src/components/common/NotificationBell.vue` 卡片化重设计** — `<article class="notif-card">` (左 file_type icon + 中 title/body/meta + 右 ArrowRight) + hover translateX(2px) + 未读左色条 + 老数据 `buildFallbackTitle` 兜底 + dark mode 非 scoped 块 (v60-v67 教训)
> ⑦ **`tests/test_notification_service_rich.py`** — 36/36 PASS (TestSimplifyFileType 14 + TestBuildTitleBody 12 + TestLookupActorName 4 + TestLookupRichMetadata 5 + TestConstants 1)
> **5 新铁律 (永久沉淀)**:
> ① title/body 存 DB + 实时拼双轨 — 历史数据 NULL 走前端 `buildFallbackTitle` fallback, 推送服务持久 metadata, dedup 命中重拼 (preview 变了)
> ② file_type 缓存 vs Knowledge join — 静态字段 (file_type/file_name) 写时存避免 N+1, 动态字段 (actor_name) 实时查
> ③ 简化分类 vs 原始 MIME — 前端友好值 ≤10 枚举, 后端/推送用原始 MIME, `_simplify_file_type()` 边界函数改一处即可
> ④ reply:N 安全防御 — N 必须是 int (try/except ValueError) + N 对应 comment.file_id 必须 == 当前 file_id (防跨文件 reply 泄漏内容)
> ⑤ dedup 命中时 title 重拼 — preview 是动态的, dedup 命中必须重拼 title/body/file_type 反映最新 (id/file_id/context/mentioned_user_id 不变)
> **端到端验证 (P0-5)**:
> testbot @赵航佳 触发 mention → DB row title="xiaoqi_testbot 在 test.pdf 提到了你" body="@... PR6-P8 测试 · pdf" file_type="pdf" / alembic 052 跑成功 / 36 单测全过 / build 0 警告 / NotificationBell 卡片化上线 / 5s dedup (PR6-P7) + rich body (PR6-P8) 双轨并存 / 老数据 NULL 走前端 fallback / cross-file reply 安全拒绝。
> ---
> **2026-07-02 早班 历史任务链**：🆕 **v2 PR6-P6 comment edit 收官**（7 文件 + 1 E2E + +988 行）= **评论 5 分钟内 owner 可编辑**，复用 PR6-P4 三路 mention 解析，结构不动。
> **核心改动**:
> ① **`app/services/comment_service.py` update_comment()** — owner 校验 + 5 分钟窗口 (`COMMENT_EDIT_WINDOW_SECONDS=300`) + 重解析 @ mentions (PR6-P4 3 路匹配) + 不动 thread_depth/parent_comment_id/reply_count + activity log `action='edit_comment'`
> ② **`app/api/v1/notifications.py` PATCH `/drive/files/{file_id}/comments/{comment_id}`** — `CommentUpdateRequest/Response` schema + try/except ValueError → 422 (与 create 镜像)
> ③ **`web/src/composables/useNotifications.js` store.updateComment()** — PATCH 调用 + 本地 comment content/mentions 同步
> ④ **`web/src/components/drive/CommentItem.vue` 编辑按钮 + inline edit form** — canEdit 守卫 (owner + 5 分钟) + own useMentionAutocomplete (与 reply 隔离) + '已编辑' tag (`comment._edited=true`) + dark mode 非 scoped 块
> ⑤ **8 pytest + 11 vitest + 3 E2E 场景全 PASS** — 错误码覆盖 4 类 (不存在/无权/窗口过/内容空超长)
> **5 新铁律 (永久沉淀)**:
> ① 5 分钟编辑窗口是行业标准 (GitHub/Slack/Notion), 过长导致历史污染
> ② 重解析 mentions 必须用 PR6-P4 三路匹配 (wechat_id + username + name, case-insensitive)
> ③ edit 不改结构: thread_depth/parent_comment_id/reply_count 全部保留
> ④ owner-only + 5 分钟窗口: 前端 canEdit() UX 守卫 + 后端 service 校验双重 (前端可绕过)
> ⑤ edited 标记靠 mentions 差异推断 (`comment._edited` 由后端维护) — v2 不加 edited_at 列, 避免 alembic migration 成本
> **端到端验证清单 (P0-12)**:
> 桌面 `/drive/file/16` (xiaoqi_testbot 自己的评论) → 5 分钟内看到"编辑"按钮 → 点编辑 → textarea 弹出 (own autocomplete) → 改内容 + @ → 保存 → content 更新 + mentions 重新解析 + 5 分钟外按钮消失 / 422 "编辑窗口已过" / 422 "无权编辑" (看别人评论) / 422 "内容不能为空" / 422 "超长" / pytest 18/18 + vitest 546/546 + E2E 3/3 + dark mode 切换 + build 0 警告 + stylelint 0 errors。
> ---
> **2026-07-02 早班 历史任务链**：🆕 **v78 "团队协作" 导航合并收官**（8 新文件 + 13 改/删 + +1995/-575 行）= **项目/成员/声纹 3 个独立路由合并为 1 个 `/workspace` el-tabs 路由**（仿 v77 P2.6-G.2 MeetingView + TemplatesPanel 范例）。
> **用户决策 (AskUserQuestion 4 项)**:
> ① 命名 `团队协作`（中性，覆盖 3 域）/ ② 项目动态硬编码入口不动 / ③ 旧路由 `/projects` `/members` `/voiceprint` 完全删除（含详情子路由）/ ④ 移动 TabBar 5 项保持不变，workspace 入口走 MainLayout 抽屉 menuRoutes
> **核心改动**:
> ① **`router/index.js` 删 5 条旧路由**（`/projects` `/projects/:id` `/members` `/members/:id` `/voiceprint`）+ 加 `/workspace`（meta.icon='Files', meta.title='团队协作'）
> ② **桌面 `WorkspaceView.vue`** + 3 子 Panel (`ProjectsPanel` / `MembersPanel` / `VoiceprintsPanel`) — `el-tabs` 3 pane + query.tab URL 同步 + 项目/成员详情用 `el-dialog` 弹层（替代原 detail 路由）
> ③ **移动 `MobileWorkspaceView.vue`** + 3 子 Panel (`MobileProjectsPanel` / `MobileMembersPanel` / `MobileVoiceprintsPanel`) — 顶栏 `PageHeader` + 横向滑动 tab strip + `keep-alive` 包裹 + `Teleport` 内嵌详情 sheet 弹层
> ④ **MainLayout iconMap** 删 `mic: Microphone` 别名 + `/workspace` 走 `Files` 图标（v62-v67 铁律：menuRoutes filter `r.meta?.icon` 自动出现，MainLayout 零业务改动）
> ⑤ **NavRail** "项目" 入口改 `/workspace?tab=projects`（避免 404）
> ⑥ **删除 8 个旧 View**（桌面 3 + 移动 5）+ **MobileMemberDetailView.test.js** + **3 个 spec 修复**（grade-tag / v77-p2-6-f-2-regression / mobile visual-regression）
> ⑦ **CLAUDE.md 铁律强化**：`menuRoutes` 自动按 `meta.icon` 过滤（v62-v67 L1114）+ 详情走 dialog/sheet 弹层优先于独立路由（v78 新增铁律，避免删除详情路由后移动端 404）
> **顺手修复的预存 bug**:
> - `MemberView.vue:235` unreachable `return a.name.localeCompare(...)`（v78 拆分时删除）
> - `MobileProjectView.vue:137` `router.push('/mobile/projects/${id}')` 路由不存在（v78 删除文件即修）
> - `MobileProjectDetailView.vue:159` `router.push('/mobile/members/${memberId}')` 路由不存在（同上）
> - `MobileMemberView.vue:170` `router.push('/mobile/members/${member.id}')` 路由不存在（同上）
> - `MobileVoiceprintView.vue:39` `router.push('/members')` 旧路由（v78 改 `/workspace?tab=members`）
> **端到端验证清单 (P0-21)**:
> 桌面 `/workspace?tab=projects` 自动定位 projects tab + 点击 tab 切换 URL query 同步 + `/workspace?tab=voiceprint` 落到声纹 tab + 侧栏仅 1 项"团队协作" + 侧栏底部"项目动态"仍存在 + 桌面成员→录入声纹 (`VoiceprintEnrollDialog` 弹) + 声纹 tab→点击卡片 (`el-drawer` 50% 详情) + 项目 tab→创建/编辑/详情 3 dialog 正常 + `/projects` `/members` `/voiceprint` 404（用户接受）/ 移动 TabBar 5 项不变 / 移动 MainLayout 抽屉"团队协作"菜单出现 / 移动端 3 tab 切换正常 / 移动成员→录入声纹 (`VoiceprintEnrollFlow` 流程) / dark mode 切换 / build 0 警告 / vitest / Playwright baseline 重生成。
>
> ---
> **2026-07-02 早班收官 历史任务链**：🆕 **v2 网盘 PR6-P5 comment threading 收官**（12 文件改动 / +1595 行）= **文件评论嵌套 (max 3 层)** + reply notification + 跨窗口 dirty 文件管理。
> **架构亮点**：
> ① **后端 model 增 3 列** — `parent_comment_id` (BigInteger FK self CASCADE) + `thread_depth` (SmallInteger 0/1/2) + `reply_count` (Integer 冗余)。MAX_DEPTH=2 硬上限 (顶层/回复/回复的回复)。alembic 050 加 2 索引 (`ix_file_comments_parent` / `ix_file_comments_file_parent`)
> ② **comment_service 加 4 段逻辑** — 校验 parent + 计算 depth (parent+1) → 批量 @mention (24h dedup) → reply notification (顶层不发, parent.user_id != 当前 user 才发, context=`reply:N`) → 父评论 reply_count +1
> ③ **comment 422 错误处理** — parent 不存在 / 跨文件 / depth 超限 → FastAPI HTTPException 422 (前端 toast 显式提示)
> ④ **删评论 reply_count 回退** — 删非顶层 → 父 reply_count -1 (CASCADE 自动删子孙, reply_count 只算"直接子")
> ⑤ **前端 CommentItem.vue 递归组件** — 自带内联 reply form + own useMentionAutocomplete 实例 (与顶层隔离) + 缩进 24px/depth + depth=2 隐藏"回复"按钮 + dark mode 非 scoped 块
> ⑥ **useCommentTree composable** — `buildCommentTree(flatList)` O(n) 组装树 + `canReply(comment)` depth 守卫 + `countRepliesRecursive(comment)` 递归计数 (孤儿 parent fallback 顶层)
> ⑦ **store.postReply + parent_comment_id** — 422 错误透传 caller, 父评论 reply_count +1 (本地状态同步)
> **E2E 验证**: 5/5 scenarios PASS (顶层 depth=0 + 回复 depth=1 + 回复的回复 depth=2 + 第 4 层 reject 422 + 孤儿 reject 422 + reply_count=1)。
> **vitest**: 535/535 PASS (新增 17 useCommentTree case: buildCommentTree 7 + canReply 5 + countRepliesRecursive 3 + MAX_COMMENT_DEPTH 1 + null 安全)。
> **pytest**: 23/23 PASS (新增 11 TestThreading + 3 TestThreadingDelete + 修 1 pre-existing dedup issue)。
> **5 新铁律 (永久沉淀)**：
> ① **MAX_DEPTH=2 (3 层) 是评论 UX 黄金分割** — 更多层视觉拥挤 (缩进 48px 已达桌面屏极限) + 1 用户几乎不读超过 3 层 + 维护成本陡增
> ② **reply notification 复用 `create_mention` 不走 `create_bulk_mentions`** — bulk 是为多 @ 设计的 (24h dedup), reply 是单条, 走单条路径更清晰且 context 可注入 `reply:comment_id` (前端可跳到新评论)
> ③ **递归 CommentItem 自带 own state** — showReplyForm / repliesCollapsed / replyContent 都在子组件内 (不污染父), 多个 reply form 同时展开不冲突
> ④ **buildCommentTree 孤儿 fallback 顶层** — parent 已被删时, 子评论仍显示在顶层 (避免数据丢失, 用户能看到"原 reply")
> ⑤ **删非顶层 reply_count -1** — reply_count 是"直接子数"语义, 删一个非顶层 = -1 (不管此评论有多少子孙), 顶层被删 + cascade 删子不需要回退 (顶层没了, reply_count 无意义)
> **未实现增量** (留给 PR6-P6+): comment edit (service 已有, 缺 REST endpoint + 前端 edit dialog) / rich notification title+body / Celery beat cleanup_old_mentions (30 天)。
> **2 个真根因**（CLAUDE.md 永久沉淀铁律）：
> ① **HTTP submit 实际 201 OK, 不是 hang** — 上一次会话提交时 stale code state 触发 500 误判 hang。验证方法：直接 service 调成功 + HTTP 端到端 201 + 删除 stale .pyc (CLAUDE.md 7a 教训强化)
> ② **alembic 048 server_default="now()" 字面量化陷阱** — PG 某些版本把字符串 `'now()'` 当字面量（执行时间戳），后续 INSERT 全部用同一固定时间。**修复**：050_audit_log_now_default `ALTER COLUMN ... SET DEFAULT now()` 让 INSERT 时刻调用 now() 函数
> **e2e 跑前/跑后**：
> - 跑前: 28/34 PASS (Group 3 submit hang + Group 6 rows=0 + Group 3 detail assertion)
> - 跑后: 34/34 PASS, audit actions 实时写入 (read|6, file_request_submit|3, write|2)
> **4 新铁律（永久沉淀）**：
> ① **alembic server_default='now()' 字面量化陷阱** — `pg_get_expr(adbin, adrelid)` 必须返回 `now()` 函数, 不是 `'2026-07-01 18:24:25'::timestamp` 字面量。验证 SQL: `SELECT pg_get_expr(d.adbin, d.adrelid) FROM pg_attrdef d WHERE adrelid='table'::regclass AND ...`。修复: 单独 alembic 迁移 ALTER COLUMN SET DEFAULT now()
> ② **e2e test assertion 必须基于真实 service 错误文本** — 不能凭印象写期望值。实际 service: `"不允许的文件类型 '.exe'，仅支持 pdf, txt"`, 断言应 `assert_true(..., "不允许" in detail)`, 不是 `"不支持"`
> ③ **alembic 多 head 必须建 merge point** — 多窗口并行 PR6-P4 + PR7 各自加 050 migration, 跑 `alembic upgrade head` 报 "Multiple head revisions", 必须显式 `alembic upgrade <specific_target>` 或建 051 merge
> ④ **HTTP 错误必须看真实 response body** — traceback 误导常见: traceback line 270 (import 行) 但实际错误来自 line 283 (13 行后), Python traceback 只标"引发异常的最后一行"+ import 触发。诊断方法: `docker exec app python -c "service_call()"` 直接调确认
> **Commit**: `2c36605d fix(drive): v2 PR7 收官 - audit_log.created_at now() default + test assertion` 已 push origin/main.
>
> **2026-07-02 早班收官 历史任务链**：v2 网盘 PR6-P4 @username autocomplete 收官（7 文件改动 / +600+ 行）= **修复 PR6 自上线以来一直被忽略的 3 个 mention 解析 bug** + 新增 autocomplete UX 闭环。
> **3 个 mention 解析 bug 修复**（CLAUDE.md 永久沉淀铁律）：
> ① **后端 regex 不能匹配含 `.` 的 wechat_id** (nuyoah. / WuWei. / HALO. 等真实用户名) — 修复后端 `_MENTION_PATTERN = @([一-龥A-Za-z0-9_.\-]{1,32})`。
> ② **前端 regex 同步** (desktop + mobile `CommentThread.vue` 都用 `@([一-龥A-Za-z]{1,16})` 太严且不匹配中文) — 修：均改为 `@([一-龥A-Za-z0-9_.\-]{1,32})` 与后端 **完全镜像**。
> ③ **`comment_service` 错查 `Member.username`（登录用户名，全小写）** — 实际用户输入习惯是 @WangTianZhi (wechat_id, 混合大小写 + 含 .) — 修：改为 wechat_id + username + name 三路匹配, 都 case-insensitive (`LOWER()`)。
> **E2E 验证**: @nuyoah. → mentions=[2] (赵航佳) ✅, @WangTianZhi @YangCi → [1, 18] ✅, @DuTongHe → [3] ✅。
> **autocomplete 闭环**:
> - **`web/src/composables/useMentionAutocomplete.js` (NEW, 270 行)** — 17/17 vitest PASS, debounce 150ms + keyboard nav (↑↓/Enter/Tab/Esc) + 优先级排序 (exact > prefix > 中文 name) + mousedown 关闭防 blur race + composable 复用 (desktop + mobile 共享)
> - **`web/src/components/drive/CommentThread.vue` (+120 行)** — desktop dropdown UI (avatar + name + @username + admin badge) + dark mode 块 + 复用一个 mention 框同步 usernameMap
> - **`web/src/views/mobile/MobileCommentThread.vue` (+100 行)** — mobile 镜像 (紧凑布局 + 200px max-height) + dark mode 块
> - **build 修复 (附带)**: pre-existing `useChatStream.ts:30` regex literal 改 RegExp constructor string-based (Rolldown 不支持 `[^{}]*` + `[^>]+` 等特殊模式)
> **vitest**: **526/526 PASS** (新增 17 个 useMentionAutocomplete 单测, 0 回归). **stylelint**: 0 errors (PR6-P4 4 文件). **cleanup**: file 298 全部副作用清.
> **5 新铁律 (永久沉淀)**:
> ① **前后端 @ regex 必须完全镜像** — 后端改了前端不改, 用户看到 "高亮但 mention 不到" 的诡异 bug (PR6 自上线 bug 修复核心)
> ② **mention 查 wechat_id 不查 username** — `Member.username` 是登录用户名 (全小写), 用户 @ 习惯是 wechat_id (混合大小写, 含 . - _)
> ③ **mention autocomplete 优先级**: wechat_id > username > name (避免 name 重名歧义) + 都 LOWER() (case-insensitive)
> ④ **autocomplete 共享 composable 不重写** — desktop + mobile 各 ~100 行 UI 但 composable 只一份 + 17 个单测一次覆盖
> ⑤ **pre-existing useChatStream.ts:30 regex 永久化** — Rolldown 不支持 regex literal 含 `[^{}]*` + `[^>]+` 等模式, 改用 `new RegExp(string, flags)` 是唯一解
> **未实现增量** (留给 PR6-P5+): comment threading (parent_comment_id + MAX_DEPTH=3) / notification 5s dedup / Celery beat cleanup_old_mentions / drive_service.py 触发 notification_service / comment edit REST + dialog / rich notification title+body.
>


> **2026-07-02 LLM 工具调用 bug 修复验证收官（35 题实测 benchmark）**：🎯 **核心结果 — Tool call accuracy 0% → 100%** ✅。切换 `LLM_BACKEND=openai_compat` 走 `https://token-plan-cn.xiaomimimo.com/v1` 后：OK rate **74.3% → 97.1%** (26→34/35), avg_score **0.371 → 0.600** (+62%), avg_TTFT **1287ms → 570ms** (-56%), avg_tokens/s **25.8 → 41.2** (+60%)。bug 修验证：每个 tool_call 维度题目 (`finish_reason="tool_calls"` + `tool_call_ok=true`)。**重要 caveat**: tool_call 维度 score=0.0（mimo OpenAI 返 tool_calls 不带文本，benchmark 单轮评分看 response_text=0）— 这不代表工具调用失败，是 benchmark 评分模型未考虑"工具触发也是正确路径"，需看 `tool_call_ok=true` 而非 score。rag/reasoning 双 100% 说明模型整体 OK。完整对比数据 [docs/llm-benchmark-2026-07-02.md](docs/llm-benchmark-2026-07-02.md)。**6 新铁律** (沉淀 memory): ① Windows curl 默认 schannel CRL 检查阻塞 HTTPS（必加 `--ssl-no-revoke`） ② Ollama 0.31.1 容器内无 GNU 工具链（curl/wget/nc 都 not found，诊断只能 `docker logs ollama`） ③ Ollama Go HTTP client 不读 HTTP_PROXY env vars（必须换网络环境） ④ OLLAMA_REGISTRY env var 在 0.31.1 不生效（硬编码 registry.ollama.ai） ⑤ benchmark 单轮 score=0 不代表工具调用失败（看 tool_call_ok+finish_reason） ⑥ tool_call 真实评估看 finish_reason 而非 response_text。**Ollama 本地 deferred**: 拉模型 4 路径全失败（`ollama pull` EOF + HF mirror API 401 + ModelScope HTTP 000 + huggingface.co GFW 阻断）。架构已就绪等网络恢复。**生产切换 1 行**: `.env` 加 `LLM_BACKEND=openai_compat` + `docker compose restart app celery-worker`。
>
> **2026-07-01 ToolCallConverter + LLMClient Backend Dispatch + Ollama 部署收官（用户需求 "修云基线工具调用 bug + 写 ToolCallConverter + Ollama 部署 Qwen3-14B" 都做）**：
> ① **云基线 tools 0% 准确率真根因** — `https://token-plan-cn.xiaomimimo.com/anthropic` (Anthropic-protocol) 代理层不转发 `tools` 参数，35 题 0/10 调用工具（`scripts/benchmark_results/cloud-mimo-v2.5.json` 实测）。
> ② **`app/core/tool_call_converter.py` (~430 行) **— 7 函数（`anthropic_to_openai_tools` / `openai_to_anthropic_tools` / `openai_response_to_tool_calls` / `openai_tool_call_accumulator` / `openai_tool_calls_finalize` / `openai_message_to_anthropic_content` / `anthropic_tools_match_openai`），Anthropic-OpenAI tool 协议双向转换 + 流式累积 + Message 互转 + round-trip 一致性 helper。
> ③ **`app/core/llm.py` LLMClient 完整重写 (~340→520 行) **— `settings.LLM_BACKEND` 派发 (`anthropic` 默认 / `openai_compat` 走 mimo `/v1` / `ollama` 走本地 11434) + `_AnthropicMessageWrapper` 把 OpenAI ChatCompletion 包装成 Anthropic-Message 形状，让 30+ 调用方代码完全不感知 backend 差异。
> ④ **`tests/unit/test_tool_call_converter.py` (200 行, 12 cases) **— **12/12 PASS** ✅，覆盖正向/反向/嵌套/缺字段/round-trip/流式 chunk 拼接/多 index 累积/混合 content 文本+tool_calls 等核心场景。
> ⑤ **`scripts/benchmark_cloud_vs_local.py` refactor **— 抽取 benchmark 内 inline 12 行转换到 ToolCallConverter 单一调用，10 MODELS 字典（现网 3 Anthropic + 新 3 OpenAI-compat cloud + 新 2 Ollama + 历史 2 vLLM 实验性）。
> ⑥ **Ollama latest (0.31.1) 部署脚本 3 件套 **— `scripts/start_ollama.ps1` + `stop_ollama.ps1` + `start_ollama_run.ps1` (RTX 5090 Blackwell sm_120 实测可用：CUDA 13.3 driver + libdirs=ollama,cuda_v13)。
> ⑦ **`app/core/llm.py` `_complete_openai_compat` 路径完整可用** — 调用 Anthropic-Message 包装器，resp.content/stop_reason/usage.input_tokens 全路径让 agentic_loop.py 30+ 调用方零迁移。
>
> **端到端 pytest 结果**：`tests/unit/test_tool_call_converter.py` **12/12 PASS** + `tests/unit/test_llm_client_model_override.py` **5/5 PASS 不回归** = 21 tests in 0.48s。**架构完整 + 21 测试 PASS** ✅。
>
> **网络硬约束（实测，0 workaround）**：
> - mimo OpenAI endpoint `https://token-plan-cn.xiaomimimo.com/v1` 实测可达（auth 工作），但跑 35 题 benchmark 时**被 mimo 限流 429**（per-IP + per-token 双重，5-15 min 自动恢复）。**workaround**：`scripts/benchmark_cloud_vs_local.py` 改用 1 worker 串发，或等 15 min 后重跑。
> - Ollama 拉模型时 `request failed: Get "registry.ollama.ai/v2/...": EOF` — Ollama 0.31.1 的 Go HTTP client **不遵守 HTTP_PROXY/HTTPS_PROXY/ALL_PROXY 环境变量**，同时 `registry.ollama.ai` 在 GFW 阻断后无法直连。**workaround**：从 HF mirror 下载 GGUF 文件 → `Modelfile FROM /path/q4_K_M.gguf` 导入（本次未执行，因 HF mirror 对 `Qwen/Qwen3-14B-Instruct-GGUF` 不同步返空，待其他 mirror 测试）。
> - Ollama `--network host` 在 Docker Desktop Windows 上默认只 bind IPv6 (`::`) 而非 IPv4，Windows `localhost:11434` 走 IPv4 → connection refused。**workaround**：用 `-p 11434:11434` 强制 IPv4 NAT 转发（已生效，curl `http://127.0.0.1:11434/api/version` 返 `{"version":"0.31.1"}`）。
>
> **CLAUDE.md 新 5 条铁律**（永久沉淀，详见 [memory/tool-call-converter-2026-07-01.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/tool-call-converter-2026-07-01.md)）：
> - **铁律 1：LLMClient backend 切换通过 settings，不代码硬编码**（`.env` 一行切换，无需 PR）
> - **铁律 2：OpenAI-compat 路径必须在调用前用 ToolCallConverter 转 tools**（裸 `input_schema` dict 不会自动包成 `type=function` shape）
> - **铁律 3：OpenAI response 必须包装成 Anthropic-Message 形状**（让 30+ 调用方代码零迁移）
> - **铁律 4：ToolCallConverter 必须是独立 `app/core/` 模块**（`llm.py` 和 `benchmark_cloud_vs_local.py` 都复用，禁止 inline 复制）
> - **铁律 5：Blackwell sm_120 选 Ollama 不选 vLLM**（vLLM 0.8.5 PyTorch 不支持 sm_120，Ollama 0.31.1 + CUDA 13.3 已实测兼容）
>
> **部署必做** (CLAUDE.md 752 行铁律)：
> ```bash
> # 1. 复制新代码到容器 (volume 不覆盖 app/core/ 和 tests/unit/)
> docker cp app/core/llm.py app/core/tool_call_converter.py microbubble-agent-app-1:/app/app/core/
> docker cp tests/unit/test_tool_call_converter.py microbubble-agent-app-1:/app/tests/unit/
>
> # 2. 装 openai 包 (新依赖)
> docker exec microbubble-agent-app-1 pip install 'openai>=1.0,<2.0'
>
> # 3. 重启后端
> docker compose restart app celery-worker
>
> # 4. 验证 (默认 backend=anthropic, 与现有 5 个 llm_client_model_override 测试保持兼容)
> docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
>   bash -c 'cd /app && python -m pytest tests/unit/test_tool_call_converter.py tests/unit/test_llm_client_model_override.py -v'
> # 期望: 21 passed in ~0.5s
> ```
>
> **后续待办（需网络恢复后跑）**：
> - 跑 `python scripts/benchmark_cloud_vs_local.py --model cloud-mimo-openai-compat`（验证 Anthropic-protocol 失败 → OpenAI-protocol 修复后 tool_call_accuracy 是否 ≥50%）
> - Ollama 模型下载 + 跑 `--model local-ollama-qwen3-14b`（需先解决 `registry.ollama.ai` 走 proxy 问题）
> - mimo rate limit 恢复后跑云 baseline 重测作为对照
>
> **2026-06-30 晚班收官 当前任务链**：🆕 **v78 UI redesign 3-zone + EP icons + 4-attr a11y**（commit `34e82fd9`）+ **#009 Self-RAG 重检索 + 用户深度思考开关**（4 commits `740ac4c1` + `a49bd644`）+ **qa-bench v3.0 6 周冲刺完整收官**（W1-W6, 700 题题库 + 535 题合并去重 + 3-tier 阈值 + 7 维评分 + KB 入库 5 防线 + 7 维雷达图 + ROI 100-150%）+ **Whisper → SenseVoice 迁移收官**（commit `9effb8ed`，VRAM 8GB→0.93GB / CER 25.7%→15.6% / 4.7x 覆盖）+ **KB 数据清洁 B+C**（commit `cfd486b6`，5 类 FK 防御 + 19 单测 + 前端 dedup toggle）+ **KB 入库监控 D5**（commits `ee442125` + `9ea0f87d`，polling 5min Q5）+ **声纹循环净化 4 会议累计**（#083 86.7%→100% + #135 诊断 + #151 90% 门禁 rollback + #167 低占比过滤 1.5s/3s/5%）+ **KB "5 个统计全 0" 修复 4 commits**（filter 残留 + SW 缓存 + 三态空态 + sub-entity total）。**1545+ commits / 313K+ 行代码 / 799+ 文件 / 46 开发天数**（[app/stats.json](app/stats.json)）。沉淀 12 个新 memory（v78 / self-rag / qa-bench-v3 w1-w6 / kb-monitor / low-occupancy / asr-migration）+ 4 个新 docs（asr-alternatives / asr-benchmark-2026-06-30 / 项目狀況報告 / memory/asr-benchmark-2026-06-30）。
>
> **2026-07-01 #009 Self-RAG 100 题 smoke benchmark 收官（OFF 100% vs ON 98% — 推荐 2026-07-30 截止时删除 flag）**：100 题 concurrency=2 + SSE tier 临时 200/min 跑完 2 round 对比。**Self-RAG 是纯延迟税**：① judge 100% parse-fail (15/15 全部返 `can_answer=True, confidence=0.5` 走 happy path) ② 实际重检索次数 0 ③ avg latency +1.3s (+17%)，p95 +1.9s，max +27.9s ④ pass rate 100% → 98%（-2%），2 个 502 errors 都在 L1 阶段（judge 引入额外 LLM 调用挤占 SSE tier 余量）。**根因**：[app/services/self_rag.py:73](app/services/self_rag.py#L73) `messages.create` 没强制 JSON 输出，LLM 在 JSON 前后加解释文字 → `re.search(r'\{.*\}', text, re.DOTALL)` 抓不到 → fallback `confidence=0.5 ≥ RELAXED_THRESHOLD=0.4` → 永远不重检索。**方案 C 铁律 6 范式** ([app/config.py:176](app/config.py#L176))：2026-07-30 截止时单 commit 删除 `AGENT_SELF_RAG_ENABLED` + Phase 0.5 gate (~200 行) + 前端 toggle + 2 测试文件 + memory，**与 v31.2.5 / chat_engine_legacy 30 天收官流程一致**。完整报告 [tests/qa-bench/results/self-rag-benchmark/REPORT.md](tests/qa-bench/results/self-rag-benchmark/REPORT.md) + memory [self-rag-benchmark-2026-07-01.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/self-rag-benchmark-2026-07-01.md)。**5 新铁律** (沉淀到 memory)：benchmark 必须配 30 天承诺 + judge parse-fail rate 必须 CI + default-on-fail 必须 fail loud + Anthropic JSON 输出 prompt 必须 strict + **`__pycache__` 是隐形 bytecode 陷阱**（本次 round 2 中 23 个 502 errors 根因 — volume mount 后 source 更新但 .pyc 没清，uvicorn 启动跑旧 code 报 `NameError: share_router`）。
>
> **2026-06-30 早班 #043 8 phase 完整收官 + voiceprint 视觉收官 + v31.2.6 + pytest-asyncio 升级**（已在 [Unreleased] 段沉淀）：① #043 8 phase 收官（PostgreSQL 三表 + 11 API + 流式持久化 + localStorage 自动迁移 + UI 升级 + Celery 30 天清理 + 12 条铁律，vitest 492/492 + pytest 7/7 PASS）② voiceprint 视觉收官（5 commits，VoiceprintCard class 化 + VoiceTestDialog Canvas getComputedStyle + ConfidenceChart ECharts 主题色 + 5 条铁律）③ v31.2.6 login_limiter Redis 化 + Retry-After 响应头（commit `c476c70f`）④ pytest-asyncio 0.23.2 → 0.25 升级 ⑤ sync_from_local tz-aware datetime 500 bug 修复（commit `a1dfca2c`）。
>
> **2026-06-30 前端视觉 5 件套 + nginx HSTS + Knowledge 卡 status 真 bug 修复（11 commits 收尾）**：① **KnowledgeToolbar 4 按钮**（commit `558962b1`）—— `.btn-text` utility class 同名冲突，scoped `color: inherit` 恢复继承 ② **MemberView 录入声纹 ghost primary**（commit 845803c3）—— `variables.css` 加 default + `[data-accent]` 双块规则 + `font-weight:600` ③ **VoiceprintView 波形颜色不一致**（commit 36e64fb4）—— 老成员 stale embedding |value|≈0 alpha≈0 不可见，`barColor()` per-card max 归一化 + min alpha floor 0.12 + NaN 守卫 ④ **SettingsView Hero 跟随主题**（commit `054668f7`）—— non-scoped `[data-theme=dark].hero-bg` 写死 `#FF6B4A→#FFB347` source 顺序靠后赢 cascade ⑤ **VoiceprintEnrollFlow mobile icon + 5 处 transition token + webhint devDep**（commit `e3b32b86`）—— 全项目扫描 38 个非 scoped style 块 + 1 个 mobile inline style 全部干净 ⑥ **nginx HSTS server-block + gzip_types 扩展**（3 commits `71e743f7` + `289338fb` + `34128fbd`）—— `strict-transport-security 12→0 errors/route`，gzip_types 加 `font/woff2`/`application/wasm`/`application/manifest+json`/`image/x-icon`/`image/vnd.microsoft.icon`/`font/woff` 6 个 MIME ⑦ **Knowledge 卡 `analysis_status` 真 bug**（commit `3653890b`）—— Step 7 `_reset_multimodal_data` 无条件覆盖终态，加 `reset_status=False` 参数 + Step 8 最终终态防御 + UI partial tag ⑧ **webhint 二次扫描 + DB stuck 卡清理** —— strict-transport-security **0 errors**（9 路由全过），KB #14 #19（5 月预存 stuck 卡）验证 content 完整性 + UPDATE → done，全表 **0 stuck 'analyzing'**。沉淀 memory 8 个：[btn-text-class-name-clash.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/btn-text-class-name-clash.md) + [plain-primary-contrast.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/plain-primary-contrast.md) + [voiceprint-bar-color-2026-06-29.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/voiceprint-bar-color-2026-06-29.md) + [scoped-vs-non-scoped-hardcoded-override-2026-06-29.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/scoped-vs-non-scoped-hardcoded-override-2026-06-29.md) + [visual-cleanup-extension-2026-06-29.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/visual-cleanup-extension-2026-06-29.md) + [nginx-hsts-gzip-2026-06-29.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/nginx-hsts-gzip-2026-06-29.md) + [knowledge-status-pipeline-vs-manual-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/knowledge-status-pipeline-vs-manual-2026-06-30.md) + [knowledge-stuck-status-cleanup-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/knowledge-stuck-status-cleanup-2026-06-30.md)。
>
> 历史节点（按时间倒序）：v70 P3 会议纪要 TL;DR → v69 P0+P1 dark mode 3 阶段 → v31.3.1 whisper 容器 bind mount → v31.3 Whisper 常驻 GPU 8GB → [v31.2.5](##2026-06-26-v3125-rate-limit-收官redis-zset-持久化) → [v31.2.3](##2026-06-25-v3123-rate-limit-基建收尾) → [v31.2.2](##2026-06-25-v3122-rate-limit-进阶强化) → [v31.2.1](##2026-06-25-v3121-rate-limit-边界强化) → [v31.2](##v312-检索质量监控埋点可选-auth--ip-维度限流--user_id-列) → [v28 论文图片结构化字段](##2026-06-20-v28-论文图片结构化字段后端集成) → [2026-06-18 移动端 26 commits 全面修复](##2026-06-18-移动端-26-commits-全面修复)。
>
> **2026-06-27 声纹 sample_count 重置为 1（手动录入 +1 自增保留）**：用户决策"前端所有成员的声纹录入次数改为一次，之后只有成员主动录入声纹的时候才会增加次数，自动学习链都已删除"。**数据迁移**：新增 alembic `034_reset_voice_sample_count.py` (down_revision=`033_mvh`) → `UPDATE members SET voice_sample_count = 1 WHERE voice_embedding IS NOT NULL`（15 个已录入成员全部归零到 1）。**后端逻辑保留**：`app/services/voiceprint_service.py:230-258` `enroll_member` 的加权平均（L245-250）+ `voice_sample_count = +1`（L253）+ `voice_enrolled_at = NOW()`（L254）全部不动——这是手动录入路径，保留后成员每次主动录入都会递增 1→2→3...，且加权平均公式继续工作（多次录入融合更稳）。**前端 9 处不改动**：DB 重置后前端读真实值自动显示「1 次」。**alembic 多 head 警告**：`033_mvh` 是 DB stamp 但本地迁移文件丢失（仅 alembic_history 中可见）；新增 `034_*` 接 `033_mvh` 下游解决。**部署必做**：`docker exec microbubble-agent-app-1 alembic upgrade 034_reset_voice_sample_count`（必须指定 target，因为 `031_search_log` 也是 head，`upgrade head` 会报"Multiple head revisions"）。**遗留风险**：自动学习若仍在某处跑（如本地 admin 脚本），DB 会被继续推高——用户需要自查本地机器是否有遗留 enroll 入口。沉淀：[memory/voiceprint-reset-count-2026-06-27.md](memory/voiceprint-reset-count-2026-06-27.md)。
>
> **2026-06-27 v70~v76 前端字面色 token 化 + 视觉回归测试收官**：① **v70 P0~P3 字面色 token 化** — ~340 处 hex 字面色 → `var(--color-*)` token，dark mode 全面修复（`e4b2eec3` + `5ea74dd5` + `f6a2bc3d` + `bd41497e`）② **v71 P1 议程 timeline + 每 speaker 8 条常驻** — `el-timeline` 金橙圆 dot + per-card "展开全部"（`46c85892`）③ **v72 P1 摘要+重点摘要合并** — 主题色 TL;DR 卡显示 `meeting.summary` 完整段落，`color-mix(in srgb, var(--color-primary) X%, transparent)` 6 套主题自适应（`eed0c409`）④ **v74 CSS variable 6 主题组合自动化测试** — CI hard fail + token 白名单（`0f77bc29`）⑤ **v75 测试稳定性** — 9 个旧 fail 修复 + PR annotation + token orphan pre-commit 拦截（`ee46c34a`）⑥ **v76.2 视觉回归 5 件套** — Playwright baseline + ci-mode + max-increase + 组件级 CSS 测试（`f19cb780`）⑦ **pre-commit hook auto-add web/dist/** — CLAUDE.md 教训第 4 次沉淀后兜底（`6565415a`）。沉淀 memory：[memory/web-token-anti-regression-v70-v74.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/web-token-anti-regression-v70-v74.md) + [memory/pre-commit-dist-auto-add-2026-06-26.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/pre-commit-dist-auto-add-2026-06-26.md)。
>
> **2026-06-19 Phase 7 多模态知识库（图片/公式/表格 OCR 入库）**：① 端到端 PDF 文档 OCR 实测 10/10 图全成功 + 10 OCR 块 + 4 图表描述（论文 id=19 催化臭氧氧化甲苯）② 后端选 LLM-Vision 复用现有 vision_service，零新依赖 + 零新模型下载，settings.MULTIMODAL_OCR_BACKEND 留 Tesseract 备选钩子 ③ 数据模型统一 `KnowledgeExtraction(kind='formula|table|chart|image_block', data JSONB)` 单一表，简化 JOIN ④ 并发控制 asyncio.Semaphore(4) 防 vision API rate limit ⑤ pre-existing bug 修复 2 项：列表接口 mutate ORM 触发 autoflush NOT NULL 违反 + 009/010 alembic chain 不一致 ⑥ docker-compose 加 `./alembic/versions` volume 挂载，新迁移无需 rebuild 镜像即生效 ⑦ 21 个 OCR 单元测试（_clean_latex_response / _clean_ocr_text thinking 块剥除 / 图片缩放 / MIME 检测 / markdown 表格解析）。详见底部 [## 2026-06-19 Phase 7 多模态知识库](#2026-06-19-phase-7-多模态知识库) section + 8 条铁律。
>
> **2026-06-19 会议发言人重处理流程标准化（修 2 个核心 bug）**：① **ERes2Net 不支持 batch** — modelscope ERes2Net_aug.py:__extract_feature 强制 unsqueeze(0) 折叠 batch，旧 `batch_extract_embeddings` 把 32 段塞给模型只处理第 1 段 → 修：ThreadPoolExecutor(8) 并行单条 + threading.Lock 保护 pipeline.model ② **SQLAlchemy 静默忽略未映射属性** — Meeting model 没 `transcript_polished_old_v1` 等列，赋值被吞，commit 不报错，"已备份"成谎言 → 修：用文件备份 `/tmp/meeting_<id>_backup_<ts>.json`。沉淀为 [scripts/reprocess_meeting.py](scripts/reprocess_meeting.py) 通用 CLI（9 步流程 + 自动依赖 + 幂等）+ 11 条铁律 + [docs/reprocess-meeting.md](docs/reprocess-meeting.md) 使用文档。会议 #120 实测：3252 段"发言人?" → 4 个真实发言人（王天志 1845 段 / 杜同贺 358 / 宋洋 335 / 贾琦 292）+ 8 字段全 0 旧错标人。详见底部 [## 2026-06-19 会议发言人重处理流程](#2026-06-19-会议发言人重处理流程-reprocess_meetingpy) section。
>
> **2026-06-19 声纹 batch bug 修复推到主路径** — `app/services/voiceprint_service.py:batch_extract_embeddings` 之前用 batch=32 喂给 modelscope ERes2Net，实际只处理 batch 第 1 段（97% 沉默失败）。**所有**通过 `post_meeting_tasks.py` 自动处理的会议都受影响——hangup 后 Celery 跑全流程，每场都只能 3% 段有效。修复：ThreadPoolExecutor(8) + Lock 并行单条 → 100% 段有效。**用户原话**："不仅是漏掉发言人的情况，就算不漏掉发言人的正常识别，识别效果也要像本次一样或者更好" — 修复后所有未来会议自动获得正确识别效果，无需手动 re-process。详见底部 [## 2026-06-19 声纹 batch bug 修复 (推到主路径)](#2026-06-19-声纹-batch-bug-修复-推到主路径) section + [memory/voiceprint-batch-bug-fix-2026-06-19.md](memory/voiceprint-batch-bug-fix-2026-06-19.md) 7 条铁律。
>
> **2026-06-17 部署与基础设施重建**：Docker Desktop 引擎崩溃循环修复（WSL2 `docker-desktop-data` 发行版丢失 → com.docker.service 7-9 分钟反复启停）+ 24GB C 盘 Docker 缓存清空 + 数据全 E 盘化（junction 透明重定向）+ huaweicloud 镜像源 404 → aliyun 正确路径（Debian bookworm-security 走 `debian-security/` 独立路径）+ aliyun PyPI 限速 600KB/s → 清华源 + pip `--retries 10 --timeout 60` + 新增 `.dockerignore`（build context 12GB→700MB 17 倍提速）+ frp 客户端 Windows 计划任务自启。详见 [CHANGELOG.md](CHANGELOG.md) `[Unreleased] 2026-06-17` section + [memory/docker-desktop-fix-2026-06-17.md](memory/docker-desktop-fix-2026-06-17.md) 10 条铁律。
>
> **2026-06-17 晚间更新**：服务器 webhook deploy 链断裂修复（dist `Last-Modified` 停在 6/15 13:52 已 2 天）。根因：服务器 `/root/.ssh/github_deploy` key 与 GitHub repo Deploy keys 不匹配，5 次重试全 `Permission denied (publickey)` → webhook 服务在线但 git fetch 失败 → deploy 静默退出（GitHub UI 显示 200 OK 但服务器代码没动）。修复：重新生成 ed25519 + GitHub 端加 deploy key + 顺便持久化 `.env.webhook`（修 6/13 教训的幽灵隐患）+ `deploy-auto.sh` 加 `.env.webhook missing` 守卫（commit `c9c60ca6`）。详见底部 [## 2026-06-17 webhook deploy 链断裂修复](#2026-06-17-webhook-deploy-链断裂修复) section 5 条铁律。

> **2026-06-15 凌晨更新**：Agent 回答质量 5 大根因修复（14 commits）+ qa-bench 360 题逐个问答闭环 + 知识库 64→247 条（+183）。详见底部 [## 2026-06-15 Agent 质量 + qa-bench 闭环](#2026-06-15-agent-质量--qa-bench-闭环) section。
>
> **2026-06-15 上午更新**：Rich Block 统一包装铁律（杨慈是谁呀 Rich Block 显示"暂无成员"修复 + 顺手修 wechat/handler.py:1031 SyntaxError + members.notification_preferences 列缺失）。详见底部 [## 2026-06-15 Rich Block 统一包装铁律](#2026-06-15-rich-block-统一包装铁律杨慈是谁呀暂无成员修复) section。
>
> **2026-06-15 下午更新**：LLM 元话语/thinking 文本泄露修复（杨慈是谁呀元话语泄露"我需要..."、"用户问的是..."、"开始回答吧"）。双管齐下：prompts.py 硬规则 + 后端 _strip_meta_thinking 兜底 + SSE done.text_without_json + 前端 useChatStream done 替换。详见底部 [## 2026-06-15 LLM 元话语/thinking 文本泄露修复](#2026-06-15-llm-元话语thinking-文本泄露修复双管齐下) section。
>
> **2026-06-15 晚间更新**：reminders 表 v2 字段缺失 → /api/v1/reminders 500（webhint 报错 index-2bce6a55.js:4 GET 500）。本地 + 生产 ALTER TABLE 加 6 列（acknowledged_at / acknowledged_by / ack_channel / snoozed_until / reminder_batch_date / policy_version）。deploy-auto.sh 集成自动迁移。
>
> **2026-06-15 晚更新**：主动提醒调度器补 11AM 窗口守卫（3 commits `c18b01e8` + `d0ddf49e` + `09e4548d`）。**根因**：`app/wechat/scheduler.py:ProactiveScheduler` 3 个 check 方法（due_soon/overdue/unconfirmed）**完全绕过 11AM 窗口**，与 v2 `reminder_service` 并行运行，Celery beat 15min tick 凌晨 2:48 推送 → 用户被叫醒。**修复**：3 个 check 方法顶部加 `is_in_digest_window()` 守卫（共享 v2 reminder_policy 策略函数）。**bonus**：`markdown.ts` plaintext fallback 未注册导致 console warning。**部署**：本地 Docker `docker compose restart celery-worker celery-beat`（CLAUDE.md 752 行铁律），重启后第一次执行耗时 0.002s = 修复生效。详见 [## 2026-06-15 任务提醒体系 v2 全面优化](#2026-06-15-任务提醒体系-v2-全面优化) 末尾"v2 漏修补救"section + 5 条新铁律。

> **2026-06-15 全天更新**：任务提醒体系 v2 全面优化（commits `223ea74` + `ba75e32`）。所有 reminder 统一在 11:00 AM 北京时间窗口发送，每个任务 1 次推完即结束；任何微信消息 = ack 取消该用户所有 pending 提醒（杜同贺痛点彻底解决）。详见 [## 2026-06-15 任务提醒体系 v2 全面优化](#2026-06-15-任务提醒体系-v2-全面优化)。
>
> **2026-06-15 全天追加**：会议 #95 声纹重置 + KMeans 重识别 + speaker_mapping 重写 + meeting_participants 修复。教训：`psycopg2` 中途失败导致整个 transaction rollback、speaker_mapping 与 meeting_participants 必须互相对齐、Whisper 幻觉段不能用作声纹学习。详见 [## 2026-06-15 会议 #95 声纹重置 + 重识别教训](#2026-06-15-会议-95-声纹重置--重识别教训) section。

## 项目简介

"小气" - 微纳米气泡课题组智能Agent系统，约20人研究实验室的AI助手。

- 后端: Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery
- 前端: Vue 3 + Vite + Element Plus（原版 `web/`，极简版 `web-minimal/`）
- AI: Claude API (Sonnet) + faster-whisper + pgvector
- 部署: 云服务器 (Nginx + FRP 服务端) + 本地电脑 (Docker 8 services + GPU Whisper)，通过 FRP 隧道连接。也支持单机部署，详见 `docs/deploy.md` 服务器迁移章节

## 当前开发阶段

**Phase 1-6 全部完成 + v2/v3/v4 全栈架构重构收官 + 移动端 10 个 PR 全栈定制收官。** 知识库已升级为**自主进化的课题组知识大脑**。会议系统已重构为**录音机 + 离线后处理模式**。**小气助手后端 Agent 架构**：从 1 个 1469 行单文件（`app/agent/core.py`）拆为 7 个职责清晰模块 + 13 个按业务域拆分的 tools/ 文件，**34 个工具全部走 `@tool` 装饰器 + Pydantic 校验**。前端用 ChatViewSSE.vue 接入真实 SSE 流式 + 12 类 Rich Block 组件 + 多会话侧栏 + dark mode + ASR/TTS 完整语音链路 + 代码高亮。**移动端**采用 NutUI 4 + Element Plus **路由级双栈**架构（`useIsMobile.js` 判定 + `resolveMobile.js` 路由适配），**18 个移动端页面 + 12 个移动端组件 + 4 个 PWA 离线策略**全部交付，**iOS Safari + Android Chrome 全兼容**。**当前状态（2026-06-13 收官后，commit `9026c07`）**：
- **43 commits 累计**（v1 修复 + v2 6 + v3 5 + v4 6 + 文档 2 + 深夜收尾 4 + 多会话并行 2 + 移动端 PR #1-10 共 10 + 文档/webhint 5 + 部署加固 1）
- **160+ 测试全过**（87 后端 + 73 前端 + 21 录音断网防御 + 2 移动端组件 + 21 多模态 OCR）
- **1014 次提交 / 135K 行代码 / 578 文件 / 30 开发天数**（`app/stats.json` 由本地 Python 准确计算；排除 frp/.git/node_modules/dist/.meta/.log/.wav/.exe 等非源代码）
- **140 项待做清单**已整合到 README.md（107 项老 + 33 项 v4 收官遗留），移动端 10 PR 完成后清单大幅缩短

**Phase 7 多模态知识库（2026-06-19）**：
- **2 张新表**：`knowledge_images`（图片 + OCR 结果）+ `knowledge_extractions`（统一 formula/table/chart/image_block）
- **OCR 服务抽象层**（`app/services/ocr_service.py`）：主后端 LLM-Vision 复用 vision_service，可选 Tesseract 备选（settings.MULTIMODAL_OCR_BACKEND 切换）
- **多模态解析管线**（`app/services/multimodal_extraction_service.py`）：PDF/PPTX 提取嵌入图片 → 缩放 → MinIO → asyncio.Semaphore 并发 OCR → 写表
- **3 个新 API**：`GET /knowledge/{id}/images`、`GET /knowledge/{id}/extractions`、`POST /knowledge/{id}/extract-multimodal`（老 PDF 手动重提）
- **KnowledgeService step 7**：上传时自动触发多模态提取；独立容错
- **5 个新 settings**：`MULTIMODAL_OCR_BACKEND` / `_CONCURRENCY=4` / `_MAX_IMAGES_PER_DOC=20` / `_MAX_IMAGE_PIXELS=2.5MP` / `_MIN_IMAGE_PIXELS=10k`
- **2 个新前端组件**：`KnowledgeImageGallery.vue`（图片网格 + 放大预览 + OCR 文本）+ `KnowledgeExtractionsPanel.vue`（公式 LaTeX + 表格 HTML + 图表描述）
- **KnowledgeCard 缩略图** + `KnowledgeUploadDialog` PDF/PPTX 多模态提示
- **端到端验证**：PDF id=19 OCR 10/10 + 10 OCR 块 + 4 图表描述成功

**v2/v3/v4 关键成果**：
- **34 个 `@tool` 装饰器工具**（覆盖任务 5 / 会议 7 / 项目 3 / 成员 2 / 知识 9 / 公式 1 / 假设 1 / 记忆 3 / 搜索 1 / 个性化 2 / 反馈 1 — 含 16 个 v2+v3 新工具）
- **12 类 Rich Block 组件**（meeting / task_list / knowledge_ref / member / formula / hypothesis / project / transcript / chart + 2 兜底）
- **真实 SSE 流式**（`/chat/stream`）替代伪流式 2s 轮询
- **10 字段响应**（content + session_id + file_url + file_name + knowledge_content + is_brief + **rich_blocks + tool_trace + usage + duration_ms**）
- **多会话侧栏**（Pinia + localStorage + 兼容 v1 单会话迁移）
- **dark mode**（CSS 变量化 + 顶栏 toggle + 主题持久化）
- **agent_traces 可观测性闭环**（Celery 异步写表 + `/admin/agent-traces` 端点 + `AgentTracesView` 管理页）
- **ASR 语音完整链路**（点 🎤 → 录音 → ASR 文字 → 自动发 + 🔊 TTS 播放）
- **代码高亮**（highlight.js + 6 种语言：python / js / bash / json / sql / yaml）
- **性能基线**（`tests/perf/` 6 测试：brief<3s / SSE<1s / tool<5ms）
- **质量评估体系**（LLM-as-judge + RAG 召回率 + 20 问标注 + 5 消融）
- **`core.py` 清理**：1469 → 689 行（-53%，原 794 行 elif 链替换为 14 行薄壳调 `dispatch_tool`）

详见 [ROADMAP.md](ROADMAP.md#v2v3v4-全栈架构重构2026-06-12-收官17-commits) 和 [README.md](README.md#近期新增按时间倒序)。

## 会议纪要标准格式（2026-06-06 硬规则）

后续所有会议 AI 分析、手动优化会议内容、历史会议补写，都必须按 `2026.5.28 例行例会` 的信息密度输出，不能只生成短摘要。完整规范见 `docs/meeting-minutes-standard.md`。

- **摘要**：3-6 句，必须包含会议背景、讨论过程、关键人物观点、结论和后续方向。
- **讨论要点**：`key_points` 必须使用 `【发言人】内容` 格式；短会议也至少提取 3 条，信息充足时 5-8 条。
- **决议事项**：`decisions` 必须使用 `【发言人/双方/全组】内容` 格式，写清楚决定/共识和后续用途。
- **原始转录保护**：不改 `transcript` 原始转录，只优化 `transcript_polished`、`summary`、`key_points`、`decisions`。
- **禁止误认**：声纹无法确认时使用 `发言人A/B`，不要为了完整性强行猜姓名。

## 前端设计系统

**CSS 设计令牌**：`web/src/assets/variables.css`，暖橙珊瑚色系，可复用于所有页面。

主要变量：
- `--color-primary: #FF7A5C`（珊瑚橙）
- `--color-accent: #FFB347`（金橙）
- 阴影层级：`--shadow-sm/md/lg/primary`
- 圆角规范：`--radius-sm(4px)/md(8px)/lg(12px)/xl(16px)`
- 动画时长：`--duration-fast(150ms)/normal(200ms)/slow(300ms)/counter(500ms)`

动画规范：使用 `fadeSlideUp`/`slideDownFade` 入场动画类，stagger 延迟 `.stagger-1` ~ `.stagger-6`。

设计规范文档：`.claude/skills/ui-design/SKILL.md`（20项 UI 升级检查清单）

## 关键架构决策

- Agent 工具调用通过 `app/agent/core.py` 的 `_execute_tool` 方法路由到 service 层（17 个工具已全部接入）
- `chat()` 和 `chat_stream()` 接收 `db: AsyncSession` 参数，由 API 路由通过 `Depends(get_db)` 传入
- 使用 `AsyncAnthropic` 客户端，不阻塞事件循环
- **Agent 回复采用"先简要后详细"双层结构** — 两阶段并行调用，简要立即返回，详细后台追加
- **MCP 视觉服务架构** — 预写架构，切换 DeepSeek 等文本模型时支持图片识别
- 认证使用 JWT，`app/core/security.py` 已实现，31 个端点全部接入 `get_current_user`
- 会话存储已迁移到 Redis（`RedisSessionStore`，24 小时 TTL）
- 知识库使用 pgvector 做向量搜索（扩展已在 main.py 启动时自动安装，已接入 text2vec-base-chinese 真实语义搜索）
- **知识库深层逻辑系统（Knowledge Brain）** — 八大模块：
  - **动态 LLM 分析**：LLM 根据内容自由生成分类/标签/key_concepts/related_topics/knowledge_type，不再硬编码
  - **自动关联引擎**：新入库条目通过 pgvector 余弦相似度 + 概念重叠自动发现关联关系，双向写入 knowledge_relations 表
  - **RAG 问答引擎**：语义搜索 → 阈值分类 → LLM 合成 → 来源引用，高相关不足时自动触发研究
  - **自主研究引擎**：知识空白检测 → 联网搜索（搜狗+必应）→ 网页抓取 → LLM 提取 → 自动入库 → 建立关联
  - **健康监控**：Celery 定时任务检测矛盾/重复/过期条目
  - **实体知识图谱**：跨文档实体融合（精确匹配→embedding 余弦→新建），共现网络，ECharts 力导向图可视化
  - **假设生成引擎**：从实体三元组+知识空白 LLM 生成可验证假设，proposed/validated/rejected 生命周期
  - **量化推理引擎**：LLM 提取数学公式 → safe_eval 安全计算 → LaTeX 渲染 → 前端计算器
  - **公式分类体系**：6 大类 24 子分类（FormulaCategory 模型树）+ 32 个内置微纳米气泡领域公式，前端分类树浏览，来源标签（内置/提取）
  - **公式自动分类**：LLM 提取公式 domain 字符串 → 模糊映射到结构化分类，新老公式统一归入分类树
- 语音识别使用 faster-whisper GPU，TTS 使用 Edge-TTS
- **会议转录总结工具** — `summarize_meeting_transcript` 工具支持对话触发与长期存储
- **任务软删除/垃圾桶** — 删除任务进入垃圾桶（deleted_at 字段），支持恢复或永久删除，3天后自动清除（Celery beat 每 1h 调度 `auto_purge_trash_task`，垃圾桶 UI 双行显示倒计时 + 5 级紧急度颜色）。详细状态见 [README.md](README.md#当前状态2026-06-03)
- **微信对话双消息模式** — 收到消息后 0.5 秒内先发"🤔 收到，让我思考一下..."，后台异步处理后发正式回复，解决等待无反馈问题
- **移动端独立抽屉架构** — 移动端侧边栏使用 el-container 外部独立 div + Vue Transition，完全绕过 Element Plus aside 的全局 CSS 干扰。桌面端 `v-if="!isMobile"` 零影响
- **通知面板** — 铃铛使用 el-popover 弹窗面板，显示每条提醒的具体内容（任务标题+提醒时间）、全部标为已读、点击跳转任务；头像读取 userStore.userInfo.avatar 真实 URL
- **任务权限模型** — 所有成员可见全部任务（降低认知负担），仅创建人/负责人/管理员可编辑、删除、恢复、永久删除
- **状态统一** — "待办"(todo) 和 "进行中"(in_progress) 语义高度重合，已统一为"进行中"。新建任务默认 in_progress，现有 todo 任务兼容显示
- **移动端路由级双栈架构**（2026-06-13 收官）— 桌面端（Element Plus）和移动端（NutUI 4）**同一 URL 不同组件**，不共享 component 树。`useIsMobile.js` 监听 viewport + UA 兜底 → `router/index.js` 通过 `resolveMobile.js` 动态 import `views/mobile/*` 或 `views/*` → 桌面端 `el-*` 与移动端 `nut-*` CSS 完全隔离。**PWA 4 策略**：manifest + service worker（workbox）预缓存 app shell + useSafeArea 读 iPhone 安全区 + 离线 IndexedDB 兜底。**视觉回归测试**：Playwright 5 viewport × 13 核心页面，CI 截图对比基线

## 2026-06-29 #043 账号持久化聊天历史（Phase 4+5 收官 6/8, Phase 6 UI 升级待启动）

> **用户原始需求**：每个人与小气助手的对话的聊天记录要跟随账号一直记住，就像 ChatGPT、豆包一样。用户登录就可以看到过往聊天记录。
>
> **痛点（现状）**：前端 100% `localStorage`（`chat_msgs_<sid>` + `chat_sessions_v3`），per-browser 不跨账号。换浏览器/换电脑/清缓存/移动端新设备 = 历史清零。多人共用一台电脑 = A 账号登入看到 B 账号的会话。后端 Redis `agent_session:{sid}:msgs` 有持久化但**无 user_id 反查**，且 `micro_bubble_agent.py:111 chat_stream()` 流式场景**不写 Redis**。

**用户决策**（2026-06-29）：
- 存储后端：**PostgreSQL SQL 表**（质量与效果最好；不是 Redis 扩展）
- 旧数据迁移：**首次登录自动迁移 localStorage → server**
- 功能范围：**尽可能全**（搜索 + 导出 + 标签/收藏/归档 + 分享链接 + 软删除 + 跨设备同步）

**完整规划**：[C:/Users/pc/.claude/plans/chatgpt-structured-floyd.md](C:/Users/pc/.claude/plans/chatgpt-structured-floyd.md)（8 phase / 22-30h / 3 PR 收官）

**8 phase 实施计划**：
1. ✅ **Phase 1（commit `558962b1` 收官）**：ORM 模型 + alembic `039_chat_history.py`（chat_sessions / chat_messages / chat_shares 三表 + 索引 + 触发器）+ Pydantic schemas
2. ✅ **Phase 2（commit `558962b1` 收官）**：11 个后端 API 端点（`/chat/sessions` CRUD + `/messages` + `/export` + `/share` + `/search` + `/sync` + `/shares/{token}`）— 17/17 e2e PASS
3. ✅ **Phase 3（commit `5bf7c5c7` 收官）**：流式 chat 持久化修复（`micro_bubble_agent.py:111` + `partial_assistant_buffer` + SSE 事件 `message_persisted` / `sync_required`）— 25/25 e2e PASS
4. ⏸ **Phase 4（待启动）**：前端 store 重构（chatHistory.ts + chatSessions.ts 同步 + useChatStream 持久化钩子 + 监听 sync_required 自动 reload）
5. ⏸ **Phase 5（待启动）**：旧数据自动迁移（useChatMigration.js + localStorage `chat_migrated_v1` 标记 + 幂等键）
6. ⏸ **Phase 6（待启动）**：UI 升级（搜索栏 + 标签 chip + 分享对话框 + 导出对话框 + 移动端长按 ActionSheet）
7. ⏸ **Phase 7（待启动）**：Celery 30 天清理任务（`cleanup_soft_deleted_sessions` 每天凌晨 3:30）
8. ⏸ **Phase 8（待启动）**：测试 + memory 沉淀（4 后端 + 2 前端单测 + 10 E2E + memory/chat-history-persistent-2026-06-29.md）

**PR 分批**：
- PR 1（Phase 1-3+7-8，~10h）✅ 已收官（含 558962b1 + 5bf7c5c7 + 后续 Phase 7/8）
- PR 2（Phase 4-5，~6h）⏸ 待启动
- PR 3（Phase 6，~8h）⏸ 待启动

**复用现有 utilities**：`app.core.security.get_current_user`（JWT 鉴权） / `app.core.rate_limit`（write tier 30/min） / `app.services.task_service.auto_purge_trash_task`（30 天清理模式） / `web/src/composables/chat/useChatStream.ts`（多会话并行 8 铁律保留） / v77 P2.6-C EP 多主题透传 dark mode 适配

**部署必做**（CLAUDE.md 752 行铁律）：
```bash
# 1. 跑迁移
docker cp alembic/versions/039_chat_history.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head
# 2. 重启后端
docker compose restart app celery-worker
# 3. 验证表（chat_sessions / chat_messages / chat_shares）
```

**关键风险与缓解**：
- 流式 chat 中断 → partial 消息：`is_partial=True` 标记 + 重新生成机制（Phase 3 SSE 限制：连接断开时 partial 可能不落库，但 user 必落）
- localStorage 迁移冲突：`client_msg_id` 幂等键 + `last_synced_at` 时间戳
- 越权访问：`WHERE user_id = current_user.id` 强制 + 单元测试
- alembic 链断：接 `038_*` 下游（v77 P2.6-F.5 cloned_from_id 已存在）

**进度跟踪**（8/8 phase 完整收官）：
- [x] Phase 1：ORM + alembic（commit 558962b1）
- [x] Phase 2：11 API 端点（commit 558962b1）
- [x] Phase 3：流式持久化（commit 5bf7c5c7）
- [x] Phase 4：前端 store（commit af8c8f7d）
- [x] Phase 5：旧数据迁移（commit af8c8f7d）
- [x] Phase 4+5 fix：sync_from_local tz-aware datetime 500 bug（commit a1dfca2c，2026-06-30）
- [x] **Phase 6：UI 升级（11 sub-tasks：SearchPalette/ShareDialog/ExportDialog/TagsEditor/useGlobalShortcuts/SessionSidebar/MobileSessionDrawer/LongPressWrapper/MobileActionSheet/MobileSearchSheet + 桌面 ChatViewSSE + 移动 MobileChatView/MobileHeader 集成）— vitest 492/492 PASS**
- [x] **Phase 7：Celery 30 天清理（`app/services/chat_history_tasks.py:cleanup_soft_deleted_sessions_task` + `CHAT_HISTORY_RETENTION_DAYS=30` + beat schedule 3600s + `celery_app.conf.imports` + autodiscover 双注册）— pytest 7/7 PASS + 端到端 15 个过期会话 100% 物理清除验证**
- [x] **Phase 8：测试 + 沉淀（5 新测试文件：test_chat_history_service.py 24 test + test_chat_history_tasks.py 7 test + useGlobalShortcuts.test.js 9 test + useChatMigration.test.js 9 test + chatHistory.test.js 9 test）— vitest 492 + pytest 7 + memory 完整沉淀**

**Phase 3 已沉淀的 5 条新铁律**（详见 [memory/chat-history-stream-persistence-2026-06-29.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/chat-history-stream-persistence-2026-06-29.md)）：
1. **流式 chat 持久化必须入场 append user** — 不能 defer 到流结束（中断时 user 消息就丢）
2. **assistant 落库必须在 done 事件 yield 之后立即** — 客户端收到 done 后才看到 message_persisted，事件顺序清晰
3. **CancelledError 必须 try/except + 落 partial + 重 raise** — 不能吞，否则上层不知道中断 SSE 不关闭
4. **JSONB 字段 mutate 后必须 `flag_modified`** — CLAUDE.md 2026-06-28 教训（rich_blocks / tool_trace / message_metadata 全部要）
5. **持久化失败必须 best-effort** — 所有持久化操作 try/except + logger.error(exc_info=True)，不阻塞流式（用户体验优先）

**Phase 4-8 已沉淀的 7 条新铁律**（详见 [memory/chat-history-persistent-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/chat-history-persistent-2026-06-30.md)）：
6. 跨设备同步：消息主存 PostgreSQL，Redis 仅短期缓存（MVP 拉取模式，WebSocket push 留待 #009 Self-RAG）
7. 软删除：30 天保留期（与 task / meeting 对齐，Celery NullPool + asyncio.run + logger.warning）
8. 越权防护：所有查询 `WHERE user_id = current_user.id`（service 函数签名 `(db, user_id, session_id, ...)` 强制 user_id 过滤）
9. 迁移幂等：`client_msg_id` 唯一约束 + `last_synced_at` 增量同步（服务端 `sync_from_local` 内部用 `hash(sid:role:ts:content[:50])` 生成）
10. 异步不阻塞登录：迁移后台跑（`useChatStream.onMounted setTimeout 1000ms`），UI 立即可用
11. localStorage 兜底：网络失败降级到本地（`chat_migrated_v1` 标志缺失时重试，**失败时不设标志**）
12. tz-aware vs naive datetime 严格隔离：Celery task 用 `datetime.now(timezone.utc)` 传 cutoff，service 内部统一 `_to_naive_datetime()` 转换（CLAUDE.md 2026-06-05 教训复用，避免 "can't subtract offset-naive and offset-aware datetimes" 500）
13. mobile long-press 必带 `navigator.vibrate(10)` 触觉反馈（CLAUDE.md 2026-06-27 教训）+ dark mode 跨组件必须非 scoped 块（CLAUDE.md v60-v67 第 5 次强化）

## 代码质量规范（2026-06-04 升级）

### API 层
- **统一异常响应格式**：`{"error": {"code": "RESOURCE_NOT_FOUND", "message": "...", "details": {...}}}`
- **异常类层次**：`app/core/exceptions.py` — AppException/NotFoundException/ValidationException/AuthException/ForbiddenException/ConflictException/RateLimitException
- **统一分页模型**：`app/schemas/pagination.py` — PaginationParams + PaginatedResponse + PaginationMeta
- **全站分级限流**：`app/core/rate_limit.py` — auth:5次/分, write:30次/分, read:100次/分, upload:10次/分
- **安全响应头**：X-Content-Type-Options/X-Frame-Options/X-XSS-Protection/Referrer-Policy/X-Request-ID

### 前端架构
- **Composable 模式**：`web/src/composables/` — useTask/useMeeting/useKnowledge 提取共享状态 + API 调用
- **子组件拆分**：18 个子组件（Task:3 + Knowledge:8 + Meeting:3），主 View ≤ 1920 行
- **Vitest 测试**：`web/vitest.config.js` — composable 测试（23 个）+ 组件测试（15 个）= 38 个测试通过

### 2026-06-13 webhint PWA 5 警告全栈修复新增（commit `08f440f` + `c855f0e`）

- **Nginx 缺 `.webmanifest` MIME（commit `08f440f`）** — Nginx 默认 `mime.types` 不包含 `.webmanifest`（到 1.27 才内置），回退 `application/octet-stream` → 浏览器拒绝解析 PWA manifest → 添加桌面图标失败。**修复**：server block 加 `types { application/manifest+json webmanifest; }` + `charset_types` 同步加 `application/manifest+json`（让 `charset utf-8` 生效）。**诊断**：`curl -I https://xxx/manifest.webmanifest | grep Content-Type` 看是不是 octet-stream。**纪律**：所有 PWA 项目上线前必须验证 manifest MIME，**仅一次**而不是每个 server 都加。
- **`vite-plugin-pwa` 输出 manifest 不带 hash（commit `08f440f`）** — `manifest.webmanifest` 文件名固定不走 rollup hash 流程，webhint cache-busting 永远警告。**修复**：写一个 Vite 插件 `manifestHashPlugin`（closeBundle 钩子）→ `crypto.createHash('sha256').update(content).digest('hex').slice(0, 8)` → 重命名为 `manifest.{8char_hash}.webmanifest` + 同步改 `index.html`/`offline.html` 的 link 引用。**8 字符 hex 满足 webhint 默认 `[0-9a-f]+` 正则**。**Vite 5+ emitFile 不适用**（manifest 是 vite-plugin-pwa 输出，emitted by another plugin），必须 fs.renameSync。
- **`/registerSW.js` 静态注入无法 cache-busting（commit `08f440f`）** — `VitePWA({ injectRegister: 'auto' })` 自动注入 `<script src="/registerSW.js">`，文件名固定无 hash。**修复**：`injectRegister: null` + `main.js` 用 `import { useRegisterSW } from 'virtual:pwa-register/vue'` 替代。**Vue composable 在生产 build 时被 rollup 处理，运行时通过 sw 注册的副作用自动跑**，无需手动写 `<script>`。**纪律**：PWA 项目**避免** `injectRegister: 'auto'`，除非真的需要纯静态（非 SPA）站点。
- **删除 manifest.webmanifest 后 SPA fallback 误返 index.html（commit `c855f0e`）** — git 删除旧 manifest 文件后，Nginx `try_files $uri $uri/ /index.html` 找不到文件 → fallback `/index.html`（1924 字节 HTML 内容） → 任何残留引用/书签/扫描器拿到 HTML 内容物以为是 manifest。**修复**：在 `/` location 前加 `location = /manifest.webmanifest { return 410; }` 精确 410 Gone。**纪律**：SPA 部署时**所有被废弃的资源路径**都应该有明确返回（410 / 404），不能依赖 try_files fallback。
- **theme-color Firefox 不支持** — Edge DevTools 内置 webhint 不读 `.hintrc`，永远警告。**纪律**：`.hintrc` 配 `meta-theme-color: "off"`（webhint CLI 0 警告），接受 Edge DevTools 误报。Chrome/Safari/iOS Safari PWA 顶部栏颜色价值 > Edge DevTools 警告噪音。**永远不要**完全删除 theme-color meta（损失浏览器原生美化）。

### 2026-07-11 PWA manifest 410 回归 (commit `59187ce8` cascade folder delete 引入, `5d2bcdfd` 修复)

> ⚠️ **铁律**: `web/package.json` `"build": "vite build && node scripts/postbuild-fix-manifest.js"` 是**唯一**合法 build 命令。**严禁** `vite build` 直跑然后 force-add commit dist — manifest.webmanifest 保持 unhashed → nginx `location = /manifest.webmanifest { return 410; }` 拦截 → 浏览器 `Manifest fetch failed, code 410` → PWA install 失败。`package.json` 有 `build:raw` 别名但**仅供调试 sw.js 内容用**, 调试完必须重跑 `npm run build` 才能 commit。

- **根因**: commit `59187ce8` 用 `vite build` 直跑绕开 postbuild → `git show 59187ce8 -- web/dist/manifest.webmanifest` 显示 `manifest.4f8d6b64.webmanifest => manifest.webmanifest` (rename 回 unhashed) → 服务器 410 → 用户浏览器 PWA install 失败。
- **修复 (commit `5d2bcdfd`)**: `cd web && npm run build` → postbuild 自动 3 件事 + 健全性自检 + `git add -f web/dist/manifest.{hash}.webmanifest` (新增文件 .gitignore 拦了必须 `-f`) + push → webhook 30s → 浏览器 DevTools Clear site data + 硬刷。云端验证: `/manifest.webmanifest` 410 (防护保留) + `/manifest.4f8d6b64.webmanifest` 200 (`application/manifest+json`)。
- **纪律**:
  1. **`npm run build` 是唯一合法 build 命令** — `vite build` 直跑 = 必坏 PWA (服务器 410 + 浏览器 install 失败)
  2. **服务器 410 manifest.webmanifest 是有意防护** — 防 SPA `try_files` fallback 误返 index.html (c855f0e 教训)。修法只能改客户端 dist, 不能动 nginx
  3. **commit 前必须 grep dist** — `git diff --cached -- web/dist/ | grep -E '"url":\s*"manifest\.webmanifest"'` 期望空输出
  4. **SW BUMP commit 必须连带重跑 npm run build** — 任何 SW_VERSION bump 都会触发 dist 改动, 调试时必须用 `npm run build`
  5. **.gitignore 含 `web/dist/` → git add 必须 -f** — `git add web/dist/` 默认啥都不加, 新增 hashed manifest 文件**极易漏 force-add**, 修法 `git add -f web/dist/manifest.{hash}.webmanifest` 逐一加
- **下次加固 PR**: `scripts/deploy-auto.sh` line 134 (v80 修复加入) `grep -oE '"url":"manifest\.webmanifest"' dist/sw.js` 只检查**新 build**, 不检查 git staged。建议加 `git diff --cached -- web/dist/sw.js | grep -qE '"url":\s*"manifest\.webmanifest"'` 拦截任何 stage 的 unhashed 引用 (commit 59187ce8 这条恰好能拦下)。
- **memory 沉淀**: [`pwa-manifest-410-regression-2026-07-11.md`](./memory/pwa-manifest-410-regression-2026-07-11.md) (含 5 铁律 + commit 链 + deploy-auto.sh 加固代码)

### 2026-06-13 Vue 3.5 'bum' null bug 真根因 + Vite plugin patch（commit `79305b7`）

- **Vue 3.5 unmountComponent 仍缺 instance null 检查** — 之前 CLAUDE.md 误记"Vue 3.5.34 PR #11487 已修 `bum` bug"，**实际未修**。`@vue/runtime-core/dist/runtime-core.esm-bundler.js:6763`（3.5.34）和 `:6763`（3.5.38 raw 检查）：
  ```js
  const unmountComponent = (instance, parentSuspense, doRemove) => {
    if (__DEV__ && instance.type.__hmrId) { ... }   // ← instance 仍可能为 null
    const { bum, scope, job, subTree, um, m, a } = instance  // ← 爆点
  ```
  只有 line 6572 的 `unmount()` 函数 vnode 解构加了 null 检查，`unmountComponent()` 的 instance 解构**漏修**。minify 后报 `Cannot destructure property 'bum' of 'e' as it is null`（`e` = `instance`）。
- **触发链路** — Element Plus el-table/el-table-column/el-checkbox/el-tooltip/el-popper 递归 unmount 时，**某子 vnode.component 已是 null**（HMR/路由切换/keep-alive 边界状态）→ `vnode.type.remove(...)` 调 `unmountComponent(null)` → 爆。常见触发页：`AgentTracesView`（19 el-table）/ `TaskTrash`（18）/ `SpeakerMappingPanel`（8）/ `KnowledgeView`（4 tab lazy）/ `VoiceprintEnrollDialog`（el-dialog + el-tabs + lazy）。
- **修复：Vite plugin transform 阶段 patch esm-bundler.js**（commit `79305b7`）—
  ```js
  // vite.config.js
  function vueBumNullPatchPlugin() {
    return {
      name: 'vue-bum-null-patch',
      enforce: 'pre',
      transform(code, id) {
        if (!/node_modules\/@vue\/runtime-core\/dist\/runtime-core\.esm-bundler\.js$/.test(id)) return null
        if (code.includes('/* patch:vue-3.5-bum-null */')) return null  // 防重复
        const pattern = /(const\s+unmountComponent\s*=\s*\([^)]*\)\s*=>\s*\{)/
        if (!code.match(pattern)) { console.warn('...pattern not found'); return null }
        return code.replace(pattern, `$1\n    /* patch:vue-3.5-bum-null */ if (!instance) return;`)
      },
    }
  }
  ```
  验证产物 grep `(e,t,n)=>{if(!e)return;let{bum` 即生效。
- **纪律** — ① 这种"上游已知 bug 但未修复"的场景，**Vite plugin transform 阶段 patch** 比 npm postinstall patch 更稳（postinstall 会被 reinstall 覆盖；plugin 在 build 时每次生效）② `enforce: 'pre'` 确保在 esbuild/rollup 处理前 patch③ 防御性 `if (code.includes('...')) return` 防重复 patch④ pattern 未命中要 `console.warn` 而非静默吞（升级 Vue 后能立即发现 plugin 失效，需要重新适配）⑤ **只 patch build 产物，不 patch dev mode**（dev 保留原始报错方便定位应用层问题）
- **临时性 + 自动失效** — 升级到 Vue 3.5.36+/3.6+ 若官方修了 `unmountComponent` instance null 检查，plugin 自动 skip（pattern 未命中 → warn）。监控 console 是否有 `[vue-bum-null-patch] pattern not found` 警告

### 2026-06-13 Nginx types 指令覆盖/合并行为差异 — 整站 octet-stream 白屏事故（commit `08f440f` 留尾 → `f148d96` + `5c24442` 修复）

- **事故** — 用户报告"打开 /dashboard /members 直接下载名为 dashboard / members 的文件"。curl 验证 `/index.html` 返回 `Content-Type: application/octet-stream` → 浏览器把 HTML 当二进制下载而非渲染。
- **根因（极隐蔽，2 层）** —
  1. `commit 08f440f` 在 `server { ... }` block 内加 `types { application/manifest+json webmanifest; }` 块想修 webmanifest MIME 问题
  2. **Nginx `types` 指令在 server context 是"完全覆盖"语义（NOT 合并）**：从 http context 继承的 mime.types 整个被丢弃，只剩 types 块里的 MIME → `.html` 找不到 `text/html` → fallback 到 `default_type application/octet-stream` → 整站 HTML/CSS/JS/PNG 全变 octet-stream
  3. **极其隐蔽**：webhint 只查 manifest.webmanifest 不查 HTML，所以没暴露这个问题；用户浏览器可能缓存了 08f440f 之前的 HTML 没刷新，所以没立即发现
- **修复路径（commit `f148d96` + `5c24442`）**—
  - **第一步（f148d96）**：删除 tunnel.conf 两个 server block 里的所有 `types { }` block，恢复 http context mime.types 默认合并语义
  - **第二步（f148d96）**：改 `scripts/deploy-auto.sh` 增加 webmanifest MIME 注入：
    ```bash
    if ! grep -q 'application/manifest+json' /etc/nginx/mime.types 2>/dev/null; then
        sed -i '/^application\/json[[:space:]]/a\    application/manifest+json           webmanifest;' /etc/nginx/mime.types
        if grep -q 'application/manifest+json' /etc/nginx/mime.types 2>/dev/null; then
            log "webmanifest MIME type added to mime.types"
        else
            log "ERROR: webmanifest MIME sed injection failed"  # fail loud
        fi
    fi
    ```
  - **第三步（5c24442）**：原 awk 模式注入失败（猜测 mime.types 行尾 `\r` 导致 awk `next+print` 行为异常）→ 改 sed `-i` 行后追加模式 + 注入后 grep 验证
- **纪律（5 条铁律）** —
  ① **Nginx `types` 指令上下文敏感**——
  - `http` context：**合并**（additive，可加新 MIME 不丢默认）
  - `server`/`location` context：**完全覆盖**（覆盖后必须列全用到的 MIME，否则 fallback octet-stream）
  - 缺省 default：`application/octet-stream bin;`（最小集）
  ② **永远不要在 server context 加 types { } block** —— 想给 PWA 加 MIME 就在 mime.types 里加（http context include 的那个文件）
  ③ **deploy-auto.sh 注入 mime.types 必须 fail loud** ——
  - sed/awk 注入后必须 `grep -q` 验证成功才 log success，否则 `log "ERROR: ..."`
  - 注入幂等（先 grep 是否已存在）
  - 优先用 sed `-i` 而非 awk（awk 在行尾 `\r` 时行为异常）
  ④ **Webhint 不查 HTML MIME** ——
  - webhint 报 manifest MIME 错误时**只查** manifest 不查 HTML/CSS/JS
  - 加 types { } block 可能悄无声息破坏整站 MIME，**改 nginx 配置后必须 curl 验证所有响应 Content-Type**（HTML + CSS + JS + PNG + manifest + sw.js 至少 6 点）
  ⑤ **改 nginx 配置后立刻 6 点 curl 验证** —
    ```bash
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/index.html
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/  # SPA fallback
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/dashboard  # SPA route
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/sw.js
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/pwa-192.png
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/manifest.{hash}.webmanifest
    ```
    任一返回 octet-stream 即配置错误，不要等用户报告
- **事故链时间线** —
  1. 08f440f（18:27 加 types block，覆盖 mime.types，**事故起点**）
  2. c855f0e（18:30 加 manifest.webmanifest 410）
  3. ef130ce（18:32 CLAUDE.md）
  4. 79305b7（18:40 Vue patch）
  5. 7a077dd（18:42 CLAUDE.md）
  6. 0a29290（18:49 试图"修复"types block，加完整 MIME 列表，但 types 指令在 server context 行为不变，整站仍 octet-stream）
  7. 用户报告"下载文件"
  8. f148d96（18:58 真修复：回滚 types block + 改 deploy-auto.sh）
  9. 5c24442（19:05 修 awk → sed）

### 2026-06-13 SW 污染 cache 修复 — 整站 HTML 修复后浏览器仍进不去（commit `747a735`）

- **第二阶段事故** — 服务器 MIME 修好后（`f148d96` + `5c24442`）curl 验证 `/` 返回正确 `text/html`，但**用户报告"网站还是进不去"**。curl 服务器一切正常 → 100% 是浏览器侧问题。
- **根因** — Service Worker 污染 cache：
  1. `08f440f` 部署后服务器开始返回 octet-stream HTML
  2. 用户访问时浏览器 SW（NetworkFirst 策略）**缓存了 octet-stream 响应到 `documents` cache**
  3. 服务器修复后 SW 仍可能返回缓存的 octet-stream（虽然 NetworkFirst 应优先网络，但浏览器 SW 缓存逻辑 + activate 时机导致老 cache 没及时清）
  4. `cleanupOutdatedCaches()` 只清 workbox 维护的 precache cache，**不**清 NetworkFirst/StaleWhileRevalidate 运行时创建的 cache
- **修复：sw.js 升级模式**（commit `747a735`）—
  ```js
  // web/src/sw.js
  const SW_VERSION = 'v2-cache-purge-2026-06-13'  // BUMP 触发 SW 字节变化
  self.__SW_VERSION__ = SW_VERSION

  self.skipWaiting()
  self.addEventListener('activate', (event) => {
    event.waitUntil((async () => {
      // 清空所有 cache（不只是 workbox 默认的）
      const keys = await caches.keys()
      await Promise.all(keys.map((n) => caches.delete(n)))
      await self.clients.claim()
      // 通知所有客户端 reload
      const clients = await self.clients.matchAll({ type: 'window' })
      clients.forEach((c) => c.postMessage({ type: 'SW_UPDATED', version: SW_VERSION }))
    })())
  })
  ```
  ```js
  // web/src/main.js
  useRegisterSW({
    immediate: true,
    onRegisteredSW(swUrl) {
      navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data?.type === 'SW_UPDATED') {
          setTimeout(() => window.location.reload(), 500)
        }
      })
    },
  })
  ```
- **修复链路** — 用户下次访问 → 浏览器检测 `/sw.js` 字节变化 → 安装新 SW → 立即 `skipWaiting` 激活 → `activate` 钩子清空所有 cache + `postMessage` → 客户端 `useRegisterSW` 收到 `SW_UPDATED` → `window.location.reload()` → 用户拿到全新资源
- **纪律（4 条铁律）** —
  ① **SW 污染 cache 修复必须改 sw.js** ——
  - 只改 HTML/JS/CSS 没用，浏览器 SW 还在用老 SW 文件
  - 改 sw.js 触发 SW 升级 + activate 钩子清 cache 是**唯一**标准修复路径
  ② **`cleanupOutdatedCaches()` 不够** ——
  - 它只清 workbox 维护的 precache cache
  - **不**清 NetworkFirst/StaleWhileRevalidate/CacheFirst 运行时创建的 cache
  - 真正"清空所有 cache"必须自己写：`caches.keys() + Promise.all(keys.map(caches.delete))`
  ③ **BUMP SW_VERSION 触发升级** ——
  - 浏览器通过**字节比较**检测 SW 更新（不是 SW 内容里的 manifest）
  - 改 sw.js 文件加一行 const 都会触发字节变化 → 浏览器拉新 SW → 升级流程
  - 每次事故修复或 SW 大改动时**都**应 bump 版本号
  ④ **postMessage + reload 闭环** ——
  - SW 升级后**不会**自动刷新页面（skipWaiting + clients.claim 立即接管但页面不 reload）
  - 必须 SW postMessage → 客户端监听 → `window.location.reload()`
  - 用 `setTimeout(..., 500)` 让 console.log 先显示出来再 reload
- **调试技巧** ——
  - 用户报"页面进不去"但服务器 curl 一切正常 → 100% 是 SW/浏览器 cache 问题
  - 让用户 DevTools → Application → Service Workers → 看到 SW 状态为 `activated` 且内容含新 `SW_VERSION` → SW 已升级
  - 让用户 DevTools → Application → Cache Storage → 应该看到 precache 列表**无 documents cache**（已被清空）
  - **兜底**：用户可手动 DevTools → Application → Storage → Clear site data 彻底重置

### 测试规范
- **后端**：pytest + httpx AsyncClient，service 层单元测试 + API 集成测试
- **前端**：Vitest + @vue/test-utils，composable 测试优先，组件测试选择性覆盖
- **Mock 策略**：Redis 用 fakeredis，Claude API 用 respx，Embedding 用固定向量

## 服务层结构

| 文件 | 职责 |
|------|------|
| `app/services/task_service.py` | 任务 CRUD + 统计 + 自动提醒 |
| `app/services/member_service.py` | 成员 CRUD + 按姓名查询 |
| `app/services/meeting_service.py` | 会议 CRUD + 参与者管理 |
| `app/services/project_service.py` | 项目+里程碑 CRUD |
| `app/services/knowledge_service.py` | 知识库 CRUD + 语义搜索 |
| `app/services/reminder_service.py` | 提醒服务 + Celery task |
| `app/services/memory_service.py` | 长期记忆 CRUD + 语义搜索 + LLM 提取 |
| `app/services/search_service.py` | 联网搜索（搜狗+必应双引擎） |
| `app/services/embedding_service.py` | 向量嵌入（text2vec-base-chinese） |
| `app/services/file_parser_service.py` | 文件内容提取（PDF/Word/Excel/PPT） |
| `app/services/llm_analysis_service.py` | LLM 内容分析（动态分类+标签+摘要+核心概念） |
| `app/services/knowledge_graph_service.py` | 知识图谱服务（自动关联+BFS 遍历+动态分类+标签云+统计） |
| `app/services/knowledge_qa_service.py` | RAG 问答引擎（检索+阈值+LLM 合成+来源引用） |
| `app/services/auto_research_service.py` | 自主研究引擎（联网搜索+知识提取+空白填充+矛盾/重复/过期检测） |
| `app/services/dynamic_taxonomy_service.py` | 动态分类体系（涌现分类+分类建议+主题网络） |
| `app/services/knowledge_evolution_tasks.py` | Celery 知识进化定时任务（每日进化/空白检测/健康检查/实体融合） |
| `app/services/reminder_scheduler.py` | Redis 精确提醒调度（秒级精度） |
| `app/services/entity_service.py` | 实体知识图谱（跨文档融合+搜索+图谱+LLM 合并） |
| `app/services/hypothesis_service.py` | 科研假设生成（LLM 驱动假设+验证生命周期） |
| `app/services/formula_service.py` | 量化推理（公式列表+安全计算+LaTeX 转换+分类树+内置公式库） |
| `app/services/meeting_analysis_service.py` | 会议 AI 分析（发言者检测+格式识别+结构化分析+发言人统计+标题生成）|
| `app/services/voiceprint_service.py` | 声纹识别（3D-Speaker 嵌入提取+pgvector 匹配+录入）|
| `app/voice/vad.py` | silero-vad 语音活动检测 |
| `app/services/audio_processor.py` | 音频格式转换（WebM→WAV）+ 离线 VAD 分段 |

## 2026-06-14 方案 C：Agent 单阶段流式渐进综合架构（plan: eager-juggling-dewdrop.md）

**6 个 stage 已收官**（commits `5ce1203` `8a76750` `9862546` `d3f74df` `59cbbb1` `2f2b619` `bf61456`）。
核心改造：取消 brief/detail 双层 → 单阶段流式综合（intent → agentic_loop → critique → done）。

### 方案 C 6 条铁律（必读）

**铁律 1：跨 event loop 安全（CLAUDE.md 752/812 行铁律升级）**
所有外部 IO 客户端（AsyncAnthropic / aioredis / async_session）**禁止在模块顶部 import 阶段创建**。统一通过 `ctx: ToolContext` 注入：
```python
# ❌ 反模式（agentic_loop.py 模块顶部）
from app.core.redis import async_redis_client  # 绑定 app loop 的全局单例
client = AsyncAnthropic(...)                   # 同上

# ✅ 正模式（ctx 注入）
async def run(self, ..., ctx: ToolContext):
    redis = ctx.redis or aioredis.from_url(settings.REDIS_URL)
    llm = ctx.llm or LLMClient()
```
`ToolContext` 字段：`redis` / `llm` / `loop_id`（debugging）。Celery worker 跨 event loop 调用时由调用方注入新 client，否则触发 "Future attached to different loop"。

**铁律 2：typing import CI 检查**
任何 `app/agent/*.py` 新文件**必须**在 commit 前跑：
```bash
bash scripts/check_typing_imports.sh   # 106 文件 0 错误
```
新代码若用了 `Dict`/`List`/`Optional` 但没 `from typing import ...` → 整个模块加载失败 → 工具一调就报。Docker 模块缓存会掩盖该 bug 数天。建议集成到 pre-commit hook。

**铁律 3：SSE 事件 delta 语义显式标注**
[app/agent/protocol.py](app/agent/protocol.py) 每个 `StreamEventType` 必须在源码注释里标注 `[increment]` 或 `[snapshot]`：
- `[increment]` delta 是新增 token，前端必须 `content += delta`
- `[snapshot]` delta 是完整快照文本，前端必须 `content = delta`（替换）或不 append
- 混用会导致 2026-06-12 brief 重复输出 bug（commit `cf70ff5`）再现
- 前端 useChatStream.ts switch case 也必须标注

**铁律 4：流式 abort 安全（trace 持久化 + 悬空 tool_use sanitize）**
`chat_engine.synthesize_stream()` 必须用 `async with TraceCollector(...) as trace` 包裹：
- `TraceCollector.__aexit__` 收到 `CancelledError`/`BaseException` 时**同步**落库（不走 Celery），保证 trace 至少有 partial 记录
- `agentic_loop.run()` 在收到 `CancelledError` 或循环达到 `max_rounds` 时，必须调 `_sanitize_pending_tool_uses(messages, reason=...)`：给悬空 tool_use 追加 `tool_result: "用户已中断"` 哨兵，否则下次拼回 context 时 Anthropic API 报 400
- `_sanitize_pending_tool_uses` 必须在调下一次 LLM 前调

**铁律 5：LLMClient 接口加 model 参数用 keyword-only**
```python
async def complete(self, messages, *, model=None, system=None, ...):
    # `*` 强制所有调用走关键字
```
老代码传位置 model 必报 TypeError（炸得明显），不会静默走错模型。LRU cache key 必须含 model 维度（防不同模型互相污染缓存）。

**铁律 6：feature flag 必须保留老路径代码（不是 git revert）**
3 个 kill switch（**2026-06-29 已全部删除**，见 [## 2026-06-29 chat_engine_legacy 收官](#2026-06-29-chat_engine_legacy-30-天承诺提前-15-天收官)）：
- `AGENT_NEW_ARCHITECTURE_ENABLED: bool = True`（全局开关）
- `AGENT_REFLECTION_ENABLED: bool = True`
- `AGENT_COMPRESSION_ENABLED: bool = True`
- 关闭时由 `chat_engine.py` 内部调 `chat_engine_legacy.py`（保留作为 30 天回滚资产，**不是 in-file dead code**）
- 30 天后（2026-07-14）单独 commit 删除 `chat_engine_legacy.py` → **已提前 15 天（2026-06-29）收官** (commit `817f1ffa`)

### 2026-06-29 chat_engine_legacy 30 天承诺提前 15 天收官

**触发**：方案 C 2026-06-14 上线，配套保留 `app/agent/chat_engine_legacy.py`（460 行老 brief+detail 双层架构）作为 30 天回滚资产，配合 3 个 feature flag。30 天观察期（15 天已过 + 0 流量走 legacy + 生产 100% 走新架构）决定提前收官。

**评估结果**：
- ✅ 生产 0 流量走 legacy（3 flag 默认 `True`，`.env` / `docker-compose` 0 覆盖为 `False`）
- ✅ 无运行时 ImportError 兜底，删文件不会触发异常
- ⚠️ 4 个 unit test 断言依赖 legacy 文件 / flag，必须同步删除
- ⚠️ 提前 15 天违反 30 天承诺 → docs 加注"提前于 2026-06-29 删除"

**原子 1 commit 收官**（详见 git log）：
- **删除（1）**：`app/agent/chat_engine_legacy.py`（460 行）
- **修改（10）**：
  - `app/agent/chat_engine.py` — 移除 kill switch + `_legacy_chat_stream` 委托方法 + 相关注释
  - `app/agent/critic.py` — 移除 `AGENT_REFLECTION_ENABLED` 短路
  - `app/agent/result_compressor.py` — 移除 `AGENT_COMPRESSION_ENABLED` 短路
  - `app/agent/agentic_loop.py` — 移除 `AGENT_COMPRESSION_ENABLED` 包裹
  - `app/config.py` — 删除 3 个 settings 字段
  - `tests/unit/test_chat_engine_synthesize.py` — 删除 3 个 legacy 相关测试
  - `tests/unit/test_agent_v2_main.py` — 删除 1 个 legacy 相关测试
  - `tests/perf/conftest.py` + `test_synthesis_latency.py` — docstring 清理
  - `docs/stage5-rollout-runbook.md` — 改写回滚步骤
  - `CLAUDE.md` — 本节加注

**回滚路径**：`git revert <commit-hash>` 一行撤销 + 重新部署。< 5 分钟恢复。

### 部署必做

```bash
# 1. 跑数据库迁移（Stage 3 加 7 列）
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -f scripts/alter_agent_traces_stage3.sql

# 2. 重启 Python 进程（CLAUDE.md 752 行铁律）
docker compose restart app celery-worker
```

不跑这两步，新架构写入 `intent_category` 等列会报 `column does not exist` 500。

### 方案 C 没做的（plan 明确范围外）

- LangGraph 风格 state machine 重写
- 多 agent 独立服务（planner / executor / critic）
- 流式 ChartBlock 渐进渲染（边输出文字边出图）
- RAG 引用图谱可视化
- ASR/TTS 真流式（边录音边出文字）
- ~~30 天后删除 `chat_engine_legacy.py`（2026-07-14）~~ — **已于 2026-06-29 提前 15 天完成** (commit `817f1ffa`)（见上节"## 2026-06-29 chat_engine_legacy 30 天承诺提前 15 天收官"）


## 完整历史任务链

所有"## 2026-XX-XX" 历史任务链 / "### lesson learned" 子章节 / "## 开发注意事项（历史）" 段都已迁移到 [docs/CLAUDE-history.md](./docs/CLAUDE-history.md) (P3-15 拆分于 2026-07-08).

**为什么拆分**: CLAUDE.md 拆前 645KB (8082 行) 含 60+ 历史任务链, Claude 会话启动需全量 read, 减慢 system prompt 处理. 拆分后核心 ≈ 50KB, Claude 启动更快.

**Claude 行为**:
- 新会话默认只读 CLAUDE.md 核心 (50KB) — 不再加载历史 lesson
- 历史相关查询可主动 \`@ docs/CLAUDE-history.md\` 或 \`@<path>\` 引用
- 不破坏现有所有引用 (CLAUDE.md 顶部 "当前任务链" 块保留)
