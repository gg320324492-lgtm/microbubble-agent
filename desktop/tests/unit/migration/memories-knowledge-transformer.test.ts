// Memories + Knowledge Brain Transformer 单元测试 — Phase 11 P11-6 + P11-7

import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const desktopRoot = resolve(__dirname, '..', '..', '..')
const mainRoot = resolve(desktopRoot, 'src/main')

describe('Phase 11 P11-6+P11-7: Schema', () => {
  it('017-memories-knowledge.sql 存在', () => {
    expect(existsSync(resolve(mainRoot, 'database/schema/017-memories-knowledge.sql'))).toBe(true)
  })

  it('desktop_memories 5 个 memory_type (含 phase 11 新增 fact/context)', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/017-memories-knowledge.sql'), 'utf8')
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_memories/)
    expect(sql).toMatch(/memory_type.*CHECK.*preference.*summary.*entity.*fact.*context/)
  })

  it('desktop_knowledge 主表 + 7 子表 (chunks/relations/entities/formulas/images/layouts/versions)', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/017-memories-knowledge.sql'), 'utf8')
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_knowledge/)
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_knowledge_chunks/)
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_knowledge_relations/)
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_knowledge_entities/)
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_knowledge_formulas/)
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_knowledge_images/)
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_knowledge_layouts/)
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_knowledge_versions/)
  })

  it('knowledge UNIQUE 约束 relations (source, target, type)', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/017-memories-knowledge.sql'), 'utf8')
    expect(sql).toContain('UNIQUE(source_knowledge_web_id, target_knowledge_web_id, relation_type)')
  })

  it('017 已加入 INLINE_SCHEMAS', () => {
    const mm = readFileSync(resolve(mainRoot, 'database/migration-manager.ts'), 'utf8')
    expect(mm).toContain("import SCHEMA_017 from './schema/017-memories-knowledge.sql?raw'")
    expect(mm).toContain("filename: '017-memories-knowledge.sql'")
  })
})

describe('Phase 11 P11-6: transformMemoryRow', () => {
  it('典型 PG row → desktop_memories row', async () => {
    const { transformMemoryRow } = await import('../../../src/main/migration/pg-snapshot/transformers/memories-knowledge')
    const lookup = new Map<number, string>([[1, 'wangtianzhi']])
    const pgRow = {
      id: 1, user_id: 1, memory_type: 'preference', key: 'preferred_format',
      content: '喜欢表格 + 流程图', importance: 0.8, access_count: 5,
      last_accessed_at: '2026-08-20 10:00:00+08', source_session: 'user_1730123456_a1b2c3',
      is_active: true, created_at: '2026-08-15 09:00:00+08', updated_at: '2026-08-20 10:00:00+08'
    }
    const out = transformMemoryRow(pgRow, lookup)
    expect(out.web_id).toBe(1)
    expect(out.owner_username).toBe('wangtianzhi')
    expect(out.memory_type).toBe('preference')
    expect(out.importance).toBe(0.8)
    expect(out.access_count).toBe(5)
    expect(out.is_active).toBe(1)
  })

  it('5 个 memory_type enum 全部保留', async () => {
    const { transformMemoryRow } = await import('../../../src/main/migration/pg-snapshot/transformers/memories-knowledge')
    for (const t of ['preference', 'summary', 'entity', 'fact', 'context']) {
      const out = transformMemoryRow({ id: 1, user_id: 1, memory_type: t, content: 'x' }, null)
      expect(out.memory_type).toBe(t)
    }
  })

  it('importance 限制 0-1', async () => {
    const { transformMemoryRow } = await import('../../../src/main/migration/pg-snapshot/transformers/memories-knowledge')
    expect(transformMemoryRow({ id: 1, user_id: 1, memory_type: 'fact', content: 'x', importance: -0.5 }).importance).toBe(0)
    expect(transformMemoryRow({ id: 1, user_id: 1, memory_type: 'fact', content: 'x', importance: 1.5 }).importance).toBe(1)
  })
})

describe('Phase 11 P11-7: transformKnowledgeRow', () => {
  it('典型 PG row → desktop_knowledge row (53 列子集)', async () => {
    const { transformKnowledgeRow } = await import('../../../src/main/migration/pg-snapshot/transformers/memories-knowledge')
    const pgRow = {
      id: 100,
      title: 'O3 消毒动力学',
      content: '臭氧与水中有机物反应...',
      category: '方法',
      topic: 'O3-MNB',
      tags: ['消毒', '臭氧'],
      key_concepts: ['k1'],
      related_topics: ['t1'],
      knowledge_type: 'paper',
      source: 'https://example.com/paper1',
      source_type: 'paper',
      summary: '研究 O3 消毒',
      formatted_content: '# 标题\n...',
      entities: '[{"subject":"O3","object":"菌","predicate":"杀灭"}]',
      quality_score: 0.85,
      auto_researched: false,
      needs_review: true,
      analysis_status: 'done',
      file_path: 'minio://kb/100.pdf',
      file_name: 'paper1.pdf',
      file_type: 'application/pdf',
      embedding_model_version: 'qwen3-0.6b'
    }
    const out = transformKnowledgeRow(pgRow)
    expect(out.web_id).toBe(100)
    expect(out.title).toBe('O3 消毒动力学')
    expect(out.quality_score).toBe(0.85)
    expect(out.needs_review).toBe(1)
    expect(out.auto_researched).toBe(0)
    expect(out.analysis_status).toBe('done')
    expect(out.embedding_model_version).toBe('qwen3-0.6b')
  })

  it('vector 字段不入 SQLite (embedding 不在 output)', async () => {
    const { transformKnowledgeRow } = await import('../../../src/main/migration/pg-snapshot/transformers/memories-knowledge')
    const out = transformKnowledgeRow({ id: 1, title: 'x', content: 'y', embedding: '[1.0,2.0,...1024d]' })
    expect(out.embedding).toBeUndefined()
  })

  it('analysis_status enum 4 值', async () => {
    const { transformKnowledgeRow } = await import('../../../src/main/migration/pg-snapshot/transformers/memories-knowledge')
    for (const s of ['pending', 'analyzing', 'done', 'failed']) {
      const out = transformKnowledgeRow({ id: 1, title: 'x', content: 'y', analysis_status: s })
      expect(out.analysis_status).toBe(s)
    }
  })
})

describe('Phase 11 P11-7: 子表 transformers', () => {
  it('transformKnowledgeChunkRow: knowledge_id → knowledge_web_id', async () => {
    const { transformKnowledgeChunkRow } = await import('../../../src/main/migration/pg-snapshot/transformers/memories-knowledge')
    const out = transformKnowledgeChunkRow({ id: 1, knowledge_id: 5, chunk_index: 0, content: 'chunk 0 text' })
    expect(out.knowledge_web_id).toBe(5)
    expect(out.chunk_index).toBe(0)
  })

  it('transformKnowledgeRelationRow: source/target knowledge_id → source/target _web_id', async () => {
    const { transformKnowledgeRelationRow } = await import('../../../src/main/migration/pg-snapshot/transformers/memories-knowledge')
    const out = transformKnowledgeRelationRow({
      id: 1, source_knowledge_id: 10, target_knowledge_id: 20,
      relation_type: 'cites', confidence: 0.9
    })
    expect(out.source_knowledge_web_id).toBe(10)
    expect(out.target_knowledge_web_id).toBe(20)
    expect(out.confidence).toBe(0.9)
  })

  it('transformKnowledgeEntityRow: knowledge_id → knowledge_web_id', async () => {
    const { transformKnowledgeEntityRow } = await import('../../../src/main/migration/pg-snapshot/transformers/memories-knowledge')
    const out = transformKnowledgeEntityRow({ id: 1, knowledge_id: 8, entity_name: '臭氧', entity_type: 'compound', mention_count: 3 })
    expect(out.knowledge_web_id).toBe(8)
    expect(out.entity_name).toBe('臭氧')
  })

  it('transformKnowledgeFormulaRow: knowledge_id → knowledge_web_id', async () => {
    const { transformKnowledgeFormulaRow } = await import('../../../src/main/migration/pg-snapshot/transformers/memories-knowledge')
    const out = transformKnowledgeFormulaRow({ id: 1, knowledge_id: 12, name: 'Henry 定律', latex: 'C = kP', category: '物理' })
    expect(out.knowledge_web_id).toBe(12)
    expect(out.latex).toBe('C = kP')
  })

  it('transformKnowledgeImageRow: knowledge_id → knowledge_web_id (image_url 必填)', async () => {
    const { transformKnowledgeImageRow } = await import('../../../src/main/migration/pg-snapshot/transformers/memories-knowledge')
    const out = transformKnowledgeImageRow({ id: 1, knowledge_id: 15, image_url: 'https://minio/x.jpg', width: 800, height: 600 })
    expect(out.knowledge_web_id).toBe(15)
    expect(out.width).toBe(800)
  })

  it('transformKnowledgeLayoutRow: knowledge_id → knowledge_web_id', async () => {
    const { transformKnowledgeLayoutRow } = await import('../../../src/main/migration/pg-snapshot/transformers/memories-knowledge')
    const out = transformKnowledgeLayoutRow({ id: 1, knowledge_id: 20, layout_type: 'grid', layout: '{"cols":3}' })
    expect(out.knowledge_web_id).toBe(20)
  })
})

describe('Phase 11 P11-7: SELECT SQL safety', () => {
  it('7 个 SELECT 都 SELECT-only', async () => {
    const m = await import('../../../src/main/migration/pg-snapshot/transformers/memories-knowledge')
    const allSqls = [m.KNOWLEDGE_SELECT_SQL, m.KNOWLEDGE_CHUNKS_SELECT_SQL, m.KNOWLEDGE_RELATIONS_SELECT_SQL, m.KNOWLEDGE_ENTITIES_SELECT_SQL, m.KNOWLEDGE_FORMULAS_SELECT_SQL, m.KNOWLEDGE_IMAGES_SELECT_SQL, m.KNOWLEDGE_LAYOUTS_SELECT_SQL, m.MEMORIES_SELECT_SQL]
    for (const sql of allSqls) {
      expect(sql.trim().toUpperCase()).toMatch(/^SELECT/)
      expect(/\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|GRANT|REVOKE)\b/i.test(sql)).toBe(false)
    }
    // 至少 1 个含 knowledge 表
    expect(m.KNOWLEDGE_SELECT_SQL).toContain('FROM knowledge')
    expect(m.MEMORIES_SELECT_SQL).toContain('FROM memories')
  })
})