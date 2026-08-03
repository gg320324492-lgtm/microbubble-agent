# W100 +51 按钮现代化 — memory (2026-08-03)

**派工**: 主拍连续派工 (W100 +51a / +51b 2 commits, 5 件套守恒, 0 production code)

**用户截图反馈**: "底部的几个按钮做的现代化一些，这几个图标看上去都不能直观看出来是干什么的"
**识别**: 4 处 emoji 按钮 + 1 处顶部眼睛图标不直观

## 实施范围 (5 files)

| 文件 | 修改 |
|---|---|
| `web/src/components/chat/ChatMessageActions.vue` | 🔄→Refresh/Loading, 📋→CopyDocument/Check; .action-icon CSS font-size emoji → el-icon svg (1em/1em) |
| `web/src/components/chat/ProEntries.vue` | 🕸️→Share, 📐→DataAnalysis, 💡→Aim; .entry-icon 同上 CSS |
| `web/src/components/chat/ChatMessageRow.vue` | 🔊 TTS→Headset; 新增 .msg-actions 容器 (gap: 8px); `import { ChatDotRound, Headset } from '@element-plus/icons-vue'` (原只 ChatDotRound) |
| `web/src/views/mobile/chat/MobileMessageBubble.vue` | 🔊 TTS→Headset; `import { Headset }`; mobile tap 区域 44px 守恒 |
| `web/src/views/chat/ChatViewSSE.vue` | 顶部 View→Notebook + 文字 '上下文' 标签; aria-label 'AI 记住了什么'→'AI 上下文' |

## 2 commits (据实)

- **W100 +51a** `773ad7f3e` — 4 组件 emoji → Element Plus Icon (4 files +77/-26)
- **W100 +51b** `a09ee5a65` — 顶部上下文按钮 Notebook + 文字标签 + 10 新测 (2 files +168/-4)

未 commit: web/dist/ rebuild (126 delete + 1 modify dist/index.html, .gitignore track, **主拍决定是否独立 commit + push**)

## 测试沉淀 (10 新测 PASS)

`web/src/components/chat/__tests__/W100Plus51ButtonModernization.test.ts` — 10 case:
- ChatMessageActions 5 测: Refresh+CopyDocument 桌面态 / hover-only 守恒 / aria-label 守恒 / 移动端 text+icon / 复制中切 Check
- ProEntries 5 测: Share+DataAnalysis+Aim 3 icon / hover-only 守恒 / entry-click emit / forceAll / LaTeX 智能显示

模式: `defineComponent` stub el-icon + 8 个 icon component (Refresh/CopyDocument/Check/Loading/Share/DataAnalysis/Aim 携带 data-icon 标记).

## 类 20 实战 (3 据实上报, 派工前提铁律沉淀)

- **类 20.13** (Element Plus icon 名实测): brief 提到 RefreshRight/CopyDocument/DocumentCopy/VideoPlay/DataLine/DataAnalysis — **实测全部存在**, 但选 Refresh + CopyDocument + Headset 路径 (与 ChatMessageActions/Row 已有 ChatDotRound 风格延续). `d.ts` 验证 `ls node_modules/@element-plus/icons-vue/dist/types/components/` — kebab-case 文件名, PascalCase import
- **类 20.108** (grep 路径必验证): brief 给的 4 文件路径全部命中 (Read 实测确认 line 号, 避免假命中)
- **类 20.124** (不动 assistantPhase.ts): 状态机未动, 23/23 PASS 守恒

## 5 件套守恒实测

1. **alembic**: 不动 → 1 head `096_add_rag_multimodal_metrics` 守恒 (W100 +51 纯前端)
2. **vitest**: 38/38 PASS (28 老 + 10 新)
   - 3 pre-existing FAIL 在 `ThinkingCapsule.test.ts` / `ThinkingCapsule.e2e.test.ts` — `git stash` 验证与本次无关 (W99 +14/+16 baseline 已存在)
3. **npm run build**: PASS, built in 8.70s, postbuild PWA disabled 跳过
4. **git diff origin/main -- app/ alembic/**: 0 (纯前端 0 后端守恒)
5. **锚点**: W100 +51a + W100 +51b 据实 (主拍连续 2 派工)

## 桌面 hover-only / 移动 tap 区域 守恒

- ChatMessageActions.mode-desktop: opacity:0 → .bot-bubble:hover 显示 (CSS 完全不动, 仅 emoji 改 icon)
- ChatMessageActions.mode-mobile: min-width:44px + height:44px (沿用 W100 +23)
- ProEntries.mode-desktop: opacity:0 → hover/focus 显示 (CSS 完全不动)
- ProEntries.mode-mobile: min-width:44px + height:44px (沿用 W100 +24)
- MobileMessageBubble.tts-btn: padding:2px 6px + .el-icon font-size:18px (新增 el-icon svg 居中布局)

## 已知 deviation (派工 brief → 实测)

- `msg.isTtsPlaying` 字段 **不存在** in ChatMessage type → 简化为静态 '播放语音' aria-label
- Element Plus icon 内 SVG `<svg viewBox>` 在 jsdom 不渲染 → 测试用 defineComponent stub + data-icon 标记代替 (`paragraphActions.test.js` 沿用模式)

## CLAUDE.md 永久锚点更新 (主拍决策)

锚点范式 W100 +28 → +29 → +30 (~537) → +51a/+51b (~539) 据实累计.
类 20.13 / 20.108 / 20.124 实战新增, 累计 137 实例 (派工 v6 §13.3 据实上报口径).

dist rebuild commit 留给主拍决定 (本任务只交付 src + tests 2 commits).
