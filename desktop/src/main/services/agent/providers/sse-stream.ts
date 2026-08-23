// SSE stream parser (Phase 8-D0 helper).
//
// Parses OpenAI-style SSE responses:
//   data: {"choices":[{"delta":{"content":"hi"}}]}\n\n
//   data: [DONE]
//
// Phase 8-D0: pure helper. No credentials, no SDK imports.

export interface SseMessage {
  data: string
  event?: string
}

/** Phase 8-D0: parse SSE chunks from a ReadableStream of UTF-8 bytes. */
export async function* parseSseStream(
  body: ReadableStream<Uint8Array> | null
): AsyncIterableIterator<SseMessage> {
  if (!body) return
  const reader = body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buf = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buf.indexOf('\n\n')) !== -1) {
      const block = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      const parsed = parseSseBlock(block)
      if (parsed) yield parsed
    }
  }
  if (buf.trim().length > 0) {
    const parsed = parseSseBlock(buf)
    if (parsed) yield parsed
  }
}

function parseSseBlock(block: string): SseMessage | null {
  let data = ''
  let event: string | undefined
  for (const line of block.split('\n')) {
    const i = line.indexOf(':')
    if (i === -1) continue
    const field = line.slice(0, i).trim()
    const value = line.slice(i + 1).trimStart()
    if (field === 'data') data += value
    else if (field === 'event') event = value
  }
  if (data.length === 0) return null
  return { data, event }
}