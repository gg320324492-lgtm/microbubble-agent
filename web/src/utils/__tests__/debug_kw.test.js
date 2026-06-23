import { describe, it } from 'vitest'
import { _detectKeywordsFromContent } from '../src/utils/paperAdapter.js'

describe('debug', () => {
  it('extract from raw content', () => {
    const content = `[PAGE:1]
Keywords:
微纳米气泡
臭氧
过氧化氢
甲苯氧化
活性氧物种
气液传质
水处理
无催化剂
[PAGE:2]
1. Introduction
...`
    const r = _detectKeywordsFromContent(content)
    console.log('Extracted keywords:', r)
  })
})
