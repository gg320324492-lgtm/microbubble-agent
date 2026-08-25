import type { MbrpInput } from '../mbrp-types';

interface KnowledgeRecord {
  id: string;
  title: string;
  summary?: string;
  content?: string;
  category?: string;
  tags?: string[] | string;
  source?: string;
  source_updated_at?: string;
  [k: string]: unknown;
}

export interface ConvertKnowledgeResult {
  entities: NonNullable<MbrpInput['entities']>['knowledge'];
  files: MbrpInput['files'];
}

export function convertKnowledge(records: KnowledgeRecord[]): ConvertKnowledgeResult {
  const files: MbrpInput['files'] = [];
  const entities: NonNullable<MbrpInput['entities']>['knowledge'] = [];

  for (const k of records) {
    entities.push({ id: k.id, title: k.title });

    const tags = Array.isArray(k.tags)
      ? k.tags
      : typeof k.tags === 'string'
        ? k.tags.split(',').map((s) => s.trim()).filter(Boolean)
        : [];

    const metadata = {
      id: k.id,
      title: k.title,
      summary: k.summary ?? '',
      category: k.category ?? 'uncategorized',
      tags,
      source: k.source ?? '',
      lastUpdated: k.source_updated_at ?? '',
      editable: true,
      path: `knowledge/${k.id}/doc.md`,
    };

    const doc = [
      `# ${k.title}`,
      '',
      k.summary ?? '',
      '',
      '## Metadata',
      '',
      `- **ID**: ${k.id}`,
      `- **Category**: ${k.category ?? 'uncategorized'}`,
      `- **Tags**: ${tags.join(', ') || '_none_'}`,
      `- **Source**: ${k.source ?? '_unknown_'}`,
      `- **Last updated**: ${k.source_updated_at ?? '_unknown_'}`,
      '',
      '## Body',
      '',
      k.content ?? '_No body content in snapshot; add locally after import._',
    ].join('\n');

    files.push({
      path: `knowledge/${k.id}/metadata.json`,
      content: JSON.stringify(metadata, null, 2),
    });
    files.push({
      path: `knowledge/${k.id}/doc.md`,
      content: doc,
    });
  }

  return { entities, files };
}
