// CanonicalMessage utility (Phase 6-A1: Model Provider Foundation).
//
// Convert between Phase 3-A ChatMessageOut and CanonicalMessage.
// Phase 3-A message_metadata preserved for round-trip.

import type { ChatMessageOut } from '@shared/chat-types'
import type { CanonicalMessage } from './provider-types'

/**
 * Phase 6-A1: convert ChatMessageOut -> CanonicalMessage.
 *
 * - role: ChatMessageRole (Phase 3-A) -> 4 standard roles
 * - content: message.content (string)
 * - tool_call_id: message_metadata.tool_call_id (Phase 3-A)
 * - name: message_metadata.name (Phase 3-A tool name field)
 *
 * Phase 3-A non-standard roles (Phase 6-A1 NOT supported, Phase 6-A2+):
 * - 'thinking' / 'synthesis' / etc. (Phase 5-B AgentState) -> drop silently
 */
export function toCanonicalMessage(msg: ChatMessageOut): CanonicalMessage | null {
  const role = msg.role
  // Phase 3-A -> Phase 6-A1 standard roles mapping
  let standardRole: CanonicalMessage['role']
  if (role === 'user') standardRole = 'user'
  else if (role === 'assistant') standardRole = 'assistant'
  else if (role === 'tool') standardRole = 'tool'
  else if (role === 'system') standardRole = 'system'
  else return null // unsupported role, drop silently

  const m = msg.message_metadata as
    | { tool_call_id?: string; name?: string }
    | undefined

  const out: CanonicalMessage = {
    role: standardRole,
    content: msg.content
  }
  if (m?.tool_call_id && standardRole === 'tool') out.tool_call_id = m.tool_call_id
  if (m?.name && standardRole === 'tool') out.name = m.name
  return out
}

/**
 * Phase 6-A1: convert array of ChatMessageOut -> CanonicalMessage[].
 * Filters out unsupported roles silently (Phase 6-A2+ supports more roles).
 */
export function toCanonicalMessages(msgs: ChatMessageOut[]): CanonicalMessage[] {
  const out: CanonicalMessage[] = []
  for (const m of msgs) {
    const c = toCanonicalMessage(m)
    if (c !== null) out.push(c)
  }
  return out
}

/**
 * Phase 6-A1: convert CanonicalMessage -> ChatMessageOut (round-trip).
 *
 * - role: 4 standard roles
 * - content: content
 * - tool_call_id -> message_metadata.tool_call_id
 * - name -> message_metadata.name
 * - id (msg.id) -> client_msg_id (Phase 3-A convention)
 */
export function fromCanonicalMessage(
  c: CanonicalMessage,
  opts: { id?: number | string; createdAt?: string } = {}
): ChatMessageOut {
  const md: Record<string, unknown> = {}
  if (c.tool_call_id) md.tool_call_id = c.tool_call_id
  if (c.name) md.name = c.name
  return {
    id: typeof opts.id === 'number' ? opts.id : 0,
    session_id: '',
    role: c.role,
    content: c.content,
    rich_blocks: [],
    tool_trace: [],
    message_metadata: md,
    is_partial: false,
    is_deleted: false,
    client_msg_id: c.tool_call_id ?? null,
    attached_knowledge_ids: [],
    image_url: null,
    created_at: opts.createdAt ?? new Date().toISOString()
  }
}
