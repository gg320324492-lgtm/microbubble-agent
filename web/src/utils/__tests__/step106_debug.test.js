import { describe, it, expect } from 'vitest'
import { normalizePaperData } from '../paperAdapter'

const visionLayout = {
  has_layout: true,
  total_pages: 9,
  total_blocks: 30,
  page_layout: [
    {
      page_number: 8,
      blocks: [
        { type: 'heading', level: 1, order: 1, text: '3.4 Anti-interference' },
        { type: 'paragraph', order: 2, text: 'first paragraph on page 8' },
        { type: 'paragraph', order: 3, text: 'second paragraph on page 8' },
        { type: 'image', order: 4, image_index: 2, caption: 'Fig. 4. Anti-interference.', figure_no: 'Fig. 4' },
      ],
    },
    {
      page_number: 8,
      blocks: [
        { type: 'heading', level: 1, order: 1, text: '3.4 Anti-interference' },
        { type: 'paragraph', order: 2, text: 'first paragraph on page 8' },
        { type: 'paragraph', order: 3, text: 'second paragraph on page 8' },
        { type: 'image', order: 4, image_index: 2, caption: 'Fig. 4. Anti-interference.', figure_no: 'Fig. 4' },
      ],
    },
    {
      page_number: 9,
      blocks: [
        { type: 'heading', level: 1, order: 1, text: '3.5 Mechanism' },
      ],
    },
  ],
}

describe('debug', () => {
  it('debug', () => {
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] }, {
      images: [{ id: 901, page_number: 8, pageNumber: 8, image_url: '/img/4.png', figure_no: 'Fig. 4', figure_type: 'chart', is_core_figure: true, is_publisher_image: false }],
      extractions: [], related: [], visionLayout,
    })
    for (let i = 0; i < r.sections.length; i++) {
      const s = r.sections[i]
      console.log(`sec[${i}] type=${s.type} title="${(s.title||'').slice(0,40)}" blocks=${s.blocks.length}`)
      for (let j = 0; j < s.blocks.length; j++) {
        const b = s.blocks[j]
        console.log(`  block[${j}] type=${b.type} page=${b.page} preview="${String(b.content||b.caption||b.text||'').slice(0,40)}"`)
      }
    }
    expect(true).toBe(true)
  })
})
