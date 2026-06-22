import { describe, it, expect } from 'vitest'
// 测 paperAdapter 实际调用
import { normalizePaperData, splitReferences } from '../paperAdapter'

const visionLayout = {
  has_layout: true,
  total_pages: 1,
  total_blocks: 5,
  page_layout: [
    {
      page_number: 1,
      blocks: [
        { type: 'paragraph', order: 1, text: 'Micro-nano bubbles (MNBs) have demonstrated broad applica-\ntion prospects in the field of environmental gover-\nnance due to their extremely large specific surface\narea, long residence time in water, and surface charge.' },
      ],
    },
  ],
}

describe('debug5', () => {
  it('debug5', () => {
    const kb = { id: 99, title: 'Test', content: '', summary: null, tags: [] }
    const r = normalizePaperData(kb, { images: [], extractions: [], related: [], visionLayout })
    for (const s of r.sections) {
      console.log('sec:', s.type, s.title.slice(0, 30))
      for (const b of s.blocks) {
        if (b.type === 'paragraph') {
          console.log('  para.content=' + JSON.stringify(b.content))
        }
      }
    }
    expect(true).toBe(true)
  })
})
