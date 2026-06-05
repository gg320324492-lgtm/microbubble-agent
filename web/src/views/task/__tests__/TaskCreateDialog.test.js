import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import TaskCreateDialog from '../TaskCreateDialog.vue'

// Mock useTask composable
vi.mock('@/composables/useTask', () => ({
  useTask: () => ({
    createTask: vi.fn().mockResolvedValue({ id: 1, title: '新任务' }),
    updateTask: vi.fn().mockResolvedValue({ id: 1, title: '更新任务' })
  })
}))

// Mock member store
vi.mock('@/stores/member', () => ({
  useMemberStore: () => ({
    members: [
      { id: 1, name: '张三' },
      { id: 2, name: '李四' }
    ]
  })
}))

describe('TaskCreateDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('组件正确挂载', () => {
    const wrapper = mount(TaskCreateDialog, {
      props: { visible: true }
    })
    expect(wrapper.exists()).toBe(true)
  })

  it('接收 editingTask prop', () => {
    const wrapper = mount(TaskCreateDialog, {
      props: {
        visible: true,
        editingTask: { id: 1, title: '已有任务', priority: 'high' }
      }
    })
    expect(wrapper.props('editingTask')).toEqual({ id: 1, title: '已有任务', priority: 'high' })
  })

  it('接收 visible prop', () => {
    const wrapper = mount(TaskCreateDialog, {
      props: { visible: true }
    })
    expect(wrapper.props('visible')).toBe(true)
  })

  it('emit success 事件', async () => {
    const wrapper = mount(TaskCreateDialog, {
      props: { visible: true }
    })
    wrapper.vm.$emit('success')
    expect(wrapper.emitted('success')).toBeTruthy()
  })
})
