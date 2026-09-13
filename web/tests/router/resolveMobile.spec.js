import { beforeEach, describe, expect, it, vi } from 'vitest'
import router from '@/router'
import { resolveMobileComponent } from '@/utils/resolveMobile'
import { useViewportRef } from '@/composables/useIsMobile'

function setViewport(width) {
  Object.defineProperty(window, 'innerWidth', {
    value: width,
    writable: true,
    configurable: true,
  })
  useViewportRef().value = { width, height: 800, dpr: 1 }
}

function routeByName(name) {
  return router.getRoutes().find((route) => route.name === name)
}

function routeComponent(name) {
  const route = routeByName(name)
  expect(route).toBeDefined()
  return route.components?.default || route.component
}

// 2026-09-13 起 resolveMobile* 返回普通异步加载函数 (Vue Router lazy 形式,
// `() => Promise<Component>`), 不再是 defineAsyncComponent 对象 (无 __asyncLoader);
// 传函数正是 Vue Router 官方推荐写法, 同时消灭每条路由的
// "Component defined using defineAsyncComponent()" 警告。
// import.meta.glob 的 loader resolve 出的是模块命名空间 — Vue Router 生产路径
// 会自动解包 .default, 测试里手动等价解包
function unwrapModule(resolved) {
  return resolved && typeof resolved === 'object' && 'default' in resolved
    ? resolved.default
    : resolved
}

async function loadRouteComponent(name, width) {
  setViewport(width)
  const comp = routeComponent(name)
  return unwrapModule(typeof comp === 'function' ? await comp() : comp)
}

async function loadResolvedComponent(desktopPath, mobilePath, width) {
  setViewport(width)
  return unwrapModule(await resolveMobileComponent(desktopPath, mobilePath)())
}

beforeEach(() => {
  setViewport(1280)
})

describe('resolveMobileComponent routing', () => {
  it('loads MobileDriveView from the real Drive route on mobile', async () => {
    const component = await loadRouteComponent('Drive', 375)

    expect(component.__name || component.name).toBe('MobileDriveView')
  })

  it('keeps DesktopDriveView on desktop', async () => {
    const component = await loadResolvedComponent(
      'DesktopDriveView',
      'MobileDriveView',
      1280
    )

    expect(component.__name || component.name).toBe('DesktopDriveView')
  })

  it('loads MobileKnowledgeView from the real Knowledge route on mobile', async () => {
    const component = await loadRouteComponent('Knowledge', 375)

    expect(component.__name || component.name).toBe('MobileKnowledgeView')
  })

  it('falls back to the desktop component when the mobile file is missing', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const component = await loadResolvedComponent(
      'DesktopDriveView',
      'MissingDriveView',
      375
    )

    expect(component.__name || component.name).toBe('DesktopDriveView')
    expect(warn).toHaveBeenCalledWith(
      '[resolveMobile] 未找到组件: mobile MissingDriveView'
    )
    warn.mockRestore()
  })
})
