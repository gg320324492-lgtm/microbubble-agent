// 模型网关 — Provider 配置管理 + OpenAI/Anthropic 双协议 SSE 流式补全。
// 安全: apiKey 仅存主进程（safeStorage 加密，可注入加密器便于测试），永不明文过 IPC。
// C-2 起提供 streamAgentTurn：Anthropic 原生 tool_use / thinking 全块解析（已实测 MiMo 支持）。
import { randomBytes } from 'node:crypto'
import type { SqlDatabase } from '../db/adapters'
import type { ModelProtocol, StreamTurnRequest, StreamTurnResult, StopReason } from '@shared/types'

export interface ProviderRecord {
  id: string
  name: string
  protocol: ModelProtocol
  baseUrl: string
  model: string
  /** safeStorage 密文 base64；空串=未配置 */
  apiKeyEncrypted: string
  isDefault: boolean
}

export interface ChatTurn {
  role: 'user' | 'assistant' | 'system'
  content: string
}

export interface KeyCipher {
  encrypt(plaintext: string): string
  decrypt(ciphertext: string): string | null
}

const genId = () => `mp-${Date.now()}-${randomBytes(3).toString('hex')}`
const SETTINGS_KEY = 'model.providers'

export class ModelGatewayService {
  /** 每个 provider 的进行中 AbortController（按 providerId+会话维度挂 sessionId） */
  private aborts = new Map<string, AbortController>()

  constructor(
    private readonly db: SqlDatabase,
    private readonly cipher: KeyCipher
  ) {}

  // ---------- 配置管理 ----------

  list(userId: string): ProviderRecord[] {
    const row = this.db.prepare('SELECT value FROM settings WHERE user_id = ? AND key = ?').get(userId, SETTINGS_KEY) as
      | { value: string }
      | undefined
    if (!row) return []
    try {
      return JSON.parse(row.value) as ProviderRecord[]
    } catch {
      return []
    }
  }

  private persist(userId: string, providers: ProviderRecord[]): void {
    this.db
      .prepare(
        `INSERT INTO settings (user_id, key, value, updated_at) VALUES (?, ?, ?, ?)
         ON CONFLICT (user_id, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at`
      )
      .run(userId, SETTINGS_KEY, JSON.stringify(providers), Date.now())
  }

  /** 保存；有 id=编辑，无 id=新建。apiKey 空串=保留旧 key。首个 provider 自动设默认。 */
  save(
    userId: string,
    input: { id?: string; name: string; protocol: ModelProtocol; baseUrl: string; model: string; apiKey?: string }
  ): ProviderRecord {
    const name = input.name.trim()
    const baseUrl = input.baseUrl.trim().replace(/\/+$/, '')
    const model = input.model.trim()
    if (!name) throw new Error('名称不能为空')
    if (!/^https:\/\//.test(baseUrl)) throw new Error('Base URL 必须是 https://')
    if (!model) throw new Error('模型 ID 不能为空')

    const providers = this.list(userId)
    const existing = input.id ? providers.find((p) => p.id === input.id) : undefined
    if (input.id && !existing) throw new Error('配置不存在')

    let apiKeyEncrypted = existing?.apiKeyEncrypted ?? ''
    if (input.apiKey) {
      apiKeyEncrypted = this.cipher.encrypt(input.apiKey)
      if (!apiKeyEncrypted) throw new Error('本机加密不可用，无法保存 API Key')
    }
    if (!apiKeyEncrypted) throw new Error('请填写 API Key')

    let record: ProviderRecord
    if (existing) {
      Object.assign(existing, { name, protocol: input.protocol, baseUrl, model, apiKeyEncrypted })
      record = existing
    } else {
      record = { id: genId(), name, protocol: input.protocol, baseUrl, model, apiKeyEncrypted, isDefault: false }
      providers.push(record)
    }
    if (providers.length === 1) record.isDefault = true
    this.persist(userId, providers)
    return record
  }

  remove(userId: string, id: string): void {
    const providers = this.list(userId)
    const next = providers.filter((p) => p.id !== id)
    if (next.length === providers.length) throw new Error('配置不存在')
    if (next.length > 0 && providers.find((p) => p.id === id)?.isDefault) next[0].isDefault = true
    this.persist(userId, next)
  }

  setDefault(userId: string, id: string): void {
    const providers = this.list(userId)
    const target = providers.find((p) => p.id === id)
    if (!target) throw new Error('配置不存在')
    for (const p of providers) p.isDefault = p.id === id
    this.persist(userId, providers)
  }

  getDefault(userId: string): ProviderRecord | null {
    const providers = this.list(userId)
    return providers.find((p) => p.isDefault) ?? providers[0] ?? null
  }

  /**
   * 列表 + key 健康状态 — 本机解密失败（DPAPI/LocalState 上下文变化）标记 invalid，
   * UI 据此给出重填引导（真机实测发生过：密文存在但解不开，用户无处下手）。
   */
  listWithKeyState(userId: string): (ProviderRecord & { keyState: 'ok' | 'invalid' })[] {
    return this.list(userId).map((p) => ({
      ...p,
      keyState: this.cipher.decrypt(p.apiKeyEncrypted) ? ('ok' as const) : ('invalid' as const)
    }))
  }

  private decryptKey(p: ProviderRecord): string {
    const key = this.cipher.decrypt(p.apiKeyEncrypted)
    if (!key) throw new Error('API Key 解密失败，请重新填写')
    return key
  }

  // ---------- 连通性测试 ----------

  async testConnection(userId: string, providerId: string): Promise<{ ok: boolean; message: string }> {
    const p = this.list(userId).find((x) => x.id === providerId)
    if (!p) throw new Error('配置不存在')
    return this.probe({ protocol: p.protocol, baseUrl: p.baseUrl, model: p.model, apiKey: this.decryptKey(p) })
  }

  /** 保存前测试（key 尚未入库的表单场景） */
  async probe(p: { protocol: ModelProtocol; baseUrl: string; model: string; apiKey: string }): Promise<{ ok: boolean; message: string }> {
    try {
      const res =
        p.protocol === 'anthropic'
          ? await fetch(`${p.baseUrl}/v1/messages`, {
              method: 'POST',
              headers: { 'content-type': 'application/json', 'x-api-key': p.apiKey, 'anthropic-version': '2023-06-01' },
              body: JSON.stringify({ model: p.model, max_tokens: 8, messages: [{ role: 'user', content: 'ping' }] }),
              signal: AbortSignal.timeout(15000)
            })
          : await fetch(`${p.baseUrl}/chat/completions`, {
              method: 'POST',
              headers: { 'content-type': 'application/json', authorization: `Bearer ${p.apiKey}` },
              body: JSON.stringify({ model: p.model, max_tokens: 8, messages: [{ role: 'user', content: 'ping' }] }),
              signal: AbortSignal.timeout(15000)
            })
      if (res.ok) return { ok: true, message: '连接成功' }
      const body = await res.text().catch(() => '')
      return { ok: false, message: `HTTP ${res.status}${body ? `: ${body.slice(0, 200)}` : ''}` }
    } catch (e) {
      return { ok: false, message: e instanceof Error ? e.message : '连接失败' }
    }
  }

  // ---------- 流式补全 ----------

  abort(sessionId: string): void {
    this.aborts.get(sessionId)?.abort()
    this.aborts.delete(sessionId)
  }

  /**
   * 流式对话。onDelta 逐段回调（增量文本）；返回完整文本。
   * OpenAI: SSE `data: {choices:[{delta:{content}}]}`；Anthropic: SSE content_block_delta。
   */
  async streamChat(
    userId: string,
    sessionId: string,
    turns: ChatTurn[],
    onDelta: (delta: string) => void
  ): Promise<string> {
    const p = this.getDefault(userId)
    if (!p) throw new Error('尚未配置模型服务，请到「设置 → 模型服务」添加')
    const apiKey = this.decryptKey(p)
    const controller = new AbortController()
    this.aborts.set(sessionId, controller)
    let full = ''

    const url = p.protocol === 'anthropic' ? `${p.baseUrl}/v1/messages` : `${p.baseUrl}/chat/completions`
    const headers: Record<string, string> =
      p.protocol === 'anthropic'
        ? { 'content-type': 'application/json', 'x-api-key': apiKey, 'anthropic-version': '2023-06-01' }
        : { 'content-type': 'application/json', authorization: `Bearer ${apiKey}` }
    const body =
      p.protocol === 'anthropic'
        ? JSON.stringify({ model: p.model, max_tokens: 4096, stream: true, messages: turns })
        : JSON.stringify({ model: p.model, stream: true, messages: turns })

    try {
      const res = await fetch(url, { method: 'POST', headers, body, signal: controller.signal })
      if (!res.ok || !res.body) {
        const detail = await res.text().catch(() => '')
        throw new Error(`模型服务返回 HTTP ${res.status}${detail ? `: ${detail.slice(0, 300)}` : ''}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data:')) continue
          const payload = trimmed.slice(5).trim()
          if (payload === '[DONE]') continue
          try {
            const json = JSON.parse(payload) as {
              choices?: { delta?: { content?: string } }[]
              type?: string
              delta?: { type?: string; text?: string }
            }
            let delta = ''
            if (p.protocol === 'anthropic') {
              if (json.type === 'content_block_delta' && json.delta?.type === 'text_delta') delta = json.delta.text ?? ''
            } else {
              delta = json.choices?.[0]?.delta?.content ?? ''
            }
            if (delta) {
              full += delta
              onDelta(delta)
            }
          } catch {
            /* 非 JSON 行忽略 */
          }
        }
      }
      if (!full.trim()) throw new Error('模型返回了空回复')
      return full
    } catch (e) {
      // 用户中止：保留已生成的部分内容（renderer 以停止按钮感知，无需错误提示）
      if (e instanceof Error && (e.name === 'AbortError' || controller.signal.aborted)) return full
      throw e
    } finally {
      this.aborts.delete(sessionId)
    }
  }

  // ---------- Agent 循环单流（C-2） ----------

  /**
   * Agent 循环的单轮流式请求（含 tools / system / 块结构 turns）。
   * Anthropic 协议：原生 tool_use + thinking 全块解析；OpenAI 协议：纯文本降级（无工具）。
   * 用户中止时不抛错 — 返回已生成的部分内容，stopReason='aborted'，循环层据此收尾。
   */
  async streamAgentTurn(userId: string, sessionId: string, req: StreamTurnRequest): Promise<StreamTurnResult> {
    const p = this.getDefault(userId)
    if (!p) throw new Error('尚未配置模型服务，请到「设置 → 模型服务」添加')
    const apiKey = this.decryptKey(p)
    const controller = new AbortController()
    this.aborts.set(sessionId, controller)

    interface BlockState {
      type: string
      text: string
      thinking: string
      id?: string
      name?: string
      json: string
    }
    const blocks = new Map<number, BlockState>()
    let stopReason: StopReason = 'end_turn'

    try {
      const isAnthropic = p.protocol === 'anthropic'
      const url = isAnthropic ? `${p.baseUrl}/v1/messages` : `${p.baseUrl}/chat/completions`
      const headers: Record<string, string> = isAnthropic
        ? { 'content-type': 'application/json', 'x-api-key': apiKey, 'anthropic-version': '2023-06-01' }
        : { 'content-type': 'application/json', authorization: `Bearer ${apiKey}` }
      const body = isAnthropic
        ? JSON.stringify({
            model: p.model,
            max_tokens: 4096,
            stream: true,
            system: req.system,
            messages: req.turns,
            ...(req.tools.length > 0 ? { tools: req.tools } : {})
          })
        : JSON.stringify({ model: p.model, stream: true, messages: req.turns })

      const res = await fetch(url, { method: 'POST', headers, body, signal: controller.signal })
      if (!res.ok || !res.body) {
        const detail = await res.text().catch(() => '')
        throw new Error(`模型服务返回 HTTP ${res.status}${detail ? `: ${detail.slice(0, 300)}` : ''}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data:')) continue
          const payload = trimmed.slice(5).trim()
          if (payload === '[DONE]') continue
          try {
            const json = JSON.parse(payload) as {
              type?: string
              index?: number
              content_block?: { type?: string; id?: string; name?: string }
              delta?: { type?: string; text?: string; thinking?: string; partial_json?: string; stop_reason?: string }
              choices?: { delta?: { content?: string }; finish_reason?: string }[]
            }
            if (isAnthropic) {
              if (json.type === 'content_block_start' && json.content_block?.type) {
                blocks.set(json.index ?? 0, {
                  type: json.content_block.type,
                  text: '',
                  thinking: '',
                  id: json.content_block.id,
                  name: json.content_block.name,
                  json: ''
                })
              } else if (json.type === 'content_block_delta') {
                const block = blocks.get(json.index ?? 0)
                if (!block) continue
                if (json.delta?.type === 'text_delta' && json.delta.text) {
                  block.text += json.delta.text
                  req.onEvent({ kind: 'text', delta: json.delta.text })
                } else if (json.delta?.type === 'thinking_delta' && json.delta.thinking) {
                  block.thinking += json.delta.thinking
                  req.onEvent({ kind: 'thinking', delta: json.delta.thinking })
                } else if (json.delta?.type === 'input_json_delta' && json.delta.partial_json) {
                  block.json += json.delta.partial_json
                }
              } else if (json.type === 'message_delta' && json.delta?.stop_reason) {
                stopReason = normalizeStopReason(json.delta.stop_reason)
              }
            } else {
              const delta = json.choices?.[0]?.delta?.content ?? ''
              if (delta) {
                const block = blocks.get(-1) ?? { type: 'text', text: '', thinking: '', json: '' }
                block.text += delta
                blocks.set(-1, block)
                req.onEvent({ kind: 'text', delta })
              }
              const finish = json.choices?.[0]?.finish_reason
              if (finish) stopReason = normalizeStopReason(finish)
            }
          } catch {
            /* 非 JSON 行忽略 */
          }
        }
      }
    } catch (e) {
      // 用户中止：保留已生成的部分内容，交循环层收尾（is_error 提示用户可见）
      if (e instanceof Error && (e.name === 'AbortError' || controller.signal.aborted)) {
        return assemble(blocks, 'aborted')
      }
      throw e
    } finally {
      this.aborts.delete(sessionId)
    }
    return assemble(blocks, stopReason)

    function assemble(blockMap: Map<number, BlockState>, reason: StopReason): StreamTurnResult {
      const ordered = [...blockMap.entries()].sort((a, b) => a[0] - b[0]).map(([, b]) => b)
      const text = ordered
        .filter((b) => b.type === 'text')
        .map((b) => b.text)
        .join('')
      const thinking = ordered
        .filter((b) => b.type === 'thinking')
        .map((b) => b.thinking)
        .join('')
      const toolUses: StreamTurnResult['toolUses'] = []
      const assistantBlocks: StreamTurnResult['assistantBlocks'] = []
      for (const b of ordered) {
        if (b.type === 'text' && b.text) assistantBlocks.push({ type: 'text', text: b.text })
        if (b.type === 'tool_use') {
          let input: Record<string, unknown> = {}
          try {
            input = b.json ? (JSON.parse(b.json) as Record<string, unknown>) : {}
          } catch {
            input = {}
          }
          toolUses.push({ id: b.id ?? `toolu-missing-${toolUses.length}`, name: b.name ?? 'unknown', input })
          assistantBlocks.push({ type: 'tool_use', id: b.id ?? `toolu-missing-${toolUses.length}`, name: b.name ?? 'unknown', input })
        }
      }
      // 彻底空响应视为异常（连 thinking 都没有），交由循环层按失败说明
      if (!text && !thinking && toolUses.length === 0 && reason !== 'aborted') {
        throw new Error('模型返回了空回复')
      }
      return { stopReason: reason, text, thinking, toolUses, assistantBlocks }
    }
  }
}

function normalizeStopReason(raw: string): StopReason {
  if (raw === 'tool_use' || raw === 'tool_calls') return 'tool_use'
  if (raw === 'end_turn' || raw === 'stop') return 'end_turn'
  if (raw === 'max_tokens' || raw === 'length') return 'max_tokens'
  if (raw === 'stop_sequence') return 'stop_sequence'
  return 'other'
}
