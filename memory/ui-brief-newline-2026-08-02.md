# W100 +25 UI-BRIEF-NEWLINE 双段折叠 closure — 2026-08-02

## 派工简述

**派工 v10 — UI-BRIEF-NEWLINE 双段折叠（用户视角 P1-B 兜底方案）**

- 锚点范式: W100 +25 (1 commit 纯前端)
- 派工日期: 2026-08-02
- worktree: `E:/agent-ui-brief-newline` (branch: `chore/ui-brief-newline`)
- commit hash: `24975f514ba8f3a4b9ea7e6d351eb69718696c16`
- base: `a74eee3a6` (W100-CACHE-MISS W100 +0)

## 目标 / 边界

- **目标**: 在 chat 助手消息中显示双段折叠 (brief / detail), 通过 `msg.content` 中 `\n\n` 分段实现
- **边界**: 不依赖 `msg.brief / msg.detail` 字段 (deprecated); 仅前端 ChatViewSSE.vue + MobileMessageBubble.vue + 新增 ContentBriefDetail.vue 组件; 不动后端
- **派工类型**: B 实施 (前端 UX 增强)

## 4 阶段交付

### 阶段 1 — ContentBriefDetail.vue 新组件 + 单测 (PASS)

**新组件**: `web/src/components/chat/ContentBriefDetail.vue` (238 行)

- 接收 prop: `content` (string) + `compact` (boolean)
- 智能分割逻辑:
  - 1 段 = 完整显示 (无折叠按钮)
  - 2+ 段 = 第一段 brief + 后续 detail 折叠
  - 按 `\n\n+` 分割 (多 `\n` 折叠为单分隔符)
- a11y 完备:
  - aria-expanded 切换
  - aria-controls + 动态 aria-label
  - 键盘 Enter/Space 触发 (`.prevent` modifier)
  - focus-visible 2px outline
  - 移动端 tap ≥ 44px (compact 模式)
- dark mode 支持
- prefers-reduced-motion 禁用过渡

**单测**: `web/src/components/chat/__tests__/ContentBriefDetail.test.ts` (129 行)

- **6/6 PASS** (派工 brief 估 ≥6)
- 覆盖 case:
  - ① 1 段完整显示无折叠按钮
  - ② 2 段默认折叠 + aria-expanded=false
  - ③ 3+ 段点击展开多段 detail + 再次点击收起
  - ④ 键盘 Enter / Space 触发
  - ⑤ aria 完备 (aria-expanded + aria-controls + 动态 aria-label)
  - ⑥ 边界 (空 content / 仅空白段 / 多 `\n\n`)

### 阶段 2 — ChatViewSSE.vue 桌面端接入

**改动**: `web/src/views/chat/ChatViewSSE.vue` (line 662 替换 + import)

```vue
<!-- W100 +25: 双段折叠 (brief / detail 自动识别 \n\n) -->
<ContentBriefDetail
  v-if="msg.role === 'assistant' && msg.content"
  :content="msg.content"
  class="msg-content"
  :data-testid="`desktop-cbd-${msg.id}`"
/>
<div
  v-else-if="msg.content"
  class="msg-content"
  v-html="renderMarkdown(msg.content)"
/>
```

- 条件: `msg.role === 'assistant' && msg.content` (避免 user 消息误折叠)
- 用户消息继续走原 `v-html="renderMarkdown(msg.content)"` 路径
- 位置: 在 ThinkingCapsule + ToolTraceItem + PlanSteps 之后, RichContent 之前

### 阶段 3 — MobileMessageBubble.vue 移动端接入

**改动**: `web/src/views/mobile/chat/MobileMessageBubble.vue` (line 38-49 替换 + import)

```vue
<!-- 文本内容 — W100 +25 双段折叠 -->
<ContentBriefDetail
  v-if="msg.role === 'assistant' && msg.content"
  :content="msg.content"
  compact
  class="msg-content"
  :data-testid="`mobile-cbd-${msg.id}`"
/>
<div
  v-else-if="msg.content"
  class="msg-content"
  v-html="renderMarkdown(msg.content)"
/>
```

- `compact` 模式: tap ≥ 44px + font-size 14px + padding 12px

## 5 件套守恒实测

1. **alembic 096 守恒** ✅ — 纯前端任务, 不动 alembic/versions/
2. **pytest N/A** ✅ — 前端 vitest 范畴
3. **PWA build PASS** ✅ — `npm run build` 8.31s, ContentBriefDetail chunk 21.26 kB
4. **0 production code** ✅ — 无 `app/`、`alembic/versions/` 改动
5. **锚点范式 +1** ✅ — W100 +25 守恒 (W100 +25.1 已被 W100-PROMPT-NOHALLUC 占用, 主锚点 W100 +25 沿用)

## git diff 文件清单

```
 web/src/components/chat/ContentBriefDetail.vue     | 238 +++++++++++++++++++++
 web/src/components/chat/__tests__/ContentBriefDetail.test.ts      | 129 +++++++++++
 web/src/views/chat/ChatViewSSE.vue                 |  14 +-
 web/src/views/mobile/chat/MobileMessageBubble.vue  |  12 +-
 4 files changed, 390 insertions(+), 3 deletions(-)
```

## 18 项反馈

| # | 项 | 实测 |
|---|----|------|
| 1 | 任务目标完成度 | 100% (双段折叠 + 桌面/移动端接入) |
| 2 | git diff 文件清单 | 4 files, +390/-3 |
| 3 | vitest PASS 数 | 6/6 PASS (ContentBriefDetail.test.ts) |
| 4 | PWA build 实际结果 | PASS 8.31s, chunk 21.26 kB |
| 5 | 0 production code 守恒 | ✅ (无 app/ alembic/versions/ 改动) |
| 6 | 锚点范式实测 | W100 +25 (派工 brief 估 ≥1, 实测 +1 守恒) |
| 7 | ContentBriefDetail 6 case 详情 | ① 1段无折叠 / ② 2段默认折叠 / ③ 3+段展开+收起 / ④ 键盘 / ⑤ aria / ⑥ 边界 |
| 8 | 智能 1段 / 2+段逻辑 | ✅ (按 `\n\n+` 分割 + filter Boolean) |
| 9 | detail 段落分隔渲染 | ✅ (`v-for="para in paragraphs.slice(1)"` + 虚线分隔线) |
| 10 | 桌面移动端 compact | ✅ (`compact=true` 时 min-height 44px) |
| 11 | tooltip / aria-label | ✅ (`展开详情（N 段）` / `折叠详情` 动态切换) |
| 12 | 折叠按钮 a11y | ✅ (aria-expanded + aria-controls + keyboard + focus-visible) |
| 13 | CHANGELOG/CLAUDE.md 沉淀 | 沿用下次 D-1 派工 (本任务 1 commit 范畴, 不强求) |
| 14 | worktree + push origin | ✅ (branch `chore/ui-brief-newline` pushed) |
| 15 | 任何回归风险 | 0 (ThinkingCapsule.test.ts pre-existing 1 fail 与本任务无关, 已 git stash 验证) |
| 16 | 边界 | ✅ (空 content/空白段/多 `\n\n` 全部测) |
| 17 | 类 20 实战沉淀 | 类 20.133 — vue-test-utils keydown.enter 在 `<script setup>` 组件中**必须**绑定 `@keydown.enter.prevent`, 缺则不触发 |
| 18 | 5 件套守恒 | ✅ 5/5 |

## 19 类错误实战

- **E13 渲染覆盖原 v-html** ✅ 拦截 — user 消息继续走原 `v-html`, 仅 assistant 切换到 ContentBriefDetail
- **E19 1 段文本不应有折叠按钮** ✅ 拦截 — `v-if="hasDetail"` 保证 1 段时无按钮

## 类 20 实战沉淀 (W100 +25)

### 类 20.133 — vue-test-utils Transition leave 动画与状态断言

- **问题**: 折叠收起后, Vue Transition 200ms leave 动画期间 DOM 仍存在, 但 `expanded` ref 已为 false
- **现象**: 测试断言 `expect(wrapper.find('[data-testid="cbd-detail"]').exists()).toBe(false)` 失败, 实际 DOM 仍残留
- **解决**: 测试断言时区分两层:
  - 即时层: `expect((wrapper.vm as any).expanded).toBe(false)` (ref 状态)
  - 延迟层: `await new Promise(r => setTimeout(r, 300))` + `await nextTick()` 后再断言 DOM
- **教训**: 含 `<Transition>` 的组件单测, 收起态断言必须 await 过渡时长, 否则 flaky

### 类 20.134 — `<script setup>` 自动暴露函数与 keydown.enter 修饰符

- **问题**: 第一版 ContentBriefDetail.vue 只绑 `@click="toggle"`, 缺 `@keydown.enter.prevent="toggle"` + `@keydown.space.prevent="toggle"`
- **现象**: 测试 `await toggle.trigger('keydown', { key: 'Enter' })` 后 `expanded` 仍为 false
- **解决**: 显式补齐 keydown 修饰符 (`.enter` / `.space`)
- **教训**: `<script setup>` 函数**自动**暴露给 template, 但**事件修饰符**仍需手动写明. `<button>` + role/aria 默认无 Enter 行为, 必须显式 `@keydown.enter.prevent`

## 派工 v10 §5 反馈 #18 (据实上报)

| 派工 brief 估 | 实测 | 偏差据实 |
|--------------|------|----------|
| ≥6 vitest case | 6/6 PASS | 0 (守恒) |
| PWA build PASS | PASS 8.31s | 0 (守恒) |
| 0 production code | ✅ | 0 (守恒) |
| 锚点 ≥ 1 commit | 1 commit (24975f5) | 0 (守恒) |

## 后续派生 (留口)

1. 文档同步 (CLAUDE.md / CHANGELOG.md / ROADMAP.md) — 待 D-1 派工
2. RAG 综合 prompt 注入 brief/detail 行为约束 (派工 v10 §1 P1-B 兜底方案)
3. ContentBriefDetail `<Teleport>` 化 (复杂气泡嵌套场景)

## 沉淀文件

- `memory/ui-brief-newline-2026-08-02.md` (本文件)
- `docs/ui-brief-newline-2026-08-02.md` (runbook)
- `web/src/components/chat/ContentBriefDetail.vue` (新组件 238 行)
- `web/src/components/chat/__tests__/ContentBriefDetail.test.ts` (单测 129 行)

## 自动化部署

- 沿用 W99 DEPLOY-AUTO 沉淀
- 推送 origin 后 GitHub webhook → 服务器 webhook.py:9001 → scripts/deploy-auto.sh → 本地 PC auto-deploy.sh
- 本任务为前端 chunk 改动, 部署需 `npm run build` + `git add -f web/dist/` (vite-plugin-pwa disabled, 无 manifest hash 拦截)