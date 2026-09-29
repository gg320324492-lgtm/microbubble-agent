// @vitest-environment jsdom
// DL-6 Part A —— 发送 UX 乐观上屏契约（真实模型时代 CHAT_SEND 悬置数秒~分钟）
//
// 三件套：
//   1) 草稿即时清空（store.send 未 resolve 时输入框已空、按钮已进入发送中）
//   2) 用户消息即时上屏（temp- 临时条目）→ 成功后原位替换 + 追加回复，无 temp 残留
//   3) 失败回滚：临时条目移除 + 草稿回填（仅当输入框为空，不覆盖期间新输入）
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ChatPanel from '@renderer/components/chat/ChatPanel.vue'
import { useChatStore } from '@renderer/stores/chat'
import type { ChatMessage, ChatSession } from '@shared/types'

type SendResult = { userMessage: ChatMessage; assistantMessage: ChatMessage }

const REAL_USER: ChatMessage = { id: 'm-1', sessionId: 's1', role: 'user', content: '你好', meta: null, createdAt: 1000 }
const REAL_ASSISTANT: ChatMessage = {
  id: 'm-2',
  sessionId: 's1',
  role: 'assistant',
  content: '你好！需要我做什么？',
  meta: null,
  createdAt: 2000
}
const NEW_SESSION: ChatSession = { id: 's1', title: '新会话', createdAt: 0, updatedAt: 0, tokensIn: 0, tokensOut: 0 }

/** 可编程 send mock：默认永远挂起（模拟模型生成中），resolve/reject 由用例驱动 */
let sendMock: ReturnType<typeof vi.fn>
let resolveSend!: (v: SendResult) => void
let rejectSend!: (e: unknown) => void

function stubApi(): void {
  sendMock = vi.fn(
    () =>
      new Promise<SendResult>((res, rej) => {
        resolveSend = res
        rejectSend = rej
      })
  )
  Object.assign(window, {
    api: {
      model: { list: vi.fn(async () => []) },
      workspace: { get: vi.fn(async () => ({ root: null })) },
      chat: {
        sessionsList: vi.fn(async () => [NEW_SESSION]),
        sessionCreate: vi.fn(async () => NEW_SESSION),
        messagesList: vi.fn(async () => [] as ChatMessage[]),
        send: sendMock,
        abort: vi.fn(async () => undefined),
        onStreamEvent: vi.fn(() => () => {})
      }
    }
  })
}

beforeEach(() => {
  stubApi()
  setActivePinia(createPinia())
})

describe('DL-6 chat store 乐观上屏/替换/回滚', () => {
  it('★ 发送即上屏临时用户消息（不等 IPC resolve）；成功后原位替换 + 追加回复，无 temp 残留', async () => {
    const store = useChatStore()
    await store.create()
    expect(store.activeId).toBe('s1')

    const p = store.send('你好')
    // IPC 仍挂起：用户消息已可见（temp- 前缀临时条目）
    expect(store.messages).toHaveLength(1)
    expect(store.messages[0]).toMatchObject({ role: 'user', content: '你好', sessionId: 's1' })
    expect(String(store.messages[0].id)).toMatch(/^temp-/)

    resolveSend({ userMessage: REAL_USER, assistantMessage: REAL_ASSISTANT })
    await p
    // 临时条目被真实消息原位替换，assistant 回复追加，列表无 temp 残留
    expect(store.messages.map((m) => m.id)).toEqual(['m-1', 'm-2'])
  })

  it('★ 失败路径：临时条目移除后抛错，列表无残留', async () => {
    const store = useChatStore()
    await store.create()
    sendMock.mockImplementation(async () => {
      throw new Error('模型 500')
    })
    await expect(store.send('你好')).rejects.toThrow('模型 500')
    expect(store.messages).toHaveLength(0)
  })
})

describe('DL-6 ChatPanel 草稿即时清空/失败回填', () => {
  async function mountPanel(): Promise<{ w: ReturnType<typeof mount>; store: ReturnType<typeof useChatStore> }> {
    const pinia = createPinia()
    setActivePinia(pinia)
    const w = mount(ChatPanel, { global: { plugins: [pinia] } })
    await flushPromises()
    const store = useChatStore()
    await store.create()
    await flushPromises()
    return { w, store }
  }

  const draftValue = (w: ReturnType<typeof mount>): string =>
    (w.get('.composer-input').element as HTMLTextAreaElement).value

  it('★ 发送后瞬间（IPC 挂起）：草稿已空、用户气泡已上屏、按钮进入发送中；收口后替换+追加', async () => {
    const { w, store } = await mountPanel()
    await w.get('.composer-input').setValue('你好')
    await w.get('.composer-send').trigger('click')
    await flushPromises()

    // 生成中中间态（真实模型时代的数秒窗口）
    expect(draftValue(w)).toBe('')
    expect(store.messages).toHaveLength(1)
    expect(store.messages[0]).toMatchObject({ role: 'user', content: '你好' })
    expect(String(store.messages[0].id)).toMatch(/^temp-/)
    expect(w.get('.composer-send').text()).toContain('发送中')

    resolveSend({ userMessage: REAL_USER, assistantMessage: REAL_ASSISTANT })
    await flushPromises()
    expect(store.messages.map((m) => m.id)).toEqual(['m-1', 'm-2'])
    expect(w.get('.composer-send').text()).toContain('发送')
  })

  it('★ 失败且输入框为空 → 草稿回填；期间已有新输入 → 不覆盖', async () => {
    const { w } = await mountPanel()
    // 场景 1：失败时输入框为空 → 回填原草稿
    await w.get('.composer-input').setValue('你好')
    await w.get('.composer-send').trigger('click')
    await flushPromises()
    expect(draftValue(w)).toBe('')
    rejectSend(new Error('模型 500'))
    await flushPromises()
    expect(draftValue(w)).toBe('你好')

    // 场景 2：生成期间用户已有新输入 → 失败不覆盖新输入。
    // 生成期间 textarea 处于 disabled（现状门控，本单不改），jsdom 下 test-utils
    // setValue 的 input 事件到不了 v-model，改用手动 dispatch 模拟「期间已有输入」；
    // 真实浏览器中 disabled 输入框无法打字，此守卫为纵深防御（工单明示要求）。
    await w.get('.composer-input').setValue('第二条')
    await w.get('.composer-send').trigger('click')
    await flushPromises()
    const ta = w.get('.composer-input').element as HTMLTextAreaElement
    ta.value = '生成期间的新输入'
    ta.dispatchEvent(new Event('input'))
    await Promise.resolve()
    rejectSend(new Error('超时'))
    await flushPromises()
    expect(draftValue(w)).toBe('生成期间的新输入')
  })
})
