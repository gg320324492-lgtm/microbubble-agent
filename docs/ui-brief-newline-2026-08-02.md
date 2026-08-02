# W100 +25 UI-BRIEF-NEWLINE 双段折叠 runbook — 2026-08-02

## 一句话摘要

Chat 助手消息按 `msg.content` 中 `\n\n` 自动分段, 1 段不折叠, 2+ 段首段 brief + 后续 detail 折叠。桌面端 (ChatViewSSE.vue) + 移动端 (MobileMessageBubble.vue) 接入新组件 `ContentBriefDetail.vue`。

## 设计动机

派工 v10 用户视角 P1-B 兜底方案:

- **背景**: AI 助手回复有时过长, 用户需先看简报再决定是否展开详情
- **现状**: 后端已 deprecated `msg.brief / msg.detail` 字段, 但用户对"折叠" UX 的呼声持续存在
- **方案**: 不依赖后端字段, 前端按 `\n\n` 自动分段识别 (brief / detail), 0 后端改动
- **优先级**: P1-B 兜底 (用户视角), 与后端 brief/detail 字段分离

## 架构

```
msg.content (string)
   │
   ├─ split('\n\n+') → paragraphs[]
   │     │
   │     ├─ paragraphs.length === 0  → 整个组件 v-if="brief" 拦截, 不渲染
   │     ├─ paragraphs.length === 1  → 完整显示 (brief-only, 无折叠按钮)
   │     └─ paragraphs.length >= 2   → 第 1 段 brief 显示 + 折叠按钮 + 后续 detail
   │
   ▼
ContentBriefDetail.vue (智能折叠)
   │
   ├─ 桌面端 ChatViewSSE.vue → 替换原 v-html="renderMarkdown(msg.content)"
   └─ 移动端 MobileMessageBubble.vue → 同上, compact 模式
```

## 实现细节

### ContentBriefDetail.vue 关键 props

```ts
withDefaults(defineProps<{
  content: string  // 原始 markdown 内容
  compact?: boolean  // 移动端模式 (tap ≥ 44px)
}>(), { compact: false })
```

### 分割正则

```ts
const paragraphs = computed(() => {
  if (!props.content) return []
  return props.content
    .split(/\n\n+/)        // \n\n+ 折叠多 \n
    .map(p => p.trim())    // 去空白
    .filter(Boolean)       // 删空段
})
```

### a11y 完备

- `aria-expanded` 动态切换 true/false
- `aria-controls` 指向 detail 元素 id (随机生成避免冲突)
- `aria-label` 动态: `展开详情（N 段）` / `折叠详情`
- 键盘 `@keydown.enter.prevent="toggle"` + `@keydown.space.prevent="toggle"`
- `:focus-visible` 2px outline (主色)
- 移动端 `min-height: 44px` (WCAG 触控目标)

### 视觉规范

- brief 段: `display: block`, 无特殊样式 (与外层 `.msg-content` 兼容)
- 折叠按钮:
  - 桌面端: 28px min-height + 6px 圆角 + 主色文本
  - 移动端 compact: 44px min-height + 12px 圆角 + 14px 字号
- detail 段落分隔: `border-top: 1px dashed` (灰色, dark mode 反色)
- 折叠动画: 200ms fadeSlideUp (prefers-reduced-motion 自动禁用)

## 集成位置

### ChatViewSSE.vue (line 662)

```vue
<!-- 替换前 -->
<div v-if="msg.content" class="msg-content" v-html="renderMarkdown(msg.content)" />

<!-- 替换后 (W100 +25) -->
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

**位置**: 在 ThinkingCapsule + ToolTraceItem + PlanSteps 之后, RichContent 之前

### MobileMessageBubble.vue (line 38-49)

```vue
<!-- 替换前 -->
<div v-if="msg.content" class="msg-content" v-html="renderMarkdown(msg.content)" />

<!-- 替换后 (W100 +25) -->
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

## 部署清单

1. **Git 推送** (✅ 已完成):
   ```bash
   git push origin chore/ui-brief-newline
   # → https://github.com/gg320324492-lgtm/microbubble-agent/pull/new/chore/ui-brief-newline
   ```

2. **Webhook 自动触发** (沿用 W99 DEPLOY-AUTO):
   ```
   git push → GitHub webhook
     → 服务器 scripts/webhook.py:9001 → scripts/deploy-auto.sh
     → 本地 PC scripts/auto-deploy.sh
     → npm run build → alembic heads → git add -f -A → push → docker cp → restart → curl /health
   ```

3. **dist 完整性**:
   - vite-plugin-pwa disabled (本项目 baseline), 无 manifest hash 拦截
   - ContentBriefDetail chunk 自动 code-split: `ContentBriefDetail-{hash}.js` (~21.26 kB)
   - 仅当 lazy import 触发 (chat 消息渲染时) 才下载

## 验证清单

### 单测 (vitest)

```bash
cd web
SKIP_DB_SETUP=1 npx vitest run src/components/chat/__tests__/ContentBriefDetail.test.ts
# 期望: 6/6 PASS
```

### PWA build

```bash
cd web
npm run build
# 期望: ✓ built in ~8s + postbuild OK
```

### 集成 e2e (手动, 沿用 W98 P2-E2E 铁证)

1. 启动 dev server: `cd web && npm run dev`
2. 浏览器访问 `http://localhost:3000/chat`
3. 发送消息测试:
   - 1 段回复 (无 `\n\n`): 应完整显示, 无折叠按钮
   - 2+ 段回复 (含 `\n\n`): 第一段显示 + 折叠按钮 + 展开后多段
4. 测试键盘: Tab 聚焦按钮 → Enter/Space 切换
5. 测试 a11y: 浏览器 DevTools Accessibility 面板查看 aria-* 属性

### 移动端验证

1. Chrome DevTools 切换到 iPhone viewport (375x812)
2. 同样发送 1 段 / 2+ 段消息
3. 验证 tap 区域 ≥ 44px + 字号 14px

## 回归风险

| 风险 | 状态 | 说明 |
|------|------|------|
| ThinkingCapsule 1 pre-existing fail | 已知 | git stash 验证与本任务无关, 沿用基线 |
| 0 production code | ✅ | 无 app/ alembic/versions/ 改动 |
| 后端 API 不动 | ✅ | 仅前端组件 |
| 现有 markdown 渲染兼容 | ✅ | 内部仍走 renderMarkdown, 无替换 |
| ChatMessageActions / ProEntries 不受影响 | ✅ | 它们在 msg-meta 行, 与 msg-content 平级 |

## 未来扩展

1. **RAG prompt 注入**: 让 LLM 输出时主动用 `\n\n` 分段, 形成 brief + detail 双段结构
2. **后端 brief/detail 字段恢复**: 如有需要, 可在后端生成时主动插入 `\n\n` 分隔符 (语义不变)
3. **`<Teleport>` 化**: 复杂嵌套场景 (如 Rich Block 内联) 时, 把 detail 提升到顶层避免 CSS 干扰
4. **动画偏好**: 沿用 prefers-reduced-motion 自动禁用

## 类 20 实战沉淀 (W100 +25)

### 类 20.133 — Transition leave 动画 vs 单测断言

- 测试断言需分层: 即时层 `expanded` ref 状态 / 延迟层 DOM 存在 (300ms 后)
- 含 `<Transition>` 组件单测必 await 过渡时长, 否则 flaky

### 类 20.134 — `<script setup>` 函数暴露 ≠ 事件修饰符自动绑定

- `<script setup>` 函数自动暴露给 template
- 但事件修饰符 (`.enter` / `.space` / `.prevent`) 仍需手动写明
- `<button>` 默认无 Enter 行为, 必须显式 `@keydown.enter.prevent`

## 沉淀文件

- `memory/ui-brief-newline-2026-08-02.md` (closure)
- `docs/ui-brief-newline-2026-08-02.md` (本文件 runbook)
- `web/src/components/chat/ContentBriefDetail.vue` (新组件)
- `web/src/components/chat/__tests__/ContentBriefDetail.test.ts` (单测)