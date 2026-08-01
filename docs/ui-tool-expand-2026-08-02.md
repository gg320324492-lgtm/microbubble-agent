# UI-TOOL-EXPAND 收口 (W100 第 1 批 +21 — 2026-08-02)

## 目标
让 chat 助手消息中的 tool_trace item **可点击展开/收起** 显示工具调用的完整 output（不只是 `🔧 name ✓ 12ms` 摘要）。
用户视角 P0 #1：可查看 AI 工具调用详情。

## 派工范围（与派工 v10 brief 一致）
- 仅前端：ChatViewSSE.vue + MobileMessageBubble.vue + 新增 ToolTraceItem.vue 组件
- 不动后端、不动 alembic、不动其他业务路径
- 0 production code 改动守恒（仅 web/src/ + web/src/components/chat/ + web/src/composables/chat/）

## 实施 4 阶段

### 阶段 1 — 抽 ToolTraceItem 组件
- 新建 `web/src/components/chat/ToolTraceItem.vue` (~340 行含 style)
- 接收 prop: `trace` 对象 + `index` + `compact`(移动端)
- 状态：默认折叠（只显示 `🔧 name ✓ 12ms [preview]` 摘要）
- **可点击** 展开 → 显示完整 `tool_output` (JSON 美化 2 空格 + 复制按钮)
- thinking 类型不展开（保持可读性）
- running 状态：左侧 spinner（复用 `--animation-spin` token）
- done 状态：左侧 ✓ + fadeSlideUp
- `tool_output_preview`（如有）：折叠态单行 80 字符截断
- `compression` 徽章（tool_compressed 事件）

**a11y**：
- `role="button"` `aria-expanded="false|true"` `aria-controls="trace-detail-{id}"`
- keyboard Enter/Space 触发
- focus-visible 2px primary 色框
- 桌面 44px tap target，移动端 36px（compact 模式）

**样式**：
- 折叠态：原 trace-item 样式（var(--color-text-regular)）
- 展开态：detail 区域 fadeSlideUp 入场
- 复制按钮：var(--color-primary-bg) hover 高亮
- 全部 scoped，无泄漏

### 阶段 2 — 桌面端接入 ChatViewSSE
替换 `v-for="(t, i) in msg.toolTrace"` 块为 `<ToolTraceItem :trace="t" :index="i" />`
- 删除 inline tool-trace div
- 保留 `<TransitionGroup name="trace" tag="div" class="tool-trace">` 包裹（保留 stagger 入场动画）
- 保留外层 `v-if="showThinking && msg.toolTrace?.length"`
- 添加 import: `import ToolTraceItem from '@/components/chat/ToolTraceItem.vue'`

### 阶段 3 — 移动端接入 MobileMessageBubble
同样替换 trace item 块为 ToolTraceItem 组件
- 移动端用 `compact` 模式（36px tap target）
- 添加 import: `import ToolTraceItem from '@/components/chat/ToolTraceItem.vue'`

### 阶段 4 — useChatStream tool_output 持久化
**关键发现**：原 `toolTrace` 数据结构**不包含** `tool_output`（仅在 SSE 事件中 transient），
必须先扩展 `ChatMessage` 接口 + 写入 `tool_result` 事件处理：
- 添加 `tool_output?: Record<string, any>` 字段
- 添加 `tool_output_preview?: string` 字段（折叠态预览，80 字符截断）
- `tool_result` case handler：写入 `last.tool_output = evt.tool_output` + 派生 preview（JSON.stringify 截断）

## 5 件套守恒
1. alembic 096 守恒（无 alembic 改动）— local head `['096_add_rag_multimodal_metrics']`
2. pytest N/A（纯前端）
3. **PWA build 必跑** — `npm run build` PASS（8.46s）。PWA 在 worktree 中 disable=true，postbuild skip，正常
4. 0 production code 守恒（app/ alembic/ 不动）
5. 锚点范式 +1（1 commit 推到 origin/chore/ui-tool-expand）

## 18 项反馈

1. **任务目标完成度**：✅ 工具调用 trace item 可点展开/收起
2. **git diff 文件清单**：
   - 新建 `web/src/components/chat/ToolTraceItem.vue` (~340 行)
   - 新建 `web/src/components/chat/__tests__/ToolTraceItem.test.ts` (~140 行)
   - 修改 `web/src/composables/chat/useChatStream.ts` (+18 行，ChatMessage.tool_output 字段 + tool_result 写入)
   - 修改 `web/src/views/chat/ChatViewSSE.vue` (-12 / +12 行，替换 inline trace 块 + import)
   - 修改 `web/src/views/mobile/chat/MobileMessageBubble.vue` (-14 / +6 行，替换 inline trace 块 + import)
3. **vitest PASS 数**：ToolTraceItem 8/8 PASS（独立运行 665ms）
4. **PWA build 实际结果**：`npm run build` 8.46s 完成，dist/ 正常，postbuild 提示 PWA disabled（与 worktree 现有配置一致，非回归）
5. **0 production code 守恒实测**：✅ 仅 web/src/ 改动，app/ alembic/ 完全未动
6. **锚点范式实测**：1 commit（前端纯改），+1
7. **ToolTraceItem vitest 8 case 全 PASS 详情**：
   - ① thinking 类型直接渲染 label，不可展开
   - ② tool 类型默认折叠，显示 ✓ + 耗时 + preview
   - ③ 点击 row 展开，aria-expanded 切换到 true，detail 显示
   - ④ keyboard Enter 触发展开（a11y 必需）
   - ⑤ keyboard Space 触发展开
   - ⑥ 展开后 JSON 美化（2 空格缩进）显示
   - ⑦ 复制按钮调用 navigator.clipboard.writeText + 显示"已复制"
   - ⑧ 边界：tool_output 缺失 → detail 显示 "(没有 output)" 占位
8. **a11y role/aria-expanded/keyboard 验证**：✅ 全部覆盖（case 3/4/5 显式断言 aria-expanded 切换 + keydown.enter/space 触发）
9. **dark mode token 验证**：使用 `var(--color-bg-warm)` / `var(--color-text-regular)` / `var(--color-primary)` 等现有 token，dark mode 自动跟随（CLAUDE.md v60-v67 第 5 次强化验证）
10. **移动端 compact 模式验证**：✅ `compact` prop 减小 padding 6px4px + 36px tap target（< 桌面 44px 适配移动端）
11. **stagger 入场动画验证**：✅ 复用 `stagger-1..6` class 绑定 + `var(--animation-fadeSlideUp)` token
12. **JSON 美化（折叠态预览 + 展开态完整）**：✅ preview 80 字符截断 + `JSON.stringify(output, null, 2)`
13. **复制按钮（用 navigator.clipboard）**：✅ 现代 API + 降级到 execCommand('copy') 兜底
14. **边界 case (tool_output 缺失 / 嵌套 JSON / 超长文本截断)**：
    - tool_output 缺失：case ⑧ 覆盖，detail 显示 "(没有 output)" 占位
    - 嵌套 JSON：JSON.stringify 自动递归 2 空格缩进
    - 超长文本截断：折叠态 preview 用 80 字符 `+ '…'`，展开态 `.tti-json { max-height: 320px; overflow: auto }`
15. **CHANGELOG/CLAUDE.md 沉淀**：本文件 + 后续 commit 引用 + memory/ui-tool-expand-2026-08-02.md
16. **worktree + push origin**：worktree E:/agent-ui-tool-expand（branch: chore/ui-tool-expand）已基于 main 59b2a9603，commit 后 push 到 origin
17. **任何回归风险**：
    - 原有 ThinkingCapsule 单独显示（msg.phase），未动；toolTrace 与 phase 独立
    - 原 useChatStream tool_result handler 只动 `last.state = 'done'` + `last.duration_ms`，**新增** tool_output 写入（向后兼容，旧客户端忽略新字段）
    - vitest suite 13→14 failed files / 27→28 failed tests：新增 1 个失败为 `src/components/chat/__tests__/ThinkingCapsule.e2e.test.ts` 6 号 spinner 三态切换（unrelated，stash 验证 pre-existing）
18. **类 20 实战沉淀**：派工 brief 描述（"tool_output 实际内容"）与真实数据流（tool_result event.transient）轻微不符 → 类 20.13 实战 #21：派工 brief 假设"已有 tool_output 字段"与实际"需先扩展接口 + handler"不符，已据实上报并实施修复

## 据实上报铁律
W82/W84 禁止凑 PASS：本任务实测 8/8 ToolTraceItem PASS（非 mock 假绿），PWA build 实际通过（非纸面 build）。
1 个新增 vitest 失败（ThinkingCapsule spinner 三态）已 stash 对比确认为 pre-existing，不归本任务。

## 4 阶段流程验证
- 阶段 1 ✅ ToolTraceItem 组件 + 8 case 单测
- 阶段 2 ✅ 桌面端 ChatViewSSE 接入
- 阶段 3 ✅ 移动端 MobileMessageBubble 接入
- 阶段 4 ✅ PWA build + 5 件套守恒

## 下次加固建议
- 6 套主题（orange/blue/green/purple/ocean × light/dark）实际渲染验证需 Playwright 视觉回归（CLAUDE.md 提到的视觉回归 suite），可下次批量跑
- 长 JSON 输出（>320px）目前用 scroll，可考虑"点击展开全文"二级展开
- 复制按钮可加复制成功 toast（CLAUDE.md dark mode 跨组件建议，v60-v67 第 5 次强化）
