// Meetings Transformer — Phase 11 P11-2
// 单向: web PG meetings + meeting_participants + meeting_templates → desktop 镜像.
// 大字段 (transcript / polished / agenda / speaker_mapping) 不入 SQLite, 仅存 web URL.

import { applyTransformers, pgJsonToJsonString, pgTimestampToEpochMs } from '../transform-pipeline'
import type { TransformerMap } from '../transform-pipeline'

const WHITELIST_STATUS = ['scheduled', 'recording', 'processing', 'completed', 'error']
const WHITELIST_UPLOAD = ['pending', 'uploading', 'completed', 'failed', 'never_uploaded', 'partial']
const WHITELIST_PARTICIPANT_ROLE = ['host', 'presenter', 'participant']

/** 转换单行 web meetings → desktop_meetings row. */
export function transformMeetingRow(pgRow: Record<string, unknown>): Record<string, unknown> {
  const map: TransformerMap = {
    title: (v) => (v == null ? '' : String(v)),
    description: (v) => (v == null ? null : String(v)),
    start_time_epoch: (v) => pgTimestampToEpochMs(v),
    end_time_epoch: (v) => pgTimestampToEpochMs(v),
    location: (v) => (v == null ? null : String(v)),
    meeting_url: (v) => (v == null ? null : String(v)),
    meeting_external_id: (v) => (v == null ? null : String(v)),
    transcript_web_url: (v) => (v == null ? null : String(v)),
    audio_url: (v) => (v == null ? null : String(v)),
    audio_duration_seconds: (v) => (v == null ? null : Number(v) || null),
    summary: (v) => (v == null ? null : String(v)),
    key_points_json: (v) => pgJsonToJsonString(v) ?? '[]',
    decisions_json: (v) => pgJsonToJsonString(v) ?? '[]',
    speaker_stats_json: (v) => pgJsonToJsonString(v) ?? '[]',
    status: (v) => validateEnum(v, 'status', WHITELIST_STATUS, 'scheduled'),
    upload_status: (v) => validateEnum(v, 'upload_status', WHITELIST_UPLOAD, 'pending'),
    processing_status: (v) => (v == null ? null : String(v)),
    quality_status: (v) => (v == null ? null : String(v)),
    media_duration_seconds: (v) => (v == null ? null : Number(v) || null),
    related_meeting_ids_json: (v) => pgJsonToJsonString(v) ?? '[]',
    presenter_ids_json: (v) => pgJsonToJsonString(v) ?? '[]',
    creator_username: (v) => (v == null ? null : String(v)),
    embedding_model_version: (v) => (v == null ? 'qwen3-0.6b' : String(v)),
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

/** web meeting_participants → desktop_meeting_participants row.
 *  pgRow 含 meeting_id + member_id (PG 列名); caller 负责 member_id → username 查表.
 *  Transformer 输出 desktop 列名 (meeting_web_id / member_username). */
export function transformParticipantRow(
  pgRow: Record<string, unknown>,
  memberUsernameLookup: Map<number, string> | null
): Record<string, unknown> {
  const meetingId = pgRow['meeting_id']
  const memberId = pgRow['member_id']
  const map: TransformerMap = {
    meeting_web_id: () => (meetingId == null ? null : Number(meetingId) || null),
    member_username: () => (memberUsernameLookup && memberId != null ? (memberUsernameLookup.get(Number(memberId)) ?? null) : null),
    role: (v) => validateEnum(v, 'role', WHITELIST_PARTICIPANT_ROLE, 'participant'),
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

/** web meeting_templates → desktop_meeting_templates row. */
export function transformMeetingTemplateRow(pgRow: Record<string, unknown>): Record<string, unknown> {
  const map: TransformerMap = {
    name: (v) => (v == null ? '' : String(v)),
    description: (v) => (v == null ? null : String(v)),
    agenda_json: (v) => pgJsonToJsonString(v) ?? '[]',
    duration_minutes: (v) => (v == null ? null : Number(v) || null),
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

function validateEnum(raw: unknown, name: string, whitelist: ReadonlyArray<string>, fallback: string): string {
  if (raw == null) return fallback
  const s = String(raw)
  if (whitelist.includes(s)) return s
  throw new Error(`Invalid meeting ${name}: '${s}' not in [${whitelist.join(', ')}]`)
}

export const MEETINGS_SELECT_SQL = `
  SELECT
    id, title, description,
    start_time, end_time,
    location, meeting_url, meeting_id,
    transcript, transcript_polished, summary,
    cluster_id_history, key_points, decisions,
    speaker_mapping, speaker_stats,
    status, upload_status, last_chunk_index, total_chunks, error_reason,
    audio_url, audio_duration, recording_started_at, recording_ended_at,
    processing_status, quality_status, media_duration_seconds, last_processing_run_id,
    user_agent, agenda, related_meeting_ids, presenter_ids,
    created_by
  FROM meetings
  ORDER BY id ASC
`

export const MEETING_PARTICIPANTS_SELECT_SQL = `
  SELECT id, meeting_id, member_id, role
  FROM meeting_participants
  ORDER BY id ASC
`

export const MEETING_TEMPLATES_SELECT_SQL = `
  SELECT id, name, description, agenda, duration_minutes
  FROM meeting_templates
  ORDER BY id ASC
`