# 移动端「液态毛玻璃 (Liquid Glass)」升级实施规范

> 2026-08-31 选定方案 D。设计 token 层已就绪：`web/src/assets/mobile-glass.css`（main.js 已注册）。
> 视觉样稿参照：`docs/design/mobile-style-preview/index.html` 的「风格 D」区块（登录/首页/对话三屏）。

## 设计语言摘要

| 要素 | 规格 |
|---|---|
| 页面根 | 视图根节点加 class `mg-page`（极光渐变背景 + 文字色自动来） |
| 卡片 | class `mg-glass`（半透明白 + 白描边 + blur18 + 22px 圆角 + 紫调阴影）；强悬浮层用 `mg-glass-strong` |
| 主按钮 | class `mg-btn-primary`（紫→粉渐变 #7C6BD8→#C66BD8→#F08AC0，圆角 18，白字 800） |
| 次按钮 | class `mg-btn-glass`（玻璃底紫字） |
| 输入框 | class `mg-input` |
| 标签芯片 | class `mg-chip` + 变体 `.ok/.warn/.dgr/.info` |
| 文字 | `--mg-text`（主）`--mg-text-strong`（标题）`--mg-text-soft`（次要）`--mg-text-faint`（占位/禁用） |
| 语义色 | `--mg-success / --mg-warning / --mg-danger / --mg-info` + 对应 `-soft` 背景 |
| 圆角 | `--mg-radius-md:16 / -lg:22 / -xl:28 / -pill` |
| 入场动画 | class `mg-rise` + `mg-stagger-1..5`（每列表 section 一个层级） |
| TabBar | 已改为悬浮玻璃胶囊（`--tabbar-height` 已 bump，页面底部占位继续用 `calc(var(--tabbar-height) + var(--sab))`） |

## 铁律（违反即返工）

0. **颜色 lint 硬约束（来自 web/tests/e2e/mobile_dark_v33.spec.js [D]/[E]）**：MobileTaskView / MobileDriveView / MobileMeetingView / MobileKnowledgeView / MobileChatView / MobileDashboard 这 6 个视图源码内，任何 CSS 属性值**不允许裸写** `: #hex` 或非黑/白的 `: rgba(...)`（除非该行含 `var(`，即 token + fallback 形式）。需要半透明品牌色时用 `var(--mg-tint)` / `var(--mg-track)` / `var(--mg-divider)`（已加进 mobile-glass.css）。纯黑/纯白半透明遮罩允许。

1. **只改 `<template>` 的 class / `<style>` 块，不改 `<script setup>` 业务逻辑、数据获取、路由、事件绑定**。允许新增纯展示用的静态 class 与装饰节点（如色团 `<div class="aurora">` 不需要——mg-page 已带背景）。
2. **保留所有 `aria-*`、`title`、`role`、`data-testid`、既有 class 名中测试/JS 依赖的部分**（vitest / Playwright 按 class 选择，删名必挂）。迁移 = 旧 class 保留 + 新样式挂到旧 class 上，或直接改旧 class 的 CSS 规则。优先后者：**尽量保持 template 结构，重写 style**。
3. 每个视图 **必须自包含 `<style scoped>`**（类 20.186）。dark mode 覆盖如果需要跨组件命中第三方元素（NutUI），放到第二个 **非 scoped** `<style>` 块（类 20.188 / v62 教训：scoped 里 `[data-theme] + :deep()` 组合永远不匹配）。
4. 颜色一律用 `--mg-*` 变量，**禁止新增硬编码 hex**（样稿里的配方已沉淀为 token；渐变必须用 `var(--mg-gradient-btn)` 等）。
5. 底部内容占位：有 TabBar 的页面 `padding-bottom: calc(var(--tabbar-height, 76px) + var(--sab, 0px))`；无 TabBar 的详情/浮层页 `calc(24px + var(--sab, 0px))`。
6. 顶部安全区沿用各视图现有 `var(--sat)` 写法，不要发明新的。
7. **不运行 npm build / dev server / 不 git commit** —— 统一收口时由指挥执行。不要动 `mobile-glass.css`、`variables.css`、`main.js`、`TabBar.vue`、登录/首页（指挥已负责）。
8. 触摸目标 ≥44px；点击态用 `:active { transform: scale(.97) }` 或透明度反馈；`prefers-reduced-motion` 由全局 token 层处理，视图内自加的 animation 需在全局规则覆盖范围内（用 mg-rise 即自动被覆盖）。
9. 保持组件对 props/emits/slots 的接口签名完全不变。
10. 改完自查：`grep -n "#[0-9a-fA-F]\{3,8\}" <文件>` 新增行里不应出现新 hex（旧行保留的除外）。

## 视图分配

| 组 | 文件 | 备注 |
|---|---|---|
| 指挥 | TabBar.vue / MobileLoginView.vue / MobileDashboard.vue / mobile-glass.css | 已完成或进行中 |
| Chat | views/mobile/chat/ 全部 (MobileChatView / MobileHeader / MobileInputBar / MobileMessageBubble / MobileSessionDrawer / MobileRichCard / FollowUpChips 如存在) | 输入栏=悬浮玻璃胶囊；气泡：用户=渐变紫、助手=mg-glass；不要动 SSE/流式逻辑 |
| Tasks | MobileTaskView.vue + MobileTaskTrash.vue | 任务行=mg-glass 列表卡；优先级点用 --mg-danger/--mg-warning/--mg-info |
| Meeting | MobileMeetingView.vue + MobileMeetingDetailView.vue + MobileMeetingRoom.vue | Room 页只重皮肤（录音控制交互逻辑零改动） |
| Knowledge | MobileKnowledgeView.vue + MobileKnowledgeDetailView.vue | 搜索头=玻璃胶囊；卡片列表 mg-glass |
| Drive + Settings | MobileDriveView.vue + MobileFileList.vue + MobileSettingsView.vue | 网盘列表行玻璃化；设置分组卡片化 |

## 视觉细节约定

- **列表行卡片**：`mg-glass` + `border-radius: var(--mg-radius-md)` + `padding: 13px 14px` + `margin-bottom: 10px`，整行可点的用 button 保持原生语义。
- **section 标题**：15-16px / 800 / `--mg-text-strong`，右侧「全部 →」`--mg-primary`。
- **大数字**（统计）：20-30px / 800；彩色变体用 `--mg-primary`、`--mg-primary-2`、`--mg-primary-3`。
- **进度环**（可选点缀）：`conic-gradient(var(--mg-primary) 0 <pct>%, rgba(124,107,216,.15) <pct>% 100%)`。
- **空态**：emoji + `--mg-text-soft` 文案，放 mg-glass 卡里，比裸文字精致。
- **聊天气泡**：用户 `border-radius: 18px 18px 6px 18px`、助手 `18px 18px 18px 6px`。
- NutUI 组件（nut-tabbar 等）颜色被 `.mg-tabbar` 全局覆盖，其余 nut-* 组件如需玻璃化在视图非 scoped 块内覆盖，作用域前缀必须带上视图根 class（避免污染）。
