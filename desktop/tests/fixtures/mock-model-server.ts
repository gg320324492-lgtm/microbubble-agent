// Mock Provider Server (Phase 6-A6: E2E Verification).
//
// Phase 6-A6: in-process Node http server that simulates OpenAI-compatible SSE
// and Ollama NDJSON streaming. Tests start one of these per test, point a
// provider at its URL, and verify the full fetch -> parseChunk -> StreamEvent
// pipeline.
//
// NOT shipped to production. Tests/fixtures only.

import http, { type IncomingMessage, type ServerResponse } from 'node:http'
import type { AddressInfo } from 'node:net'

/**
 * Phase 6-A6: kind of mock server to spin up.
 *   - 'openai'   -> SSE `data: {json}\n\n` chunks
 *   - 'ollama'   -> NDJSON (one JSON object per line)
 */
export type MockProviderKind = 'openai' | 'ollama'

export interface MockScriptChunk {
  /** text to emit (Ollama) or as content delta (OpenAI). */
  content: string
}

/**
 * Phase 6-A6: scripted response.
 * Each test configures a list of chunks + an optional terminal event.
 */
export interface MockScript {
  chunks: MockScriptChunk[]
  /**
   * Phase 6-A6: optional explicit error response.
   * If set, server returns HTTP {status} with body {error: {message}}.
   */
  errorStatus?: number
  errorBody?: string
  /**
   * Phase 6-A6: optional delay before responding (ms). Useful for timeout tests.
   */
  delayMs?: number
  /**
   * Phase 6-A6: optional AbortSignal. If aborted mid-stream, server ends response.
   */
  signal?: AbortSignal
}

export interface MockServerHandle {
  url: string
  port: number
  close: () => Promise<void>
  /** Recorded: how many requests arrived + their paths. */
  requests: Array<{ method: string; path: string; headers: Record<string, string>; body: string }>
}

/**
 * Phase 6-A6: start a mock server on an ephemeral port.
 *
 * @param kind  'openai' (SSE) or 'ollama' (NDJSON)
 * @param script what to send back
 * @returns handle with URL + close()
 */
export async function startMockProviderServer(
  kind: MockProviderKind,
  script: MockScript
): Promise<MockServerHandle> {
  const requests: MockServerHandle['requests'] = []

  const server = http.createServer((req: IncomingMessage, res: ServerResponse) => {
    // Capture request
    let body = ''
    req.on('data', (chunk) => { body += chunk.toString('utf8') })
    req.on('end', () => {
      const headers: Record<string, string> = {}
      for (const [k, v] of Object.entries(req.headers)) {
        if (typeof v === 'string') headers[k] = v
      }
      requests.push({ method: req.method ?? '', path: req.url ?? '', headers, body })

      // Honor script.signal
      const onAbort = (): void => {
        try { res.end() } catch (_e) { /* ignore */ }
      }
      if (script.signal) {
        if (script.signal.aborted) {
          onAbort()
          return
        }
        script.signal.addEventListener('abort', onAbort, { once: true })
      }

      // Error response (Phase 6-A6)
      if (script.errorStatus) {
        const status = script.errorStatus
        res.writeHead(status, { 'Content-Type': 'application/json' })
        res.end(script.errorBody ?? JSON.stringify({ error: { message: `mock error ${status}` } }))
        return
      }

      const respond = (): void => {
        if (kind === 'openai') {
          // SSE: `data: {json}\n\n` per chunk, then `data: [DONE]\n\n`
          res.writeHead(200, {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            Connection: 'keep-alive'
          })
          for (const c of script.chunks) {
            const payload = JSON.stringify({
              choices: [{ delta: { content: c.content }, finish_reason: null }]
            })
            res.write(`data: ${payload}\n\n`)
          }
          res.write('data: [DONE]\n\n')
          res.end()
        } else {
          // Ollama NDJSON: one JSON object per line, last has done:true
          res.writeHead(200, {
            'Content-Type': 'application/x-ndjson',
            'Cache-Control': 'no-cache'
          })
          for (const c of script.chunks) {
            const payload = JSON.stringify({
              model: 'mock',
              message: { role: 'assistant', content: c.content },
              done: false
            })
            res.write(payload + '\n')
          }
          res.write(JSON.stringify({
            model: 'mock',
            message: { role: 'assistant', content: '' },
            done: true,
            done_reason: 'stop',
            eval_count: 5,
            prompt_eval_count: 3
          }) + '\n')
          res.end()
        }
      }

      if (script.delayMs && script.delayMs > 0) {
        setTimeout(respond, script.delayMs)
      } else {
        respond()
      }
    })
  })

  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
  const addr = server.address() as AddressInfo
  const port = addr.port
  const url = `http://127.0.0.1:${port}`

  return {
    url,
    port,
    requests,
    close: async () => {
      await new Promise<void>((resolve) => server.close(() => resolve()))
    }
  }
}
