import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ElButton, ElDialog, ElForm, ElFormItem, ElInput, ElCheckbox, ElIcon, ElDivider, ElTag, ElTooltip } from 'element-plus'
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

describe('MeetingCreateDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // 全局注册 Element Plus 组件 (jsdom 不挂载 el-* 组件导致 button 找不到)
  const globalComponents = {
    ElButton, ElDialog, ElForm, ElFormItem, ElInput, ElCheckbox, ElIcon, ElDivider, ElTag, ElTooltip,
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

  it('接收 templates prop', () => {
    const templates = [
      { id: 1, name: '组会', is_builtin: true }
    ]
    const wrapper = mount(MeetingCreateDialog, {
      props: { visible: true, templates }
    })
    expect(wrapper.props('templates')).toEqual(templates)
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

  // v77 P2.6-F.3: '存为新模板' 按钮 + emit save-template 测试
  it('存为新模板功能在新建模式触发 emit (按钮 v-if !editingId)', () => {
    const wrapper = mount(MeetingCreateDialog, {
      props: { visible: true, editingId: null },
    })
    wrapper.vm.form.title = '测试会议'
    wrapper.vm.onSaveAsTemplate()
    expect(wrapper.emitted('save-template'), '新建模式应触发 save-template emit').toBeTruthy()
  })

  it('存为新模板功能在编辑模式不触发 (按钮 v-if 编辑模式隐藏)', () => {
    const wrapper = mount(MeetingCreateDialog, {
      props: { visible: true, editingId: 5 },
    })
    wrapper.vm.form.title = '测试会议'
    wrapper.vm.onSaveAsTemplate()
    expect(wrapper.emitted('save-template'), '编辑模式不应触发 save-template emit').toBeFalsy()
  })

  it('点击存为新模板 → emit save-template 携带 form 数据', async () => {
    const wrapper = mount(MeetingCreateDialog, {
      props: { visible: true, editingId: null },
    })
    // 设置 form 数据 (通过 vm 直接访问, 绕开 jsdom el-input 渲染)
    wrapper.vm.form.title = '周三组会'
    wrapper.vm.form.description = '周内复盘'
    wrapper.vm.form.agenda = ['议题 1', '议题 2', '']  // 含空字符串验证 filter
    wrapper.vm.form.participants = [1, 2]
    wrapper.vm.form.location = '会议室 A'
    // 调用 onSaveAsTemplate (直接调方法比 click 按钮更可靠)
    wrapper.vm.onSaveAsTemplate()
    await wrapper.vm.$nextTick()
    // 验证 emit
    const events = wrapper.emitted()
    expect(events['save-template'], '应 emit save-template').toBeTruthy()
    expect(events['save-template'][0][0]).toMatchObject({
      name: '周三组会',
      title_template: '周三组会',
      description: '周内复盘',
      default_duration_minutes: 60,
      default_location: '会议室 A',
      default_participant_ids: [1, 2],
    })
    // agenda 应过滤空字符串
    expect(events['save-template'][0][0].agenda).toEqual(['议题 1', '议题 2'])
  })

  it('无标题时点击存为新模板 → 不 emit + 弹 warning', async () => {
    const wrapper = mount(MeetingCreateDialog, {
      props: { visible: true, editingId: null }
    })
    wrapper.vm.form.title = ''
    wrapper.vm.onSaveAsTemplate()
    await wrapper.vm.$nextTick()
    const events = wrapper.emitted()
    expect(events['save-template'], '无标题不应 emit').toBeFalsy()
  })
})
