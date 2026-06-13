import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import CardList from '../CardList.vue'

describe('CardList', () => {
  const items = [
    { id: 1, name: '项目 A', status: 'active' },
    { id: 2, name: '项目 B', status: 'completed' },
    { id: 3, name: '项目 C', status: 'paused' },
  ]

  const factory = (props = {}) => mount(CardList, {
    props: {
      items,
      fieldConfig: {
        title: (item) => item.name,
        badge: (item) => ({ label: item.status, type: item.status === 'active' ? 'success' : 'info' }),
      },
      ...props,
    },
  })

  it('渲染每个 item', () => {
    const wrapper = factory()
    const cards = wrapper.findAll('.list-item')
    expect(cards.length).toBe(3)
  })

  it('空 items 显示空态', () => {
    const wrapper = factory({ items: [] })
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('自定义空态', () => {
    const wrapper = factory({
      items: [],
      emptyIcon: '🎉',
      emptyTitle: '全部完成',
    })
    expect(wrapper.text()).toContain('全部完成')
  })

  it('非 selectable 模式点击触发 item-click', async () => {
    const wrapper = factory()
    await wrapper.findAll('.list-item')[0].trigger('click')
    expect(wrapper.emitted('item-click')).toBeTruthy()
    expect(wrapper.emitted('item-click')[0][0]).toEqual(items[0])
  })

  it('selectable 模式点击切换选中', async () => {
    const wrapper = factory({ selectable: true, selected: [] })
    await wrapper.findAll('.list-item')[0].trigger('click')
    expect(wrapper.emitted('update:selected')).toBeTruthy()
    expect(wrapper.emitted('update:selected')[0][0]).toEqual([items[0]])
  })

  it('selectable 模式再次点击取消选中', async () => {
    const wrapper = factory({ selectable: true, selected: [items[0]] })
    await wrapper.findAll('.list-item')[0].trigger('click')
    expect(wrapper.emitted('update:selected')[0][0]).toEqual([])
  })

  it('hasMore=true 显示加载更多', () => {
    const wrapper = factory({ hasMore: true })
    expect(wrapper.find('.load-more').exists()).toBe(true)
  })

  it('点击加载更多触发 load-more 事件', async () => {
    const wrapper = factory({ hasMore: true })
    await wrapper.find('.load-more').trigger('click')
    expect(wrapper.emitted('load-more')).toBeTruthy()
  })

  it('loading=true 显示 spinner', () => {
    const wrapper = factory({ loading: true, hasMore: true })
    expect(wrapper.find('.loading-state').exists()).toBe(true)
  })

  it('有 selected 时显示 batch-bar', () => {
    const wrapper = factory({ selectable: true, selected: [items[0]] })
    expect(wrapper.find('.batch-bar').exists()).toBe(true)
    expect(wrapper.text()).toContain('1 项已选')
  })
})