/**
 * ContentBriefDetail 组件单测 — W100 +25
 * 6 case 覆盖：1 段 / 2 段 / 3+ 段 / 折叠态 / 展开态 / 边界
 *
 * 注：detail 折叠使用 <Transition> 200ms 渐隐。
 * 收起后断言 expanded=false 而非 DOM 存在性，等 transition 完成再断言 DOM。
 */
import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ContentBriefDetail from '../ContentBriefDetail.vue'

describe('ContentBriefDetail — W100 +25', () => {
  beforeEach(() => {
    // noop
  })

  it('① 1 段文本完整显示，无折叠按钮', async () => {
    const wrapper = mount(ContentBriefDetail, {
      props: { content: '这是一个完整的回答，没有任何分段。' },
    })
    await nextTick()
    expect(wrapper.find('[data-testid="cbd-brief"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="cbd-toggle"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="cbd-detail"]').exists()).toBe(false)
    expect(wrapper.attributes('data-paragraph-count')).toBe('1')
    expect(wrapper.attributes('data-expanded')).toBe('false')
  })

  it('② 2 段文本默认折叠，brief 显示 + 折叠按钮可点', async () => {
    const wrapper = mount(ContentBriefDetail, {
      props: { content: '第一段简报内容。\n\n第二段详情内容比较长。' },
    })
    await nextTick()
    expect(wrapper.find('[data-testid="cbd-toggle"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="cbd-toggle"]').text()).toContain('展开')
    expect(wrapper.find('[data-testid="cbd-toggle"]').text()).toContain('1 段')
    expect(wrapper.attributes('data-paragraph-count')).toBe('2')
    expect(wrapper.find('[data-testid="cbd-toggle"]').attributes('aria-expanded')).toBe(
      'false',
    )
    expect(wrapper.find('[data-testid="cbd-detail"]').exists()).toBe(false)
  })

  it('③ 3+ 段折叠，点击展开后渲染多段 detail', async () => {
    const wrapper = mount(ContentBriefDetail, {
      props: {
        content: '简要结论\n\n第一段详情\n\n第二段详情\n\n第三段详情',
      },
    })
    await nextTick()
    expect(wrapper.find('[data-testid="cbd-toggle"]').text()).toContain('3 段')
    expect(wrapper.attributes('data-paragraph-count')).toBe('4')
    // 点击展开
    await wrapper.find('[data-testid="cbd-toggle"]').trigger('click')
    await nextTick()
    expect((wrapper.vm as any).expanded).toBe(true)
    expect(wrapper.find('[data-testid="cbd-detail"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid^="cbd-detail-para-"]').length).toBe(3)
    // 再次点击收起
    await wrapper.find('[data-testid="cbd-toggle"]').trigger('click')
    await nextTick()
    expect((wrapper.vm as any).expanded).toBe(false)
    // transition leave 动画 ~200ms
    await new Promise((r) => setTimeout(r, 300))
    await nextTick()
    expect(wrapper.find('[data-testid="cbd-detail"]').exists()).toBe(false)
  })

  it('④ 键盘 Enter / Space 触发折叠切换', async () => {
    const wrapper = mount(ContentBriefDetail, {
      props: { content: '第一段\n\n第二段' },
    })
    await nextTick()
    const toggle = wrapper.find('[data-testid="cbd-toggle"]')
    // Enter
    await toggle.trigger('keydown', { key: 'Enter' })
    await nextTick()
    expect((wrapper.vm as any).expanded).toBe(true)
    expect(wrapper.find('[data-testid="cbd-detail"]').exists()).toBe(true)
    // Space
    await toggle.trigger('keydown', { key: ' ' })
    await nextTick()
    expect((wrapper.vm as any).expanded).toBe(false)
  })

  it('⑤ aria 完备：aria-expanded + aria-controls + aria-label', async () => {
    const wrapper = mount(ContentBriefDetail, {
      props: { content: '简要\n\n详细一\n\n详细二' },
    })
    await nextTick()
    const toggle = wrapper.find('[data-testid="cbd-toggle"]')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    const detailId = toggle.attributes('aria-controls')
    expect(detailId).toBeTruthy()
    expect(toggle.attributes('aria-label')).toContain('2 段')
    // 展开后 aria-label 变化
    await toggle.trigger('click')
    await nextTick()
    expect(toggle.attributes('aria-label')).toBe('折叠详情')
    // detail 元素 id 与 aria-controls 对应
    const detail = wrapper.find('[data-testid="cbd-detail"]')
    expect(detail.attributes('id')).toBe(detailId)
  })

  it('⑥ 边界：空 content / 仅空白段 / 多 \\n\\n', async () => {
    // 空
    const w1 = mount(ContentBriefDetail, { props: { content: '' } })
    await nextTick()
    expect(w1.find('[data-testid="cbd-brief"]').exists()).toBe(false)
    expect(w1.find('[data-testid="cbd-toggle"]').exists()).toBe(false)

    // 仅空白段（trim 后空）
    const w2 = mount(ContentBriefDetail, {
      props: { content: '   \n\n   \n\n   ' },
    })
    await nextTick()
    expect(w2.find('[data-testid="cbd-brief"]').exists()).toBe(false)
    expect(w2.find('[data-testid="cbd-toggle"]').exists()).toBe(false)

    // 多 \n\n 折叠为单个分隔
    const w3 = mount(ContentBriefDetail, {
      props: { content: 'A\n\n\n\n\nB\n\n\nC' },
    })
    await nextTick()
    expect(w3.attributes('data-paragraph-count')).toBe('3')
    expect(w3.find('[data-testid="cbd-toggle"]').text()).toContain('2 段')
  })
})