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
