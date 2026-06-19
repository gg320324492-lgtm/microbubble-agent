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
  cleanContent,
  classifyImageKind,
  matchFiguresWithCaptions,
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
    const { sections: tree } = buildAnchorTree(sections)
    expect(tree).toHaveLength(3)
    expect(tree[0]).toMatchObject({ id: 's1', title: 'Abstract', anchor: 'section-s1' })
    expect(tree[2].level).toBe(2)
  })

  it('过滤空 title', () => {
    const sections = [
      { id: 's1', title: '', level: 1 },
      { id: 's2', title: 'Real Title', level: 1 },
    ]
    const { sections: tree } = buildAnchorTree(sections)
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


// ============================================================
// cleanContent 测试（第二轮优化新增）
// ============================================================

describe('cleanContent', () => {
  it('剥离 HTML 属性残留（target/rel/class/style/width/height）', () => {
    const text = '<a href="x" target="_blank" rel="noopener" class="link" style="color:red" width="100">link</a>'
    const { content } = cleanContent(text, { stripImageUrls: false })
    expect(content).not.toContain('target=')
    expect(content).not.toContain('rel=')
    expect(content).not.toContain('class=')
    expect(content).not.toContain('style=')
    expect(content).not.toContain('width=')
  })

  it('剥离 markdown 图片语法 ![alt](url) 到 figures', () => {
    const text = '前面文字 ![图 1](https://x.com/fig1.png "图1") 后面文字'
    const { content, extractedImages } = cleanContent(text)
    expect(content).not.toContain('![')
    expect(content).not.toContain('.png')
    expect(extractedImages.length).toBe(1)
    expect(extractedImages[0].url).toBe('https://x.com/fig1.png')
    expect(extractedImages[0].alt).toBe('图 1')
  })

  it('剥离裸图片 URL（行内 + 整行）', () => {
    const text = '看图 https://x.com/foo.jpg 这里。\nhttps://x.com/bar.png\n继续'
    const { content, extractedImages } = cleanContent(text)
    expect(content).not.toContain('.jpg')
    expect(content).not.toContain('.png')
    expect(extractedImages.length).toBe(2)
  })

  it('剥离 agent.mnb-lab.cn/minio 内部图片 URL', () => {
    const text = '看图 https://agent.mnb-lab.cn/minio/microbubble/avatars/abc.png'
    const { content, extractedImages } = cleanContent(text)
    expect(content).not.toContain('minio')
    expect(extractedImages.length).toBe(1)
  })

  it('剥离系统内部标记 <!-- MULTIMODAL_INLINED v2 -->', () => {
    const text = '正文1\n<!-- MULTIMODAL_INLINED v2 -->\n正文2'
    const { content } = cleanContent(text)
    expect(content).not.toContain('MULTIMODAL_INLINED')
    expect(content).not.toContain('<!--')
  })

  it('修复重复 DOI 链接 https://doi.org/https://doi.org/xxx', () => {
    const text = '见 https://doi.org/https://doi.org/10.1234/abc 文献'
    const { content } = cleanContent(text, { stripImageUrls: false })
    expect(content).not.toContain('https://doi.org/https://doi.org/')
    expect(content).toContain('https://doi.org/10.1234/abc')
  })

  it('修复 doi.org/ 重复', () => {
    const text = 'DOI: doi.org/doi.org/10.1234/abc'
    const { content } = cleanContent(text, { stripImageUrls: false })
    expect(content).not.toContain('doi.org/doi.org/')
  })

  it('修复字符间隔的标题 H I G H L I G H T S → HIGHLIGHTS', () => {
    const text = 'H I G H L I G H T S\n- Novel method'
    const { content } = cleanContent(text)
    expect(content).toContain('HIGHLIGHTS')
    expect(content).not.toContain('H I G H L I G H T S')
  })

  it('修复字符间隔的标题 A B S T R A C T → ABSTRACT', () => {
    const text = 'A B S T R A C T\nThis paper...'
    const { content } = cleanContent(text)
    expect(content).toContain('ABSTRACT')
  })

  it('剥离 PDF 页脚（Journal of Xxx 123 (2024) 456）', () => {
    const text = '正文\nJournal of Hazardous Materials 513 (2026) 142456\n继续'
    const { content } = cleanContent(text)
    expect(content).not.toContain('Journal of Hazardous Materials')
  })

  it('剥离 "图表说明 (P4)" 孤立元行', () => {
    const text = '段落1\n图表说明 (P4)\n段落2'
    const { content } = cleanContent(text)
    expect(content).not.toContain('图表说明')
  })

  it('剥离 "Caption:" 孤立元行', () => {
    const text = '段落1\nCaption:\n段落2'
    const { content } = cleanContent(text)
    expect(content).not.toContain('Caption')
  })

  it('cleanContent 不破坏普通 DOI / URL', () => {
    const text = 'DOI: 10.1234/abc and URL: https://example.com'
    const { content, extractedImages } = cleanContent(text, { stripImageUrls: false })
    expect(extractedImages.length).toBe(0)
    expect(content).toContain('10.1234/abc')
    expect(content).toContain('https://example.com')
  })

  it('空内容返回空', () => {
    expect(cleanContent('')).toEqual({ content: '', extractedImages: [] })
    expect(cleanContent(null)).toEqual({ content: '', extractedImages: [] })
  })

  // === v26 回归修复新增 ===

  it('v26: 剥离残余 [PAGE:N] 标记（行尾、行中、独立行）', () => {
    const text = 'T. Wang et al. 3 [PAGE:4]\nSection\n[PAGE:3]\n\nPAGE:5'
    const { content } = cleanContent(text)
    expect(content).not.toContain('[PAGE:4]')
    expect(content).not.toContain('[PAGE:3]')
    expect(content).not.toContain('PAGE:5')
    expect(content).toContain('T. Wang et al.')
  })

  it('v26: 剥离 JSON 残留 { category: mixed ... }', () => {
    const text = '正文段落\n{ category: mixed, kind: chart, model: llm }\n继续'
    const { content } = cleanContent(text)
    expect(content).not.toContain('category')
    expect(content).not.toContain('kind:')
    expect(content).not.toContain('mixed')
    expect(content).toContain('正文段落')
    expect(content).toContain('继续')
  })

  it('v26: 剥离 JSON 残留 {"kind":"chart"}', () => {
    const text = '段落1\n{"kind":"chart","confidence":0.9}\n段落2'
    const { content } = cleanContent(text)
    expect(content).not.toContain('kind')
    expect(content).not.toContain('confidence')
  })

  it('v26: 剥离中文图表说明 "图（P8，{...}）"', () => {
    const text = '正文段落\n图（P8，{ category: mixed }）\n继续段落'
    const { content } = cleanContent(text)
    expect(content).not.toContain('图（P8')
    expect(content).not.toContain('category')
  })

  it('v26: 剥离中文图表说明 "图表说明（P4）"', () => {
    const text = '段落1\n图表说明（P4）\n段落2'
    const { content } = cleanContent(text)
    expect(content).not.toContain('图表说明')
  })

  it('v26: 剥离 "Figure caption (P4)" 英文变体', () => {
    const text = 'Some text\nFigure caption (P4)\nMore text'
    const { content } = cleanContent(text)
    expect(content).not.toContain('Figure caption')
  })

  it('v26: 剥离 agent/minio 内网图片 URL', () => {
    const text = '段落\nhttps://agent.mnb-lab.cn/minio/microbubble/x.jpeg\n继续'
    const { content, extractedImages } = cleanContent(text)
    expect(content).not.toContain('mnb-lab.cn')
    expect(content).not.toContain('minio')
    // 图片被提取
    expect(extractedImages.length).toBeGreaterThan(0)
  })

  it('v26: 剥离 MULTIMODAL_INLINED 标记', () => {
    const text = '段落\nMULTIMODAL_INLINED: image-1\n继续'
    const { content } = cleanContent(text)
    expect(content).not.toContain('MULTIMODAL_INLINED')
  })
})


// ============================================================
// 图片分类测试
// ============================================================

describe('classifyImageKind', () => {
  it('Elsevier logo 识别为 cover', () => {
    const img = { id: 1, page: 1, ocrText: 'Elsevier', imageUrl: 'https://x.com/fig1.png' }
    const cls = classifyImageKind(img)
    expect(cls.kind).toBe('cover')
  })

  it('copyright 文字 → cover', () => {
    const img = { id: 1, ocrText: '© 2024 Elsevier B.V. All rights reserved.' }
    expect(classifyImageKind(img).kind).toBe('cover')
  })

  it('logo 文件名 → logo', () => {
    const img = { id: 1, ocrText: '', imageUrl: 'https://x.com/brand-logo.png' }
    expect(classifyImageKind(img).kind).toBe('logo')
  })

  it('极小尺寸 → logo', () => {
    const img = { id: 1, width: 30, height: 30 }
    expect(classifyImageKind(img).kind).toBe('logo')
  })

  it('P1 无 OCR + 大尺寸 → cover', () => {
    const img = { id: 1, page: 1, ocrText: '', width: 1200, height: 800 }
    expect(classifyImageKind(img).kind).toBe('cover')
  })

  it('普通 P5 图 → figure', () => {
    const img = { id: 1, page: 5, ocrText: 'Figure 1. Setup diagram', width: 600, height: 400 }
    expect(classifyImageKind(img).kind).toBe('figure')
  })
})


// ============================================================
// matchFiguresWithCaptions 测试
// ============================================================

describe('matchFiguresWithCaptions', () => {
  it('从 extractions.data.caption 绑定 caption', () => {
    const figures = [{ id: 'fig-1', imageId: 1, src: 'x', ocrText: '' }]
    const extractions = [{
      id: 100, kind: 'image_block', sourceImageId: 1,
      data: { caption: '图 1：实验装置图' },
    }]
    const result = matchFiguresWithCaptions(figures, extractions, 'content')
    expect(result[0].caption).toBe('图 1：实验装置图')
    expect(result[0].figureNo).toBe('Fig. 1')
  })

  it('从 content 文本扫描 "Fig. 1" 后 1-3 句作为 caption', () => {
    const figures = [
      { id: 'fig-1', imageId: 11, src: 'x' },
      { id: 'fig-2', imageId: 12, src: 'y' },
    ]
    const content = `Fig. 1. The experimental setup showing reactor geometry.
Fig. 2. Toluene degradation efficiency vs time under different conditions.`
    const result = matchFiguresWithCaptions(figures, [], content)
    expect(result[0].caption).toContain('experimental setup')
    expect(result[1].caption).toContain('Toluene degradation')
  })

  it('从 content 扫描 "图 1" 也能识别（中文）', () => {
    const figures = [{ id: 'fig-1', imageId: 1, src: 'x' }]
    const content = '图 1. 微纳米气泡装置示意图，包括气泡发生器和氧化反应器。\n接下来描述方法。'
    const result = matchFiguresWithCaptions(figures, [], content)
    expect(result[0].caption).toContain('微纳米气泡')
  })

  it('没匹配上时 caption 为 null', () => {
    const figures = [{ id: 'fig-1', imageId: 99, src: 'x' }]
    const result = matchFiguresWithCaptions(figures, [], 'no figure mentioned')
    expect(result[0].caption).toBeNull()
  })
})


// ============================================================
// buildAnchorTree 升级版测试
// ============================================================

describe('buildAnchorTree (升级版)', () => {
  it('返回 {sections, modules} 结构', () => {
    const sections = [
      { id: 's1', title: 'Abstract', level: 1, type: 'abstract' },
      { id: 's2', title: '1 Introduction', level: 1, type: 'introduction' },
    ]
    const result = buildAnchorTree(sections, { moduleCounts: { figures: 3, related: 2 } })
    expect(result).toHaveProperty('sections')
    expect(result).toHaveProperty('modules')
    expect(result.sections).toHaveLength(2)
    expect(result.modules).toHaveLength(2)
  })

  it('figures / extractions / related 数量为 0 时不输出模块入口', () => {
    const result = buildAnchorTree([], { moduleCounts: { figures: 0, related: 0 } })
    expect(result.modules).toEqual([])
  })

  it('sections 为 null / undefined 时安全降级', () => {
    expect(buildAnchorTree(null).sections).toEqual([])
    expect(buildAnchorTree(undefined).modules).toEqual([])
  })
})


// ============================================================
// 端到端：当前这篇臭氧论文场景
// ============================================================

describe('完整流程：模拟当前 PDF', () => {
  it('识别 Abstract / Introduction / Methods / Results / Conclusion / References 全部章节', () => {
    const raw = {
      id: 1,
      title: 'Catalyst-free aqueous-phase oxidation of toluene by ozone micro-nanobubbles',
      content: `<PAGE:1>
H I G H L I G H T S
- A novel catalyst-free ozone micro-nanobubble system is proposed.
- Toluene removal efficiency reached 92.4% in 30 min.
A B S T R A C T
This paper presents a novel ozone micro-nanobubble system for toluene oxidation. The system achieves high removal efficiency without catalyst addition.
K E Y W O R D S
Ozone, micro-nanobubble, toluene, oxidation
<PAGE:2>
1. Introduction
The emission of toluene from industrial processes has raised serious environmental concerns.
<PAGE:3>
2. Materials and methods
2.1. Chemicals
Toluene was analytical grade.
<PAGE:5>
2.2. Experimental system
The schematic diagram is shown in Fig. 1. The system consists of a bubble generator, a reactor and an ozone supply.
<PAGE:6>
3. Results and discussion
The toluene removal efficiency was investigated. Fig. 2 shows the degradation kinetics.
<PAGE:8>
4. Conclusion
Ozone micro-nanobubbles effectively oxidize toluene with high efficiency.
<PAGE:9>
References
[1] Smith J, et al. Environ. Sci. Technol., 2020, 54, 100-110.
[2] Wang L, Zhang H. Chem. Eng. J., 2019, 378, 122-134.
Journal of Hazardous Materials 513 (2026) 142456
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
        { id: 1, page_number: 1, image_url: 'https://x.com/cover.png', ocr_status: 'done', width: 1200, height: 800, ocr_text: '' },
        { id: 2, page_number: 5, image_url: 'https://x.com/fig1.png', ocr_status: 'done', width: 800, height: 600, ocr_text: 'Figure 1 schematic' },
        { id: 3, page_number: 6, image_url: 'https://x.com/fig2.png', ocr_status: 'done', width: 800, height: 600, ocr_text: 'Figure 2 kinetics' },
      ],
    })
    // 1. 章节拆分
    const types = paper.sections.map(s => s.type)
    expect(types).toContain('abstract')
    expect(types).toContain('introduction')
    expect(types).toContain('methods')
    expect(types).toContain('results')
    expect(types).toContain('conclusion')
    expect(types).toContain('references')

    // 2. cleanContent 字符间隔修复
    const allText = paper.sections.map(s => (s.title || '') + '\n' + s.blocks.map(b => b.content).join('\n')).join('\n')
    expect(allText).not.toContain('H I G H L I G H T S')
    expect(allText).toContain('HIGHLIGHTS')

    // 3. PDF 页脚剥除
    expect(allText).not.toContain('Journal of Hazardous Materials')

    // 4. 图片分类：cover 单独出来
    const coverImgs = paper.figures.filter(f => f.kind === 'cover')
    const coreImgs = paper.figures.filter(f => f.kind === 'figure' || !f.kind)
    expect(coverImgs.length).toBeGreaterThanOrEqual(1)
    expect(coreImgs.length).toBeGreaterThanOrEqual(1)
    expect(paper.coreFigureCount).toBeGreaterThanOrEqual(2)

    // 5. 图注绑定：fig 2 / 3 应该绑定到 content 里的 Fig. 1 / Fig. 2
    const coreWithCaption = coreImgs.filter(f => f.caption)
    expect(coreWithCaption.length).toBeGreaterThanOrEqual(1)

    // 6. 关键词（raw.tags 已包含小写形式）
    expect(paper.keywords.length).toBeGreaterThan(0)
    expect(paper.keywords).toContain('ozone')

    // 7. references 拆分
    expect(paper.references.length).toBeGreaterThanOrEqual(2)
  })

  it('空 content + 空 extractions 时不报错', () => {
    const raw = {
      id: 2, title: 'Empty', content: '', summary: null, tags: null,
      analysis_status: 'done', created_at: '2026-06-19T10:00:00', updated_at: '2026-06-19T10:00:00',
    }
    const paper = normalizePaperData(raw)
    expect(paper).toBeTruthy()
    expect(paper.sections).toBeDefined()
  })
})
