// 模型网关契约 — 配置管理（key 加密/掩码/默认切换）+ 双协议 SSE 解析（mock fetch）
import { describe, expect, it, vi } from 'vitest'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { ModelGatewayService, type KeyCipher } from '@main/services/model-gateway.service'

const cipher: KeyCipher = {
  encrypt: (s) => Buffer.from('enc:' + s).toString('base64'),
  decrypt: (c) => (c.startsWith(Buffer.from('enc:').toString('base64').slice(0, 8)) || true ? decode(c) : null),
}
function decode(c: string): string | null {
  const raw = Buffer.from(c, 'base64').toString('utf8')
  return raw.startsWith('enc:') ? raw.slice(4) : null
}

function makeGateway() {
  const db = openNodeSqlite(':memory:')
  runMigrations(db)
  return { gw: new ModelGatewayService(db, cipher) }
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

describe('Provider 配置管理', () => {
  it('保存时 key 加密入库、掩码不出明文；首个自动设默认', () => {
    const { gw } = makeGateway()
    gw.save('u1', { name: 'DeepSeek', protocol: 'openai', baseUrl: 'https://api.deepseek.com', model: 'deepseek-chat', apiKey: 'sk-secret' })
    const [p] = gw.list('u1')
    expect(p.isDefault).toBe(true)
    expect(p.apiKeyEncrypted).not.toContain('sk-secret')
    expect(gw.list('u1')).toHaveLength(1)
  })

  it('编辑时空 apiKey 保留旧 key；Base URL 校验 https', () => {
    const { gw } = makeGateway()
    const p = gw.save('u1', { name: 'A', protocol: 'openai', baseUrl: 'https://a.com', model: 'm', apiKey: 'k1' })
    gw.save('u1', { id: p.id, name: 'A2', protocol: 'openai', baseUrl: 'https://a.com', model: 'm2' })
    const [edited] = gw.list('u1')
    expect(edited.apiKeyEncrypted).toBe(p.apiKeyEncrypted)
    expect(() => gw.save('u1', { name: 'B', protocol: 'openai', baseUrl: 'http://a.com', model: 'm', apiKey: 'k' })).toThrow('https')
  })

  it('删除默认后自动转移；用户间配置隔离', () => {
    const { gw } = makeGateway()
    const p1 = gw.save('u1', { name: 'A', protocol: 'openai', baseUrl: 'https://a.com', model: 'm', apiKey: 'k1' })
    const p2 = gw.save('u1', { name: 'B', protocol: 'openai', baseUrl: 'https://b.com', model: 'm', apiKey: 'k2' })
    gw.remove('u1', p1.id)
    expect(gw.list('u1')[0].id).toBe(p2.id)
    expect(gw.list('u1')[0].isDefault).toBe(true)
    expect(gw.list('u2')).toHaveLength(0)
  })

  it('listWithKeyState — 正常密文 ok；解不开的密文标记 invalid（重填引导依据）', () => {
    const db = openNodeSqlite(':memory:')
    runMigrations(db)
    const gwOk = new ModelGatewayService(db, cipher)
    gwOk.save('u1', { name: 'A', protocol: 'anthropic', baseUrl: 'https://a.com', model: 'm', apiKey: 'k1' })
    const [okRow] = gwOk.listWithKeyState('u1')
    expect(okRow.keyState).toBe('ok')

    const brokenCipher: KeyCipher = {
      encrypt: (s) => Buffer.from('enc:' + s).toString('base64'),
      decrypt: () => null // 模拟 DPAPI/LocalState 上下文变化后解密失败
    }
    const gwBroken = new ModelGatewayService(db, brokenCipher)
    const [badRow] = gwBroken.listWithKeyState('u1')
    expect(badRow.keyState).toBe('invalid') // 同一条密文，环境变了就解不开
    db.close()
  })
})

describe('streamChat 双协议 SSE 解析', () => {
  it('OpenAI 协议: 增量拼接 + onDelta 回调', async () => {
    const { gw } = makeGateway()
    gw.save('u1', { name: 'DS', protocol: 'openai', baseUrl: 'https://api.deepseek.com', model: 'deepseek-chat', apiKey: 'sk' })
    const deltas: string[] = []
    vi.stubGlobal('fetch', vi.fn(async () =>
      sseResponse([
        'data: {"choices":[{"delta":{"content":"你好"}}]}\n\n',
        'data: {"choices":[{"delta":{"content":"，世界"}}]}\n\n',
        'data: [DONE]\n\n'
      ])
    ))
    const full = await gw.streamChat('u1', 's1', [{ role: 'user', content: 'hi' }], (d) => deltas.push(d))
    vi.unstubAllGlobals()
    expect(full).toBe('你好，世界')
    expect(deltas).toEqual(['你好', '，世界'])
  })

  it('Anthropic 协议: content_block_delta 解析', async () => {
    const { gw } = makeGateway()
    gw.save('u1', { name: 'MiMo', protocol: 'anthropic', baseUrl: 'https://api-mimo.xiaomi.com', model: 'mimo-v2.5', apiKey: 'sk' })
    vi.stubGlobal('fetch', vi.fn(async () =>
      sseResponse([
        'event: content_block_delta\ndata: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello"}}\n\n',
        'event: content_block_stop\ndata: {"type":"content_block_stop"}\n\n'
      ])
    ))
    const full = await gw.streamChat('u1', 's1', [{ role: 'user', content: 'hi' }], () => {})
    vi.unstubAllGlobals()
    expect(full).toBe('Hello')
  })

  it('HTTP 错误透出状态码与片段', async () => {
    const { gw } = makeGateway()
    gw.save('u1', { name: 'Bad', protocol: 'openai', baseUrl: 'https://bad.com', model: 'm', apiKey: 'k' })
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{"error":"invalid key"}', { status: 401 })))
    await expect(gw.streamChat('u1', 's1', [{ role: 'user', content: 'hi' }], () => {})).rejects.toThrow('401')
    vi.unstubAllGlobals()
  })

  it('未配置模型时明确报错', async () => {
    const { gw } = makeGateway()
    await expect(gw.streamChat('nobody', 's1', [], () => {})).rejects.toThrow('尚未配置模型服务')
  })
})
