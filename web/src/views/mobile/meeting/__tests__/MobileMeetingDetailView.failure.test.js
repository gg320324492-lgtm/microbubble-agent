/**
 * 移动端会议详情 —— 失败态 UI 回归测试 (2026-10-25)
 *
 * 背景: 会议 258 失败后, 移动端详情页只把裸技术串
 *   「录音超过 30min 未 stop, (last_chunk_index=-1, total_chunks=None), [UA: ...]」
 * 直接甩给用户, 既看不懂也不知道能做什么; 后端早有 reprocess 补救能力, 前端一处都没调用。
 *
 * 本测试 mount **真实视图** (不是内联复刻), 覆盖:
 * ① status=error + 无音频(258 现场) ⇒ 渲染失败卡片 + 可读标题 + 「去听会页面上传」入口
 * ② status=error + 有音频 ⇒ 渲染「重新处理」按钮, 点击真的打 POST /api/v1/meetings/{id}/reprocess
 * ③ status=completed ⇒ 不渲染失败卡片 (不误伤正常会议)
 * ④ 转录空态展示可读文案, 不再暴露裸技术串
 */
import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { nextTick } from 'vue'
// 静态导入: 动态 import 会把 SFC 编译时间算进第一个用例的 5s 超时里 (实测必超时)
import MobileMeetingDetailView from '../MobileMeetingDetailView.vue'

const axiosMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}))
const routerPush = vi.hoisted(() => vi.fn())

vi.mock('axios', () => ({ default: axiosMock }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '259' }, query: {} }),
  useRouter: () => ({ push: routerPush, replace: vi.fn(), back: vi.fn() }),
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

const MEETING_OK = {
  ...MEETING_NO_AUDIO,
  id: 261,
  status: 'completed',
  error_reason: null,
}

async function mountView(meeting) {
  axiosMock.get.mockResolvedValue({ data: meeting })
  const wrapper = mount(MobileMeetingDetailView, {
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

describe('MobileMeetingDetailView 失败态 UI', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('① status=error + 无音频(258 现场) ⇒ 失败卡片 + 可读标题 + 上传入口', async () => {
    const wrapper = await mountView(MEETING_NO_AUDIO)

    const card = wrapper.find('.failure-card')
    expect(card.exists()).toBe(true)

    const title = wrapper.find('.failure-title').text()
    expect(title).toBe('录音没有正常结束')

    // 不得把裸技术串当主文案
    const detail = wrapper.find('.failure-detail').text()
    expect(detail).not.toContain('last_chunk_index')
    expect(detail).not.toContain('未 stop')
    expect(detail.length).toBeGreaterThan(0)

    // 无音频 ⇒ 不能给「重新处理」(后端会 400), 只能引导去上传
    const buttons = wrapper.findAll('.failure-actions button')
    expect(buttons.length).toBe(1)
    expect(buttons[0].text()).toContain('去听会页面上传')

    wrapper.unmount()
  })

  it('② status=error + 有音频 ⇒ 「重新处理」按钮点击真的调 reprocess', async () => {
    const wrapper = await mountView(MEETING_WITH_AUDIO)

    expect(wrapper.find('.failure-card').exists()).toBe(true)
    expect(wrapper.find('.failure-title').text()).toBe('音频合并失败')

    const btn = wrapper.find('.failure-actions button')
    expect(btn.text()).toContain('重新处理')

    axiosMock.post.mockResolvedValue({ data: { status: 'processing' } })
    await btn.trigger('click')
    await flushPromises()

    expect(axiosMock.post).toHaveBeenCalledTimes(1)
    expect(axiosMock.post).toHaveBeenCalledWith('/api/v1/meetings/260/reprocess')

    wrapper.unmount()
  })

  it('③ status=completed ⇒ 不渲染失败卡片', async () => {
    const wrapper = await mountView(MEETING_OK)
    expect(wrapper.find('.failure-card').exists()).toBe(false)
    wrapper.unmount()
  })

  it('④ 转录空态展示可读文案, 不暴露裸技术串', async () => {
    const wrapper = await mountView(MEETING_NO_AUDIO)

    // 转录 tab 默认不激活 ⇒ 必须先切过去, 否则断言的是"未渲染"而非"渲染错"
    wrapper.vm.activeTab = 'transcript'
    await nextTick()

    const hint = wrapper.find('.empty-hint.error')
    expect(hint.exists()).toBe(true)
    expect(hint.text()).toContain('录音没有正常结束')
    expect(hint.text()).not.toContain('last_chunk_index')

    wrapper.unmount()
  })
})
