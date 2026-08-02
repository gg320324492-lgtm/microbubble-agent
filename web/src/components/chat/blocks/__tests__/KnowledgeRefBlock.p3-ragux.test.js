import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import KnowledgeRefBlock from '../KnowledgeRefBlock.vue'

const mobileState = vi.hoisted(() => ({ isMobile: null }))
const messageBoxState = vi.hoisted(() => ({ alert: vi.fn() }))

vi.mock('@/composables/useIsMobile', () => ({
  useIsMobile: () => ({ isMobile: mobileState.isMobile }),
}))

vi.mock('element-plus', () => ({
  ElMessageBox: { alert: messageBoxState.alert },
}))

const createTestRouter = () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/knowledge', name: 'Knowledge', component: { template: '<div />' } },
      { path: '/knowledge/:id', name: 'KnowledgeDetail', component: { template: '<div />' } },
    ],
  })
  router.push = vi.fn()
  return router
}

const baseResults = [
  {
    id: 'k1',
    title: '纳米气泡综述',
    content: '微纳米气泡在水处理中的应用',
    summary: '综述微纳米气泡的水处理应用',
    snippet: '微纳米气泡在水处理中的应用',
    score: 0.92,
    category: 'review',
    tags: ['综述', '水处理'],
    source: 'paper-2025.pdf',
    entities: ['微纳米气泡', '水处理'],
    related: [{ id: 'k2', title: '相关研究' }],
    created_at: '2026-05-15',
  },
  {
    id: 'k2',
    title: '实验方法论',
    content: '微纳米气泡制备实验方法',
    score: 0.72,
    category: 'experiment',
    tags: ['实验'],
    entities: ['制备方法'],
    created_at: '2026-04-10',
  },
  {
    id: 'k3',
    title: '理论推导',
    content: '气泡动力学方程',
    score: 0.45,
    category: 'research',
    tags: ['理论'],
    created_at: '2026-06-01',
  },
  {
    id: 'k4',
    title: '博士论文',
    content: '微纳米气泡机理',
    score: 0.83,
    category: 'thesis',
    created_at: '2026-01-20',
  },
  {
    id: 'k5',
    title: '期刊论文',
    content: '气泡传质效率',
    score: 0.65,
    category: 'paper',
    created_at: '2026-02-25',
  },
]

const makeBlock = (results = baseResults) => ({
  type: 'knowledge_ref',
  title: '知识引用',
  data: { results },
})

const mountBlock = ({ results = baseResults, citations = [], router = createTestRouter() } = {}) => ({
  router,
  wrapper: mount(KnowledgeRefBlock, {
    props: { block: makeBlock(results), citations },
    global: { plugins: [router] },
  }),
})

const advanceHover = async (item) => {
  await item.trigger('mouseenter')
  await vi.advanceTimersByTimeAsync(300)
  await flushPromises()
}

describe('KnowledgeRefBlock P3-RAGUX retry', () => {
  beforeEach(() => {
    localStorage.clear()
    mobileState.isMobile = ref(false)
    messageBoxState.alert.mockReset()
    messageBoxState.alert.mockResolvedValue(undefined)
    vi.useRealTimers()
  })

  describe('2.1 score tiers and category icons', () => {
    it('uses the high tier at 80 percent and above', () => {
      const { wrapper } = mountBlock({
        results: [{ id: 'a', title: 'A', content: 'A', score: 0.8 }],
      })
      expect(wrapper.find('.ref-item').classes()).toContain('score-high')
      expect(wrapper.find('.score-badge').text()).toBe('80%')
    })

    it('uses the medium tier from 60 to below 80 percent', () => {
      const { wrapper } = mountBlock({
        results: [{ id: 'a', title: 'A', content: 'A', score: 0.6 }],
      })
      expect(wrapper.find('.ref-item').classes()).toContain('score-med')
    })

    it('uses the low tier below 60 percent', () => {
      const { wrapper } = mountBlock({
        results: [{ id: 'a', title: 'A', content: 'A', score: 0.599 }],
      })
      expect(wrapper.find('.ref-item').classes()).toContain('score-low')
    })

    it('keeps missing scores neutral', () => {
      const { wrapper } = mountBlock({
        results: [{ id: 'a', title: 'A', content: 'A' }],
      })
      expect(wrapper.find('.ref-item').classes()).toContain('score-neutral')
      expect(wrapper.find('.score-badge').exists()).toBe(false)
    })

    it('maps the five supported categories to their icons', () => {
      const expected = {
        research: '🔬',
        experiment: '⚗️',
        review: '📖',
        paper: '📄',
        thesis: '🎓',
      }

      Object.entries(expected).forEach(([category, icon]) => {
        const { wrapper } = mountBlock({
          results: [{ id: category, title: category, content: category, category }],
        })
        expect(wrapper.find('.cat-icon').text()).toBe(icon)
      })
    })

    it('falls back to the folder icon for unknown categories', () => {
      const { wrapper } = mountBlock({
        results: [{ id: 'a', title: 'A', content: 'A', category: 'other' }],
      })
      expect(wrapper.find('.cat-icon').text()).toBe('📁')
    })
  })

  describe('2.2 sorting and persistence', () => {
    it('sorts by score descending by default', () => {
      const { wrapper } = mountBlock()
      expect(wrapper.findAll('.ref-item')[0].text()).toContain('纳米气泡综述')
      expect(wrapper.findAll('.ref-item')[1].text()).toContain('博士论文')
    })

    it('renders all three sort choices', () => {
      const { wrapper } = mountBlock()
      const options = wrapper.findAll('.sort-select option')
      expect(options.map((option) => option.attributes('value'))).toEqual([
        'score_desc',
        'date_desc',
        'category',
      ])
    })

    it('sorts newest records first', async () => {
      const { wrapper } = mountBlock()
      await wrapper.find('.sort-select').setValue('date_desc')
      expect(wrapper.findAll('.ref-item')[0].text()).toContain('理论推导')
    })

    it('sorts categories ascending and scores ties descending', async () => {
      const results = [
        { id: 'a', title: '较低实验', content: 'a', score: 0.61, category: 'experiment' },
        { id: 'b', title: '论文', content: 'b', score: 0.9, category: 'paper' },
        { id: 'c', title: '较高实验', content: 'c', score: 0.82, category: 'experiment' },
      ]
      const { wrapper } = mountBlock({ results })
      await wrapper.find('.sort-select').setValue('category')
      const titles = wrapper.findAll('.ref-item').map((item) => item.find('.title-text').text())
      expect(titles).toEqual(['较高实验', '较低实验', '论文'])
    })

    it('persists the selected sort mode', async () => {
      const { wrapper } = mountBlock()
      await wrapper.find('.sort-select').setValue('category')
      expect(localStorage.getItem('kb_ref_sort')).toBe('category')
    })

    it('restores a valid saved sort mode', async () => {
      localStorage.setItem('kb_ref_sort', 'date_desc')
      const { wrapper } = mountBlock()
      await flushPromises()
      expect(wrapper.find('.sort-select').element.value).toBe('date_desc')
      expect(wrapper.findAll('.ref-item')[0].text()).toContain('理论推导')
    })

    it('ignores an invalid saved sort mode', async () => {
      localStorage.setItem('kb_ref_sort', 'invalid')
      const { wrapper } = mountBlock()
      await flushPromises()
      expect(wrapper.find('.sort-select').element.value).toBe('score_desc')
      expect(wrapper.findAll('.ref-item')[0].text()).toContain('纳米气泡综述')
    })

    it('hides sorting when only one reference exists', () => {
      const { wrapper } = mountBlock({
        results: [{ id: 'a', title: '唯一引用', content: 'A', score: 0.9 }],
      })
      expect(wrapper.find('.sort-control').exists()).toBe(false)
    })
  })

  describe('2.3 desktop hover and mobile modal', () => {
    it('keeps desktop details hidden before the hover delay', async () => {
      vi.useFakeTimers()
      const { wrapper } = mountBlock()
      await wrapper.find('.ref-item').trigger('mouseenter')
      await vi.advanceTimersByTimeAsync(299)
      expect(wrapper.find('.detail-panel').exists()).toBe(false)
    })

    it('opens desktop details after 300 milliseconds', async () => {
      vi.useFakeTimers()
      const { wrapper } = mountBlock()
      await advanceHover(wrapper.find('.ref-item'))
      const detail = wrapper.find('.detail-panel')
      expect(detail.exists()).toBe(true)
      expect(detail.text()).toContain('综述微纳米气泡的水处理应用')
    })

    it('shows entities, related knowledge, and date in desktop details', async () => {
      vi.useFakeTimers()
      const { wrapper } = mountBlock()
      await advanceHover(wrapper.find('.ref-item'))
      expect(wrapper.find('.detail-panel').text()).toContain('水处理')
      expect(wrapper.find('.detail-panel').text()).toContain('相关研究')
      expect(wrapper.find('.detail-panel').text()).toContain('2026-05-15')
    })

    it('cancels a pending hover before it opens', async () => {
      vi.useFakeTimers()
      const { wrapper } = mountBlock()
      await wrapper.find('.ref-item').trigger('mouseenter')
      await wrapper.find('.kb-ref').trigger('mouseleave')
      await vi.advanceTimersByTimeAsync(300)
      expect(wrapper.find('.detail-panel').exists()).toBe(false)
    })

    it('does not open desktop hover details on mobile', async () => {
      vi.useFakeTimers()
      mobileState.isMobile.value = true
      const { wrapper } = mountBlock()
      await advanceHover(wrapper.find('.ref-item'))
      expect(wrapper.find('.detail-panel').exists()).toBe(false)
    })

    it('opens the mobile detail modal on tap', async () => {
      mobileState.isMobile.value = true
      messageBoxState.alert.mockRejectedValueOnce(new Error('closed'))
      const { wrapper } = mountBlock()
      await wrapper.find('.ref-item').trigger('click')
      await flushPromises()
      expect(messageBoxState.alert).toHaveBeenCalledOnce()
      expect(messageBoxState.alert.mock.calls[0][0]).toContain('关键实体：微纳米气泡、水处理')
    })

    it('navigates from the mobile modal primary action', async () => {
      mobileState.isMobile.value = true
      const router = createTestRouter()
      const { wrapper } = mountBlock({ router })
      await wrapper.find('.ref-item').trigger('click')
      await flushPromises()
      expect(router.push).toHaveBeenCalledWith('/knowledge/k1')
    })
  })

  describe('2.4 canonical navigation and compatibility', () => {
    it('uses the canonical knowledge detail route on desktop', async () => {
      const router = createTestRouter()
      const { wrapper } = mountBlock({ router })
      await wrapper.find('.ref-item').trigger('click')
      expect(router.push).toHaveBeenCalledWith('/knowledge/k1')
    })

    it('encodes an id before building the canonical route', async () => {
      const router = createTestRouter()
      const { wrapper } = mountBlock({
        router,
        results: [{ id: 'id with/slash', title: '特殊 ID', content: 'A' }],
      })
      await wrapper.find('.ref-item').trigger('click')
      expect(router.push).toHaveBeenCalledWith('/knowledge/id%20with%2Fslash')
    })

    it('does not navigate without a knowledge id', async () => {
      const router = createTestRouter()
      const { wrapper } = mountBlock({
        router,
        results: [{ id: '', title: '无 ID', content: 'A' }],
      })
      await wrapper.find('.ref-item').trigger('click')
      expect(router.push).not.toHaveBeenCalled()
    })

    it('retains citation highlighting', () => {
      const results = [{
        id: 'a',
        chunk_id: 'chunk-a',
        title: '引用高亮',
        content: '原始内容',
        snippet: '0123456789',
        score: 0.8,
      }]
      const citations = [{ chunk_id: 'chunk-a', char_range: [2, 5] }]
      const { wrapper } = mountBlock({ results, citations })
      expect(wrapper.find('.citation-mark').text()).toBe('234')
    })

    it('retains W101 list, listitem, heading, and focus semantics', () => {
      const { wrapper } = mountBlock()
      expect(wrapper.find('.kb-ref').attributes('role')).toBe('list')
      expect(wrapper.find('.card-header').attributes('role')).toBe('heading')
      expect(wrapper.find('.card-header').attributes('aria-level')).toBe('3')
      expect(wrapper.find('.ref-item').attributes('role')).toBe('listitem')
      expect(wrapper.find('.ref-item').attributes('tabindex')).toBe('0')
      expect(wrapper.find('.ref-item').attributes('aria-label')).toContain('相似度 92%')
    })

    it('activates the canonical route with the Enter key', async () => {
      const router = createTestRouter()
      const { wrapper } = mountBlock({ router })
      await wrapper.find('.ref-item').trigger('keydown', { key: 'Enter' })
      expect(router.push).toHaveBeenCalledWith('/knowledge/k1')
    })

    it('activates the canonical route with the Space key', async () => {
      const router = createTestRouter()
      const { wrapper } = mountBlock({ router })
      await wrapper.find('.ref-item').trigger('keydown', { key: ' ' })
      expect(router.push).toHaveBeenCalledWith('/knowledge/k1')
    })

    it('renders the empty state without a sort control', () => {
      const { wrapper } = mountBlock({ results: [] })
      expect(wrapper.find('.empty').text()).toBe('暂无知识')
      expect(wrapper.find('.sort-control').exists()).toBe(false)
      expect(wrapper.find('.kb-ref').attributes('role')).toBe('list')
    })

    it('falls back to content when no snippet or summary exists', async () => {
      vi.useFakeTimers()
      const { wrapper } = mountBlock({
        results: [{ id: 'a', title: '内容兜底', content: '<b>完整内容</b>', score: 0.9 }],
      })
      await advanceHover(wrapper.find('.ref-item'))
      expect(wrapper.find('.detail-panel').text()).toContain('完整内容')
      expect(wrapper.find('.detail-panel').text()).not.toContain('<b>')
    })
  })
})
