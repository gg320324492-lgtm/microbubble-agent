/**
 * useChatViewBackgroundPoll — ChatViewSSE 断线续答轮询 (2026-09-20)
 *
 * L-1 阶段 2 (2026-10-07): 从 ChatViewSSE.vue <script setup> **原样迁出**,
 * 0 行为改动 (行为由 views/chat/__tests__/ChatViewSSE.behavior.test.js 兜底)。
 *
 * 刷新/切页后回到会话, 若服务端仍在后台生成, 轮询状态, 完成后自动拉取完整回答
 * 进会话 (配合后端 producer 解耦, ChatGPT 行为)。
 * 生命周期自管: sessionId watch (immediate) 在 setup 注册, onUnmounted 清轮询。
 */
import { ref, nextTick, watch, onUnmounted, type Ref } from 'vue'

import { chatHistoryApi } from '@/api/chatHistory'

export interface UseChatViewBackgroundPollOptions {
  sessionId: Ref<string>
  /** useChatStream.fetchSessionFromServer — 轮询完成后拉取完整回答 */
  fetchSessionFromServer: (sid: string) => Promise<void>
  /** 视图滚动模块的 scrollToBottom — 拉取完成后滚到底 */
  scrollToBottom: (force?: boolean) => Promise<void>
}

export function useChatViewBackgroundPoll(options: UseChatViewBackgroundPollOptions) {
  const { sessionId, fetchSessionFromServer, scrollToBottom } = options

  let genPollTimer: ReturnType<typeof setInterval> | null = null
  let genPollSid = ''

  function stopBackgroundPoll() {
    if (genPollTimer) {
      clearInterval(genPollTimer)
      genPollTimer = null
    }
    genPollSid = ''
  }

  async function pollBackgroundGeneration() {
    const sid = sessionId.value
    if (!sid) return
    try {
      const st = await chatHistoryApi.generationStatus(sid)
      if (!st?.generating) return
    } catch {
      return // 网络抖动: 下一轮 sessionId 变化或刷新再试
    }
    if (genPollSid === sid && genPollTimer) return // 已在轮询同一会话
    stopBackgroundPoll()
    genPollSid = sid
    console.info('[ChatViewSSE] 检测到后台生成进行中, 开始轮询:', sid)
    genPollTimer = setInterval(async () => {
      if (genPollSid !== sessionId.value) {
        stopBackgroundPoll()
        return
      }
      try {
        const st = await chatHistoryApi.generationStatus(sid)
        if (!st?.generating) {
          stopBackgroundPoll()
          await fetchSessionFromServer(sid)
          await nextTick()
          scrollToBottom()
          console.info('[ChatViewSSE] 后台生成完成, 完整回答已拉取:', sid)
        }
      } catch {
        /* 网络抖动忽略, 下个 tick 再试 */
      }
    }, 3000)
    // 安全上限 8 分钟自动停 (生成看门狗 600s + 富余)
    setTimeout(() => {
      if (genPollSid === sid) stopBackgroundPoll()
    }, 8 * 60 * 1000)
  }

  watch(
    sessionId,
    (sid) => {
      if (sid) void pollBackgroundGeneration()
    },
    { immediate: true },
  )

  onUnmounted(() => {
    stopBackgroundPoll() // 2026-09-20 断线续答: 组件卸载清轮询
  })

  return { pollBackgroundGeneration, stopBackgroundPoll }
}

export default useChatViewBackgroundPoll
