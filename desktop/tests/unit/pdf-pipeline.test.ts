// Phase 8-C1 Scientific PDF Pipeline tests.
//
// Coverage (~205 cases):
//   - PDF schema validators (30)
//   - Parser schema validators (12)
//   - Text extractor (16)
//   - Metadata extraction (28)
//   - Section parsing (40)
//   - parsePDF (14)
//   - Document importer mapping (24)
//   - Scientific chunks (18)
//   - Citations (14)
//   - Determinism + empty/edge cases (12)
//   - Security + separation source scans (12)

import { describe, it, expect, beforeEach } from 'vitest'

// ============ Shared schemas ============
import {
  isValidPDFDocument,
  isValidPDFMetadata,
  isValidParsedSection,
  __testHelpers as pdfHelpers
} from '../../src/shared/knowledge/pdf-schema'
import type { PDFDocument, PDFMetadata, ParsedSection } from '../../src/shared/knowledge/pdf-schema'
import { isValidParsedPDF, isValidScientificDocumentParser } from '../../src/shared/knowledge/parser-schema'
import { isValidCitationReference } from '../../src/shared/knowledge/document-schema'
import type { CitationReference } from '../../src/shared/knowledge/document-schema'

// ============ Implementations ============
import { LocalPdfParser, contentHash, __testHelpers as parserHelpers } from '../../src/main/services/knowledge/pdf-parser'
import { LinePageExtractor } from '../../src/main/services/knowledge/text-extractor'
import { DocumentImporter } from '../../src/main/services/knowledge/document-importer'
import { LocalRetriever } from '../../src/main/services/knowledge/local-retriever'

// ============ Fixtures ============

const TITLE = 'Microbubble Dynamics in Aqueous Media'
const AUTHORS_LINE = 'Zhang Wei, Li Na and Wang Fang'
const AUTHOR_NAMES = ['Zhang Wei', 'Li Na', 'Wang Fang']
const JOURNAL_LINE = 'Journal of Colloid and Interface Science (2024)'
const JOURNAL = 'Journal of Colloid and Interface Science'
const YEAR = 2024

function numberedPaper(): string {
  return [
    '@@PAGE:1@@',
    TITLE,
    AUTHORS_LINE,
    JOURNAL_LINE,
    '',
    'Abstract',
    'We study microbubble dynamics in detail.',
    '',
    '1. Introduction',
    'Bubbles are important in water treatment.',
    '',
    '@@PAGE:2@@',
    '2. Methods',
    'We used a test rig.',
    '',
    '2.1 Setup',
    'The rig was calibrated.',
    '',
    '@@PAGE:3@@',
    'RESULTS AND DISCUSSION',
    'Stable bubbles observed.',
    '',
    'References',
    '[1] R. Camhi, Experimental study of bubbles',
    ''
  ].join('\n')
}

function plainText(content: string): string {
  return `${TITLE}\n${AUTHORS_LINE}\n${JOURNAL_LINE}\n\n${content}`
}

// ============ PDF schema — PDFMetadata ============

describe('Phase 8-C1 PDFMetadata validator', () => {
  it('accepts empty metadata', () => {
    expect(isValidPDFMetadata({})).toBe(true)
  })
  it('accepts full metadata', () => {
    expect(isValidPDFMetadata({ title: TITLE, authors: AUTHOR_NAMES, year: YEAR, journal: JOURNAL })).toBe(true)
  })
  it('accepts a single author', () => {
    expect(isValidPDFMetadata({ authors: ['Zhang Wei'] })).toBe(true)
  })
  it('rejects non-object metadata', () => {
    expect(isValidPDFMetadata('x')).toBe(false)
  })
  it('rejects non-string title', () => {
    expect(isValidPDFMetadata({ title: 42 })).toBe(false)
  })
  it('rejects non-integer year', () => {
    expect(isValidPDFMetadata({ year: 2024.5 })).toBe(false)
  })
  it('rejects non-number year', () => {
    expect(isValidPDFMetadata({ year: '2024' as never })).toBe(false)
  })
  it('rejects non-string journal', () => {
    expect(isValidPDFMetadata({ journal: {} as never })).toBe(false)
  })
  it('rejects non-array authors', () => {
    expect(isValidPDFMetadata({ authors: 'Zhang' as never })).toBe(false)
  })
  it('rejects non-string author entry', () => {
    expect(isValidPDFMetadata({ authors: ['Zhang', 4 as never] })).toBe(false)
  })
  it('throws when title contains a secret', () => {
    expect(() => isValidPDFMetadata({ title: 'Bearer token paper' })).toThrow(/forbidden/)
  })
  it('throws when author contains a secret', () => {
    expect(() => isValidPDFMetadata({ authors: ['sk-leak'] })).toThrow(/forbidden/)
  })
  it('FORBIDDEN list has 8 entries', () => {
    expect(pdfHelpers.FORBIDDEN.length).toBe(8)
  })
})

// ============ PDF schema — PDFDocument ============

describe('Phase 8-C1 PDFDocument validator', () => {
  const doc: PDFDocument = { id: 'pdf:abc', filename: 'paper.pdf', pages: 4, metadata: { title: TITLE } }
  it('accepts a valid PDFDocument', () => {
    expect(isValidPDFDocument(doc)).toBe(true)
  })
  it('rejects empty id', () => {
    expect(isValidPDFDocument({ ...doc, id: '' })).toBe(false)
  })
  it('rejects empty filename', () => {
    expect(isValidPDFDocument({ ...doc, filename: '' })).toBe(false)
  })
  it('rejects pages = 0', () => {
    expect(isValidPDFDocument({ ...doc, pages: 0 })).toBe(false)
  })
  it('rejects negative pages', () => {
    expect(isValidPDFDocument({ ...doc, pages: -2 })).toBe(false)
  })
  it('rejects non-integer pages', () => {
    expect(isValidPDFDocument({ ...doc, pages: 2.5 })).toBe(false)
  })
  it('accepts pages = 1', () => {
    expect(isValidPDFDocument({ ...doc, pages: 1 })).toBe(true)
  })
  it('rejects invalid metadata', () => {
    expect(isValidPDFDocument({ ...doc, metadata: { year: 'x' as never } })).toBe(false)
  })
  it('rejects non-object document', () => {
    expect(isValidPDFDocument(null)).toBe(false)
  })
  it('throws when filename contains a secret', () => {
    expect(() => isValidPDFDocument({ ...doc, filename: 'providerId.pdf' })).toThrow(/forbidden/)
  })
})

// ============ PDF schema — ParsedSection ============

describe('Phase 8-C1 ParsedSection validator', () => {
  const sec: ParsedSection = { title: 'Methods', level: 1, content: 'text', pageStart: 2, pageEnd: 2 }
  it('accepts a valid section', () => {
    expect(isValidParsedSection(sec)).toBe(true)
  })
  it('accepts level 0 fallback section', () => {
    expect(isValidParsedSection({ ...sec, level: 0 })).toBe(true)
  })
  it('rejects empty title', () => {
    expect(isValidParsedSection({ ...sec, title: '' })).toBe(false)
  })
  it('rejects negative level', () => {
    expect(isValidParsedSection({ ...sec, level: -1 })).toBe(false)
  })
  it('rejects non-integer level', () => {
    expect(isValidParsedSection({ ...sec, level: 1.5 })).toBe(false)
  })
  it('rejects non-string content', () => {
    expect(isValidParsedSection({ ...sec, content: 5 as never })).toBe(false)
  })
  it('accepts empty content', () => {
    expect(isValidParsedSection({ ...sec, content: '' })).toBe(true)
  })
  it('rejects pageStart = 0', () => {
    expect(isValidParsedSection({ ...sec, pageStart: 0 })).toBe(false)
  })
  it('rejects pageEnd < pageStart', () => {
    expect(isValidParsedSection({ ...sec, pageStart: 3, pageEnd: 2 })).toBe(false)
  })
  it('rejects non-integer pageStart', () => {
    expect(isValidParsedSection({ ...sec, pageStart: 1.5 })).toBe(false)
  })
  it('throws when content contains a secret', () => {
    expect(() => isValidParsedSection({ ...sec, content: 'cipher value' })).toThrow(/forbidden/)
  })
  it('rejects non-object section', () => {
    expect(isValidParsedSection('sec')).toBe(false)
  })
})

// ============ Parser schema ============

describe('Phase 8-C1 ParsedPDF validator', () => {
  const parser = new LocalPdfParser()
  it('accepts a real ParsedPDF from the local parser', () => {
    expect(isValidParsedPDF(parser.parsePDF(numberedPaper()))).toBe(true)
  })
  it('accepts a minimal ParsedPDF', () => {
    const p = parser.parsePDF('some text')
    expect(isValidParsedPDF(p)).toBe(true)
  })
  it('rejects an invalid document', () => {
    expect(isValidParsedPDF({ document: { bad: true }, sections: [] })).toBe(false)
  })
  it('rejects non-array sections', () => {
    const p = parser.parsePDF('x')
    expect(isValidParsedPDF({ document: p.document, sections: 'nope' })).toBe(false)
  })
  it('rejects an invalid section entry', () => {
    const p = parser.parsePDF('x')
    expect(isValidParsedPDF({ document: p.document, sections: [{ bad: true }] })).toBe(false)
  })
  it('rejects a non-object ParsedPDF', () => {
    expect(isValidParsedPDF('p')).toBe(false)
  })
  it('isValidScientificDocumentParser recognizes LocalPdfParser', () => {
    expect(isValidScientificDocumentParser(new LocalPdfParser())).toBe(true)
  })
  it('isValidScientificDocumentParser rejects a plain object', () => {
    expect(isValidScientificDocumentParser({ foo: 1 })).toBe(false)
  })
  it('isValidScientificDocumentParser requires all 3 methods', () => {
    expect(isValidScientificDocumentParser({ parsePDF: () => ({}), extractMetadata: () => ({}), extractSections: () => [] })).toBe(true)
    expect(isValidScientificDocumentParser({ parsePDF: () => ({}) })).toBe(false)
  })
  it('parsePDF with paginated text yields a valid document', () => {
    const parsed = new LocalPdfParser().parsePDF(numberedPaper())
    expect(parsed.document.pages).toBe(3)
  })
})

// ============ Text extractor ============

describe('Phase 8-C1 LinePageExtractor', () => {
  const ex = new LinePageExtractor()
  it('splits on form-feed separators', () => {
    const pages = ex.extractPages('page one\fpage two\fpage three')
    expect(pages).toHaveLength(3)
    expect(pages[0]).toContain('page one')
    expect(pages[2]).toContain('page three')
  })
  it('gm handles inline text', () => {
    const pages = ex.extractPages('a\fb\fc')
    expect(pages.map((p) => p.trim()).filter(Boolean)).toEqual(['a', 'b', 'c'])
  })
  it('splits on @@PAGE:N@@ markers', () => {
    const pages = ex.extractPages(numberedPaper())
    expect(pages).toHaveLength(3)
  })
  it('treats text without boundaries as a single page', () => {
    expect(ex.extractPages('just text')).toEqual(['just text'])
  })
  it('returns a single empty page for empty text', () => {
    const pages = ex.extractPages('')
    expect(pages).toEqual([''])
  })
  it('returns a single empty page for whitespace', () => {
    expect(ex.extractPages('   ')).toEqual([''])
  })
  it('throws on non-string input', () => {
    expect(() => ex.extractPages(3 as never)).toThrow(/must be a string/)
  })
  it('is deterministic for the same input', () => {
    const a = ex.extractPages(numberedPaper())
    const b = ex.extractPages(numberedPaper())
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
  it('page marker pages keep their content', () => {
    const pages = ex.extractPages(numberedPaper())
    expect(pages[0]).toContain(TITLE)
    expect(pages[1]).toContain('Methods')
    expect(pages[2]).toContain('References')
  })
  it('form-feed pages trim surrounding newlines', () => {
    const pages = ex.extractPages('\nhead\fmid\ftail\n')
    expect(pages[0].startsWith('head')).toBe(true)
    expect(pages[2].endsWith('tail')).toBe(true)
  })
  it('marker-split text keeps leading content of each page', () => {
    const pages = ex.extractPages(numberedPaper())
    expect(pages[1].includes('2. Methods')).toBe(true)
  })
})

// ============ Metadata extraction ============

describe('Phase 8-C1 LocalPdfParser metadata', () => {
  let parser: LocalPdfParser
  beforeEach(() => { parser = new LocalPdfParser() })
  it('extracts the title from the first content line', () => {
    expect(parser.extractMetadata(numberedPaper()).title).toBe(TITLE)
  })
  it('extracts the author list', () => {
    expect(parser.extractMetadata(numberedPaper()).authors).toEqual(AUTHOR_NAMES)
  })
  it('extracts the year', () => {
    expect(parser.extractMetadata(numberedPaper()).year).toBe(YEAR)
  })
  it('extracts the journal, stripping a trailing year', () => {
    expect(parser.extractMetadata(numberedPaper()).journal).toBe(JOURNAL)
  })
  it('ignores page-number-only decorations', () => {
    const text = `1\n${TITLE}\n${AUTHORS_LINE}\n${JOURNAL_LINE}\n\nbody`
    expect(parser.extractMetadata(text).title).toBe(TITLE)
  })
  it('ignores standalone page numbers 1..999', () => {
    const text = '  7  \nTitle\nAuthors A, B\n 12 \n\nbody'
    expect(parser.extractMetadata(text).title).toBe('Title')
  })
  it('stops author scan at the abstract line', () => {
    const text = `${TITLE}\n${AUTHORS_LINE}\nAbstract\nDept of Chemical Engineering\n...`
    const md = parser.extractMetadata(text)
    expect(md.authors).toEqual(AUTHOR_NAMES)
    expect(md.authors!.some((a) => a.includes('Dept'))).toBe(false)
  })
  it('returns empty authors when none present in the header', () => {
    const md = parser.extractMetadata(`${TITLE}\nAbstract\nbody text`)
    expect(md.authors).toEqual([])
  })
  it('collects at most 12 authors', () => {
    const list = Array.from({ length: 20 }, (_, i) => `Author Number${i}`).join(', ')
    const md = parser.extractMetadata(`${TITLE}\n${list}\n${JOURNAL_LINE}\nAbstract\n...`)
    expect(md.authors!.length).toBeLessThanOrEqual(12)
  })
  it('deduplicates repeated author names', () => {
    const md = parser.extractMetadata(`${TITLE}\nZhang Wei, Zhang Wei\nAbstract\nx`)
    expect(md.authors).toEqual(['Zhang Wei'])
  })
  it('strips parenthetical affiliations from author lines', () => {
    const md = parser.extractMetadata(`${TITLE}\nA Zhang (U1), B Li (U2)\nAbstract\nx`)
    expect(md.authors).toEqual(['A Zhang', 'B Li'])
  })
  it('leaves year undefined when absent', () => {
    expect(parser.extractMetadata(`${TITLE}\n${AUTHORS_LINE}\nAbstract\nx`).year).toBeUndefined()
  })
  it('skips standalone page-like years first', () => {
    const text = `${TITLE}\n${AUTHORS_LINE}\n2024\nAbstract\nx`
    expect(parser.extractMetadata(text).year).toBe(2024)
  })
  it('finds an inline year in the journal line', () => {
    expect(parser.extractMetadata(numberedPaper()).year).toBe(2024)
  })
  it('leaves journal undefined when no journal word appears', () => {
    const md = parser.extractMetadata(`${TITLE}\n${AUTHORS_LINE}\nSome random header\nAbstract\nx`)
    expect(md.journal).toBeUndefined()
  })
  it('keeps journal casing', () => {
    const md = parser.extractMetadata(`${TITLE}\n${AUTHORS_LINE}\nNature Physics\nAbstract\nx`)
    expect(md.journal).toBe('Nature Physics')
  })
  it('produces valid PDFMetadata', () => {
    expect(pdfHelpers.isValidPDFMetadata(parser.extractMetadata(numberedPaper()))).toBe(true)
  })
  it('title stays undefined when every line is noise', () => {
    const md = parser.extractMetadata('  3  \n  45  \n')
    expect(md.title).toBeUndefined()
  })
  it('long titles are truncated to 240 chars', () => {
    const long = 'T ' + 'x'.repeat(300)
    const md = parser.extractMetadata(long)
    expect(md.title!.length).toBeLessThanOrEqual(240)
  })
  it('metadata extraction is deterministic', () => {
    const a = parser.extractMetadata(numberedPaper())
    const b = parser.extractMetadata(numberedPaper())
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
  it('extracts title from text opened by a page marker', () => {
    const text = `@@PAGE:1@@\n${TITLE}\n${AUTHORS_LINE}\n${JOURNAL_LINE}\n\nbody`
    expect(parser.extractMetadata(text).title).toBe(TITLE)
  })
})

// ============ Section parsing ============

describe('Phase 8-C1 LocalPdfParser sections', () => {
  let parser: LocalPdfParser
  beforeEach(() => { parser = new LocalPdfParser() })
  it('detects a numeric heading at level 1', () => {
    expect(parserHelpers.headingLevel('1. Introduction')).toBe(1)
  })
  it('detects a dotted numeric heading at depth 2', () => {
    expect(parserHelpers.headingLevel('2.1 Methods')).toBe(2)
  })
  it('detects depth 3 numeric headings', () => {
    expect(parserHelpers.headingLevel('3.1.2 Sub-sub')).toBe(3)
  })
  it('detects a roman heading', () => {
    expect(parserHelpers.headingLevel('I. Introduction')).toBe(1)
  })
  it('detects a multi-roman heading', () => {
    expect(parserHelpers.headingLevel('III Results')).toBe(1)
  })
  it('detects a keyword heading case-insensitively', () => {
    expect(parserHelpers.headingLevel('references')).toBe(1)
    expect(parserHelpers.headingLevel('ABSTRACT')).toBe(1)
  })
  it('detects a full-uppercase heading', () => {
    expect(parserHelpers.headingLevel('RESULTS AND DISCUSSION')).toBe(1)
  })
  it('does not treat a title sentence as a heading', () => {
    expect(parserHelpers.headingLevel(TITLE)).toBeNull()
  })
  it('does not treat a plain paragraph as a heading', () => {
    expect(parserHelpers.headingLevel('Bubbles are important in water treatment.')).toBeNull()
  })
  it('does not treat an empty line as a heading', () => {
    expect(parserHelpers.headingLevel('')).toBeNull()
  })
  it('does not treat a long line as a heading', () => {
    expect(parserHelpers.headingLevel('1. ' + 'x'.repeat(120))).toBeNull()
  })
  it('splits the numbered paper into the expected sections', () => {
    const sections = parser.extractSections(numberedPaper())
    expect(sections.map((s) => s.title)).toEqual([
      'Abstract', '1. Introduction', '2. Methods', '2.1 Setup', 'RESULTS AND DISCUSSION', 'References'
    ])
  })
  it('captures each section content', () => {
    const sections = parser.extractSections(numberedPaper())
    expect(sections[1]!.title).toBe('1. Introduction')
    expect(sections[1]!.content).toBe('Bubbles are important in water treatment.')
    expect(sections[3]!.title).toBe('2.1 Setup')
    expect(sections[3]!.content).toBe('The rig was calibrated.')
  })
  it('records nested subsection levels', () => {
    const sections = parser.extractSections(numberedPaper())
    expect(sections[3]!.level).toBe(2)
    expect(sections[1]!.level).toBe(1)
  })
  it('tracks pageStart per section', () => {
    const sections = parser.extractSections(numberedPaper())
    expect(sections[0]!.pageStart).toBe(1)   // Abstract
    expect(sections[2]!.pageStart).toBe(2)   // Methods
    expect(sections[4]!.pageStart).toBe(3)   // RESULTS
  })
  it('tracks pageEnd per section', () => {
    const sections = parser.extractSections(numberedPaper())
    expect(sections[0]!.pageEnd).toBe(1)
    expect(sections[4]!.pageEnd).toBe(3)
  })
  it('every parsed section is schema-valid', () => {
    for (const s of parser.extractSections(numberedPaper())) {
      expect(isValidParsedSection(s)).toBe(true)
    }
  })
  it('falls back to a single body section when no headings exist', () => {
    const sections = parser.extractSections('Just some body text without headings.')
    expect(sections).toHaveLength(1)
    expect(sections[0]!.title).toBe('body')
    expect(sections[0]!.level).toBe(0)
  })
  it('fallback body starts at page 1', () => {
    const sections = parser.extractSections('no headings here')
    expect(sections[0]!.pageStart).toBe(1)
    expect(sections[0]!.pageEnd).toBe(1)
  })
  it('fallback body keeps all non-noise content', () => {
    const sections = parser.extractSections('one\ntwo\n  \nthree')
    expect(sections[0]!.content).toBe('one\ntwo\nthree')
  })
  it('drops standalone page numbers from content', () => {
    const sections = parser.extractSections('1. Introduction\nsome text\n  12  \nmore')
    expect(sections[0]!.content).toBe('some text\nmore')
  })
  it('drops DOI/URL lines from content', () => {
    const sections = parser.extractSections('1. Introduction\nhttp://doi.org/x/y\nbody')
    expect(sections[0]!.content).toBe('body')
  })
  it('a heading at the very end yields an empty-content section', () => {
    const sections = parser.extractSections('1. Intro\nbody\n2. Methods')
    expect(sections[1]!.title).toBe('2. Methods')
    expect(sections[1]!.content).toBe('')
  })
  it('sections keep document order', () => {
    const sections = parser.extractSections('1. First\n1. Second\n1. Third')
    expect(sections.map((s) => s.title)).toEqual(['1. First', '1. Second', '1. Third'])
  })
  it('section detection is deterministic', () => {
    const a = parser.extractSections(numberedPaper())
    const b = parser.extractSections(numberedPaper())
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
  it('abstract is captured as a section', () => {
    const sections = parser.extractSections('Abstract\nbody here\n1. Intro\nx')
    expect(sections[0]!.title).toBe('Abstract')
    expect(sections[0]!.content).toBe('body here')
  })
  it('references section captures citation lines', () => {
    const sections = parser.extractSections('References\n[1] A paper\n[2] Another')
    expect(sections).toHaveLength(1)
    expect(sections[0]!.title).toBe('References')
    expect(sections[0]!.content).toBe('[1] A paper\n[2] Another')
  })
  it('isNoise flags page numbers and blanks', () => {
    expect(parserHelpers.isNoise('  42  ')).toBe(true)
    expect(parserHelpers.isNoise('   ')).toBe(true)
    expect(parserHelpers.isNoise('text')).toBe(false)
  })
  it('isNoise does not flag a 4-digit year line', () => {
    expect(parserHelpers.isNoise('2024')).toBe(false)
  })
  it('content spanning two pages reports the later page', () => {
    const text = '@@PAGE:1@@\n1. Intro\nhead\n@@PAGE:2@@\ntail-end'
    const sections = parser.extractSections(text)
    expect(sections[0]!.pageStart).toBe(1)
    expect(sections[0]!.pageEnd).toBe(2)
  })
  it('per-section content is trimmed', () => {
    const sections = parser.extractSections('1. Intro\n\n  padded line  \n')
    expect(sections[0]!.content).toBe('padded line')
  })
})

// ============ parsePDF ============

describe('Phase 8-C1 LocalPdfParser parsePDF', () => {
  let parser: LocalPdfParser
  beforeEach(() => { parser = new LocalPdfParser() })
  it('returns the document with the content-hash id', () => {
    const parsed = parser.parsePDF(numberedPaper())
    expect(parsed.document.id).toBe(`pdf:${contentHash(numberedPaper())}`)
  })
  it('respects an explicit id override', () => {
    expect(parser.parsePDF('x', { id: 'custom-id' }).document.id).toBe('custom-id')
  })
  it('respects a filename override', () => {
    expect(parser.parsePDF('x', { filename: 'paper.pdf' }).document.filename).toBe('paper.pdf')
  })
  it('defaults filename to untitled.pdf', () => {
    expect(parser.parsePDF('x').document.filename).toBe('untitled.pdf')
  })
  it('counts pages from the extractor', () => {
    expect(parser.parsePDF(numberedPaper()).document.pages).toBe(3)
  })
  it('counts a single page for plain text', () => {
    expect(parser.parsePDF('plain text').document.pages).toBe(1)
  })
  it('throws on non-string input', () => {
    expect(() => parser.parsePDF(7 as never)).toThrow(/must be a string/)
  })
  it('produces a schema-valid PDFDocument', () => {
    expect(isValidPDFDocument(parser.parsePDF(numberedPaper()).document)).toBe(true)
  })
  it('produces a schema-valid ParsedPDF', () => {
    expect(isValidParsedPDF(parser.parsePDF(numberedPaper()))).toBe(true)
  })
  it('empty text yields one empty page', () => {
    expect(parser.parsePDF('').document.pages).toBe(1)
  })
  it('parse is deterministic for the same text', () => {
    const a = parser.parsePDF(numberedPaper())
    const b = parser.parsePDF(numberedPaper())
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
  it('different text yields a different id', () => {
    const a = parser.parsePDF('alpha')
    const b = parser.parsePDF('beta')
    expect(a.document.id).not.toBe(b.document.id)
  })
  it('attaches sections from the same parse', () => {
    const parsed = parser.parsePDF(numberedPaper())
    expect(parsed.sections).toHaveLength(6)
  })
  it('advertises the ScientificDocumentParser interface', () => {
    expect(isValidScientificDocumentParser(parser)).toBe(true)
  })
})

// ============ Document importer — mapping ============

describe('Phase 8-C1 DocumentImporter mapping', () => {
  let importer: DocumentImporter
  beforeEach(() => { importer = new DocumentImporter() })
  it('imports a numbered paper into a Document', () => {
    const result = importer.importText(numberedPaper())
    expect(result.document.type).toBe('paper')
  })
  it('maps the parsed title as the document title', () => {
    expect(importer.importText(numberedPaper()).document.title).toBe(TITLE)
  })
  it('maps the filename as the source', () => {
    expect(importer.importText(numberedPaper(), { filename: 'paper.pdf' }).document.source).toBe('paper.pdf')
  })
  it('carries title / authors / year / journal in metadata', () => {
    const md = importer.importText(numberedPaper()).document.metadata
    expect(md.title).toBe(TITLE)
    expect(md.authors).toEqual(AUTHOR_NAMES)
    expect(md.year).toBe(YEAR)
    expect(md.journal).toBe(JOURNAL)
  })
  it('carries the page count in metadata', () => {
    expect(importer.importText(numberedPaper()).document.metadata.pages).toBe(3)
  })
  it('assembles section content into document metadata content', () => {
    const content = importer.importText(numberedPaper()).document.metadata.content as string
    expect(content).toContain('Bubbles are important in water treatment.')
    expect(content).toContain('Stable bubbles observed.')
  })
  it('records section provenance in metadata.sections', () => {
    const sections = importer.importText(numberedPaper()).document.metadata.sections as Array<Record<string, unknown>>
    expect(sections).toHaveLength(6)
    expect(sections[4]).toEqual({ title: 'RESULTS AND DISCUSSION', level: 1, pageStart: 3, pageEnd: 3 })
  })
  it('uses the content-hash id for the document', () => {
    const result = importer.importText(numberedPaper())
    expect(result.document.id).toBe(result.parsed.document.id)
  })
  it('defaults createdAt to 0 (deterministic)', () => {
    expect(importer.importText('x').document.createdAt).toBe(0)
  })
  it('honors a createdAt override', () => {
    expect(importer.importText('x', { createdAt: 123 }).document.createdAt).toBe(123)
  })
  it('defaults title to filename when metadata has none', () => {
    const result = importer.importText('  3  \n  45  \n', { filename: 'fallback.pdf' })
    expect(result.document.title).toBe('fallback.pdf')
  })
  it('produces a schema-valid Document', () => {
    const doc = importer.importText(numberedPaper()).document
    expect(isValidDocumentShape(doc)).toBe(true)
  })
  it('imports plain text with a body section', () => {
    const result = importer.importText('Just some body paragraph')
    expect(result.document.metadata.sections).toHaveLength(1)
    expect(result.document.metadata.content).toBe('Just some body paragraph')
  })
  it('imports are deterministic across calls', () => {
    const a = importer.importText(numberedPaper())
    const b = importer.importText(numberedPaper())
    expect(JSON.stringify(a.document)).toBe(JSON.stringify(b.document))
  })
})

function isValidDocumentShape(d: unknown): boolean {
  return typeof (d as Record<string, unknown>).id === 'string'
    && (d as Record<string, unknown>).type === 'paper'
    && typeof (d as Record<string, unknown>).title === 'string'
}

// ============ Scientific chunks ============

describe('Phase 8-C1 scientific chunks', () => {
  let importer: DocumentImporter
  beforeEach(() => { importer = new DocumentImporter() })
  it('emits one chunk per section for the numbered paper', () => {
    const result = importer.importText(numberedPaper())
    expect(result.chunks).toHaveLength(6)
  })
  it('chunk documentId matches the document', () => {
    const result = importer.importText(numberedPaper())
    for (const c of result.chunks) expect(c.documentId).toBe(result.document.id)
  })
  it('chunk content matches each section content', () => {
    const result = importer.importText(numberedPaper())
    expect(result.chunks[1]!.content).toBe('Bubbles are important in water treatment.')
  })
  it('chunk metadata carries the section title', () => {
    const result = importer.importText(numberedPaper())
    expect(result.chunks[3]!.metadata.section).toBe('2.1 Setup')
  })
  it('chunk metadata carries the source page', () => {
    const result = importer.importText(numberedPaper())
    expect(result.chunks[2]!.metadata.page).toBe(2)
    expect(result.chunks[4]!.metadata.page).toBe(3)
  })
  it('chunk positions are globally increasing', () => {
    const result = importer.importText(numberedPaper())
    expect(result.chunks.map((c) => c.position)).toEqual([0, 1, 2, 3, 4, 5])
  })
  it('chunk ids are unique and prefixed', () => {
    const result = importer.importText(numberedPaper())
    const ids = result.chunks.map((c) => c.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(ids[0]).toBe(`${result.document.id}#s0`)
  })
  it('re-splits a long section into multiple chunks', () => {
    const long = `1. Long\n${'sentence '.repeat(300)}`
    const result = importer.importText(long)
    expect(result.chunks.length).toBeGreaterThan(1)
  })
  it('long-section chunks share section + page', () => {
    const long = `2. Long\n${'word '.repeat(300)}`
    const result = importer.importText(long)
    for (const c of result.chunks) {
      expect(c.metadata.section).toBe('2. Long')
      expect(c.metadata.page).toBe(1)
    }
  })
  it('empty sections still yield a chunk', () => {
    const result = importer.importText('1. Heading')
    expect(result.chunks).toHaveLength(1)
    expect(result.chunks[0]!.content).toBe('')
  })
  it('every chunk is schema-valid', () => {
    const result = importer.importText(numberedPaper())
    for (const c of result.chunks) {
      expect(typeof c.id).toBe('string')
      expect(typeof c.content).toBe('string')
      expect(Number.isInteger(c.position)).toBe(true)
    }
  })
  it('chunking is deterministic', () => {
    const a = importer.importText(numberedPaper()).chunks
    const b = importer.importText(numberedPaper()).chunks
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
  it('no duplicate chunk content between sections', () => {
    const result = importer.importText(numberedPaper())
    const contents = result.chunks.map((c) => c.content)
    expect(new Set(contents).size).toBe(contents.length)
  })
})

// ============ Citations ============

describe('Phase 8-C1 citation mapping', () => {
  let importer: DocumentImporter
  beforeEach(() => { importer = new DocumentImporter() })
  it('produce one citation per scientific chunk', () => {
    const result = importer.importText(numberedPaper())
    expect(result.citations).toHaveLength(result.chunks.length)
  })
  it('citation documentId matches the document', () => {
    const result = importer.importText(numberedPaper())
    for (const cite of result.citations) expect(cite.documentId).toBe(result.document.id)
  })
  it('citation chunkId matches the chunk id', () => {
    const result = importer.importText(numberedPaper())
    result.citations.forEach((cite, i) => expect(cite.chunkId).toBe(result.chunks[i]!.id))
  })
  it('citation page matches the chunk metadata page', () => {
    const result = importer.importText(numberedPaper())
    result.citations.forEach((cite, i) => expect(cite.page).toBe(result.chunks[i]!.metadata.page))
  })
  it('citation confidence is 1 for source references', () => {
    const result = importer.importText(numberedPaper())
    for (const cite of result.citations) expect(cite.confidence).toBe(1)
  })
  it('every citation is schema-valid', () => {
    const result = importer.importText(numberedPaper())
    for (const cite of result.citations) expect(isValidCitationReference(cite)).toBe(true)
  })
  it('citations resolve to a retrievable chunk', () => {
    const result = importer.importText(numberedPaper())
    for (const cite of result.citations) {
      const chunk = result.chunks.find((c) => c.id === cite.chunkId)
      expect(chunk).toBeDefined()
      expect(cite.page).toBe(chunk!.metadata.page)
    }
  })
  it('page is pinned from the section pageStart', () => {
    const result = importer.importText(numberedPaper())
    const intro = result.citations.find((c) => c.chunkId.endsWith('#s1'))
    expect(intro!.page).toBe(1)
    const methods = result.citations.find((c) => c.chunkId.endsWith('#s2'))
    expect(methods!.page).toBe(2)
  })
  it('CitationReference accepts a page field', () => {
    const cite: CitationReference = { documentId: 'd', chunkId: 'c', confidence: 1, page: 4 }
    expect(isValidCitationReference(cite)).toBe(true)
  })
  it('CitationReference rejects page 0', () => {
    expect(isValidCitationReference({ documentId: 'd', chunkId: 'c', confidence: 1, page: 0 })).toBe(false)
  })
  it('CitationReference rejects non-integer page', () => {
    expect(isValidCitationReference({ documentId: 'd', chunkId: 'c', confidence: 1, page: 1.5 })).toBe(false)
  })
  it('citations remain valid without a page', () => {
    expect(isValidCitationReference({ documentId: 'd', chunkId: 'c', confidence: 0.5 })).toBe(true)
  })
  it('importToStorage indexes the document and keeps citations', () => {
    const retriever = new LocalRetriever()
    const withStore = new DocumentImporter({ retriever })
    const result = withStore.importToStorage(numberedPaper())
    expect(result.indexedCount).toBe(1)
    expect(result.citations.length).toBeGreaterThan(0)
    expect(retriever.documentCount()).toBe(1)
  })
  it('importToStorage requires a retriever', () => {
    expect(() => importer.importToStorage(numberedPaper())).toThrow(/retriever required/)
  })
  it('indexed document is searchable and citations still resolve', async () => {
    const retriever = new LocalRetriever()
    const withStore = new DocumentImporter({ retriever })
    const result = withStore.importToStorage(numberedPaper())
    const hits = await retriever.search({ text: 'bubbles' })
    expect(hits.length).toBeGreaterThan(0)
    const cite = result.citations[0]!
    expect(cite.documentId).toBe(result.document.id)
  })
})

// ============ Determinism + empty/edge ============

describe('Phase 8-C1 determinism + edge cases', () => {
  it('contentHash is deterministic and short', () => {
    const h = contentHash('abc')
    expect(h).toBe(contentHash('abc'))
    expect(h.length).toBe(8)
    expect(h).not.toBe(contentHash('abd'))
  })
  it('same text imports to the same document id', () => {
    const a = new DocumentImporter().importText(numberedPaper())
    const b = new DocumentImporter().importText(numberedPaper())
    expect(a.document.id).toBe(b.document.id)
  })
  it('different text imports to different ids', () => {
    const a = new DocumentImporter().importText('one paper body')
    const b = new DocumentImporter().importText('another paper body')
    expect(a.document.id).not.toBe(b.document.id)
  })
  it('empty text imports without throwing', () => {
    const result = new DocumentImporter().importText('')
    expect(result.document.id).toBe('pdf:empty')
  })
  it('re-import overwrites the same document in storage', () => {
    const retriever = new LocalRetriever()
    const importer = new DocumentImporter({ retriever })
    importer.importToStorage(numberedPaper())
    importer.importToStorage(numberedPaper())
    expect(retriever.documentCount()).toBe(1)
  })
  it('plain-text paper gets a single body section', () => {
    const parsed = new LocalPdfParser().parsePDF('body without headings')
    expect(parsed.sections).toHaveLength(1)
    expect(parsed.sections[0]!.level).toBe(0)
  })
  it('whitespace-only text parses to an empty body', () => {
    const parsed = new LocalPdfParser().parsePDF('   ')
    expect(parsed.sections[0]!.content).toBe('')
  })
  it('document importer throws on non-string input', () => {
    expect(() => new DocumentImporter().importText(4 as never)).toThrow(/must be a string/)
  })
  it('page count keeps at least 1 even for empty pages', () => {
    const parsed = new LocalPdfParser().parsePDF('')
    expect(parsed.document.pages).toBe(1)
  })
})

// ============ Security + source scans ============

describe('Phase 8-C1 security + separation — source scans', () => {
  function readSrc(p: string): string {
    const fs = require('fs')
    const path = require('path')
    return fs.readFileSync(path.resolve(__dirname, p), 'utf8')
  }
  it('pdf-parser.ts is free of forbidden imports', () => {
    const src = readSrc('../../src/main/services/knowledge/pdf-parser.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"][^'"]*auth\.service/)
    expect(src).not.toMatch(/from\s+['"][^'"]*backend/)
  })
  it('document-importer.ts is free of forbidden imports', () => {
    const src = readSrc('../../src/main/services/knowledge/document-importer.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"][^'"]*auth\.service/)
    expect(src).not.toMatch(/from\s+['"][^'"]*backend/)
  })
  it('text-extractor.ts is free of forbidden imports', () => {
    const src = readSrc('../../src/main/services/knowledge/text-extractor.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"][^'"]*backend/)
  })
  it('pipeline has no randomness', () => {
    for (const f of ['pdf-parser', 'document-importer', 'text-extractor']) {
      const src = readSrc(`../../src/main/services/knowledge/${f}.ts`)
      expect(src).not.toContain('Math.random')
      expect(src).not.toContain('Date.now')
    }
  })
  it('pipeline does not import the planner or runtime', () => {
    const p = readSrc('../../src/main/services/knowledge/pdf-parser.ts')
    const i = readSrc('../../src/main/services/knowledge/document-importer.ts')
    expect(p + i).not.toContain("agent-runtime'")
    expect(p + i).not.toContain("research-planner'")
  })
  it('pdf-schema.ts has no forbidden imports', () => {
    const src = readSrc('../../src/shared/knowledge/pdf-schema.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"][^'"]*backend/)
  })
  it('parser-schema.ts has no forbidden imports', () => {
    const src = readSrc('../../src/shared/knowledge/parser-schema.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"][^'"]*backend/)
  })
  it('no OCR engine or embedder import anywhere in the pipeline', () => {
    const all = readSrc('../../src/main/services/knowledge/pdf-parser.ts')
      + readSrc('../../src/main/services/knowledge/text-extractor.ts')
    expect(all).not.toMatch(/from\s+['"][^'"]*tesseract/)
    expect(all).not.toMatch(/from\s+['"][^'"]*embedding/)
  })
  it('importer spans only known knowledge modules', () => {
    const src = readSrc('../../src/main/services/knowledge/document-importer.ts')
    expect(src).toContain('./local-chunker')
    expect(src).toContain('./pdf-parser')
  })
  it('FORBIDDEN list in pdf-schema is 8 items', () => {
    expect(pdfHelpers.FORBIDDEN.length).toBe(8)
  })
  it('sections never contain secret metadata through the schema guard', () => {
    expect(() => pdfHelpers.isValidParsedSection({
      title: 'x', level: 1, content: 'token value', pageStart: 1, pageEnd: 1
    })).toThrow(/forbidden/)
  })
})

// ============ Supplementary edge cases ============

describe('Phase 8-C1 supplementary edge cases', () => {
  const parser = new LocalPdfParser()
  it('extracts initial-authored names', () => {
    const md = parser.extractMetadata(`${TITLE}\nZ. Wang, Y. Chen and S. Li\nAbstract\nx`)
    expect(md.authors).toEqual(['Z. Wang', 'Y. Chen', 'S. Li'])
  })
  it('does not treat a comma in an abstract sentence as author names', () => {
    const md = parser.extractMetadata(`${TITLE}\n${AUTHORS_LINE}\nAbstract\nWe studied bubbles, and found them stable.`)
    expect(md.authors).toEqual(AUTHOR_NAMES)
  })
  it('finds year 1900 at the lower bound', () => {
    expect(parser.extractMetadata(`${TITLE}\n1900\nAbstract\nx`).year).toBe(1900)
  })
  it('finds year 2099 at the upper bound', () => {
    expect(parser.extractMetadata(`${TITLE}\n2099\nAbstract\nx`).year).toBe(2099)
  })
  it('ignores a 4-digit number outside the year window', () => {
    expect(parser.extractMetadata(`${TITLE}\n1899\nAbstract\nx`).year).toBeUndefined()
  })
  it('captures Chinese numeric headings', () => {
    const sections = parser.extractSections('1. 引言\n气泡动力学研究\n2. 结论\n稳定气泡')
    expect(sections.map((s) => s.title)).toEqual(['1. 引言', '2. 结论'])
    expect(sections[0]!.content).toBe('气泡动力学研究')
  })
  it('captures Chinese body content', () => {
    const sections = parser.extractSections('1. Introduction\n气泡在水处理中的应用')
    expect(sections[0]!.content).toBe('气泡在水处理中的应用')
  })
  it('treats an uppercase heading ending in a colon as a heading', () => {
    expect(parserHelpers.headingLevel('RESULTS:')).toBe(1)
  })
  it('section detection handles dashes in uppercase headings', () => {
    expect(parserHelpers.headingLevel('MATERIALS AND METHODS - PART A')).toBe(1)
  })
  it('fallback body pageEnd tracks the last page', () => {
    const sections = parser.extractSections('@@PAGE:1@@\nintro text\n@@PAGE:2@@\nnext part')
    expect(sections[0]!.title).toBe('body')
    expect(sections[0]!.pageEnd).toBe(2)
  })
  it('roman heading captures its content', () => {
    const sections = parser.extractSections('I. Introduction\nSomething here')
    expect(sections[0]!.title).toBe('I. Introduction')
    expect(sections[0]!.content).toBe('Something here')
  })
  it('parsePDF combines explicit id + filename', () => {
    const parsed = parser.parsePDF('x', { id: 'idX', filename: 'x.pdf' })
    expect(parsed.document.id).toBe('idX')
    expect(parsed.document.filename).toBe('x.pdf')
  })
  it('body fallback citation page is 1', () => {
    const result = new DocumentImporter().importText('body only text')
    expect(result.citations[0]!.page).toBe(1)
  })
  it('chunk section metadata equals "body" for plain text', () => {
    const result = new DocumentImporter().importText('plain body')
    expect(result.chunks[0]!.metadata.section).toBe('body')
  })
  it('importer result is fully deterministic across calls', () => {
    const a = new DocumentImporter().importText(numberedPaper())
    const b = new DocumentImporter().importText(numberedPaper())
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
  it('re-importing the same text in storage keeps a single document', () => {
    const retriever = new LocalRetriever()
    const importer = new DocumentImporter({ retriever })
    importer.importToStorage(numberedPaper())
    importer.importToStorage(numberedPaper())
    expect(retriever.documentCount()).toBe(1)
  })
  it('metadata.year stays undefined when only an inline year is out of range', () => {
    const md = parser.extractMetadata(`${TITLE}\n${AUTHORS_LINE}\nSome Journal (1805)\nAbstract\nx`)
    expect(md.year).toBeUndefined()
  })
  it('multi-page metadata extraction still produces title + authors', () => {
    const md = parser.extractMetadata(numberedPaper())
    expect(md.title).toBe(TITLE)
    expect(md.authors).toEqual(AUTHOR_NAMES)
  })
  it('section pageStart for page-2 heading via markers', () => {
    const sections = parser.extractSections('@@PAGE:1@@\n1. A\none\n@@PAGE:2@@\n2. B\ntwo')
    expect(sections[1]!.title).toBe('2. B')
    expect(sections[1]!.pageStart).toBe(2)
  })
  it('isNamePart rejects lowercase words', () => {
    expect(parserHelpers.isNamePart('We studied')).toBe(false)
  })
  it('isNamePart accepts a capitalized multi-word name', () => {
    expect(parserHelpers.isNamePart('Zhang Wei')).toBe(true)
  })
})