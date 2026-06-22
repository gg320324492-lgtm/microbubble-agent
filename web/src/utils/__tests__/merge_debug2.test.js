import { describe, it, expect } from 'vitest'
import { normalizePaperData } from '../paperAdapter'

const visionLayout = {
  has_layout: true,
  total_pages: 1,
  total_blocks: 5,
  page_layout: [
    {
      page_number: 1,
      blocks: [
        { type: 'paragraph', order: 1, text: 'Micro-nano bubbles (MNBs) have demons-\ntrated broad applica-\ntion prospects.' },
      ],
    },
  ],
}

describe('debug2', () => {
  it('debug2', () => {
    const kb = { id: 99, title: 'Test', content: '', summary: null, tags: [] }
    const r = normalizePaperData(kb, { images: [], extractions: [], related: [], visionLayout })
    console.log('sections:', r.sections.length)
    for (const s of r.sections) {
      console.log('  sec:', s.type, s.title.slice(0, 20))
      for (const b of s.blocks) {
        console.log('    block type=' + b.type + ' content=' + b.content?.slice(0, 100))
      }
    }
    expect(true).toBe(true)
  })
})
