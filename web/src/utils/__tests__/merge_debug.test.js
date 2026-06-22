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
        { type: 'paragraph', order: 1, text: 'Micro-nano bubbles (MNBs) have demons-\ntrated broad applica-\ntion prospects in the field of environmental gover-\nnance.' },
      ],
    },
  ],
}

describe('debug', () => {
  it('debug', () => {
    const kb = { id: 99, title: 'Test', content: '', summary: null, tags: [] }
    const r = normalizePaperData(kb, { images: [], extractions: [], related: [], visionLayout })
    const para = r.sections[0]?.blocks[0]
    console.log('content:', para?.content)
    expect(true).toBe(true)
  })
})
