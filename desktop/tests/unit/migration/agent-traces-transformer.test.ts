// Agent Traces + Activity Events Transformer 单元测试 — Phase 11 P11-11

import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const desktopRoot = resolve(__dirname, '..', '..', '..')
const mainRoot = resolve(desktopRoot, 'src/main')

describe('Phase 11 P11-11: Agent Traces + Activity Events Schema', () => {
  it('018-agent-traces.sql 存在', () => {
    expect(existsSync(resolve(mainRoot, 'database/schema/018-agent-traces.sql'))).toBe(true)
  })

  it('desktop_agent_traces 7 值 trace_type CHECK', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/018-agent-traces.sql'), 'utf8')
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_agent_traces/)
    expect(sql).toMatch(/trace_type.*CHECK.*tool_use.*tool_result.*message.*system.*error.*plan.*reflection/)
  })

  it('desktop_activity_events 12 值 event_type CHECK', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/018-agent-traces.sql'), 'utf8')
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_activity_events/)
    expect(sql).toMatch(/event_type.*CHECK.*view.*edit.*login.*logout.*create.*delete.*update.*search.*export.*share.*click.*error/)
  })

  it('desktop_activity_events 含 ip_address + user_agent (本地化保留)', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/018-agent-traces.sql'), 'utf8')
    expect(sql).toMatch(/ip_address\s+TEXT/)
    expect(sql).toMatch(/user_agent\s+TEXT/)
  })

  it('018 已加入 INLINE_SCHEMAS', () => {
    const mm = readFileSync(resolve(mainRoot, 'database/migration-manager.ts'), 'utf8')
    expect(mm).toContain("import SCHEMA_018 from './schema/018-agent-traces.sql?raw'")
    expect(mm).toContain("filename: '018-agent-traces.sql'")
  })
})

describe('Phase 11 P11-11: transformAgentTraceRow', () => {
  it('典型 PG row → desktop row', async () => {
    const { transformAgentTraceRow } = await import('../../../src/main/migration/pg-snapshot/transformers/agent-traces')
    const lookup = new Map<number, string>([[1, 'wangtianzhi']])
    const pgRow = {
      id: 100, session_id: 'sess-001', agent_name: 'scientific',
      trace_type: 'tool_use', role: 'assistant',
      content: '调用工具 x', tool_name: 'run_kinetic',
      tool_input: '{"experimentId":"e1"}', tool_output: '{"k":0.05}',
      duration_ms: 120, user_id: 1, created_at: '2026-08-26 10:00:00+08'
    }
    const out = transformAgentTraceRow(pgRow, lookup)
    expect(out.web_id).toBe(100)
    expect(out.session_id).toBe('sess-001')
    expect(out.agent_name).toBe('scientific')
    expect(out.trace_type).toBe('tool_use')
    expect(out.tool_name).toBe('run_kinetic')
    expect(out.duration_ms).toBe(120)
    expect(out.owner_username).toBe('wangtianzhi')
  })

  it('trace_type web "tool_call" → desktop "tool_use" (兼容映射)', async () => {
    const { transformAgentTraceRow } = await import('../../../src/main/migration/pg-snapshot/transformers/agent-traces')
    const out = transformAgentTraceRow({ id: 1, trace_type: 'tool_call' }, null)
    expect(out.trace_type).toBe('tool_use')
  })

  it('trace_type web "tool_response" → desktop "tool_result"', async () => {
    const { transformAgentTraceRow } = await import('../../../src/main/migration/pg-snapshot/transformers/agent-traces')
    const out = transformAgentTraceRow({ id: 1, trace_type: 'tool_response' }, null)
    expect(out.trace_type).toBe('tool_result')
  })

  it('7 个 desktop trace_type 全部保留', async () => {
    const { transformAgentTraceRow } = await import('../../../src/main/migration/pg-snapshot/transformers/agent-traces')
    for (const t of ['tool_use', 'tool_result', 'message', 'system', 'error', 'plan', 'reflection']) {
      const out = transformAgentTraceRow({ id: 1, trace_type: t }, null)
      expect(out.trace_type).toBe(t)
    }
  })

  it('未知 trace_type 降级到 system (不抛错, 保护数据完整性)', async () => {
    const { transformAgentTraceRow } = await import('../../../src/main/migration/pg-snapshot/transformers/agent-traces')
    const out = transformAgentTraceRow({ id: 1, trace_type: 'unknown_type_xyz' }, null)
    expect(out.trace_type).toBe('system')
  })
})

describe('Phase 11 P11-11: transformActivityEventRow', () => {
  it('典型 PG row → desktop row', async () => {
    const { transformActivityEventRow } = await import('../../../src/main/migration/pg-snapshot/transformers/agent-traces')
    const lookup = new Map<number, string>([[1, 'wangtianzhi']])
    const pgRow = {
      id: 200, user_id: 1, event_type: 'view',
      resource_type: 'task', resource_id: '42',
      action: 'task.view', metadata: '{"duration_ms":1200}',
      ip_address: '192.168.1.100', user_agent: 'Mozilla/5.0...',
      created_at: '2026-08-26 10:00:00+08'
    }
    const out = transformActivityEventRow(pgRow, lookup)
    expect(out.web_id).toBe(200)
    expect(out.owner_username).toBe('wangtianzhi')
    expect(out.event_type).toBe('view')
    expect(out.resource_type).toBe('task')
    expect(out.resource_id).toBe('42')
    expect(out.ip_address).toBe('192.168.1.100')
    expect(out.user_agent).toBe('Mozilla/5.0...')
  })

  it('12 个 desktop event_type 全部保留', async () => {
    const { transformActivityEventRow } = await import('../../../src/main/migration/pg-snapshot/transformers/agent-traces')
    for (const t of ['view', 'edit', 'login', 'logout', 'create', 'delete', 'update', 'search', 'export', 'share', 'click', 'error']) {
      const out = transformActivityEventRow({ id: 1, event_type: t }, null)
      expect(out.event_type).toBe(t)
    }
  })

  it('未知 event_type 降级到 view', async () => {
    const { transformActivityEventRow } = await import('../../../src/main/migration/pg-snapshot/transformers/agent-traces')
    const out = transformActivityEventRow({ id: 1, event_type: 'unknown' }, null)
    expect(out.event_type).toBe('view')
  })
})

describe('Phase 11 P11-11: SELECT SQL safety', () => {
  it('两个 SELECT 都 SELECT-only', async () => {
    const { AGENT_TRACES_SELECT_SQL, ACTIVITY_EVENTS_SELECT_SQL } = await import('../../../src/main/migration/pg-snapshot/transformers/agent-traces')
    expect(AGENT_TRACES_SELECT_SQL.trim().toUpperCase()).toMatch(/^SELECT/)
    expect(ACTIVITY_EVENTS_SELECT_SQL.trim().toUpperCase()).toMatch(/^SELECT/)
    expect(AGENT_TRACES_SELECT_SQL).toContain('FROM agent_traces')
    expect(ACTIVITY_EVENTS_SELECT_SQL).toContain('FROM activity_events')
    for (const sql of [AGENT_TRACES_SELECT_SQL, ACTIVITY_EVENTS_SELECT_SQL]) {
      expect(/\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|GRANT|REVOKE)\b/i.test(sql)).toBe(false)
    }
  })
})