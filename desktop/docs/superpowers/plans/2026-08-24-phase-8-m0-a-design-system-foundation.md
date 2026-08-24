# Phase 8-M0-A Scientific Research OS Design System Foundation 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 `executing-plans` 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在不改变科研业务数据流的前提下，建立 Phase 8-M0 的高级设计基础、桌面应用外壳和无 Store 依赖的共享 UI 原语。

**架构：** 保留当前 `View → Pinia Store → Service / IPC` 边界；令牌、全局样式和共享展示组件只提供视觉与无障碍能力。`Sidebar` 与 `HeaderBar` 继续是页面级 Store 适配层，新增原语只接受 props/emits。为避免破坏既有页面，保留既有 `ResearchPageShell`、`StatusBadge`、`ScientificMetric` 与 `ResearchState`，同时新增 M0-A 规范命名组件。

**技术栈：** Vue 3 `<script setup>`、TypeScript、Vue Router、Pinia、Vitest、Vue Test Utils、happy-dom、CSS Custom Properties。

---

## 审计结论

- `Sidebar.vue`、`HeaderBar.vue`、`MainLayout.vue` 已使用研究令牌，但导航仍是 I3-B 名称，缺少实验控制中心和命令入口。
- 研究路由未注册 `ExperimentControlCenter.vue`；既有 `research-project` 路由可承载“研究工作区”导航。
- 三份 CSS 文件已经存在；需要从蓝紫主题扩展为批准的浅色科研工作台与深色 SCADA 双主题，并保留旧令牌兼容。
- 已有 `ResearchPanel.vue`、`ResearchPageShell.vue`、`StatusBadge.vue`、`ScientificMetric.vue` 和 `ResearchState.vue`；M0-A 新组件不得导入任何 Store 或 Service。
- 既有研究 UI 合同测试采用源码契约与真实 happy-dom 挂载；新测试延续该模式并以表驱动用例达到至少 150 条新增断言实例。

## 文件结构

### 创建

- `desktop/src/renderer/src/components/research/ResearchPageHeader.vue`：纯 props 的页面标题、描述、状态与操作槽位。
- `desktop/src/renderer/src/components/research/ResearchStatusBadge.vue`：状态文字、图标与语义属性。
- `desktop/src/renderer/src/components/research/ResearchMetricCard.vue`：科学数值、单位、趋势与辅助说明。
- `desktop/src/renderer/src/components/research/ResearchEmptyState.vue`：纯 props 空状态。
- `desktop/src/renderer/src/components/research/ResearchLoadingState.vue`：纯 props 加载状态。
- `desktop/tests/unit/phase-8-m0-a-design-system.dom.test.ts`：M0-A 设计系统、外壳、原语、a11y 与导入边界的 ≥150 条视觉契约。

### 修改

- `desktop/src/renderer/src/styles/research-design-tokens.css`：双主题语义色、指定间距、圆角、阴影和排版令牌。
- `desktop/src/renderer/src/styles/research-global.css`：页面工作面、滚动条、焦点、选区和 `data-research-theme`。
- `desktop/src/renderer/src/styles/research-motion.css`：状态动效与 reduced-motion 降级。
- `desktop/src/renderer/src/layouts/Sidebar.vue`：11 项中文导航、实验控制入口、可读选中态。
- `desktop/src/renderer/src/layouts/HeaderBar.vue`：项目选择器、系统状态、全局 AI 状态与命令入口。
- `desktop/src/renderer/src/layouts/MainLayout.vue`：统一主壳 landmark 与 SCADA 路由主题标记。
- `desktop/src/renderer/src/router/index.ts`：实验控制中心路由与 M0-A 中文页面标题。
- `desktop/src/renderer/src/components/research/ResearchPanel.vue`：新增无障碍标题关联与 SCADA tone，不引入 Store。

## 任务 1：设计令牌与全局样式

**文件：**

- 修改：`desktop/src/renderer/src/styles/research-design-tokens.css`
- 修改：`desktop/src/renderer/src/styles/research-global.css`
- 修改：`desktop/src/renderer/src/styles/research-motion.css`
- 测试：`desktop/tests/unit/phase-8-m0-a-design-system.dom.test.ts`

- [ ] **步骤 1：编写令牌与动效的失败契约测试**

```ts
const REQUIRED_TOKENS = [
  '--research-graphite-950', '--research-mist-50', '--research-paper-0',
  '--research-teal-700', '--research-coral-500', '--research-amber-500',
  '--research-red-600', '--research-instrument-950', '--research-signal-green',
  '--research-space-1', '--research-space-2', '--research-space-3',
  '--research-space-4', '--research-space-5', '--research-space-6',
  '--research-space-8', '--research-space-10', '--research-radius-sm',
  '--research-radius-md', '--research-radius-lg', '--research-shadow-surface',
  '--research-shadow-floating', '--research-shadow-modal', '--research-font-ui',
  '--research-font-scientific', '--research-font-paper'
] as const

it.each(REQUIRED_TOKENS)('%s 是 M0-A 基础令牌', (name) => {
  expect(tokens).toContain(name)
})

it('SCADA 主题、焦点、选择、滚动条和 reduced-motion 具有可用规则', () => {
  expect(tokens).toContain("[data-research-theme='scada']")
  expect(globalStyles).toContain(':focus-visible')
  expect(globalStyles).toContain('::selection')
  expect(globalStyles).toContain('::-webkit-scrollbar')
  expect(motion).toContain('@media (prefers-reduced-motion: reduce)')
})
```

- [ ] **步骤 2：运行测试确认正确失败**

运行：`npm run test:unit -- phase-8-m0-a-design-system.dom.test.ts`

预期：FAIL，原因是 M0-A 测试文件和 SCADA / graphite 令牌尚不存在。

- [ ] **步骤 3：以兼容方式实现令牌与全局样式**

```css
:root {
  --research-graphite-950: #172129;
  --research-mist-50: #f6f8f7;
  --research-paper-0: #ffffff;
  --research-teal-700: #0e766e;
  --research-coral-500: #ef7256;
  --research-amber-500: #d9982d;
  --research-red-600: #c94757;
  --research-instrument-950: #111a1d;
  --research-signal-green: #7ed6ad;
  --research-space-1: 4px;
  --research-space-2: 8px;
  --research-space-3: 12px;
  --research-space-4: 16px;
  --research-space-5: 20px;
  --research-space-6: 24px;
  --research-space-8: 32px;
  --research-space-10: 40px;
  --research-radius-sm: 8px;
  --research-radius-md: 12px;
  --research-radius-lg: 16px;
  --research-shadow-surface: 0 8px 24px rgb(23 33 41 / 6%);
  --research-shadow-floating: 0 20px 48px rgb(23 33 41 / 14%);
  --research-shadow-modal: 0 28px 72px rgb(10 22 26 / 24%);
  --research-font-ui: Inter, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  --research-font-scientific: 'SFMono-Regular', Consolas, monospace;
  --research-font-paper: 'Noto Serif SC', 'Songti SC', serif;
}

[data-research-theme='scada'] {
  --research-bg-main: var(--research-instrument-950);
  --research-bg-card: var(--research-instrument-900);
  --research-text-primary: var(--research-instrument-text);
}
```

将旧 `primary`、`ai`、`success` 等令牌保留为兼容映射；在全局样式添加数据主题背景、科学数字与论文排版类；在动效中为 SCADA 运行状态添加克制脉冲，且在 reduced-motion 下禁用所有连续动画。

- [ ] **步骤 4：运行令牌测试确认通过**

运行：`npm run test:unit -- phase-8-m0-a-design-system.dom.test.ts`

预期：PASS；令牌、全局工作面和 reduced-motion 契约通过。

- [ ] **步骤 5：提交该任务的文件**

```bash
git add desktop/src/renderer/src/styles/research-design-tokens.css desktop/src/renderer/src/styles/research-global.css desktop/src/renderer/src/styles/research-motion.css desktop/tests/unit/phase-8-m0-a-design-system.dom.test.ts
git commit -m "test: define Phase 8-M0-A design token contracts"
```

## 任务 2：纯 props 共享科研原语

**文件：**

- 创建：`desktop/src/renderer/src/components/research/ResearchPageHeader.vue`
- 创建：`desktop/src/renderer/src/components/research/ResearchStatusBadge.vue`
- 创建：`desktop/src/renderer/src/components/research/ResearchMetricCard.vue`
- 创建：`desktop/src/renderer/src/components/research/ResearchEmptyState.vue`
- 创建：`desktop/src/renderer/src/components/research/ResearchLoadingState.vue`
- 修改：`desktop/src/renderer/src/components/research/ResearchPanel.vue`
- 测试：`desktop/tests/unit/phase-8-m0-a-design-system.dom.test.ts`

- [ ] **步骤 1：补充失败的组件和无 Store 依赖契约**

```ts
const PRIMITIVES = [
  ['ResearchPageHeader.vue', '当前研究', '研究目标'],
  ['ResearchStatusBadge.vue', '运行中', 'status'],
  ['ResearchMetricCard.vue', '传质系数', 'min⁻¹'],
  ['ResearchEmptyState.vue', '暂无科研数据', 'status'],
  ['ResearchLoadingState.vue', 'AI 正在分析...', 'status']
] as const

it.each(PRIMITIVES)('%s 提供中文视觉与语义契约', async (file, label, role) => {
  const source = componentSource(`research/${file}`)
  expect(source).toContain('defineProps')
  expect(source).not.toMatch(/stores\/|services\//)
  expect(source).toContain(label)
  expect(source).toContain(`role="${role}"`)
})
```

增加真实挂载断言：页面标题/描述/状态/操作槽位，徽章五种 tone，数值卡的单位和趋势，空状态的操作槽位，加载状态的 `aria-busy`。将完整 case 数组扩展到至少 95 个新增原语实例。

- [ ] **步骤 2：运行测试确认正确失败**

运行：`npm run test:unit -- phase-8-m0-a-design-system.dom.test.ts`

预期：FAIL，原因是 5 个 M0-A 命名组件不存在，`ResearchPanel` 尚无标题关联。

- [ ] **步骤 3：实现最小可复用原语**

```vue
<script setup lang="ts">
defineProps<{ title: string; description?: string; eyebrow?: string; status?: string }>()
</script>
<template>
  <header class="research-page-header">
    <div><p v-if="eyebrow">{{ eyebrow }}</p><h1>{{ title }}</h1><p v-if="description">{{ description }}</p></div>
    <div v-if="$slots.actions"><slot name="actions" /></div>
  </header>
</template>
```

每个原语只使用 `defineProps`、`defineEmits`、slot、`ResearchIcon` 和 CSS 令牌。`ResearchPanel` 为标题生成稳定 `id`，根节点使用 `aria-labelledby`；允许 `tone: 'scada'`。

- [ ] **步骤 4：运行原语测试确认通过**

运行：`npm run test:unit -- phase-8-m0-a-design-system.dom.test.ts`

预期：PASS；组件挂载、中文文案、a11y 语义和无 Store/Service import 全部通过。

- [ ] **步骤 5：提交该任务的文件**

```bash
git add desktop/src/renderer/src/components/research desktop/tests/unit/phase-8-m0-a-design-system.dom.test.ts
git commit -m "feat: add Phase 8-M0-A research UI primitives"
```

## 任务 3：应用外壳、路由与可访问导航

**文件：**

- 修改：`desktop/src/renderer/src/layouts/Sidebar.vue`
- 修改：`desktop/src/renderer/src/layouts/HeaderBar.vue`
- 修改：`desktop/src/renderer/src/layouts/MainLayout.vue`
- 修改：`desktop/src/renderer/src/router/index.ts`
- 测试：`desktop/tests/unit/phase-8-m0-a-design-system.dom.test.ts`

- [ ] **步骤 1：编写外壳导航与 header 的失败契约**

```ts
const M0A_NAVIGATION = [
  '科研驾驶舱', '科研助手', '研究工作区', '文献研究', '实验设计', '数据分析',
  'SCI写作', '知识图谱', 'AI研究团队', '实验控制中心', '系统设置'
] as const

it.each(M0A_NAVIGATION)('侧栏提供 %s 导航项', (label) => {
  expect(sidebarSource).toContain(`label: '${label}'`)
})

it('注册实验控制路由并提供项目选择、系统状态、AI 状态与命令入口', () => {
  expect(routerSource).toContain("name: 'research-experiment-control'")
  expect(headerSource).toContain('当前项目选择器')
  expect(headerSource).toContain('系统状态：在线')
  expect(headerSource).toContain('全局 AI 状态')
  expect(headerSource).toContain('打开命令与搜索')
})
```

增加真实挂载测试：11 个 RouterLink 的 `aria-label`、当前页 `aria-current`、侧栏收起按钮、项目选择器 `aria-expanded`、命令按钮 `aria-keyshortcuts="Control+K"`、系统/AI live region，及 `Escape` 关闭 popover。使外壳相关 case 总数达到至少 55。

- [ ] **步骤 2：运行测试确认正确失败**

运行：`npm run test:unit -- phase-8-m0-a-design-system.dom.test.ts`

预期：FAIL，原因是导航名称、控制中心路由和 header 控件尚未满足 M0-A 合同。

- [ ] **步骤 3：实现外壳升级与路由**

```ts
const NAV_ITEMS = [
  { label: '科研驾驶舱', icon: 'home', routeName: 'research-dashboard' },
  // …保留现有 routeName，更新 M0-A 中文标签…
  { label: '实验控制中心', icon: 'experiment', routeName: 'research-experiment-control' },
  { label: '系统设置', icon: 'settings', routeName: 'research-settings' }
] as const
```

为 `HeaderBar` 增加：当前项目选择器按钮和只显示 Store 中已有 `projectList` 的 listbox；系统在线状态；保留动态全局 AI 状态；`Ctrl+K` 命令/搜索入口与本地 placeholder popover。所有弹层支持 Escape、点击外部关闭和焦点恢复。为控制中心路由设置 `meta.theme: 'scada'`，`MainLayout` 以根元素 `data-research-theme` 消费它。

- [ ] **步骤 4：运行外壳测试确认通过**

运行：`npm run test:unit -- phase-8-m0-a-design-system.dom.test.ts`

预期：PASS；11 个中文导航、路由、header 控件、键盘行为与主题边界通过。

- [ ] **步骤 5：提交该任务的文件**

```bash
git add desktop/src/renderer/src/layouts/Sidebar.vue desktop/src/renderer/src/layouts/HeaderBar.vue desktop/src/renderer/src/layouts/MainLayout.vue desktop/src/renderer/src/router/index.ts desktop/tests/unit/phase-8-m0-a-design-system.dom.test.ts
git commit -m "feat: upgrade Phase 8-M0-A research application shell"
```

## 任务 4：测试计数、类型、构建与最终提交

**文件：**

- 修改：`desktop/tests/unit/phase-8-m0-a-design-system.dom.test.ts`
- 修改：仅为类型或测试失败所需的 `desktop/**` 文件

- [ ] **步骤 1：增加 150 条以上有效 M0-A 视觉契约并先运行失败用例**

```ts
const M0A_CASES = [
  ...TOKEN_CASES,
  ...GLOBAL_STYLE_CASES,
  ...PRIMITIVE_CASES,
  ...NAVIGATION_CASES,
  ...ACCESSIBILITY_CASES,
  ...IMPORT_BOUNDARY_CASES
] as const

it('M0-A 视觉契约不少于 150 条', () => {
  expect(M0A_CASES).toHaveLength(150)
})
```

每个数组元素对应一个不同的令牌、中文标签、状态、组件行为、a11y 语义或导入边界。计数断言不得替代逐项断言。

- [ ] **步骤 2：运行完整单元测试**

运行：`npm run test:unit`

预期：PASS；测试输出无失败，M0-A 契约数量至少 150。

- [ ] **步骤 3：运行类型与构建验证**

运行：

```bash
npx tsc --noEmit -p tsconfig.node.json
npx vue-tsc --noEmit -p tsconfig.web.json
npm run build
```

预期：每条命令 exit 0。

- [ ] **步骤 4：验证作用域与构建确定性**

运行：

```bash
git diff --check
git diff --name-only HEAD^..HEAD -- backend web app
npm run build
Get-ChildItem -Recurse out | Get-FileHash -Algorithm SHA256 | Sort-Object Path
```

预期：无 whitespace 错误、非 `desktop/**` 变更为零、两次构建产物清单一致。

- [ ] **步骤 5：提交最终 M0-A**

```bash
git add -- desktop
git commit -m "Phase 8-M0-A Scientific Research OS Design System Foundation"
```

## 计划自检

- 设计令牌、全局样式、应用外壳、6 个原语、可访问性、150 条测试、四项验证和最终提交均有明确任务。
- 测试在生产代码之前创建并运行失败；每个实现任务有独立红绿步骤。
- 组件名称、tone 与路由名在任务间一致：`ResearchPageHeader`、`ResearchStatusBadge`、`ResearchMetricCard`、`ResearchEmptyState`、`ResearchLoadingState`、`research-experiment-control`、`scada`。
- 文本未包含待定项；所有变更路径在 `desktop/**`。
