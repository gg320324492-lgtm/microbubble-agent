// @vitest-environment happy-dom
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router, type RouteRecordRaw } from 'vue-router'
import HeaderBar from '@/layouts/HeaderBar.vue'
import Sidebar from '@/layouts/Sidebar.vue'
import Dashboard from '@/pages/research/Dashboard.vue'
import ProjectWorkspace from '@/pages/research/ProjectWorkspace.vue'
import { useAuthStore } from '@/stores/auth'
import { useDatasetStore } from '@/stores/research/dataset.store'
import { useExperimentStore } from '@/stores/research/experiment.store'
import { useKnowledgeStore } from '@/stores/research/knowledge.store'
import { useManuscriptStore } from '@/stores/research/manuscript.store'
import { useProjectStore } from '@/stores/research/project.store'
import { useWorkflowStore } from '@/stores/research/workflow.store'
import { useUserStore } from '@/stores/user'
import { router as applicationRouter } from '@/router'
import { RESEARCH_NAV } from '../fixtures/research-ui'

const rendererRoot = resolve(process.cwd(), 'src/renderer/src')
const routeTargets = {
  'research-dashboard': '/research/dashboard',
  'research-assistant': '/research/assistant',
  'research-project': '/research/project',
  'research-literature': '/research/literature',
  'research-experiment': '/research/experiment',
  'research-data-analysis': '/research/data-analysis',
  'research-manuscript': '/research/manuscript',
  'research-knowledge-graph': '/research/knowledge-graph',
  'research-agent-center': '/research/agent-center',
  'research-settings': '/research/settings'
} as const

const dummy = { template: '<div />' }
const researchRoutes: RouteRecordRaw[] = RESEARCH_NAV.map(([, name]) => ({
  path: routeTargets[name],
  name,
  component: dummy,
  meta: { title: '科研页面' }
}))

async function mountSidebar(initialPath = '/research/dashboard'): Promise<{ wrapper: VueWrapper; router: Router }> {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({ history: createMemoryHistory(), routes: researchRoutes })
  await router.push(initialPath)
  await router.isReady()
  const wrapper = mount(Sidebar, { global: { plugins: [pinia, router] } })
  return { wrapper, router }
}

async function mountHeader(): Promise<{ wrapper: VueWrapper; router: Router }> {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/research/dashboard', name: 'research-dashboard', component: dummy, meta: { title: '科研首页' } },
      { path: '/login', name: 'login', component: dummy }
    ]
  })
  await router.push('/research/dashboard')
  await router.isReady()

  const authStore = useAuthStore()
  authStore.hasSession = true
  authStore.expiresAt = Date.now() + 60_000
  useUserStore().setProfile({
    id: 7,
    name: '测试研究员',
    role: 'researcher',
    grade: null,
    research_area: '环境科学',
    email: null,
    phone: null,
    bio: null,
    avatar: null,
    is_active: true
  })

  const wrapper = mount(HeaderBar, { attachTo: document.body, global: { plugins: [pinia, router] } })
  return { wrapper, router }
}

async function mountWorkspace(): Promise<VueWrapper> {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(ProjectWorkspace, { attachTo: document.body, global: { plugins: [pinia] } })
}

beforeEach(() => {
  document.body.innerHTML = ''
  localStorage.clear()
  vi.restoreAllMocks()
})

describe('科研导航标签（10）', () => {
  it.each(RESEARCH_NAV)('显示“%s”且使用 %s 路由的科研图标', async (label, routeName) => {
    const { wrapper } = await mountSidebar()
    const link = wrapper.get(`[data-nav="${routeName}"]`)
    expect(link.text()).toContain(label)
    expect(link.find('svg.research-icon').exists()).toBe(true)
    expect(link.text()).not.toMatch(/[💬📁📚🧪📊📝🔗🤖⚙️🔬]/u)
  })
})

describe('科研导航目标（10）', () => {
  it.each(RESEARCH_NAV)('点击“%s”进入命名路由 %s', async (label, routeName) => {
    const { wrapper, router } = await mountSidebar()
    const link = wrapper.get(`[data-nav="${routeName}"]`)
    expect(link.attributes('href')).toBe(routeTargets[routeName])
    await link.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe(routeName)
    expect(router.currentRoute.value.path).toBe(routeTargets[routeName])
  })
})

describe('侧栏收起与持久化（5）', () => {
  it('从本地存储恢复收起状态', async () => {
    localStorage.setItem('research-sidebar-collapsed', '1')
    const { wrapper } = await mountSidebar()
    expect(wrapper.get('aside').classes()).toContain('is-collapsed')
  })

  it('点击收起按钮把 1 写入准确的本地存储键', async () => {
    const { wrapper } = await mountSidebar()
    await wrapper.get('[aria-label="收起导航栏"]').trigger('click')
    expect(localStorage.getItem('research-sidebar-collapsed')).toBe('1')
  })

  it('再次展开把 0 写入本地存储', async () => {
    localStorage.setItem('research-sidebar-collapsed', '1')
    const { wrapper } = await mountSidebar()
    await wrapper.get('[aria-label="展开导航栏"]').trigger('click')
    expect(localStorage.getItem('research-sidebar-collapsed')).toBe('0')
    expect(wrapper.get('aside').classes()).not.toContain('is-collapsed')
  })

  it('收起后控制按钮的可读名称切换为展开导航栏', async () => {
    const { wrapper } = await mountSidebar()
    await wrapper.get('[aria-label="收起导航栏"]').trigger('click')
    expect(wrapper.get('[data-testid="sidebar-toggle"]').attributes('aria-label')).toBe('展开导航栏')
  })

  it('收起后隐藏当前研究卡正文并保留项目数据', async () => {
    const { wrapper } = await mountSidebar()
    const projectName = useProjectStore().currentProject.name
    expect(wrapper.get('[data-testid="current-research"]').text()).toContain(projectName)
    await wrapper.get('[aria-label="收起导航栏"]').trigger('click')
    expect(wrapper.get('[data-testid="current-research"]').attributes('aria-hidden')).toBe('true')
    expect(useProjectStore().currentProject.name).toBe(projectName)
  })
})

describe('顶部栏区域（5）', () => {
  it('显示当前页面层级和中文标题', async () => {
    const { wrapper } = await mountHeader()
    expect(wrapper.get('[data-testid="header-context"]').text()).toContain('科研工作台')
    expect(wrapper.get('h2').text()).toBe('科研首页')
  })

  it('显示 Store 中的当前项目', async () => {
    const { wrapper } = await mountHeader()
    expect(wrapper.get('[data-testid="header-project"]').text()).toContain(useProjectStore().currentProject.name)
  })

  it('从 runningTasks 派生 AI 运行状态', async () => {
    const { wrapper } = await mountHeader()
    useWorkflowStore().addTask({ id: 'analysis-1', type: 'analysis', label: '拟合模型', status: 'running' })
    await wrapper.vm.$nextTick()
    expect(wrapper.get('[data-testid="header-ai-status"]').text()).toContain('1 项任务运行中')
  })

  it('从 errors 派生 AI 异常状态而不伪造数量', async () => {
    const { wrapper } = await mountHeader()
    useWorkflowStore().addError('模型服务不可用')
    await wrapper.vm.$nextTick()
    expect(wrapper.get('[data-testid="header-ai-status"]').text()).toContain('1 项异常')
  })

  it('通知空态可切换、Escape 与关闭按钮可关闭，并保留真实退出动作', async () => {
    const { wrapper, router } = await mountHeader()
    const logout = vi.spyOn(useAuthStore(), 'logout').mockResolvedValue()
    const notification = wrapper.get('[data-testid="notification-button"]')
    expect(notification.attributes('aria-label')).toBe('查看科研通知')
    expect(notification.attributes('aria-expanded')).toBe('false')
    await notification.trigger('click')
    expect(notification.attributes('aria-expanded')).toBe('true')
    expect(notification.attributes('aria-controls')).toBe('research-notification-popover')
    const popover = wrapper.get('#research-notification-popover')
    expect(popover.attributes('role')).toBe('status')
    expect(popover.attributes('aria-live')).toBe('polite')
    expect(popover.text()).toContain('暂无科研通知')
    await wrapper.get('#research-notification-popover').trigger('keydown', { key: 'Escape' })
    expect(wrapper.find('#research-notification-popover').exists()).toBe(false)
    await notification.trigger('click')
    await wrapper.get('[data-testid="notification-close"]').trigger('click')
    expect(wrapper.find('#research-notification-popover').exists()).toBe(false)
    await wrapper.get('[data-testid="user-menu-button"]').trigger('click')
    await wrapper.get('[data-testid="logout-button"]').trigger('click')
    await flushPromises()
    expect(logout).toHaveBeenCalledOnce()
    expect(router.currentRoute.value.name).toBe('login')
  })
})

describe('默认与旧路由兼容（6）', () => {
  it('根路径按命名路由重定向到科研首页', () => {
    const route = applicationRouter.getRoutes().find(item => item.path === '/')
    expect(route?.redirect).toEqual({ name: 'research-dashboard' })
  })

  it('/home 保留 home 名称并按命名路由重定向科研首页', () => {
    const route = applicationRouter.getRoutes().find(item => item.path === '/home')
    expect(route?.name).toBe('home')
    expect(route?.redirect).toEqual({ name: 'research-dashboard' })
  })

  it('/research/dashboard 保持命名科研首页和认证元信息', () => {
    const route = applicationRouter.getRoutes().find(item => item.path === '/research/dashboard')
    expect(route?.name).toBe('research-dashboard')
    expect(route?.meta.requiresAuth).toBe(true)
  })

  it('/dashboard 旧视图与 dashboard 名称完整保留', () => {
    const route = applicationRouter.getRoutes().find(item => item.path === '/dashboard')
    expect(route?.name).toBe('dashboard')
    expect(typeof route?.components?.default).toBe('function')
  })

  it('旧入口完整保留且 Electron 继续使用 hash history', () => {
    const names = applicationRouter.getRoutes().map(route => route.name)
    expect(names).toEqual(expect.arrayContaining(['knowledge', 'knowledge-detail', 'chat', 'settings-models']))
    expect(applicationRouter.options.history.createHref('/research/dashboard')).toContain('#/research/dashboard')
  })

  it('已认证用户访问登录页由真实守卫导向科研首页', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const authStore = useAuthStore()
    authStore.restoreAttempted = true
    authStore.hasSession = true
    authStore.expiresAt = Date.now() + 60_000
    await applicationRouter.push('/login')
    await flushPromises()
    expect(applicationRouter.currentRoute.value.name).toBe('research-dashboard')
  })
})

describe('1440 与 1920 桌面契约（6）', () => {
  it('展开侧栏按纵向组织品牌、导航与研究状态', () => {
    const source = readFileSync(resolve(rendererRoot, 'layouts/Sidebar.vue'), 'utf8')
    expect(source).toMatch(/\.sidebar\s*\{[^}]*flex-direction:\s*column/s)
  })

  it('侧栏消费 232 与 76 像素设计令牌', () => {
    const source = readFileSync(resolve(rendererRoot, 'layouts/Sidebar.vue'), 'utf8')
    expect(source).toContain('var(--research-sidebar-width)')
    expect(source).toContain('var(--research-sidebar-collapsed-width)')
  })

  it('顶部栏消费 64 像素高度令牌', () => {
    const source = readFileSync(resolve(rendererRoot, 'layouts/HeaderBar.vue'), 'utf8')
    expect(source).toContain('height: var(--research-header-height)')
  })

  it('主内容允许网格收缩且不会产生外层横向溢出', () => {
    const source = readFileSync(resolve(rendererRoot, 'layouts/MainLayout.vue'), 'utf8')
    expect(source).toMatch(/main-layout__body[\s\S]*min-width:\s*0/)
    expect(source).toMatch(/main-layout__content[\s\S]*overflow-x:\s*hidden/)
  })

  it('科研首页响应式契约下拒绝英文异常并提供中文重试', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const source = readFileSync(resolve(rendererRoot, 'pages/research/Dashboard.vue'), 'utf8')
    expect(source).toContain('minmax(0, 1fr)')
    expect(source).toContain('@media (max-width: 1480px)')
    expect(source).toMatch(/\.dashboard__hero-meta dt\s*\{[^}]*color:\s*var\(--research-text-secondary\)/s)
    expect(source).not.toMatch(/\.dashboard__hero-meta dt\s*\{[^}]*color:\s*var\(--research-text-muted\)/s)
    const pinia = createPinia()
    setActivePinia(pinia)
    const knowledgeLoad = vi.spyOn(useKnowledgeStore(), 'loadDocuments').mockRejectedValue(new Error('ECONNRESET'))
    vi.spyOn(useDatasetStore(), 'loadReport').mockResolvedValue()
    vi.spyOn(useManuscriptStore(), 'loadManuscript').mockResolvedValue()
    const wrapper = mount(Dashboard, { global: { plugins: [pinia] } })
    await flushPromises()
    expect(wrapper.text()).toContain('科研数据分析失败，请重试。')
    expect(wrapper.text()).not.toContain('ECONNRESET')
    await wrapper.get('.research-state__retry').trigger('click')
    await flushPromises()
    expect(knowledgeLoad).toHaveBeenCalledTimes(2)
  })

  it('项目空间响应式契约下拒绝英文异常并提供中文重试', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const source = readFileSync(resolve(rendererRoot, 'pages/research/ProjectWorkspace.vue'), 'utf8')
    expect(source).toContain('@media (min-width: 1720px)')
    expect(source).toContain('minmax(0, 1fr)')
    expect(source).not.toMatch(/\.workspace\s*\{[^}]*width:\s*1[4-9]\d{2}px/s)
    const pinia = createPinia()
    setActivePinia(pinia)
    const knowledgeLoad = vi.spyOn(useKnowledgeStore(), 'loadDocuments').mockRejectedValue(new Error('ECONNRESET'))
    vi.spyOn(useDatasetStore(), 'loadReport').mockResolvedValue()
    vi.spyOn(useManuscriptStore(), 'loadManuscript').mockResolvedValue()
    vi.spyOn(useExperimentStore(), 'loadDesign').mockResolvedValue()
    const wrapper = mount(ProjectWorkspace, { global: { plugins: [pinia] } })
    await flushPromises()
    expect(wrapper.text()).toContain('项目数据加载失败，请重试。')
    expect(wrapper.text()).not.toContain('ECONNRESET')
    await wrapper.get('.research-state__retry').trigger('click')
    await flushPromises()
    expect(knowledgeLoad).toHaveBeenCalledTimes(2)
  })
})

describe('焦点、ARIA 与键盘（5）', () => {
  it('侧栏与导航提供中文可读区域标签', async () => {
    const { wrapper } = await mountSidebar()
    expect(wrapper.get('aside').attributes('aria-label')).toBe('科研工作台导航')
    expect(wrapper.get('nav').attributes('aria-label')).toBe('科研模块')
  })

  it('折叠导航链接仍保留 aria-label 与 title 提示', async () => {
    localStorage.setItem('research-sidebar-collapsed', '1')
    const { wrapper } = await mountSidebar()
    for (const [label, routeName] of RESEARCH_NAV) {
      const link = wrapper.get(`[data-nav="${routeName}"]`)
      expect(link.attributes('aria-label')).toBe(label)
      expect(link.attributes('title')).toBe(label)
    }
  })

  it('用户菜单管理焦点、键盘游标、Escape 恢复触发器与外部关闭', async () => {
    const { wrapper } = await mountHeader()
    expect(wrapper.get('[data-testid="notification-button"]').attributes('aria-label')).toBe('查看科研通知')
    const trigger = wrapper.get<HTMLButtonElement>('[data-testid="user-menu-button"]')
    expect(trigger.attributes('aria-label')).toBe('打开用户菜单')
    expect(trigger.attributes('aria-controls')).toBe('research-user-menu')
    await trigger.trigger('click')
    await flushPromises()
    const menu = wrapper.get('#research-user-menu')
    expect(document.activeElement).toBe(wrapper.get('[data-testid="logout-button"]').element)
    for (const key of ['ArrowDown', 'ArrowUp', 'Home', 'End']) {
      await menu.trigger('keydown', { key })
      expect(document.activeElement).toBe(wrapper.get('[data-testid="logout-button"]').element)
    }
    await menu.trigger('keydown', { key: 'Escape' })
    expect(wrapper.find('#research-user-menu').exists()).toBe(false)
    expect(document.activeElement).toBe(trigger.element)
    await trigger.trigger('click')
    document.body.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('#research-user-menu').exists()).toBe(false)
  })

  it('项目空间提供六个 button 标签及 tablist 语义', async () => {
    const wrapper = await mountWorkspace()
    expect(wrapper.get('[role="tablist"]').attributes('aria-label')).toBe('项目工作区')
    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs).toHaveLength(6)
    expect(tabs.map(tab => tab.text())).toEqual(expect.arrayContaining(['项目概览', '文献', '实验', '数据', '模型', '论文']))
  })

  it('标签支持 ArrowRight 键盘切换并同步 aria-selected', async () => {
    const wrapper = await mountWorkspace()
    const tabs = wrapper.findAll<HTMLButtonElement>('[role="tab"]')
    expect(tabs[0].attributes('aria-selected')).toBe('true')
    await tabs[0].trigger('keydown', { key: 'ArrowRight' })
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('[role="tab"]')[1].attributes('aria-selected')).toBe('true')
    expect((document.activeElement as HTMLElement | null)?.textContent).toContain('文献')
  })
})
