/**
 * ContentBriefDetail 组件单测 — W100 +25 / W100 +49a
 * W100 +49a RICHTEXT-UNFOLD 沿用:
 *   - 默认 (collapsedByDefault 不传 / false) = 全部段直接渲染, 无 toggle 按钮
 *   - collapsedByDefault=true = 折叠模式, 保留 toggle UI
 *
 * 7 case 覆盖：默认渲染 / 折叠模式渲染 / 折叠模式点击展开 / 折叠模式 keyboard
 * / aria 完备 / 边界 / collapsedByDefault=true 显式折叠
 */
import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ContentBriefDetail from '../ContentBriefDetail.vue'

describe('ContentBriefDetail — W100 +49a RICHTEXT-UNFOLD 默认展开', () => {
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
    expect(wrapper.attributes('data-collapsed-by-default')).toBe('false')
  })

  it('② 2 段文本默认直接渲染全部段，无折叠按钮', async () => {
    const wrapper = mount(ContentBriefDetail, {
      props: { content: '第一段简报内容。\n\n第二段详情内容比较长。' },
    })
    await nextTick()
    expect(wrapper.find('[data-testid="cbd-toggle"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="cbd-detail"]').exists()).toBe(false)
    expect(wrapper.attributes('data-paragraph-count')).toBe('2')
    // 第二段作为 detail-para 渲染
    expect(wrapper.find('[data-testid="cbd-detail-para-0"]').exists()).toBe(true)
  })

  it('③ 3+ 段默认全部渲染，无折叠按钮', async () => {
    const wrapper = mount(ContentBriefDetail, {
      props: {
        content: '简要结论\n\n第一段详情\n\n第二段详情\n\n第三段详情',
      },
    })
    await nextTick()
    expect(wrapper.find('[data-testid="cbd-toggle"]').exists()).toBe(false)
    expect(wrapper.attributes('data-paragraph-count')).toBe('4')
    expect(wrapper.findAll('[data-testid^="cbd-detail-para-"]').length).toBe(3)
  })

  it('④ collapsedByDefault=true 折叠模式：toggle 存在，detail 默认折叠', async () => {
    const wrapper = mount(ContentBriefDetail, {
      props: { content: '简要\n\n详细一\n\n详细二', collapsedByDefault: true },
    })
    await nextTick()
    const toggle = wrapper.find('[data-testid="cbd-toggle"]')
    expect(toggle.exists()).toBe(true)
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('[data-testid="cbd-detail"]').exists()).toBe(false)
    expect(wrapper.attributes('data-collapsed-by-default')).toBe('true')
    await toggle.trigger('click')
    await nextTick()
    expect(wrapper.find('[data-testid="cbd-detail"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid^="cbd-detail-para-"]').length).toBe(2)
  })

  it('⑤ collapsedByDefault=true 折叠模式键盘 Enter / Space 触发折叠切换', async () => {
    const wrapper = mount(ContentBriefDetail, {
      props: { content: '第一段\n\n第二段', collapsedByDefault: true },
    })
    await nextTick()
    const toggle = wrapper.find('[data-testid="cbd-toggle"]')
    // Enter
    await toggle.trigger('keydown', { key: 'Enter' })
    await nextTick()
    expect(wrapper.find('[data-testid="cbd-detail"]').exists()).toBe(true)
    // Space
    await toggle.trigger('keydown', { key: ' ' })
    await nextTick()
    // Transition leave 200ms, 等动画完成断言 DOM 移除
    await new Promise((r) => setTimeout(r, 300))
    await nextTick()
    expect(wrapper.find('[data-testid="cbd-detail"]').exists()).toBe(false)
  })

  it('⑥ collapsedByDefault=true 折叠模式 aria 完备', async () => {
    const wrapper = mount(ContentBriefDetail, {
      props: { content: '简要\n\n详细一\n\n详细二', collapsedByDefault: true },
    })
    await nextTick()
    const toggle = wrapper.find('[data-testid="cbd-toggle"]')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    const detailId = toggle.attributes('aria-controls')
    expect(detailId).toBeTruthy()
    expect(toggle.attributes('aria-label')).toContain('2 段')
    await toggle.trigger('click')
    await nextTick()
    expect(toggle.attributes('aria-label')).toBe('折叠详情')
    const detail = wrapper.find('[data-testid="cbd-detail"]')
    expect(detail.attributes('id')).toBe(detailId)
  })

  it('⑦ 边界：空 content / 仅空白段 / 多 \\n\\n', async () => {
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
    expect(w3.find('[data-testid="cbd-toggle"]').exists()).toBe(false)
    expect(w3.findAll('[data-testid^="cbd-detail-para-"]').length).toBe(2)
  })
})
