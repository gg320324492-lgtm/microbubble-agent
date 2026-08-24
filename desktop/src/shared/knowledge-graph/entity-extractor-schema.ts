// Entity Extractor Schema — 实体抽取契约。
import type { DocumentChunk } from '../../shared/knowledge/document-schema'
import type { ScientificEntity, KnowledgeRelation } from './knowledge-graph-schema'

export interface EntityExtractionResult {
  entities: ScientificEntity[]
  relations: KnowledgeRelation[]
  confidence: number
}

export interface ScientificEntityExtractor {
  extractEntities(chunk: DocumentChunk): Promise<EntityExtractionResult>
  extractRelations(chunk: DocumentChunk, entities: ScientificEntity[]): Promise<EntityExtractionResult>
}
