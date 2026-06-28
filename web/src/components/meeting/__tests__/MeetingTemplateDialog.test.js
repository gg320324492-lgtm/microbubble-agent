/**
 * MeetingTemplateDialog.test.js — v77 P2.6-F.2 Step 3 新增 Vitest 单测
 *
 * ★ TDZ 防御测试（commit 7f0ac109 教训第 1 次复用）
 *   resetForm 必须 function declaration 而非 const arrow，
 *   watch(immediate: true) 同步触发时若 resetForm 还未声明 → TDZ 报错
 *
 * 模式：参考 MeetingCreateDialog.test.js — 不注册 el-* 组件，只测脚本逻辑
 *       jsdom + el-dialog 渲染问题（Cannot read properties of undefined 'setAttribute'）通过
 *       不挂载 el-* 子组件规避，专注测 props / watch / emit / submit 行为
 *
 * 覆盖:
 * - TDZ 防御: mount 时 editingTemplate=null 触发 immediate watch 调 resetForm, 不能 throw
 * - TDZ 防御: mount 时 editingTemplate=Object 触发 watch 回填表单
 * - 多次 mount/unmount 不 throw
 * - watch 回填: editingTemplate.name → form.name
 * - watch 回填: editingTemplate.agenda 数组展开
 * - handleSubmit 空 name → 不调 axios
 * - handleSubmit POST: editingTemplate=null → POST
 * - handleSubmit PUT: editingTemplate.id=N → PUT /N
 * - emit saved + update:modelValue=false 提交成功
 * - defineExpose resetForm 清除 form
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import axios from 'axios'
import MeetingTemplateDialog from '../MeetingTemplateDialog.vue'

vi.mock('axios')

const mockMembers = [
  { id: 1, name: '王天志' },
  { id: 2, name: '杜同贺' },
]

describe('MeetingTemplateDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ★ TDZ 防御核心测试
  it('does NOT throw TDZ on mount with editingTemplate=null', () => {
    expect(() => {
      mount(MeetingTemplateDialog, {
        props: { modelValue: true, editingTemplate: null, members: mockMembers, isMobile: false },
      })
    }).not.toThrow()
  })

  it('does NOT throw TDZ on mount with editingTemplate=Object', () => {
    expect(() => {
      mount(MeetingTemplateDialog, {
        props: {
          modelValue: true,
          editingTemplate: { id: 1, name: '原名', description: '原说明', default_duration_minutes: 90, agenda: ['议题 1'] },
          members: mockMembers,
          isMobile: false,
        },
      })
    }).not.toThrow()
  })

  it('does NOT throw on multiple rapid mount/unmount cycles', () => {
    for (let i = 0; i < 5; i++) {
      const w = mount(MeetingTemplateDialog, {
        props: { modelValue: true, editingTemplate: null, members: mockMembers, isMobile: false },
      })
      w.unmount()
    }
  })

  it('watch fills form when editingTemplate is provided', () => {
    const wrapper = mount(MeetingTemplateDialog, {
      props: {
        modelValue: true,
        editingTemplate: {
          id: 5,
          name: '组会模板',
          description: '周内复盘',
          title_template: '组会 - {date}',
          default_duration_minutes: 90,
          default_location: '会议室A',
          default_participant_ids: [1, 2],
          agenda: ['议题 1', '议题 2', '议题 3'],
        },
        members: mockMembers,
        isMobile: false,
      },
    })
    expect(wrapper.vm.form.name).toBe('组会模板')
    expect(wrapper.vm.form.description).toBe('周内复盘')
    expect(wrapper.vm.form.title_template).toBe('组会 - {date}')
    expect(wrapper.vm.form.default_duration_minutes).toBe(90)
    expect(wrapper.vm.form.default_location).toBe('会议室A')
    expect(wrapper.vm.form.default_participant_ids).toEqual([1, 2])
    expect(wrapper.vm.form.agenda).toEqual(['议题 1', '议题 2', '议题 3'])
  })

  it('watch resets form when editingTemplate becomes null (open dialog in create mode)', async () => {
    const wrapper = mount(MeetingTemplateDialog, {
      props: { modelValue: true, editingTemplate: { id: 1, name: 'dirty' }, members: mockMembers, isMobile: false },
    })
    expect(wrapper.vm.form.name).toBe('dirty')
    await wrapper.setProps({ editingTemplate: null })
    expect(wrapper.vm.form.name).toBe('')
    expect(wrapper.vm.form.default_duration_minutes).toBe(60)
    expect(wrapper.vm.form.agenda).toEqual([])
  })

  it('handleSubmit with empty name → does not call axios', async () => {
    const wrapper = mount(MeetingTemplateDialog, {
      props: { modelValue: true, editingTemplate: null, members: mockMembers, isMobile: false },
    })
    await wrapper.vm.handleSubmit()
    await flushPromises()
    expect(axios.post).not.toHaveBeenCalled()
    expect(axios.put).not.toHaveBeenCalled()
  })

  it('handleSubmit POST /api/v1/meeting-templates when editingTemplate=null', async () => {
    axios.post.mockResolvedValue({ data: { id: 99, name: '新模板' } })
    const wrapper = mount(MeetingTemplateDialog, {
      props: { modelValue: true, editingTemplate: null, members: mockMembers, isMobile: false },
    })
    wrapper.vm.form.name = '测试模板'
    wrapper.vm.form.default_duration_minutes = 60
    await wrapper.vm.handleSubmit()
    await flushPromises()
    expect(axios.post).toHaveBeenCalledWith('/api/v1/meeting-templates', expect.objectContaining({ name: '测试模板' }))
  })

  it('handleSubmit PUT /api/v1/meeting-templates/{id} when editingTemplate set', async () => {
    axios.put.mockResolvedValue({ data: { id: 1, name: '更新' } })
    const wrapper = mount(MeetingTemplateDialog, {
      props: {
        modelValue: true,
        editingTemplate: { id: 1, name: '原名' },
        members: mockMembers,
        isMobile: false,
      },
    })
    await wrapper.vm.handleSubmit()
    await flushPromises()
    expect(axios.put).toHaveBeenCalledWith('/api/v1/meeting-templates/1', expect.any(Object))
  })

  it('emits update:modelValue=false and saved after successful submit', async () => {
    axios.post.mockResolvedValue({ data: { id: 100, name: 'x' } })
    const wrapper = mount(MeetingTemplateDialog, {
      props: { modelValue: true, editingTemplate: null, members: mockMembers, isMobile: false },
    })
    wrapper.vm.form.name = 'Test'
    await wrapper.vm.handleSubmit()
    await flushPromises()
    const events = wrapper.emitted()
    expect(events['update:modelValue']).toBeTruthy()
    expect(events['update:modelValue'][0]).toEqual([false])
    expect(events.saved).toBeTruthy()
  })

  it('defineExpose exposes resetForm and handleSubmit', () => {
    const wrapper = mount(MeetingTemplateDialog, {
      props: { modelValue: true, editingTemplate: null, members: mockMembers, isMobile: false },
    })
    expect(typeof wrapper.vm.resetForm).toBe('function')
    expect(typeof wrapper.vm.handleSubmit).toBe('function')
  })

  it('resetForm clears form state to defaults', () => {
    const wrapper = mount(MeetingTemplateDialog, {
      props: { modelValue: true, editingTemplate: null, members: mockMembers, isMobile: false },
    })
    wrapper.vm.form.name = 'dirty'
    wrapper.vm.form.default_duration_minutes = 999
    wrapper.vm.form.agenda = ['x', 'y']
    wrapper.vm.form.default_participant_ids = [1, 2]
    wrapper.vm.resetForm()
    expect(wrapper.vm.form.name).toBe('')
    expect(wrapper.vm.form.default_duration_minutes).toBe(60)
    expect(wrapper.vm.form.agenda).toEqual([])
    expect(wrapper.vm.form.default_participant_ids).toEqual([])
  })

  it('does not throw when saving fails (network error)', async () => {
    axios.post.mockRejectedValue(new Error('Network Error'))
    const wrapper = mount(MeetingTemplateDialog, {
      props: { modelValue: true, editingTemplate: null, members: mockMembers, isMobile: false },
    })
    wrapper.vm.form.name = 'Test'
    await wrapper.vm.handleSubmit()
    await flushPromises()
    expect(axios.post).toHaveBeenCalled()
    expect(wrapper.emitted('saved')).toBeFalsy()
    expect(wrapper.vm.saving).toBe(false)
  })
})