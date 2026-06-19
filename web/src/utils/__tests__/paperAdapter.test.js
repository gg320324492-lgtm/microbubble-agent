/**
 * paperAdapter 单元测试
 * 覆盖：英文论文、中文论文、无摘要、无图、图很多、含公式/表格/参考文献
 */
import { describe, it, expect } from 'vitest'
import {
  normalizePaperData,
  parsePaperSections,
  extractPageMarkers,
  extractFigureMarkers,
  extractTableMarkers,
  splitReferences,
  buildAnchorTree,
  autoLinkContent,
} from '../paperAdapter'

describe('extractPageMarkers', () => {
  it('识别 [PAGE:N] 标准格式', () => {
    const content = '[PAGE:1]Title[PAGE:2]Body[PAGE:3]More'
    const markers = extractPageMarkers(content)
    expect(markers).toHaveLength(3)
    expect(markers[0]).toMatchObject({ page: 1, index: 0 })
    expect(markers[1]).toMatchObject({ page: 2, index: 13 })
    expect(markers[2]).toMatchObject({ page: 3, index: 25 })
  })

  it('识别中文 第N页 格式', () => {
    const content = '第一段\n第2页\n第二段\n第 10 页\n结束'
    const markers = extractPageMarkers(content)
    expect(markers.length).toBeGreaterThanOrEqual(2)
  })

  it('空内容返回空数组', () => {
    expect(extractPageMarkers('')).toEqual([])
    expect(extractPageMarkers(null)).toEqual([])
  })

  it('去重：同一 page 的多个格式只保留一个', () => {
    const content = '[PAGE:1]xxx Page 1 yyy'
    const markers = extractPageMarkers(content)
    // 不应该重复
    const pages = markers.map(m => m.page)
    const uniq = new Set(pages)
    expect(uniq.size).toBe(pages.length)
  })
})

describe('extractFigureMarkers', () => {
  it('识别 [FIGURE:N]', () => {
    const content = 'text[FIGURE:1]more[FIGURE:2]'
    const markers = extractFigureMarkers(content)
    expect(markers).toHaveLength(2)
    expect(markers[0].id).toBe('1')
    expect(markers[1].id).toBe('2')
  })

  it('识别 [FIGURE:1.2] 子图', () => {
    const content = 'text[FIGURE:1.2]'
    const markers = extractFigureMarkers(content)
    expect(markers).toHaveLength(1)
    expect(markers[0].id).toBe('1.2')
  })

  it('空内容返回空', () => {
    expect(extractFigureMarkers('')).toEqual([])
  })
})

describe('extractTableMarkers', () => {
  it('识别 [TABLE:N]', () => {
    const content = 'a[TABLE:1]b'
    const markers = extractTableMarkers(content)
    expect(markers).toHaveLength(1)
    expect(markers[0].id).toBe('1')
  })
})

describe('parsePaperSections - 纯文本', () => {
  it('识别英文论文章节（Abstract / Introduction / Conclusion）', () => {
    const content = `[PAGE:1]
Title of paper
Authors
[PAGE:2]
Abstract
This paper presents a novel method for micro-nano bubble generation.
Keywords: bubble, ozone, oxidation
[PAGE:3]
1 Introduction
Micro-nano bubbles have been widely used in water treatment.
[PAGE:5]
2 Materials and methods
2.1 Reagents
All chemicals were analytical grade.
[PAGE:8]
3 Results and discussion
The results show that...
[PAGE:11]
4 Conclusion
This study demonstrates the effectiveness of ozone micro-nano bubbles.
[PAGE:12]
References
[1] Smith J, et al. J. Environ. Sci., 2020, 12(3), 45-67.
[2] Wang L, Zhang H. Chem. Eng. J., 2019, 378, 122-134.
`
    const sections = parsePaperSections(content, { isMarkdown: false })
    // 至少识别出 abstract / introduction / methods / results / conclusion / references
    const types = sections.map(s => s.type)
    expect(types).toContain('abstract')
    expect(types).toContain('introduction')
    expect(types).toContain('methods')
    expect(types).toContain('results')
    expect(types).toContain('conclusion')
    expect(types).toContain('references')
  })

  it('识别中文论文章节（摘要 / 引言 / 实验方法 / 结论）', () => {
    const content = `[PAGE:1]
题目：臭氧微纳米气泡氧化甲苯的研究
[PAGE:2]
摘要
本文研究了臭氧微纳米气泡催化氧化甲苯的效果。
关键词：臭氧；微纳米气泡；甲苯
[PAGE:3]
1 引言
微纳米气泡技术是一种新兴的水处理技术。
[PAGE:4]
1.1 研究背景
近年来水污染问题日益严重。
[PAGE:5]
2 实验方法
2.1 实验材料
本实验所用试剂均为分析纯。
[PAGE:8]
3 结果与讨论
实验结果表明...
[PAGE:11]
4 结论
本文方法具有高效、环保的优点。
[PAGE:12]
参考文献
[1] 张三, 李四. 环境科学, 2020, 41(3), 123-135.
[2] 王五, 赵六. 化学工程, 2019, 35(2), 67-80.
`
    const sections = parsePaperSections(content, { isMarkdown: false })
    const types = sections.map(s => s.type)
    expect(types).toContain('abstract')
    expect(types).toContain('introduction')
    expect(types).toContain('methods')
    expect(types).toContain('results')
    expect(types).toContain('conclusion')
    expect(types).toContain('references')
  })

  it('完全识别不出章节时不报错，返回单 section', () => {
    const content = 'Just some random text without any structure markers.\nMore text here.\nEven more lines.'
    const sections = parsePaperSections(content)
    expect(sections.length).toBeGreaterThanOrEqual(1)
    expect(sections[0].blocks.length).toBeGreaterThan(0)
  })

  it('空内容返回空数组', () => {
    expect(parsePaperSections('')).toEqual([])
    expect(parsePaperSections(null)).toEqual([])
  })
})

describe('parsePaperSections - Markdown', () => {
  it('按 # / ## / ### 拆分', () => {
    const md = `# Main Title

## Introduction

Some intro text.

### Background

Background details.

## Methods

Method details.
`
    const sections = parsePaperSections(md, { isMarkdown: true })
    expect(sections.length).toBeGreaterThanOrEqual(3)
    expect(sections[0].title).toContain('Main')
    expect(sections.find(s => s.title.includes('Introduction'))).toBeDefined()
    expect(sections.find(s => s.title.includes('Methods'))).toBeDefined()
  })
})

describe('splitReferences', () => {
  it('按 [1] / 1. 拆分参考文献', () => {
    const refText = `[1] Smith J, et al. J. Environ. Sci., 2020, 12(3), 45-67.
[2] Wang L, Zhang H. Chem. Eng. J., 2019, 378, 122-134.
[3] Liu X. Water Res., 2018, 50, 100-110.`
    const refs = splitReferences(refText)
    expect(refs).toHaveLength(3)
    expect(refs[0]).toMatch(/Smith J/)
    expect(refs[2]).toMatch(/Liu X/)
  })

  it('空参考文献返回空', () => {
    expect(splitReferences('')).toEqual([])
  })
})

describe('buildAnchorTree', () => {
  it('从 sections 生成导航树', () => {
    const sections = [
      { id: 's1', title: 'Abstract', level: 1, type: 'abstract' },
      { id: 's2', title: '1 Introduction', level: 1, type: 'introduction' },
      { id: 's3', title: '1.1 Background', level: 2, type: 'normal' },
    ]
    const tree = buildAnchorTree(sections)
    expect(tree).toHaveLength(3)
    expect(tree[0]).toMatchObject({ id: 's1', title: 'Abstract', anchor: 'section-s1' })
    expect(tree[2].level).toBe(2)
  })

  it('过滤空 title', () => {
    const sections = [
      { id: 's1', title: '', level: 1 },
      { id: 's2', title: 'Real Title', level: 1 },
    ]
    const tree = buildAnchorTree(sections)
    expect(tree).toHaveLength(1)
  })
})

describe('autoLinkContent', () => {
  it('DOI 转链接', () => {
    const text = 'See DOI: 10.1016/j.watres.2020.115962 for details.'
    const html = autoLinkContent(text)
    expect(html).toContain('href="https://doi.org/10.1016/j.watres.2020.115962"')
  })

  it('URL 转链接', () => {
    const text = 'Visit https://example.com for info'
    const html = autoLinkContent(text)
    expect(html).toContain('href="https://example.com"')
  })

  it('邮箱转链接', () => {
    const text = 'Contact author@example.com for help'
    const html = autoLinkContent(text)
    expect(html).toContain('href="mailto:author@example.com"')
  })

  it('HTML 字符先转义再插链接', () => {
    const text = '<script>alert(1)</script> 10.1234/abcd'
    const html = autoLinkContent(text)
    expect(html).not.toContain('<script>')
    expect(html).toContain('&lt;script&gt;')
  })

  it('空内容返回空串', () => {
    expect(autoLinkContent('')).toBe('')
  })
})

describe('normalizePaperData', () => {
  it('完整英文论文', () => {
    const raw = {
      id: 1,
      title: 'Catalyst-free aqueous-phase oxidation of toluene by ozone micro-nanobubbles',
      content: `[PAGE:1]
Title here
[PAGE:2]
Abstract
This paper presents a novel ozone micro-nanobubble system for toluene oxidation. The system achieves high removal efficiency without any catalyst addition.
Keywords: ozone, micro-nanobubble, toluene, oxidation
[PAGE:3]
1 Introduction
Micro-nano bubbles are sub-millimeter gas bubbles.
[PAGE:5]
2 Materials and methods
2.1 Chemicals
Toluene was analytical grade.
[PAGE:8]
3 Results and discussion
The results show effective toluene degradation.
[PAGE:11]
4 Conclusion
Ozone micro-nanobubbles effectively oxidize toluene.
[PAGE:12]
References
[1] Smith J, et al. Environ. Sci. Technol., 2020, 54, 100-110.
`,
      summary: 'A novel catalyst-free system for toluene oxidation.',
      tags: ['ozone', 'micro-nanobubble', 'toluene'],
      file_name: 'paper.pdf',
      file_type: 'application/pdf',
      analysis_status: 'done',
      created_at: '2026-06-19T10:00:00',
      updated_at: '2026-06-19T10:00:00',
    }
    const paper = normalizePaperData(raw, {
      images: [
        { id: 1, page_number: 3, image_url: 'http://x.com/fig1.png', ocr_status: 'done', width: 800, height: 600 },
        { id: 2, page_number: 8, image_url: 'http://x.com/fig2.png', ocr_status: 'done', width: 800, height: 600 },
      ],
      extractions: [
        { id: 1, kind: 'formula', page_number: 5, content_text: 'O3 + H2O2 → •OH', confidence: 0.9, data: { latex: 'O_3 + H_2O_2 \\rightarrow \\cdot OH' } },
        { id: 2, kind: 'chart', page_number: 8, content_text: 'Toluene removal efficiency vs time', confidence: 0.85, data: { description: 'Line chart showing degradation kinetics' } },
      ],
      related: [
        { id: 99, title: 'Related Paper 1', score: 0.85, relation_type: 'similar', reason: 'Similar topic' },
      ],
    })
    expect(paper).toBeTruthy()
    expect(paper.title).toContain('Catalyst-free')
    // 后端 summary 优先（用户编辑过的）
    expect(paper.abstract).toContain('catalyst-free')
    // 关键词
    expect(paper.keywords).toContain('ozone')
    // 章节应识别出 abstract/intro/methods/results/conclusion/references
    const types = paper.sections.map(s => s.type)
    expect(types).toContain('abstract')
    expect(types).toContain('introduction')
    expect(types).toContain('methods')
    expect(types).toContain('results')
    expect(types).toContain('conclusion')
    expect(types).toContain('references')
    expect(paper.figures).toHaveLength(2)
    expect(paper.formulas).toHaveLength(1)
    expect(paper.extractions.length).toBeGreaterThanOrEqual(1)
    expect(paper.relatedKnowledge).toHaveLength(1)
    expect(paper.references.length).toBeGreaterThan(0)
    expect(paper.isChineseHeavy).toBe(false)
  })

  it('中文论文：isChineseHeavy 为 true', () => {
    const raw = {
      id: 2,
      title: '臭氧微纳米气泡氧化甲苯的研究',
      content: `[PAGE:1]
题目
[PAGE:2]
摘要
本文研究了臭氧微纳米气泡催化氧化甲苯的效果。
关键词：臭氧；微纳米气泡
[PAGE:3]
1 引言
微纳米气泡是一种新兴技术。
[PAGE:5]
2 实验方法
试剂均为分析纯。
[PAGE:8]
3 结果
结果良好。
[PAGE:11]
4 结论
本方法有效。
[PAGE:12]
参考文献
[1] 张三, 李四. 环境科学, 2020.
`,
      summary: null,
      tags: null,
      file_name: 'cn.pdf',
      analysis_status: 'done',
      created_at: '2026-06-19T10:00:00',
      updated_at: '2026-06-19T10:00:00',
    }
    const paper = normalizePaperData(raw)
    expect(paper.isChineseHeavy).toBe(true)
    expect(paper.abstract).toBeTruthy()
    expect(paper.keywords).toContain('臭氧')
    const types = paper.sections.map(s => s.type)
    expect(types).toContain('abstract')
    expect(types).toContain('conclusion')
  })

  it('完全没有内容时不抛错', () => {
    const raw = {
      id: 3,
      title: 'Empty',
      content: '',
      summary: null,
      tags: null,
      analysis_status: 'pending',
      created_at: '2026-06-19T10:00:00',
      updated_at: '2026-06-19T10:00:00',
    }
    const paper = normalizePaperData(raw)
    expect(paper).toBeTruthy()
    expect(paper.title).toBe('Empty')
    expect(paper.sections).toEqual([])
    expect(paper.figures).toEqual([])
    expect(paper.formulas).toEqual([])
  })

  it('图很多的论文：30+ 图片正常处理', () => {
    const raw = {
      id: 4,
      title: 'Image-rich paper',
      content: 'Some content',
      summary: null,
      tags: null,
      file_name: 'r.pdf',
      analysis_status: 'done',
      created_at: '2026-06-19T10:00:00',
      updated_at: '2026-06-19T10:00:00',
    }
    const images = []
    for (let i = 1; i <= 35; i += 1) {
      images.push({ id: i, page_number: i % 10 + 1, image_url: `http://x.com/fig${i}.png`, ocr_status: 'done' })
    }
    const paper = normalizePaperData(raw, { images })
    expect(paper.figures).toHaveLength(35)
  })

  it('有 formatted_content (markdown) 走 markdown 解析', () => {
    const raw = {
      id: 5,
      title: 'Markdown paper',
      content: 'Original raw',
      formatted_content: `# Main Title

## Abstract

This is the abstract in markdown.

## 1 Introduction

Some intro text.
`,
      summary: 'abstract summary',
      tags: ['x'],
      file_name: 'm.pdf',
      analysis_status: 'done',
      created_at: '2026-06-19T10:00:00',
      updated_at: '2026-06-19T10:00:00',
    }
    const paper = normalizePaperData(raw)
    expect(paper.sections.length).toBeGreaterThan(2)
    expect(paper.sections.some(s => s.title.includes('Abstract'))).toBe(true)
  })

  it('相关知识为空时安全降级', () => {
    const raw = {
      id: 6,
      title: 'No related',
      content: 'Content',
      summary: null,
      tags: null,
      analysis_status: 'done',
      created_at: '2026-06-19T10:00:00',
      updated_at: '2026-06-19T10:00:00',
    }
    const paper = normalizePaperData(raw)
    expect(paper.relatedKnowledge).toEqual([])
  })

  it('多模态数据为空时安全降级', () => {
    const raw = {
      id: 7,
      title: 'No multimodal',
      content: 'Content',
      summary: null,
      tags: null,
      analysis_status: 'done',
      created_at: '2026-06-19T10:00:00',
      updated_at: '2026-06-19T10:00:00',
    }
    const paper = normalizePaperData(raw, { images: [], extractions: [] })
    expect(paper.figures).toEqual([])
    expect(paper.formulas).toEqual([])
    expect(paper.tables).toEqual([])
    expect(paper.extractions).toEqual([])
  })

  it('没有 references section 时 references 为空', () => {
    const raw = {
      id: 8,
      title: 'No references',
      content: '[PAGE:1]Hello',
      summary: null,
      tags: null,
      analysis_status: 'done',
      created_at: '2026-06-19T10:00:00',
      updated_at: '2026-06-19T10:00:00',
    }
    const paper = normalizePaperData(raw)
    expect(paper.references).toEqual([])
  })
})

describe('解析鲁棒性', () => {
  it('章节标题后面是空行也能识别', () => {
    const content = 'Abstract\n\nThis is the abstract.'
    const sections = parsePaperSections(content, { isMarkdown: false })
    const types = sections.map(s => s.type)
    expect(types).toContain('abstract')
  })

  it('异常换行：OCR 断行合并', () => {
    // simulate _cleanText
    const paper = normalizePaperData({
      id: 9,
      title: 'OCR',
      content: '中文一\n中文二\n中文三',
      summary: null,
      tags: null,
      analysis_status: 'done',
      created_at: '2026-06-19T10:00:00',
      updated_at: '2026-06-19T10:00:00',
    })
    expect(paper.isChineseHeavy).toBe(true)
  })

  it('超长内容（>10000 字符）不抛错', () => {
    const longContent = 'Some text. '.repeat(2000)
    const paper = normalizePaperData({
      id: 10,
      title: 'Long',
      content: longContent,
      summary: null,
      tags: null,
      analysis_status: 'done',
      created_at: '2026-06-19T10:00:00',
      updated_at: '2026-06-19T10:00:00',
    })
    expect(paper).toBeTruthy()
    expect(paper.sections.length).toBeGreaterThan(0)
  })
})
