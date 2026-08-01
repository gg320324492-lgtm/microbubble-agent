# FIX-IMAGES-FRONTEND W99 +20 runbook — 2026-08-02

## 任务

前端 img 加载失败时显示占位符（"图片加载失败"），避免 404 静默。

## 范围

- **纯前端**：仅 `web/src/` 改动
- **不动后端**：app/、alembic/、scripts/

## 改动文件

| 类型 | 文件 | 作用 |
|------|------|------|
| 新建 | `web/src/components/chat/ImageWithFallback.vue` | 通用图片兜底组件，@error 监听 |
| 新建 | `web/src/components/chat/__tests__/ImageWithFallback.test.ts` | 6 个单测 |
| 新建 | `web/src/utils/__tests__/markdown.test.ts` | 5 个 onerror 注入单测 |
| 修改 | `web/src/utils/markdown.ts` | `injectImgOnerror` 后处理函数 |
| 修改 | `web/src/views/chat/ChatViewSSE.vue` | `msg.imageUrl` 改用 ImageWithFallback |

## 关键设计决策

### 决策 1：双轨覆盖（marked 后处理 + 单文件组件）

派工 v10 §2.2 推荐的 `@error.capture` 在 `<div>` 上方案**实证不可行**：

- v-html 注入的 `<img>` 加载失败时，浏览器**不**派发可冒泡的 DOM error 事件
- 资源加载错误由 img 自身处理，error 事件不冒泡到祖先 div
- Vue 的 `@error` / `@error.capture` 在父元素上**完全收不到**

修正后双轨方案：

1. **marked 后处理（`markdown.ts`）** — 解析完后正则替换 `<img>` → 注入内联 onerror + data-fallback-text
2. **ImageWithFallback.vue** — 用于 Vue 模板里直接写的 `<img>` 场景（如 `msg.imageUrl`）

### 决策 2：占位符走内联 SVG data URL

不依赖外链资源（防止 404 链），1x1 base64 SVG + 文本"🖼️ 图片加载失败"，dark mode 兼容（用 design token）。

### 决策 3：ChatViewSSE `msg.imageUrl` 改用组件

`@click="openImage(msg.imageUrl)"` 自动透传到 ImageWithFallback 根 `<span>`，行为不变。

### 决策 4：MobileMessageBubble 不改

`grep` 后未发现直接 `<img>` 引用（只走 `v-html="renderMarkdown"`），自动继承 markdown onerror 注入。

## 部署步骤

```bash
# 1. 拉取最新
cd E:/agent-fix-images-frontend
git pull origin chore/fix-images-frontend

# 2. 跑测试
cd web
npm install --prefer-offline
npx vitest run src/components/chat/__tests__/ImageWithFallback.test.ts src/utils/__tests__/markdown.test.ts
# 预期 11/11 PASS

# 3. Build
npm run build
# 预期 8-10s 完成，PWA disable 模式无 unhashed manifest

# 4. 浏览器验证
# - 打开任一 ChatViewSSE 含 markdown ![](http://broken.url/x.png) 的对话
# - 期望：图片位置显示"🖼️ 图片加载失败"占位符（不闪白、不显示碎图图标）
# - DevTools console 无 error 噪音
```

## 5 件套守恒

1. alembic 1 head 094 守恒 ✅（不动 alembic）
2. pytest N/A ✅（纯前端）
3. PWA build 必跑 ✅（npm run build 成功）
4. 0 production code 守恒 ✅（仅 web/src/ + web/dist/）
5. 锚点范式 +1 ✅（49b6b7640 → a7ef24af7）

## 回归风险

- **风险 1**：`ImageWithFallback` 包了 `<span>` 改变 DOM 结构。验证：@click 自动冒泡到根，行为一致
- **风险 2**：marked 后处理可能影响其他 markdown 渲染场景。验证：单测 ④（已存在 onerror 防重）+ 浏览器全场景实测
- **风险 3**：base64 SVG 占位符在 dark mode 不可见。验证：占位符用 `var(--color-bg-warm)` + `var(--color-text-secondary)` 走 design token

## 派工前提修正记录

派工 v10 段 1 §"2.2 阶段 2 — RichContent 改造（关键）" 的 `@error.capture` 方案**实战不可行**，已修正走双轨方案。详见 `memory/fix-images-frontend-2026-08-02.md` 类 20.130 实战。

## 相关链接

- Commit: `a7ef24af7`
- Branch: `chore/fix-images-frontend`
- Push: ✅ origin/chore/fix-images-frontend
- Memory: `memory/fix-images-frontend-2026-08-02.md`
- Worktree: `E:/agent-fix-images-frontend`
