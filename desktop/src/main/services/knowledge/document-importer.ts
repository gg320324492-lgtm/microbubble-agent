// Document Importer (Phase 8-C1: Scientific PDF Document Import Pipeline).
//
// Pipeline:
//   PDF text  →  ScientificDocumentParser  →  Document  →  Chunks  →  Storage (Retriever)
//
// Importer owns the Paper → Document mapping and the scientific (section + page
// aware) chunking used for citations. The retriever keeps its own search chunks;
// the importer's chunks back CitationReference with an exact page.
//
// Phase 8-C1 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - No LLM, no OCR, no embeddings — deterministic
//   - Does NOT import model-provider / auth / backend

import type { Document, DocumentChunk, CitationReference } from '../../../shared/knowledge/document-schema'
import { isValidDocument, isValidDocumentChunk } from '../../../shared/knowledge/document-schema'
import type { ScientificDocumentParser, ParsedPDF } from '../../../shared/knowledge/parser-schema'
import { splitContent } from './local-chunker'
import { LocalPdfParser } from './pdf-parser'

/**
 * Phase 8-C1: the minimal retriever surface the importer needs.
 * LocalRetriever satisfies this structurally; keeps importer decoupled.
 */
export interface RetrieverLike {
  indexDocuments(documents: Document[]): number
  listChunks(documentId: string): DocumentChunk[]
}

export interface ImportTextOptions {
  filename?: string
  id?: string
  /** Seconds epoch override — default 0 keeps the pipeline fully deterministic. */
  createdAt?: number
}

export interface PaperImportResult {
  parsed: ParsedPDF
  document: Document
  /** Scientific (section/page-aware) chunks backing the citations. */
  chunks: DocumentChunk[]
  /** Page-pinned citations for the scientific chunks. */
  citations: CitationReference[]
}

/**
 * Phase 8-C1: Paper → Document mapping using Phase 8-C0 contracts.
 */
export class DocumentImporter {
  private readonly parser: ScientificDocumentParser
  private readonly retriever: RetrieverLike | null

  constructor(options: {
    parser?: ScientificDocumentParser
    retriever?: RetrieverLike
  } = {}) {
    this.parser = options?.parser ?? new LocalPdfParser()
    this.retriever = options?.retriever ?? null
  }

  /** Phase 8-C1: PDF text → ParsedPDF → Document + scientific chunks + citations. */
  importText(text: string, options: ImportTextOptions = {}): PaperImportResult {
    if (typeof text !== 'string') {
      throw new Error('document importer: text must be a string (Phase 8-C1 strict)')
    }
    const parsed = this.parser.parsePDF(text, { id: options.id, filename: options.filename })
    const document = this.toDocument(parsed, options)
    const chunks = this.toScientificChunks(document, parsed)
    const citations: CitationReference[] = chunks.map((c) => ({
      documentId: c.documentId,
      chunkId: c.id,
      page: typeof c.metadata.page === 'number' ? c.metadata.page : 1,
      confidence: 1
    }))
    return { parsed, document, chunks, citations }
  }

  /** Phase 8-C1: import into the retriever (indexes the document for search). */
  importToStorage(text: string, options: ImportTextOptions = {}): PaperImportResult & { indexedCount: number } {
    const result = this.importText(text, options)
    if (!this.retriever) {
      throw new Error('document importer: retriever required for importToStorage (Phase 8-C1 strict)')
    }
    const indexedCount = this.retriever.indexDocuments([result.document])
    return { ...result, indexedCount }
  }

  // ============ Paper → Document mapping ============

  private toDocument(parsed: ParsedPDF, options: ImportTextOptions): Document {
    const md = parsed.document.metadata
    const title = md.title ?? parsed.document.filename
    const document: Document = {
      id: parsed.document.id,
      type: 'paper',
      title,
      source: parsed.document.filename,
      metadata: {
        content: parsed.sections.map((s) => s.content).filter((c) => c.length > 0).join('\n\n'),
        title: md.title,
        authors: md.authors,
        year: md.year,
        journal: md.journal,
        pages: parsed.document.pages,
        sections: parsed.sections.map((s) => ({
          title: s.title,
          level: s.level,
          pageStart: s.pageStart,
          pageEnd: s.pageEnd
        }))
      },
      createdAt: options.createdAt ?? 0
    }
    if (!isValidDocument(document)) {
      throw new Error('document importer: produced invalid Document (Phase 8-C1 strict)')
    }
    return document
  }

  // ============ Scientific chunks (section + page aware) ============

  /**
   * Phase 8-C1: one chunk per section-partition, tagged with section + page.
   * Long sections are re-split deterministically via splitContent.
   */
  toScientificChunks(document: Document, parsed: ParsedPDF): DocumentChunk[] {
    const chunks: DocumentChunk[] = []
    let position = 0
    for (const section of parsed.sections) {
      const content = section.content
      if (content.length === 0) {
        chunks.push(this.sectionChunk(document, section, '', position))
        position++
        continue
      }
      const maxChars = 800
      const parts = splitContent(content, maxChars, 0, false)
      for (const part of parts) {
        chunks.push(this.sectionChunk(document, section, part, position))
        position++
      }
    }
    return chunks
  }

  private sectionChunk(
    document: Document,
    section: { title: string; pageStart: number },
    content: string,
    position: number
  ): DocumentChunk {
    const chunk: DocumentChunk = {
      id: `${document.id}#s${position}`,
      documentId: document.id,
      content,
      position,
      metadata: { section: section.title, page: section.pageStart }
    }
    if (!isValidDocumentChunk(chunk)) {
      throw new Error('document importer: produced invalid DocumentChunk (Phase 8-C1 strict)')
    }
    return chunk
  }
}

export const __testHelpers = {
  splitContent
}