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
  it('preload 引用的 channel 都被 main 侧消费（ipc.ts + index.ts）', () => {
    const preload = channelsUsed('preload/index.ts')
    const main = new Set([...channelsUsed('main/ipc.ts'), ...channelsUsed('main/index.ts')])
    expect(preload.size).toBeGreaterThan(0)
    for (const ch of preload) expect(main.has(ch)).toBe(true)
  })

  it('所有声明的 channel 都被消费（无死常量）', () => {
    const declared = new Set(Object.keys(IPC))
    const used = new Set([...channelsUsed('main/ipc.ts'), ...channelsUsed('main/index.ts'), ...channelsUsed('preload/index.ts')])
    expect([...used].sort()).toEqual([...declared].sort())
  })
})
