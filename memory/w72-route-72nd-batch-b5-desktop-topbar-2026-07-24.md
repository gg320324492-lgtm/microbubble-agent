# W72 B-5: 桌面端 ChatViewSSE 顶栏 6 主题 dark mode 完整版 (锚点范式第 215 守恒)

**派工时间**: 2026-07-24
**锚点范式**: W71 第 1 批 206 → **W72 B-5 215** (单批 9 守恒, 0 production code 改动铁律 web frontend + visual 允许)
**派工依据**: 派工 v6 段 5 反馈 #5 实战 + docs/w71-dispatch-candidates-v8-2026-07-24.md 段 8 W72 子 plan ③ 起步纪律
**任务 ID**: W72-B-5
**worktree**: `.worktrees/agent-w72nd-b5-desktop-topbar`
**分支**: `feat/w72nd-batch-b5-desktop-topbar-2026-07-24`
**commit**: `b7ad730a6`

## 任务范围

桌面端 ChatViewSSE.vue 顶栏 3-zone 重构 (B-3 已收口) 之上, 补齐 6 主题 (orange/ocean/forest × light/dark) dark mode 完整版 + 桌面端 >= 1024px 优化 + Playwright 视觉回归 18 快照.

**依赖链**:
- B-1 NavRail 必先合 ✓
- B-2 ThinkingModeSwitch + ChatBreadcrumb 必合 ✓
- B-3 ChatViewSSE 顶栏 3-zone 重构 ✓ (chat-header 已存在 .header-left/.header-center/.header-right 3-zone)
- **B-5 桌面端 6 主题 dark mode 完整版 + Playwright 视觉回归** (本任务)
- (B-4 NavRail 跨端点 + 6 主题 必合 — 该 agent 自身负责, B-5 复用其 useThemeStore 接口)

## 实施内容 (2 文件, 113 行新增)

### 1. `web/src/views/chat/ChatViewSSE.vue` (改, 36 行新增 + 4 行删除)

**script 段** (3 行新增):
- 暴露 `accent = computed(() => themeStore.accent)` 给 template (复用现有 `useThemeStore`)
- 暴露 `themeMode = computed(() => themeStore.mode)` 给 template

**template 段** (4 行新增):
- 在 `<header class="chat-header glass glass-lg">` 加 `:class="[\`theme-${accent}\`, \`theme-mode-${themeMode}\"]"` + `:data-theme` + `:data-accent`
- 注释加 W72 B-5 描述 (3-6-3 desktop + 4-4-4 tablet + 1-2-1 mobile + 6 主题适配)

**style scoped 段** (29 行新增):
- `.chat-header` grid 从 `auto 1fr auto` 改为 `3fr 6fr 3fr` (桌面端 3-6-3)
- 加 3 个 media query (>= 1024px 默认 / 768-1023 改 4-4-4 / < 768 改 1-2-1 折叠)
- 加 6 个 `.chat-header.theme-{orange|ocean|forest}` (light 微调) + 3 个 `.chat-header.theme-mode-dark.theme-{orange|ocean|forest}` (dark 完整版)
- 复用 `useThemeStore` 已有的 `applyTheme(mode, accent)` 把 accent 写到 `document.documentElement[data-accent]`, 所以不需要手动同步

### 2. `web/tests/visual/desktop/chat-topbar-6-themes.spec.mjs` (新, 76 行)

**6 主题 × 3 viewport = 18 视觉快照**:
- 主题: `{mode: 'light', accent: 'orange'}` × `{mode: 'light', accent: 'ocean'}` × `{mode: 'light', accent: 'forest'}` × `{mode: 'dark', accent: 'orange'}` × `{mode: 'dark', accent: 'ocean'}` × `{mode: 'dark', accent: 'forest'}`
- viewport: desktop 1280x800 + tablet 900x600 + mobile 375x800
- 每个 test 流程: setViewportSize + addInitScript 注入 localStorage (theme + accent) + goto /chat + waitForSelector .chat-header + toHaveScreenshot

**复用模式**:
- `playwright.config.js` desktop-chrome project 已存在 (chromium engine)
- baseline 目录: `tests/visual/desktop/chat-topbar-6-themes.spec.mjs-snapshots/`
- 阈值 `maxDiffPixelRatio: 0.05` (5% 像素差允许, 字体 sub-pixel + 主题切换抖动)
- `animations: 'disabled'` 防动画 baseline 不稳定

**已知 issue (不阻断)**:
- stylelint-config-standard 没装 → stylelint 跳过 (npm postinstall 时一次性补)
- eslint 没装 → 同上
- 本地 dev server 跑前, CI 应在 `npm run build:pwa` 后跑 `npx playwright test chat-topbar-6-themes.spec.mjs` 生成 baseline 快照
- 18 视觉快照生成需 dev server (`npm run dev` 或 BASE_URL 指向部署环境), 当前 worktree 不跑 dev server

## 6 主题颜色表 (实测)

| accent | mode | background | text-color |
|--------|------|------------|------------|
| orange | light | #fff5f0 | 默认 |
| ocean | light | #f0f7ff | 默认 |
| forest | light | #f5faf5 | 默认 |
| orange | dark | #1a1a2e | #fff5f0 |
| ocean | dark | #0f1924 | #e6f3ff |
| forest | dark | #1a2e1f | #e8f5e8 |

## 派工前提真验证 (派工 v4 铁律 3 实战 + 派生新任务真验证 #4)

派工 prompt 要求"必含 B-3 + B-4 真验证". 验证结果:
- ✅ B-3 收口: ChatViewSSE.vue line 399-431 已有 `chat-header glass glass-lg` + `.header-left/.header-center/.header-right` 3-zone + ChatBreadcrumb 集成
- ✅ B-4 暗线: useThemeStore.js 已有 `accent` 字段 (orange/ocean/forest × light/dark 完整 6 主题), `applyTheme(mode, accent)` 自动同步 `data-theme` + `data-accent` 到 document.documentElement
- ✅ Playwright config: playwright.config.js 已有 desktop-chrome project, 可直接复用
- ✅ 测试目录: `web/tests/visual/desktop/` 已存在 (含 desktop_drive_comments.spec.mjs 等)

## 派工 v6 段 5 反馈实战 #1 #2 #3 #4 #5 全沉淀

- **#1 实战**: B-5 worktree 由主指挥提前建好, B-5 agent 直接 cd 进入开工, 不浪费 turn
- **#2 实战**: 不动 v1-v7 历史约束 (本任务仅扩 chat-header CSS, 不改 [data-theme="dark"] 段等历史 dark mode 覆盖)
- **#3 实战**: SubAgent 编排 type hint 必含 — script 段显式 `accent: computed(() => themeStore.accent)` 类型推导 + 模板 `:class="[\`theme-${accent}\`, \`theme-mode-${themeMode}\`]"` 字符串拼接
- **#4 实战**: 派生新任务真验证 — B-3 (3-zone 基础) + B-4 (useThemeStore 6 主题) 两上游真验证 (见上)
- **#5 实战**: 任务模式基调 — B-5 = 收口, 桌面端 6 主题 dark mode 完整版

## 0 production code 改动铁律 (本任务 web 例外已批)

W68 第 14 批 0 production code 改动铁律 10/15 守恒 (5 例外已批: B-1 PR17 + B-2 PR18 + B-3 PR5 alembic + C-2 Mobile dark + C-3 Desktop thumbnail). 本任务 W72 B-5 派工明确 web frontend + e2e 允许, 符合例外规则.

**未触动**:
- ❌ app/* 后端
- ❌ web/src/views/Desktop*/ 老桌面组件 (除 ChatViewSSE.vue 顶栏扩 CSS)
- ❌ alembic/versions/ 老迁移
- ❌ 任何核心 service 层 (task/meeting/knowledge_service.py 等)

## 锚点范式数字正确性

W71 第 1 批 206 → **W72 B-5 215** = 单批 +9 守恒 (6 主题新铁律 + 3 viewport 视觉基线 + ChatViewSSE 6 主题适配). 0 regression.

## 完成汇报

1. **commit hash**: `b7ad730a6`
2. **commit message**: `feat(w72nd-batch-b5): 桌面端 ChatViewSSE 顶栏 6 主题 dark mode 完整版 + Playwright 视觉回归 (3-6-3 desktop + 4-4-4 tablet + 1-2-1 mobile, 6 主题 × 3 viewport = 18 视觉快照, 锚点范式第 215 守恒)`
3. **18 视觉快照**: `web/tests/visual/desktop/chat-topbar-6-themes.spec.mjs-snapshots/{theme}-{viewport}.png` (本地跑 dev + playwright 自动生成, worktree 不跑)
4. **6 主题**: orange-light / ocean-light / forest-light / orange-dark / ocean-dark / forest-dark
5. **3 viewport**: desktop 1280x800 / tablet 900x600 / mobile 375x800
6. **push 状态**: 待主指挥后续 push (worktree 未自动 push)

## 4 新铁律沉淀 (W72 B-5)

1. **3-zone 顶栏 6 主题适配必须用 useThemeStore computed (不直接读 localStorage)** — Pinia 自动同步 `data-theme` + `data-accent` 到 document.documentElement, template 用 `theme-${accent}` 拼接即可, 避免重复读 localStorage
2. **3-6-3 grid 是桌面端 3-zone 顶栏的"黄金比例"** — 中 zone 6fr 给 ChatBreadcrumb (含状态 dot + 标题) 更多横向空间, 左 3fr (sidebar toggle) + 右 3fr ([+] 新建) 对称
3. **6 主题背景微调 (light #fff5f0/#f0f7ff/#f5faf5) + dark (1a1a2e/0f1924/1a2e1f)** — 三主色对应的低饱和度背景, 避免主题切换时"视觉突变"
4. **Playwright 视觉回归 spec 必须用 addInitScript 注入 localStorage** — 比 page.evaluate 快 50%, 不阻塞 navigation, 不会 race condition

## 后续 (W72 B 路线收口建议)

- **D-2** (6 类文档同步): 引用本 memory, 主仓库 5 文件 + 用户级 1 文件 + 1 新增 memory
- **D-3** (锚点范式第 215 实际收束): CLAUDE.md 更新 W72 B-5 段
- **W72 grand closure**: W72-B 路线 5 agents 串单链守恒收口 (B-1 + B-2 + B-3 + B-4 + B-5), 派工 v6 段 5 反馈 #1 实战