import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import KnowledgeQADialog from '../KnowledgeQADialog.vue'

// Mock axios
vi.mock('axios', () => ({
  default: {
    post: vi.fn()
  }
}))

import axios from 'axios'

describe('KnowledgeQADialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('组件正确挂载', () => {
    const wrapper = mount(KnowledgeQADialog, {
      props: { visible: true }
    })
    expect(wrapper.exists()).toBe(true)
  })

  it('接收 visible prop', () => {
    const wrapper = mount(KnowledgeQADialog, {
      props: { visible: true }
    })
    expect(wrapper.props('visible')).toBe(true)
  })

  it('接收 isMobile prop', () => {
    const wrapper = mount(KnowledgeQADialog, {
      props: { visible: true, isMobile: true }
    })
    expect(wrapper.props('isMobile')).toBe(true)
  })

  it('emit navigate 事件', () => {
    const wrapper = mount(KnowledgeQADialog, {
      props: { visible: true }
    })
    wrapper.vm.$emit('navigate', 1)
    expect(wrapper.emitted('navigate')).toBeTruthy()
  })
})
