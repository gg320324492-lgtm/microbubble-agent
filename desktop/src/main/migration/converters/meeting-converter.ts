import type { MbrpInput } from '../mbrp-types';

interface MeetingRecord {
  id: string;
  title: string;
  agenda?: string;
  scheduled_at?: string;
  started_at?: string;
  ended_at?: string;
  created_by?: string;
  source_updated_at?: string;
  [k: string]: unknown;
}

export interface ConvertMeetingsResult {
  entities: NonNullable<MbrpInput['entities']>['meetings'];
  files: MbrpInput['files'];
}

export function convertMeetings(meetings: MeetingRecord[]): ConvertMeetingsResult {
  const files: MbrpInput['files'] = [];
  const entities: NonNullable<MbrpInput['entities']>['meetings'] = [];

  for (const m of meetings) {
    entities.push({ id: m.id, title: m.title });

    const record = [
      `# ${m.title}`,
      '',
      `**Meeting ID**: ${m.id}`,
      `**Scheduled**: ${m.scheduled_at ?? '_unknown_'}`,
      `**Started**: ${m.started_at ?? '_unknown_'}`,
      `**Ended**: ${m.ended_at ?? '_unknown_'}`,
      `**Created by**: ${m.created_by ?? '_unknown_'}`,
      `**Last updated**: ${m.source_updated_at ?? '_unknown_'}`,
      '',
      '## Agenda',
      '',
      m.agenda ?? '_No agenda recorded_',
      '',
      '## Notes',
      '',
      '_Transcript and notes will be imported separately once available._',
      '',
      '## Attachments',
      '',
      '_Attachments are referenced via SHA-256 in the original snapshot._',
    ].join('\n');

    files.push({ path: `meetings/${m.id}/record.md`, content: record });
  }

  return { entities, files };
}
