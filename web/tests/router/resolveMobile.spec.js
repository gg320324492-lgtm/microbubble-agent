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

async function loadRouteComponent(name, width) {
  setViewport(width)
  return routeComponent(name).__asyncLoader()
}

async function loadResolvedComponent(desktopPath, mobilePath, width) {
  setViewport(width)
  const asyncComponent = resolveMobileComponent(desktopPath, mobilePath)
  return asyncComponent.__asyncLoader()
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
