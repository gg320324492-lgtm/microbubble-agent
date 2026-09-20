// M8-1 §3 循环与传输解耦 — 编排式 mock 驱动（正常 / 工具调用 / 中止 / 失败并文 / 重试路径）
import { describe, expect, it } from 'vitest'
import { ScriptedFailure, createRetryingScriptedStreamTurn, createScriptedStreamTurn, replaySteps } from '@main/agent/turn-stream'
import type { StreamTurnEvent, StreamTurnRequest, StreamTurnResult } from '@shared/types'

function makeReq(): { req: StreamTurnRequest; events: StreamTurnEvent[] } {
  const events: StreamTurnEvent[] = []
  return {
    events,
    req: {
      system: 'sys',
      turns: [{ role: 'user', content: '你好' }],
      tools: [],
      onEvent: (e) => events.push(e)
    }
  }
}

const instantSleep = (): { sleep: (ms: number) => Promise<void>; slept: number[] } => {
  const slept: number[] = []
  return {
    slept,
    sleep: async (ms) => {
      slept.push(ms)
    }
  }
}

describe('replaySteps — 纯数据脚本 → 一轮结果', () => {
  it('文本与思考按序回放，stopReason=end_turn', async () => {
    const { req, events } = makeReq()
    const res = await replaySteps(
      [
        { kind: 'thinking', delta: '想一下' },
        { kind: 'text', delta: '你好' },
        { kind: 'text', delta: '，世界' }
      ],
      req
    )
    expect(res.text).toBe('你好，世界')
    expect(res.thinking).toBe('想一下')
    expect(res.stopReason).toBe('end_turn')
    expect(events).toEqual([
      { kind: 'thinking', delta: '想一下' },
      { kind: 'text', delta: '你好' },
      { kind: 'text', delta: '，世界' }
    ])
    expect(res.assistantBlocks).toEqual([{ type: 'text', text: '你好，世界' }])
  })

  it('工具调用 → stopReason=tool_use，toolUses 与 assistantBlocks 同步（thinking 不回传）', async () => {
    const { req } = makeReq()
    const res = await replaySteps(
      [
        { kind: 'thinking', delta: '需要读文件' },
        { kind: 'text', delta: '我看一下' },
        { kind: 'tool', name: 'read_file', input: { path: 'a.md' } }
      ],
      req
    )
    expect(res.stopReason).toBe('tool_use')
    expect(res.toolUses).toHaveLength(1)
    expect(res.toolUses[0]!.name).toBe('read_file')
    expect(res.toolUses[0]!.id).toMatch(/^toolu_scripted_1$/)
    expect(res.assistantBlocks.map((b) => b.type)).toEqual(['text', 'tool_use'])
  })

  it('可显式覆盖 stopReason（如 max_tokens）', async () => {
    const { req } = makeReq()
    const res = await replaySteps([{ kind: 'text', delta: 'x' }, { kind: 'stop', reason: 'max_tokens' }], req)
    expect(res.stopReason).toBe('max_tokens')
  })

  it('delay 步骤走注入的 sleep（时序可断言）', async () => {
    const { req } = makeReq()
    const { sleep, slept } = instantSleep()
    await replaySteps([{ kind: 'delay', ms: 30 }, { kind: 'text', delta: 'a' }, { kind: 'delay', ms: 70 }], req, { sleep })
    expect(slept).toEqual([30, 70])
  })

  it('abort 步骤 → 抛出 ScriptedFailure 且 aborted=true', async () => {
    const { req } = makeReq()
    await expect(replaySteps([{ kind: 'text', delta: '半句' }, { kind: 'abort' }], req)).rejects.toBeInstanceOf(ScriptedFailure)
  })

  it('失败并文形态（throwOnFail=false）→ 正常结束且正文含中断标记', async () => {
    const { req } = makeReq()
    const res = await replaySteps([{ kind: 'text', delta: '开头' }, { kind: 'fail', status: 500 }], req, { throwOnFail: false })
    expect(res.stopReason).toBe('end_turn')
    expect(res.text).toContain('开头')
    expect(res.text).toContain('[本轮中断]')
  })
})

describe('createScriptedStreamTurn — 多轮编排', () => {
  it('按轮次取脚本，越界复用最后一个', async () => {
    const calls: number[] = []
    const fn = createScriptedStreamTurn({
      turns: [[{ kind: 'text', delta: '第一轮' }], [{ kind: 'text', delta: '第二轮' }]],
      onCall: (n) => calls.push(n)
    })
    const { req } = makeReq()
    expect((await fn('u', 's', req)).text).toBe('第一轮')
    expect((await fn('u', 's', req)).text).toBe('第二轮')
    expect((await fn('u', 's', req)).text).toBe('第二轮') // 越界复用最后一个
    expect(calls).toEqual([1, 2, 3])
  })

  it('onCall 能拿到该轮的请求（可断言 system/turns 被正确传递）', async () => {
    let seen: StreamTurnRequest | null = null
    const fn = createScriptedStreamTurn({ steps: [{ kind: 'text', delta: 'x' }], onCall: (_n, req) => (seen = req) })
    const { req } = makeReq()
    await fn('u', 's', req)
    expect(seen).not.toBeNull()
    expect((seen as unknown as StreamTurnRequest).system).toBe('sys')
    expect((seen as unknown as StreamTurnRequest).turns).toHaveLength(1)
  })
})

describe('createRetryingScriptedStreamTurn — 重试路径的循环行为', () => {
  it('首次 429 → 重试成功：事件只出现一次（未提交前重试对上层透明）', async () => {
    const { sleep, slept } = instantSleep()
    const retries: Array<{ attempt: number; delayMs: number }> = []
    const fn = createRetryingScriptedStreamTurn({
      turns: [[{ kind: 'fail', status: 429 }], [{ kind: 'text', delta: '重试成功' }]],
      sleep,
      random: () => 0.5,
      onRetry: (i) => retries.push({ attempt: i.attempt, delayMs: i.delayMs })
    })
    const { req, events } = makeReq()
    const res = await fn('u', 's', req)
    expect(res.text).toBe('重试成功')
    expect(retries).toEqual([{ attempt: 1, delayMs: 1000 }])
    expect(slept).toEqual([1000])
    // 关键：重试对上层完全透明 —— 事件序列里没有任何「失败」痕迹
    expect(events).toEqual([{ kind: 'text', delta: '重试成功' }])
  })

  it('已提交后失败 → 不重试，抛出中性文案（避免重复内容）', async () => {
    const { sleep, slept } = instantSleep()
    let call = 0
    const fn = createRetryingScriptedStreamTurn({
      turns: [[{ kind: 'text', delta: '已经开始输出' }, { kind: 'fail', status: 500 }], [{ kind: 'text', delta: '不该发生' }]],
      sleep,
      random: () => 0.5
    })
    const { req, events } = makeReq()
    await expect(fn('u', 's', req)).rejects.toThrow(/模型服务出现内部错误/)
    expect(slept).toEqual([]) // 未发生重试
    expect(events).toEqual([{ kind: 'text', delta: '已经开始输出' }])
    call += 1
    expect(call).toBe(1)
  })

  it('5xx 连续失败 → 用尽 5 次重试后抛出，退避序列 1s/2s/4s/8s/16s', async () => {
    const { sleep, slept } = instantSleep()
    const fn = createRetryingScriptedStreamTurn({
      turns: [
        [{ kind: 'fail', status: 503 }],
        [{ kind: 'fail', status: 503 }],
        [{ kind: 'fail', status: 503 }],
        [{ kind: 'fail', status: 503 }],
        [{ kind: 'fail', status: 503 }],
        [{ kind: 'fail', status: 503 }]
      ],
      sleep,
      random: () => 0.5
    })
    const { req } = makeReq()
    await expect(fn('u', 's', req)).rejects.toThrow(/繁忙|稍后再试/)
    expect(slept).toEqual([1000, 2000, 4000, 8000, 16000])
  })

  it('尊重 Retry-After（编排里带上响应头即按它等待）', async () => {
    const { sleep, slept } = instantSleep()
    const fn = createRetryingScriptedStreamTurn({
      turns: [[{ kind: 'fail', status: 429, headers: { 'retry-after': '4' } }], [{ kind: 'text', delta: 'ok' }]],
      sleep,
      random: () => 0.5
    })
    const { req } = makeReq()
    await expect(fn('u', 's', req)).resolves.toMatchObject({ text: 'ok' } as Partial<StreamTurnResult>)
    expect(slept).toEqual([4000])
  })

  it('401 不可重试 → 立即失败，无 sleep（中性文案指向设置页）', async () => {
    const { sleep, slept } = instantSleep()
    const fn = createRetryingScriptedStreamTurn({ turns: [[{ kind: 'fail', status: 401 }]], sleep })
    const { req } = makeReq()
    await expect(fn('u', 's', req)).rejects.toThrow(/设置 · 模型服务|凭据/)
    expect(slept).toEqual([])
  })
})
