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
        { type: 'paragraph', order: 1, text: 'Micro-nano bubbles (MNBs) have demonstrated broad applica-\ntion prospects in the field of environmental gover-\nnance due to their extremely large specific surface\narea, long residence time in water, and surface charge.' },
      ],
    },
  ],
}

describe('debug3', () => {
  it('debug3', () => {
    const kb = { id: 99, title: 'Test', content: '', summary: null, tags: [] }
    const r = normalizePaperData(kb, { images: [], extractions: [], related: [], visionLayout })
    const para = r.sections[0]?.blocks[0]
    console.log('content:', para?.content)
    console.log('contains "surface area":', para.content.includes('surface area'))
    console.log('contains "specific surface":', para.content.includes('specific surface'))
    expect(true).toBe(true)
  })
})
