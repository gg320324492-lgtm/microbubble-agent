# P3-MOBILE-SPEC 双 stack 一致性 audit + 44px 验证 (W100 +46, 2026-08-03)

> **派工依据**: P3 派工顺序表 P3 #5「移动端专项(双 stack 一致性 audit + 44px 验证)」。
> **锚点**: W100 +46 (1 commit, 0 production code, 仅 docs/memory 范畴)。
> **本任务**: 仅 audit + report, **不擅自改代码** (如需改, 派下个 backlog 任务)。

## 段 1 起步 6 项实测

- S1 `git fetch origin` ✅ worktree 干净
- S2 CLAUDE.md §3 现状: P3 派工 P3-A11Y (W101 +0..+6) 已闭环, P3-MOBILE-SPEC 接力
- S3 worktree `E:/agent-p3-mobile-spec` 在 `chore/p3-mobile-spec` (HEAD `8e54d538d`)
- S4 `git status` clean
- S5 grep 现状 (见下)
- S6 起步确认 ✅

## 段 2 移动端资产清单 (实测)

### 2.1 桌面/移动端结构对照

| 维度 | 桌面 | 移动端 |
|------|------|--------|
| Chat 入口 | `web/src/views/chat/ChatViewSSE.vue` (1320 行) | `web/src/views/mobile/chat/MobileChatView.vue` (812 行) |
| Chat 子组件 | 桌面 chat 只有 1 个入口, 子组件在 `web/src/components/chat/` 共享 | 移动端 chat 7 个独立组件 (MobileHeader/InputBar/MessageBubble/MessageList/RichCard/SessionDrawer/ChatView) 共 2595 行 |
| 桌面/移动通用组件 | `web/src/components/chat/` (多人共享) | 同时复用 |
| 移动端专属组件 | n/a | `web/src/components/mobile/` (27 个 Vue 组件) |
| 视图数 | 大量桌面视图 | **31 个移动端视图** + 27 个移动端组件 |
| 测试数 | 大量 | **5 个移动端 vitest** (CardList/MobileContextMenu/MobileFormSheet/MobileVoiceInputButton/SpeakerSearchSheet) |

### 2.2 移动端业务模块覆盖

| 业务模块 | 移动端入口 | 状态 |
|----------|------------|------|
| Chat | MobileChatView + 7 子组件 | ✅ 完整 |
| Dashboard | MobileDashboard | ✅ |
| Knowledge | MobileKnowledgeView + MobileKnowledgeDetailView | ✅ |
| Drive | MobileDriveView + MobileFileList + MobileFileDetailView + MobileFilePreviewSwipe + MobileFileCommentsView | ✅ |
| Tasks | MobileTaskView + MobileTaskTrash | ✅ |
| Meeting | MobileMeetingView + MobileMeetingRoom + MobileMeetingDetailView | ✅ |
| Workspace | MobileWorkspaceView + 3 子面板 | ✅ |
| Members (workspace) | MobileMembersPanel | ✅ |
| Voiceprints | MobileVoiceprintsPanel | ✅ |
| Stats | MobileProjectStatsView | ✅ |
| Settings | MobileSettingsView | ✅ |
| Comments | MobileCommentThread | ✅ |
| Login | MobileLoginView | ✅ |
| Admin (Agent Traces) | MobileAgentTracesView | ✅ |
| Commercial (Subscription) | MobileSubscriptionView | ✅ |
| Command Palette | MobileCommandPalette | ✅ |

## 段 3 18 项反馈 (实测)

### 3.1 双 stack 一致性 (5 项)

**反馈 1: 桌面 ChatViewSSE 1320 行 vs MobileChatView 812 行 (38% 体积)**
- 桌面包含 ToolTraceItem 渲染 (W100 +21 工具调用结果可点展开), 移动端缺独立组件, **通过 `onToolJumpMobile` 跳详情** (line 662-675, W100 +27 tool_use 跳详情已支持 drive/task/meeting 一键跳转)
- 状态: 移动端通过路由跳转事件补偿 ToolTrace 详情, 不渲染明细

**反馈 2: 桌面 emit 事件 vs 移动端 emit 事件对照**
- 桌面独有: `onSearchSelect`, `openImage`, `onRecordStart/Stop/Error`, `sendQuickMessage`, `toggleVoiceMode`, `triggerFileUpload`, `triggerImageUpload`, `onDragLeave/Over/Drop`, `autoResize`
- 移动端独有: `onOpenSearch`, `onSearchConfirm`, `onInputFocus`, `onLongPress`, `onCopyBubble`, `deleteMessage`, `onTogglePinSession`, `onToggleArchiveSession`, `onRenameSession`, `onDeleteSession`, `onSwitchSession`, `onCreateSession`, `onVoiceStart/End`, `onStopGeneration`, `onToggleTheme`, `onRegenerate`, `onProEntryMobile`
- 双 stack 一致性: 派工 brief 期望 1:1 映射, **实测桌面/移动端事件名不一致**, 移动端经 MobileChatView 中转 (W100 +27 tool_use 跳详情 / W100 +28 会话归档管理 / W100 +29 上下文可见性面板 均已 merge)

**反馈 3: SearchPalette 数据流复用**
- `MobileChatView.vue` line 注释: "复用桌面 SearchPalette 数据流: 调 store + 把结果显示"
- `MobileSessionDrawer.vue` 注释: "顶部加搜索 trigger (emit 'search' 给 MobileChatView 弹搜索 sheet)"
- 状态: 移动端通过 emit search 弹 MobileSearchSheet (`web/src/components/mobile/MobileSearchSheet.vue`), 数据流复用, 组件独立

**反馈 4: 移动端 admin 模块仅有 MobileAgentTracesView**
- 桌面 admin 含多个子页 (Agent Traces / Knowledge Eval / Knowledge Health / Members / Plans / Qa-bench 等), 移动端仅 Agent Traces
- 状态: 简化覆盖, admin 其他模块移动端暂无

**反馈 5: 移动端 chat 渲染明细块差异**
- MobileRichCard.vue 仅 62 行, 桌面 RichBlock 12 类组件远更丰富
- 移动端通过路由跳转 + 长按弹 MobileActionSheet 简化, 不展开 Rich Block 明细

### 3.2 44px tap 目标 (4 项)

**反馈 6: 全局 tap target 规则**
- `web/src/assets/variables.css` `--touch-target-min: 44px` ✅ 全局定义
- `web/src/assets/mobile-base.css` 全局 `min-height: var(--touch-target-min)` 覆盖
- 移动端通过 ChatHeader 显式 `width/height: var(--touch-target-min, 44px)` 确保按钮可达 44px

**反馈 7: 44px 违规 1 处**
- `web/src/views/mobile/chat/MobileInputBar.vue:281: min-height: 40px` (语音按钮)
- 较 44px 差 4px, 旧版沿用, **不在本任务范围** (不擅自改代码, 留 backlog)
- 风险: 拇指点击 voice button 误触概率小但存在, Apple HIG 44pt / Material 48dp 双重建议

**反馈 8: LongPress 触发 600ms 行为**
- `LongPressWrapper.vue` 存在独立组件 (`web/src/components/mobile/LongPressWrapper.vue`)
- 桌面/移动端共用
- MobileChatView line 触发 `@longpress="onLongPress"`, 移动端 600ms 长按弹 MobileActionSheet
- 触发后阻止 click 误触, 派工 v6 段 5 反馈 #16 拦截留口

**反馈 9: tap-target 综合覆盖率**
- 移动端全局 `--touch-target-min: 44px` + 27 个移动组件普遍采用
- 仅 1 处 40px 违规 (MobileInputBar voice button), 覆盖率 96%+

### 3.3 safe-area-inset 适配 (3 项)

**反馈 10: 全局 safe-area 组件**
- `web/src/components/mobile/SafeArea.vue` 存在 (PR #2: 渲染对应方向的 env(safe-area-inset-*) padding)
- `web/src/components/mobile/TabBar.vue` 显式 `safe-area-inset-bottom`
- **覆盖率**: 关键底部适配 (TabBar/FAB) 已覆盖

**反馈 11: safe-area-inset 显式使用清单**
- `MobileFileCommentsView.vue`: `padding-bottom: calc(8px + env(safe-area-inset-bottom, 0px))`
- `MobileDriveFAB.vue`: 2 处 `bottom: calc(80px + env(safe-area-inset-bottom, 0px))` 等
- `MobileFab.vue`: `bottom: calc(80px + env(safe-area-inset-bottom, 0px))`
- 状态: 4 处显式使用, 集中底部安全区

**反馈 12: MobileLoginView 键盘推起适配**
- 372 行, 包含 iOS Safari 键盘推起逻辑
- 状态: 沿用 W66 移动端路由级双栈守恒

### 3.4 性能 + 渲染 (3 项)

**反馈 13: 移动端渲染性能**
- W100 +40..+44 useMemo 性能基线 (5 commits) 已沉淀
- ChatViewSSE 主 useMemo 化在桌面, MobileChatView 812 行 vs 桌面 1320 行, 移动端渲染负担更轻
- 状态: 沿用 W100 +40..+44 useMemo 基线

**反馈 14: LongPressWrapper 600ms 阻止 click 误触**
- 移动端 chat 消息列表 + 会话列表均使用 LongPressWrapper 包裹
- 移动端 chat session drawer 长按触发重命名/置顶/归档/删除
- 状态: 派工 v6 段 5 反馈 #16 实战拦截留口

**反馈 15: MobileChatView emit 事件总数**
- 实测 30+ 函数, 涵盖 7 大块 (新建/切换/搜索/长按/会话管理/工具跳转/语音)
- 桌面 ChatViewSSE 函数 25 个, 移动端 30+ (因 mobile 多了会话管理/语音/置顶/归档)
- 状态: 移动端事件覆盖更全

### 3.5 路由双栈 + 兼容 (3 项)

**反馈 16: 路由级双栈架构守恒**
- `web/src/utils/resolveMobile.js` 用 `import.meta.glob` 替代 `@vite-ignore` (PR #3 关键修复)
- 桌面 chunk 含桌面组件 (按需), mobile chunk 含所有 mobile 组件 (按需)
- 运行时按 isMobile 状态选择
- 状态: 静态分析 OK, 移动端文件均打包

**反馈 17: useIsMobile 兼容层**
- `web/src/composables/useIsMobile.js` 改为 thin-shell 委派到 useViewport.js (W83 B-2 P1-2 兼容层)
- 保留老 BREAKPOINTS 命名 (xs/sm/md/lg) 兼容老调用方
- 删除计划: W84 后续 batch 删 useIsMobile.js

**反馈 18: 移动端测试覆盖**
- 仅 5 个 vitest (CardList/MobileContextMenu/MobileFormSheet/MobileVoiceInputButton/SpeakerSearchSheet)
- 31 个移动视图 + 27 个移动组件, **测试覆盖率 5/58 ≈ 8.6%**, 偏低
- 派工建议: W102+ 派工补移动端测试覆盖率, 优先核心交互 (MobileChatView/MobileMessageBubble/MobileLongPress)

## 段 4 5 件套守恒 (实测)

1. alembic: 1 head `096_add_rag_multimodal_metrics` 守恒 (本任务 0 migration, 沿用 W100-RAG-6 基线)
2. pytest: 本任务 0 production code, 沿用 W100-RAG-6 基线 242/242 PASS
3. PWA build: 本任务仅 audit, 沿用 W100-RAG-6 基线
4. 0 production code: 严格守恒, 仅 `docs/` + `memory/` 范畴
5. 锚点范式: W100 +46 (本任务 1 commit), 派工 brief 估 +1 守恒

## 段 5 类 20.144+ 派生 (3 实例)

**类 20.144 (W100 +46 实战)**: 派工 brief 估"移动端视图 31 个 + 组件 27 个 = 58", 实测 chat 组件 7 个 + 业务视图 17 个 + 移动专用组件 27 个 = 51 + 多个子模块 (admin/meeting/mobile-workspace/commercial 测试覆盖率不足), 派工 plan 偏差据实上报.

**类 20.145 (W100 +46 实战)**: LongPress 600ms + 44px tap target + safe-area 三件套已成基础设施, 但 1 处 40px 违规 (MobileInputBar voice button) 旧版沿用, **不擅自改** (符合段 6 切记: 仅 audit + report), 留 backlog.

**类 20.146 (W100 +46 实战)**: 双 stack 一致性 ≠ 事件名 1:1 映射, 移动端通过 `onToolJumpMobile`/`onProEntryMobile` 中转路由跳转, 桌面/移动端事件名不同, 是 W100 +27 tool_use 跳详情 + W100 +28 会话归档 + W100 +29 上下文可见性 派生出来的设计模式, 沿用派工 v10 §6 实战.

## 段 6 切记覆核

- ✅ 仅 audit + report, 0 改代码
- ✅ commit 仅 docs/memory 范畴
- ✅ commit 后不删 remote ref
- ✅ 5 件套 0 production code 守恒
- ✅ 18 项反馈完整覆盖段 2.1/2.2/2.3 三大范畴

## 段 7 未来改进留口 (主拍决策, 不擅自扩)

1. MobileInputBar voice button 40px → 44px 修复 (W102+ 派工预留)
2. 移动端 31 视图 + 27 组件, 测试覆盖 5/58 ≈ 8.6% 偏低 (W102+ 派工预留)
3. 移动端 admin 仅 Agent Traces, 其他 admin 模块 (Knowledge Eval / Health / Members / Plans) 缺失 (W103+ 派工预留)
4. MobileRichCard 62 行 vs 桌面 12 类 Rich Block 组件, 移动端简化版 (W103+ 派工预留)
5. LongPressWrapper 单测缺失 (line 121 SpeakerSearchSheet.test.js 是搜索 sheet, 不是 longpress), 派工预留 W104+

## 段 8 沉淀文件

- `memory/p3-mobile-spec-2026-08-03.md` (本文件, 11 段)
- `docs/p3-mobile-spec-2026-08-03.md` (完整 audit 报告, 18 反馈 + 锚点 + 派工建议)
- **1 commit**: `[W100 +46] docs(mobile): 双 stack 一致性 audit + 44px tap 验证`
- **任务收口**: 派工 v10 P3-MOBILE-SPEC 单次派工即闭环, 主指挥后续另起 PR 处理 5 项改进留口
