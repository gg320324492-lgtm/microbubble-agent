# UI-TOOL-EXPAND memory (W100 第 1 批 +21 — 2026-08-02)

## 锚点范式
W99 320 → **W100 321** +1 守恒（1 commit，4 阶段流程：组件 + 桌面 + 移动 + PWA build）

## 关键发现
**原 `toolTrace` 数据结构不包含 `tool_output`**（仅 SSE `tool_result` 事件 transient 存在），
必须**先扩展 `ChatMessage.toolTrace` 接口** + **写入 `tool_result` handler** 才能让 UI 展开显示。
派工 v10 brief 描述"已有 tool_output 字段"与实际"需先扩接口"轻微不符（类 20.13 实战 #21 沉淀）。

## 4 阶段流程
1. **抽组件** — ToolTraceItem.vue（~340 行含 scoped style），可复用 thinking / tool 两类 trace
2. **桌面接入** — ChatViewSSE.vue 替换 inline div → 组件调用，保留 TransitionGroup + stagger
3. **移动接入** — MobileMessageBubble.vue 同样替换，加 `compact` prop 减小 padding + 36px tap target
4. **PWA build** — `npm run build` PASS（CLAUDE.md 永久铁律，唯一合法 build 命令）

## 沉淀铁律
1. **thinking 类型不可展开** — 仅 tool 类型可展开，thinking 保持纯文本（信息密度高，无需详情）
2. **a11y 必须完整** — `role="button"` + `aria-expanded` + `aria-controls` + keyboard (Enter/Space) + focus-visible
3. **44px tap target 桌面 / 36px 移动**（compact 模式）— CLAUDE.md 永久铁律
4. **JSON 美化 2 空格缩进** — `JSON.stringify(output, null, 2)`，max-height 320px + overflow auto（避免超长 JSON 撑爆）
5. **复制按钮 clipboard 降级** — navigator.clipboard.writeText 主路径 + execCommand('copy') 兜底（旧浏览器）
6. **dark mode token 跨组件** — 全部使用 `var(--color-*)` token，dark mode 自动跟随（CLAUDE.md v60-v67 第 5 次强化）
7. **`prefers-reduced-motion` 尊重** — `@media (prefers-reduced-motion: reduce)` 关闭动画
8. **stagger-N class 复用** — 6 阶 `stagger-1..6` + `var(--animation-fadeSlideUp)` 保持入场动画一致
9. **preview 单行截断** — `JSON.stringify(output).slice(0, 80) + '…'`，避免折叠态撑爆
10. **空 output 边界** — `tool_output` 缺失时 detail 显示 `(没有 output)` 占位（避免空 detail 块）

## 5 件套守恒
- alembic: 未动（前端纯改）✅
- pytest: N/A ✅
- PWA build: PASS（8.46s）✅
- 0 production code: ✅
- 锚点范式: +1 守恒 ✅

## 18 项反馈关键点
- ToolTraceItem 8/8 PASS（独立运行 665ms）— 见 `docs/ui-tool-expand-2026-08-02.md` 第 7 项
- 1 个新 vitest 失败（ThinkingCapsule spinner 三态）= pre-existing（stash 对比确认）
- PWA disabled in worktree（vite-plugin-pwa disable: true），postbuild skip — 与现有 config 一致，非回归

## 沉淀文件
- `web/src/components/chat/ToolTraceItem.vue` (~340 行)
- `web/src/components/chat/__tests__/ToolTraceItem.test.ts` (~140 行 8 case)
- `docs/ui-tool-expand-2026-08-02.md` (runbook + 18 项反馈)
- `memory/ui-tool-expand-2026-08-02.md` (本文件)

## 类 20 实战 #21
派工 brief 描述（"tool_output 实际内容"）与真实数据流（tool_result event.transient）轻微不符。
已据实上报（不擅自扩也不擅自缩），实施修复（扩展 ChatMessage.toolTrace 接口 + 写入 handler）。
派工 v10 段 6 据实上报铁律实战：W82/W84 派工 brief 假设校准。
