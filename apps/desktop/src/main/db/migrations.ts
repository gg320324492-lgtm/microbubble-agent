// 数据库迁移链 — 001-002 起步（骨架设计 §2），SQL 内联便于 asar 打包与测试复用
import type { SqlDatabase } from './adapters'

export interface Migration {
  id: number
  name: string
  sql: string
}

export const MIGRATIONS: Migration[] = [
  {
    id: 1,
    name: 'users-and-sessions',
    sql: `
      CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        display_name TEXT,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'researcher',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
      );
      CREATE TABLE IF NOT EXISTS user_sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL,
        issued_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL,
        last_seen_at INTEGER,
        revoked_at INTEGER
      );
      CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(token_hash);
    `
  },
  {
    id: 2,
    name: 'settings',
    sql: `
      CREATE TABLE IF NOT EXISTS settings (
        user_id TEXT NOT NULL DEFAULT '',
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        updated_at INTEGER NOT NULL,
        PRIMARY KEY (user_id, key)
      );
    `
  },
  {
    id: 3,
    name: 'chat-sessions-and-messages',
    sql: `
      CREATE TABLE IF NOT EXISTS chat_sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '新会话',
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id, updated_at);
      CREATE TABLE IF NOT EXISTS chat_messages (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at INTEGER NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id, created_at);
    `
  },
  {
    id: 4,
    name: 'workspace-audit',
    sql: `
      CREATE TABLE IF NOT EXISTS workspace_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        tool TEXT,
        input_summary TEXT,
        ok INTEGER,
        created_at INTEGER
      );
    `
  },
  {
    id: 5,
    name: 'chat-messages-meta',
    sql: `
      ALTER TABLE chat_messages ADD COLUMN meta TEXT;
    `
  },
  {
    id: 6,
    name: 'knowledge-documents',
    sql: `
      CREATE TABLE IF NOT EXISTS knowledge_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        file_name TEXT,
        file_size INTEGER NOT NULL DEFAULT 0,
        tags TEXT NOT NULL DEFAULT '[]',
        source TEXT NOT NULL DEFAULT 'local_import',
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_knowledge_user ON knowledge_documents(user_id, updated_at);
      CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(title_seg, content_seg, tokenize='unicode61');
    `
  },
  {
    id: 7,
    name: 'meeting-archives',
    sql: `
      CREATE TABLE IF NOT EXISTS meetings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        meeting_date INTEGER,
        location TEXT NOT NULL DEFAULT '',
        attendees TEXT NOT NULL DEFAULT '[]',
        minutes TEXT NOT NULL DEFAULT '',
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_meetings_user ON meetings(user_id, updated_at);
      CREATE TABLE IF NOT EXISTS meeting_transcripts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'paste',
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_meeting_transcripts_meeting ON meeting_transcripts(meeting_id);
      CREATE TABLE IF NOT EXISTS meeting_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER NOT NULL,
        file_name TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        created_at INTEGER NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_meeting_files_meeting ON meeting_files(meeting_id);
      CREATE VIRTUAL TABLE IF NOT EXISTS meeting_fts USING fts5(title_seg, minutes_seg, transcript_seg, tokenize='unicode61');
    `
  },
  {
    id: 8,
    name: 'experiment-notebook',
    sql: `
      CREATE TABLE IF NOT EXISTS experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        code TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'ongoing',
        tags TEXT NOT NULL DEFAULT '[]',
        content TEXT NOT NULL DEFAULT '',
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_experiments_user ON experiments(user_id, updated_at);
      CREATE TABLE IF NOT EXISTS experiment_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        experiment_id INTEGER NOT NULL,
        file_name TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        created_at INTEGER NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_experiment_files_exp ON experiment_files(experiment_id);
      CREATE VIRTUAL TABLE IF NOT EXISTS experiments_fts USING fts5(title_seg, content_seg, tokenize='unicode61');
      CREATE TABLE IF NOT EXISTS eln_counters (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
    `
  },
  {
    id: 9,
    name: 'manuscript-library',
    sql: `
      CREATE TABLE IF NOT EXISTS manuscripts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft',
        target_journal TEXT NOT NULL DEFAULT '',
        tags TEXT NOT NULL DEFAULT '[]',
        content TEXT NOT NULL DEFAULT '',
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_manuscripts_user ON manuscripts(user_id, updated_at);
      CREATE TABLE IF NOT EXISTS manuscript_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        manuscript_id INTEGER NOT NULL,
        file_name TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        created_at INTEGER NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_manuscript_files_ms ON manuscript_files(manuscript_id);
      CREATE VIRTUAL TABLE IF NOT EXISTS manuscripts_fts USING fts5(title_seg, content_seg, tokenize='unicode61');
    `
  }
]

/** 幂等迁移 — 每个迁移单事务，失败回滚并抛出 */
export function runMigrations(db: SqlDatabase): void {
  db.exec('CREATE TABLE IF NOT EXISTS schema_migrations (id INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at INTEGER NOT NULL)')
  const applied = new Set(
    (db.prepare('SELECT id FROM schema_migrations').all() as { id: number }[]).map((r) => r.id)
  )
  for (const m of MIGRATIONS) {
    if (applied.has(m.id)) continue
    db.exec('BEGIN')
    try {
      db.exec(m.sql)
      db.prepare('INSERT INTO schema_migrations (id, name, applied_at) VALUES (?, ?, ?)').run(m.id, m.name, Date.now())
      db.exec('COMMIT')
    } catch (err) {
      db.exec('ROLLBACK')
      throw err
    }
  }
}
