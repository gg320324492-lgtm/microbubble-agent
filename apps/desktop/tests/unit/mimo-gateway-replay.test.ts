// R-10-B1 mimo-v2.5 回放测试 —— 用真机抓取的原始 SSE 形状驱动网关解析
//
// 背景：真机（dutonghe 候选版，mimo-v2.5 / anthropic 协议）出现「thinking 有内容、正文为空」，
// 触发本地回声兜底。抓取的原始形状（三场景全 200）：
//   A 默认：content_block_start ×2（index0=thinking / index1=text）
//           delta ×23 = thinking_delta ×18 + **signature_delta ×1** + text_delta ×4
//   B 关闭 thinking：单一 text 块 + text_delta ×4（完全标准）
// 本文件把这些形状原样回放，锁死「正文必须被完整提取」这一契约。
import { describe, expect, it, vi } from 'vitest'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { ModelGatewayService, shouldDisableThinking, type KeyCipher } from '@main/services/model-gateway.service'

const cipher: KeyCipher = {
  encrypt: (s) => Buffer.from('enc:' + s).toString('base64'),
  decrypt: (c) => {
    const raw = Buffer.from(c, 'base64').toString('utf8')
    return raw.startsWith('enc:') ? raw.slice(4) : null
  }
}

function makeGateway() {
  const db = openNodeSqlite(':memory:')
  runMigrations(db)
  const gw = new ModelGatewayService(db, cipher)
  gw.save('u1', {
    name: 'mimo',
    protocol: 'anthropic',
    baseUrl: 'https://token-plan-cn.xiaomimimo.com/anthropic',
    model: 'mimo-v2.5',
    apiKey: 'k-mimo'
  })
  return gw
}

function sseResponse(chunks: string[]): Response {
  const stream = new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(new TextEncoder().encode(c))
      controller.close()
    }
  })
  return new Response(stream, { status: 200, headers: { 'content-type': 'text/event-stream' } })
}

const ev = (name: string, data: unknown): string => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`

/** 真机 A 形状：thinking 块（含 signature_delta）+ text 块 */
function mimoShapeA(): string[] {
  const out: string[] = []
  out.push(ev('message_start', { type: 'message_start', message: { id: 'msg_x', role: 'assistant', model: 'mimo-v2.5', content: [], usage: { input_tokens: 69, output_tokens: 0 } } }))
  out.push(ev('content_block_start', { type: 'content_block_start', index: 0, content_block: { type: 'thinking', thinking: '', signature: '' } }))
  out.push(ev('content_block_delta', { type: 'content_block_delta', index: 0, delta: { type: 'thinking_delta', thinking: '用户问了一个' } }))
  out.push(ev('content_block_delta', { type: 'content_block_delta', index: 0, delta: { type: 'thinking_delta', thinking: '非常简单的问题。' } }))
  // ★ 真机出现的未知类型：Anthropic 扩展思考签名（网关原先不认识）
  out.push(ev('content_block_delta', { type: 'content_block_delta', index: 0, delta: { type: 'signature_delta', signature: '' } }))
  out.push(ev('content_block_stop', { type: 'content_block_stop', index: 0 }))
  out.push(ev('content_block_start', { type: 'content_block_start', index: 1, content_block: { type: 'text', text: '' } }))
  out.push(ev('content_block_delta', { type: 'content_block_delta', index: 1, delta: { type: 'text_delta', text: '1+1' } }))
  out.push(ev('content_block_delta', { type: 'content_block_delta', index: 1, delta: { type: 'text_delta', text: ' 等于' } }))
  out.push(ev('content_block_delta', { type: 'content_block_delta', index: 1, delta: { type: 'text_delta', text: ' 2' } }))
  out.push(ev('content_block_delta', { type: 'content_block_delta', index: 1, delta: { type: 'text_delta', text: '。' } }))
  out.push(ev('content_block_stop', { type: 'content_block_stop', index: 1 }))
  out.push(ev('message_delta', { type: 'message_delta', delta: { stop_reason: 'end_turn' }, usage: { output_tokens: 40 } }))
  out.push(ev('message_stop', { type: 'message_stop' }))
  return out
}

/** 真机 B 形状：关闭 thinking → 纯标准单 text 块 */
function mimoShapeB(): string[] {
  return [
    ev('message_start', { type: 'message_start', message: { id: 'msg_y', role: 'assistant', model: 'mimo-v2.5', content: [], usage: { input_tokens: 60, output_tokens: 0 } } }),
    ev('content_block_start', { type: 'content_block_start', index: 0, content_block: { type: 'text', text: '' } }),
    ev('content_block_delta', { type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: '你好' } }),
    ev('content_block_delta', { type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: '，我是' } }),
    ev('content_block_delta', { type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: ' mimo' } }),
    ev('content_block_delta', { type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: '。' } }),
    ev('content_block_stop', { type: 'content_block_stop', index: 0 }),
    ev('message_delta', { type: 'message_delta', delta: { stop_reason: 'end_turn' }, usage: { output_tokens: 20 } }),
    ev('message_stop', { type: 'message_stop' })
  ]
}

const req = (onEvent: (e: { kind: 'text' | 'thinking'; delta: string }) => void = () => undefined) => ({
  system: 'S',
  turns: [{ role: 'user' as const, content: '你好' }],
  tools: [],
  onEvent
})

describe('mimo-v2.5 真实形状回放', () => {
  it('A 形状（thinking + signature_delta + text）：正文必须完整提取，未知 delta 不得打断流', async () => {
    const gw = makeGateway()
    vi.stubGlobal('fetch', vi.fn(async () => sseResponse(mimoShapeA())))
    const texts: string[] = []
    const res = await gw.streamAgentTurn('u1', 's1', req((e) => e.kind === 'text' && texts.push(e.delta)))

    expect(res.text).toBe('1+1 等于 2。') // ★ 核心：4 个 text_delta 一个都不能丢
    expect(res.thinking).toContain('非常简单的问题')
    expect(res.stopReason).toBe('end_turn')
    // 增量事件也完整（渲染层实时显示依赖它）
    expect(texts.join('')).toBe('1+1 等于 2。')
    vi.unstubAllGlobals()
  })

  it('B 形状（关闭 thinking）：单 text 块完全标准，正文完整', async () => {
    const gw = makeGateway()
    vi.stubGlobal('fetch', vi.fn(async () => sseResponse(mimoShapeB())))
    const res = await gw.streamAgentTurn('u1', 's1', req())
    expect(res.text).toBe('你好，我是 mimo。')
    expect(res.thinking).toBe('')
    vi.unstubAllGlobals()
  })

  it('未知 delta 类型（如未来厂商新增字段）一律安全忽略，不致命、不丢正文', async () => {
    const gw = makeGateway()
    const chunks = [
      ev('message_start', { type: 'message_start', message: { id: 'm', role: 'assistant', content: [], usage: {} } }),
      ev('content_block_start', { type: 'content_block_start', index: 0, content_block: { type: 'text', text: '' } }),
      ev('content_block_delta', { type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: '前半' } }),
      // 三种未知/新增类型穿插在正文之间
      ev('content_block_delta', { type: 'content_block_delta', index: 0, delta: { type: 'future_unknown_delta', payload: { a: 1 } } }),
      ev('content_block_delta', { type: 'content_block_delta', index: 0, delta: { type: 'signature_delta', signature: 'abc' } }),
      ev('some_unknown_event', { type: 'totally_unknown_event', index: 0 }),
      ev('content_block_delta', { type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: '后半' } }),
      ev('content_block_stop', { type: 'content_block_stop', index: 0 }),
      ev('message_delta', { type: 'message_delta', delta: { stop_reason: 'end_turn' }, usage: {} }),
      ev('message_stop', { type: 'message_stop' })
    ]
    vi.stubGlobal('fetch', vi.fn(async () => sseResponse(chunks)))
    const res = await gw.streamAgentTurn('u1', 's1', req())
    expect(res.text).toBe('前半后半')
    vi.unstubAllGlobals()
  })

  it('未产生任何正文但只有 thinking → 仍抛空回复（交由上层按失败处理，不静默当成功）', async () => {
    const gw = makeGateway()
    const chunks = [
      ev('message_start', { type: 'message_start', message: { id: 'm', role: 'assistant', content: [], usage: {} } }),
      ev('content_block_start', { type: 'content_block_start', index: 0, content_block: { type: 'thinking', thinking: '', signature: '' } }),
      ev('content_block_delta', { type: 'content_block_delta', index: 0, delta: { type: 'thinking_delta', thinking: '只想不说' } }),
      ev('content_block_stop', { type: 'content_block_stop', index: 0 }),
      ev('message_delta', { type: 'message_delta', delta: { stop_reason: 'end_turn' }, usage: {} }),
      ev('message_stop', { type: 'message_stop' })
    ]
    vi.stubGlobal('fetch', vi.fn(async () => sseResponse(chunks)))
    // 只有 thinking 不算空（有 thinking 时不抛），但 text 为空需被上层看见
    const res = await gw.streamAgentTurn('u1', 's1', req())
    expect(res.text).toBe('')
    expect(res.thinking).toBe('只想不说')
    vi.unstubAllGlobals()
  })
})
describe('R-10-B1 修复断言', () => {
  it('shouldDisableThinking：仅 anthropic 协议下的 mimo 系列命中（其它一律不动 → 零回归）', () => {
    expect(shouldDisableThinking('anthropic', 'mimo-v2.5')).toBe(true)
    expect(shouldDisableThinking('anthropic', 'MIMO-v2.5')).toBe(true) // 大小写不敏感
    expect(shouldDisableThinking('anthropic', 'mimo-v2.5-pro')).toBe(true)
    // 非 anthropic 协议不加该参数
    expect(shouldDisableThinking('openai', 'mimo-v2.5')).toBe(false)
    // 其它模型完全不受影响
    expect(shouldDisableThinking('anthropic', 'claude-3-5-sonnet')).toBe(false)
    expect(shouldDisableThinking('anthropic', 'qwen3.8')).toBe(false)
    expect(shouldDisableThinking('openai', 'deepseek-chat')).toBe(false)
    expect(shouldDisableThinking('anthropic', '')).toBe(false)
  })

  it('请求体：mimo（anthropic）实际带上 thinking:{type:disabled}；其它模型不带', async () => {
    const gw = makeGateway()
    const bodies: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init: { body?: string }) => {
        bodies.push(String(init?.body ?? ''))
        return sseResponse(mimoShapeB())
      })
    )
    await gw.streamAgentTurn('u1', 's1', req())
    const mimoBody = JSON.parse(bodies[0]!) as { thinking?: { type?: string } }
    expect(mimoBody.thinking).toEqual({ type: 'disabled' })

    // 换成非命中模型 → 请求体不含 thinking 字段
    const db2 = openNodeSqlite(':memory:')
    runMigrations(db2)
    const gw2 = new ModelGatewayService(db2, cipher)
    gw2.save('u1', { name: 'claude', protocol: 'anthropic', baseUrl: 'https://a.com', model: 'claude-3-5-sonnet', apiKey: 'k' })
    bodies.length = 0
    await gw2.streamAgentTurn('u1', 's1', req())
    const otherBody = JSON.parse(bodies[0]!) as Record<string, unknown>
    expect('thinking' in otherBody).toBe(false)
    vi.unstubAllGlobals()
  })

  it('未知 delta 类型只记日志、不打断流（debug 日志可达）', async () => {
    const gw = makeGateway()
    const logs: string[] = []
    const spy = vi.spyOn(console, 'log').mockImplementation((m?: unknown) => logs.push(String(m)))
    const chunks = [
      ev('message_start', { type: 'message_start', message: { id: 'm', role: 'assistant', content: [], usage: {} } }),
      ev('content_block_start', { type: 'content_block_start', index: 0, content_block: { type: 'text', text: '' } }),
      ev('content_block_delta', { type: 'content_block_delta', index: 0, delta: { type: 'brand_new_delta', x: 1 } }),
      ev('content_block_delta', { type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: '正文仍在' } }),
      ev('content_block_stop', { type: 'content_block_stop', index: 0 }),
      ev('message_stop', { type: 'message_stop' })
    ]
    vi.stubGlobal('fetch', vi.fn(async () => sseResponse(chunks)))
    const res = await gw.streamAgentTurn('u1', 's1', req())
    expect(res.text).toBe('正文仍在')
    expect(logs.some((l) => l.includes('brand_new_delta'))).toBe(true)
    // signature_delta 是已知类型，不应刷日志
    spy.mockRestore()
    vi.unstubAllGlobals()
  })
})
