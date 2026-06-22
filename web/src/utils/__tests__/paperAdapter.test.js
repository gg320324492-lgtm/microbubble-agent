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

  // v28 step 106: vision 后处理 — 合并重复 page_number
  //   vision model 经常把 page 8 输出多次（page 计数不稳定）
  //   paperAdapter 必须按 page_number 去重，合并相同 page 的 blocks
  it('v28 step 106: vision page_number 重复时应合并', () => {
    const visionLayout = {
      has_layout: true,
      total_pages: 9,
      total_blocks: 30,
      page_layout: [
        // page 8 出现 3 次（vision 不稳定）
        {
          page_number: 8,
          blocks: [
            { type: 'heading', level: 1, order: 1, text: '3.4 Anti-interference' },
            { type: 'paragraph', order: 2, text: 'first paragraph on page 8' },
          ],
        },
        {
          page_number: 8,
          blocks: [
            { type: 'paragraph', order: 3, text: 'second paragraph on page 8' },
            { type: 'image', order: 4, image_index: 2, caption: 'Fig. 4. Anti-interference.', figure_no: 'Fig. 4' },
          ],
        },
        {
          page_number: 8,
          blocks: [
            { type: 'image', order: 5, image_index: 2, caption: 'Fig. 4. Anti-interference.', figure_no: 'Fig. 4' },
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
    // 合并后 page 8 只出现 1 次（3 个 blocks 唯一去重）
    const allBlocks = r.sections.flatMap(s => s.blocks)
    const page8Blocks = allBlocks.filter(b => b.page === 8)
    expect(page8Blocks.length).toBe(3)  // heading + 2 paragraphs/images（image_index 重复的去重）
    // 重复 image_index 2 的去重
    const fig4Blocks = allBlocks.filter(b => b.figure_no === 'Fig. 4')
    expect(fig4Blocks.length).toBe(1)
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
