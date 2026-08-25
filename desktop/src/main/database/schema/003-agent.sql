-- Migration 003: Agent History
-- Stores agent actions / inputs / outputs for audit and replay

CREATE TABLE IF NOT EXISTS agent_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent TEXT NOT NULL,
  action TEXT NOT NULL,
  input TEXT,
  output TEXT,
  timestamp INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_history_agent_ts ON agent_history (agent, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_agent_history_action ON agent_history (action);
CREATE INDEX IF NOT EXISTS idx_agent_history_timestamp ON agent_history (timestamp DESC);