import { describe, it, expect } from 'vitest'
import { splitReferences } from '../paperAdapter'
import fs from 'fs'

const l16 = JSON.parse(fs.readFileSync('C:/Users/pc/AppData/Local/Temp/l16_v2.json', 'utf-8'))
const refs = []
for (const p of (l16.page_layout || [])) {
  for (const b of (p.blocks || [])) {
    if (b.type === 'reference_list') refs.push(b.text || '')
  }
}
const combinedText = refs.join('\n')

describe('debug splitReferences ID 16', () => {
  it('debug', () => {
    const r = splitReferences(combinedText)
    process.stdout.write('splitReferences 返回数量: ' + r.length + '\n')
    for (let i = 0; i < Math.min(5, r.length); i++) {
      process.stdout.write(`  [${i}] ${r[i].slice(0, 80)}...\n`)
    }
    process.stdout.write('\n原文前 600 字符:\n')
    process.stdout.write(combinedText.slice(0, 600) + '\n')
    expect(true).toBe(true)
  })
})
