/**
 * 桌面端会议详情 —— 失败态 UI 回归测试 (2026-10-25)
 *
 * 背景: 会议 258 失败后, 桌面详情页只有一枚「处理失败」徽标 ——
 * 用户看不到原因、更不知道能做什么; 而后端早有 reprocess 补救能力, 前端一处都没调用。
 *
 * 本测试 mount **真实视图** (shallowMount, 子组件 stub 掉), 覆盖:
 * ① status=error + 无音频(258 现场) ⇒ 失败卡片 + 可读标题 + 「去听会页面上传」入口
 * ② 「去听会页面上传」真的跳 /meetings/room (有音频时这条路径不适用)
 * ③ status=error + 有音频 ⇒ 「重新处理」点击真的打 POST /api/v1/meetings/{id}/reprocess
 * ④ status=completed ⇒ 不渲染失败卡片 (不误伤正常会议)
 */
import { shallowMount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import MeetingDetailView from '../MeetingDetailView.vue'

const axiosMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
  patch: vi.fn(),
}))
const routerPush = vi.hoisted(() => vi.fn())

vi.mock('axios', () => ({ default: axiosMock }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '259' }, query: {}, push: routerPush }),
  useRouter: () => ({ push: routerPush, replace: vi.fn(), back: vi.fn() }),
}))
vi.mock('@/stores/member', () => ({
  useMemberStore: () => ({ fetchMembers: vi.fn(), members: [], memberInfo: {} }),
}))

const REASON_258 =
  '录音超过 30min 未 stop, (last_chunk_index=-1, total_chunks=None), ' +
  '[UA: Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 ' +
  '(KHTML, like Gecko) Version/26.6 Mobile/15E148 Safari/604.1]'

const MEETING_NO_AUDIO = {
  id: 259,
  title: '正在听会（ID 259）',
  status: 'error',
  error_reason: REASON_258,
  audio_url: null,
  last_chunk_index: -1,
  transcript: [],
  transcript_polished: [],
  speaker_stats: [],
  start_time: '2026-10-19T13:00:00',
  location: '三问园',
}

const MEETING_WITH_AUDIO = {
  ...MEETING_NO_AUDIO,
  id: 260,
  status: 'error',
  error_reason: 'merge failed: ffmpeg exited 1',
  audio_url: 'recordings/260/merged.m4a',
  last_chunk_index: 2,
}

const MEETING_OK = { ...MEETING_NO_AUDIO, id: 261, status: 'completed', error_reason: null }

async function mountView(meeting) {
  axiosMock.get.mockImplementation((url) => {
    if (String(url).includes('/meetings/259') || String(url).includes('/meetings/260') || String(url).includes('/meetings/261')) {
      return Promise.resolve({ data: meeting })
    }
    return Promise.resolve({ data: {} })
  })
  const wrapper = shallowMount(MeetingDetailView, {
    global: {
      stubs: {
        'el-icon': { template: '<i><slot /></i>' },
      },
    },
  })
  await flushPromises()
  await nextTick()
  return wrapper
}

describe('MeetingDetailView 失败态 UI', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('① status=error + 无音频(258 现场) ⇒ 失败卡片 + 可读标题 + 上传入口', async () => {
    const wrapper = await mountView(MEETING_NO_AUDIO)

    const card = wrapper.find('.failure-banner')
    expect(card.exists()).toBe(true)
    expect(wrapper.find('.failure-title').text()).toBe('录音没有正常结束')

    // 不得把裸技术串当主文案
    const detail = wrapper.find('.failure-detail').text()
    expect(detail).not.toContain('last_chunk_index')
    expect(detail).not.toContain('未 stop')

    // 无音频 ⇒ 不能给「重新处理」(后端会 400), 只能引导去上传
    const buttons = wrapper.findAll('.failure-actions button')
    expect(buttons.length).toBe(1)
    expect(buttons[0].text()).toContain('去听会页面上传')

    wrapper.unmount()
  })

  it('② 「去听会页面上传」真的跳到 /meetings/room', async () => {
    const wrapper = await mountView(MEETING_NO_AUDIO)

    await wrapper.find('.failure-actions button').trigger('click')
    expect(routerPush).toHaveBeenCalledWith('/meetings/room')

    wrapper.unmount()
  })

  it('③ status=error + 有音频 ⇒ 「重新处理」点击真的调 reprocess', async () => {
    const wrapper = await mountView(MEETING_WITH_AUDIO)

    expect(wrapper.find('.failure-banner').exists()).toBe(true)
    expect(wrapper.find('.failure-title').text()).toBe('音频合并失败')

    const btn = wrapper.find('.failure-actions button')
    expect(btn.text()).toContain('重新处理')

    axiosMock.post.mockResolvedValue({ data: { status: 'processing' } })
    await btn.trigger('click')
    await flushPromises()

    expect(axiosMock.post).toHaveBeenCalledWith('/api/v1/meetings/260/reprocess')

    wrapper.unmount()
  })

  it('④ status=completed ⇒ 不渲染失败卡片', async () => {
    const wrapper = await mountView(MEETING_OK)
    expect(wrapper.find('.failure-banner').exists()).toBe(false)
    wrapper.unmount()
  })
})
