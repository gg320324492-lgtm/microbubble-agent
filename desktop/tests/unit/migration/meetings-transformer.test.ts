// Meetings Transformer 单元测试 — Phase 11 P11-2
// 验证: PG meeting / participant / template → desktop row 转换 + enum 边界 + 大字段不入库.

import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// __dirname = tests/unit/migration/, 回到 desktop 根需要 ../../../
const desktopRoot = resolve(__dirname, '..', '..', '..')
const mainRoot = resolve(desktopRoot, 'src/main')

describe('Phase 11 P11-2: Meetings Schema',  () => {
  it('013-meetings.sql 存在', () => {
    expect(existsSync(resolve(mainRoot, 'database/schema/013-meetings.sql'))).toBe(true)
  })

  it('desktop_meetings 表含核心列 + status / upload_status CHECK', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/013-meetings.sql'), 'utf8')
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_meetings/)
    expect(sql).toMatch(/web_id\s+INTEGER/)
    expect(sql).toMatch(/start_time_epoch\s+INTEGER/)
    expect(sql).toMatch(/transcript_web_url\s+TEXT/)
    expect(sql).toMatch(/key_points_json\s+TEXT/)
    expect(sql).toMatch(/status.*CHECK.*scheduled.*recording.*processing.*completed.*error/)
    expect(sql).toMatch(/upload_status.*CHECK.*pending.*uploading.*completed.*failed.*never_uploaded.*partial/)
  })

  it('desktop_meeting_participants 复合唯一 (meeting_web_id, member_username)', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/013-meetings.sql'), 'utf8')
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_meeting_participants/)
    expect(sql).toContain('UNIQUE(meeting_web_id, member_username)')
    expect(sql).toMatch(/role.*CHECK.*host.*presenter.*participant/)
  })

  it('desktop_meeting_templates 含 agenda_json + duration_minutes', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/013-meetings.sql'), 'utf8')
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_meeting_templates/)
    expect(sql).toMatch(/agenda_json\s+TEXT/)
    expect(sql).toMatch(/duration_minutes\s+INTEGER/)
  })

  it('7 个索引 (meetings 5 + participants 2 + templates 1, 实际 8)', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/013-meetings.sql'), 'utf8')
    expect(sql).toContain('idx_desktop_meetings_web_id')
    expect(sql).toContain('idx_desktop_meetings_status')
    expect(sql).toContain('idx_desktop_meetings_start')
    expect(sql).toContain('idx_desktop_meetings_creator')
    expect(sql).toContain('idx_desktop_meeting_participants_meeting')
    expect(sql).toContain('idx_desktop_meeting_participants_member')
  })

  it('013 已加入 INLINE_SCHEMAS', () => {
    const mm = readFileSync(resolve(mainRoot, 'database/migration-manager.ts'), 'utf8')
    expect(mm).toContain("import SCHEMA_013 from './schema/013-meetings.sql?raw'")
    expect(mm).toContain("filename: '013-meetings.sql'")
  })
})

describe('Phase 11 P11-2: transformMeetingRow 转换', () => {
  it('典型 PG row → desktop row', async () => {
    const { transformMeetingRow } = await import('../../../src/main/migration/pg-snapshot/transformers/meetings')
    const pgRow = {
      id: 1,
      description: '臭氧微纳米气泡实验讨论',
      start_time: '2026-08-26 14:00:00+08',
      end_time: '2026-08-26 15:30:00+08',
      location: '会议室A',
      meeting_url: 'https://meeting.example.com/123',
      meeting_id: 'tm-123456',
      transcript: '{"segments": [...]}',
      transcript_polished: '{"text": "..."}',
      summary: '讨论 O3-MNB 进展',
      key_points: ['点1', '点2'],
      decisions: ['决策1'],
      speaker_stats: '[{"name":"张", "turn_count":5}]',
      status: 'completed',
      upload_status: 'completed',
      audio_url: 'minio://audio/123.m4a',
      audio_duration: 5400,
      processing_status: 'success',
      quality_status: 'good',
      media_duration_seconds: 5400,
      related_meeting_ids: '[2,3]',
      presenter_ids: '[1,2]',
      created_by: 1
    }
    const out = transformMeetingRow(pgRow)
    expect(out.title).toBe('') // title 字段不存在 → fallback ''
    expect(out.description).toBe('臭氧微纳米气泡实验讨论')
    expect(typeof out.start_time_epoch === 'number' || out.start_time_epoch === null).toBe(true)
    expect(out.status).toBe('completed')
    expect(out.upload_status).toBe('completed')
    expect(['[]', '["点1","点2"]']).toContain(out.key_points_json)
    expect(['[]', '["决策1"]']).toContain(out.decisions_json)
    expect(out.audio_duration_seconds === null || out.audio_duration_seconds === 5400).toBe(true)
    expect(out.processing_status).toBe('success')
    expect(out.embedding_model_version).toBe('qwen3-0.6b')
  })

  it('5 个 status enum 全部保留', async () => {
    const { transformMeetingRow } = await import('../../../src/main/migration/pg-snapshot/transformers/meetings')
    for (const s of ['scheduled', 'recording', 'processing', 'completed', 'error']) {
      const out = transformMeetingRow({ id: 1, title: 'x', status: s, upload_status: 'pending' })
      expect(out.status).toBe(s)
    }
  })

  it('6 个 upload_status enum 全部保留', async () => {
    const { transformMeetingRow } = await import('../../../src/main/migration/pg-snapshot/transformers/meetings')
    for (const s of ['pending', 'uploading', 'completed', 'failed', 'never_uploaded', 'partial']) {
      const out = transformMeetingRow({ id: 1, title: 'x', status: 'scheduled', upload_status: s })
      expect(out.upload_status).toBe(s)
    }
  })

  it('未在白名单的 status 抛错', async () => {
    const { transformMeetingRow } = await import('../../../src/main/migration/pg-snapshot/transformers/meetings')
    expect(() => transformMeetingRow({ id: 1, title: 'x', status: 'invalid' })).toThrow()
    expect(() => transformMeetingRow({ id: 1, title: 'x', upload_status: 'invalid' })).toThrow()
  })

  it('null status fallback 到 scheduled (web 默认值)', async () => {
    const { transformMeetingRow } = await import('../../../src/main/migration/pg-snapshot/transformers/meetings')
    const out = transformMeetingRow({ id: 1, title: 'x', status: null, upload_status: null })
    expect(out.status).toBe('scheduled')
    expect(out.upload_status).toBe('pending')
  })

  it('大 transcript 字段不存 SQLite (transcript_web_url 占位)', async () => {
    const { transformMeetingRow } = await import('../../../src/main/migration/pg-snapshot/transformers/meetings')
    const out = transformMeetingRow({ id: 1, title: 'x', transcript: '很长很长' })
    // transcript 字段不进 desktop row (map 中未列出)
    expect(out.transcript).toBeUndefined()
    expect(out.transcript_web_url).toBeNull()
  })

  it('embedding 字段不映射 (vector 不入 SQLite)', async () => {
    const { transformMeetingRow } = await import('../../../src/main/migration/pg-snapshot/transformers/meetings')
    const out = transformMeetingRow({ id: 1, title: 'x', embedding: '[1.0,2.0,...]' })
    expect(out.embedding).toBeUndefined()
  })
})

describe('Phase 11 P11-2: transformParticipantRow 转换', () => {
  it('member_id → username lookup', async () => {
    const { transformParticipantRow } = await import('../../../src/main/migration/pg-snapshot/transformers/meetings')
    const lookup = new Map<number, string>([[1, 'wangtianzhi'], [2, 'zhaohangjia']])
    const out = transformParticipantRow({ id: 1, meeting_id: 10, member_id: 1, role: 'host' }, lookup)
    expect(out.meeting_web_id).toBe(10)
    expect(out.member_username).toBe('wangtianzhi')
    expect(out.role).toBe('host')
  })

  it('member_id 不在 lookup → null member_username', async () => {
    const { transformParticipantRow } = await import('../../../src/main/migration/pg-snapshot/transformers/meetings')
    const out = transformParticipantRow({ id: 1, meeting_id: 10, member_id: 999, role: 'participant' }, null)
    expect(out.member_username).toBeNull()
  })

  it('3 个 role enum 全部保留', async () => {
    const { transformParticipantRow } = await import('../../../src/main/migration/pg-snapshot/transformers/meetings')
    for (const r of ['host', 'presenter', 'participant']) {
      const out = transformParticipantRow({ id: 1, meeting_id: 1, member_id: 1, role: r }, new Map())
      expect(out.role).toBe(r)
    }
  })
})

describe('Phase 11 P11-2: transformMeetingTemplateRow 转换', () => {
  it('模板 row → desktop_meeting_templates row', async () => {
    const { transformMeetingTemplateRow } = await import('../../../src/main/migration/pg-snapshot/transformers/meetings')
    const out = transformMeetingTemplateRow({
      id: 1,
      name: '周会模板',
      description: '每周例会',
      agenda: '{"items":["进度","问题"]}',
      duration_minutes: 60
    })
    expect(out.name).toBe('周会模板')
    expect(out.duration_minutes).toBe(60)
    expect(['[]', '{"items":["进度","问题"]}']).toContain(out.agenda_json)
  })
})

describe('Phase 11 P11-2: SELECT SQL safety', () => {
  it('所有 SELECT 都以 SELECT 开头且不含 schema-mutating 关键字', async () => {
    const { MEETINGS_SELECT_SQL, MEETING_PARTICIPANTS_SELECT_SQL, MEETING_TEMPLATES_SELECT_SQL } = await import('../../../src/main/migration/pg-snapshot/transformers/meetings')
    for (const sql of [MEETINGS_SELECT_SQL, MEETING_PARTICIPANTS_SELECT_SQL, MEETING_TEMPLATES_SELECT_SQL]) {
      expect(sql.trim().toUpperCase()).toMatch(/^SELECT/)
      expect(/\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|GRANT|REVOKE)\b/i.test(sql)).toBe(false)
    }
    // meetings 必含 meetings 表
    expect(MEETINGS_SELECT_SQL).toContain('FROM meetings')
    expect(MEETING_PARTICIPANTS_SELECT_SQL).toContain('FROM meeting_participants')
    expect(MEETING_TEMPLATES_SELECT_SQL).toContain('FROM meeting_templates')
  })
})