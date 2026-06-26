# MicroBubble Agent 设计 Token 指南

> **v70 P3 沉淀**（2026-06-26）：本文档作为新组件开发第一手参考。新增任何颜色都必须从本文档选 token，不允许直接写 `#xxx`。
> **自动化守卫**：`npm run lint:css` 会拦截 `color: #xxx` / `background: #xxx` 字面（除 `rgba()` 透明色 + `currentColor` + `variables.css` 定义 token 本身 + 合法设计意图白名单）。
> **v73 沉淀**（2026-06-27）：`var(--token, #fallback)` 形式**允许保留**——fallback 是 token 缺失时的安全网，stylelint **不**拦截（属性值是 `var()` 函数不是裸 `#hex`）。全项目 217 处 fallback 全部是常用 token（`--color-primary` / `--color-danger` / `--color-success` 等），无需清理。

---

## 1. 主色（品牌色，6 主题 × 2 明暗 = 12 组合）

| Token | 用途 | light | dark |
|---|---|---|---|
| `--color-primary` | 主色（按钮/链接/激活态） | `#FF7A5C` 暖橙 | `#FF9D85` 亮橙 |
| `--color-primary-light` | hover 态 / 浅主色 | `#FF9D85` 亮橙 | `#FF7A5C` 暖橙 |
| `--color-primary-dark` | active 态 / 深主色 | `#E85A3A` 深橙 | `#FFB347` 金橙 |
| `--color-primary-bg` | 主色背景（按钮 hover 浅底） | `#FFF0ED` 奶橙 | `rgba(255,122,92,0.15)` |
| `--color-primary-border` | 主色边框 | `rgba(255,122,92,0.20)` | `rgba(255,122,92,0.25)` |
| `--color-accent` | 强调色（次按钮/高亮） | `#FFB347` 金橙 | `#FFC067` 亮金 |
| `--color-accent-bg` | 强调背景 | `#FFF8ED` 奶金 | `rgba(255,179,71,0.12)` |

**3 主题色板**（P1a 新增，`<html data-accent="X">` 切换）：
- **orange**（默认暖橙）— `--color-primary: #FF7A5C`
- **ocean**（海蓝）— `--color-primary: #4A90E2`
- **forest**（森林绿）— `--color-primary: #4CAF50`

---

## 2. 功能色（成功/警告/危险/信息）

| Token | 用途 | light | dark |
|---|---|---|---|
| `--color-success` | 成功色（已完成/通过） | `#67C23A` 绿 | `#85ce61` 亮绿 |
| `--color-success-bg` | 成功背景 | `#F0F9EB` 浅绿 | `rgba(103,194,58,0.15)` |
| `--color-warning` | 警告色（进行中/注意） | `#E6A23C` 黄 | `#ebb563` 亮黄 |
| `--color-warning-bg` | 警告背景 | `#FDF6EC` 浅黄 | `rgba(230,162,60,0.15)` |
| `--color-danger` | 危险色（错误/删除） | `#F56C6C` 红 | `#f78989` 亮红 |
| `--color-danger-bg` | 危险背景 | `#FEF0F0` 浅红 | `rgba(245,108,108,0.15)` |
| `--color-info` | 信息色（次要提示） | `#909399` 灰 | `#a6a9ad` 亮灰 |
| `--color-info-bg` | 信息背景 | `#F4F4F5` 浅灰 | `rgba(144,147,153,0.15)` |

---

## 3. 中性色（文本/边框/背景）

### 文本层级（4 级，从主到次）

| Token | 用途 | light | dark | 对比度 |
|---|---|---|---|---|
| `--color-text-primary` | 主文本（标题/正文） | `#2D2D2D` | `#e8eaed` | **12:1** (WCAG AAA) |
| `--color-text-regular` | 次文本（描述/标签） | `#606266` | `#c0c4cc` | **7:1** (WCAG AAA) |
| `--color-text-secondary` | 辅助文本（时间/来源） | `#909399` (v69 提亮) | `#a8aab0` (v69 提亮) | **4.5:1** (WCAG AA) |
| `--color-text-placeholder` | 占位符/disabled | `#C0C4CC` | `#606266` | 3:1 (仅 disabled) |

### 边框（2 级）

| Token | 用途 | light | dark |
|---|---|---|---|
| `--color-border` | 标准边框（卡片/输入框） | `#EBEEF5` | `#3a3d45` |
| `--color-border-light` | 浅边框（分隔线/次级容器） | `#F0F0F0` | `#2a2d35` |
| `--color-border-base` | 别名（同 `--color-border`） | `#EBEEF5` | `#3a3d45` |

### 背景（5 级）

| Token | 用途 | light | dark |
|---|---|---|---|
| `--color-bg-page` | 页面背景 | `#F5F7FA` | `#1a1d23` |
| `--color-bg-card` | 卡片背景 | `#FFFFFF` | `#2a2d35` |
| `--color-bg-warm` | 暖色背景（hero/任务配对卡） | `#FFF8F5` | `#2a2d35` |
| `--color-bg-hover` | hover 态背景 | `#F5F7FA` | `#3a3d45` |
| `--color-bg-sidebar` | 侧栏玻璃底 | `rgba(255,245,240,0.92)` | `rgba(26,29,35,0.92)` |
| `--color-sidebar-border` | 侧栏边框 | `rgba(255,122,92,0.12)` | `rgba(255,157,133,0.18)` |

---

## 4. 阴影（7 级，dark 模式自动增强透明度）

| Token | 用途 | light | dark |
|---|---|---|---|
| `--shadow-xs` | 极轻阴影（chip 悬浮） | `0 1px 2px rgba(0,0,0,0.04)` | `0 1px 2px rgba(0,0,0,0.30)` |
| `--shadow-sm` | 轻阴影（卡片默认） | `0 2px 8px rgba(0,0,0,0.06)` | `0 2px 8px rgba(0,0,0,0.40)` |
| `--shadow-md` | 中阴影（卡片 hover） | `0 4px 16px rgba(0,0,0,0.08)` | `0 4px 16px rgba(0,0,0,0.50)` |
| `--shadow-lg` | 重阴影（弹窗/dialog） | `0 8px 32px rgba(0,0,0,0.12)` | `0 8px 32px rgba(0,0,0,0.60)` |
| `--shadow-primary` | 主色光晕（hover 高亮） | `0 4px 20px rgba(255,122,92,0.30)` | `0 4px 20px rgba(255,122,92,0.40)` |
| `--shadow-glow` | 主色光晕（弱） | `0 4px 24px rgba(255,122,92,0.20)` | `0 4px 24px rgba(255,122,92,0.30)` |
| `--shadow-sidebar` | 侧栏阴影 | `4px 0 24px rgba(255,122,92,0.08)` | `4px 0 24px rgba(0,0,0,0.50)` |

---

## 5. 渐变库（6 主渐变 + 3 强调渐变）

| Token | 用途 | light |
|---|---|---|
| `--gradient-group-header` | 任务配对卡头部 | `linear-gradient(135deg, #FFF8F5 0%, #FFF0ED 100%)` |
| `--gradient-stat-in-progress` | Dashboard 进行中 stat | `linear-gradient(135deg, #FFF0ED 0%, #FFE4DC 100%)` |
| `--gradient-stat-done` | Dashboard 完成 stat | `linear-gradient(135deg, #F0F9EB 0%, #DCFCE7 100%)` |
| `--gradient-stat-overdue` | Dashboard 逾期 stat | `linear-gradient(135deg, #FEF0F0 0%, #FEE2E2 100%)` |
| `--gradient-welcome-hero` | Welcome 区域 hero | `linear-gradient(135deg, #FF7A5C 0%, #FFB347 100%)` |

**注意**：渐变 token 在 `[data-accent]` 主题切换时**不重定义**（保持原色），因为渐变是设计意图。

---

## 6. 间距/圆角/字体/动画

### 圆角（5 级）
- `--radius-sm: 4px` — chip / 小按钮
- `--radius-md: 8px` — 按钮 / 输入框
- `--radius-lg: 12px` — 卡片 / 弹窗
- `--radius-xl: 16px` — 大卡片 / 容器
- `--radius-full: 9999px` — 圆形 / 胶囊

### 间距（6 级，4px 步长）
- `--space-1: 4px` / `--space-2: 8px` / `--space-3: 12px` / `--space-4: 16px` / `--space-5: 20px` / `--space-6: 24px` / `--space-8: 32px` / `--space-10: 40px` / `--space-12: 48px`

### 字号（8 级）
- `--font-size-xs: 12px` / `--font-size-sm: 13px` / `--font-size-base: 14px` / `--font-size-md: 15px` / `--font-size-lg: 18px` / `--font-size-xl: 22px` / `--font-size-2xl: 28px` / `--font-size-3xl: 36px`

### 字重（4 级）
- `--font-weight-normal: 400` / `--font-weight-medium: 500` / `--font-weight-semibold: 600` / `--font-weight-bold: 700`

### 动画时长（3 级）
- `--duration-fast: 150ms` / `--duration-normal: 200ms` / `--duration-slow: 300ms`

### 缓动函数
- `--ease-out: cubic-bezier(0.16, 1, 0.3, 1)` — 主要缓动

### 主题切换过渡
- `--theme-transition: 280ms ease` — 切换 dark/light 时 bg/border/color/box-shadow 走平滑过渡

---

## 7. 反例 vs 正例对照

### ❌ 反模式（会触发 lint error）

```css
/* ❌ 字面色硬编码 */
.title { color: #1F2937; }            /* → var(--color-text-primary) */
.subtitle { color: #333; }            /* → var(--color-text-primary) */
.muted { color: #999; }              /* → var(--color-text-secondary) */
.label { color: #FF7A5C; }            /* → var(--color-primary) */
.danger { color: #F56C6C; }           /* → var(--color-danger) */
.success { color: #67C23A; }          /* → var(--color-success) */
.bg-page { background: #fff; }        /* → var(--color-bg-card) */
.bg-page2 { background: #f5f7fa; }    /* → var(--color-bg-page) */
.bg-success { background: #f0f9eb; }  /* → var(--color-success-bg) */
.border { border: 1px solid #e8eaed; }/* → var(--color-border) */
.shadow { box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
/* → var(--shadow-sm) — token 在 dark 自动重定义为 0 2px 8px rgba(0,0,0,0.4) */

/* ❌ 命名颜色 */
.x { color: white; }            /* → var(--color-text-primary) 或 #fff 仅在彩色 hero 上保留 */
.y { color: red; }              /* → var(--color-danger) */
```

### ✅ 正模式（lint pass）

```css
/* ✅ 全部用 token */
.title { color: var(--color-text-primary); }
.subtitle { color: var(--color-text-regular); }
.muted { color: var(--color-text-secondary); }
.label { color: var(--color-primary); }
.danger { color: var(--color-danger); }
.success { color: var(--color-success); }
.bg-page { background: var(--color-bg-card); }
.bg-page2 { background: var(--color-bg-page); }
.bg-success { background: var(--color-success-bg); }
.border { border: 1px solid var(--color-border); }
.shadow { box-shadow: var(--shadow-sm); }
```

### 🟡 合法例外（lint 自动豁免）

```css
/* ✅ rgba() 透明色（阴影/透明覆盖/玻璃拟态） */
.shadow-soft { box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
.overlay { background: rgba(0,0,0,0.5); }
.glass { backdrop-filter: blur(12px); background: rgba(255,255,255,0.7); }

/* ✅ currentColor（自动继承父级 color） */
.icon { color: currentColor; }

/* ✅ variables.css 自身（定义 token 必须用字面） */
:root { --color-primary: #FF7A5C; }

/* ✅ 渐变内的彩色字面（设计色变体，lint 暂不扫） */
.hero { background: linear-gradient(135deg, #FEE2E2 0%, #FCA5A5 100%); }
.btn { background: linear-gradient(135deg, #FF7A5C 0%, #FFB347 100%); }
```

### 🔵 已知设计意图白名单（`!important` 或 hero 上白字，**保留 #fff**）

| 位置 | 行 | 原因 |
|---|---|---|
| `views/Dashboard.vue:616` | `.btn-welcome { background: #fff !important; }` | 橙色 hero 上的白底按钮 |
| `views/Dashboard.vue:629-630` | `.btn-welcome-secondary { background: rgba(255,255,255,0.15); color: #fff; }` | 橙色 hero 上的玻璃态次按钮 |
| `layouts/MainLayout.vue:851` | `.recording-dot { background: #fff; }` | 录音胶囊红点中心白点（指示器反光） |
| `views/SettingsView.vue:627` | `.hero-content { color: #fff; }` | Settings 头像 hero 文字（橙色渐变背景） |
| `components/DashboardPet.vue:717` | 宠物光晕（白色） | 装饰元素 |

---

## 8. 新组件开发流程

### 第 1 步：选 token
- 问自己：这是"主色按钮"还是"次要文本"还是"卡片背景"？
- 查本文档 §1-5 选对应 token

### 第 2 步：写 CSS
```vue
<style scoped>
.card {
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
}
.card-title { color: var(--color-text-primary); }
.card-subtitle { color: var(--color-text-regular); }
.card-button {
  background: var(--color-primary);
  color: white;  /* ← 等等，这是命名颜色！ */
}
</style>
```

**等等**——`color: white` 会触发 lint。改用：
```vue
<style scoped>
.card-button {
  background: var(--color-primary);
  color: #fff;  /* ← 字面 #fff，lint 也会拦！ */
}
</style>
```

**正确做法**：在深色背景上需要白字时，用 **EP 默认白** 通过 `background: var(--color-primary); color: #fff;` 是错的——lint 拦。应该：
- 方案 A：用 `var(--color-text-on-primary)`（如果 token 存在，本项目**未定义**）
- 方案 B：把白字设计改为"高对比色"（如 `--color-text-primary` 在 light 上是深色，OK）
- 方案 C：明确写 `color: #fff` 并加 `/* stylelint-disable color-no-hex */` 注释（lint 显式豁免）
- 方案 D（推荐）：**在 token 系统加 `--color-text-on-primary` 变量**（如果有需要再补）

### 第 3 步：跑 lint
```bash
npm run lint:css
```
期望：0 errors。

### 第 4 步：硬刷新验证
- 切换 light/dark → 颜色跟随
- 切换 3 主题（orange/ocean/forest）→ 主色跟随

---

## 9. 常见错误 FAQ

### Q1: `color: #fff` 在深色按钮上 lint 拦了怎么办？
**A**: 加 `/* stylelint-disable color-no-hex */ ... /* stylelint-enable color-no-hex */` 局部豁免。或在 variables.css 加 `--color-text-on-primary: #fff;` 主题感知变量（推荐）。

### Q2: `background: rgba(0,0,0,0.1)` 这种阴影会被拦吗？
**A**: 不会。`rgba()` / `hsla()` 在 stylelint 配置中**自动豁免**（不在 `declaration-property-value-disallowed-list` 规则范围内）。但**强烈推荐**用 `var(--shadow-*)` 替代——`--shadow-sm` 在 dark 模式自动增强透明度。

### Q3: 现有 461 个 lint error 怎么办？
**A**: 这是 P2 范围外残留（命名颜色 / 主题感知后的彩色字面 / 旧组件残留）。**优先级**：
- v71+ 新增组件 → **0 error**（lint 拦截）
- 旧组件 → 临时豁免（`/* stylelint-disable */`），或单独 commit 清理

### Q4: `linear-gradient` 内的 `#FEE2E2` 等设计色会拦吗？
**A**: 当前**不拦**——`declaration-property-value-disallowed-list` 只匹配 `color:` / `background:` 精确属性名 + `#xxx` 模式，不匹配 `linear-gradient()` 内的颜色。**未来可加**（plan §3.3 提到的"渐变内颜色审查"是 P3 范围外）。

### Q5: 怎么跳过某个文件？
**A**: 在 `.stylelintrc.json` 的 `ignoreFiles` 加文件路径。**仅限**：
- `src/assets/variables.css`（定义 token）
- `src/assets/nutui-theme.scss`（NutUI 内部主题）
- `src/assets/mobile-base.css`（移动端基础样式）

### Q6: 旧组件临时跳过但不想让 lint 全部失败怎么办？
**A**: 用 `npm run lint:css:fix` 自动修复（`--fix` 选项，会修可自动修的），或临时注释 `/* stylelint-disable */` 在文件顶部。**禁止**全局加 `ignoreFiles` 跳过整个目录。

---

## 10. 沉淀纪律（永久）

1. **新增组件第一件事**：先看本文档选 token，不要直接写 `#xxx`
2. **dark mode 适配 = 用 token，不是写 dark 块**：v69 P1b 教训——加 100 条 `[data-theme="dark"] .x { ... }` 不如改源头用 token
3. **Stylelint v70 P3 起自动拦截**：CI 失败阻止 merge
4. **例外只有**：`variables.css`（定义 token）/ 渐变内白色 / `rgba()` 透明色 / `currentColor` / `/* stylelint-disable */` 局部豁免
5. **替换前 grep 上下文**：批量替换时检查"是否在彩色背景上"——白字在深色按钮上是设计意图
6. **dark 模式测试 = 切到 dark 看一遍**：所有 token 在 light/dark 都有定义，**硬刷新后切 dark 必须视觉正确**

---

## 11. 自动化工具

### 跑 lint
```bash
# 检查所有 vue/css/scss
cd web && npm run lint:css

# 自动修复（仅修可修的）
cd web && npm run lint:css:fix
```

### lint 规则定义
[`web/.stylelintrc.json`](../web/.stylelintrc.json)：
- `color-named: never` — 禁止命名颜色（white/red/blue 等）
- `declaration-property-value-disallowed-list` — 禁止 `color: #xxx` / `background: #xxx`
- `ignoreFiles` — `variables.css` / `nutui-theme.scss` / `mobile-base.css`

### 计划扩展（v71+）
- 加 `linear-gradient` 内的颜色审查
- 加 `var(--xxx, #fallback)` fallback 清理（204 处）
- 加 6 主题切换的视觉回归测试（Playwright 截图对比）

---

## 12. 关联文档

- [v70 plan](../C:/Users/pc/.claude/plans/snazzy-greeting-sedgewick.md) — 4 阶段 plan
- [CLAUDE.md](../CLAUDE.md) — 项目主文档（v69/v70 章节）
- [variables.css](../web/src/assets/variables.css) — token 定义源
- [stylelint 配置](../web/.stylelintrc.json) — 规则定义

---

## 13. v73 Fallback 政策（217 处 var fallback 不清理）

### 13.1 现象

v70 P3 Stylelint 守卫**只**拦截裸 `#hex` 字面（`color: #fff` / `background: #000`），**不**拦截 `var(--token, #hex)` 形式。实际项目中保留 217 处 `var(--xxx, #fallback)` 形式（统计时间：v73 启动）。

### 13.2 高频 fallback 模式

| 形式 | 数量 | 含义 |
|---|---:|---|
| `var(--color-danger, #F56C6C)` | 40 | 危险色 fallback |
| `var(--color-success, #67C23A)` | 28 | 成功色 fallback |
| `var(--color-primary, #FF7A5C)` | 24 | 主色 fallback |
| `var(--color-warning, #E6A23C)` | 20 | 警告色 fallback |
| `var(--color-text-secondary, #909399)` | 16 | 文本 fallback |
| 其它 `--color-*` | 89 | 各种 token fallback |

### 13.3 为什么保留 fallback

1. **防御性编程**：如果 `variables.css` 删了某个 token，fallback 兜底避免样式白屏
2. **变量调试**：DevTools 临时删 `--color-x` 可看 fallback 实际值，无需翻 variables.css
3. **零运行时成本**：CSS 解析时 var() 命中第一参就 short-circuit，fallback 不读
4. **视觉无差异**：变量已定义，fallback 永远不触发
5. **不浪费 bundle**：fallback 字符串不进 JS，CSS 压缩后保留

### 13.4 反例（不推荐形式）

```css
/* ❌ 反模式 1: fallback 是字面色但 token 名是缩写（易读错） */
.x { color: var(--c-p, #f57) }

/* ❌ 反模式 2: fallback 跟 token 实际值不一致（误导） */
:root { --color-primary: #FF7A5C; }
.x { color: var(--color-primary, #F00) }  /* fallback 写错 */

/* ❌ 反模式 3: 嵌套 var fallback（CSS 不支持） */
.x { color: var(--color-x, var(--color-y, #fff)) }  /* 第二参必须是字面 */
```

### 13.5 正例（推荐形式）

```css
/* ✅ 正模式 1: fallback = token 在 variables.css 的实际 light 值 */
.x { color: var(--color-primary, #FF7A5C) }

/* ✅ 正模式 2: EP 调色板用 EP 实际值 */
.x { color: var(--color-danger, #F56C6C) }

/* ✅ 正模式 3: NutUI 变量兜底 */
.x { color: var(--nut-white, #fff) }
```

### 13.6 何时应该清 fallback

唯一场景：token 在 `variables.css` **已经**删了，fallback 仍保留 → 100% 应该删 fallback，否则误导后续开发者以为"变量还在"。

**验证命令**（v73 实测找到 6 个真 orphan）：
```bash
cd e:/microbubble-agent
# 列出所有 fallback + 对应 token 在 3 个全局 CSS 文件是否仍存在
grep -rEho 'var\(--[a-z-]+,' web/src/ | sort -u | while read v; do
  token=$(echo "$v" | sed 's/var(\(--[^,]*\).*/\1/')
  if ! grep -qE "(^|\s)${token}(\s|:)" \
      web/src/assets/variables.css \
      web/src/assets/nutui-theme.scss \
      web/src/assets/mobile-base.css 2>/dev/null; then
    echo "ORPHAN: $v (token=$token)"
  fi
done
```

### 13.8 v73 实测 orphan 修复记录

| Orphan token | 文件:行 | 修复 |
|---|---|---|
| `--color-border-lighter` | TaskView.vue:540,551,570 | → `--color-border-light`（variables.css 实际存在） |
| `--bg-card` | UploadStatusBadge.vue:79 | → `--color-bg-card` |
| `--border-color` | UploadStatusBadge.vue:81 | → `--color-border` |
| `--text-primary` | UploadStatusBadge.vue:82 | → `--color-text-primary` |
| `--radius-pill` | MobileTaskView.vue:522 | → `--radius-full`（9999px 等价 pill 圆角） |
| `--color-primary-light-7` | ThemeToggleButton.vue:50 + MainLayout.vue:532（v73 二次扫描发现） | → `--color-primary-light`（实际 light 值 `#FF9D85`） |
| `--font-family-mono` | KnowledgeExtractionsPanel.vue:350,389 + KnowledgeImageGallery.vue:355 | **新增 token** `--font-family-mono: 'Courier New', Courier, monospace` + 3 处改用 token（无 fallback） |
| `--nut-white` / `--nut-black` | TabBar.vue:188,219 | **合法**（定义在 `nutui-theme.scss:35-36`，不在 variables.css） |
| `--i` | MainLayout.vue:720,724 | **保留**（CSS 动画 stagger 计数器，本地无 token 必要） |

**结果**：7 个真 orphan 全部修复（5 个改 token 名 + 1 个新增 token + 1 个 `--i` 保留为本地计算变量），2 个真合法（nutui 主题）。`npm run lint:css` 0 errors，`bash scripts/check-token-orphans.sh` 仅 1 个本地计算变量 `--i` 命中（设计意图保留）。

**新增脚本** `scripts/check-token-orphans.sh`：CI 集成时可加进 lint-css.yml 跑，确保未来新增 var fallback 必查 token 定义。

### 13.7 沉淀纪律

1. **fallback 不清理是设计决策**，不是技术债
2. **写 fallback 时复制 variables.css 实际值**，不要凭印象写
3. **CI 不会拦截**（stylelint 只扫裸 `#hex`），但人工 code review 必查
4. **删 variables.css token 时同步删所有 fallback**——避免孤儿

---

**最后更新**：2026-06-27（v73 fallback 政策 + CI 集成）
