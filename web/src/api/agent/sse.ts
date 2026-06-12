/**
 * SSE 客户端（POST + ReadableStream）
 *
 * EventSource 不支持 POST 改用 fetch + reader。
 * 服务端发 'data: {...}\n\n' 帧，'[DONE]' 表示流结束。
 *
 * 用法：
 *   for await (const evt of sseFetch('/api/v1/chat/stream', { message, session_id })) {
 *     switch (evt.type) { ... }
 *   }
 */

import type { StreamEvent } from './protocol'

export async function* sseFetch(url: string, body: any, options: { signal?: AbortSignal } = {}): AsyncGenerator<StreamEvent> {
  const { signal } = options
  const token = localStorage.getItem('access_token') || ''
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    },
    body: JSON.stringify(body),
    signal
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`)
  }
  if (!res.body) throw new Error('响应无 body')

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  try {
    while (true) {
      // 检查 abort：如有 signal 且已 abort，立即 cancel reader 并 return
      // （防止切会话后旧 SSE 流继续 yield 把内容写到被覆盖的 assistantMsg）
      if (signal?.aborted) {
        try { await reader.cancel() } catch {}
        return
      }
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6).trim()
        if (!data || data === '[DONE]') return
        try {
          const evt = JSON.parse(data)
          yield evt as StreamEvent
        } catch (e) {
          console.warn('SSE 帧解析失败', e, data)
        }
      }
    }
  } finally {
    try { reader.releaseLock() } catch {}
  }
}
