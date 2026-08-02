# P3-MOBILE-SPEC 移动端专项 audit 报告 (W100 +46, 2026-08-03)

> **派工依据**: P3 派工顺序表 P3 #5「移动端专项(双 stack 一致性 audit + 44px 验证)」。
> **核心结论**: 移动端 31 视图 + 27 组件覆盖核心 16 个业务模块, 双 stack 通过 emit + 路由跳转补偿一致性,
> 44px tap target 覆盖率 96%+ (1 处 40px 旧版违规), safe-area 关键节点已覆盖, 测试覆盖率 5/58 ≈ 8.6% 偏低。

## 1. 范围与目标

- **双 stack 一致性 audit**: 桌面 ChatViewSSE ↔ 移动端 MobileChatView 组件对应表 + 缺失功能识别
- **44px tap 目标**: 移动端所有可点击元素 min-height 44px + LongPress 600ms + 小按钮检测
- **safe-area-inset 适配**: iOS notch / Android navigation bar + env(safe-area-inset-*) + LongPress/bottom-sheet 适配

## 2. 双 stack 一致性 audit

### 2.1 入口与组件结构

| 维度 | 桌面 (`web/src/views/`) | 移动端 (`web/src/views/mobile/`) |
|------|--------------------------|----------------------------------|
| Chat 入口 | `chat/ChatViewSSE.vue` (1320 行) | `chat/MobileChatView.vue` (812 行) |
| Chat 子组件 | 1 个入口, 子组件在 `components/chat/` 共享 | 7 个独立组件 (Header/InputBar/MessageBubble/MessageList/RichCard/SessionDrawer/ChatView) 共 2595 行 |
| 视图数 | 大量桌面视图 | **31 个移动端视图** |
| 业务模块 | 15+ 模块 | 16 模块 (chat/dashboard/knowledge/drive/task/meeting/workspace/members/voiceprints/stats/settings/comments/login/admin/商业/command) |
| 视图测试 | 大量 | **5 个移动端 vitest** (测试覆盖率 8.6%) |

### 2.2 桌面 vs 移动端 Chat 事件对照

| 事件类型 | 桌面事件 | 移动端事件 |
|----------|----------|------------|
| 消息操作 | onFollowUpClick, regenerate, copyMessage, playTTSWrap | onFollowUp, onRegenerate, onCopyBubble, onPlayTTS |
| 工具跳转 | onToolJump | onToolJumpMobile (W100 +27 跳详情) |
| Pro Entry | onProEntryClick | onProEntryMobile (W100 +24 知识图谱/公式/假设入口) |
| 会话管理 | onEditTagsSession, onExportSession, onShareSession, onNewSession | + onDeleteSession, onRenameSession, onTogglePinSession, onToggleArchiveSession, onSwitchSession (W100 +28) |
| 搜索 | onSearchSelect | onOpenSearch, onSearchConfirm (MobileSearchSheet) |
| 语音/录音 | onRecordStart/Stop/Error, toggleVoiceMode, sendQuickMessage | onVoiceStart/End (MobileVoiceInputButton) |
| 文件上传 | handleFileSelect, handleImageSelect, triggerFileUpload, triggerImageUpload, openImage, onDragLeave/Over/Drop | handleFileSelect, handleImageSelect, clearFile, clearImage |
| 上下文面板 | 无 | W100 +29 上下文可见性面板 (3 tab: 对话/知识/工具) |
| 长按 | 无 | onLongPress (LongPressWrapper 600ms) |
| 主题切换 | 无 | onToggleTheme |
| 中断生成 | 无 | onStopGeneration |

**关键发现**: 移动端功能比桌面更丰富 (会话管理 + 上下文面板 + 长按 + 主题切换), 但桌面纯文本交互 (粘贴/拖拽/语音模式切换) 移动端未覆盖。

### 2.3 桌面 vs 移动端 Rich Block 渲染

| 维度 | 桌面 | 移动端 |
|------|------|--------|
| Rich Block 组件数 | 12 类 (meeting/task_list/knowledge_ref/member/formula/hypothesis/project/transcript/chart + 3 兜底) | MobileRichCard 仅 62 行单一组件 |
| 交互模式 | 完整渲染 | 路由跳转 + MobileActionSheet 简化 |
| 详情展开 | 桌面内嵌展开 | 移动端跳详情页 |

**结论**: 移动端通过"详情跳路由 + ActionSheet 简化"模式补偿 Rich Block 简化, 派工 v10 §6 实战模式沿用。

## 3. 44px tap 目标 audit

### 3.1 全局规则

```css
/* web/src/assets/variables.css */
--touch-target-min: 44px;

/* web/src/assets/mobile-base.css */
button, a, .btn, .el-button {
  touch-action: manipulation;
}
```

### 3.2 实际违规清单

**1 处违规** (实测):
- `web/src/views/mobile/chat/MobileInputBar.vue:281: min-height: 40px` (语音按钮)
- 较 44px 差 4px, 旧版沿用
- **本任务不擅自改**, 留 backlog (W102+ 派工预留)

**关键按钮 44px 守恒**:
- `MobileSessionDrawer.vue`: 显式 `min-height: 44px` (会话列表项)
- `MobileHeader.vue`: `width/height: var(--touch-target-min, 44px)` (导航按钮)
- `MobileActionSheet.vue`: 全局 44px (27 移动组件均沿用)

**LongPress 600ms 行为**:
- `LongPressWrapper.vue` 存在独立组件 (桌面/移动共用)
- MobileChatView 触发 `@longpress="onLongPress"`, 600ms 长按弹 MobileActionSheet
- 阻止 click 误触 (派工 v6 段 5 反馈 #16 拦截)

### 3.3 覆盖率

- 移动端全局 `--touch-target-min: 44px` + 27 个移动组件普遍采用
- 仅 1 处 40px 违规 (MobileInputBar voice button)
- **覆盖率 96%+** (1/27 移动组件有小偏差)

## 4. safe-area-inset 适配

### 4.1 全局组件

- `web/src/components/mobile/SafeArea.vue` 存在 (PR #2: 渲染对应方向的 env(safe-area-inset-*) padding)
- `web/src/components/mobile/TabBar.vue` 显式 `safe-area-inset-bottom`

### 4.2 显式使用清单 (4 处)

| 文件 | 行 | 用途 |
|------|------|------|
| `MobileFileCommentsView.vue` | 多处 | `padding-bottom: calc(8px + env(safe-area-inset-bottom, 0px))` |
| `MobileDriveFAB.vue` | 2 处 | `bottom: calc(80px + 60px + env(safe-area-inset-bottom, 0px) + 10px)` |
| `MobileDriveFAB.vue` | 2 处 | `bottom: calc(80px + 56px + 12px + env(safe-area-inset-bottom, 0px))` |
| `MobileFab.vue` | 1 处 | `bottom: calc(80px + env(safe-area-inset-bottom, 0px))` |

**结论**: 4 处显式使用, 集中底部安全区。顶部安全区 (MobileHeader) 沿用 NutUI 内置 SafeArea 组件。

### 4.3 移动端登录页键盘推起

- MobileLoginView 372 行, 包含 iOS Safari 键盘推起逻辑
- 沿用 W66 移动端路由级双栈守恒

## 5. 性能 + 渲染

### 5.1 移动端渲染性能

- W100 +40..+44 useMemo 性能基线 (5 commits) 已沉淀
- ChatViewSSE 主 useMemo 化在桌面, MobileChatView 812 行 vs 桌面 1320 行, 移动端渲染负担更轻
- 沿用 W100 +40..+44 useMemo 基线

### 5.2 LongPress 600ms 阻止 click 误触

- 移动端 chat 消息列表 + 会话列表均使用 LongPressWrapper 包裹
- 移动端 chat session drawer 长按触发: 重命名 / 置顶 / 归档 / 删除
- 状态: 派工 v6 段 5 反馈 #16 实战拦截留口

## 6. 路由双栈 + 兼容

### 6.1 路由级双栈架构守恒

- `web/src/utils/resolveMobile.js` 用 `import.meta.glob` 替代 `@vite-ignore` (PR #3 关键修复)
- 桌面 chunk 含桌面组件 (按需), mobile chunk 含所有 mobile 组件 (按需)
- 运行时按 isMobile 状态选择
- 静态分析 OK, 移动端文件均打包

### 6.2 useIsMobile 兼容层

- `web/src/composables/useIsMobile.js` 改为 thin-shell 委派到 useViewport.js (W83 B-2 P1-2 兼容层)
- 保留老 BREAKPOINTS 命名 (xs/sm/md/lg) 兼容老调用方
- 删除计划: W84 后续 batch 删 useIsMobile.js

## 7. 移动端测试覆盖

### 7.1 覆盖率

- 31 视图 + 27 组件 = 58 文件
- 5 个 vitest 测试 (CardList/MobileContextMenu/MobileFormSheet/MobileVoiceInputButton/SpeakerSearchSheet)
- **覆盖率 5/58 ≈ 8.6%**, 偏低

### 7.2 派工建议

- 优先核心交互: MobileChatView / MobileMessageBubble / MobileLongPress
- 派工预留 W102+ 派工 (本任务不擅自改)

## 8. 18 项反馈总结

| # | 反馈 | 类别 | 状态 |
|---|------|------|------|
| 1 | 桌面 ChatViewSSE 1320 行 vs MobileChatView 812 行 (38% 体积) | 双 stack | 移动端通过路由跳转补偿 |
| 2 | 桌面 vs 移动端 emit 事件名不一致 | 双 stack | 移动端经 MobileChatView 中转 |
| 3 | SearchPalette 数据流复用 | 双 stack | MobileSearchSheet 独立组件 |
| 4 | 移动端 admin 仅 Agent Traces | 双 stack | 简化覆盖 |
| 5 | MobileRichCard 62 行 vs 桌面 12 类 Rich Block | 双 stack | 路由跳转 + ActionSheet 简化 |
| 6 | 全局 tap target 规则 44px | 44px | ✅ |
| 7 | 44px 违规 1 处 (MobileInputBar voice 40px) | 44px | 留 backlog |
| 8 | LongPress 600ms 行为 | 44px | ✅ |
| 9 | tap-target 覆盖率 96%+ | 44px | ✅ |
| 10 | 全局 SafeArea 组件 | safe-area | ✅ |
| 11 | safe-area-inset 显式使用清单 4 处 | safe-area | ✅ |
| 12 | MobileLoginView 键盘推起适配 | safe-area | ✅ |
| 13 | 移动端渲染性能 (W100 +40..+44) | 性能 | 沿用 useMemo 基线 |
| 14 | LongPressWrapper 600ms 阻止 click 误触 | 性能 | ✅ |
| 15 | MobileChatView emit 30+ 函数 | 性能 | 移动端更全 |
| 16 | 路由级双栈 import.meta.glob | 路由 | ✅ |
| 17 | useIsMobile 兼容层 | 路由 | 沿用 W83 B-2 |
| 18 | 移动端测试覆盖率 8.6% | 路由 | 派工预留 W102+ |

## 9. 5 件套守恒

| 件 | 状态 | 说明 |
|----|------|------|
| 1. alembic 1 head | ✅ | 沿用 W100-RAG-6 `096_add_rag_multimodal_metrics` |
| 2. pytest 全套件 | ✅ | 沿用 W100-RAG-6 基线 242/242 PASS |
| 3. PWA build | ✅ | 沿用 W100-RAG-6 基线 |
| 4. 0 production code | ✅ | 仅 docs/memory 范畴 |
| 5. 锚点范式 | ✅ | W100 +46 (派工 brief 估 +1 守恒) |

## 10. 类 20.144+ 派生 (3 实例)

**类 20.144 (W100 +46 实战)**: 派工 brief 估"移动端视图 31 + 组件 27 = 58", 实测 chat 7 组件 + 业务 17 视图 + 移动组件 27 + admin/meeting/mobile-workspace/commercial 子模块, 测试覆盖率 8.6%, 派工 plan 偏差据实上报.

**类 20.145 (W100 +46 实战)**: LongPress 600ms + 44px tap target + safe-area 三件套已成基础设施, 1 处 40px 违规 (MobileInputBar voice button) 旧版沿用, **不擅自改** (符合段 6 切记: 仅 audit + report), 留 backlog.

**类 20.146 (W100 +46 实战)**: 双 stack 一致性 ≠ 事件名 1:1 映射, 移动端通过 `onToolJumpMobile` / `onProEntryMobile` 中转路由跳转, 桌面/移动端事件名不同, 派工 v10 §6 实战模式沿用.

## 11. 未来改进留口 (主拍决策, 不擅自扩)

1. MobileInputBar voice button 40px → 44px 修复 (W102+ 派工预留)
2. 移动端 31 视图 + 27 组件, 测试覆盖 5/58 ≈ 8.6% 偏低 (W102+ 派工预留)
3. 移动端 admin 仅 Agent Traces, 其他 admin 模块 (Knowledge Eval / Health / Members / Plans) 缺失 (W103+ 派工预留)
4. MobileRichCard 62 行 vs 桌面 12 类 Rich Block 组件, 移动端简化版 (W103+ 派工预留)
5. LongPressWrapper 单测缺失 (line 121 SpeakerSearchSheet.test.js 是搜索 sheet, 不是 longpress), 派工预留 W104+

## 12. 沉淀文件

- `memory/p3-mobile-spec-2026-08-03.md` (本任务 memory 11 段)
- `docs/p3-mobile-spec-2026-08-03.md` (本文件, 12 段完整 audit 报告)
- `commit: [W100 +46] docs(mobile): 双 stack 一致性 audit + 44px tap 验证`

## 13. 派工结论

- 派工 v10 P3-MOBILE-SPEC 单次派工即闭环, 18 项反馈完整覆盖段 2.1/2.2/2.3 三大范畴
- 主指挥后续另起 PR 处理 5 项改进留口 (40px 修复 / 测试覆盖率 / admin 模块 / RichCard 扩展 / LongPress 单测)
- 主拍决策: 沿用 W100 +46 收口, 不擅自扩
