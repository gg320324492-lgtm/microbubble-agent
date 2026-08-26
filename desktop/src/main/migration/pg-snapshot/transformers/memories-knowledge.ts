// Memories + Knowledge Brain Transformers — Phase 11 P11-6 + P11-7
// 单向: web PG memories + knowledge + 7 子表 → desktop 镜像.
// vector (1024d) 不入 SQLite. JSONB 截断 / TEXT-only.

import { applyTransformers, pgJsonToJsonString, pgTimestampToEpochMs } from '../transform-pipeline'
import type { TransformerMap } from '../transform-pipeline'

const WHITELIST_MEMORY_TYPE = ['preference', 'summary', 'entity', 'fact', 'context']
const WHITELIST_ANALYSIS = ['pending', 'analyzing', 'done', 'failed']

// ============ P11-6 Memories ============

/** web memories → desktop_memories row. */
export function transformMemoryRow(
  pgRow: Record<string, unknown>,
  ownerUsernameLookup: Map<number, string> | null
): Record<string, unknown> {
  const pgId = pgRow['id']
  const userId = pgRow['user_id']
  const map: TransformerMap = {
    web_id: () => (pgId == null ? null : Number(pgId) || null),
    owner_username: () => (ownerUsernameLookup && userId != null ? (ownerUsernameLookup.get(Number(userId)) ?? null) : null),
    memory_type: (v) => validateEnum(v, 'memory_type', WHITELIST_MEMORY_TYPE, 'fact'),
    key: (v) => (v == null ? null : String(v)),
    content: (v) => (v == null ? '' : String(v)),
    importance: (v) => (v == null ? 1.0 : Math.max(0, Math.min(1, Number(v) || 1))),
    access_count: (v) => (v == null ? 0 : Number(v) || 0),
    last_accessed_at_epoch: (v) => pgTimestampToEpochMs(v),
    source_session: (v) => (v == null ? null : String(v)),
    is_active: (v) => (v == null ? 1 : Number(v) ? 1 : 0),
    created_at_epoch: (v) => pgTimestampToEpochMs(v),
    updated_at_epoch: (v) => pgTimestampToEpochMs(v),
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

export const MEMORIES_SELECT_SQL = `
  SELECT
    id, user_id, memory_type, key, content,
    importance, access_count, last_accessed_at,
    source_session, is_active, created_at, updated_at
  FROM memories
  WHERE is_active = true
  ORDER BY id ASC
`

// ============ P11-7 Knowledge Brain ============

/** web knowledge (53 列) → desktop_knowledge row. */
export function transformKnowledgeRow(pgRow: Record<string, unknown>): Record<string, unknown> {
  const pgId = pgRow['id']
  const map: TransformerMap = {
    web_id: () => (pgId == null ? null : Number(pgId) || null),
    title: (v) => (v == null ? '' : String(v)),
    content: (v) => (v == null ? '' : String(v)),
    category: (v) => (v == null ? null : String(v)),
    topic: (v) => (v == null ? null : String(v)),
    tags_json: (v) => pgJsonToJsonString(v) ?? '[]',
    key_concepts_json: (v) => pgJsonToJsonString(v) ?? '[]',
    related_topics_json: (v) => pgJsonToJsonString(v) ?? '[]',
    knowledge_type: (v) => (v == null ? null : String(v)),
    source: (v) => (v == null ? null : String(v)),
    source_type: (v) => (v == null ? null : String(v)),
    source_url: (v) => (v == null ? null : String(v)),
    summary: (v) => (v == null ? null : String(v)),
    formatted_content: (v) => (v == null ? null : String(v)),
    entities_json: (v) => pgJsonToJsonString(v) ?? '[]',
    quality_score: (v) => (v == null ? null : Math.max(0, Math.min(1, Number(v) || 0))),
    auto_researched: (v) => (v == null ? 0 : Number(v) ? 1 : 0),
    needs_review: (v) => (v == null ? 0 : Number(v) ? 1 : 0),
    analysis_status: (v) => validateEnum(v, 'analysis_status', WHITELIST_ANALYSIS, 'pending'),
    file_path: (v) => (v == null ? null : String(v)),
    file_name: (v) => (v == null ? null : String(v)),
    file_type: (v) => (v == null ? null : String(v)),
    embedding_model_version: (v) => (v == null ? 'qwen3-0.6b' : String(v)),
    created_at_epoch: (v) => pgTimestampToEpochMs(v),
    updated_at_epoch: (v) => pgTimestampToEpochMs(v),
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

/** web knowledge_chunks → desktop_knowledge_chunks row. */
export function transformKnowledgeChunkRow(pgRow: Record<string, unknown>): Record<string, unknown> {
  const knowledgeId = pgRow['knowledge_id']
  const map: TransformerMap = {
    web_id: (v) => (v == null ? null : Number(v) || null),
    knowledge_web_id: () => (knowledgeId == null ? null : Number(knowledgeId) || null),
    chunk_index: (v) => (v == null ? 0 : Number(v) || 0),
    content: (v) => (v == null ? '' : String(v)),
    embedding_model_version: (v) => (v == null ? 'qwen3-0.6b' : String(v)),
    created_at_epoch: (v) => pgTimestampToEpochMs(v),
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

/** web knowledge_relations → desktop_knowledge_relations row. */
export function transformKnowledgeRelationRow(pgRow: Record<string, unknown>): Record<string, unknown> {
  const sourceId = pgRow['source_knowledge_id']
  const targetId = pgRow['target_knowledge_id']
  const map: TransformerMap = {
    web_id: (v) => (v == null ? null : Number(v) || null),
    source_knowledge_web_id: () => (sourceId == null ? null : Number(sourceId) || null),
    target_knowledge_web_id: () => (targetId == null ? null : Number(targetId) || null),
    relation_type: (v) => (v == null ? '' : String(v)),
    confidence: (v) => (v == null ? null : Math.max(0, Math.min(1, Number(v) || 0))),
    description: (v) => (v == null ? null : String(v)),
    created_at_epoch: (v) => pgTimestampToEpochMs(v),
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

/** web knowledge_entities → desktop_knowledge_entities row. */
export function transformKnowledgeEntityRow(pgRow: Record<string, unknown>): Record<string, unknown> {
  const knowledgeId = pgRow['knowledge_id']
  const map: TransformerMap = {
    web_id: (v) => (v == null ? null : Number(v) || null),
    knowledge_web_id: () => (knowledgeId == null ? null : Number(knowledgeId) || null),
    entity_name: (v) => (v == null ? '' : String(v)),
    entity_type: (v) => (v == null ? null : String(v)),
    confidence: (v) => (v == null ? null : Math.max(0, Math.min(1, Number(v) || 0))),
    mention_count: (v) => (v == null ? 0 : Number(v) || 0),
    context_json: (v) => pgJsonToJsonString(v) ?? '[]',
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

/** web knowledge_formulas → desktop_knowledge_formulas row. */
export function transformKnowledgeFormulaRow(pgRow: Record<string, unknown>): Record<string, unknown> {
  const knowledgeId = pgRow['knowledge_id']
  const map: TransformerMap = {
    web_id: (v) => (v == null ? null : Number(v) || null),
    knowledge_web_id: () => (knowledgeId == null ? null : Number(knowledgeId) || null),
    name: (v) => (v == null ? '' : String(v)),
    latex: (v) => (v == null ? null : String(v)),
    category: (v) => (v == null ? null : String(v)),
    description: (v) => (v == null ? null : String(v)),
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

/** web knowledge_images → desktop_knowledge_images row. */
export function transformKnowledgeImageRow(pgRow: Record<string, unknown>): Record<string, unknown> {
  const knowledgeId = pgRow['knowledge_id']
  const map: TransformerMap = {
    web_id: (v) => (v == null ? null : Number(v) || null),
    knowledge_web_id: () => (knowledgeId == null ? null : Number(knowledgeId) || null),
    image_url: (v) => (v == null ? '' : String(v)),
    caption: (v) => (v == null ? null : String(v)),
    width: (v) => (v == null ? null : Number(v) || null),
    height: (v) => (v == null ? null : Number(v) || null),
    alt_text: (v) => (v == null ? null : String(v)),
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

/** web knowledge_layouts → desktop_knowledge_layouts row. */
export function transformKnowledgeLayoutRow(pgRow: Record<string, unknown>): Record<string, unknown> {
  const knowledgeId = pgRow['knowledge_id']
  const map: TransformerMap = {
    web_id: (v) => (v == null ? null : Number(v) || null),
    knowledge_web_id: () => (knowledgeId == null ? null : Number(knowledgeId) || null),
    layout_type: (v) => (v == null ? null : String(v)),
    layout_json: (v) => pgJsonToJsonString(v),
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

function validateEnum(raw: unknown, name: string, whitelist: ReadonlyArray<string>, fallback: string): string {
  if (raw == null) return fallback
  const s = String(raw)
  if (whitelist.includes(s)) return s
  throw new Error(`Invalid ${name}: '${s}' not in [${whitelist.join(', ')}]`)
}

// SELECT SQL (web PG column names)
export const KNOWLEDGE_SELECT_SQL = `
  SELECT
    id, title, content,
    category, topic, tags,
    key_concepts, related_topics, knowledge_type,
    analysis_status, auto_researched, quality_score, needs_review,
    entities, source, source_type, meta,
    file_path, file_name, file_type,
    summary, formatted_content,
    embedding_model_version, created_at, updated_at
  FROM knowledge
  ORDER BY id ASC
`

export const KNOWLEDGE_CHUNKS_SELECT_SQL = `
  SELECT id, knowledge_id, chunk_index, content, embedding_model_version, created_at
  FROM knowledge_chunks
  ORDER BY knowledge_id ASC, chunk_index ASC
`

export const KNOWLEDGE_RELATIONS_SELECT_SQL = `
  SELECT id, source_knowledge_id, target_knowledge_id, relation_type, confidence, description, created_at
  FROM knowledge_relations
  ORDER BY id ASC
`

export const KNOWLEDGE_ENTITIES_SELECT_SQL = `
  SELECT id, knowledge_id, entity_name, entity_type, confidence, mention_count, context, created_at
  FROM knowledge_entities
  ORDER BY knowledge_id ASC, mention_count DESC
`

export const KNOWLEDGE_FORMULAS_SELECT_SQL = `
  SELECT id, knowledge_id, name, latex, category, description
  FROM knowledge_formulas
  ORDER BY knowledge_id ASC
`

export const KNOWLEDGE_IMAGES_SELECT_SQL = `
  SELECT id, knowledge_id, image_url, caption, width, height, alt_text
  FROM knowledge_images
  ORDER BY knowledge_id ASC
`

export const KNOWLEDGE_LAYOUTS_SELECT_SQL = `
  SELECT id, knowledge_id, layout_type, layout
  FROM knowledge_layouts
  ORDER BY knowledge_id ASC
`