-- Migration 017 — Phase 11 P11-6 + P11-7: Memories + Knowledge Brain
-- 单向 snapshot. 大字段不入 SQLite, vector 不入.
-- 1) memories (29 行, 简单) + 2) knowledge (530 行) + 3-9) 7 子表.

CREATE TABLE IF NOT EXISTS desktop_memories (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  web_id              INTEGER,
  owner_username      TEXT,
  memory_type         TEXT NOT NULL CHECK (memory_type IN ('preference','summary','entity','fact','context')),
  key                 TEXT,
  content             TEXT NOT NULL,
  importance          REAL NOT NULL DEFAULT 1.0,
  access_count        INTEGER NOT NULL DEFAULT 0,
  last_accessed_at_epoch INTEGER,
  source_session      TEXT,
  is_active           INTEGER NOT NULL DEFAULT 1,
  created_at_epoch    INTEGER,
  updated_at_epoch    INTEGER,
  synced_at_epoch     INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_desktop_memories_web_id ON desktop_memories(web_id);
CREATE INDEX IF NOT EXISTS idx_desktop_memories_owner ON desktop_memories(owner_username);
CREATE INDEX IF NOT EXISTS idx_desktop_memories_type ON desktop_memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_desktop_memories_synced ON desktop_memories(synced_at_epoch DESC);

-- Knowledge 主表 (53 列 web → desktop 字段子集)
CREATE TABLE IF NOT EXISTS desktop_knowledge (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  web_id                INTEGER,
  title                 TEXT NOT NULL,
  content               TEXT NOT NULL,
  category              TEXT,
  topic                 TEXT,
  tags_json             TEXT,
  key_concepts_json     TEXT,
  related_topics_json   TEXT,
  knowledge_type        TEXT,
  source                TEXT,
  source_type           TEXT,
  source_url            TEXT,
  summary               TEXT,
  formatted_content     TEXT,
  entities_json         TEXT,
  quality_score         REAL,
  auto_researched       INTEGER NOT NULL DEFAULT 0,
  needs_review          INTEGER NOT NULL DEFAULT 0,
  analysis_status       TEXT NOT NULL DEFAULT 'pending',
  file_path             TEXT,
  file_name             TEXT,
  file_type             TEXT,
  embedding_model_version TEXT NOT NULL DEFAULT 'qwen3-0.6b',
  -- vector (1024d) 不入 SQLite. desktop 用本地 mini-embedding 128d 替代 (deferred to P11-7.5)
  created_at_epoch      INTEGER,
  updated_at_epoch      INTEGER,
  synced_at_epoch       INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_desktop_knowledge_web_id ON desktop_knowledge(web_id);
CREATE INDEX IF NOT EXISTS idx_desktop_knowledge_category ON desktop_knowledge(category);
CREATE INDEX IF NOT EXISTS idx_desktop_knowledge_source_type ON desktop_knowledge(source_type);
CREATE INDEX IF NOT EXISTS idx_desktop_knowledge_synced ON desktop_knowledge(synced_at_epoch DESC);

-- Knowledge 子表: chunks (37 行, vector 1024d 不存)
CREATE TABLE IF NOT EXISTS desktop_knowledge_chunks (
  web_id            INTEGER PRIMARY KEY,
  knowledge_web_id  INTEGER NOT NULL,
  chunk_index       INTEGER NOT NULL,
  content           TEXT NOT NULL,
  embedding_model_version TEXT NOT NULL DEFAULT 'qwen3-0.6b',
  created_at_epoch  INTEGER,
  synced_at_epoch   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_desktop_knowledge_chunks_knowledge ON desktop_knowledge_chunks(knowledge_web_id);

-- Knowledge 子表: relations (210 行)
CREATE TABLE IF NOT EXISTS desktop_knowledge_relations (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  web_id            INTEGER,
  source_knowledge_web_id  INTEGER NOT NULL,
  target_knowledge_web_id  INTEGER NOT NULL,
  relation_type     TEXT NOT NULL,
  confidence        REAL,
  description       TEXT,
  created_at_epoch  INTEGER,
  synced_at_epoch   INTEGER NOT NULL,
  UNIQUE(source_knowledge_web_id, target_knowledge_web_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_desktop_knowledge_relations_source ON desktop_knowledge_relations(source_knowledge_web_id);
CREATE INDEX IF NOT EXISTS idx_desktop_knowledge_relations_target ON desktop_knowledge_relations(target_knowledge_web_id);

-- Knowledge 子表: entities (131 行, JSON 数组)
CREATE TABLE IF NOT EXISTS desktop_knowledge_entities (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  web_id            INTEGER,
  knowledge_web_id  INTEGER NOT NULL,
  entity_name       TEXT NOT NULL,
  entity_type       TEXT,
  confidence        REAL,
  mention_count     INTEGER,
  context_json      TEXT,
  synced_at_epoch   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_desktop_knowledge_entities_knowledge ON desktop_knowledge_entities(knowledge_web_id);
CREATE INDEX IF NOT EXISTS idx_desktop_knowledge_entities_name ON desktop_knowledge_entities(entity_name);

-- Knowledge 子表: formulas (2 行)
CREATE TABLE IF NOT EXISTS desktop_knowledge_formulas (
  web_id              INTEGER PRIMARY KEY,
  knowledge_web_id    INTEGER NOT NULL,
  name                TEXT NOT NULL,
  latex               TEXT,
  category            TEXT,
  description         TEXT,
  synced_at_epoch     INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_desktop_knowledge_formulas_knowledge ON desktop_knowledge_formulas(knowledge_web_id);

-- Knowledge 子表: images (37 行, file_path 不存, 仅 reference)
CREATE TABLE IF NOT EXISTS desktop_knowledge_images (
  web_id            INTEGER PRIMARY KEY,
  knowledge_web_id  INTEGER NOT NULL,
  image_url         TEXT NOT NULL,
  caption           TEXT,
  width             INTEGER,
  height            INTEGER,
  alt_text          TEXT,
  synced_at_epoch   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_desktop_knowledge_images_knowledge ON desktop_knowledge_images(knowledge_web_id);

-- Knowledge 子表: layouts (400 行, JSON 截断)
CREATE TABLE IF NOT EXISTS desktop_knowledge_layouts (
  web_id            INTEGER PRIMARY KEY,
  knowledge_web_id  INTEGER NOT NULL,
  layout_type       TEXT,
  layout_json       TEXT,
  synced_at_epoch   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_desktop_knowledge_layouts_knowledge ON desktop_knowledge_layouts(knowledge_web_id);

-- Knowledge 子表: versions (32 行, 0 数据, 跳过)
-- 保留 schema 占位但 Phase 11 Stage 2 不强制导入 (web 0 行, plan 明确 out of scope)
CREATE TABLE IF NOT EXISTS desktop_knowledge_versions (
  web_id            INTEGER PRIMARY KEY,
  knowledge_web_id  INTEGER NOT NULL,
  version           INTEGER,
  content_snapshot  TEXT,
  created_at_epoch  INTEGER,
  synced_at_epoch   INTEGER NOT NULL
);