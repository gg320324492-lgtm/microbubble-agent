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
  translateKeywordToEnglish,
  translateKeywordsToEnglish,
  extractAuthorsAndJournal,
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

  // v28 step 88: OCR 把所有 ref 压成一段（无 [N] 编号，无换行），
  //   且混入 "Journal Pre-proof N" / "P33-39" 水印，splitReferences 必须能拆分。
  // 用户截图（杨慈 UV/MNBs 论文）："Alapi T, Dombi A. ... Yang S, Wang Y, ..."
  //   全部塞在一条 entry 里导致 references UI 显示 1 条。
  it('v28 step 88: OCR 压扁的 references 仍能拆成多条', () => {
    const refText = `References
P33-39
参考文献（共 1 条）
展开全部 ▾
Alapi T, Dombi A. Comparative study of the UV and UV/VUV-induced photolysis of phenol in aqueous solution[J]. Journal of Photochemistry and Photobiology A: Chemistry, 2007,188(2-3): 409-418. Aslan M M, Crofcheck C, Tao D, et al. Evaluation of micro-bubble size and gas hold-up in two-phase gas–liquid columns via scattered light measurements[J]. Journal of Quantitative Spectroscopy and Radiative Transfer, 2006,101(3): 527-539. Yang J. Influencing Factors and Improvement Strategies for Ultraviolet Disinfection in Sewage Treatment Plants in Shenzhen [D]. Harbin Institute of Technology, 2013. Yang S, Wang Y, Liu Y, et al. Cereulide and emetic Bacillus cereus[J]. Foods, 2023,12(4): 833.`

    const refs = splitReferences(refText)
    // 期望至少拆出 3 条：Alapi / Aslan / Yang S（Yang J. 单作者可能合并到 Yang S）
    expect(refs.length).toBeGreaterThanOrEqual(3)
    // 关键 ref 必须出现
    const allText = refs.join('\n')
    expect(allText).toContain('Alapi T, Dombi A')
    expect(allText).toContain('Aslan M M, Crofcheck C')
    expect(allText).toContain('Yang S, Wang Y')
    // 不含 boilerplate
    expect(refs.some((r) => r.startsWith('References P33-39'))).toBe(false)
    expect(refs.some((r) => r.startsWith('参考文献'))).toBe(false)
  })

  it('v28 step 88: 剥除 Journal Pre-proof N + P33-39 水印', () => {
    const refText = `References P33-39 Gao Y, Duan Y, Fan W, et al. Intensifying ozonation[J]. Environmental Science Journal Pre-proof 32 and Pollution Research, 2019,26: 21915-21924. Sumikura M, Hidaka M, et al. Ozone micro-bubble[J]. Water Sci Technol, 2007,56(5):53-61.`

    const refs = splitReferences(refText)
    expect(refs.length).toBeGreaterThanOrEqual(2)
    const allText = refs.join('\n')
    expect(allText).not.toMatch(/Journal Pre-proof/)
    expect(allText).not.toMatch(/P33-39/)
    expect(allText).toContain('Gao Y')
    expect(allText).toContain('Sumikura M')
  })

  it('v28 step 88: 单作者 ref (Yang Y X. Title. [D]) 也能切分', () => {
    // 单作者格式：Lastname F X. Title. [D]. University, Year.
    //   不能用"Lastname F X, Author"模式切（无逗号作者列表）
    //   改用 "卷: 页码. " 或 "Year. " 后跟单作者模式切分
    const refText = `Yang J. Influencing Factors and Improvement Strategies for Ultraviolet Disinfection in Sewage Treatment Plants in Shenzhen [D]. Harbin Institute of Technology, 2013. Choi W, Kim S. Outbreaks[J]. Journal of food protection, 2020,83(9): 1480-1487.`
    const refs = splitReferences(refText)
    expect(refs.length).toBeGreaterThanOrEqual(2)
    const allText = refs.join('\n')
    expect(allText).toContain('Yang J. Influencing Factors')
    expect(allText).toContain('Choi W, Kim S')
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
    // v28 step 109.37: 中文关键词已被翻译成英文
    expect(paper.keywords).toContain('Ozone')
    expect(paper.keywords).toContain('Micro-nanobubbles')
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

  it('有 formatted_content 含 [PAGE:N] (OCR 内容) 走 plain text 路径', () => {
    // v28 fix: 含 [PAGE:N] 标记 = OCR 提取的内容, 不是 LLM 真排版的 markdown
    // 应该走 plain text 路径（用 rawContent 解析 — 纯 OCR 文本）
    // (rawFormatted 是混合格式: OCR 文本 + 注入的 markdown 标题,
    //  plain text parser 不识别 ## 标题 → 0 sections)
    // 真实 PDF: content 和 formatted_content 都含 [PAGE:N] (从同一个 OCR 提取)
    const raw = {
      id: 5,
      title: 'Markdown paper',
      content: `[PAGE:1]

Abstract

This is the abstract in OCR text.

[PAGE:2]

1 Introduction

Some intro text.

[PAGE:3]
`,
      formatted_content: `# Main Title

[PAGE:1]

## Abstract

This is the abstract in markdown.

[PAGE:2]

## 1 Introduction

Some intro text.

[PAGE:3]
`,
      summary: 'abstract summary',
      tags: ['x'],
      file_name: 'm.pdf',
      analysis_status: 'done',
      created_at: '2026-06-19T10:00:00',
      updated_at: '2026-06-19T10:00:00',
    }
    const paper = normalizePaperData(raw)
    // formatted 含 [PAGE:N] + ## 标题 (混合) → 走 plain text 路径
    // 用 rawContent 解析（纯 OCR 文本）
    expect(paper.sections.length).toBeGreaterThanOrEqual(2)
    // 关键: pageMarkers 应该 ≥ 3（从 rawContent [PAGE:1/2/3]）
    expect(paper.pageMarkers.length).toBeGreaterThanOrEqual(3)
  })

  it('有 formatted_content 真 markdown (无 [PAGE:N]) 走 markdown 解析', () => {
    // 真 LLM 排版的内容通常无 [PAGE:N] 标记, 应走 markdown 路径
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
    // simulate _cleanText — fixture 必须 > 30 中文字符才能触发 _isChineseHeavy(cn > 30)
    // OCR 真实场景：多行短句被合并成长文档，每行 3-5 字，整篇 50+ 字
    const ocrLikeContent = [
      '微纳米气泡',
      '是一种新型的',
      '水处理技术',
      '具有传质效率高',
      '停留时间长',
      '比表面积大',
      '等诸多优点',
      '近年来受到',
      '广泛关注',
    ].join('\n')
    const paper = normalizePaperData({
      id: 9,
      title: 'OCR',
      content: ocrLikeContent,
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

  // v28 step 82: front matter 剥离（Elsevier Pre-proof 风格）
  it('v28 step 82: Elsevier PDF front matter 剥离 + 抽 Abstract/Keywords', () => {
    const raw = {
      id: 82,
      title: 'Elsevier Pre-proof Test',
      content: `[PAGE:1]Journal Pre-proof
Disinfection mechanism of micro-nano bubbles
Yang Ci, Wang Tianzhi, Liu Ziyi
PII: S1385-8947(25)12584-9
DOI: https://doi.org/10.1016/j.cej.2025.171737
Reference: CEJ 171737
To appear in:
Received date: 17 August 2025
Revised date: 26 November 2025
Accepted date: 8 December 2025
Please cite this article as: Y. Ci, W. Tianzhi, L. Ziyi, et al., Mechanism (2024)
This is a PDF of an article that has undergone enhancements after acceptance.
Please
also
note
that,
during
the
production process, errors may be discovered which could affect the content, and all legal
disclaimers that apply to the journal pertain.
© 2025 Published by Elsevier B.V.
[PAGE:2]
Abstract: This paper presents a novel micro-nano bubble system.
Keywords: ozone, micro-nanobubble, water treatment
[PAGE:3]
1. Introduction
Micro-nano bubbles are sub-millimeter gas bubbles.
[PAGE:5]
2. Materials and methods
Toluene was analytical grade.
[PAGE:8]
3. Results
The results show effective degradation.
[PAGE:11]
4. Conclusion
Effective method.
[PAGE:12]
References
[1] Smith J. Nature. 2020.
[2] Wang L. Science. 2019.
`,
      summary: null,
      tags: null,
      file_name: 'elsevier.pdf',
      file_type: 'application/pdf',
      analysis_status: 'done',
      created_at: '2026-06-19T10:00:00',
      updated_at: '2026-06-19T10:00:00',
    }
    const paper = normalizePaperData(raw)

    // front matter 字段应被剥离（不应作为 sections 出现）
    const sectionContents = paper.sections.map(s => (s.content || '') + ' ' + (s.title || '')).join(' ')
    expect(sectionContents).not.toContain('Reference: CEJ')
    expect(sectionContents).not.toContain('Please cite this article as')
    expect(sectionContents).not.toContain('Pleasealsonote') // word-per-line 修复
    expect(sectionContents).not.toContain('© 2025 Published by Elsevier')
    expect(sectionContents).not.toContain('PII: S1385')

    // 1. Introduction 应该是第一个 section
    expect(paper.sections[0].type).toBe('introduction')

    // Abstract 应该被抽出（单词换行 bug 已修复）
    expect(paper.abstract).toContain('micro-nano bubble')
    expect(paper.abstract).not.toContain('Pleasealsonote')

    // References 应该在文末并有多个
    const refsSection = paper.sections.find(s => s.type === 'references')
    expect(refsSection).toBeTruthy()
    expect(paper.references.length).toBeGreaterThanOrEqual(2)
  })

  // v28 step 82: 普通 PDF (无 Elsevier 元信息) 不应触发 front matter 剥离
  it('v28 step 82: 普通 PDF 不剥离 front matter (避免误删 Abstract section)', () => {
    const raw = {
      id: 83,
      title: 'Normal Paper',
      content: `[PAGE:1]
Title here
[PAGE:2]
Abstract
This paper presents a novel system.
Keywords: ozone, water treatment
[PAGE:3]
1 Introduction
Test intro.
[PAGE:5]
2 Methods
Test methods.
[PAGE:8]
3 Results
Test results.
[PAGE:11]
4 Conclusion
Test conclusion.
[PAGE:12]
References
[1] Smith J. Nature. 2020.
`,
      summary: null,
      tags: null,
      file_name: 'normal.pdf',
      file_type: 'application/pdf',
      analysis_status: 'done',
      created_at: '2026-06-19T10:00:00',
      updated_at: '2026-06-19T10:00:00',
    }
    const paper = normalizePaperData(raw)

    // Abstract section 应该存在（不被剥离）
    const types = paper.sections.map(s => s.type)
    expect(types).toContain('abstract')
    expect(types).toContain('introduction')
    expect(types).toContain('methods')
    expect(types).toContain('results')
    expect(types).toContain('conclusion')
    expect(types).toContain('references')
  })

  // v28 step 82: 单词逐行 OCR 修复
  it('v28 step 82: 单词逐行 OCR 修复 (Please\\nalso\\nnote → Please also note)', () => {
    const text = 'Please\nalso\nnote\nthat,\nduring\nthe\nproduction process, errors may be discovered.'
    const { content } = cleanContent(text, { stripImageUrls: false, isMarkdown: false })
    // 单短词行（Please/also/note/that,/during/the）应合并成 "Please also note that, during the"
    expect(content).toContain('Please also note that, during the')
    // 不应出现单词粘连
    expect(content).not.toContain('Pleasealsonote')
    expect(content).not.toContain('duringtheproduction')
  })

  // v28 step 82: 单词内换行不应误加空格
  it('v28 step 82: 单词内换行不加空格 (disinfection 不会被拆)', () => {
    const text = 'The method of disin\n        fection is well-established.'
    const { content } = cleanContent(text, { stripImageUrls: false, isMarkdown: false })
    expect(content).toContain('disinfection')
    expect(content).not.toContain('disin fection')
  })

  // v28 step 82: 独立段落行不应被合并（避免段落合并）
  it('v28 step 82: 独立段落行不合并 (Chemicals\\nToluene 保持换行)', () => {
    const text = '2.1 Chemicals\nToluene was analytical grade.'
    const { content } = cleanContent(text, { stripImageUrls: false, isMarkdown: false })
    expect(content).toContain('Chemicals')
    expect(content).toContain('Toluene')
    // 不应合并为 ChemicalsToluene
    expect(content).not.toContain('ChemicalsToluene')
  })

  // v28 step 82: table row 修复
  it('v28 step 82: 表格行号 + 内容同行 (1\\nIndividual MNBs → 1 Individual MNBs)', () => {
    const text = 'Tab.1. Description of conditions.\n1\nIndividual MNBs treatment\nMNBs\n2\nUV irradiation\nUV1'
    const { content } = cleanContent(text, { stripImageUrls: false, isMarkdown: false })
    // 行号 + 内容应该合并成同行
    expect(content).toMatch(/1 Individual MNBs treatment MNBs/)
  })

  // v28 step 82: Published Journal Article 修复（核心目标：不粘连）
  it('v28 step 82: 跨行单词不粘连 (Published\\nJournal 至少不能 PublishedJournal)', () => {
    const text = 'Please note that Elsevier\'s sharing policy for the Published\nJournal Article applies.'
    const { content } = cleanContent(text, { stripImageUrls: false, isMarkdown: false })
    // 至少不应出现无空格粘连
    expect(content).not.toContain('PublishedJournal')
    // 完整合并需要更复杂的逻辑（边界处理由 removeFrontMatter 优先剥除此段）
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

  it('v28 fix: 保留 [PAGE:N] 标记（让 extractPageMarkers 提取，不再剥除）', () => {
    const text = 'T. Wang et al. 3 [PAGE:4]\nSection\n[PAGE:3]\n\nPAGE:5'
    const { content } = cleanContent(text)
    // v28 fix: 保留 [PAGE:N] 让后续 extractPageMarkers 提取（删了会让 pageMarkers=0 → sections 解析失败）
    expect(content).toContain('[PAGE:4]')
    expect(content).toContain('[PAGE:3]')
    // 仅剥除无方括号的 'PAGE:5'（避免误删 [PAGE:5]）
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

  // === v26.1 修复新增：多模态 chart 描述块（OCR 漏闭合 }） ===

  it('v26.1: 剥离 { category: mixed, text: ... } 多模态块（无闭合 }，OCR 漏识别）', () => {
    // 用户报告的真实场景：OCR 漏闭合 } + 长描述 + 后接学术句末 "species. Consistent ..."
    // 终止符: . [大写字母开头单词] [小写单词] → "species. Consistent with"
    // 期望: 剥除到 "species" 之前；". Consistent with...Fig. 5d..." 保留
    const text = 'orbital ![图（P8, { "category": "mixed", "text": "(a) C O H [分子模拟图] coupling and electron transfer between toluene and the oxidizing species. Consistent with these results, the free-energy profiles in Fig. 5d demonstrate that the energy barrier.'
    const { content } = cleanContent(text)
    expect(content).not.toContain('category')
    expect(content).not.toContain('mixed')
    expect(content).not.toContain('分子模拟')
    expect(content).toContain('orbital')
    // 学术句末 "Fig. 5d" 后应保留
    expect(content).toContain('Fig. 5d')
    expect(content).toContain('Consistent with')
  })

  it('v26.1: 剥离 { kind: chart, text: ... } 变体', () => {
    // 终止符: ". The final"（. 后大写字母开头单词 + 空格 + 小写）
    const text = '前文 { "kind": "chart", "text": "(图说明内容很长). The final text comes here.'
    const { content } = cleanContent(text)
    expect(content).not.toContain('kind')
    expect(content).not.toContain('图说明内容')
    expect(content).toContain('前文')
    expect(content).toContain('The final text')
  })

  it('v26.1: 剥离 { category: mixed } 闭合版本（带 }）', () => {
    // 闭合版本（INTERNAL_MARKER_RES 那条带 } 闭合的正则处理）
    const text = '段落 1 { "category": "mixed", "text": "图描述" } 段落 2'
    const { content } = cleanContent(text)
    expect(content).not.toContain('category')
    expect(content).toContain('段落 1')
    expect(content).toContain('段落 2')
  })
})


// ============================================================
// _buildFigureRegistry v27 段落级锚定测试
// ============================================================

// ============================================================
// v27.2 中文污染多规则过滤测试
// ============================================================

describe('v27.2 中文污染多规则过滤', () => {
  const testInput = (paragraphs) => ({
    id: 19,
    title: 'test',
    content: 'PLACEHOLDER',
    formatted_content: 'PLACEHOLDER',
    images: [],
    extractions: [],
  })

  it('强删中文图注关键词（图表说明）', () => {
    const paper = normalizePaperData({
      ...testInput(),
      content: 'See results.\n图表说明（P8，{ "category": "mixed", "text": "(a) C O H" }）the figure.\nConclusion.',
      formatted_content: 'See results.\n图表说明（P8，{ "category": "mixed", "text": "(a) C O H" }）the figure.\nConclusion.',
    })
    const allText = (paper.sections || []).flatMap(s => s.blocks || []).map(b => b.content).join('\n')
    expect(allText).not.toContain('图表说明')
  })

  it('强删 JSON-like 结构（多模态 OCR 输出混入）', () => {
    const paper = normalizePaperData({
      ...testInput(),
      content: 'Paragraph 1.\n{ "category": "mixed", "text": "(a) C O H 分子模拟图", "kind": "chart" }\nParagraph 2.',
      formatted_content: 'Paragraph 1.\n{ "category": "mixed", "text": "(a) C O H 分子模拟图", "kind": "chart" }\nParagraph 2.',
    })
    const allText = (paper.sections || []).flatMap(s => s.blocks || []).map(b => b.content).join('\n')
    expect(allText).not.toContain('category')
    expect(allText).not.toContain('分子模拟图')
  })

  it('强删中英混合的中文图表说明（含 "图（Px"）', () => {
    const paper = normalizePaperData({
      ...testInput(),
      content: 'Some English text.\n图（P8，{ "category": "mixed", "text": "(a) 分子模拟图" }()\nMore English text.',
      formatted_content: 'Some English text.\n图（P8，{ "category": "mixed", "text": "(a) 分子模拟图" }()\nMore English text.',
    })
    const allText = (paper.sections || []).flatMap(s => s.blocks || []).map(b => b.content).join('\n')
    expect(allText).not.toContain('分子模拟图')
    expect(allText).not.toContain('图（P8')
  })

  it('保留正常英文段落（包括化学式）', () => {
    const paper = normalizePaperData({
      ...testInput(),
      content: 'The reaction between O3 and H2O2 produces OH radicals.\n\nFig. S2 shows the heatmap.\n\nSee Section 2.1 for details.',
      formatted_content: 'The reaction between O3 and H2O2 produces OH radicals.\n\nFig. S2 shows the heatmap.\n\nSee Section 2.1 for details.',
    })
    const allText = (paper.sections || []).flatMap(s => s.blocks || []).map(b => b.content).join('\n')
    expect(allText).toContain('The reaction')
    expect(allText).toContain('Fig. S2')
    expect(allText).toContain('Section 2.1')
  })

  it('不误伤"中文图"等纯英文内嵌词', () => {
    const paper = normalizePaperData({
      ...testInput(),
      content: 'The chinese figure illustrates the mechanism.\n\nMore English text here.',
      formatted_content: 'The chinese figure illustrates the mechanism.\n\nMore English text here.',
    })
    const allText = (paper.sections || []).flatMap(s => s.blocks || []).map(b => b.content).join('\n')
    expect(allText).toContain('chinese figure')
  })

  it('段落级深度清洗：整段是 JSON 时整段删除', () => {
    const paper = normalizePaperData({
      ...testInput(),
      content: 'Normal paragraph 1.\n\n{"category": "mixed", "text": "(a) COH 分子模拟图", "kind": "chart"}\n\nNormal paragraph 2.',
      formatted_content: 'Normal paragraph 1.\n\n{"category": "mixed", "text": "(a) COH 分子模拟图", "kind": "chart"}\n\nNormal paragraph 2.',
    })
    const allText = (paper.sections || []).flatMap(s => s.blocks || []).map(b => b.content).join('\n')
    expect(allText).not.toContain('category')
    expect(allText).not.toContain('分子模拟图')
  })
})

describe('normalizePaperData - v27 inline figure 段落级锚定', () => {
  // 用户报告的真实场景模拟数据
  // 后端 OCR 不输出 "Fig. 1" 这种图号字符串，只输出图描述
  // 要求：按 page 顺序兜底分配 Fig. N，确保 Elsevier logo / 期刊封面不进正文
  const realWorldInput = {
    id: 19,
    title: 'O3-MNBs/H2O2 system for toluene oxidation',
    content: 'See Fig. 1 for the heatmap.',
    formatted_content: 'See Fig. 1 for the heatmap. Fig. 2 shows results.',
    images: [
      { id: 518, page_number: 1, image_url: 'a.jpg', ocr_text: 'NON SOLUS\nELSEVIER' },
      { id: 519, page_number: 1, image_url: 'b.jpg', ocr_text: 'ELSEVIER\nJOURNAL OF HAZARDOUS MATERIALS' },
      { id: 520, page_number: 1, image_url: 'c.jpg', ocr_text: 'Liquid Phase\nO3-MNBs\nH2O2\nOH radicals' },
      { id: 521, page_number: 3, image_url: 'd.jpg', ocr_text: 'toluene conversion vs time' },
      { id: 522, page_number: 4, image_url: 'e.jpg', ocr_text: 'oxidant supply chart' },
      { id: 527, page_number: 6, image_url: 'f.jpg', ocr_text: 'economic analysis' },
    ],
    extractions: [
      { id: 1, source_image_id: 518, kind: 'image_block', data: { text: 'NON SOLUS\nELSEVIER', caption: null } },
      { id: 2, source_image_id: 519, kind: 'image_block', data: { text: 'ELSEVIER\nJOURNAL OF...', caption: null } },
      { id: 3, source_image_id: 520, kind: 'chart', data: { description: '热力图展示甲苯转化率' } },
      { id: 4, source_image_id: 527, kind: 'chart', data: { description: '成本对比柱状图' } },
    ],
  }

  it('Elsevier logo / 期刊封面被识别为 publisher/cover, 不进正文', () => {
    const paper = normalizePaperData(realWorldInput, {
      images: realWorldInput.images,
      extractions: realWorldInput.extractions,
    })
    const figs = paper.figureRegistry || []
    const id518 = figs.find(f => f.id === 518)
    const id519 = figs.find(f => f.id === 519)
    expect(id518?.figureType).toBe('publisher')
    expect(id519?.figureType).toBe('publisher')
    expect(id518?.isCoreFigure).toBe(false)
    expect(id519?.isCoreFigure).toBe(false)
    expect(id518?.figureNo).toBeNull()
    expect(id519?.figureNo).toBeNull()
  })

  it('核心图（OCR 无图号）按 page + 顺序兜底分配 Fig. 1, Fig. 2, ...', () => {
    const paper = normalizePaperData(realWorldInput, {
      images: realWorldInput.images,
      extractions: realWorldInput.extractions,
    })
    const figs = paper.figureRegistry || []
    const id520 = figs.find(f => f.id === 520)
    const id521 = figs.find(f => f.id === 521)
    const id522 = figs.find(f => f.id === 522)
    const id527 = figs.find(f => f.id === 527)

    // 核心图必须有 figureNo（兜底分配）
    expect(id520?.figureNo).toBe('Fig. 1')
    expect(id521?.figureNo).toBe('Fig. 2')
    expect(id522?.figureNo).toBe('Fig. 3')
    expect(id527?.figureNo).toBe('Fig. 4')
    // 都是 isCoreFigure=true
    expect(id520?.isCoreFigure).toBe(true)
    expect(id521?.isCoreFigure).toBe(true)
  })

  it('正文 paragraph 含 Fig. N 引用 → 对应图被锚定到 paragraph 后', () => {
    const paper = normalizePaperData(realWorldInput, {
      images: realWorldInput.images,
      extractions: realWorldInput.extractions,
    })
    // 至少 1 个 inlineFigureAnchor（Fig. 1 锚到引用它的 paragraph）
    const anchors = paper.inlineFigureAnchors || {}
    const anchorIds = Object.keys(anchors)
    expect(anchorIds.length).toBeGreaterThan(0)

    // 找到 Fig. 1 锚定的 paragraph
    const fig1Anchor = Object.values(anchors).find(arr => arr.some(f => f.figureNo === 'Fig. 1'))
    expect(fig1Anchor).toBeDefined()
    // 该 paragraph 必须有 "Fig. 1" 文本引用
    const fig1Pid = Object.keys(anchors).find(pid =>
      anchors[pid].some(f => f.figureNo === 'Fig. 1')
    )
    expect(fig1Pid).toMatch(/__p\d+$/)
  })

  it('Elsevier logo / 期刊封面不在 inlineFigureAnchors 中', () => {
    const paper = normalizePaperData(realWorldInput, {
      images: realWorldInput.images,
      extractions: realWorldInput.extractions,
    })
    const anchors = paper.inlineFigureAnchors || {}
    const allAnchoredFigs = Object.values(anchors).flat()
    const anchoredIds = new Set(allAnchoredFigs.map(f => f.id))
    expect(anchoredIds.has(518)).toBe(false)  // Elsevier logo
    expect(anchoredIds.has(519)).toBe(false)  // 期刊封面
  })
})

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

  // v28 step 87: 章节标题识别不再误吃表格行 + 页码+图注合并行
  // 用户截图（杨慈 UV/MNBs 论文）：
  //   "7\nFig. 1. ..." 被当章节
  //   "1\nIndividual MNBs treatment\nMNBs" 表格行被当章节
  //   "2.2\nPreparation of strain..." 真实章节标题保留
  it('v28 step 87: 表格行 + 页码+图注 行不被识别为章节标题', () => {
    const content = `7
Fig. 1. Water treatment sterilization system based on MNBs/UV technology.
Tab.1. Description of different treatment conditions. Serial number Treatment condition Symbol

1
Individual MNBs treatment MNBs
2
UV irradiation for 0.5 min in combination with MNBs treatment MNBs/UV0.5
3
UV irradiation for 1 min in combination with MNBs treatment MNBs/UV1
4
Individual UV irradiation for 0.5 min UV0.5
5
Individual UV irradiation for 1 min UV1
2.2
Preparation of strain and bacterial suspension
In this study, the selected bacterial strain was B. cereus ATCC 11778.`

    const cleaned = cleanContent(content, { isMarkdown: false })
    const sections = parsePaperSections(cleaned.content, { isMarkdown: false })

    // 1. 表格行 1-5 + "7 Fig. 1." 不应是独立章节标题
    const tableRowTitles = sections.filter((s) =>
      /^(7\s+Fig|1\s+Individual|2\s+UV|3\s+UV|4\s+Individual|5\s+Individual)/.test(s.title || '')
    )
    expect(tableRowTitles.length).toBe(0)

    // 2. 真实章节标题 2.2 保留
    const realChapter = sections.find((s) => /^2\.2\s+Preparation/.test(s.title || ''))
    expect(realChapter).toBeTruthy()
    expect(realChapter.type).toBe('normal')

    // 3. 内容块含 "In this study..." 段落
    const allBlockText = sections.flatMap((s) => s.blocks || []).map((b) => b.content || '').join('\n')
    expect(allBlockText).toContain('In this study')
    expect(allBlockText).toContain('Tab.1')
    expect(allBlockText).toContain('Individual MNBs treatment MNBs')
  })

  // v28 step 87: 单数字章节编号（无小数）必须含 SECTION_KEYWORDS 才识别
  // 否则 OCR 错误数字行（"1\n3.5 L of..." 等）会被误识别
  it('v28 step 87: level=1 编号必须匹配 SECTION_KEYWORDS', () => {
    // 不在关键词列表的 level=1 → 不识别为章节（落到 preamble）
    const s1 = parsePaperSections('1 Some random text', { isMarkdown: false })
    expect(s1.length).toBe(1) // 只有 preamble
    expect(s1[0].type).toBe('preamble')

    // SECTION_KEYWORDS 内的 → 识别为章节
    const s2 = parsePaperSections('1 Introduction\nThis is intro.', { isMarkdown: false })
    expect(s2.length).toBeGreaterThanOrEqual(1)
    expect(s2.some((s) => /^1\s+Introduction/.test(s.title || ''))).toBe(true)
    expect(s2.some((s) => s.type === 'introduction')).toBe(true)
  })

  // v28 step 89: OCR 把章节标题与正文黏在一行 + 混入页码范围标记（P28-29）
  // 用户截图（杨慈 UV/MNBs 论文）："4.2\nThe mechanism of continuous sterilization
  //   by UV-enhanced MNB water Our findings reveal that...\nP28-29\nand improving..."
  it('v28 step 89: 标题与正文黏在一起 + P28-29 水印应被切分', () => {
    const content = `4.2
The mechanism of continuous sterilization by UV-enhanced MNB water Our findings reveal that MNBs/UV treatment can effectively inactivate B. cereus, with a maximum inactivation efficiency rate of 97.91%, overcoming its intrinsic tolerance mechanism
P28-29
and improving water biosafety. The collapse of MNBs generates microjets with velocities reaching several hundred meters per second, accompanied by localized high te`

    const cleaned = cleanContent(content, { isMarkdown: false })

    // 1. P28-29 应被剥除
    expect(cleaned.content).not.toMatch(/P28-29/)
    expect(cleaned.content).not.toMatch(/^P\d+-\d+$/m)

    // 2. 标题应被识别为 4.2 normal section
    const sections = parsePaperSections(cleaned.content, { isMarkdown: false })
    const sec = sections.find((s) => s.type === 'normal' && /^4\.2/.test(s.title || ''))
    expect(sec).toBeTruthy()
    // title 只包含章节标题（不包含 "Our findings..."）
    expect(sec.title).not.toMatch(/Our findings/)
    expect(sec.title).toMatch(/The mechanism of continuous sterilization by UV-enhanced MNB water/)

    // 3. 正文块包含 "Our findings..." 但不包含 "P28-29"
    const allBlockText = sections.flatMap((s) => s.blocks || []).map((b) => b.content || '').join('\n')
    expect(allBlockText).toContain('Our findings reveal that')
    expect(allBlockText).toContain('and improving water biosafety')
    expect(allBlockText).not.toMatch(/P28-29/)
  })

  // v28 step 102: OCR 长标题含人名缩写（B./Dr./Mr.）不应被错误切成「标题/正文」
  //   用户截图（ID 17 UV/MNBs 论文）：「2.1 Test system for the inactivation of B. Cereus
  //   in water using MNBs combined with UV」被错误切成
  //   title="2.1 Test system for the inactivation of B" + body="Cereus in water using MNBs combined with UV"
  //   导致正文变成 "Cereus in water using MNBs combined with UV\nThis study..."
  // 修复：要求 candidateTitle 必须以已知章节关键词结尾 + 切分点前不能是 1-3 字母英文缩写
  it('v28 step 102: B./Dr./Mr. 缩写不应触发 split（ID 17 真实场景）', () => {
    const content = `2. Materials and methods
2.1 Test system for the inactivation of B. Cereus in water using MNBs combined with UV
This study systematically evaluated the inactivation efficacy of MNBs against B. cereus
under UV irradiation, employing two experimental approaches: individual treatment and
combined treatment. The experimental setup was composed of four primary components: a MNB
generator.`

    const cleaned = cleanContent(content, { isMarkdown: false })
    const sections = parsePaperSections(cleaned.content, { isMarkdown: false })
    const sec = sections.find((s) => s.type === 'normal' && /^2\.1/.test(s.title || ''))
    expect(sec).toBeTruthy()
    // 标题应包含完整 "B. Cereus in water using MNBs combined with UV"
    expect(sec.title).toContain('B. Cereus in water using MNBs combined with UV')
    // 标题不应被错误截断在 "B" 处
    expect(sec.title).not.toMatch(/\binactivation of B$/)
    // 正文块不应以 "Cereus in water using MNBs" 开头（因为整行是标题的一部分）
    const firstBlockContent = sec.blocks[0]?.content || ''
    expect(firstBlockContent.startsWith('Cereus in water')).toBe(false)
    // 正文应从 "This study" 开始（OCR 原 lines 数组下一行）
    expect(firstBlockContent).toContain('This study')
  })

  it('v28 step 102: Dr./Mr. 缩写不应触发 split', () => {
    const content = `3.1 The role of Dr. Smith in the project
This section discusses his contributions.`

    const cleaned = cleanContent(content, { isMarkdown: false })
    const sections = parsePaperSections(cleaned.content, { isMarkdown: false })
    const sec = sections.find((s) => /^3\.1/.test(s.title || ''))
    expect(sec).toBeTruthy()
    expect(sec.title).toContain('The role of Dr. Smith in the project')
    expect(sec.title).not.toMatch(/\brole of Dr$/)
    const firstBlockContent = sec.blocks[0]?.content || ''
    expect(firstBlockContent.startsWith('Smith in the project')).toBe(false)
  })

  it('v28 step 102: 关键词结尾 + 短缩写仍可正确切分（保留 step 89 设计）', () => {
    // step 89 的设计场景：「Materials and methods. The reactor consisted of a 3 L chamber」
    //   末尾是关键词 "methods" → 应该切
    const content = `2.2 Materials and methods. The reactor consisted of a 3 L cylindrical chamber
and an UV lamp was used.`

    const cleaned = cleanContent(content, { isMarkdown: false })
    const sections = parsePaperSections(cleaned.content, { isMarkdown: false })
    const sec = sections.find((s) => /^2\.2/.test(s.title || ''))
    expect(sec).toBeTruthy()
    expect(sec.title).toContain('Materials and methods')
    expect(sec.title).not.toContain('The reactor consisted')
    const firstBlockContent = sec.blocks[0]?.content || ''
    expect(firstBlockContent).toContain('The reactor consisted')
  })

  // v28 step 103: _parseMarkdownSections 必须识别 `\n\n` 为段落分隔符
  //   LLM reformat 输出的 formatted_content 用 `\n\n` 分段
  //   （如 "Table 1.\n\n(1) To investigate..."），旧逻辑只在 line.trim() 真值时 push paragraphBuf，
  //   遇到空行不 flush，导致后续内容累积到同一 paragraph，最后 join('\n') 丢失段落边界
  // 用户场景（ID 17 UV/MNBs 论文）：section 2.1 应拆成多段（列表项 (1)/(2) 独立成段）
  it('v28 step 103: markdown 段落 \\n\\n 分隔符应触发 flush（ID 17 reformat 场景）', () => {
    const content = `## 2.1 Test system

This study systematically evaluated the inactivation efficacy of MNBs against B. cereus under UV irradiation, employing two experimental approaches: individual treatment and combined treatment. The experimental setup was composed of four primary components: a MNB generator.

(1) To investigate the individual disinfection effects of MNBs and UV irradiation on B. cereus: Bacterial suspensions with an initial concentration of 10⁷-10⁸ CFU/mL were subjected to either 3W UV irradiation or MNBs aeration separately.

(2) To assess the synergistic disinfection effect of MNBs and UV irradiation on B. cereus: Bacterial suspensions with the same initial concentration were exposed to simultaneous MNBs aeration and UV irradiation.

| Serial | Treatment | Symbol |
| :--- | :--- | :--- |
| 1 | MNBs alone | MNBs |
| 2 | MNBs + UV | MNBs/UV |

The disinfection effects were compared accordingly.`

    const sections = parsePaperSections(content, { isMarkdown: true })
    const sec = sections.find((s) => /^2\.1/.test(s.title || ''))
    expect(sec).toBeTruthy()
    // section 2.1 应有 ≥ 4 blocks（intro paragraph + (1) + (2) + table + closing paragraph）
    expect(sec.blocks.length).toBeGreaterThanOrEqual(4)
    // 列表项 (1) 应独立成段（不是和 intro 合并）
    const block1 = sec.blocks.find((b) => b.content?.startsWith('(1)'))
    expect(block1).toBeTruthy()
    // 列表项 (2) 应独立成段
    const block2 = sec.blocks.find((b) => b.content?.startsWith('(2)'))
    expect(block2).toBeTruthy()
    // intro 段落不应包含 (1) 内容（如果合并会出问题）
    const introBlock = sec.blocks[0]
    expect(introBlock.content).not.toContain('(1) To investigate')
    expect(introBlock.content).not.toContain('(2) To assess')
  })

  // v28 step 90: 中文 blockquote 图注（"该图由..."）混入英文正文 + orphan PDF 页码
  // 用户截图（杨慈 UV/MNBs 论文）：英文段后跟 > 该图由六个子图... 长图注，然后
  //   "15 disinfection." — OCR 把 PDF 页码 15 错误插入段落开头
  it('v28 step 90: 中文图注剥除 + orphan PDF 页码 15 剥除（保留空格）', () => {
    const content = `significant reduction of 29.05% over time, suggesting consumption of ionic species during
> 该图由六个子图（a-f）组成，展示了不同处理方式（MNBs, MNBs/UV1, MNBs/UV0.5, UV1, UV0.5）下水质参数随时间（0-9分钟）的变化趋势。(a) MNBs/UV1的灭菌效率最高，接近100%；(b) TOC在初期下降后趋于稳定；(c) ORP随时间下降并稳定；(d) pH值在初期下降后保持在7-8之间；(e) CDC值在MNBs处理下较低且稳定；(f) DO值在初期略有上升后缓慢下降。
15 disinfection. The average CDC value in the MNBs/UV1 group was 157.40 μS/cm (SD = 22.67), which was 0.29% higher than that in the MNBs/UV0.5 group.`

    const cleaned = cleanContent(content, { isMarkdown: false })

    // 1. 中文 blockquote 图注应被剥除
    expect(cleaned.content).not.toMatch(/该图由/)
    expect(cleaned.content).not.toMatch(/六个子图/)
    expect(cleaned.content).not.toMatch(/灭菌效率最高/)

    // 2. orphan 页码 15 应被剥除，但前后空格保留（避免 "duringdisinfection"）
    expect(cleaned.content).not.toMatch(/\b15 disinfection/)
    expect(cleaned.content).toMatch(/during disinfection/)
    expect(cleaned.content).not.toMatch(/duringdisinfection/)

    // 3. 正文连贯：前半段 + 后半段用空格连接，无 phantom text
    const sections = parsePaperSections(cleaned.content, { isMarkdown: false })
    const allText = sections.flatMap((s) => s.blocks || []).map((b) => b.content || '').join('\n')
    expect(allText).toContain('significant reduction of 29.05% over time')
    expect(allText).toContain('The average CDC value in the MNBs/UV1 group')
    expect(allText).not.toMatch(/该图由/)
    expect(allText).not.toMatch(/\b15 disinfection/)
  })

  // v28 step 91: paper 17 的 formatted_content 含 [PAGE:N] 标记 + 多模态注入的 ## 标题
  //   → 必须强制走 rawContent 路径（让 cleanContent 完整处理 OCR 残留：
  //     Journal Pre-proof / P33-39 / 该图由 / 标题/正文切分）
  //   之前 hasMdHeading 检测太宽松（"## 多模态提取" 也算 markdown），走了 rawFormatted
  //   → rawFormatted 没经过完整 cleanContent → references 解析失败
  it('v28 step 91: formatted_content 含 [PAGE:N] 时强制走 rawContent 路径（references 解析正常）', () => {
    const rawContent = `4.2 The mechanism of continuous sterilization by UV-enhanced MNB water Our findings reveal that MNBs/UV treatment can effectively inactivate B. cereus.

References

Alapi T, Dombi A. Comparative study[J]. Journal, 2007,188(2-3): 409-418. Yang S, Wang Y. Cereulide[J]. Foods, 2023,12(4): 833.`
    // 模拟 paper 17：formatted_content 是 OCR 文本 + 多模态注入的 ## 标题 + [PAGE:N] 标记
    const rawFormatted = `## 多模态提取

### 提取的公式

$$y=2.33x+93.53$$

## Abstract

This paper presents novel micro-nano bubble systems.
${rawContent.replace('4.2 The mechanism', '## 4.2 The mechanism')}

[PAGE:33]Journal Pre-proof
Journal Pre-proof

32

`

    const raw = {
      id: 17,
      title: 'Test',
      content: rawContent,
      formatted_content: rawFormatted,
      summary: null, tags: null, analysis_status: 'done',
      created_at: '2026-06-19T10:00:00', updated_at: '2026-06-19T10:00:00',
    }

    const paper = normalizePaperData(raw)

    // 1. 应走 rawContent 路径 → 含 [PAGE:N] 的 rawFormatted 的 OCR 残留被剥除
    const allText = paper.sections.flatMap((s) => s.blocks || []).map((b) => b.content || '').join('\n')
    expect(allText).not.toMatch(/Journal Pre-proof/)
    expect(allText).not.toMatch(/该图由/)

    // 2. References 章节被识别，references array 含至少 2 条
    expect(paper.references.length).toBeGreaterThanOrEqual(2)
    expect(paper.references[0]).toContain('Alapi T')
    expect(paper.references[1]).toContain('Yang S')

    // 3. References section 标题被识别
    const refSec = paper.sections.find((s) => s.type === 'references')
    expect(refSec).toBeTruthy()
  })

  // v28 step 92: SECTION_KEYWORDS results regex 漏匹配 "Results and analysis"
  //   旧 regex 只识别 "Results and discussion" 或 "结果与讨论"
  //   但 Elsevier 等期刊常用 "3. Results and analysis" 章节标题
  //   → 被错认为普通段落，并入上一个 section 的 block
  it('v28 step 92: "3. Results and analysis" 应被识别为 results section', () => {
    const content = `2.1 Materials and methods
All chemicals were of analytical grade.

Statistical analysis
Each experiment was repeated three times.

3. Results and analysis
3.1 Disinfection efficiency
The disinfection efficiency was 97.91% under optimal conditions.`

    const sections = parsePaperSections(content, { isMarkdown: false })

    // 1. 应有 3 个 sections：methods / results / normal
    const methodsSec = sections.find((s) => s.type === 'methods')
    const resultsSec = sections.find((s) => s.type === 'results')
    expect(methodsSec).toBeTruthy()
    expect(resultsSec).toBeTruthy()
    expect(resultsSec.title).toMatch(/3\. Results and analysis/)

    // 2. 3.1 Disinfection efficiency 作为 results 子章节（type=normal）
    const disinSection = sections.find((s) => /^3\.1/.test(s.title || ''))
    expect(disinSection).toBeTruthy()

    // 3. "Statistical analysis" 段内小标题并入 methods section block
    const methodsBlockText = methodsSec.blocks.map((b) => b.content || '').join('\n')
    expect(methodsBlockText).toContain('Statistical analysis')
    expect(methodsBlockText).toContain('Each experiment was repeated')
  })

  // v28 step 92: "3. Results and discussion" 也应识别（之前已支持 + 验证不破坏）
  it('v28 step 92: "3. Results and discussion" 仍正确识别为 results', () => {
    const content = `2 Methods
All experiments were conducted at 25°C.
3. Results and discussion
3.1 Effect of pH
The pH effect was significant.`

    const sections = parsePaperSections(content, { isMarkdown: false })
    const resultsSec = sections.find((s) => s.type === 'results')
    expect(resultsSec).toBeTruthy()
    expect(resultsSec.title).toMatch(/3\. Results and discussion/)
  })

  // v28 step 95: OCR 把英文单词从中间断行（无缩进）— "bacterial\ndisinfection" 应合并
  //   之前 step 5.1b 只匹配有缩进的续行（[ \t]+），无缩进的单词中断无法合并
  //   触发条件：上一行末尾小写 + 下一行开头小写（区别于独立段落 "句末标点 + 大写开头"）
  it('v28 step 95: OCR 单词内部断行（无缩进）应合并', () => {
    const content = `3.5 The influence of ROS species in MNB water under UV irradiation on the bacterial
disinfection process This study systematically assessed the contributions of three ROS types, including ·OH, hydrogen peroxide (H₂O₂), and superoxide radicals (·O₂⁻), to the synergistic sterilization`

    const cleaned = cleanContent(content, { isMarkdown: false })

    // 1. "bacterial disinfection" 应合并（单空格，不是换行）
    expect(cleaned.content).toContain('bacterial disinfection process')
    expect(cleaned.content).not.toContain('bacterial\ndisinfection')

    // 2. 标题完整（不被错误截断）
    const sections = parsePaperSections(cleaned.content, { isMarkdown: false })
    const sec = sections.find((s) => /^3\.5/.test(s.title || ''))
    expect(sec).toBeTruthy()
    expect(sec.title).toContain('bacterial disinfection process')

    // 3. 正文块以 "This study" 开头（小写 d + 上一段大写开头保持独立段）
    const allText = sections.flatMap((s) => s.blocks || []).map((b) => b.content || '').join('\n')
    expect(allText).toContain('This study systematically assessed')
    // 段落边界保留（"process" 后 title 与 block 边界）
    expect(sec.title).toMatch(/bacterial disinfection process$/)
  })

  it('v28 step 95: 句末标点 + 大写开头仍是独立段落（不误合并）', () => {
    const content = `2.1 Materials and methods
The experiment was conducted.
The analysis showed significant results.
Each test was repeated three times.`

    const cleaned = cleanContent(content, { isMarkdown: false })
    // 句末标点 + 大写开头 = 独立段落，必须保留换行
    expect(cleaned.content).toContain('conducted.\nThe analysis')
    expect(cleaned.content).toContain('results.\nEach test')
  })

  // v28 step 96: 右侧导航 buildAnchorTree 应让子章节继承父级 type
  //   "2. Materials and methods"（methods）下的 "2.3. Experimental" / "2.4. Statistical analysis"
  //   原识别为 type=normal（typeLabelMap 无），显示 "2.3. Experimental" 没 "材料与方法 ·" 前缀
  //   修复：子章节（level>=2 + type=normal）继承最近的 methods/results/discussion 父级 type
  it('v28 step 96: 子章节继承父级 type（methods/results/discussion 等）', () => {
    const sections = [
      { id: 's1', title: '1. Introduction', level: 1, type: 'introduction' },
      { id: 's2', title: '2. Materials and methods', level: 1, type: 'methods' },
      { id: 's3', title: '2.1. Test system', level: 2, type: 'normal' },
      { id: 's4', title: '2.2. Preparation', level: 2, type: 'normal' },
      { id: 's5', title: '2.3. Experimental', level: 2, type: 'normal' },
      { id: 's6', title: '2.4. Statistical analysis', level: 2, type: 'normal' },
      { id: 's7', title: '3. Results and discussion', level: 1, type: 'results' },
      { id: 's8', title: '3.1. Disinfection efficiency', level: 2, type: 'normal' },
    ]

    const tree = buildAnchorTree(sections)

    // 1. 父级 type 保持不变
    expect(tree.sections[0].type).toBe('introduction')
    expect(tree.sections[1].type).toBe('methods')
    expect(tree.sections[6].type).toBe('results')

    // 2. 子章节（level=2, type=normal）继承父级 type
    expect(tree.sections[2].type).toBe('methods')  // 2.1. Test system
    expect(tree.sections[3].type).toBe('methods')  // 2.2. Preparation
    expect(tree.sections[4].type).toBe('methods')  // 2.3. Experimental
    expect(tree.sections[5].type).toBe('methods')  // 2.4. Statistical analysis
    expect(tree.sections[7].type).toBe('results')  // 3.1. Disinfection efficiency

    // 3. 标题保持不变（仅 type 继承）
    expect(tree.sections[4].title).toBe('2.3. Experimental')
    expect(tree.sections[4].level).toBe(2)
  })

  it('v28 step 96: 不破坏 level=1 normal sections（不向上找父）', () => {
    const sections = [
      { id: 's1', title: '2. Materials and methods', level: 1, type: 'methods' },
      { id: 's2', title: 'Discussion', level: 1, type: 'normal' },  // level=1 normal 不继承
    ]
    const tree = buildAnchorTree(sections)
    expect(tree.sections[0].type).toBe('methods')
    expect(tree.sections[1].type).toBe('normal')  // level=1 不向上继承
  })

  // v28 step 98: OCR 工具把 'Journal Pre-proof N' 水印错误插入到英文段落中间
  //   例: '... a MNB\nJournal Pre-proof generator (RuiDe...' → '... a MNB generator (RuiDe...'
  //   触发条件: 前后都是小写字母（说明 Journal Pre-proof 是 OCR artifact，不是 watermark 行）
  //   之前只剥行首 Journal Pre-proof（^...$），中间的不剥
  it('v28 step 98: OCR 错误插入的 Journal Pre-proof 水印（段落中间）应被剥除', () => {
    const content = `The experimental setup was composed of four primary components: a MNB
Journal Pre-proof generator (RuiDe ZhiChuang Innovation Technology (Tianjin) Co., Ltd.), a 3 L cylindrical reactor, an UV lamp (Philips, 3 W, 100 mm length), and the necessary connecting tubing.`

    const cleaned = cleanContent(content, { isMarkdown: false })

    // 1. Journal Pre-proof 应被剥除
    expect(cleaned.content).not.toMatch(/Journal Pre-proof/)

    // 2. MNB generator 应合并（中间无换行）
    expect(cleaned.content).toContain('MNB generator')
    expect(cleaned.content).not.toMatch(/MNB\s*\n\s*generator/)
  })

  it('v28 step 98: 行首的 Journal Pre-proof（独立行）仍正确剥除（不破坏旧行为）', () => {
    const content = `Some real content here.
Journal Pre-proof

More content after the watermark.`

    const cleaned = cleanContent(content, { isMarkdown: false })
    expect(cleaned.content).not.toMatch(/Journal Pre-proof/)
    expect(cleaned.content).toContain('Some real content here')
    expect(cleaned.content).toContain('More content after')
  })

  // v28 step 99: step 98 的边界 regex 太严格（只匹配 [a-z] 两边），实际 OCR 中
  //   Journal Pre-proof 后跟数字（页码）也很常见，如 "B. cereusJournal Pre-proof\n3 (Grutsch et al.)"
  //   修复：放宽为 (\S)\s*...\s*(\S)，匹配任何非空白字符
  it('v28 step 99: Journal Pre-proof 后跟数字（页码）也能合并', () => {
    const cases = [
      {
        in: 'associated with B. cereusJournal Pre-proof\n3 (Grutsch et al., 2018)',
        out: 'associated with B. cereus 3 (Grutsch et al., 2018)',  // step 99 剥 JP；孤立 '3' (page phantom) 保留
      },
      {
        in: 'compared accordingly.Journal Pre-proof\nFig. 1.',
        out: 'compared accordingly. Fig. 1.',  // v28 step 101 进一步剥除孤立数字页码（双换行情况）
      },
      {
        in: 'with a concentration of 1 mg/L O₃ MNBsJournal Pre-proof\ncapable of completely inactivating',
        out: 'with a concentration of 1 mg/L O₃ MNBs capable of completely inactivating',
      },
      {
        in: 'in bothJournal Pre-proof\nmechanistic complementarity',
        out: 'in both mechanistic complementarity',
      },
      {
        in: 'a MNBJournal Pre-proof\ngenerator (RuiDe ZhiChuang',
        out: 'a MNB generator (RuiDe ZhiChuang',
      },
    ]
    for (const { in: input, out } of cases) {
      const cleaned = cleanContent(input, { isMarkdown: false })
      expect(cleaned.content).not.toMatch(/Journal Pre-proof/)
      expect(cleaned.content).toContain(out.slice(0, 40))
    }
  })

  // v28 step 100: OCR 把章节号单独成行（"1\n\n正文"），应合并到正文开头
  //   之前 step 81 只匹配章节号紧跟正文的格式（"1. Introduction"），OCR 把章节号
  //   单独成行 + 空行 + 正文（"[PAGE:1]\n\n1\n\nEnsuring..."）会漏掉
  //   修复：新增 regex 匹配 "数字\n\n大写字母" 模式（章节号 + 空行 + 正文）
  it('v28 step 100: 单独成行的章节号（"1\n\n正文"）应合并', () => {
    const cases = [
      {
        in: '[PAGE:1]Journal Pre-proof\n\n1\n\nEnsuring the safety of drinking water.',
        out: '[PAGE:1] 1 Ensuring the safety of drinking water.',  // JP 剥（已合并到 [PAGE:1] 同行）+ 1 合并到正文
      },
      {
        in: '2.2\n\nPreparation of strain and bacterial suspension',
        out: '2.2. Preparation of strain and bacterial suspension',  // 章节号 "2.2" + 双换行 + 正文（step 100 处理）
      },
    ]
    for (const { in: input, out } of cases) {
      const cleaned = cleanContent(input, { isMarkdown: false })
      expect(cleaned.content).not.toMatch(/Journal Pre-proof/)
      expect(cleaned.content).toContain(out.slice(0, 50))
    }
  })

  // v28 step 101: OCR 把 [PAGE:N] 写成裸数字 N（phantom 页码）插入段落中间
  //   "B. cereus\n\n3 (Grutsch et al., 2018)" → "B. cereus 3 (Grutsch et al., 2018)"
  //   "MNBs\n\ncapable of completely..." → "MNBs capable of completely..."
  //   触发条件：上一行末尾小写/右括号（非 . ! ? 句末标点）+ 双空行 + 下一行小写/数字/左括号
  it('v28 step 101: OCR phantom 页码 + 段落间双空行应合并（小写/数字后）', () => {
    const cases = [
      {
        in: 'associated with B. cereus\n\n3\n\n(Grutsch et al., 2018)',
        out: 'associated with B. cereus 3 (Grutsch et al., 2018)',
      },
      {
        in: 'concentration of 1 mg/L O₃ MNBs\n\ncapable of completely inactivating 10⁶ CFU/mL',
        out: 'concentration of 1 mg/L O₃ MNBs capable of completely inactivating 10⁶ CFU/mL',
      },
      {
        in: 'advantages in both\n\nmechanistic complementarity and performance enhancement',
        out: 'advantages in both mechanistic complementarity and performance enhancement',
      },
    ]
    for (const { in: input, out } of cases) {
      const cleaned = cleanContent(input, { isMarkdown: false })
      expect(cleaned.content).not.toMatch(/\n\n3\n\n/)
      expect(cleaned.content).toContain(out.slice(0, 40))
    }
  })

  // v28 step 101 不破坏真段落边界（句末标点 + 大写开头）
  it('v28 step 101: 句末标点 + 大写开头的真段落边界应保留 \\n\\n', () => {
    // OCR 真实风格：段落间用 \n\n 隔开（不是单 \n）
    // "here.\n\nThe" 的 lookbehind 是 . 不是小写 → step 101 不触发 → 保留 \n\n
    const content = `This is the first paragraph that ends here.

The second paragraph starts with a capital letter and is a real paragraph boundary.`
    const cleaned = cleanContent(content, { isMarkdown: false })
    // 真段落间应保留 \n\n（step 101 不应吃掉）
    expect(cleaned.content).toContain('here.\n\nThe second')
    // 输入有 \n\n，输出长度应 >= 输入长度（不能合并丢空行）
    expect(cleaned.content.length).toBeGreaterThanOrEqual(content.length)
  })

  // v28 step 105: vision model 扫描整篇论文输出的 page_layout → 重建 PaperDetail
  //   vision 真正"看"了 PDF 每页（不只是单图），输出每页的 blocks 数组（按视觉顺序）
  //   paperAdapter 优先消费 vision layout，不再依赖 regex 推断
  it('v28 step 105: vision layout 重建 paper detail（按视觉顺序，图片精确位置）', () => {
    const visionLayout = {
      has_layout: true,
      total_pages: 2,
      total_blocks: 8,
      vision_model_used: 'mimo-v2.5',
      page_layout: [
        {
          page_number: 1,
          blocks: [
            { type: 'heading', level: 1, order: 1, text: 'Test Paper Title' },
            { type: 'paragraph', order: 2, text: 'Authors: John Doe, Jane Smith' },
            { type: 'paragraph', order: 3, text: 'Abstract: This paper studies something.' },
          ],
        },
        {
          page_number: 2,
          blocks: [
            { type: 'heading', level: 1, order: 1, text: '1. Introduction' },
            { type: 'paragraph', order: 2, text: 'This is the introduction paragraph.' },
            { type: 'image', order: 3, image_index: 0, caption: 'Fig. 1. The system setup.', figure_no: 'Fig. 1', position: 'below_paragraph' },
            { type: 'paragraph', order: 4, text: 'This paragraph references the figure above.' },
            { type: 'heading', level: 1, order: 5, text: '2. Methods' },
            { type: 'paragraph', order: 6, text: 'Methods paragraph here.' },
            { type: 'image', order: 7, image_index: 1, caption: 'Fig. 2. The results chart.', figure_no: 'Fig. 2', position: 'below_paragraph' },
            { type: 'table', order: 8, caption: 'Table 1. Conditions.', headers: ['A', 'B'], rows: [['1', '2']] },
          ],
        },
      ],
    }
    const kb = {
      id: 99,
      title: 'Test Paper Title',
      content: 'placeholder',
      summary: null,
      tags: [],
    }
    const images = [
      { id: 901, page_number: 2, pageNumber: 2, image_url: '/img/1.png', figure_no: 'Fig. 1', figure_type: 'chart', is_core_figure: true, is_publisher_image: false, visual_summary: 'chart 1', section_hint: 'methods', anchor_text: null },
      { id: 902, page_number: 2, pageNumber: 2, image_url: '/img/2.png', figure_no: 'Fig. 2', figure_type: 'chart', is_core_figure: true, is_publisher_image: false, visual_summary: 'chart 2', section_hint: 'results', anchor_text: null },
    ]
    const r = normalizePaperData(kb, {
      images,
      extractions: [],
      related: [],
      visionLayout,
    })
    // 1. 应该用 vision layout 路径
    expect(r._source).toBe('vision_layout')
    // 2. sections 应该识别 Introduction / Methods
    expect(r.sections.length).toBeGreaterThanOrEqual(3)
    const secTitles = r.sections.map(s => s.title)
    expect(secTitles.some(t => /Introduction/.test(t))).toBe(true)
    expect(secTitles.some(t => /Methods/.test(t))).toBe(true)
    // 3. Introduction section 应该是 'introduction' type（不是 preamble）
    const introSec = r.sections.find(s => /Introduction/.test(s.title))
    expect(introSec.type).toBe('introduction')
    // 4. Methods section 应该是 'methods' type
    const methodsSec = r.sections.find(s => /Methods/.test(s.title))
    expect(methodsSec.type).toBe('methods')
    // 5. 图片应分散到 ≥ 2 个 sections（不再全挤 preamble）
    const anchorSecIds = new Set(Object.keys(r.inlineFigureAnchors).map(p => p.split('__')[0]))
    expect(anchorSecIds.size).toBeGreaterThanOrEqual(2)
    // 6. figures 应该包含 vision 给的 figure_no
    expect(r.figures.some(f => f.figureNo === 'Fig. 1')).toBe(true)
    expect(r.figures.some(f => f.figureNo === 'Fig. 2')).toBe(true)
    // 7. table block 应被识别
    const allBlocks = r.sections.flatMap(s => s.blocks)
    expect(allBlocks.some(b => b.type === 'table')).toBe(true)
    // 8. layout stats 应该传递
    expect(r._layoutStats.totalPages).toBe(2)
  })

  // v28 step 108: vision 后处理 — 合并同一 page_number 的多次输出
  //   vision model 经常把同一 page 输出多次（ID 19 page 8 输出 2 次完全相同）
  //   paperAdapter 必须按 page_number 合并所有 blocks，去重重复 block
  it('v28 step 108: vision page_number 重复时应合并 blocks', () => {
    const visionLayout = {
      has_layout: true,
      total_pages: 9,
      total_blocks: 30,
      page_layout: [
        // page 8 第一次输出（完整内容）
        {
          page_number: 8,
          blocks: [
            { type: 'heading', level: 1, order: 1, text: '3.4 Anti-interference' },
            { type: 'paragraph', order: 2, text: 'first paragraph on page 8' },
            { type: 'paragraph', order: 3, text: 'second paragraph on page 8' },
            { type: 'image', order: 4, image_index: 2, caption: 'Fig. 4. Anti-interference.', figure_no: 'Fig. 4' },
          ],
        },
        // page 8 第二次输出（内容完全相同，vision 重复扫描）
        {
          page_number: 8,
          blocks: [
            { type: 'heading', level: 1, order: 1, text: '3.4 Anti-interference' },
            { type: 'paragraph', order: 2, text: 'first paragraph on page 8' },
            { type: 'paragraph', order: 3, text: 'second paragraph on page 8' },
            { type: 'image', order: 4, image_index: 2, caption: 'Fig. 4. Anti-interference.', figure_no: 'Fig. 4' },
          ],
        },
        // 正常 page
        {
          page_number: 9,
          blocks: [
            { type: 'heading', level: 1, order: 1, text: '3.5 Mechanism' },
          ],
        },
      ],
    }
    const kb = { id: 99, title: 'Test', content: '', summary: null, tags: [] }
    const images = [
      { id: 901, page_number: 8, pageNumber: 8, image_url: '/img/4.png', figure_no: 'Fig. 4', figure_type: 'chart', is_core_figure: true, is_publisher_image: false },
    ]
    const r = normalizePaperData(kb, {
      images, extractions: [], related: [], visionLayout,
    })
    // page 8 合并：2 paragraphs + 1 image_anchor（heading 不在 blocks 里，重复扫描去重）
    const allBlocks = r.sections.flatMap(s => s.blocks)
    const page8Blocks = allBlocks.filter(b => b.page === 8)
    expect(page8Blocks.length).toBe(3)  // 2 paragraphs + 1 image_anchor
    // Fig. 4 只出现 1 次（去重）
    const fig4Blocks = allBlocks.filter(b => b.figure_no === 'Fig. 4')
    expect(fig4Blocks.length).toBe(1)
  })

  // v28 step 108.2: 中文论文（封面+中英文摘要+目录+正文）被 vision 当成 page 1 重复
  //   多次但内容不同 → 不应合并，应拆成独立页（page 1.1, 1.2, 1.3）
  it('v28 step 108.2: 同一 pn 内容不同时应拆为独立页（中文论文格式）', () => {
    const visionLayout = {
      has_layout: true,
      total_pages: 5,
      total_blocks: 12,
      page_layout: [
        { page_number: 1, blocks: [{ type: 'paragraph', order: 1, text: '重庆大学硕士学位论文封面' }] },
        { page_number: 1, blocks: [{ type: 'paragraph', order: 1, text: 'Research on the Control of Manganese' }] },
        { page_number: 1, blocks: [{ type: 'heading', order: 1, text: '摘 要' }, { type: 'paragraph', order: 2, text: '中文摘要内容...' }] },
        { page_number: 1, blocks: [{ type: 'heading', order: 1, text: 'Abstract' }, { type: 'paragraph', order: 2, text: 'English abstract content...' }] },
        { page_number: 2, blocks: [{ type: 'heading', order: 1, text: '1 绪论' }] },
      ],
    }
    const kb = { id: 100, title: 'T', content: '', summary: null, tags: [] }
    const r = normalizePaperData(kb, { images: [], extractions: [], related: [], visionLayout })
    // page 1 应被拆成多个不同 page (1, 1.1, 1.2, 1.3)
    const allBlocks = r.sections.flatMap(s => s.blocks)
    const distinctPages = new Set(allBlocks.map(b => b.page))
    expect(distinctPages.size).toBeGreaterThanOrEqual(4)
    // heading 顺序应保留：摘 要 + Abstract 应成为独立 section
    const abstractSection = r.sections.find(s => s.title?.includes('摘 要'))
    expect(abstractSection).toBeTruthy()
    const englishAbstractSection = r.sections.find(s => s.title?.includes('Abstract'))
    expect(englishAbstractSection).toBeTruthy()
    // 封面 section 应只含封面内容（不含 Abstract 段落）
    const coverSection = r.sections.find(s => s.type === 'preamble' && s.blocks[0]?.content?.includes('重庆大学'))
    expect(coverSection).toBeTruthy()
    expect(coverSection.blocks.find(b => b.content?.includes('Abstract'))).toBeUndefined()
  })

  // v28 step 109.25: vision OCR 把段落错断（如 "the" + 换行 + "conversion"）应合并
  it('v28 step 109.25: vision OCR 断错的两段应自动合并', () => {
    const visionLayout = {
      has_layout: true, total_pages: 3, total_blocks: 4,
      page_layout: [
        {
          page_number: 3,
          blocks: [
            // 段 1 末尾"the"被截断（应该是和段 2 连续的）
            { type: 'paragraph', order: 1, text: 'such as radical generation. It is worth noting that the' },
            // 段 2 是接着的"conversion for..."
            { type: 'paragraph', order: 2, text: 'conversion for CH₃SH over the tested concentration range.' },
            // 段 3 真独立段落（小写开头但是另一段了？还是新话题？）
            { type: 'paragraph', order: 3, text: 'The system showed consistently high and stable' },
            // 段 4 应该和段 3 合并（"The system" + "showed"）
            { type: 'paragraph', order: 4, text: 'showed consistently high and stable conversion.' },
          ],
        },
      ],
    }
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images: [], extractions: [], related: [], visionLayout })
    const allParas = r.sections.flatMap(s => s.blocks || []).filter(b => b.type === 'paragraph')
    console.log('段落数:', allParas.length)
    for (const para of allParas) {
      console.log('  -', para.content.slice(0, 100))
    }
    // 应该合并成 2 段（"the conversion for..." 和 "The system showed consistently..."）
    expect(allParas.length).toBe(2)
    // 关键：CH3SH 段应在第一段
    expect(allParas[0].content).toContain('CH₃SH')
    expect(allParas[0].content).toContain('conversion for')
  })

  // 不应合并的反例：上一段以句末符号结尾（正常段落边界）
  it('v28 step 109.25: 上一段以句末符号结尾则不合并', () => {
    const visionLayout = {
      has_layout: true, total_pages: 1, total_blocks: 3,
      page_layout: [{
        page_number: 1,
        blocks: [
          { type: 'paragraph', order: 1, text: 'This is a complete first paragraph that ends with a period.' },
          { type: 'paragraph', order: 2, text: 'A new sentence starts with capital letter.' },
        ],
      }],
    }
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images: [], extractions: [], related: [], visionLayout })
    const allParas = r.sections.flatMap(s => s.blocks || []).filter(b => b.type === 'paragraph')
    expect(allParas.length).toBe(2)  // 不应合并
  })

  // v28 step 109.30: vision OCR 输出顺序 bug — heading 之前的 paragraph 实际属于新 section
  //   真实数据：page 8 上 block 顺序是
  //     [67] paragraph "conversion for CH₃SH..." (属于 3.4)
  //     [68] paragraph "the molecular model reveals..." (属于 3.5)
  //     [69] heading "3.5. Interfacial microenvironment..."
  //   vision 误把 3.5 内容输出在 heading 之前
  //   修复：heading X.Y 出现时，把上一个 section 中"同一 page 且紧邻 heading"的
  //         最后一个 paragraph 块移到当前 section
  //   关键限制：只移 1 个 block（避免误移 [67] 这种属于 3.4 的内容）
  it('v28 step 109.30: heading 之前紧邻的 paragraph 应属于新 section', () => {
    const visionLayout = {
      has_layout: true, total_pages: 2, total_blocks: 7,
      page_layout: [
        {
          page_number: 8,
          blocks: [
            // 3.4 标题
            { type: 'heading', level: 1, order: 1, text: '3.4. Effects of complex environmental factors' },
            // 3.4 内容
            { type: 'paragraph', order: 2, text: 'CH3SH test' },
            { type: 'paragraph', order: 3, text: 'DCM test' },
            // 3.5 内容（被 vision 误输出在 heading 之前）
            { type: 'paragraph', order: 4, text: 'the molecular model reveals the presence of a stable interface' },
            // 3.5 标题
            { type: 'heading', level: 1, order: 5, text: '3.5. Interfacial microenvironment-promoted activation' },
            // 3.5 后续内容
            { type: 'paragraph', order: 6, text: 'In the O3-MNBs system, the highly efficient removal' },
          ],
        },
      ],
    }
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images: [], extractions: [], related: [], visionLayout })

    // 应有 2 个 section（3.4 + 3.5）
    expect(r.sections.length).toBe(2)

    // 3.4 section 应包含 'CH3SH test' 和 'DCM test'（不含 'molecular model'）
    const sec34 = r.sections[0]
    const sec34Paras = sec34.blocks.filter(b => b.type === 'paragraph').map(b => b.content)
    expect(sec34Paras.some(c => c.includes('CH3SH test'))).toBe(true)
    expect(sec34Paras.some(c => c.includes('DCM test'))).toBe(true)
    expect(sec34Paras.some(c => c.includes('molecular model'))).toBe(false)

    // 3.5 section 应包含 'molecular model' 和 'O3-MNBs system'
    const sec35 = r.sections[1]
    const sec35Paras = sec35.blocks.filter(b => b.type === 'paragraph').map(b => b.content)
    expect(sec35Paras.some(c => c.includes('molecular model'))).toBe(true)
    expect(sec35Paras.some(c => c.includes('O3-MNBs system'))).toBe(true)
    expect(sec35Paras.some(c => c.includes('CH3SH test'))).toBe(false)
    expect(sec35Paras.some(c => c.includes('DCM test'))).toBe(false)

    // 顺序：O3-MNBs system (natural 3.5 content) 应在 molecular model (misplaced) 之前
    // 用户需求："第二段才应该首先出现，之后才是这个第一段内容"
    // 即 misplaced paragraph 应追加到 section 末尾，不抢占开头位置
    const o3Idx = sec35Paras.findIndex(c => c.includes('O3-MNBs system'))
    const mmIdx = sec35Paras.findIndex(c => c.includes('molecular model'))
    expect(o3Idx).toBeGreaterThanOrEqual(0)
    expect(mmIdx).toBeGreaterThanOrEqual(0)
    expect(o3Idx).toBeLessThan(mmIdx)
  })

  // v28 step 109.31: figure-aware 插入 — misplaced paragraph 应按子图字母顺序定位
  //   用户的 paper 真实场景：Fig. 5a → Fig. 5 image → Fig. 5b/c → Fig. 5d/e
  //   vision 把 Fig. 5b/c 段落输出在 heading 之前，应按子图字母顺序插入到 image_anchor 之后、Fig. 5d 之前
  it('v28 step 109.31: misplaced paragraph 应按 figure 子图字母顺序插入', () => {
    const visionLayout = {
      has_layout: true, total_pages: 2, total_blocks: 6,
      page_layout: [
        {
          page_number: 8,
          blocks: [
            // 3.4 heading
            { type: 'heading', level: 1, order: 1, text: '3.4. Effects' },
            // 3.5 misplaced: 引用 Fig. 5b/c（应插在 Fig. 5d 之前、Fig. 5 image 之后）
            { type: 'paragraph', order: 2, text: 'the molecular model reveals a stable interface. Fig. 5b shows charges and Fig. 5c shows orbitals' },
            // 3.5 heading
            { type: 'heading', level: 1, order: 3, text: '3.5. Interfacial activation' },
            // 3.5 intro: 引用 Fig. 5a
            { type: 'paragraph', order: 4, text: 'In the O3-MNBs system, removal is efficient. As illustrated in Fig. 5a, the interface matters.' },
            // 3.5 Fig. 5 image
            { type: 'image', order: 5, image_index: 0, caption: 'Fig. 5. Schematic illustration.', figure_no: 'Fig. 5' },
            // 3.5 orbital coupling: 引用 Fig. 5d
            { type: 'paragraph', order: 6, text: 'orbital coupling and electron transfer. Fig. 5d shows energy profiles and Fig. 5e summarizes the mechanism.' },
          ],
        },
      ],
    }
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images: [], extractions: [], related: [], visionLayout })

    const sec35 = r.sections.find(s => (s.title || '').includes('3.5'))
    expect(sec35).toBeTruthy()

    const paraOrder = sec35.blocks
      .filter(b => b.type === 'paragraph')
      .map(b => {
        if ((b.content || '').includes('molecular model')) return 'molecular_model'
        if ((b.content || '').includes('O3-MNBs system')) return 'O3_MNBs_intro'
        if ((b.content || '').includes('orbital coupling')) return 'orbital_coupling'
        return '?'
      })

    console.log('=== 3.5 paragraph 顺序 ===')
    paraOrder.forEach((p, i) => console.log(`  [${i}] ${p}`))

    // 期望顺序：O3_MNBs_intro → molecular_model → orbital_coupling
    expect(paraOrder).toEqual(['O3_MNBs_intro', 'molecular_model', 'orbital_coupling'])
  })

  // v28 step 109.32: vision 误把 page header 标成 paragraph（应过滤，避免污染正文）
  it('v28 step 109.32: vision 误识的页眉 paragraph 应被过滤', () => {
    const visionLayout = {
      has_layout: true, total_pages: 2, total_blocks: 5,
      page_layout: [
        {
          page_number: 9,
          blocks: [
            // 模拟 vision 误分类：作者行 + 期刊行被标成 paragraph
            { type: 'paragraph', order: 1, text: 'T. Wang et al.\nJournal of Hazardous Materials 513 (2026) 142456' },
            // 真正的正文段
            { type: 'paragraph', order: 2, text: 'orbital coupling and electron transfer between toluene and the oxidizing species. Consistent with these results, the free-energy profiles in Fig. 5d demonstrate the mechanism.' },
          ],
        },
      ],
    }
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images: [], extractions: [], related: [], visionLayout })
    const allBlocks = r.sections.flatMap(s => s.blocks || []).filter(b => b.type === 'paragraph')
    // 页眉应被过滤，只剩 1 个正文段
    expect(allBlocks.length).toBe(1)
    // 正文段不应包含页眉内容
    expect(allBlocks[0].content).not.toContain('T. Wang et al')
    expect(allBlocks[0].content).not.toContain('Journal of Hazardous Materials')
    expect(allBlocks[0].content).toContain('orbital coupling')
  })

  // v28 step 109.34: 跨 section 边界插入 deferred block 后应触发合并
  //   真实案例：用户 paper 中 step 109.30/109.31 把 molecular_model 移到 3.5 末尾 deferred
  //   → 后续 orbital_coupling（step 109.33 拆段后的 Part 1）被 push 到 3.5 currentBlocks
  //   → heading 4 触发 startSection，Step 1 插入 molecular_model 时
  //   → 之前的合并逻辑只在 _processSingleParagraph 中跑，deferred 插入时不跑
  //   → 导致 molecular_model 和 orbital_coupling 错分成两段
  //   修复：Step 1 插入后立即检查与 prev/next 邻居的合并
  it('v28 step 109.34: deferred block 插入后应与下一个 paragraph 合并', () => {
    const visionLayout = {
      has_layout: true, total_pages: 2, total_blocks: 6,
      page_layout: [
        {
          page_number: 8,
          blocks: [
            // 3.4 heading
            { type: 'heading', level: 1, order: 1, text: '3.4. Effects' },
            // 3.4 末段（3.5 引导 paragraph 前一个）
            { type: 'paragraph', order: 2, text: 'last paragraph of 3.4 ends with no period so it stays' },
            // 3.5 misplaced: "the molecular model..." 引用 Fig. 5b/c，无句末符号结尾
            { type: 'paragraph', order: 3, text: 'the molecular model reveals a stable interface. Fig. 5b shows charges and Fig. 5c shows orbitals' },
            // 3.5 heading
            { type: 'heading', level: 1, order: 4, text: '3.5. Interfacial activation' },
            // 3.5 开头段落（Fig. 5a）
            { type: 'paragraph', order: 5, text: 'In the O3-MNBs system. As illustrated in Fig. 5a, the interface matters.' },
            // 3.5 Fig. 5 image
            { type: 'image', order: 6, image_index: 0, caption: 'Fig. 5. Schematic illustration.', figure_no: 'Fig. 5' },
          ],
        },
        {
          page_number: 9,
          blocks: [
            // orbital coupling 段（小写开头 + Fig. 5d）→ 应与 molecular_model 合并
            { type: 'paragraph', order: 1, text: 'orbital coupling and electron transfer. Fig. 5d shows the energy barrier is lower.' },
            // 第二个独立段（Consistent with this...）→ 不应合并到上一段
            { type: 'paragraph', order: 2, text: 'Consistent with this mechanistic picture, the ROS generation further supports the role of interfacial activation.' },
            // 4. heading（触发 startSection 走 Step 1 插入 deferred molecular_model）
            { type: 'heading', level: 1, order: 3, text: '4. Stability' },
          ],
        },
      ],
    }
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images: [], extractions: [], related: [], visionLayout })

    const sec35 = r.sections.find(s => (s.title || '').includes('3.5'))
    expect(sec35).toBeTruthy()

    const paras = sec35.blocks.filter(b => b.type === 'paragraph')
    console.log('=== 3.5 paragraphs ===')
    paras.forEach((p, i) => {
      const first50 = p.content.slice(0, 60).replace(/\n/g, ' ')
      const last50 = p.content.slice(-60).replace(/\n/g, ' ')
      console.log(`  [${i}] "${first50}..." → "...${last50}"`)
    })

    // 期望：
    // 段 1: "In the O3-MNBs system... Fig. 5a"（独立）
    // 段 2: molecular_model + orbital_coupling 合并成一段（关键！）
    // 段 3: "Consistent with this..."（独立）
    expect(paras.length).toBe(3)

    // 段 2 包含 molecular_model 内容
    expect(paras[1].content).toContain('the molecular model reveals')
    // 段 2 也包含 orbital_coupling 内容（合并成功）
    expect(paras[1].content).toContain('orbital coupling and electron transfer')
    // 合并后应自然连接（molecular_model 在前，orbital_coupling 在后，中间是空格）
    const mmIdx = paras[1].content.indexOf('the molecular model')
    const ocIdx = paras[1].content.indexOf('orbital coupling')
    expect(mmIdx).toBeGreaterThanOrEqual(0)
    expect(ocIdx).toBeGreaterThan(mmIdx)
  })

  // v28 step 109.34 反例：插入后没有可合并的邻居 → 不动
  it('v28 step 109.34: deferred block 插入后无邻居可合并 → 不变', () => {
    const visionLayout = {
      has_layout: true, total_pages: 2, total_blocks: 5,
      page_layout: [
        {
          page_number: 8,
          blocks: [
            { type: 'heading', level: 1, order: 1, text: '3.4. Effects' },
            // misplaced: 以 "of" 结尾（无句末符号）→ step 2 会移到 deferred
            { type: 'paragraph', order: 2, text: 'molecular discussion incomplete Fig. 5b shows charges of' },
            { type: 'heading', level: 1, order: 3, text: '3.5. Interfacial activation' },
            // 3.5 段大写开头，不应与上一段合并
            { type: 'paragraph', order: 4, text: 'In the O3-MNBs system. As illustrated in Fig. 5a, the interface matters.' },
          ],
        },
        {
          page_number: 9,
          blocks: [
            // 3.5 末段 - 也大写开头，不应合并
            { type: 'paragraph', order: 1, text: 'Overall, this validates the mechanism. Fig. 5d shows profiles.' },
            { type: 'heading', level: 1, order: 2, text: '4. Stability' },
          ],
        },
      ],
    }
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images: [], extractions: [], related: [], visionLayout })

    const sec35 = r.sections.find(s => (s.title || '').includes('3.5'))
    const paras = sec35.blocks.filter(b => b.type === 'paragraph')
    // 3 段都独立（molecular... 不完整段移到 3.5，但 next 段是大写开头 → 不合并）
    expect(paras.length).toBe(3)
    // 实际位置：figure-aware 插入到 In the O3-MNBs（Fig. 5a）和 Overall（Fig. 5d）之间
    expect(paras[0].content).toContain('In the O3-MNBs')
    expect(paras[1].content).toContain('molecular discussion')
    expect(paras[2].content).toContain('Overall')
  })

  // v28 step 109.34: 完整段（以 . 结尾）不应被 step 2 错移到下一 section
  it('v28 step 109.34: 完整段（以 . 结尾）不应被 step 2 错移', () => {
    const visionLayout = {
      has_layout: true, total_pages: 2, total_blocks: 4,
      page_layout: [
        {
          page_number: 8,
          blocks: [
            { type: 'heading', level: 1, order: 1, text: '3.4. Effects' },
            // misplaced 但以 "." 结尾（完整段）→ step 2 不应移动
            { type: 'paragraph', order: 2, text: 'complete paragraph ends with period. Fig. 5b shows charges.' },
            { type: 'heading', level: 1, order: 3, text: '3.5. Interfacial activation' },
          ],
        },
        {
          page_number: 9,
          blocks: [
            { type: 'paragraph', order: 1, text: 'In the O3-MNBs system. As illustrated in Fig. 5a, the interface matters.' },
            { type: 'heading', level: 1, order: 2, text: '4. Stability' },
          ],
        },
      ],
    }
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images: [], extractions: [], related: [], visionLayout })

    // 完整段留在 3.4（不移动到 3.5）
    const sec34 = r.sections.find(s => (s.title || '').includes('3.4'))
    expect(sec34.blocks.some(b => b.type === 'paragraph' && (b.content || '').includes('complete paragraph'))).toBe(true)

    // 3.5 只有 intro 段
    const sec35 = r.sections.find(s => (s.title || '').includes('3.5'))
    const sec35Paras = sec35.blocks.filter(b => b.type === 'paragraph')
    expect(sec35Paras.length).toBe(1)
    expect(sec35Paras[0].content).toContain('In the O3-MNBs')
  })

  // v28 step 109.33: vision 合并多段到一个 block 时应按过渡短语拆开
  //   真实案例：PDF id=19 page 9 vision [1] block 含两个独立段落
  //     "orbital coupling... facilitates key reaction steps."
  //     "Consistent with this mechanistic picture... reactive oxygen species."
  it('v28 step 109.33: vision 合并多段到一个 block 时按过渡短语拆开', () => {
    const visionLayout = {
      has_layout: true, total_pages: 2, total_blocks: 4,
      page_layout: [
        {
          page_number: 9,
          blocks: [
            // heading 3.5
            { type: 'heading', level: 1, order: 1, text: '3.5 Mechanism' },
            // vision 把两个段合并到一个 block
            { type: 'paragraph', order: 2, text: 'orbital coupling and electron transfer. Consistent with these results, energy barrier is lower. Therefore, the interface facilitates key reaction steps.\nConsistent with this mechanistic picture, the measured OH concentrations further support the role of interfacial ROS generation.' },
            // 真正的第二段（用大写开头 + 过渡短语验证）
            { type: 'paragraph', order: 3, text: 'Furthermore, the experiment validates the proposed mechanism.' },
          ],
        },
      ],
    }
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images: [], extractions: [], related: [], visionLayout })
    const allBlocks = r.sections.flatMap(s => s.blocks || []).filter(b => b.type === 'paragraph')
    // 应该拆成 3 段
    // Para 1: "orbital coupling... facilitates key reaction steps." （中间 .\nConsistent with 触发拆段）
    // Para 2: "Consistent with this mechanistic picture... interfacial ROS generation."
    // Para 3: "Furthermore, the experiment validates..."
    // （顺序：拆分后由 step 109.25 决定是否合并）
    console.log('=== 段落数 ===')
    console.log('共', allBlocks.length, '段')
    allBlocks.forEach((b, i) => {
      console.log(`[${i}] (${b.content.length} chars) "${b.content.slice(0, 80)}..."`)
    })

    // 第一段：以 "orbital coupling" 开头
    expect(allBlocks[0].content).toContain('orbital coupling')
    // 至少一段以 "Consistent with this" 开头
    const hasConsistent = allBlocks.some(b => b.content.startsWith('Consistent with this'))
    expect(hasConsistent).toBe(true)
    // 至少一段以 "Furthermore" 开头
    const hasFurthermore = allBlocks.some(b => b.content.startsWith('Furthermore'))
    expect(hasFurthermore).toBe(true)
  })

  // v28 step 109.33 反例：换行不在句末符号后 → 不应误拆
  it('v28 step 109.33: 软换行（句中换行）不应触发段落分拆', () => {
    const visionLayout = {
      has_layout: true, total_pages: 1, total_blocks: 2,
      page_layout: [{
        page_number: 1,
        blocks: [
          // 软换行（行末无句末符号）→ 不拆段
          { type: 'paragraph', order: 1, text: 'this is a long sentence that\ncontinues on the next line but is still\none paragraph logically' },
        ],
      }],
    }
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images: [], extractions: [], related: [], visionLayout })
    const allBlocks = r.sections.flatMap(s => s.blocks || []).filter(b => b.type === 'paragraph')
    expect(allBlocks.length).toBe(1)
    expect(allBlocks[0].content).toContain('one paragraph logically')
  })

  // v28 step 109.35: OCR 把多段塞进一行（中间仅 1-2 空格）也应拆
  //   真实案例：PDF id=19 section 4 block [2] (2457 字符) 包含三段
  //   step 109.33 只处理换行分隔；新规则处理无换行的多段
  it('v28 step 109.35: 无换行长文本含 Meanwhile / Beyond 等硬段首词应拆段', () => {
    const longText = 'with more comprehensive monitoring are still required to evaluate its long-term performance. Meanwhile, CO₂ was continuously detected throughout the reaction, indicating the mineralization of toluene. Beyond achieving high toluene removal efficiency, the system also demonstrates excellent stability over 7 days of continuous operation. The relevant assumptions, parameters, and detailed calculation procedures are provided in the Supporting Information (Text S3 and Table S1).'
    expect(longText.length).toBeGreaterThan(300)  // 触发长度阈值
    const visionLayout = {
      has_layout: true, total_pages: 1, total_blocks: 1,
      page_layout: [{
        page_number: 4,
        blocks: [{ type: 'paragraph', order: 1, text: longText }],
      }],
    }
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images: [], extractions: [], related: [], visionLayout })
    const allBlocks = r.sections.flatMap(s => s.blocks || []).filter(b => b.type === 'paragraph')
    // 应拆成 3 段
    expect(allBlocks.length).toBe(3)
    expect(allBlocks[0].content).toContain('with more comprehensive')
    expect(allBlocks[1].content).toContain('Meanwhile')
    expect(allBlocks[1].content).not.toContain('Beyond achieving')
    expect(allBlocks[2].content).toContain('Beyond achieving')
    expect(allBlocks[2].content).toContain('Supporting Information')
  })

  // v28 step 109.35 反例：无换行 + 短文本 → 不拆（避免误拆 step 109.25 想合并的"段中段"）
  it('v28 step 109.35: 无换行短文本不应拆段（让 step 109.25 决定）', () => {
    const shortText = 'orbital coupling and electron transfer between toluene and the oxidizing species. Consistent with these results, the free-energy profiles demonstrate the mechanism.'
    expect(shortText.length).toBeLessThan(300)  // 不触发长度阈值
    const visionLayout = {
      has_layout: true, total_pages: 1, total_blocks: 1,
      page_layout: [{
        page_number: 1,
        blocks: [{ type: 'paragraph', order: 1, text: shortText }],
      }],
    }
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images: [], extractions: [], related: [], visionLayout })
    const allBlocks = r.sections.flatMap(s => s.blocks || []).filter(b => b.type === 'paragraph')
    // 应保持 1 段
    expect(allBlocks.length).toBe(1)
    expect(allBlocks[0].content).toContain('Consistent with')
  })

  // v28 step 109.36: lookahead 把下节内容推迟到新 section
  //   真实案例：PDF id=19 page 9 vision [2] = "orbital coupling... oxygen species." (3.5 节内容)
  //   [3] = "with more comprehensive monitoring..." (4 节内容但 OCR 放在 heading 4 之前)
  //   [4] = heading "4. Stability and economic analysis"
  //   → paragraph 3 引用的图号 (Fig. 6) > 当前 section (3.5) 的图号 (Fig. 5) → 推迟到 4 节
  it('v28 step 109.36: paragraph 引用下节图号 + 同 page 紧跟 heading → 推迟到下节', () => {
    const visionLayout = {
      has_layout: true, total_pages: 1, total_blocks: 4,
      page_layout: [{
        page_number: 9,
        blocks: [
          // 3.5 节内容：引用 Fig. 5
          { type: 'heading', level: 3, order: 1, text: '3.5. Microenvironment' },
          { type: 'paragraph', order: 2, text: 'orbital coupling and electron transfer between toluene and the oxidizing species. Consistent with these results, the free-energy profiles in Fig. 5d demonstrate the energy barrier is lower.' },
          // 错位：本应是 4 节内容（引用 Fig. 6），但放在 heading 4 之前
          { type: 'paragraph', order: 3, text: 'with more comprehensive monitoring required. As shown in Fig. 6b-c, the cost is mainly O3 generation. Therefore, this work demonstrates competitive OPEX.' },
          // 4 节 heading
          { type: 'heading', level: 2, order: 4, text: '4. Stability and economic analysis' },
        ],
      }],
    }
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images: [], extractions: [], related: [], visionLayout })
    const sec35 = r.sections.find(s => /3\.5/.test(s.title || ''))
    const sec4 = r.sections.find(s => /4\.\s+Stability/.test(s.title || ''))
    expect(sec35).toBeTruthy()
    expect(sec4).toBeTruthy()
    const sec35Paras = (sec35.blocks || []).filter(b => b.type === 'paragraph')
    const sec4Paras = (sec4.blocks || []).filter(b => b.type === 'paragraph')
    // 3.5 应该有 orbital coupling 段
    expect(sec35Paras.some(b => b.content.includes('orbital coupling'))).toBe(true)
    // 3.5 不应该有 with more comprehensive（已被推迟到 4 节）
    expect(sec35Paras.some(b => b.content.includes('with more comprehensive'))).toBe(false)
    // 4 节应该有 with more comprehensive 段
    expect(sec4Paras.some(b => b.content.includes('with more comprehensive'))).toBe(true)
  })

  // v28 step 109.36 反例：paragraph 引用同节图号 → 不推迟
  it('v28 step 109.36: paragraph 引用同节图号 → 不推迟', () => {
    const visionLayout = {
      has_layout: true, total_pages: 1, total_blocks: 3,
      page_layout: [{
        page_number: 9,
        blocks: [
          { type: 'heading', level: 2, order: 1, text: '3. Results' },
          { type: 'paragraph', order: 2, text: 'As shown in Fig. 3a, the conversion increased with time. In contrast, Fig. 3b shows the opposite trend.' },
          { type: 'heading', level: 2, order: 3, text: '4. Discussion' },
        ],
      }],
    }
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images: [], extractions: [], related: [], visionLayout })
    const sec3 = r.sections.find(s => /3\.\s*Results/.test(s.title || ''))
    const sec4 = r.sections.find(s => /4\.\s*Discussion/.test(s.title || ''))
    expect(sec3).toBeTruthy()
    expect(sec4).toBeTruthy()
    const sec3Paras = (sec3.blocks || []).filter(b => b.type === 'paragraph')
    const sec4Paras = (sec4.blocks || []).filter(b => b.type === 'paragraph')
    // Fig. 3 引用应在 3 节（heading 4 也只引用 Fig. 3 → nextMaxNum=0 → 不推迟）
    expect(sec3Paras.some(b => b.content.includes('Fig. 3a'))).toBe(true)
  })

  // v28 step 109.32: page header 不应与 adjacent paragraph 合并
  it('v28 step 109.32: 页眉段不与正文段合并（step 109.25 合并前置过滤）', () => {
    const visionLayout = {
      has_layout: true, total_pages: 2, total_blocks: 5,
      page_layout: [
        {
          page_number: 9,
          blocks: [
            // 真实正文段（uppercase + period 结尾 → 不应被合并）
            { type: 'paragraph', order: 1, text: 'first paragraph ends with period.' },
            // 页眉段（无 period 结尾，vision 误识为可合并的段）
            { type: 'paragraph', order: 2, text: 'T. Wang et al.\nJournal of Hazardous Materials 513 (2026) 142456' },
            // 第二段正文
            { type: 'paragraph', order: 3, text: 'second paragraph of body.' },
          ],
        },
      ],
    }
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images: [], extractions: [], related: [], visionLayout })
    const allBlocks = r.sections.flatMap(s => s.blocks || []).filter(b => b.type === 'paragraph')
    // 应该是 2 段（first + second），页眉被过滤
    expect(allBlocks.length).toBe(2)
    expect(allBlocks[0].content).toContain('first paragraph')
    expect(allBlocks[1].content).toContain('second paragraph')
    // 不能有页眉内容残留
    allBlocks.forEach(b => {
      expect(b.content).not.toContain('T. Wang et al')
    })
  })

  // v28 step 109.31 反例：misplaced 无 figure 引用 → 仍追加到末尾
  it('v28 step 109.31: misplaced 无 figure 引用时应追加到末尾（不破坏现有逻辑）', () => {
    const visionLayout = {
      has_layout: true, total_pages: 2, total_blocks: 5,
      page_layout: [
        {
          page_number: 8,
          blocks: [
            { type: 'heading', level: 1, order: 1, text: '3.4 Effects' },
            { type: 'paragraph', order: 2, text: 'some text without figure references' },
            { type: 'heading', level: 1, order: 3, text: '3.5 Mechanism' },
            { type: 'paragraph', order: 4, text: 'first paragraph of 3.5' },
            { type: 'paragraph', order: 5, text: 'second paragraph of 3.5' },
          ],
        },
      ],
    }
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images: [], extractions: [], related: [], visionLayout })
    const sec35 = r.sections.find(s => (s.title || '').includes('3.5'))
    const paras = sec35.blocks.filter(b => b.type === 'paragraph')
    // misplaced（无 fig ref）应在末尾
    expect(paras.length).toBe(3)
    expect(paras[2].content).toContain('without figure references')
  })

  // v28 step 109.30 反例：heading 之前是不同 page 的 paragraph（不应移动）
  it('v28 step 109.30: heading 之前跨 page 的 paragraph 不应被移动', () => {
    const visionLayout = {
      has_layout: true, total_pages: 2, total_blocks: 5,
      page_layout: [
        {
          page_number: 7,
          blocks: [
            { type: 'heading', level: 1, order: 1, text: '3.4 Effects' },
            { type: 'paragraph', order: 2, text: 'paragraph on page 7' },
          ],
        },
        {
          page_number: 8,
          blocks: [
            // heading 直接出现，前一段是不同 page
            { type: 'heading', level: 1, order: 1, text: '3.5 Mechanism' },
            { type: 'paragraph', order: 2, text: 'content of 3.5' },
          ],
        },
      ],
    }
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images: [], extractions: [], related: [], visionLayout })
    // 跨 page 时不移动，page 7 的 paragraph 应保留在 3.4 section
    const sec34 = r.sections[0]
    const sec34Paras = sec34.blocks.filter(b => b.type === 'paragraph').map(b => b.content)
    expect(sec34Paras.some(c => c.includes('paragraph on page 7'))).toBe(true)
  })

  // v28 step 109.26: 上一段末尾是开括号未闭合 → 下一段任何字符开头都应合并
  it('v28 step 109.26: 上一段末尾是开括号未闭合则合并（无论下段首字符大小写）', () => {
    const visionLayout = {
      has_layout: true, total_pages: 1, total_blocks: 3,
      page_layout: [{
        page_number: 1,
        blocks: [
          // 上段末尾是 '(' 开括号未闭合
          { type: 'paragraph', order: 1, text: 'The zeta potential was measured using a Zetasizer nanoparticle analyzer (Malvern Panalytical' },
          // 下段开头是大写缩写 "ZS₉₀)"，其实是上段括号内接续
          { type: 'paragraph', order: 2, text: 'ZS₉₀), and the bubble size was measured using a nanoparticle tracking analyzer.' },
        ],
      }],
    }
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images: [], extractions: [], related: [], visionLayout })
    const allParas = r.sections.flatMap(s => s.blocks || []).filter(b => b.type === 'paragraph')
    // 应合并成 1 段
    expect(allParas.length).toBe(1)
    // 合并后内容应包含括号完整匹配
    expect(allParas[0].content).toContain('(Malvern Panalytical ZS₉₀)')
    expect(allParas[0].content).toContain('and the bubble size')
  })

  // v28 step 109.5: vision layout 路径下 imageId 提取必须兼容 DB 数字 ID
  //   之前：imageId 提取只看 'fig-' 前缀字符串 → vision 路径用 DB 数字 ID 永远 null
  //   结果：paperFigures[*].src 全是 null → FigureCard 的 <img src=""> 空字符串
  //   用户 console 显示 "7 个 img 全部 src 空"
  it('v28 step 109.5: vision 路径 imageId 提取兼容 DB 数字 ID（src 不为空）', () => {
    const visionLayout = {
      has_layout: true, total_pages: 1, total_blocks: 2,
      page_layout: [{
        page_number: 1,
        blocks: [
          { type: 'image', order: 1, image_index: 0, figure_no: 'Fig. 1', caption: 'Fig. 1. Test' },
          { type: 'paragraph', order: 2, text: 'paragraph after figure' },
        ],
      }],
    }
    const images = [
      { id: 528, page_number: 1, image_url: 'https://example.com/img1.png' },
    ]
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images, extractions: [], related: [], visionLayout })
    expect(r.figures.length).toBeGreaterThan(0)
    // 关键：src 必须有值，不能空字符串
    const fig = r.figures[0]
    expect(fig.src).toBe('https://example.com/img1.png')
    expect(fig.imageUrl).toBe('https://example.com/img1.png')
    expect(fig.imageId).toBe(528)
    // figureRegistry 自身也要有 src（PaperBlockRenderer._resolveFigure 读这个）
    expect(r.figureRegistry[0].src).toBe('https://example.com/img1.png')
  })

  // v28 step 109.6: isPublisherImage 的图不应出现在 paperFigures（避免 Elsevier logo 重复）
  //   vision 经常把 image_index=0 赋给多张图（imageByGlobalIndex[0] 是 logo）
  //   关联到 publisher 图的 fig 应被丢弃 src
  it('v28 step 109.6: publisher 图不应污染 paperFigures 的 src', () => {
    const visionLayout = {
      has_layout: true, total_pages: 1, total_blocks: 3,
      page_layout: [{
        page_number: 1,
        blocks: [
          { type: 'image', order: 1, image_index: 0, figure_no: 'Fig. 1', caption: 'Fig. 1. Real' },
          { type: 'image', order: 2, image_index: 0, figure_no: 'Fig. 2', caption: 'Fig. 2. Real but matched logo' },
          { type: 'paragraph', order: 3, text: 'normal text after figures' },
        ],
      }],
    }
    const images = [
      { id: 528, page_number: 1, image_url: 'https://example.com/logo.png',
        is_publisher_image: true },  // Elsevier logo
      { id: 529, page_number: 1, image_url: 'https://example.com/fig1.png' },
    ]
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images, extractions: [], related: [], visionLayout })
    // v28 step 109.9: smart fallback — Fig. 1 命中 logo → fallback level 3（同 page 未用非 publisher）
    //   → 找到 image 529 → 应有 src
    //   Fig. 2 命中 logo → fallback 仍找不到（image 529 已被 Fig. 1 占用）→ src=null
    const fig1 = r.figures.find(f => f.figureNo === 'Fig. 1')
    const fig2 = r.figures.find(f => f.figureNo === 'Fig. 2')
    expect(fig1?.src).toBe('https://example.com/fig1.png')
    expect(fig2?.src).toBeNull()
  })

  // v28 step 109.12: figureNo 优先从 caption 提取（vision 经常 figure_no 与 caption 不对应）
  it('v28 step 109.12: figureNo 优先从 caption 提取（更可靠）', () => {
    const visionLayout = {
      has_layout: true, total_pages: 1, total_blocks: 2,
      page_layout: [{
        page_number: 8,
        blocks: [
          // vision 给 figure_no="Fig. 1" 但 caption 是 "Fig. 3. Effects..." —— 错位
          { type: 'image', order: 1, image_index: 2, figure_no: 'Fig. 1',
            caption: 'Fig. 3. Effects of complex environmental factors on the toluene conversion' },
        ],
      }],
    }
    const images = [
      { id: 536, page_number: 8, image_url: 'https://example.com/536.png',
        is_publisher_image: false, is_core_figure: true, figure_type: 'chart' },
    ]
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images, extractions: [], related: [], visionLayout })
    // figureNo 应该从 caption 提取 = "Fig. 3"（不是 vision 的 "Fig. 1"）
    const fig = r.figures[0]
    expect(fig.figureNo).toBe('Fig. 3')
  })

  // v28 step 109.9: vision image_index 命中 publisher 时，4 级 fallback 找真实图
  //   Level 1: 同 page + 同 figureNo
  //   Level 2: 同 page + 同 figureType
  //   Level 3: 同 page 未用的非 publisher 图
  //   Level 4: 全局未用的非 publisher 图
  it('v28 step 109.9: vision image_index 错位时 fallback 到同 page 真实图', () => {
    const visionLayout = {
      has_layout: true, total_pages: 5, total_blocks: 4,
      page_layout: [
        {
          page_number: 8,  // vision 说 Fig. 3 在 page 8
          blocks: [
            { type: 'image', order: 1, image_index: 0, figure_no: 'Fig. 3', caption: 'Fig. 3. Mechanism' },
          ],
        },
        {
          page_number: 8.2,
          blocks: [
            { type: 'image', order: 2, image_index: 0, figure_no: 'Fig. 5', caption: 'Fig. 5. Mechanism' },
          ],
        },
      ],
    }
    // image 528 (logo) 在 page 1，image 536 (真实图) 在 page 8
    const images = [
      { id: 528, page_number: 1, image_url: 'https://example.com/logo.png',
        is_publisher_image: true, is_core_figure: false, figure_type: 'logo' },
      { id: 536, page_number: 8, image_url: 'https://example.com/fig3-5.png',
        is_publisher_image: false, is_core_figure: true, figure_type: 'mechanism' },
    ]
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images, extractions: [], related: [], visionLayout })
    // Fig. 3 image_index=0 → 命中 528 (logo) → fallback level 3 同 page=8 找 → 找到 536
    const fig3 = r.figures.find(f => f.figureNo === 'Fig. 3')
    expect(fig3?.src).toBe('https://example.com/fig3-5.png')
    // Fig. 5 image_index=0 → 命中 528 (logo) → fallback → 同 page=8.2 没图
    //   → level 4 全局未用 → 536 已被 Fig. 3 占用 → null
    const fig5 = r.figures.find(f => f.figureNo === 'Fig. 5')
    expect(fig5?.src).toBeNull()
  })

  // v28 step 109.7: OCR 误识的图说明段落应被过滤
  it('v28 step 109.7: 过滤 OCR 图说明段落（该图为/This figure shows）', () => {
    const visionLayout = {
      has_layout: true, total_pages: 1, total_blocks: 5,
      page_layout: [{
        page_number: 1,
        blocks: [
          { type: 'image', order: 1, image_index: 0, figure_no: 'Fig. 1', caption: 'Fig. 1. Setup' },
          // vision OCR 把图说明误当 paragraph
          { type: 'paragraph', order: 2, text: '该图为一套用于微纳米气泡（MNB）处理挥发性有机物（甲苯，C7H8）的实验装置流程示意图。' },
          { type: 'paragraph', order: 3, text: 'This figure shows the experimental setup used for testing.' },
          // 真正的正文段落
          { type: 'paragraph', order: 4, text: '本章主要研究了微纳米气泡在不同条件下的氧化性能。' },
          { type: 'paragraph', order: 5, text: 'The conversion of toluene was measured under various conditions.' },
        ],
      }],
    }
    const images = [
      { id: 528, page_number: 1, image_url: 'https://example.com/fig1.png' },
    ]
    const r = normalizePaperData({ id: 99, title: 'T', content: '', summary: null, tags: [] },
      { images, extractions: [], related: [], visionLayout })
    const allParas = r.sections.flatMap(s => s.blocks || []).filter(b => b.type === 'paragraph')
    const paraTexts = allParas.map(b => b.content)
    // OCR 图说明应被过滤
    expect(paraTexts.find(t => t && t.includes('该图为一套'))).toBeUndefined()
    expect(paraTexts.find(t => t && t.includes('This figure shows'))).toBeUndefined()
    // 真正的正文应保留
    expect(paraTexts.find(t => t && t.includes('本章主要研究'))).toBeTruthy()
    expect(paraTexts.find(t => t && t.includes('conversion of toluene'))).toBeTruthy()
  })

  // v28 step 109.3: vision 误识 TOC 条目应被过滤（不创建虚假 sections）
  //   目录里的 "1 绪论..............1" 被 vision 当 heading
  //   但不能误杀普通段落里的省略号 "..."
  it('v28 step 109.3: TOC 条目过滤（不误杀正常省略号）', () => {
    const visionLayout = {
      has_layout: true, total_pages: 3, total_blocks: 8,
      page_layout: [
        // 目录页
        {
          page_number: 2,
          blocks: [
            { type: 'heading', order: 1, text: '目录' },
            { type: 'heading', order: 2, text: '1 绪论..............................1' },
            { type: 'heading', order: 3, text: '2 试验材料与方法............5' },
            { type: 'heading', order: 4, text: '摘 要...........I' },  // 中文 TOC 无数字前缀
            { type: 'heading', order: 5, text: 'Abstract...........II' },
            { type: 'paragraph', order: 6, text: '正常段落里的省略号...' },  // 不能误杀
          ],
        },
        // 真正的 1 绪论正文页（章节标题+正常段落）
        {
          page_number: 3,
          blocks: [
            { type: 'heading', order: 1, text: '1 绪论' },
            { type: 'paragraph', order: 2, text: '随着工业化进程加快...' },
            { type: 'paragraph', order: 3, text: '研究表明存在以下问题...' },
          ],
        },
      ],
    }
    const kb = { id: 101, title: 'T', content: '', summary: null, tags: [] }
    const r = normalizePaperData(kb, { images: [], extractions: [], related: [], visionLayout })
    // TOC entry heading 不应创建 sections
    const tocSubsection = r.sections.find(s => s.title?.includes('试验材料与方法'))
    expect(tocSubsection).toBeUndefined()
    // 真正的 1 绪论章节应保留（section title 不含 dot leader）
    const introSection = r.sections.find(s => s.title === '1 绪论' && s.type === 'introduction')
    expect(introSection).toBeTruthy()
    expect(introSection.blocks.length).toBeGreaterThanOrEqual(2)
  })

  // v28 step 109.1: vision 输出 paragraph text 会保留 OCR 软换行（词中断开）
  //   paperAdapter 必须合并这些软换行（hyphen + 词中断开）
  it('v28 step 109.1: vision paragraph OCR 软换行应合并', () => {
    const visionLayout = {
      has_layout: true,
      total_pages: 1,
      total_blocks: 5,
      page_layout: [
        {
          page_number: 1,
          blocks: [
            // vision 保留了 OCR 软换行（PDF 原始换行，用真 \n 字符）
            { type: 'paragraph', order: 1, text: 'Micro-nano bubbles (MNBs) have demonstrated broad applica-\ntion prospects in the field of environmental gover-\nnance due to their extremely large specific surface\narea, long residence time in water, and surface charge.' },
          ],
        },
      ],
    }
    const kb = { id: 99, title: 'Test', content: '', summary: null, tags: [] }
    const r = normalizePaperData(kb, {
      images: [], extractions: [], related: [], visionLayout,
    })
    const para = r.sections[0]?.blocks[0]
    expect(para).toBeTruthy()
    // hyphen 词断行应该合并（applica-tion → application, gover-nance → governance）
    expect(para.content).toContain('application')
    expect(para.content).toContain('governance')
    expect(para.content).not.toContain('applica-\ntion')
    expect(para.content).not.toContain('gover-\nnance')
    // 单词被换行截断（surface + area）应该合并为 surface area
    expect(para.content).toContain('surface area')
  })

  // v28 step 106: vision 输出 reference_list 类型
  //   当 vision 识别参考文献时，paperAdapter 应作为独立 block 处理
  it('v28 step 106: vision reference_list 应作为独立 block', () => {
    const visionLayout = {
      has_layout: true,
      total_pages: 2,
      total_blocks: 8,
      page_layout: [
        {
          page_number: 1,
          blocks: [
            { type: 'heading', level: 1, order: 1, text: '5. Conclusions' },
            { type: 'paragraph', order: 2, text: 'In conclusion, ...' },
          ],
        },
        {
          page_number: 2,
          blocks: [
            { type: 'heading', level: 1, order: 1, text: 'References' },
            { type: 'reference_list', order: 2, text: '[1] Smith J., 2024. Title. Journal 1, 10-20.\n[2] Wang T., 2024. Title. Journal 2, 30-40.' },
          ],
        },
      ],
    }
    const kb = { id: 99, title: 'Test', content: '', summary: null, tags: [] }
    const r = normalizePaperData(kb, {
      images: [], extractions: [], related: [], visionLayout,
    })
    // 应该有 references section
    const refSec = r.sections.find(s => s.type === 'references')
    expect(refSec).toBeTruthy()
    expect(refSec.blocks.some(b => b.type === 'reference_list')).toBe(true)
    const refBlock = refSec.blocks.find(b => b.type === 'reference_list')
    expect(refBlock.content).toContain('[1] Smith J.')
    expect(refBlock.content).toContain('[2] Wang T.')
  })

  // v28 step 106: paperAdapter 兜底检测 paragraph 里的 [N] 参考文献格式
  //   当 vision 没识别 reference_list 时，paragraph blocks 里的 [N] ... 应被提取
  it('v28 step 106: paragraph 含 [N] 参考文献格式应自动提取', () => {
    const visionLayout = {
      has_layout: true,
      total_pages: 1,
      total_blocks: 5,
      page_layout: [
        {
          page_number: 10,
          blocks: [
            { type: 'heading', level: 1, order: 1, text: '4. Discussion' },
            { type: 'paragraph', order: 2, text: 'The MNBs/UV system offers...', page: 10 },
            // vision 没识别 references，但 paragraph 含 [N] 格式
            { type: 'paragraph', order: 3, text: '[1] Smith J., Wang T., 2024. Synergistic disinfection. Chem Eng J 525, 117-128.', page: 10 },
            { type: 'paragraph', order: 4, text: '[2] Yu J., Le T., 2023. Catalyst-free oxidation. Nat Commun 14 (1), 7514.', page: 10 },
          ],
        },
      ],
    }
    const kb = { id: 99, title: 'Test', content: '', summary: null, tags: [] }
    const r = normalizePaperData(kb, {
      images: [], extractions: [], related: [], visionLayout,
    })
    // 应该从 paragraph 里抽出 reference_list
    const allBlocks = r.sections.flatMap(s => s.blocks)
    const refBlocks = allBlocks.filter(b => b.type === 'reference_list')
    expect(refBlocks.length).toBeGreaterThanOrEqual(1)
    expect(refBlocks[0].content).toContain('[1] Smith J.')
    expect(refBlocks[0].content).toContain('[2] Yu J.')
  })
})

// ============================================================
// v28 step 109.37: 关键词中英翻译
// ============================================================
//
// 用户需求：关键词也用英文显示
// 数据库 tags 字段经常是中文（运维录入 / LLM 抽取），但 PDF 原文 Keywords 段是英文
// _translateKeywordsToEnglish 通过 KEYWORD_ZH_TO_EN 映射表翻译中文 tags 为英文

describe('v28 step 109.37: 关键词中英翻译 - translateKeywordToEnglish', () => {
  it('完全匹配的中文关键词应翻译', () => {
    expect(translateKeywordToEnglish('微纳米气泡')).toBe('Micro-nanobubbles')
    expect(translateKeywordToEnglish('臭氧')).toBe('Ozone')
    expect(translateKeywordToEnglish('过氧化氢')).toBe('Hydrogen peroxide')
    expect(translateKeywordToEnglish('甲苯氧化')).toBe('Toluene oxidation')
    expect(translateKeywordToEnglish('活性氧物种')).toBe('Reactive oxygen species')
    expect(translateKeywordToEnglish('气液传质')).toBe('Gas-liquid mass transfer')
    expect(translateKeywordToEnglish('水处理')).toBe('Water treatment')
    expect(translateKeywordToEnglish('无催化剂')).toBe('Catalyst-free')
  })

  it('已经是英文的关键词应原样保留', () => {
    expect(translateKeywordToEnglish('Micro-nanobubbles')).toBe('Micro-nanobubbles')
    expect(translateKeywordToEnglish('Hydrogen peroxide')).toBe('Hydrogen peroxide')
    expect(translateKeywordToEnglish('Toluene oxidation')).toBe('Toluene oxidation')
    expect(translateKeywordToEnglish('Ozone')).toBe('Ozone')
  })

  it('不在映射表的中文关键词应原样保留', () => {
    expect(translateKeywordToEnglish('未知中文术语')).toBe('未知中文术语')
    expect(translateKeywordToEnglish('人工智能')).toBe('人工智能')
  })

  it('子串匹配：长 key 优先', () => {
    // "微纳米气泡技术" 含 "微纳米气泡"，但 "微纳米气泡技术" 在映射表更具体
    expect(translateKeywordToEnglish('微纳米气泡技术')).toBe('Micro-nanobubble technology')
    expect(translateKeywordToEnglish('臭氧微纳米气泡')).toBe('Ozone micro-nanobubbles')
    expect(translateKeywordToEnglish('高级氧化工艺')).toBe('Advanced oxidation processes')
  })

  it('空字符串和非字符串应安全返回', () => {
    expect(translateKeywordToEnglish('')).toBe('')
    expect(translateKeywordToEnglish(null)).toBe(null)
    expect(translateKeywordToEnglish(undefined)).toBe(undefined)
    expect(translateKeywordToEnglish(123)).toBe(123)
  })

  it('去除前后空白', () => {
    expect(translateKeywordToEnglish('  微纳米气泡  ')).toBe('Micro-nanobubbles')
    expect(translateKeywordToEnglish('\t臭氧\n')).toBe('Ozone')
  })
})

describe('v28 step 109.37: 关键词中英翻译 - translateKeywordsToEnglish', () => {
  it('PDF id=19 的 8 个中文关键词应正确翻译', () => {
    // 用户提供的完整列表
    const input = [
      '微纳米气泡', '臭氧', '过氧化氢', '甲苯氧化',
      '活性氧物种', '气液传质', '水处理', '无催化剂',
    ]
    const result = translateKeywordsToEnglish(input)
    expect(result).toEqual([
      'Micro-nanobubbles',
      'Ozone',
      'Hydrogen peroxide',
      'Toluene oxidation',
      'Reactive oxygen species',
      'Gas-liquid mass transfer',
      'Water treatment',
      'Catalyst-free',
    ])
  })

  it('混合中英文应只翻译中文', () => {
    const input = ['微纳米气泡', 'Micro-nanobubbles', 'Hydrogen peroxide', '臭氧']
    const result = translateKeywordsToEnglish(input)
    // Micro-nanobubbles 出现两次（中文翻译 + 原文），去重保留首次
    expect(result).toContain('Micro-nanobubbles')
    expect(result).toContain('Hydrogen peroxide')
    expect(result).toContain('Ozone')
    expect(result.length).toBe(3)
  })

  it('空数组和非数组应安全返回', () => {
    expect(translateKeywordsToEnglish([])).toEqual([])
    expect(translateKeywordsToEnglish(null)).toEqual([])
    expect(translateKeywordsToEnglish(undefined)).toEqual([])
    expect(translateKeywordsToEnglish('not an array')).toEqual([])
  })

  it('过滤空字符串和非字符串', () => {
    const input = ['微纳米气泡', '', null, undefined, '臭氧', '  ']
    const result = translateKeywordsToEnglish(input)
    expect(result).toEqual(['Micro-nanobubbles', 'Ozone'])
  })

  it('大小写不同的翻译结果应去重', () => {
    const input = ['微纳米气泡', 'MICRO-NANOBUBBLES', 'micro-nanobubbles']
    const result = translateKeywordsToEnglish(input)
    expect(result.length).toBe(1)
  })
})

describe('v28 step 109.37: normalizePaperData 集成 - 关键词翻译', () => {
  it('PDF id=19 raw.tags 是中文应被翻译', () => {
    const raw = {
      id: 19,
      title: 'Test',
      content: '...',
      summary: '...',
      tags: ['微纳米气泡', '臭氧', '过氧化氢', '甲苯氧化', '活性氧物种', '气液传质', '水处理', '无催化剂'],
    }
    const r = normalizePaperData(raw, { images: [], extractions: [], related: [] })
    expect(r.keywords).toEqual([
      'Micro-nanobubbles',
      'Ozone',
      'Hydrogen peroxide',
      'Toluene oxidation',
      'Reactive oxygen species',
      'Gas-liquid mass transfer',
      'Water treatment',
      'Catalyst-free',
    ])
    // tags 字段也同步翻译
    expect(r.tags).toEqual(r.keywords)
  })

  it('PDF id=19 raw.tags 是英文应原样保留', () => {
    const raw = {
      id: 14,
      title: 'Test',
      content: '...',
      summary: '...',
      tags: ['Micro-nanobubbles', 'Ozone', 'Hydrogen peroxide'],
    }
    const r = normalizePaperData(raw, { images: [], extractions: [], related: [] })
    expect(r.keywords).toEqual(['Micro-nanobubbles', 'Ozone', 'Hydrogen peroxide'])
  })

  it('raw.tags 为空时（从原文 content 抽）应也走翻译', () => {
    const raw = {
      id: 19,
      title: 'Test',
      content: '[PAGE:1]\nAbstract:\nThis is a test abstract.\nKeywords:\n微纳米气泡\n臭氧\n过氧化氢\n甲苯氧化\n活性氧物种\n气液传质\n水处理\n无催化剂\n[PAGE:2]\n1. Introduction\n...',
      summary: '...',
      tags: [],
    }
    const r = normalizePaperData(raw, { images: [], extractions: [], related: [] })
    // v28 step 109.37: 期望每个关键词被独立翻译（不是合并成一个字符串）
    expect(r.keywords.length).toBeGreaterThanOrEqual(7)
    expect(r.keywords).toContain('Micro-nanobubbles')
    expect(r.keywords).toContain('Ozone')
  })
})


// ============================================================
// v28 step 109.38: 作者 + 期刊 + 机构 提取
// ============================================================
//
// 用户反馈：PaperHeader 顶部 UI 应该展示论文的所有作者和期刊名。
// PDF 原文包含：
//   - 作者行（"Name1 a, Name2 b, Name3 c, Name4 a,*"）
//   - 机构行（"a School of...", "b College of...", "c State..."）
//   - 期刊头（"Journal of Hazardous Materials 513 (2026) 142456"）
//
// _extractAuthorsAndJournal 从原文 content 抽这些结构化信息。

describe('v28 step 109.38: extractAuthorsAndJournal', () => {
  it('PDF id=19: 完整 Elsevier 格式', () => {
    const content = `Catalyst-free aqueous-phase oxidation of toluene by ozone
micro-nanobubbles coupled with H2O2 via interfacial reactive
oxygen species
Tianzhi Wang a, Hangjia Zhao a, Yongtao Li a, Ziyue Jiang b, Lingye Zhang b, Andrei Ivanets c
,
Fawei Lin a,*
a School of Environmental Science and Engineering, Tianjin University/Tianjin Key Lab of Biomass/Wastes Utilization, Tianjin 300072, PR China
b College of energy environment and safety engineering, China Jiliang University, Hangzhou 310018, PR China
c State Scientific Institution, Institute of General and Inorganic Chemistry of National Academy of Sciences of Belarus, Minsk 220072, Belarus
H I G H L I G H T S
T. Wang et al.
Journal of Hazardous Materials 513 (2026) 142456
A B S T R A C T
Conventional aqueous ozonation...`
    const r = extractAuthorsAndJournal(content)

    // Authors: 7 人 + 通讯作者标记
    expect(r.authors.length).toBe(7)
    expect(r.authors[0]).toMatchObject({ name: 'Tianzhi Wang', affiliation: 'a' })
    expect(r.authors[1].name).toBe('Hangjia Zhao')
    expect(r.authors[3].name).toBe('Ziyue Jiang')
    expect(r.authors[6]).toMatchObject({ name: 'Fawei Lin', affiliation: 'a', isCorresponding: true })

    // Affiliations: 3 个机构
    expect(r.affiliations.length).toBe(3)
    expect(r.affiliations[0].id).toBe('a')
    expect(r.affiliations[0].name).toContain('School of Environmental')
    expect(r.affiliations[1].id).toBe('b')
    expect(r.affiliations[2].id).toBe('c')

    // Journal
    expect(r.journal.name).toBe('Journal of Hazardous Materials')
    expect(r.journal.volume).toBe('513')
    expect(r.journal.year).toBe('2026')
    expect(r.journal.articleId).toBe('142456')
    expect(r.journal.fullCitation).toBe('Journal of Hazardous Materials 513 (2026) 142456')
  })

  it('空 content 返回空结构', () => {
    const r = extractAuthorsAndJournal('')
    expect(r.authors).toEqual([])
    expect(r.affiliations).toEqual([])
    expect(r.journal.name).toBeNull()
    expect(r.doi).toBeNull()
  })

  it('null/undefined content 安全返回', () => {
    expect(extractAuthorsAndJournal(null).authors).toEqual([])
    expect(extractAuthorsAndJournal(undefined).authors).toEqual([])
  })

  it('单作者无机构', () => {
    const content = `Some Title
John Smith
H I G H L I G H T S
A B S T R A C T
Body`
    const r = extractAuthorsAndJournal(content)
    expect(r.authors.length).toBe(1)
    expect(r.authors[0].name).toBe('John Smith')
  })

  it('通用期刊名提取（不在白名单）', () => {
    const content = `Title
John Smith a
a School of X
H I G H L I G H T S
Letters in Organic Chemistry 25 (2024) 1234
A B S T R A C T`
    const r = extractAuthorsAndJournal(content)
    // 通用模式匹配 Letters/Reviews/Advances/Journal
    expect(r.journal.name).toBe('Letters in Organic Chemistry')
    expect(r.journal.volume).toBe('25')
    expect(r.journal.year).toBe('2024')
    expect(r.journal.articleId).toBe('1234')
  })

  it('DOI 提取（doi.org 格式）', () => {
    const content = `Title
Author a
a School
H I G H L I G H T S
Journal of Foo 1 (2024) 100
A B S T R A C T
Body. See https://doi.org/10.1016/j.foo.2024.100 for details.`
    const r = extractAuthorsAndJournal(content)
    expect(r.doi).toBe('10.1016/j.foo.2024.100')
  })

  it('DOI 提取（DOI: 前缀格式）', () => {
    const content = `Title
Author a
a School
Journal of Foo 1 (2024) 100
DOI: 10.1234/foo.bar.2024.001
A B S T R A C T`
    const r = extractAuthorsAndJournal(content)
    expect(r.doi).toBe('10.1234/foo.bar.2024.001')
  })

  it('集成测试：normalizePaperData 注入 authors/journal/affiliations', () => {
    const content = `Title
John Smith a, Jane Doe b
a School of Foo, City
b University of Bar
H I G H L I G H T S
Journal of Foo 1 (2024) 100
A B S T R A C T
Body`
    const raw = {
      id: 99,
      title: 'Title',
      content,
      summary: '',
      tags: [],
    }
    const r = normalizePaperData(raw, { images: [], extractions: [], related: [] })
    expect(r.authors.length).toBe(2)
    expect(r.authors[0].name).toBe('John Smith')
    expect(r.authors[1].name).toBe('Jane Doe')
    expect(r.affiliations.length).toBe(2)
    expect(r.journal.name).toBe('Journal of Foo')
    expect(r.journal.fullCitation).toBe('Journal of Foo 1 (2024) 100')
  })

  it('v28 step 109.38 regression: blockquote 中的 CapitalName 不应误抽为作者', () => {
    // v28 step 109.38 修复前：line scanner 兜底 regex `CapitalName+CapitalName`
    //   把 '> 图表说明中的 Toluene Conversion (%)' 误抽为 author[0]
    const content = `[PAGE:1]

> 📊 **图表说明（P1）**
> 图表为热力图，标题为'Toluene Conversion (%)'，展示不同O₃浓度对甲苯转化率影响。

Catalyst-free aqueous-phase oxidation of toluene by ozone
micro-nanobubbles coupled with H2O2 via interfacial reactive oxygen species
Tianzhi Wang a, Hangjia Zhao a, Yongtao Li a
a School of Foo
H I G H L I G H T S`
    const r = extractAuthorsAndJournal(content)
    expect(r.authors.length).toBe(3)
    expect(r.authors[0].name).toBe('Tianzhi Wang')
    expect(r.authors[0].affiliation).toBe('a')
    // 关键 regression check：不误抽 'Toluene Conversion'
    expect(r.authors.find(a => a.name === 'Toluene Conversion')).toBeUndefined()
  })

  it('v28 step 109.38 regression: markdown image alt 中的 CapitalName 不应误抽为作者', () => {
    const content = `[PAGE:1]

![图（P1，Liquid Phase O₃-MNBs Toluene Conversion (%) 99.40）](https://example.com/img.png)

Title Here
John Smith a
a School of Foo
H I G H L I G H T S`
    const r = extractAuthorsAndJournal(content)
    expect(r.authors.length).toBe(1)
    expect(r.authors[0].name).toBe('John Smith')
  })
})

// ============================================================
// v28 step 109.39: paper.abstract 字段走 formatScientificText
//   用户报告：abstract 中 O2•− 等 radical 上下标没渲染正确
//   根因：abstract 字段直接走原文（OCR 字符），没经过 chemFormat 流水线
//   修复：normalizePaperData / _buildPaperFromVisionLayout 末尾对 abstract 调 formatScientificText
// ============================================================

describe('v28 step 109.39: abstract 字段 chemFormat 集成', () => {
  it('PDF id=19 真实 abstract 文本 - O₂⋅⁻/O₃-MNBs/H₂O₂/⋅OH 全部格式化', () => {
    // 真实 OCR 文本（来自 paper 19 /tmp/p19_full.json）
    const rawAbstract = 'A process coupling ozone micro-nanobubbles (O3-MNBs) with H2O2 was developed. The mechanism involves O2⋅⁻-associated pathways and ⋅OH-associated pathways. O3-MNBs and H2O2 both contribute.'
    const raw = {
      id: 19,
      title: 'Test paper',
      content: `[PAGE:1]\nAbstract: ${rawAbstract}\nKeywords: x\n[PAGE:2]\n1 Introduction\ntext`,
      summary: rawAbstract,
      tags: ['test'],
    }
    const paper = normalizePaperData(raw, { images: [], extractions: [], related: [] })
    // 验证 abstract 已格式化
    expect(paper.abstract).toBeTruthy()
    // O3-MNBs 应该是 O₃-MNBs（下标）
    expect(paper.abstract).toContain('O₃-MNBs')
    // H2O2 应该是 H₂O₂
    expect(paper.abstract).toContain('H₂O₂')
    // O2⋅⁻ 应该保持原样（已经是规范 Unicode）
    expect(paper.abstract).toContain('O₂⋅⁻')
    // ⋅OH 归一为 ·OH（v28 step 109.39: 所有 radical 字符归一）
    expect(paper.abstract).toContain('·OH')
    // 不应含原始 O3 / H2O2 / O2
    expect(paper.abstract).not.toMatch(/\bO3-MNBs\b/)
    expect(paper.abstract).not.toMatch(/\bH2O2\b/)
  })

  it('abstract 含 • 字符（OCR 旧 radical）- 归一为 ·', () => {
    const rawAbstract = 'The mechanism involves O2•- and •OH radical pathways.'
    const raw = {
      id: 20,
      title: 'Test',
      content: `[PAGE:1]\nAbstract: ${rawAbstract}\nKeywords: x\n[PAGE:2]\n1 Introduction\ntext`,
      summary: rawAbstract,
    }
    const paper = normalizePaperData(raw, { images: [], extractions: [], related: [] })
    // O2•- 应该被 formatScientificText 处理为 O₂·⁻
    expect(paper.abstract).toContain('O₂·⁻')
    expect(paper.abstract).toContain('·OH')
    // • 不应再出现
    expect(paper.abstract).not.toContain('•')
  })

  it('abstract 含 ⋅ OCR variant - 保持 ⋅', () => {
    const rawAbstract = 'O2⋅- and ⋅OH radical pathways.'
    const raw = {
      id: 21,
      title: 'Test',
      content: `[PAGE:1]\nAbstract: ${rawAbstract}\nKeywords: x\n[PAGE:2]\n1 Introduction\ntext`,
      summary: rawAbstract,
    }
    const paper = normalizePaperData(raw, { images: [], extractions: [], related: [] })
    // O2⋅- 走 formatScientificText → O₂·⁻（- 转 ⁻, 数字变下标）
    expect(paper.abstract).toContain('O₂·⁻')
  })

  it('不破坏 plain text abstract（无化学式）', () => {
    const rawAbstract = 'A novel approach for water treatment without any chemicals.'
    const raw = {
      id: 22,
      title: 'Test',
      content: `[PAGE:1]\nAbstract: ${rawAbstract}\nKeywords: x\n[PAGE:2]\n1 Introduction\ntext`,
      summary: rawAbstract,
    }
    const paper = normalizePaperData(raw, { images: [], extractions: [], related: [] })
    expect(paper.abstract).toBe(rawAbstract)
  })

  it('不破坏中文 abstract', () => {
    const rawAbstract = '本研究开发了一种无需催化剂的臭氧微纳米气泡工艺'
    const raw = {
      id: 23,
      title: '中文测试',
      content: `[PAGE:1]\n摘要：${rawAbstract}\n关键词：x\n[PAGE:2]\n1 引言\ntext`,
      summary: rawAbstract,
    }
    const paper = normalizePaperData(raw, { images: [], extractions: [], related: [] })
    expect(paper.abstract).toBe(rawAbstract)
  })
})
