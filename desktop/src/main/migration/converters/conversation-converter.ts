import type { MbrpInput } from '../mbrp-types';

interface ChatRecord {
  id: string;
  user_id: string;
  role: string;
  content: string;
  session_id: string;
  source_updated_at?: string;
  [k: string]: unknown;
}

export interface ConvertConversationsResult {
  entities: NonNullable<MbrpInput['entities']>['conversations'];
  files: MbrpInput['files'];
}

export function convertConversations(
  records: ChatRecord[],
): ConvertConversationsResult {
  const files: MbrpInput['files'] = [];
  const entities: NonNullable<MbrpInput['entities']>['conversations'] = [];

  const bySession = new Map<string, ChatRecord[]>();
  for (const r of records) {
    const sid = r.session_id;
    if (!bySession.has(sid)) bySession.set(sid, []);
    bySession.get(sid)!.push(r);
  }

  const sortedSessionIds = Array.from(bySession.keys()).sort();

  for (const sessionId of sortedSessionIds) {
    const msgs = bySession.get(sessionId)!;

    msgs.sort((a, b) =>
      String(a.source_updated_at ?? '').localeCompare(String(b.source_updated_at ?? '')) ||
      String(a.id).localeCompare(String(b.id)),
    );

    entities.push({ id: sessionId });

    const md = [
      `# Conversation ${sessionId}`,
      '',
      `**Session**: ${sessionId}`,
      `**Messages**: ${msgs.length}`,
      `**Generated**: ${msgs[msgs.length - 1]?.source_updated_at ?? ''}`,
      '',
      '---',
      '',
      ...msgs.flatMap((m) => [
        `### ${m.role} (${m.source_updated_at ?? '?'})`,
        '',
        m.content,
        '',
        '---',
        '',
      ]),
    ].join('\n');

    const json = {
      sessionId,
      generatedAt: msgs[msgs.length - 1]?.source_updated_at ?? '',
      messageCount: msgs.length,
      messages: msgs.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        author_id: m.user_id,
        timestamp: m.source_updated_at,
      })),
    };

    files.push({ path: `conversations/${sessionId}.md`, content: md });
    files.push({ path: `conversations/${sessionId}.json`, content: JSON.stringify(json, null, 2) });
  }

  return { entities, files };
}
