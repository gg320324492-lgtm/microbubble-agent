import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'

// Mock useChatSessionsStore
vi.mock('@/stores/chatSessions', () => ({
  useChatSessionsStore: vi.fn(() => ({
    sessions: [],
    currentId: null,
    sortedSessions: [],
    currentSession: () => null,
    createSession: vi.fn(),
    updateActivity: vi.fn(),
    switchSession: vi.fn(),
    deleteSession: vi.fn(),
    migrateFromV1: vi.fn(),
  })),
}))

// Mock sse
vi.mock('@/api/agent/sse', () => ({
  sseFetch: vi.fn(),
}))

// Mock axios
vi.mock('axios', () => ({
  default: {
    post: vi.fn(),
  },
}))

// Mock ElMessage
vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}))

import { useChatStream } from '../chat/useChatStream'

describe('useChatStream', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Mock localStorage
    global.localStorage = {
      getItem: vi.fn((key) => {
        if (key === 'chat_current_session_v3') return 'test_session_id'
        return null
      }),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    }
  })

  it('导出核心状态和函数', () => {
    const stream = useChatStream()
    expect(stream).toHaveProperty('sessionId')
    expect(stream).toHaveProperty('messages')
    expect(stream).toHaveProperty('isCurrentSessionSending')
    expect(stream).toHaveProperty('sendMessage')
    expect(stream).toHaveProperty('onCreateSession')
    expect(stream).toHaveProperty('onSwitchSession')
    expect(stream).toHaveProperty('clearChat')
    expect(stream).toHaveProperty('playTTS')
    expect(stream).toHaveProperty('asrRecognize')
    expect(stream).toHaveProperty('persistSessionSync')
    expect(stream).toHaveProperty('persistSessionDebounced')
    expect(stream).toHaveProperty('ensureSessionLoaded')
  })

  it('sessionId 初始化从 localStorage 读取', () => {
    const stream = useChatStream()
    expect(stream.sessionId.value).toBe('test_session_id')
  })

  it('messages 计算属性从 messagesBySession 派生', () => {
    const stream = useChatStream()
    // 初始为空
    expect(stream.messages.value).toEqual([])
  })

  it('isCurrentSessionSending 初始为 false', () => {
    const stream = useChatStream()
    expect(stream.isCurrentSessionSending.value).toBe(false)
  })

  it('clearChat 重置当前会话为欢迎消息', () => {
    const stream = useChatStream()
    stream.clearChat()
    // messagesBySession 中应该有欢迎消息
    expect(stream.messages.value.length).toBe(1)
    expect(stream.messages.value[0].role).toBe('assistant')
  })
})