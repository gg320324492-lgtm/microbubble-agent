-- Migration 018 — Phase 11 P11-11: AgentTraces + ActivityEvents
-- 1) desktop_agent_traces (web agent_traces 3619 行, type 映射 tool_use/tool_result/message)
-- 2) desktop_activity_events (web activity_events 1086 行)

CREATE TABLE IF NOT EXISTS desktop_agent_traces (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  web_id            INTEGER,
  session_id        TEXT,
  agent_name        TEXT,
  trace_type        TEXT NOT NULL CHECK (trace_type IN ('tool_use','tool_result','message','system','error','plan','reflection')),
  role              TEXT,
  content_json      TEXT,
  tool_name          TEXT,
  tool_input_json   TEXT,
  tool_output_json  TEXT,
  duration_ms       INTEGER,
  user_id           INTEGER,
  owner_username    TEXT,
  created_at_epoch  INTEGER,
  synced_at_epoch   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_desktop_agent_traces_web_id ON desktop_agent_traces(web_id);
CREATE INDEX IF NOT EXISTS idx_desktop_agent_traces_session ON desktop_agent_traces(session_id);
CREATE INDEX IF NOT EXISTS idx_desktop_agent_traces_type ON desktop_agent_traces(trace_type);
CREATE INDEX IF NOT EXISTS idx_desktop_agent_traces_owner ON desktop_agent_traces(owner_username);
CREATE INDEX IF NOT EXISTS idx_desktop_agent_traces_synced ON desktop_agent_traces(synced_at_epoch DESC);

CREATE TABLE IF NOT EXISTS desktop_activity_events (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  web_id            INTEGER,
  user_id           INTEGER,
  owner_username    TEXT,
  event_type        TEXT NOT NULL CHECK (event_type IN ('view','edit','login','logout','create','delete','update','search','export','share','click','error')),
  resource_type     TEXT,
  resource_id       TEXT,
  action            TEXT,
  metadata_json     TEXT,
  ip_address        TEXT,
  user_agent        TEXT,
  created_at_epoch  INTEGER,
  synced_at_epoch   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_desktop_activity_events_web_id ON desktop_activity_events(web_id);
CREATE INDEX IF NOT EXISTS idx_desktop_activity_events_owner ON desktop_activity_events(owner_username);
CREATE INDEX IF NOT EXISTS idx_desktop_activity_events_type ON desktop_activity_events(event_type);
CREATE INDEX IF NOT EXISTS idx_desktop_activity_events_resource ON desktop_activity_events(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_desktop_activity_events_synced ON desktop_activity_events(synced_at_epoch DESC);