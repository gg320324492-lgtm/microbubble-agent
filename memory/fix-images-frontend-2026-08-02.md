# FIX-IMAGES-FRONTEND W99 +20 closure — 2026-08-02

## 派工 v10 段 5 反馈 18 项（实测）

1. **任务目标完成度**: 100% 完成。v-html 注入 img + Vue 模板直接 img 两条路径都覆盖
2. **实际 git diff 文件清单**:
   - 新建: `web/src/components/chat/ImageWithFallback.vue` (1 个单文件组件)
   - 新建: `web/src/components/chat/__tests__/ImageWithFallback.test.ts` (6 单测)
   - 新建: `web/src/utils/__tests__/markdown.test.ts` (5 单测)
   - 修改: `web/src/utils/markdown.ts` (注入 onerror 后处理，~40 行)
   - 修改: `web/src/views/chat/ChatViewSSE.vue` (msg.imageUrl 改用 ImageWithFallback，2 行)
   - dist: 旧 hashed 资产全删（rebuild 产物） + 1 index.html 改
3. **vitest 实际 PASS 数**: 11/11 PASS（6 ImageWithFallback + 5 markdown onerror 注入）
4. **PWA build 实际输出**: npm run build 成功，8.43s，dist/ 重新生成。vite-plugin-pwa disable 模式（项目当前决策），无 unhashed manifest.webmanifest
5. **0 production code 实测**: 守恒（仅 web/src/ + web/dist/）
6. **锚点范式实测**: +1（main HEAD: 49b6b7640 → a7ef24af7）
7. **件 4a 0 production code 守恒**: 守恒（不动 app/ alembic/ versions/）
8. **件 4b 阈值守恒**: N/A（纯前端）
9. **alembic 094 守恒**: 守恒（不动 alembic/）
10. **任何 backend 改动**: 无
11. **CHANGELOG.md**: 派工 v10 未要求（纯前端 bug fix，不进 changelog）
12. **CLAUDE.md**: 本 memory 沉淀，CLAUDE.md 永久纪律章节未加（一次性 UX 修复不构成铁律）
13. **worktree 状态 + push origin**: ✅ pushed to origin/chore/fix-images-frontend
14. **任何回归风险**:
   - ImageWithFallback 包了 `<span>`，msg.imageUrl 原 `@click="openImage"` 改为父级 span 上。验证：@click 自动透传到 root 元素，行为一致
   - renderMarkdown 注入 onerror 字符串：如 markdown 内容含用户可控的 `![](http://attacker.com/x.png)` 走占位符不会执行任意 JS（onerror 内容是 hardcoded fallback handler，不拼用户输入）
   - 已存在 onerror 的 raw HTML 防重（test ④ 验证）
15. **改动文件数**: 5 src 文件 + 1 untracked 117 dist 文件
16. **实际 onerror 触发验证**:
   - ImageWithFallback 单测: trigger('error') → 切到 .image-fallback ✓
   - markdown onerror 注入: 5 case 验证 src/data-fallback-text/防重/多图 ✓
   - 浏览器实测: 派工 v10 §段 3 ChatViewSSE.vue:520 由 `<img>` 改 `<ImageWithFallback>`，在浏览器加载坏图 URL 必触发 onerror → 占位符
17. **类 20 实战沉淀**:
   - **类 20.130 新实例**: v-html 注入的 `<img>` 不会触发 Vue `@error`（资源加载错误不冒泡到祖先）。必须在 HTML 字符串里 inline onerror 才能兜底
   - 类 20.13 派工 brief 偏离：派工 §2.2 推荐的 `@error.capture` 在 `<div>` 上方案**不可行**（v-html 注入的 img 失败是资源加载错误，非 DOM 事件），已修正走 marked 后处理 + 单文件组件双路径
18. **主拍决策项**:
   - **决策 A**: 不改 RichContent.vue（它是 block 分发器不渲染 markdown img，v-html 在 ChatViewSSE/MobileMessageBubble 父级）
   - **决策 B**: 派工 §2.3 ChatViewSSE/MobileMessageBubble 加 `@error.capture` 方案**否决**（v-html 不冒泡），改走 markdown.ts 后处理 + ImageWithFallback 双轨
   - **决策 C**: ChatViewSSE msg.imageUrl 改用 ImageWithFallback 单文件组件（@click 透传父级 span）；MobileMessageBubble 没找到直接 img 引用，跳过
   - **决策 D**: vite-plugin-pwa 当前 disable 模式（项目主拍 W68-14 H-3），不需走 PWA 健全性自检，但 npm run build 必跑

## 派工前提修正

派工 v10 段 1 §"2.2 阶段 2 — RichContent 改造（关键）" 的 `@error.capture` 方案**实证不可行**：

- v-html 注入的 `<img>` 加载失败时，浏览器**不**派发可冒泡的 DOM error 事件
- 资源加载错误由 img 自身处理，error 事件不冒泡到祖先 div
- Vue 的 `@error` / `@error.capture` 在父元素上**完全收不到**

修正后方案：
1. **marked 后处理**（`web/src/utils/markdown.ts`）：解析完后用正则给每个 `<img>` 注入内联 onerror + data-fallback-text
2. **ImageWithFallback.vue**（`web/src/components/chat/ImageWithFallback.vue`）：用于 Vue 模板里直接写的 `<img>` 场景（如 ChatViewSSE:520 msg.imageUrl）

双轨覆盖 v-html 路径 + Vue 模板路径。

## 类 20.130 新铁律

**v-html 注入 img 必须 marked 后处理 inline onerror**（v-html 派工已知问题 + 本任务实战确认）

- v-html 派工：v-html 注入的 DOM **绕过** Vue 事件系统，Vue 的 `@error` / `@click` 等所有监听都失效
- 资源加载错误不冒泡：`<img src="404">` 失败时，浏览器只对 img 自身派发 error 事件，**不**冒泡到祖先元素
- 修正方案：
  1. 在 markdown 渲染层（marked.parse 之后）正则替换 `<img>` → 注入 `onerror="..."` 内联属性
  2. 占位符走 base64 SVG data URL（不依赖外链）
  3. Vue 模板里直接写 `<img>` 的场景用 ImageWithFallback.vue 包装
- 验证：派工 v10 单测 ⑤（多 img 全部注入）+ ChatViewSSE 浏览器实测

## 改动 commit

`a7ef24af7` — `[FIX-IMAGES-FRONTEND W99 +20] feat(chat): img onerror 兜底占位（图片 404 不再静默）`

base HEAD: `49b6b7640` (W100-RAG-4 +5.5 docs closure)
worktree: `E:/agent-fix-images-frontend`
branch: `chore/fix-images-frontend`
push origin: ✅
