// @vitest-environment jsdom
// 命令面板组件契约（M4）— 渲染过滤 / 键盘导航 / 执行回调
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { CommandRegistry } from '@shared/command-registry'
import CommandPalette from '@renderer/components/CommandPalette.vue'

// jsdom 未实现 scrollIntoView — 组件在 nextTick 中调用会产生 unhandled rejection
beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn()
})

function makeRegistry(): CommandRegistry {
  const r = new CommandRegistry()
  const calls: string[] = []
  r.register({ id: 'nav-eln', title: '实验 ELN', keywords: 'sy shiyan', action: () => calls.push('eln') })
  r.register({ id: 'nav-knowledge', title: '知识库', keywords: 'zsk zhishi', action: () => calls.push('kb') })
  r.register({ id: 'quit', title: '退出应用', keywords: 'tc quit', action: () => calls.push('quit') })
  // 暴露 calls 供断言（挂到 registry 上）
  ;(r as unknown as { calls: string[] }).calls = calls
  return r
}

function getCalls(r: CommandRegistry): string[] {
  return (r as unknown as { calls: string[] }).calls
}

function mountPalette(visible = true) {
  const registry = makeRegistry()
  const w = mount(CommandPalette, { props: { registry, visible } })
  return { w, registry }
}

describe('CommandPalette 命令面板', () => {
  it('visible=true 渲染面板；空查询列出全部命令', async () => {
    const { w } = mountPalette(true)
    await w.vm.$nextTick()
    expect(w.find('[data-testid="palette-input"]').exists()).toBe(true)
    const items = w.findAll('[data-testid^="palette-item-"]')
    expect(items).toHaveLength(3)
  })

  it('visible=false 不渲染', () => {
    const { w } = mountPalette(false)
    expect(w.find('[data-testid="palette-input"]').exists()).toBe(false)
  })

  it('输入过滤 — 子串匹配只保留命中命令', async () => {
    const { w } = mountPalette(true)
    await w.find('[data-testid="palette-input"]').setValue('退出')
    await w.vm.$nextTick()
    const items = w.findAll('[data-testid^="palette-item-"]')
    expect(items).toHaveLength(1)
    expect(items[0].text()).toContain('退出应用')
  })

  it('Enter 执行选中命令', async () => {
    const { w, registry } = mountPalette(true)
    await w.vm.$nextTick()
    await w.find('[data-testid="palette-input"]').trigger('keydown', { key: 'Enter' })
    expect(getCalls(registry)).toEqual(['eln']) // 首项 = 实验 ELN
  })

  it('Esc 触发 close 事件', async () => {
    const { w } = mountPalette(true)
    await w.vm.$nextTick()
    await w.find('[data-testid="palette-input"]').trigger('keydown', { key: 'Escape' })
    expect(w.emitted('close')).toHaveLength(1)
  })

  it('ArrowDown/ArrowUp 循环选择', async () => {
    const { w } = mountPalette(true)
    await w.vm.$nextTick()
    await w.find('[data-testid="palette-input"]').trigger('keydown', { key: 'ArrowDown' })
    await w.find('[data-testid="palette-input"]').trigger('keydown', { key: 'ArrowDown' })
    await w.find('[data-testid="palette-input"]').trigger('keydown', { key: 'Enter' })
    expect(getCalls(w.vm.registry as CommandRegistry)).toContain('quit') // 第三项
    await w.find('[data-testid="palette-input"]').trigger('keydown', { key: 'ArrowUp' })
    await w.find('[data-testid="palette-input"]').trigger('keydown', { key: 'ArrowUp' })
    await w.find('[data-testid="palette-input"]').trigger('keydown', { key: 'Enter' })
    expect(getCalls(w.vm.registry as CommandRegistry)).toContain('eln')
  })
})
