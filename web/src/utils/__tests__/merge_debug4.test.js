import { describe, it, expect } from 'vitest'

function _mergeOCRSoftLineBreaks(text) {
  if (!text) return text
  let result = text
  result = result.replace(/([A-Za-z])-\s*\n\s*([a-z])/g, '$1$2')
  result = result.replace(/([A-Za-z])\s*\n\s*([a-z])/g, '$1$2')
  return result
}

describe('regex test', () => {
  it('test', () => {
    const t = 'Micro-nano bubbles (MNBs) have demonstrated broad applica-\ntion prospects in the field of environmental gover-\nnance due to their extremely large specific surface\narea, long residence time in water, and surface charge.'
    const r = _mergeOCRSoftLineBreaks(t)
    console.log('input has \n:', t.includes('\n'))
    console.log('result:', r)
    expect(true).toBe(true)
  })
})
