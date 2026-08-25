/**
 * semantic-converter.ts — convert a loaded web snapshot to a `.mbrp` package.
 *
 * R3 of the adaptive release program. Reads an in-memory snapshot payload
 * (already loaded by the caller; no DB / no network access) and emits a
 * deterministic `.mbrp` archive.
 *
 * Determinism: the resulting zip bytes are bytewise identical for the same
 * snapshot input across runs. We achieve this by:
 *   1. Sorting the file list by path before serialization (matches R1's
 *      `buildManifest` ordering so manifest entries line up).
 *   2. Using a deterministic `createdAt` (the snapshot's `endedAt`),
 *      not `new Date()`.
 *   3. Setting every ZIP entry's DOS modification time to a fixed epoch
 *      (1980-01-01) so adm-zip's default `new Date()` per-entry time
 *      cannot leak into the central directory.
 *
 * Note: the R1 `createMbrp` uses `new Date()` for both `createdAt` and
 * per-entry timestamps, which would make two consecutive runs of the same
 * snapshot produce different SHA-256s. We bypass it here so R3 keeps the
 * "deterministic" contract; the public API shape (`MbrpInput` /`MbrpManifest`)
 * stays identical so consumers (R4 importer, tests) see no change.
 */

import { createHash } from 'node:crypto';
import { existsSync } from 'node:fs';
import AdmZip from 'adm-zip';
import type {
  MbrpInput,
  MbrpManifest,
  MbrpFileEntry,
} from './mbrp-types';
import { convertProjects } from './converters/project-converter';
import { convertMeetings } from './converters/meeting-converter';
import { convertKnowledge } from './converters/knowledge-converter';
import { convertConversations } from './converters/conversation-converter';

/** A loaded snapshot as produced by the R2 exporter. */
export interface SnapshotPayload {
  /** Directory the snapshot was loaded from (for diagnostics / manifest echo). */
  snapshotDir: string;
  /** The parsed snapshot-manifest.json. */
  manifest: {
    snapshot_id?: string;
    startedAt?: string;
    endedAt?: string;
    files?: Array<{ name: string }>;
    [k: string]: unknown;
  };
  /** Records keyed by NDJSON file basename without the `.ndjson` extension. */
  records: Record<string, any[]>;
}

export interface ConvertOptions {
  snapshot: SnapshotPayload;
  outputPath: string;
  /**
   * Whether to mark the produced package as having come from an untouched
   * web/system stack. Defaults to `true`. R4 may downgrade this if it
   * detects post-export drift.
   */
  webUntouched?: boolean;
}

/**
 * Convert an in-memory snapshot to a deterministic `.mbrp` package.
 * No database or network access is performed.
 */
export async function convertSnapshotToMbrp(opts: ConvertOptions): Promise<MbrpManifest> {
  const { snapshot, outputPath, webUntouched = true } = opts;
  const { manifest, records } = snapshot;

  // 1) Compose all converters' outputs
  const projOut = convertProjects(records.projects ?? [], records.tasks ?? []);
  const meetOut = convertMeetings(records.meetings ?? []);
  const knowOut = convertKnowledge(records.knowledge ?? []);
  const convOut = convertConversations(records.chat ?? []);

  const allFiles = [
    ...projOut.files,
    ...meetOut.files,
    ...knowOut.files,
    ...convOut.files,
  ];

  // 2) Deterministic createdAt: prefer snapshot.endedAt (set once at capture
  //    time), fall back to startedAt, then a fixed epoch. NEVER use new Date().
  const deterministicCreatedAt =
    (typeof manifest.endedAt === 'string' && manifest.endedAt) ||
    (typeof manifest.startedAt === 'string' && manifest.startedAt) ||
    '1970-01-01T00:00:00.000Z';

  const sourceSnapshot = {
    capturedAt:
      (typeof manifest.endedAt === 'string' && manifest.endedAt) ||
      (typeof manifest.startedAt === 'string' && manifest.startedAt) ||
      deterministicCreatedAt,
    capturedCommit:
      (typeof manifest.snapshot_id === 'string' && manifest.snapshot_id) || '',
    webUntouched,
  };

  const input: MbrpInput = {
    entities: {
      projects: projOut.entities,
      meetings: meetOut.entities,
      knowledge: knowOut.entities,
      conversations: convOut.entities,
    },
    files: allFiles,
    sourceSnapshot,
  };

  // 3) Build the manifest deterministically, then serialize to a zip with
  //    fixed DOS timestamps so the byte stream is reproducible.
  return await writeDeterministicMbrp(outputPath, input, deterministicCreatedAt);
}

/**
 * Convenience loader: read snapshot-manifest.json + all *.ndjson files
 * from a directory into an in-memory SnapshotPayload. Useful for R3 tests
 * and CLI entry points.
 */
export async function loadSnapshotFromDir(snapshotDir: string): Promise<SnapshotPayload> {
  const fs = await import('node:fs/promises');
  const path = await import('node:path');

  const manifestPath = path.join(snapshotDir, 'snapshot-manifest.json');
  if (!existsSync(manifestPath)) {
    throw new Error(`Snapshot manifest not found: ${manifestPath}`);
  }
  const manifest = JSON.parse(await fs.readFile(manifestPath, 'utf8'));
  const records: Record<string, any[]> = {};
  const fileList: Array<{ name: string }> = manifest.files ?? [];
  for (const f of fileList) {
    if (!f.name.endsWith('.ndjson')) continue;
    const text = await fs.readFile(path.join(snapshotDir, f.name), 'utf8');
    records[f.name.replace(/\.ndjson$/, '')] = text
      .split('\n')
      .map((l: string) => l.trim())
      .filter(Boolean)
      .map((l: string) => JSON.parse(l));
  }
  return { snapshotDir, manifest, records };
}

// ---------------------------------------------------------------------------
// Deterministic serialization helpers
// ---------------------------------------------------------------------------

/**
 * Build a manifest from a raw input. Mirrors R1's `buildManifest` so the
 * resulting manifest is bytewise identical to what R1's verifier expects
 * (formatVersion, createdAt, sourceSnapshot, entities, files sorted by
 * path with sha256/size, warnings).
 */
function buildDeterministicManifest(
  input: MbrpInput,
  createdAt: string,
): MbrpManifest {
  const sortedFiles = [...input.files].sort((a, b) =>
    a.path.localeCompare(b.path),
  );
  const entries: MbrpFileEntry[] = sortedFiles.map((f) => {
    const buf = typeof f.content === 'string' ? Buffer.from(f.content, 'utf8') : f.content;
    return {
      path: f.path,
      sha256: createHash('sha256').update(buf).digest('hex'),
      size: buf.length,
    };
  });

  return {
    formatVersion: 1,
    createdAt,
    sourceSnapshot: {
      capturedAt: input.sourceSnapshot?.capturedAt ?? createdAt,
      capturedCommit: input.sourceSnapshot?.capturedCommit ?? '',
      webUntouched: input.sourceSnapshot?.webUntouched ?? true,
    },
    entities: input.entities,
    files: entries,
    warnings: [],
  };
}

/**
 * Epoch 1980-01-01 00:00:00 — the earliest date representable in the DOS
 * time format used by ZIP local headers. Using a fixed value strips the
 * `new Date()` noise adm-zip would otherwise inject per entry.
 */
const ZIP_EPOCH_TIME = new Date(0);

/**
 * Write a deterministic `.mbrp` archive:
 *   - file entries sorted by path (so manifest order matches zip order)
 *   - all entry DOS times pinned to ZIP_EPOCH_TIME
 *   - manifest.createdAt fixed (passed by caller)
 *   - entities written in canonical (input) order
 *
 * Uses adm-zip directly because R1's `createMbrp` (R1 file, not modifiable
 * from R3) uses `new Date()` for both `createdAt` and per-entry
 * timestamps, which would break SHA-256 determinism across runs.
 */
async function writeDeterministicMbrp(
  outPath: string,
  input: MbrpInput,
  createdAt: string,
): Promise<MbrpManifest> {
  const zip = new AdmZip();

  // Build the manifest first so its entries drive the zip order.
  const manifest = buildDeterministicManifest(input, createdAt);

  // 1) Write all content files in the same order they appear in the manifest.
  const contentByPath = new Map<string, { content: string | Buffer }>();
  for (const f of input.files) {
    contentByPath.set(f.path, f);
  }
  for (const entry of manifest.files) {
    const f = contentByPath.get(entry.path);
    if (!f) {
      throw new Error(`internal: manifest entry has no content: ${entry.path}`);
    }
    const buf =
      typeof f.content === 'string' ? Buffer.from(f.content, 'utf8') : f.content;
    const zipEntry = zip.addFile(entry.path, buf);
    zipEntry.header.time = ZIP_EPOCH_TIME;
  }

  // 2) Write manifest.json last with the same fixed DOS time.
  const manifestBytes = Buffer.from(JSON.stringify(manifest, null, 2), 'utf8');
  const manifestEntry = zip.addFile('manifest.json', manifestBytes);
  manifestEntry.header.time = ZIP_EPOCH_TIME;

  zip.writeZip(outPath);
  return manifest;
}
