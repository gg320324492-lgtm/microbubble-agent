// 端到端测试: 真装载 MeetingView, 验证 el-popover :visible 受控模式真能开
import { mount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { nextTick, ref } from 'vue'
import ElementPlus from 'element-plus'

const makeStub = (name) => ({ default: { name, template: '<div class="stub-' + name.toLowerCase().replace(/[^a-z0-9]/g, '') + '"><slot /></div>' } })

// 所有 vi.mock 工厂都用字面量,不引用外部变量(vi.mock hoist 限制)
vi.mock('@/composables/useRecordingState', () => ({
  useRecordingState: () => ({
    recordingMeetingId: { value: null },
    startRecording: () => {},
    stopRecording: () => {},
  }),
}))
vi.mock('@/stores/member', () => ({
  useMemberStore: () => ({ members: [], fetchMembers: () => {} }),
}))
// 关键:deleteMeeting 用 spy 才能验证"真被调"
const deleteSpy = vi.fn(() => Promise.resolve({}))
vi.mock('@/composables/useMeeting', () => ({
  useMeeting: () => ({
    meetings: ref([{ id: 100, title: '测试会议', status: 'completed', start_time: '2026-07-08T10:00:00Z' }]),
    total: ref(1),
    currentPage: ref(1),
    pageSize: ref(20),
    loading: ref(false),
    keyword: ref(''),
    dateFrom: ref(''),
    dateTo: ref(''),
    currentMeeting: ref(null),
    fetchMeetings: () => {},
    createMeeting: () => {},
    updateMeeting: () => {},
    deleteMeeting: deleteSpy,
    updateAgenda: () => {},
  }),
}))
vi.mock('@/utils/task', () => ({
  getStatusType: () => 'success',
  getStatusLabel: () => '已完成',
}))
vi.mock('axios', () => ({
  default: {
    get: () => Promise.resolve({ data: { items: [], pagination: { total: 0 } } }),
    post: () => {}, put: () => {}, patch: () => {},
    delete: () => Promise.resolve({}),
  },
}))
const pushSpy = vi.fn(), replaceSpy = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushSpy, replace: replaceSpy }),
  useRoute: () => ({ query: {}, params: {} }),
}))

// 全部用独立工厂避免变量引用
vi.mock('@/components/common/TabStrip.vue', () => ({ default: { name: 'TabStrip', template: '<div class="stub-tabstrip" />' } }))
vi.mock('@/views/meeting/MeetingCreateDialog.vue', () => ({ default: { name: 'MeetingCreateDialog', template: '<div class="stub-meeting-createdialog" />' } }))
vi.mock('@/components/PasteAnalyzeDialog.vue', () => ({ default: { name: 'PasteAnalyzeDialog', template: '<div class="stub-paste" />' } }))
vi.mock('@/components/ProcessingDialog.vue', () => ({ default: { name: 'ProcessingDialog', template: '<div class="stub-proc" />' } }))
vi.mock('@/components/VoiceTestDialog.vue', () => ({ default: { name: 'VoiceTestDialog', template: '<div class="stub-vt" />' } }))
vi.mock('@/components/ParticipantAvatars.vue', () => ({ default: { name: 'ParticipantAvatars', template: '<div class="stub-avatars" />' } }))
vi.mock('@/components/meeting/MeetingMinutesDialog.vue', () => ({ default: { name: 'MeetingMinutesDialog', template: '<div class="stub-minutes" />' } }))

const MeetingView = (await import('@/views/MeetingView.vue')).default

describe('MeetingView e2e - 删除链路', () => {
  beforeEach(() => { pushSpy.mockClear(); replaceSpy.mockClear(); deleteSpy.mockClear() })

  it('点击删除按钮 -> 弹框打开 (popover DOM 出现) -> 点确定 -> deleteMeetingApi 被调', async () => {
    const wrapper = mount(MeetingView, {
      attachTo: document.body,
      global: { plugins: [ElementPlus] },
    })

    await nextTick()
    await new Promise(r => setTimeout(r, 100))

    console.log('[e2e] 初始 popover DOM 数:', document.querySelectorAll('.delete-meeting-popover').length)

    const delBtn = wrapper.find('[data-delete-ref-id="100"]')
    console.log('[e2e] 找到删除按钮:', delBtn.exists(), 'html:', delBtn.exists() ? delBtn.html().slice(0, 100) : 'NOT FOUND')

    if (!delBtn.exists()) {
      console.log('[e2e] ❌ 删除按钮找不到, 看下整个 wrapper html:')
      console.log(wrapper.html().slice(0, 2000))
    }

    expect(delBtn.exists()).toBe(true)

    await delBtn.trigger('click')
    await nextTick()
    await new Promise(r => setTimeout(r, 300))

    const popoverDom = document.querySelectorAll('.delete-meeting-popover')
    console.log('[e2e] 点击后 popover DOM 数:', popoverDom.length)
    Array.from(popoverDom).forEach((p, i) => {
      console.log(`  popover[${i}] display=${window.getComputedStyle(p).display} class="${p.className}" children=${p.children.length}`)
    })

    expect(popoverDom.length).toBeGreaterThan(0)  // 核心断言: 弹框真开

    if (popoverDom.length > 0) {
      const popoverContent = popoverDom[0]
      // 找"确定删除"按钮 (textContent 包含"确定删除")
      const btns = popoverContent.querySelectorAll('button')
      let confirmBtn = null
      btns.forEach((b, i) => {
        console.log(`  popover btn[${i}]: text="${b.textContent.trim()}"`)
        if (b.textContent.trim() === '确定删除') confirmBtn = b
      })

      if (confirmBtn) {
        console.log('[e2e] 点击"确定删除"前: deleteSpy 调用次数 =', deleteSpy.mock.calls.length)
        confirmBtn.click()  // 原生 click
        await nextTick()
        await new Promise(r => setTimeout(r, 300))
        console.log('[e2e] 点击"确定删除"后: deleteSpy 调用次数 =', deleteSpy.mock.calls.length)
        console.log('[e2e] deleteSpy 被调时的参数:', JSON.stringify(deleteSpy.mock.calls))

        // 弹框应已自动关闭
        const popoverAfter = document.querySelectorAll('.delete-meeting-popover[aria-hidden="false"]')
        console.log('[e2e] 确认后弹框是否关闭: aria-hidden=false 数量 =', popoverAfter.length)

        // 弹框虽然还在 DOM 中 (teleported div), 但 visible 应已切 false
        expect(deleteSpy).toHaveBeenCalled()
        expect(deleteSpy.mock.calls[0][0]).toBe(100)  // id=100
        console.log('[e2e] ✅ 整条链路 OK: 点击删除 → 弹框开 → 点确定 → deleteMeetingApi(100) 被调')
      } else {
        console.log('[e2e] ❌ 找不到"确定删除"按钮')
        expect(confirmBtn).not.toBeNull()
      }
    }

    wrapper.unmount()
  }, 10000)
})
