/**
 * mbrp-manifest.ts — build & validate an `.mbrp` manifest.
 *
 * Separated from mbrp-archive so manifest logic (hashing, sorting, shape
 * checking) is reusable in places that don't need a zip (e.g. R3 in-memory
 * transform).
 */

import { createHash } from 'node:crypto';
import type { MbrpInput, MbrpManifest, MbrpFileEntry } from './mbrp-types';

/**
 * Build a manifest from a raw input. File entries are sorted by path to make
 * the resulting JSON deterministic — that matters for bytewise diffing
 * archives produced from the same source.
 */
export function buildManifest(input: MbrpInput): MbrpManifest {
  const sortedFiles = [...input.files].sort((a, b) => a.path.localeCompare(b.path));
  const entries: MbrpFileEntry[] = sortedFiles.map((f) => {
    const buf = typeof f.content === 'string' ? Buffer.from(f.content, 'utf8') : f.content;
    return {
      path: f.path,
      sha256: createHash('sha256').update(buf).digest('hex'),
      size: buf.length,
    };
  });

  const now = new Date().toISOString();
  return {
    formatVersion: 1,
    createdAt: now,
    sourceSnapshot: {
      capturedAt: input.sourceSnapshot?.capturedAt ?? now,
      capturedCommit: input.sourceSnapshot?.capturedCommit ?? '',
      webUntouched: input.sourceSnapshot?.webUntouched ?? true,
    },
    entities: input.entities,
    files: entries,
    warnings: [],
  };
}

/**
 * Throws on malformed input. We only check the structural shape needed for
 * safe verification — entity content is opaque to this layer.
 */
export function validateManifestShape(m: unknown): asserts m is MbrpManifest {
  if (!m || typeof m !== 'object') {
    throw new Error('invalid manifest: not an object');
  }
  const o = m as Record<string, unknown>;
  if (o.formatVersion !== 1) {
    throw new Error(`invalid manifest: unsupported formatVersion: ${String(o.formatVersion)}`);
  }
  if (typeof o.createdAt !== 'string') {
    throw new Error('invalid manifest: createdAt must be string');
  }
  if (!o.entities || typeof o.entities !== 'object') {
    throw new Error('invalid manifest: entities missing');
  }
  if (!Array.isArray(o.files)) {
    throw new Error('invalid manifest: files must be array');
  }
}
