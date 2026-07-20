/**
 * ParagraphActions.test.js — 2026-07-20 paper 段落操作 3 TODO 实装验证
 *
 * 覆盖 (3 case):
 *   1. handleTranslate → 调 translation API, 成功显示译文; 失败 toast error
 *   2. handleHighlight → localStorage `paper_highlights_<file_id>` 写入/移除 paragraph.id
 *   3. handleAsk → router.push 到 chat 路由, query 包含 preset
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// Element Plus stubs
// inheritAttrs: false 防止 el-button 的 @click 属性 fallthrough 到 inner <button> 重复触发
// 父组件 @click="handleXxx" 在 inheritAttrs:false 下只通过 $emit('click') 单次触发
const stubs = {
  'el-tooltip': { template: '<div class="tooltip-stub"><slot /></div>' },
  'el-button': {
    inheritAttrs: false,
    template: '<button :data-test="$attrs[\'data-test\']" @click="$emit(\'click\', $event)"></button>',
  },
}

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  Promotion: { template: '<i />' },
  CopyDocument: { template: '<i />' },
  Brush: { template: '<i />' },
  ChatLineRound: { template: '<i />' },
}))

// Mock Element Plus messages
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

// Mock translation API
const mockTranslateText = vi.fn()
vi.mock('@/api/translation', () => ({
  translateText: (...args) => mockTranslateText(...args),
}))

// Mock router
const mockRouterPush = vi.fn().mockResolvedValue(undefined)
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockRouterPush }),
}))

import ParagraphActions from '../ParagraphActions.vue'

const globalConfig = {
  stubs,
  mocks: {},
}

const makeParagraph = (overrides = {}) => ({
  id: 'p-1',
  content: 'Microbubbles have unique properties for water treatment.',
  ...overrides,
})

describe('ParagraphActions 2026-07-20 实装', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('handleTranslate 成功 → 调 API + 显示译文 + 二次点击收起', async () => {
    mockTranslateText.mockResolvedValue({ translated_text: '微纳米气泡在水处理方面具有独特性质。' })
    const wrapper = mount(ParagraphActions, {
      props: { paragraph: makeParagraph(), fileId: 42 },
      global: globalConfig,
    })
    const btn = wrapper.find('[data-test="translate-btn"]')
    await btn.trigger('click')
    await flushPromises()
    expect(mockTranslateText).toHaveBeenCalledWith({
      text: 'Microbubbles have unique properties for water treatment.',
      target_lang: 'en',
    })
    expect(wrapper.text()).toContain('微纳米气泡在水处理方面具有独特性质。')
    // 二次点击 → 收起
    await btn.trigger('click')
    await nextTick()
    expect(wrapper.text()).not.toContain('微纳米气泡在水处理方面具有独特性质。')
  })

  it('handleHighlight → localStorage 写入 + 切换', async () => {
    const { ElMessage } = await import('element-plus')
    const wrapper = mount(ParagraphActions, {
      props: { paragraph: makeParagraph({ id: 'p-99' }), fileId: 7 },
      global: globalConfig,
    })
    const btn = wrapper.find('[data-test="highlight-btn"]')
    // 首次点击 → 高亮
    await btn.trigger('click')
    await nextTick()
    await nextTick()  // computed 重新求值 (isHighlighted)
    expect(JSON.parse(localStorage.getItem('paper_highlights_7'))).toEqual(['p-99'])
    expect(ElMessage.success).toHaveBeenCalledWith('已高亮标注')
    // 二次点击 → 取消
    await btn.trigger('click')
    await nextTick()
    await nextTick()
    expect(JSON.parse(localStorage.getItem('paper_highlights_7'))).toEqual([])
    expect(ElMessage.success).toHaveBeenCalledWith('已取消高亮')
  })

  it('handleHighlight 无 fileId → warning toast, 不写 localStorage', async () => {
    const { ElMessage } = await import('element-plus')
    const wrapper = mount(ParagraphActions, {
      props: { paragraph: makeParagraph() },  // fileId 不传
      global: globalConfig,
    })
    const btn = wrapper.find('[data-test="highlight-btn"]')
    await btn.trigger('click')
    await nextTick()
    expect(ElMessage.warning).toHaveBeenCalledWith(expect.stringContaining('file_id'))
    expect(localStorage.getItem('paper_highlights_undefined')).toBeNull()
  })

  it('handleAsk → router.push 到 /chat + query.preset 含段落内容', async () => {
    const wrapper = mount(ParagraphActions, {
      props: { paragraph: makeParagraph(), fileId: 42 },
      global: globalConfig,
    })
    const btn = wrapper.find('[data-test="ask-btn"]')
    await btn.trigger('click')
    await flushPromises()
    expect(mockRouterPush).toHaveBeenCalledTimes(1)
    const [arg] = mockRouterPush.mock.calls[0]
    expect(arg.path).toBe('/chat')
    expect(arg.query.preset).toContain('Microbubbles have unique properties for water treatment.')
    expect(arg.query.preset.startsWith('请帮我分析这段')).toBe(true)
  })

  it('handleTranslate 失败 → ElMessage.error 兜底', async () => {
    const { ElMessage } = await import('element-plus')
    mockTranslateText.mockRejectedValue(new Error('翻译服务 500'))
    const wrapper = mount(ParagraphActions, {
      props: { paragraph: makeParagraph(), fileId: 1 },
      global: globalConfig,
    })
    const btn = wrapper.find('[data-test="translate-btn"]')
    await btn.trigger('click')
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('翻译服务 500')
  })
})
