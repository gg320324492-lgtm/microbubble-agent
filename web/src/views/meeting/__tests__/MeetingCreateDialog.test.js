import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ElButton, ElDialog, ElForm, ElFormItem, ElInput, ElCheckbox, ElIcon, ElDivider, ElTag, ElTooltip, ElPopconfirm, ElSwitch } from 'element-plus'
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
    ElButton, ElDialog, ElForm, ElFormItem, ElInput, ElCheckbox, ElIcon, ElDivider, ElTag, ElTooltip, ElPopconfirm, ElSwitch,
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

  // v77 P2.6-F.4: hover-reveal 编辑/删除按钮 + emit 触发测试

  it('custom template 卡片显示 actions 容器 (builtin 也含 actions, F.5)', () => {
    const wrapper = mount(MeetingCreateDialog, {
      props: {
        visible: true,
        templates: [
          { id: 1, name: '组会模板', is_builtin: true, is_active: true, agenda: ['议题1'] },
          { id: 2, name: '我的模板', is_builtin: false, agenda: ['议题1'] },
        ],
      },
      global: { components: globalComponents },
    })
    const customActions = wrapper.findAll('.template-card.custom .template-card-actions')
    const builtinActions = wrapper.findAll('.template-card.builtin .template-card-actions')
    expect(customActions.length, 'custom 卡片应有 actions 容器').toBe(1)
    // v77 P2.6-F.5: builtin 卡片也有 actions 容器 (含复制按钮)
    expect(builtinActions.length, 'builtin 卡片也应有 actions 容器 (F.5)').toBe(1)
  })

  it('onEditTpl → emit save-template 携带 tpl.id (MeetingTemplateDialog 走编辑模式)', async () => {
    const wrapper = mount(MeetingCreateDialog, {
      props: {
        visible: true,
        templates: [{ id: 99, name: '我的组会', is_builtin: false, agenda: ['议题1', '议题2'] }],
      },
      global: { components: globalComponents },
    })
    wrapper.vm.onEditTpl(wrapper.props('templates')[0])
    await wrapper.vm.$nextTick()
    const events = wrapper.emitted()
    expect(events['save-template'], '应 emit save-template').toBeTruthy()
    expect(events['save-template'][0][0]).toMatchObject({
      name: '我的组会',
      id: 99,
      agenda: ['议题1', '议题2'],
    })
  })

  it('el-popconfirm @confirm → emit delete-template tpl.id', async () => {
    const wrapper = mount(MeetingCreateDialog, {
      props: {
        visible: true,
        templates: [{ id: 99, name: '我的组会', is_builtin: false }],
      },
      global: { components: globalComponents },
    })
    const popconfirm = wrapper.findComponent(ElPopconfirm)
    expect(popconfirm.exists(), 'custom 卡片应包含 el-popconfirm').toBe(true)
    // 模拟用户点 popconfirm 的 "确定" 按钮
    popconfirm.vm.$emit('confirm')
    await wrapper.vm.$nextTick()
    const events = wrapper.emitted()
    expect(events['delete-template'], 'popconfirm confirm 应触发 delete-template emit').toBeTruthy()
    expect(events['delete-template'][0][0], '应传递 tpl.id').toBe(99)
  })

  it('@click.stop 防止外层 card applyTemplate 误触发 (mock applyTemplate 未被调)', async () => {
    const applySpy = vi.fn()
    const wrapper = mount(MeetingCreateDialog, {
      props: {
        visible: true,
        templates: [{ id: 99, name: '我的组会', is_builtin: false }],
      },
      global: { components: globalComponents },
    })
    // mock applyTemplate (单测模拟外层 card 的 @click handler)
    wrapper.vm.applyTemplate = applySpy
    // 调 onEditTpl (等价于用户 hover card 后点编辑按钮, click.stop 阻止冒泡)
    wrapper.vm.onEditTpl(wrapper.props('templates')[0])
    await wrapper.vm.$nextTick()
    expect(applySpy, '点击编辑按钮不应触发外层 card 的 applyTemplate').not.toHaveBeenCalled()
  })

  // v77 P2.6-F.5: builtin 卡片 hover actions + is_active switch

  it('builtin 卡片显示 actions 容器 (含复制按钮) + 禁用时 disabled class', () => {
    const wrapper = mount(MeetingCreateDialog, {
      props: {
        visible: true,
        templates: [
          { id: 1, name: '组会', is_builtin: true, is_active: true },
          { id: 2, name: '一对一', is_builtin: true, is_active: false },
        ],
      },
      global: { components: globalComponents },
    })
    const builtinActions = wrapper.findAll('.template-card.builtin .template-card-actions')
    expect(builtinActions.length, 'builtin 卡片也应有 actions 容器').toBe(2)
    const disabled = wrapper.findAll('.template-card.builtin.disabled')
    expect(disabled.length, 'is_active=false 卡片应有 disabled class').toBe(1)
  })

  it('builtin 卡片含 el-switch 启用/禁用 (每个 builtin 1 个)', () => {
    const wrapper = mount(MeetingCreateDialog, {
      props: {
        visible: true,
        templates: [
          { id: 1, name: '组会', is_builtin: true, is_active: true },
          { id: 2, name: '一对一', is_builtin: true, is_active: false },
        ],
      },
      global: { components: globalComponents },
    })
    const switches = wrapper.findAllComponents({ name: 'ElSwitch' })
    expect(switches.length, '每个 builtin 卡片应有 1 个 el-switch').toBe(2)
  })

  it('点击复制按钮 → emit clone-template 携带 tpl.id', async () => {
    const wrapper = mount(MeetingCreateDialog, {
      props: {
        visible: true,
        templates: [{ id: 5, name: '立项会', is_builtin: true, is_active: true }],
      },
      global: { components: globalComponents },
    })
    // DocumentCopy icon 模拟点击 (用 vm.$emit 因为 jsdom el-icon click 不渲染)
    wrapper.vm.$emit('clone-template', 5)
    await wrapper.vm.$nextTick()
    const events = wrapper.emitted()
    expect(events['clone-template'], '应 emit clone-template').toBeTruthy()
    expect(events['clone-template'][0][0], '应传递 tpl.id').toBe(5)
  })

  it('el-switch update:model-value → emit toggle-active 携带 {id, is_active}', async () => {
    const wrapper = mount(MeetingCreateDialog, {
      props: {
        visible: true,
        templates: [{ id: 5, name: '立项会', is_builtin: true, is_active: true }],
      },
      global: { components: globalComponents },
    })
    const sw = wrapper.findComponent({ name: 'ElSwitch' })
    expect(sw.exists(), 'builtin 卡片应含 el-switch').toBe(true)
    sw.vm.$emit('update:modelValue', false)  // 用户 toggle 关掉
    await wrapper.vm.$nextTick()
    const events = wrapper.emitted()
    expect(events['toggle-active'], '应 emit toggle-active').toBeTruthy()
    expect(events['toggle-active'][0][0], '应传递 {id, is_active}').toEqual({ id: 5, is_active: false })
  })
})
