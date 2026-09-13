// IPC 白名单一致性 — preload 暴露的方法与 main 注册的 handler 必须引用同一套 channel 常量
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { IPC } from '@shared/ipc-channels'

const root = resolve(__dirname, '../../src')

function channelsUsed(rel: string): Set<string> {
  const src = readFileSync(resolve(root, rel), 'utf8')
  const used = new Set<string>()
  for (const m of src.matchAll(/IPC\.([A-Z_]+)/g)) used.add(m[1])
  return used
}

describe('IPC 白名单一致性', () => {
  it('preload 与 main 引用的 channel 集合完全一致', () => {
    const preload = channelsUsed('preload/index.ts')
    const main = channelsUsed('main/ipc.ts')
    expect(preload.size).toBeGreaterThan(0)
    expect([...preload].sort()).toEqual([...main].sort())
  })

  it('所有声明的 channel 都被消费（无死常量）', () => {
    const declared = new Set(Object.keys(IPC))
    const used = channelsUsed('main/ipc.ts')
    expect([...used].sort()).toEqual([...declared].sort())
  })
})
