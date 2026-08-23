# Phase 8-I3-B Scientific Research OS Visual Pro 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在不改变现有科研业务数据流与服务接口的前提下，把 `desktop/**` 升级为定制级中文 AI 科研桌面应用，并新增不少于 300 个有效 UI 测试。

**架构：** 建立 CSS 设计令牌、定制 SVG 图标、通用科研展示组件和 ECharts 科学主题；页面仍由现有 Pinia Store 驱动，通用组件只通过 props/emit 工作。先建立真实组件挂载测试，再按应用外壳、首页、Agent 中心和四类科研工作区逐批实现。

**技术栈：** Electron 32、Vue 3.5、TypeScript 5.6、Pinia 2、Vue Router 4、Vitest 2、Vue Test Utils 2、Happy DOM、ECharts 5、CSS 自定义属性。

**执行目录：** 所有 `npm`、`npx`、`tsc` 和 `vue-tsc` 命令从 `desktop/` 运行；所有 `git` 命令从仓库根运行。

---

## 文件结构

### 新建

- `desktop/src/renderer/src/styles/research-design-tokens.css`：色彩、排版、间距、圆角、阴影、层级和桌面断点。
- `desktop/src/renderer/src/styles/research-global.css`：全局浅色工作面、焦点、滚动条和基础元素。
- `desktop/src/renderer/src/styles/research-motion.css`：页面、卡片、进度、Agent 运行态和减少动态效果。
- `desktop/src/renderer/src/components/icons/research-icons.ts`：图标名称类型与 SVG 路径数据。
- `desktop/src/renderer/src/components/icons/ResearchIcon.vue`：统一定制 SVG 图标渲染器。
- `desktop/src/renderer/src/components/research/ResearchPageShell.vue`：页面标题、说明、状态和操作区。
- `desktop/src/renderer/src/components/research/ResearchPanel.vue`：科研面板标题、状态、操作与内容插槽。
- `desktop/src/renderer/src/components/research/ResearchState.vue`：加载、空、错误三态。
- `desktop/src/renderer/src/components/research/ScientificChart.vue`：ECharts 生命周期封装。
- `desktop/src/renderer/src/utils/scientific-chart.ts`：从现有模型拟合结果构建科学图表配置。
- `desktop/tests/helpers/mount-research.ts`：Pinia、Router 与组件挂载辅助函数。
- `desktop/tests/fixtures/research-ui.ts`：UI 状态矩阵和页面中文契约 fixture。
- `desktop/tests/unit/research-design-tokens.dom.test.ts`：72 个令牌与动效契约。
- `desktop/tests/unit/research-icon.dom.test.ts`：48 个图标与可访问性契约。
- `desktop/tests/unit/research-primitives.dom.test.ts`：74 个通用组件契约。
- `desktop/tests/unit/research-layout.dom.test.ts`：46 个布局、导航与路由契约。
- `desktop/tests/unit/research-pages.dom.test.ts`：96 个页面、状态与中文标签契约。
- `desktop/tests/unit/scientific-chart.dom.test.ts`：34 个图表构建与生命周期契约。
- `desktop/docs/ui-design/phase8-i3-b-verification.md`：最终测试、构建、隔离与视觉验收记录。

### 修改

- `desktop/package.json`、`desktop/package-lock.json`：增加 ECharts 与组件测试依赖。
- `desktop/vitest.config.ts`：保留 Node 默认环境，DOM 测试通过文件指令使用 Happy DOM。
- `desktop/src/renderer/src/main.ts`：加载三份全局科研样式。
- `desktop/src/renderer/src/App.vue`：移除深色根主题并加入页面过渡。
- `desktop/src/renderer/src/router/index.ts`：默认入口和 `/home` 指向科研首页，保留旧路由。
- `desktop/src/renderer/src/layouts/MainLayout.vue`、`Sidebar.vue`、`HeaderBar.vue`：升级应用外壳。
- `desktop/src/renderer/src/components/ui/{Button,Card,Loading,EmptyState,ErrorState}.vue`：保留 props/emit，内部迁移到新令牌。
- `desktop/src/renderer/src/components/research/{AgentCard,ChartPanel,CitationCard,EvidenceCard,InsightCard,ProjectCard,ScientificMetric,StatusBadge,Timeline}.vue`：移除 Emoji 和硬编码主题色，使用通用图标与令牌。
- `desktop/src/renderer/src/pages/research/{Dashboard,Assistant,ProjectWorkspace,Literature,Experiment,DataAnalysis,Manuscript,KnowledgeGraph,AgentCenter,Settings}.vue`：升级视觉、布局、状态与交互。
- `desktop/tests/unit/research-os-frontend.test.ts`：迁移 36 个已过时的硬编码/假数据断言。
- `desktop/tests/unit/research-os-integration.test.ts`：迁移 1 个已过时的 Dashboard 源码断言。

### 明确不修改

- `desktop/src/renderer/src/stores/research/**`
- `desktop/src/renderer/src/services/research/**`
- `desktop/src/main/**`
- `desktop/src/shared/**`
- `web/**`、`app/**`、`backend/**`

---

## 任务 1：建立真实 Vue UI 测试环境并迁移旧红灯契约

**文件：**

- 修改：`desktop/package.json`
- 修改：`desktop/package-lock.json`
- 修改：`desktop/vitest.config.ts`
- 创建：`desktop/tests/helpers/mount-research.ts`
- 创建：`desktop/tests/fixtures/research-ui.ts`
- 修改：`desktop/tests/unit/research-os-frontend.test.ts`
- 修改：`desktop/tests/unit/research-os-integration.test.ts`

- [ ] **步骤 1：记录当前失败基线**

运行：

```powershell
npm run test:unit
```

预期：`5943 passed / 37 failed`；失败只来自 `research-os-frontend.test.ts` 的 36 条旧源码断言与 `research-os-integration.test.ts` 的 1 条旧 Dashboard 断言。

- [ ] **步骤 2：安装测试与图表依赖**

运行：

```powershell
npm install echarts@^5.6.0
npm install --save-dev @vue/test-utils@^2.4.6 happy-dom@^18.0.1
```

预期：`package.json` 和 `package-lock.json` 更新；不修改根目录或 `web/package.json`。

- [ ] **步骤 3：创建挂载辅助函数**

写入 `desktop/tests/helpers/mount-research.ts`：

```ts
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { mount, type ComponentMountingOptions, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import type { Component } from 'vue'

export interface ResearchMountResult {
  wrapper: VueWrapper
  pinia: Pinia
  router: Router
}

export async function mountResearch(
  component: Component,
  options: ComponentMountingOptions<Record<string, unknown>> = {}
): Promise<ResearchMountResult> {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'research-dashboard', component: { template: '<div />' } },
      { path: '/research/agent-center', name: 'research-agent-center', component: { template: '<div />' } }
    ]
  })
  await router.push('/')
  await router.isReady()
  const wrapper = mount(component, {
    ...options,
    global: {
      ...options.global,
      plugins: [pinia, router, ...(options.global?.plugins ?? [])]
    }
  })
  return { wrapper, pinia, router }
}
```

- [ ] **步骤 4：创建测试矩阵 fixture**

写入 `desktop/tests/fixtures/research-ui.ts`：

```ts
export const RESEARCH_NAV = [
  ['科研首页', 'research-dashboard', 'home'],
  ['科研助手', 'research-assistant', 'assistant'],
  ['项目空间', 'research-project', 'project'],
  ['文献研究', 'research-literature', 'literature'],
  ['实验设计', 'research-experiment', 'experiment'],
  ['数据分析', 'research-data-analysis', 'data'],
  ['论文生成', 'research-manuscript', 'manuscript'],
  ['知识图谱', 'research-knowledge-graph', 'graph'],
  ['Agent 中心', 'research-agent-center', 'agent'],
  ['系统设置', 'research-settings', 'settings']
] as const

export const RESEARCH_STATES = [
  ['loading', 'AI 正在分析...'],
  ['empty', '暂无科研数据'],
  ['error', '分析失败，请重试']
] as const

export const RESEARCH_PAGES = [
  ['Dashboard', ['当前科研项目', 'AI 研究活动', '研究洞察']],
  ['Assistant', ['研究会话', '研究轨迹', '引用文献']],
  ['ProjectWorkspace', ['项目概览', '文献', '实验', '数据', '模型', '论文']],
  ['Literature', ['文献证据工作区', '相关度', '证据等级', '引用位置']],
  ['Experiment', ['研究假设', '实验变量', 'AI 实验建议']],
  ['DataAnalysis', ['数据质量', '模型拟合', 'AI 解释']],
  ['Manuscript', ['论文结构', '正文草稿', 'SCI 审阅']],
  ['KnowledgeGraph', ['实体列表', '关系详情']],
  ['AgentCenter', ['AI 思考时间线', '智能体协作矩阵', '工具执行可视化']],
  ['Settings', ['模型配置', '知识库管理', '用户研究方向', 'API 设置']]
] as const
```

- [ ] **步骤 5：把旧设计契约改成新设计红灯**

在两个旧测试文件中迁移当前 37 条失败断言，并主动迁移目前仍通过但会与新设计冲突的断言。删除对 `#0f172a`、`#f97316`、Emoji、220px 旧侧栏、固定 mock 数字、固定假数据字符串和“不允许页面导入 Store”的错误要求；改为断言新令牌导入、`ResearchIcon`、默认科研首页、真实 Store 数据绑定、统一三态和新中文结构标签。保留与新设计无冲突的路由存在性、组件存在性和服务隔离测试。

关键替换示例：

```ts
it('sidebar uses shared research tokens and custom icons', () => {
  expect(sidebarContent).toContain('var(--research-sidebar-width)')
  expect(sidebarContent).toContain('ResearchIcon')
  expect(sidebarContent).not.toMatch(/[💬📁📚🧪📊📝🔗🤖⚙️]/u)
})

it('Dashboard renders a stable dataset state contract', () => {
  const content = readFileSync(resolve(rendererRoot, 'pages/research/Dashboard.vue'), 'utf8')
  expect(content).toContain('datasetStore.isLoading')
  expect(content).toContain('ResearchState')
})

it('research pages may connect Pinia while presentational components stay isolated', () => {
  const component = readFileSync(resolve(rendererRoot, 'components/research/ResearchPanel.vue'), 'utf8')
  expect(component).not.toMatch(/stores\/research|services\/research/)
})
```

- [ ] **步骤 6：运行新契约并确认正确失败**

运行：

```powershell
npx vitest run tests/unit/research-os-frontend.test.ts tests/unit/research-os-integration.test.ts --config vitest.config.ts
```

预期：失败原因是 `ResearchIcon`、令牌、`ResearchState` 和新页面结构尚未实现；不得出现依赖解析错误。

- [ ] **步骤 7：提交测试基础设施**

```powershell
git add desktop/package.json desktop/package-lock.json desktop/vitest.config.ts desktop/tests
git commit -m "test(desktop): establish visual pro UI contracts"
```

---

## 任务 2：实现设计令牌、全局工作面与动效系统

**文件：**

- 创建：`desktop/src/renderer/src/styles/research-design-tokens.css`
- 创建：`desktop/src/renderer/src/styles/research-global.css`
- 创建：`desktop/src/renderer/src/styles/research-motion.css`
- 修改：`desktop/src/renderer/src/main.ts`
- 修改：`desktop/src/renderer/src/App.vue`
- 创建：`desktop/tests/unit/research-design-tokens.dom.test.ts`

- [ ] **步骤 1：编写 72 个令牌与动效红灯测试**

测试采用以下独立矩阵：22 个颜色令牌、10 个排版令牌、10 个间距令牌、6 个圆角令牌、6 个阴影令牌、6 个层级/布局令牌、6 个动效时长/曲线令牌、6 个全局与减少动态效果契约，共 72 个测试实例。

核心测试代码：

```ts
// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(__dirname, '../../src/renderer/src')
const readOrEmpty = (file: string): string => existsSync(file) ? readFileSync(file, 'utf8') : ''
const tokens = readOrEmpty(resolve(root, 'styles/research-design-tokens.css'))
const motion = readOrEmpty(resolve(root, 'styles/research-motion.css'))

const tokenNames = [
  '--research-primary-500', '--research-primary-600', '--research-ai-500',
  '--research-success-500', '--research-warning-500', '--research-danger-500',
  '--research-bg-main', '--research-bg-card', '--research-bg-panel',
  '--research-text-primary', '--research-text-secondary', '--research-border-subtle',
  '--research-space-1', '--research-space-2', '--research-space-3', '--research-space-4',
  '--research-radius-card', '--research-radius-button', '--research-radius-panel',
  '--research-shadow-soft', '--research-shadow-medium', '--research-shadow-floating'
] as const

describe('科研设计令牌', () => {
  it.each(tokenNames)('定义 %s', (name) => expect(tokens).toContain(name))
  it('为 1440px 定义平衡密度', () => expect(tokens).toContain('--research-sidebar-width: 232px'))
  it('为 1920px 定义扩展间距', () => expect(tokens).toContain('@media (min-width: 1720px)'))
  it('支持减少动态效果', () => expect(motion).toContain('prefers-reduced-motion: reduce'))
})
```

- [ ] **步骤 2：运行测试确认文件缺失导致红灯**

运行：

```powershell
npx vitest run tests/unit/research-design-tokens.dom.test.ts --config vitest.config.ts
```

预期：FAIL，原因是三份样式文件尚不存在。

- [ ] **步骤 3：实现完整令牌**

`research-design-tokens.css` 至少包含：

```css
:root {
  --research-primary-50: #eef3ff;
  --research-primary-500: #4263df;
  --research-primary-600: #3152c9;
  --research-ai-50: #f3efff;
  --research-ai-500: #7654d8;
  --research-success-50: #edf9f4;
  --research-success-500: #1a9b72;
  --research-warning-50: #fff7ea;
  --research-warning-500: #d98925;
  --research-danger-50: #fff1f2;
  --research-danger-500: #d84f63;
  --research-bg-main: #f5f7fb;
  --research-bg-card: #ffffff;
  --research-bg-panel: #fafbfe;
  --research-text-primary: #17223b;
  --research-text-secondary: #66748d;
  --research-text-muted: #8d98aa;
  --research-border-subtle: #e4e9f1;
  --research-space-1: 4px;
  --research-space-2: 8px;
  --research-space-3: 12px;
  --research-space-4: 16px;
  --research-space-5: 20px;
  --research-space-6: 24px;
  --research-space-8: 32px;
  --research-radius-button: 10px;
  --research-radius-card: 14px;
  --research-radius-panel: 18px;
  --research-shadow-soft: 0 4px 16px rgb(33 52 86 / 5%);
  --research-shadow-medium: 0 12px 30px rgb(33 52 86 / 10%);
  --research-shadow-floating: 0 22px 54px rgb(33 52 86 / 15%);
  --research-sidebar-width: 232px;
  --research-sidebar-collapsed-width: 76px;
  --research-header-height: 64px;
  --research-duration-fast: 160ms;
  --research-duration-normal: 240ms;
  --research-duration-slow: 320ms;
  --research-ease-standard: cubic-bezier(.2,.8,.2,1);
}

@media (min-width: 1720px) {
  :root { --research-page-gutter: 32px; --research-grid-gap: 20px; }
}
```

`research-global.css` 负责浅色 body、字体、焦点、选择色和滚动条；`research-motion.css` 定义 `.research-page-enter-active`、`.research-card-interactive`、`.research-agent-running`，并在减少动态效果媒体查询中关闭 animation 与 transform。

- [ ] **步骤 4：在入口加载样式并移除深色根主题**

`main.ts` 顶部加入：

```ts
import './styles/research-design-tokens.css'
import './styles/research-global.css'
import './styles/research-motion.css'
```

`App.vue` 使用路由过渡：

```vue
<RouterView v-slot="{ Component }">
  <Transition name="research-page" mode="out-in">
    <component :is="Component" :key="route.fullPath" />
  </Transition>
</RouterView>
```

- [ ] **步骤 5：运行 72 个测试并确认绿灯**

```powershell
npx vitest run tests/unit/research-design-tokens.dom.test.ts --config vitest.config.ts
```

预期：72 passed。

- [ ] **步骤 6：提交设计系统**

```powershell
git add desktop/src/renderer/src/styles desktop/src/renderer/src/main.ts desktop/src/renderer/src/App.vue desktop/tests/unit/research-design-tokens.dom.test.ts
git commit -m "feat(desktop): add scientific research design system"
```

---

## 任务 3：实现定制图标、科研原语与全局三态

**文件：**

- 创建：`desktop/src/renderer/src/components/icons/research-icons.ts`
- 创建：`desktop/src/renderer/src/components/icons/ResearchIcon.vue`
- 创建：`desktop/src/renderer/src/components/research/ResearchPageShell.vue`
- 创建：`desktop/src/renderer/src/components/research/ResearchPanel.vue`
- 创建：`desktop/src/renderer/src/components/research/ResearchState.vue`
- 修改：`desktop/src/renderer/src/components/ui/{Button,Card,Loading,EmptyState,ErrorState}.vue`
- 修改：`desktop/src/renderer/src/components/research/{AgentCard,CitationCard,EvidenceCard,InsightCard,ProjectCard,ScientificMetric,StatusBadge,Timeline}.vue`
- 创建：`desktop/tests/unit/research-icon.dom.test.ts`
- 创建：`desktop/tests/unit/research-primitives.dom.test.ts`

- [ ] **步骤 1：编写 48 个图标红灯测试**

图标名称固定为：`home`、`assistant`、`project`、`literature`、`experiment`、`data`、`manuscript`、`graph`、`agent`、`settings`、`notification`、`user`、`collapse`、`expand`、`search`、`upload`、`check`、`warning`、`error`、`idle`、`running`、`sparkles`、`tool`、`evidence`、`citation`、`model`、`clock`、`progress`、`folder`、`document`。每个图标验证 SVG、名称类、`aria-hidden` 或可读 label；另验证未知名称降级、尺寸与色彩继承，共 48 个实例。

```ts
// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'

const componentPath = resolve(__dirname, '../../src/renderer/src/components/icons/ResearchIcon.vue')
const iconDataPath = resolve(__dirname, '../../src/renderer/src/components/icons/research-icons.ts')

describe('ResearchIcon', () => {
  it('图标实现文件存在', () => {
    expect(existsSync(componentPath)).toBe(true)
    expect(existsSync(iconDataPath)).toBe(true)
  })
  it.each(['home', 'assistant', 'project', 'literature'] as const)('渲染 %s 图标', async (name) => {
    if (!existsSync(componentPath) || !existsSync(iconDataPath)) return
    const [{ mount }, { default: ResearchIcon }] = await Promise.all([
      import('@vue/test-utils'),
      import('@/components/icons/ResearchIcon.vue')
    ])
    const wrapper = mount(ResearchIcon, { props: { name } })
    expect(wrapper.find('svg').exists()).toBe(true)
    expect(wrapper.classes()).toContain(`research-icon--${name}`)
  })
  it('装饰图标对读屏隐藏', async () => {
    if (!existsSync(componentPath)) return
    const [{ mount }, { default: ResearchIcon }] = await Promise.all([
      import('@vue/test-utils'), import('@/components/icons/ResearchIcon.vue')
    ])
    expect(mount(ResearchIcon, { props: { name: 'home' } }).attributes('aria-hidden')).toBe('true')
  })
  it('有标签时暴露中文名称', async () => {
    if (!existsSync(componentPath)) return
    const [{ mount }, { default: ResearchIcon }] = await Promise.all([
      import('@vue/test-utils'), import('@/components/icons/ResearchIcon.vue')
    ])
    const wrapper = mount(ResearchIcon, { props: { name: 'home', label: '科研首页' } })
    expect(wrapper.attributes('aria-label')).toBe('科研首页')
  })
})
```

- [ ] **步骤 2：编写 74 个科研原语红灯测试**

覆盖 `ResearchPageShell` 12 个、`ResearchPanel` 12 个、`ResearchState` 18 个、`Button/Card` 12 个、`AgentCard/Timeline/Metric/Badge/Insight` 20 个状态与事件实例。

`ResearchState` 核心测试：

```ts
it.each([
  ['loading', 'AI 正在分析...'],
  ['empty', '暂无科研数据'],
  ['error', '分析失败，请重试']
] as const)('%s 状态显示标准中文', (state, label) => {
  const wrapper = mount(ResearchState, { props: { state } })
  expect(wrapper.text()).toContain(label)
})

it('错误态发出 retry', async () => {
  const wrapper = mount(ResearchState, { props: { state: 'error' } })
  await wrapper.get('button').trigger('click')
  expect(wrapper.emitted('retry')).toHaveLength(1)
})
```

- [ ] **步骤 3：运行测试确认正确红灯**

```powershell
npx vitest run tests/unit/research-icon.dom.test.ts tests/unit/research-primitives.dom.test.ts --config vitest.config.ts
```

预期：FAIL，缺少新图标与科研原语。

- [ ] **步骤 4：实现图标类型和渲染器**

`research-icons.ts` 导出只读路径表和类型：

```ts
export const RESEARCH_ICONS = {
  home: ['M4 13h6V4H4v9Z', 'M4 20h6v-4H4v4Z', 'M14 20h6v-9h-6v9Z', 'M14 4v4h6V4h-6Z'],
  assistant: ['M5 18l-2 3v-5a8 8 0 1 1 3 2', 'M8 10h.01', 'M12 10h.01', 'M16 10h.01'],
  project: ['M3 7h7l2 2h9v10H3V7Z'],
  literature: ['M4 5.5A2.5 2.5 0 0 1 6.5 3H11v17H6.5A2.5 2.5 0 0 0 4 22V5.5Z', 'M20 5.5A2.5 2.5 0 0 0 17.5 3H13v17h4.5A2.5 2.5 0 0 1 20 22V5.5Z']
} as const

export type ResearchIconName = keyof typeof RESEARCH_ICONS
export const RESEARCH_ICON_NAMES = Object.keys(RESEARCH_ICONS) as ResearchIconName[]
```

补齐上述 30 个名称，每个 path 使用 `fill="none"`、`stroke="currentColor"`、统一 `viewBox="0 0 24 24"`。

- [ ] **步骤 5：实现三种科研原语**

`ResearchState.vue` 完整接口：

```vue
<script setup lang="ts">
import ResearchIcon from '../icons/ResearchIcon.vue'

const props = withDefaults(defineProps<{
  state: 'loading' | 'empty' | 'error'
  title?: string
  description?: string
}>(), {})
const emit = defineEmits<{ retry: [] }>()
const copy = {
  loading: { icon: 'sparkles', title: 'AI 正在分析...', description: '正在整理科研数据与证据，请稍候。' },
  empty: { icon: 'document', title: '暂无科研数据', description: '导入资料或创建研究任务后，这里会显示结果。' },
  error: { icon: 'error', title: '分析失败，请重试', description: '已有内容不会丢失，可以重新发起本次分析。' }
} as const
</script>

<template>
  <section :class="['research-state', `research-state--${state}`]" :aria-busy="state === 'loading'">
    <ResearchIcon :name="copy[state].icon" />
    <h3>{{ title ?? copy[state].title }}</h3>
    <p>{{ description ?? copy[state].description }}</p>
    <button v-if="state === 'error'" type="button" @click="emit('retry')">重新分析</button>
    <slot />
  </section>
</template>
```

`ResearchPageShell` 提供 `eyebrow`、`title`、`description`、`status`、`actions` 和默认插槽；`ResearchPanel` 提供 `title`、`subtitle`、`tone`、`actions` 和默认插槽。两者不导入 Store 或 Service。

- [ ] **步骤 6：迁移现有 UI 与科研组件**

保留公开 props/emit；用 `ResearchIcon` 替代 Emoji，用 `var(--research-*)` 替代所有主题色。`AgentCard` 增加可选 `duration`，状态扩展为 `running | completed | idle | error`；`Timeline` 节点使用 SVG 与 CSS 状态，不再输出字符图标。

- [ ] **步骤 7：运行 122 个测试并确认绿灯**

```powershell
npx vitest run tests/unit/research-icon.dom.test.ts tests/unit/research-primitives.dom.test.ts --config vitest.config.ts
```

预期：122 passed。

- [ ] **步骤 8：提交图标与原语**

```powershell
git add desktop/src/renderer/src/components desktop/tests/unit/research-icon.dom.test.ts desktop/tests/unit/research-primitives.dom.test.ts
git commit -m "feat(desktop): add premium research UI primitives"
```

---

## 任务 4：升级主布局、默认路由与科研首页

**文件：**

- 修改：`desktop/src/renderer/src/router/index.ts`
- 修改：`desktop/src/renderer/src/layouts/MainLayout.vue`
- 修改：`desktop/src/renderer/src/layouts/Sidebar.vue`
- 修改：`desktop/src/renderer/src/layouts/HeaderBar.vue`
- 修改：`desktop/src/renderer/src/pages/research/Dashboard.vue`
- 修改：`desktop/src/renderer/src/pages/research/ProjectWorkspace.vue`
- 创建：`desktop/tests/unit/research-layout.dom.test.ts`

- [ ] **步骤 1：编写 46 个布局与路由红灯测试**

覆盖 10 个导航标签、10 个路由目标、5 个收起/持久化行为、5 个顶部栏区域、6 个默认路由/旧路由兼容、5 个 1440/1920 样式契约、5 个焦点/ARIA 契约。

```ts
// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest'
import Sidebar from '@/layouts/Sidebar.vue'
import { mountResearch } from '../helpers/mount-research'
import { RESEARCH_NAV } from '../fixtures/research-ui'

describe('科研导航', () => {
  it.each(RESEARCH_NAV)('%s 指向 %s', async (label, routeName) => {
    const { wrapper } = await mountResearch(Sidebar)
    const link = wrapper.findAll('a').find(node => node.text().includes(label))
    expect(link?.attributes('href')).toContain(String(routeName).replace('research-', ''))
  })
  it('收起状态写入本地存储', async () => {
    const { wrapper } = await mountResearch(Sidebar)
    await wrapper.get('[aria-label="收起导航栏"]').trigger('click')
    expect(localStorage.getItem('research-sidebar-collapsed')).toBe('1')
  })
})
```

- [ ] **步骤 2：运行测试确认红灯**

```powershell
npx vitest run tests/unit/research-layout.dom.test.ts --config vitest.config.ts
```

预期：FAIL，缺少科研首页导航、收起状态和新顶部栏。

- [ ] **步骤 3：实现默认科研路由与兼容入口**

路由变更：

```ts
{ path: '/', redirect: { name: 'research-dashboard' } },
{ path: '/home', name: 'home', redirect: { name: 'research-dashboard' } }
```

保留 `{ path: '/dashboard', name: 'dashboard', ... }`，不得删除旧视图。

- [ ] **步骤 4：实现侧栏收起与导航**

核心状态：

```ts
const collapsed = ref(localStorage.getItem('research-sidebar-collapsed') === '1')
function toggleCollapsed(): void {
  collapsed.value = !collapsed.value
  localStorage.setItem('research-sidebar-collapsed', collapsed.value ? '1' : '0')
}
```

侧栏使用 10 个中文导航项和 `ResearchIcon`；展开 232px、收起 76px；当前研究卡读取 `useProjectStore().currentProject`；选中态以背景、文字和左侧指示条三重表达。

- [ ] **步骤 5：升级顶部栏**

顶部栏读取 `useProjectStore` 和 `useWorkflowStore`，展示当前项目、AI 状态、通知与用户区。AI 状态从 `workflowStore.runningTasks.length` 与 `errors.length` 派生，不新增业务字段。退出操作放入用户区域，保留现有 `authStore.logout()`。

- [ ] **步骤 6：升级科研首页与项目空间**

`Dashboard.vue` 保持四个现有 Store 和 `Promise.all` 加载；新增项目 Hero、四指标、AI 活动与洞察区，并用 `datasetStore.isLoading`、`knowledgeStore.isLoading`、`manuscriptStore.isLoading` 驱动 `ResearchState`。

`ProjectWorkspace.vue` 标签固定为：

```ts
const tabs = [
  { id: 'overview', label: '项目概览', icon: 'home' },
  { id: 'literature', label: '文献', icon: 'literature' },
  { id: 'experiment', label: '实验', icon: 'experiment' },
  { id: 'data', label: '数据', icon: 'data' },
  { id: 'model', label: '模型', icon: 'model' },
  { id: 'manuscript', label: '论文', icon: 'manuscript' }
] as const
```

标签使用 button、`role="tab"`、`aria-selected`，切换只改变本地 `activeTab`，不得清空 Store。

- [ ] **步骤 7：运行布局与相关旧契约**

```powershell
npx vitest run tests/unit/research-layout.dom.test.ts tests/unit/research-os-frontend.test.ts tests/unit/research-os-integration.test.ts --config vitest.config.ts
```

预期：布局 46 passed；两个旧文件中与后续页面相关的红灯可以保留，但侧栏、路由、首页相关断言必须通过。

- [ ] **步骤 8：提交外壳与首页**

```powershell
git add desktop/src/renderer/src/router desktop/src/renderer/src/layouts desktop/src/renderer/src/pages/research/Dashboard.vue desktop/src/renderer/src/pages/research/ProjectWorkspace.vue desktop/tests/unit/research-layout.dom.test.ts
git commit -m "feat(desktop): build premium research workspace shell"
```

---

## 任务 5：实现 Agent 中心与科研助手的高级可观察界面

**文件：**

- 修改：`desktop/src/renderer/src/pages/research/AgentCenter.vue`
- 修改：`desktop/src/renderer/src/pages/research/Assistant.vue`
- 修改：`desktop/src/renderer/src/components/research/AgentCard.vue`
- 修改：`desktop/src/renderer/src/components/research/Timeline.vue`
- 创建：`desktop/tests/unit/research-pages.dom.test.ts`（先加入 Agent 与 Assistant 的 26 个实例）

- [ ] **步骤 1：编写 Agent 页面 26 个红灯测试**

覆盖 5 个时间线阶段、5 个智能体、4 种节点状态、工具调用输入/输出/结果、运行按钮、回车提交、禁用态、错误保留、中文标签和展示组件隔离。

```ts
it.each(['理解科研问题', '检索知识与证据', '分析降解机制', '设计实验参数', '生成科研报告'])('%s 节点存在', async (label) => {
  const { wrapper } = await mountResearch(AgentCenter)
  expect(wrapper.text()).toContain(label)
})

it('科研任务仍调用现有 agentStore.runResearch', async () => {
  const { wrapper } = await mountResearch(AgentCenter)
  const store = useAgentStore()
  const run = vi.spyOn(store, 'runResearch').mockResolvedValue(undefined)
  await wrapper.get('input').setValue('分析 TC 降解动力学')
  await wrapper.get('form').trigger('submit')
  expect(run).toHaveBeenCalledWith('分析 TC 降解动力学')
})
```

- [ ] **步骤 2：运行聚焦测试确认红灯**

```powershell
npx vitest run tests/unit/research-pages.dom.test.ts -t "Agent|科研助手" --config vitest.config.ts
```

预期：FAIL，缺少三层可观察结构和中文智能体名称。

- [ ] **步骤 3：实现 Agent 中心三层结构**

页面继续使用 `useAgentStore` 与 `useWorkflowStore`：

- `agentStore.events` 映射为思考时间线；为空时显示五阶段等待结构。
- `workflowStore.tasks` 映射为智能体任务；`agentStore.isLoading` 驱动当前实验智能体运行态。
- `agentStore.designResult` 显示问题、假设、变量和模型结果。
- 最近一条 `agentStore.messages[].toolCalls` 映射到工具执行面板。
- 错误使用 `workflowStore.errors`，保留已完成事件并提供 `clearErrors` 与重新运行入口。

禁止修改 Store 或 Service 接口，禁止把高保真稿中的示例耗时伪装为真实值。无耗时时显示 `—`。

- [ ] **步骤 4：升级科研助手三栏**

保留会话选择、消息发送、引用和证据数据流。左栏使用科研会话状态；中栏强化消息、研究轨迹和工具结果；右栏固定显示引用与证据。发送中统一显示 `AI 正在分析...`；无选中会话显示 `暂无科研数据`。

- [ ] **步骤 5：运行 26 个页面测试并确认绿灯**

```powershell
npx vitest run tests/unit/research-pages.dom.test.ts -t "Agent|科研助手" --config vitest.config.ts
```

预期：26 passed。

- [ ] **步骤 6：提交 Agent 体验**

```powershell
git add desktop/src/renderer/src/pages/research/AgentCenter.vue desktop/src/renderer/src/pages/research/Assistant.vue desktop/src/renderer/src/components/research/AgentCard.vue desktop/src/renderer/src/components/research/Timeline.vue desktop/tests/unit/research-pages.dom.test.ts
git commit -m "feat(desktop): visualize scientific agent execution"
```

---

## 任务 6：升级文献证据与实验设计工作区

**文件：**

- 修改：`desktop/src/renderer/src/pages/research/Literature.vue`
- 修改：`desktop/src/renderer/src/pages/research/Experiment.vue`
- 修改：`desktop/src/renderer/src/components/research/CitationCard.vue`
- 修改：`desktop/src/renderer/src/components/research/EvidenceCard.vue`
- 修改：`desktop/tests/unit/research-pages.dom.test.ts`（加入 22 个文献与 22 个实验实例）

- [ ] **步骤 1：编写 44 个工作区红灯测试**

文献 22 个：论文题名、作者、年份、相关度、证据等级、引用位置、搜索、选中、分析、AI 摘要、加载/空/错、键盘和弹层。实验 22 个：假设、变量、分组、指标、参数标签、生成建议、运行/禁用、三态、三栏和 1440px 合约。

```ts
it('文献选择仍调用现有 Store action', async () => {
  const { wrapper } = await mountResearch(Literature)
  const store = useKnowledgeStore()
  await store.loadDocuments()
  const select = vi.spyOn(store, 'selectDocument')
  await wrapper.find('[data-document-id="d1"]').trigger('click')
  expect(select).toHaveBeenCalledWith('d1')
})

it.each(['研究假设', '实验变量', 'AI 实验建议'])('实验工作区显示 %s', async (label) => {
  const { wrapper } = await mountResearch(Experiment)
  expect(wrapper.text()).toContain(label)
})
```

- [ ] **步骤 2：运行聚焦测试确认红灯**

```powershell
npx vitest run tests/unit/research-pages.dom.test.ts -t "文献|实验" --config vitest.config.ts
```

预期：FAIL，缺少证据等级、引用位置、AI 建议栏和新结构。

- [ ] **步骤 3：实现文献工作区**

左栏保留文件夹与搜索，中间显示稳定论文详情，右栏显示论文卡列表与 AI 摘要。证据等级从现有 `PaperAssessment` 的三项得分平均值计算：

```ts
function evidenceStars(documentId: string): number {
  const item = assessment(documentId)
  if (!item) return 0
  const average = (item.reliabilityScore + item.evidenceScore + item.methodologyScore) / 3
  return Math.max(1, Math.min(5, Math.round(average * 5)))
}
```

引用位置在现有接口没有页码时明确显示 `原文定位待提取`，不得伪造“第 3 页图 2”。AI 摘要继续调用 `literatureService.summarizePaper`。

- [ ] **步骤 4：实现实验工作区**

三栏固定为假设、变量/分组、AI 建议。变量可编辑视觉状态以 input 展示当前范围和单位，但本阶段不自动写回 Service；只有用户确认保存时才调用既有 `experimentService.updateDesign`。AI 生成继续调用 `generateHypotheses`，生成结果以紫色建议卡显示。

- [ ] **步骤 5：运行 44 个测试并确认绿灯**

```powershell
npx vitest run tests/unit/research-pages.dom.test.ts -t "文献|实验" --config vitest.config.ts
```

预期：44 passed。

- [ ] **步骤 6：提交文献与实验工作区**

```powershell
git add desktop/src/renderer/src/pages/research/Literature.vue desktop/src/renderer/src/pages/research/Experiment.vue desktop/src/renderer/src/components/research/CitationCard.vue desktop/src/renderer/src/components/research/EvidenceCard.vue desktop/tests/unit/research-pages.dom.test.ts
git commit -m "feat(desktop): refine evidence and experiment workspaces"
```

---

## 任务 7：实现 ECharts 科学图表与数据分析工作区

**文件：**

- 创建：`desktop/src/renderer/src/utils/scientific-chart.ts`
- 创建：`desktop/src/renderer/src/components/research/ScientificChart.vue`
- 修改：`desktop/src/renderer/src/components/research/ChartPanel.vue`
- 修改：`desktop/src/renderer/src/pages/research/DataAnalysis.vue`
- 创建：`desktop/tests/unit/scientific-chart.dom.test.ts`
- 修改：`desktop/tests/unit/research-pages.dom.test.ts`（加入 18 个数据分析实例）

- [ ] **步骤 1：编写 34 个图表红灯测试**

纯函数 20 个：模型名翻译、k 参数、预测点、残差上下界、R²、空模型、非法数值、颜色与中文 tooltip。组件 14 个：初始化、setOption、ResizeObserver、resize、卸载 dispose、空状态、aria label 和配置更新。

```ts
// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'

const builderPath = resolve(__dirname, '../../src/renderer/src/utils/scientific-chart.ts')

describe('buildKineticFitOption', () => {
  it('构建器文件存在', () => expect(existsSync(builderPath)).toBe(true))
  it('从一级动力学 k 生成归一化预测曲线', async () => {
    if (!existsSync(builderPath)) return
    const { buildKineticFitOption } = await import('@/utils/scientific-chart')
    const option = buildKineticFitOption({
      model: 'first-order', parameters: { k: 0.0243 }, rSquared: 0.9887, residualError: 0.0211
    })
    const series = option.series as Array<{ name: string; data: Array<[number, number]> }>
    expect(series[0].name).toBe('模型预测曲线')
    expect(series[0].data[0]).toEqual([0, 1])
    expect(series[0].data.at(-1)?.[1]).toBeLessThan(1)
  })
  it('残差带不冒充置信区间', async () => {
    if (!existsSync(builderPath)) return
    const { buildKineticFitOption } = await import('@/utils/scientific-chart')
    expect(JSON.stringify(buildKineticFitOption({
      model: 'first-order', parameters: { k: 0.1 }, rSquared: 0.9, residualError: 0.02
    }))).toContain('残差范围')
  })
})
```

- [ ] **步骤 2：运行测试确认红灯**

```powershell
npx vitest run tests/unit/scientific-chart.dom.test.ts --config vitest.config.ts
```

预期：FAIL，缺少图表构建器和组件。

- [ ] **步骤 3：实现科学图表配置构建器**

`buildKineticFitOption(model)` 从现有 `ModelFitResult.parameters.k` 计算 `C/C₀ = exp(-kt)`；用 `residualError` 生成并明确标记为“残差范围”，不称为统计置信区间。R² 在模型卡显示为“拟合可信度”。非法或缺失 k 时返回空 series 和中文说明。

核心返回结构：

```ts
return {
  aria: { enabled: true, description: `动力学拟合图，模型 ${modelLabel}，R² ${model.rSquared.toFixed(3)}` },
  animationDuration: 420,
  color: ['#4263df', '#7654d8', '#1a9b72'],
  tooltip: { trigger: 'axis', valueFormatter: (value: number) => value.toFixed(3) },
  legend: { data: ['模型预测曲线', '残差范围'] },
  xAxis: { type: 'value', name: '时间（分钟）' },
  yAxis: { type: 'value', name: '归一化浓度 C/C₀', min: 0, max: 1 },
  series
}
```

- [ ] **步骤 4：实现 ECharts 生命周期封装**

`ScientificChart.vue` 接口：

```vue
<script setup lang="ts">
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent, AriaComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { EChartsOption } from 'echarts'
import type { EChartsType } from 'echarts/core'

echarts.use([LineChart, GridComponent, LegendComponent, TooltipComponent, AriaComponent, CanvasRenderer])
const props = defineProps<{ option: EChartsOption; ariaLabel: string; empty?: boolean }>()
const host = ref<HTMLDivElement | null>(null)
let chart: EChartsType | null = null
let observer: ResizeObserver | null = null

onMounted(() => {
  if (!host.value || props.empty) return
  chart = echarts.init(host.value)
  chart.setOption(props.option)
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(host.value)
})
watch(() => props.option, option => chart?.setOption(option, { notMerge: true }), { deep: true })
onBeforeUnmount(() => { observer?.disconnect(); chart?.dispose() })
</script>

<template><div ref="host" class="scientific-chart" role="img" :aria-label="ariaLabel" /></template>
```

- [ ] **步骤 5：升级数据分析页面**

使用 `datasetStore.report`、`quality`、`statistics`、`models`、`importance`、`conclusions` 和 `figures`；不使用页面硬编码 `importanceData`。页面展示数据质量、真实变量重要性、模型卡、图表和 AI 解释。加载、空和错误使用 `ResearchState`。

- [ ] **步骤 6：运行 52 个图表与页面测试并确认绿灯**

```powershell
npx vitest run tests/unit/scientific-chart.dom.test.ts tests/unit/research-pages.dom.test.ts -t "图表|数据分析" --config vitest.config.ts
```

预期：52 passed。

- [ ] **步骤 7：提交图表与分析体验**

```powershell
git add desktop/src/renderer/src/utils/scientific-chart.ts desktop/src/renderer/src/components/research/ScientificChart.vue desktop/src/renderer/src/components/research/ChartPanel.vue desktop/src/renderer/src/pages/research/DataAnalysis.vue desktop/tests/unit/scientific-chart.dom.test.ts desktop/tests/unit/research-pages.dom.test.ts
git commit -m "feat(desktop): add scientific chart analysis experience"
```

---

## 任务 8：升级论文、知识图谱与系统设置

**文件：**

- 修改：`desktop/src/renderer/src/pages/research/Manuscript.vue`
- 修改：`desktop/src/renderer/src/pages/research/KnowledgeGraph.vue`
- 修改：`desktop/src/renderer/src/pages/research/Settings.vue`
- 修改：`desktop/tests/unit/research-pages.dom.test.ts`（加入 30 个实例）

- [ ] **步骤 1：编写 30 个页面红灯测试**

论文 14 个：结构树、活动节、正文、生成、字数、引用、语言/逻辑/创新/引用审阅、问题、禁用、加载与空。知识图谱 8 个：实体、关系、SVG、语义色、空、键盘和中文。设置 8 个：四分组、提供商状态、表单焦点、危险操作隔离和中文。

```ts
it.each(['语言', '逻辑', '创新', '引用'])('SCI 审阅包含 %s 维度', async (label) => {
  const { wrapper } = await mountResearch(Manuscript)
  expect(wrapper.text()).toContain(label)
})

it('知识图谱节点不再输出 Emoji', async () => {
  const { wrapper } = await mountResearch(KnowledgeGraph)
  expect(wrapper.text()).not.toMatch(/[🔬⚙️📊📄🧪⚡]/u)
})
```

- [ ] **步骤 2：运行聚焦测试确认红灯**

```powershell
npx vitest run tests/unit/research-pages.dom.test.ts -t "论文|知识图谱|设置" --config vitest.config.ts
```

预期：FAIL，缺少新审阅维度名称、图标系统和设置分组布局。

- [ ] **步骤 3：实现论文三栏工作区**

保留 `store.sections`、`activeSection`、`issues`、`highlights` 和 `generateContent`。审阅维度根据现有数据诚实呈现：语言与逻辑从问题类型聚合，创新性显示“待进一步评估”，引用显示有引用节数/总节数；不得硬编码 82/78/85/75 冒充真实评分。

- [ ] **步骤 4：升级知识图谱与设置**

知识图谱保留当前实体/关系数据和 SVG，节点图标使用 `ResearchIcon`，实体类型使用统一语义色。设置页改为左侧分组导航、右侧表单；不改变模型配置和 API 服务接口，不把密钥写入新位置。

- [ ] **步骤 5：运行 30 个测试并确认绿灯**

```powershell
npx vitest run tests/unit/research-pages.dom.test.ts -t "论文|知识图谱|设置" --config vitest.config.ts
```

预期：30 passed。

- [ ] **步骤 6：提交剩余科研页面**

```powershell
git add desktop/src/renderer/src/pages/research/Manuscript.vue desktop/src/renderer/src/pages/research/KnowledgeGraph.vue desktop/src/renderer/src/pages/research/Settings.vue desktop/tests/unit/research-pages.dom.test.ts
git commit -m "feat(desktop): polish writing graph and settings workspaces"
```

---

## 任务 9：完成 370 个新增测试、隔离守卫与响应式验收

**文件：**

- 修改：`desktop/tests/unit/research-design-tokens.dom.test.ts`
- 修改：`desktop/tests/unit/research-icon.dom.test.ts`
- 修改：`desktop/tests/unit/research-primitives.dom.test.ts`
- 修改：`desktop/tests/unit/research-layout.dom.test.ts`
- 修改：`desktop/tests/unit/research-pages.dom.test.ts`
- 修改：`desktop/tests/unit/scientific-chart.dom.test.ts`
- 修改：`desktop/tests/unit/research-os-frontend.test.ts`
- 修改：`desktop/tests/unit/research-os-integration.test.ts`

- [ ] **步骤 1：核对新增测试实例总数**

目标矩阵：

```text
research-design-tokens.dom.test.ts  72
research-icon.dom.test.ts           48
research-primitives.dom.test.ts     74
research-layout.dom.test.ts         46
research-pages.dom.test.ts          96
scientific-chart.dom.test.ts        34
新增合计                            370
```

用 Vitest JSON 报告确认这六个文件合计不少于 370 个 tests；不得用空断言或重复名字凑数。

- [ ] **步骤 2：加入隔离和主题硬编码守卫**

在 `research-pages.dom.test.ts` 加入：

```ts
it.each(presentationalComponents)('%s 不越过 Store/Service 边界', (file) => {
  const content = readFileSync(resolve(rendererRoot, file), 'utf8')
  expect(content).not.toMatch(/stores\/research|services\/research|window\.api/)
})

it.each(researchVueFiles)('%s 不新增旧主题主色', (file) => {
  const content = readFileSync(resolve(rendererRoot, file), 'utf8')
  expect(content).not.toMatch(/#f97316|#0f172a|#020617/i)
})

it.each(researchVueFiles)('%s 的用户界面不使用 Emoji 导航图标', (file) => {
  const content = readFileSync(resolve(rendererRoot, file), 'utf8')
  expect(content).not.toMatch(/[💬📁📚🧪📊📝🔗🤖⚙️🔬⚡]/u)
})
```

- [ ] **步骤 3：加入 1440 与 1920 响应式契约**

断言科研页面根元素含 `min-width: 0`、网格使用 `minmax(0, 1fr)`，三栏辅助区使用令牌宽度，且样式包含 `@media (min-width: 1720px)` 与 `@media (max-width: 1480px)`。禁止在根页面使用超过内容区的固定像素宽度。

- [ ] **步骤 4：运行六个新增测试文件**

```powershell
npx vitest run tests/unit/research-design-tokens.dom.test.ts tests/unit/research-icon.dom.test.ts tests/unit/research-primitives.dom.test.ts tests/unit/research-layout.dom.test.ts tests/unit/research-pages.dom.test.ts tests/unit/scientific-chart.dom.test.ts --config vitest.config.ts
```

预期：370+ passed，0 failed。

- [ ] **步骤 5：运行全部单元测试**

```powershell
npm run test:unit
```

预期：原有 5980 个测试与新增 370+ 测试全部执行，0 failed；原先 37 条旧红灯已迁移。

- [ ] **步骤 6：提交测试收口**

```powershell
git add desktop/tests desktop/vitest.config.ts
git commit -m "test(desktop): cover visual pro research workflows"
```

---

## 任务 10：类型、构建、隔离与桌面视觉验收

**文件：**

- 创建：`desktop/docs/ui-design/phase8-i3-b-verification.md`

- [ ] **步骤 1：运行 Node TypeScript 检查**

```powershell
npx tsc --noEmit -p tsconfig.node.json
```

预期：exit 0，0 errors。

- [ ] **步骤 2：运行 Vue TypeScript 检查**

```powershell
npx vue-tsc --noEmit -p tsconfig.web.json
```

预期：exit 0，0 errors。

- [ ] **步骤 3：运行完整单元测试**

```powershell
npm run test:unit
```

预期：0 failed，新增测试不少于 370。

- [ ] **步骤 4：运行 Electron 构建**

```powershell
npm run build
```

预期：exit 0；生成 `out/main`、`out/preload`、`out/renderer`。

- [ ] **步骤 5：验证严格隔离**

从仓库根运行：

```powershell
git diff -- web app backend
```

预期：0 行。

再运行：

```powershell
git status --short
```

预期：本阶段所有已跟踪变更都位于 `desktop/**`；保留并忽略会话开始前已存在的 `.agents/skills/verify/` 与 `tmp/` 未跟踪项。

- [ ] **步骤 6：启动桌面应用并做两种尺寸视觉验收**

运行：

```powershell
npm run dev
```

在 Electron 窗口依次验证：

1. 1440×900：侧栏展开/收起、科研首页、Agent 中心、文献、实验、数据、论文，无横向溢出。
2. 1920×1080：内容网格与留白扩大，正文与侧栏不过度拉伸。
3. 加载、空、错误三态文案与操作可见。
4. Agent 完成、运行、等待、错误四态可辨识。
5. ECharts 缩放后重绘，切换页面后无控制台错误。
6. 键盘 Tab 顺序、焦点环、侧栏按钮、标签页和错误重试正常。
7. 系统启用“减少动态效果”后，无连续呼吸或位移动画。

- [ ] **步骤 7：写入验证记录**

`phase8-i3-b-verification.md` 必须记录日期、命令、退出码、测试总数、新增测试数、两种窗口尺寸、隔离输出与已知限制。没有通过的项目明确写失败证据，不写“应该通过”。

- [ ] **步骤 8：提交最终收口**

先运行：

```powershell
git diff --check
```

预期：0 输出，exit 0。

然后：

```powershell
git add desktop/docs/ui-design/phase8-i3-b-verification.md
git commit -m "Phase 8-I3-B Scientific Research OS Visual Pro Upgrade"
```

最终 HEAD 的提交信息必须与用户指定内容完全一致。

---

## 规格覆盖自检

- 全局令牌：任务 2。
- 应用外壳、默认科研首页、收起侧栏、顶部状态：任务 4。
- Dashboard Pro 与项目工作区：任务 4。
- Agent 中心与工具执行可视化：任务 5。
- 文献与实验工作区：任务 6。
- ECharts、拟合曲线、残差范围、R² 与 AI 解释：任务 7。
- 论文、知识图谱、设置：任务 8。
- 加载、空、错误、动效、减少动态效果、键盘与中文：任务 2、3、9。
- 1440×900 与 1920×1080：任务 4、9、10。
- 新增不少于 300 个测试：任务 3、4、5、6、7、8、9，共 370+。
- 单测、TypeScript、Vue 类型、构建与隔离：任务 10。
- 所有生产变更仅在 `desktop/**`：任务 10 隔离守卫。
