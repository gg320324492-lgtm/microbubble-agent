-- Migration 008 — Standardization Tables (Phase 10.6)
-- 实验条件标准化字段表 + 时间单位索引.

CREATE TABLE IF NOT EXISTS experiment_conditions (
  experiment_id TEXT PRIMARY KEY,
  conditions_json TEXT NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_experiment_conditions_updated_at
  ON experiment_conditions (updated_at DESC);