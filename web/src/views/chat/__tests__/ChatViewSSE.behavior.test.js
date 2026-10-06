/**
 * ChatViewSSE mount 级行为测试 (L-1 阶段 1)
 *
 * 与既有 ChatViewSSEA11y / W100Plus61 / W100Plus55 的 readFileSync 源码钉互补:
 * 本文件真实挂载组件、驱动 script 的可观察行为 (发送流程 / SSE 消息流 mock /
 * 流式停止互换 / 会话切换+断线续答轮询 / 对话内搜索 / 错误态), 断言 DOM 与
 * composable 调用 —— 不读一行源码。
 *
 * 拆分依赖 (2026-10-07 实测):
 * - ChatMessageRow 的模块图含 /lab-logo.png 公共资产, vitest 下 file URL 解析
 *   在 Windows 炸 → 以 vi.mock 工厂替换 (行渲染契约用 props 断言)。
 * - vue-router / useChatStream / useNetworkStatus / warmup / chatHistory 为受控
 *   mock; 其余 (stores / 顶栏 / 搜索 / 附件 / 快捷键) 走真实 script。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { ElMessage } from 'element-plus'

import ChatViewSSE from '../ChatViewSSE.vue'
import { useChatStream } from '@/composables/chat/useChatStream'
import { useNetworkStatus } from '@/composables/useNetworkStatus'
import { chatHistoryApi } from '@/api/chatHistory'
import { useChatSessionsStore } from '@/stores/chatSessions'

// ---------------------------------------------------------------------------
// mocks
// ---------------------------------------------------------------------------
const routerMock = vi.hoisted(() => ({ push: vi.fn() }))

vi.mock('vue-router', () => ({ useRouter: () => routerMock }))

vi.mock('@/composables/chat/useChatStream', async () => {
  const { ref: r } = await import('vue')
  const state = {
    sessionId: r(''),
    messages: r([]),
    isCurrentSessionSending: r(false),
    onCreateSession: vi.fn(),
    onSwitchSession: vi.fn(),
    clearChat: vi.fn(),
    sendMessage: vi.fn(async () => {}),
    stopGeneration: vi.fn(),
    playTTS: vi.fn(),
    asrRecognize: vi.fn(async () => ''),
    resendUserMessage: vi.fn(),
    fetchSessionFromServer: vi.fn(async () => {}),
  }
  return { useChatStream: () => state }
})

vi.mock('@/composables/useNetworkStatus', async () => {
  const { ref: r } = await import('vue')
  const online = r(true)
  const net = { online, effectiveType: r('4g'), status: r('online'), pendingCount: r(0) }
  return {
    useNetworkStatus: () => ({ ...net, setPendingCount: () => {} }),
    getNetworkStatus: () => net,
    markReachable: () => { online.value = true },
    markUnreachable: () => { online.value = false },
    _resetForTesting: () => { online.value = true },
  }
})

vi.mock('@/api/agent/warmup', () => ({
  warmupChatModel: vi.fn(async () => {}),
  resetWarmupForTest: vi.fn(),
}))

vi.mock('@/api/chatHistory', () => ({
  chatHistoryApi: {
    generationStatus: vi.fn(async () => ({ generating: false })),
    listSessions: vi.fn(async () => []),
    getSession: vi.fn(async () => ({})),
    listMessages: vi.fn(async () => []),
    exportSession: vi.fn(async () => ''),
    appendMessage: vi.fn(async () => ({})),
  },
}))

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    ElMessage: {
      info: vi.fn(),
      success: vi.fn(),
      warning: vi.fn(),
      error: vi.fn(),
    },
  }
})

vi.mock('@/components/chat/ChatMessageRow.vue', () => ({
  default: {
    name: 'ChatMessageRow',
    props: {
      msg: { type: Object, default: null },
      prevTimestamp: { type: [String, Date], default: null },
      sessionId: { type: String, default: '' },
      showThinking: { type: Boolean, default: false },
      allMessages: { type: Array, default: () => [] },
      virtualTop: { type: Number, default: undefined },
      virtualMode: { type: Boolean, default: false },
    },
    emits: [
      'tool-jump', 'regenerate', 'copy', 'pro-entry-click',
      'image-open', 'tts-play', 'follow-up-click', 'quote', 'edit-send',
    ],
    template: `<div class="stub-msg-row"><div class="content">{{ msg && msg.content }}</div></div>`,
  },
}))

// ---------------------------------------------------------------------------
// 环境垫片 (jsdom 缺口)
// ---------------------------------------------------------------------------
if (typeof globalThis.requestAnimationFrame === 'undefined') {
  globalThis.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0)
  globalThis.cancelAnimationFrame = (id) => clearTimeout(id)
}
if (typeof Element.prototype.scrollIntoView !== 'function') {
  Element.prototype.scrollIntoView = () => {}
}
// jsdom 无 URL.createObjectURL (图片选择需要)
if (typeof URL.createObjectURL !== 'function') {
  URL.createObjectURL = () => 'blob:mock-url'
}

// ---------------------------------------------------------------------------
// 受控 stub 组件
// ---------------------------------------------------------------------------
const SessionSidebarStub = {
  name: 'SessionSidebar',
  props: { collapsed: { type: Boolean, default: false } },
  emits: ['create', 'switch', 'share', 'export', 'edit-tags'],
  template: `<aside class="stub-sidebar" :data-collapsed="collapsed">
    <button class="stub-switch" type="button" @click="$emit('switch', 'sess-2')">切到 sess-2</button>
    <button class="stub-share" type="button" @click="$emit('share', { id: 'sess-9' })">分享</button>
  </aside>`,
}

const ChatBreadcrumbStub = {
  name: 'ChatBreadcrumb',
  props: { status: { type: String, default: 'idle' } },
  template: `<span class="stub-breadcrumb" :data-status="status" />`,
}

const InputToolPanelStub = {
  name: 'InputToolPanel',
  props: {
    visible: { type: Boolean, default: false },
    webSearchOn: { type: Boolean, default: false },
  },
  emits: ['update:visible', 'pick-image', 'pick-file', 'pick-from-drive', 'toggle-web-search', 'set-deep-research'],
  template: `<div class="stub-tool-panel">
    <button class="stub-tool-web" type="button" @click="$emit('toggle-web-search')">web</button>
    <button class="stub-tool-drive" type="button" @click="$emit('pick-from-drive')">drive</button>
    <button class="stub-tool-file" type="button" @click="$emit('pick-file')">file</button>
  </div>`,
}

const SearchPaletteStub = {
  name: 'SearchPalette',
  props: { modelValue: { type: Boolean, default: false } },
  emits: ['update:modelValue', 'select'],
  template: `<div class="stub-palette" :data-open="modelValue" />`,
}

const ShareDialogStub = {
  name: 'ShareDialog',
  props: { modelValue: { type: Boolean, default: false }, session: { type: Object, default: null } },
  emits: ['update:modelValue'],
  template: `<div class="stub-share-dialog" :data-session="session && session.id" />`,
}

const ContextPanelStub = {
  name: 'ContextPanel',
  props: { messages: { type: Array, default: () => [] } },
  template: `<div class="stub-context-panel" :data-count="messages.length" />`,
}

const VoiceRecorderStub = {
  name: 'VoiceRecorder',
  emits: ['record-start', 'record-stop', 'record-error'],
  template: `<div class="stub-voice-recorder" />`,
}

const mountView = () =>
  mount(ChatViewSSE, {
    attachTo: document.body,
    global: {
      stubs: {
        SessionSidebar: SessionSidebarStub,
        ChatBreadcrumb: ChatBreadcrumbStub,
        InputToolPanel: InputToolPanelStub,
        SearchPalette: SearchPaletteStub,
        ShareDialog: ShareDialogStub,
        ExportDialog: true,
        TagsEditor: true,
        ContextPanel: ContextPanelStub,
        VoiceRecorder: VoiceRecorderStub,
        ThinkingModeSwitch: true,
        'el-icon': { template: '<i class="stub-icon"><slot /></i>' },
        'el-avatar': { template: '<div class="stub-avatar"><slot /></div>' },
      },
    },
  })

const mkMsg = (id, role, content, timestamp = '2026-10-07T08:00:00.000Z') => ({
  id, role, content, timestamp,
})

// ---------------------------------------------------------------------------
// 共享受控状态
// ---------------------------------------------------------------------------
const stream = useChatStream()
const net = useNetworkStatus()

let wrapper = null

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  document.body.innerHTML = ''
  stream.sessionId.value = ''
  stream.messages.value = []
  stream.isCurrentSessionSending.value = false
  stream.sendMessage.mockImplementation(async () => {})
  chatHistoryApi.generationStatus.mockResolvedValue({ generating: false })
  net.online.value = true
  wrapper = null
})

afterEach(() => {
  if (wrapper && wrapper.unmount) {
    try { wrapper.unmount() } catch { /* 已卸载 */ }
  }
  wrapper = null
  document.body.innerHTML = ''
})

// ---------------------------------------------------------------------------
// 1. 渲染骨架 / a11y (行为版, 接住 ChatViewSSEA11y ①② 静态钉)
// ---------------------------------------------------------------------------
describe('ChatViewSSE 渲染骨架 (mount 级行为)', () => {
  it('skip-link 是文档首个可聚焦元素, 指向 #chat-main; 主区域 role=main', async () => {
    wrapper = mountView()
    await nextTick()
    const focusables = document.querySelectorAll(
      'a[href], button, input, textarea, select, [tabindex]:not([tabindex="-1"])'
    )
    const skip = wrapper.find('[data-testid="skip-link"]')
    expect(skip.exists()).toBe(true)
    expect(focusables[0]).toBe(skip.element)
    expect(skip.attributes('href')).toBe('#chat-main')
    const main = wrapper.find('#chat-main')
    expect(main.exists()).toBe(true)
    expect(main.attributes('role')).toBe('main')
    expect(main.attributes('aria-label')).toBe('聊天对话主区域')
  })

  it('输入提示文案渲染 "Enter 发送 · Shift+Enter 换行"', async () => {
    wrapper = mountView()
    expect(wrapper.find('.input-hint').text()).toBe('Enter 发送 · Shift+Enter 换行')
  })

  it('网络断线横幅随 online 状态显隐', async () => {
    wrapper = mountView()
    await nextTick()
    expect(wrapper.find('.network-banner').exists()).toBe(false)
    net.online.value = false
    await nextTick()
    expect(wrapper.find('.network-banner').text()).toContain('网络已断开')
    net.online.value = true
    await nextTick()
    expect(wrapper.find('.network-banner').exists()).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// 2. 发送流程 (script 的核心可观察行为)
// ---------------------------------------------------------------------------
describe('ChatViewSSE 发送流程', () => {
  it('空输入禁用发送; 输入后点击发送 → sendMessage 收到文本且输入清空', async () => {
    wrapper = mountView()
    await nextTick()
    const btn = wrapper.find('#chat-send-btn')
    expect(btn.exists()).toBe(true)
    expect(btn.attributes('disabled')).toBeDefined()

    const ta = wrapper.find('#chat-input-textarea')
    await ta.setValue('你好小气')
    expect(wrapper.find('#chat-send-btn').attributes('disabled')).toBeUndefined()

    await wrapper.find('#chat-send-btn').trigger('click')
    await flushPromises()
    expect(stream.sendMessage).toHaveBeenCalledTimes(1)
    expect(stream.sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({ text: '你好小气', webSearchOn: false })
    )
    expect(ta.element.value).toBe('')
  })

  it('Enter 发送, Shift+Enter 不发送 (keydown 守卫)', async () => {
    wrapper = mountView()
    const ta = wrapper.find('#chat-input-textarea')
    await ta.setValue('abc')

    await ta.trigger('keydown', { key: 'Enter', shiftKey: true })
    await flushPromises()
    expect(stream.sendMessage).not.toHaveBeenCalled()

    await ta.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(stream.sendMessage).toHaveBeenCalledTimes(1)
    expect(stream.sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({ text: 'abc' })
    )
  })

  it('sendMessage 底层 reject 时组件不炸、输入已清 (错误态吞掉)', async () => {
    wrapper = mountView()
    stream.sendMessage.mockRejectedValueOnce(new Error('SSE connection lost'))
    const ta = wrapper.find('#chat-input-textarea')
    await ta.setValue('会失败的消息')
    await wrapper.find('#chat-send-btn').trigger('click')
    await flushPromises()
    expect(stream.sendMessage).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.chat-immersive').exists()).toBe(true)
    expect(ta.element.value).toBe('')
  })

  it('流式生成中: 发送按钮换停止按钮 + 面包屑 generating; 点停止 → stopGeneration', async () => {
    wrapper = mountView()
    stream.isCurrentSessionSending.value = true
    await nextTick()

    expect(wrapper.find('#chat-send-btn').exists()).toBe(false)
    expect(wrapper.find('#chat-stop-btn').exists()).toBe(true)
    expect(wrapper.find('.stub-breadcrumb').attributes('data-status')).toBe('generating')

    await wrapper.find('#chat-stop-btn').trigger('click')
    expect(stream.stopGeneration).toHaveBeenCalledTimes(1)

    stream.isCurrentSessionSending.value = false
    await nextTick()
    expect(wrapper.find('#chat-send-btn').exists()).toBe(true)
    expect(wrapper.find('#chat-stop-btn').exists()).toBe(false)
    expect(wrapper.find('.stub-breadcrumb').attributes('data-status')).toBe('idle')
  })
})

// ---------------------------------------------------------------------------
// 3. SSE 消息流 (mock 驱动) + 消息行接线
// ---------------------------------------------------------------------------
describe('ChatViewSSE SSE 消息流与消息行接线', () => {
  it('messages 增长驱动消息行渲染; welcome-hero 只在恰 1 条时出现', async () => {
    wrapper = mountView()
    stream.messages.value = [mkMsg('m1', 'user', '第一问')]
    await nextTick()
    expect(wrapper.findAll('.stub-msg-row')).toHaveLength(1)
    expect(wrapper.find('.welcome-hero').exists()).toBe(true)
    expect(wrapper.findAll('.quick-btn')).toHaveLength(4)

    stream.messages.value = [
      mkMsg('m1', 'user', '第一问'),
      mkMsg('m2', 'assistant', '第一答'),
    ]
    await nextTick()
    expect(wrapper.findAll('.stub-msg-row')).toHaveLength(2)
    expect(wrapper.find('.welcome-hero').exists()).toBe(false)
  })

  it('welcome-hero 快捷提问点击 → sendMessage 带该条文案', async () => {
    wrapper = mountView()
    stream.messages.value = [mkMsg('m1', 'user', 'x')]
    await nextTick()
    const quick = wrapper.findAll('.quick-btn')
    expect(quick).toHaveLength(4)
    await quick[0].trigger('click')
    await flushPromises()
    expect(stream.sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({ text: '我最近有什么任务？' })
    )
  })

  it('每条消息以 msg + prev-timestamp 接入 ChatMessageRow (时间分隔线数据源)', async () => {
    wrapper = mountView()
    const m1 = mkMsg('m1', 'user', 'A', '2026-10-06T08:00:00.000Z')
    const m2 = mkMsg('m2', 'assistant', 'B', '2026-10-07T08:00:00.000Z')
    stream.messages.value = [m1, m2]
    await nextTick()

    const rows = wrapper.findAllComponents({ name: 'ChatMessageRow' })
    expect(rows).toHaveLength(2)
    expect(rows[0].props('msg')).toStrictEqual(m1)
    expect(rows[0].props('prevTimestamp')).toBeNull()
    expect(rows[1].props('msg')).toStrictEqual(m2)
    expect(rows[1].props('prevTimestamp')).toBe(m1.timestamp)
    expect(rows[0].props('allMessages')).toStrictEqual([m1, m2])
  })

  it('侧栏 switch 事件 → onSwitchSession; sessionId 就绪即触发断线续答轮询', async () => {
    wrapper = mountView()
    await wrapper.find('.stub-switch').trigger('click')
    expect(stream.onSwitchSession).toHaveBeenCalledWith('sess-2')

    stream.sessionId.value = 'sess-2'
    await flushPromises()
    expect(chatHistoryApi.generationStatus).toHaveBeenCalledWith('sess-2')
  })

  it('分享入口 → ShareDialog 挂载并携带 session', async () => {
    wrapper = mountView()
    await wrapper.find('.stub-share').trigger('click')
    await nextTick()
    expect(wrapper.find('.stub-share-dialog').exists()).toBe(true)
    expect(wrapper.find('.stub-share-dialog').attributes('data-session')).toBe('sess-9')
  })
})

// ---------------------------------------------------------------------------
// 4. 对话内搜索 (doSearch / 清除 / 快捷键 —— script 重逻辑)
// ---------------------------------------------------------------------------
describe('ChatViewSSE 对话内搜索', () => {
  it('输入关键词 → DOM 高亮 + 计数; 下一条导航; 清除按钮复位', async () => {
    wrapper = mountView()
    stream.messages.value = [
      mkMsg('m1', 'user', 'zeta 电位怎么测'),
      mkMsg('m2', 'assistant', 'zeta potential 受 pH 影响'),
    ]
    await nextTick()

    const input = wrapper.find('#chat-header-search')
    await input.setValue('zeta')
    await nextTick()
    expect(wrapper.findAll('.search-highlight')).toHaveLength(2)
    expect(wrapper.find('.hsp-count').text()).toBe('1/2')

    // Enter → searchNav(1) → 2/2
    await input.trigger('keydown', { key: 'Enter' })
    await nextTick()
    expect(wrapper.find('.hsp-count').text()).toBe('2/2')

    // 清除按钮 → 高亮还原 + 输入清空
    await wrapper.find('.hsp-clear').trigger('click')
    await nextTick()
    expect(wrapper.findAll('.search-highlight')).toHaveLength(0)
    expect(wrapper.find('#chat-header-search').element.value).toBe('')
    expect(wrapper.find('.hsp-count').exists()).toBe(false)
  })

  it('无匹配时不出计数, 高亮为 0', async () => {
    wrapper = mountView()
    stream.messages.value = [mkMsg('m1', 'user', '无关内容')]
    await nextTick()
    await wrapper.find('#chat-header-search').setValue('不存在的词')
    await nextTick()
    expect(wrapper.findAll('.search-highlight')).toHaveLength(0)
    expect(wrapper.find('.hsp-count').exists()).toBe(false)
  })

  it('Ctrl+F 聚焦搜索框; mod+k 开 / Esc 关全局搜索面板', async () => {
    wrapper = mountView()
    await nextTick()

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'f', ctrlKey: true }))
    await nextTick()
    await nextTick()
    expect(document.activeElement).toBe(wrapper.find('#chat-header-search').element)

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true }))
    await nextTick()
    expect(wrapper.find('.stub-palette').attributes('data-open')).toBe('true')

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await nextTick()
    expect(wrapper.find('.stub-palette').attributes('data-open')).toBe('false')
  })
})

// ---------------------------------------------------------------------------
// 5. 顶栏 / 工具面板 / 附件 (script UI 状态)
// ---------------------------------------------------------------------------
describe('ChatViewSSE 顶栏与工具面板', () => {
  it('侧栏折叠按钮: aria-label 与 sidebarCollapsed 同步翻转', async () => {
    wrapper = mountView()
    const toggle = wrapper.find('#chat-header-sidebar-toggle')
    expect(toggle.attributes('aria-label')).toBe('收起侧栏')
    expect(wrapper.find('.stub-sidebar').attributes('data-collapsed')).toBe('false')

    await toggle.trigger('click')
    await nextTick()
    expect(wrapper.find('#chat-header-sidebar-toggle').attributes('aria-label')).toBe('展开侧栏')
    expect(wrapper.find('.stub-sidebar').attributes('data-collapsed')).toBe('true')
  })

  it('新建对话 → chatSessionsStore 落一条新会话', async () => {
    wrapper = mountView()
    const store = useChatSessionsStore()
    expect(store.sessions).toHaveLength(0)
    await wrapper.find('#chat-header-new-session').trigger('click')
    expect(store.sessions).toHaveLength(1)
    expect(store.currentId).toBe(store.sessions[0].id)
  })

  it('网页搜索开关: 面板事件 → websearch-flag 出现; 关闭按钮熄灭', async () => {
    wrapper = mountView()
    expect(wrapper.find('.websearch-flag').exists()).toBe(false)

    await wrapper.find('.stub-tool-web').trigger('click')
    await nextTick()
    expect(wrapper.find('.websearch-flag').exists()).toBe(true)
    expect(wrapper.find('.websearch-flag').text()).toContain('网页搜索已开启')
    expect(ElMessage.success).toHaveBeenCalledWith('🌐 网页搜索已开启')

    await wrapper.find('.wsf-off').trigger('click')
    await nextTick()
    expect(wrapper.find('.websearch-flag').exists()).toBe(false)
  })

  it('语音入口 → ElMessage.info + 录音面板挂载', async () => {
    wrapper = mountView()
    expect(wrapper.find('.stub-voice-recorder').exists()).toBe(false)
    await wrapper.find('#chat-voice-trigger').trigger('click')
    await nextTick()
    expect(ElMessage.info).toHaveBeenCalledWith(expect.stringContaining('语音对话功能开发中'))
    expect(wrapper.find('.stub-voice-recorder').exists()).toBe(true)
  })

  it('从资料库添加 → startSelecting + 跳转 /knowledge', async () => {
    wrapper = mountView()
    await wrapper.find('.stub-tool-drive').trigger('click')
    expect(routerMock.push).toHaveBeenCalledWith('/knowledge')
  })
})

// ---------------------------------------------------------------------------
// 6. 附件选择 (formatFileSize + 校验错误态) 与 regenerate 重发
// ---------------------------------------------------------------------------
describe('ChatViewSSE 附件与重新生成', () => {
  const setInputFiles = (inputWrapper, files) => {
    Object.defineProperty(inputWrapper.element, 'files', {
      value: files,
      configurable: true,
    })
  }

  it('合法图片 → 预览块 (文件名 + 格式化大小); 移除后消失', async () => {
    wrapper = mountView()
    const imgInput = wrapper.find('#chat-image-upload')
    const file = new File([new Uint8Array(2048)], 'pic.png', { type: 'image/png' })
    setInputFiles(imgInput, [file])
    await imgInput.trigger('change')
    await nextTick()

    expect(wrapper.find('.input-attachment-preview').exists()).toBe(true)
    expect(wrapper.find('.iap-name').text()).toBe('pic.png')
    expect(wrapper.find('.iap-size').text()).toBe('2.0 KB')

    await wrapper.find('.iap-remove').trigger('click')
    await nextTick()
    expect(wrapper.find('.input-attachment-preview').exists()).toBe(false)
  })

  it('非图片类型 → ElMessage.error 且不产生预览 (校验错误态)', async () => {
    wrapper = mountView()
    const imgInput = wrapper.find('#chat-image-upload')
    const bad = new File(['x'], 'doc.txt', { type: 'text/plain' })
    setInputFiles(imgInput, [bad])
    await imgInput.trigger('change')
    await nextTick()
    expect(ElMessage.error).toHaveBeenCalledWith('请选择图片文件')
    expect(wrapper.find('.input-attachment-preview').exists()).toBe(false)
  })

  it('regenerate: 生成中 → warning 拦截; 空闲 → 用前一条 user 文案重发', async () => {
    wrapper = mountView()
    const m1 = mkMsg('m1', 'user', '原始提问')
    const m2 = mkMsg('m2', 'assistant', 'AI 回答')
    stream.messages.value = [m1, m2]
    await nextTick()

    const rows = wrapper.findAllComponents({ name: 'ChatMessageRow' })
    expect(rows).toHaveLength(2)

    stream.isCurrentSessionSending.value = true
    await nextTick()
    await rows[1].vm.$emit('regenerate', m2)
    await flushPromises()
    expect(ElMessage.warning).toHaveBeenCalledWith(expect.stringContaining('正在生成'))
    expect(stream.sendMessage).not.toHaveBeenCalled()

    stream.isCurrentSessionSending.value = false
    await nextTick()
    await rows[1].vm.$emit('regenerate', m2)
    await flushPromises()
    expect(stream.sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({ text: '原始提问' })
    )
  })

  it('消息行 copy 事件 → 空内容不弹成功提示', async () => {
    wrapper = mountView()
    const m1 = mkMsg('m1', 'assistant', '')
    stream.messages.value = [m1]
    await nextTick()
    const rows = wrapper.findAllComponents({ name: 'ChatMessageRow' })
    await rows[0].vm.$emit('copy', m1)
    await flushPromises()
    expect(ElMessage.success).not.toHaveBeenCalled()
  })
})
