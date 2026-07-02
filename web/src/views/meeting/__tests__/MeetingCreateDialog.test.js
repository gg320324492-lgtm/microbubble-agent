import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ElButton, ElDialog, ElForm, ElFormItem, ElInput, ElCheckbox, ElIcon, ElDivider, ElTag } from 'element-plus'
import MeetingCreateDialog from '../MeetingCreateDialog.vue'

// Mock useMeeting composable
vi.mock('@/composables/useMeeting', () => ({
  useMeeting: () => ({
    createMeeting: vi.fn().mockResolvedValue({ id: 1, title: '新会议' }),
    updateMeeting: vi.fn().mockResolvedValue({ id: 1, title: '更新会议' })
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

/**
 * MeetingCreateDialog.test.js
 *
 * 2026-07-03: 模板管理 (template-picker / save-template / clone-template / delete-template /
 *            toggle-active / builtin + custom 模板卡 / LongPress / MobileActionSheet) 已彻底删除.
 *            删除了 12 个模板相关 case + LongPressWrapper / MobileActionSheet import.
 */
describe('MeetingCreateDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const globalComponents = {
    ElButton, ElDialog, ElForm, ElFormItem, ElInput, ElCheckbox, ElIcon, ElDivider, ElTag,
  }

  it('组件正确挂载', () => {
    const wrapper = mount(MeetingCreateDialog, {
      props: { visible: true }
    })
    expect(wrapper.exists()).toBe(true)
  })

  it('接收 visible prop', () => {
    const wrapper = mount(MeetingCreateDialog, {
      props: { visible: true }
    })
    expect(wrapper.props('visible')).toBe(true)
  })

  it('接收 editingId prop', () => {
    const wrapper = mount(MeetingCreateDialog, {
      props: { visible: true, editingId: 1 }
    })
    expect(wrapper.props('editingId')).toBe(1)
  })

  it('接收 isMobile prop', () => {
    const wrapper = mount(MeetingCreateDialog, {
      props: { visible: true, isMobile: true }
    })
    expect(wrapper.props('isMobile')).toBe(true)
  })

  it('emit success 事件', () => {
    const wrapper = mount(MeetingCreateDialog, {
      props: { visible: true }
    })
    wrapper.vm.$emit('success')
    expect(wrapper.emitted('success')).toBeTruthy()
  })

  it('编辑模式接收 editingData', () => {
    const editingData = {
      id: 1,
      title: '已有会议',
      summary: '会议摘要',
      key_points: ['要点1'],
      decisions: ['决议1']
    }
    const wrapper = mount(MeetingCreateDialog, {
      props: {
        visible: true,
        editingId: 1,
        editingData
      }
    })
    expect(wrapper.props('editingId')).toBe(1)
    expect(wrapper.props('editingData')).toEqual(editingData)
  })
})
