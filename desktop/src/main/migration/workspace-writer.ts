import { createHash } from 'node:crypto';
import { writeFileSync, mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';

export interface WorkspaceEntry {
  path: string;
  content: Buffer;
}

export interface WorkspaceWriteResult {
  path: string;
  content_sha256: string;
  size: number;
}

export class WorkspaceWriter {
  constructor(private readonly stagingRoot: string) {}

  async writeAll(entries: WorkspaceEntry[]): Promise<WorkspaceWriteResult[]> {
    const results: WorkspaceWriteResult[] = [];
    for (const entry of entries) {
      // 校验 path 安全（在 importer 里已校验过，这里只防 second-order 注入）
      if (entry.path.includes('..') || entry.path.startsWith('/')) {
        throw new Error(`WorkspaceWriter refused unsafe path: ${entry.path}`);
      }
      const fullPath = join(this.stagingRoot, entry.path);
      mkdirSync(dirname(fullPath), { recursive: true });
      writeFileSync(fullPath, entry.content);
      results.push({
        path: entry.path,
        content_sha256: createHash('sha256').update(entry.content).digest('hex'),
        size: entry.content.length,
      });
    }
    return results;
  }
}
