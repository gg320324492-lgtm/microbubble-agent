/**
 * mbrp-archive.ts — read/write verified `.mbrp` archives.
 *
 * Wraps `adm-zip` and bolts on:
 *   - safe-path validation (no traversal, no absolute, no backslash, no dot
 *     segments) so a maliciously-crafted entry name cannot escape the archive
 *     when a downstream consumer writes it back to disk
 *   - duplicate-entry detection (adm-zip happily lets two entries share a name
 *     if you reach past its public API; we enforce uniqueness both on write
 *     and on read)
 *   - SHA-256 verification of every manifest-listed file
 *   - extra-file detection (any zip entry not listed in the manifest fails
 *     verification — prevents silent addition of rogue payloads)
 *
 * All thrown errors carry an `MbrpErrorCode` (`code` property) so the verify
 * layer can convert them into structured `VerifyResult` codes.
 */

import AdmZip from 'adm-zip';
import { createHash } from 'node:crypto';
import type {
  MbrpInput,
  MbrpManifest,
  MbrpErrorCode,
  VerifyResult,
} from './mbrp-types';
import { buildManifest, validateManifestShape } from './mbrp-manifest';

/**
 * Allow-list pattern: forward slashes only, segments made of [A-Za-z0-9._-],
 * no leading dot, no trailing dot, no empty segments, no parent refs.
 * Conservative on purpose; R2 exporters can use whatever names they want as
 * long as they pass this filter.
 */
const SAFE_PATH_RE = /^(?!\/|\.\.|.*\/\.\.)[A-Za-z0-9._-]+(?:\/[A-Za-z0-9._-]+)*$/;

/**
 * Internal error type. Carries a stable machine-readable `code` alongside the
 * human-readable message, so `verifyMbrp` can map exceptions to `VerifyResult`
 * without parsing strings.
 */
export class MbrpArchiveError extends Error {
  constructor(
    public readonly code: MbrpErrorCode,
    message: string,
  ) {
    super(message);
    this.name = 'MbrpArchiveError';
  }
}

function validatePath(path: string): void {
  if (typeof path !== 'string' || path.length === 0) {
    throw new MbrpArchiveError('INVALID_PATH', 'invalid path: empty or non-string path');
  }
  if (path.includes('\\')) {
    throw new MbrpArchiveError('INVALID_PATH', `invalid path: backslash not allowed: ${path}`);
  }
  if (path.startsWith('/')) {
    throw new MbrpArchiveError('INVALID_PATH', `invalid path: absolute path not allowed: ${path}`);
  }
  const segments = path.split('/');
  if (segments.some((s) => s === '.' || s === '..')) {
    throw new MbrpArchiveError('INVALID_PATH', `invalid path: relative segment not allowed: ${path}`);
  }
  if (!SAFE_PATH_RE.test(path)) {
    throw new MbrpArchiveError('INVALID_PATH', `invalid path: invalid characters: ${path}`);
  }
}

/**
 * Assemble a new `.mbrp` archive at `outPath`. Returns the manifest that was
 * written (callers usually want to echo this back in the API response).
 *
 * Rejects duplicate paths in `input.files` — the manifest only carries one
 * entry per path, so accepting duplicates would silently lose data.
 */
export async function createMbrp(outPath: string, input: MbrpInput): Promise<MbrpManifest> {
  // Reject obviously bad input eagerly so we never write a partial archive.
  const seen = new Set<string>();
  for (const f of input.files) {
    validatePath(f.path);
    if (seen.has(f.path)) {
      throw new MbrpArchiveError('DUPLICATE_ENTRY', `duplicate entry: ${f.path}`);
    }
    seen.add(f.path);
  }

  const zip = new AdmZip();
  const manifest = buildManifest(input);

  // 1) Write all content files.
  for (const f of input.files) {
    const buf = typeof f.content === 'string' ? Buffer.from(f.content, 'utf8') : f.content;
    zip.addFile(f.path, buf);
  }
  // 2) Write manifest.json (literal entry name, no user input).
  zip.addFile('manifest.json', Buffer.from(JSON.stringify(manifest, null, 2), 'utf8'));
  zip.writeZip(outPath);
  return manifest;
}

/**
 * Open and parse an `.mbrp` archive. Throws `MbrpArchiveError` on any
 * structural problem; callers (`verifyMbrp`) translate those into
 * `VerifyResult` codes.
 */
export async function openMbrp(
  path: string,
): Promise<{ manifest: MbrpManifest; files: Map<string, Buffer> }> {
  let zip: AdmZip;
  try {
    zip = new AdmZip(path);
  } catch (err) {
    throw new MbrpArchiveError('BAD_ZIP', `bad zip: ${(err as Error).message}`);
  }
  const entries = zip.getEntries();

  // Detect duplicate entry names + validate every name before we read bytes.
  const names = new Set<string>();
  for (const e of entries) {
    if (names.has(e.entryName)) {
      throw new MbrpArchiveError('DUPLICATE_ENTRY', `duplicate entry: ${e.entryName}`);
    }
    names.add(e.entryName);
    validatePath(e.entryName);
  }

  // Locate manifest.json. Missing manifest is fatal — we cannot verify a
  // package that doesn't tell us what it claims to contain.
  const manifestEntry = entries.find((e) => e.entryName === 'manifest.json');
  if (!manifestEntry) {
    throw new MbrpArchiveError('INVALID_MANIFEST', 'invalid manifest: manifest.json missing');
  }

  let manifest: MbrpManifest;
  try {
    manifest = JSON.parse(manifestEntry.getData().toString('utf8')) as MbrpManifest;
  } catch (err) {
    throw new MbrpArchiveError(
      'INVALID_MANIFEST',
      `invalid manifest: parse failed: ${(err as Error).message}`,
    );
  }
  validateManifestShape(manifest);

  const files = new Map<string, Buffer>();
  for (const e of entries) {
    if (e.entryName === 'manifest.json') continue;
    files.set(e.entryName, e.getData());
  }

  return { manifest, files };
}

/**
 * Read-only integrity check. Never throws — every failure mode returns a
 * structured `VerifyResult` so callers can surface them in UI.
 */
export async function verifyMbrp(path: string): Promise<VerifyResult> {
  let opened;
  try {
    opened = await openMbrp(path);
  } catch (err) {
    if (err instanceof MbrpArchiveError) {
      return { ok: false, code: err.code, message: err.message };
    }
    return { ok: false, code: 'BAD_ZIP', message: (err as Error).message };
  }

  const { manifest, files } = opened;

  // Every manifest-listed file must exist and hash correctly.
  const listed = new Set<string>();
  for (const entry of manifest.files) {
    listed.add(entry.path);
    const actual = files.get(entry.path);
    if (!actual) {
      return {
        ok: false,
        code: 'MISSING_FILE',
        message: `manifest lists ${entry.path} but zip lacks it`,
        path: entry.path,
      };
    }
    const actualSha = createHash('sha256').update(actual).digest('hex');
    if (actualSha !== entry.sha256) {
      return {
        ok: false,
        code: 'CHECKSUM_MISMATCH',
        message: `sha256 mismatch for ${entry.path}`,
        path: entry.path,
      };
    }
    if (actual.length !== entry.size) {
      return {
        ok: false,
        code: 'CHECKSUM_MISMATCH',
        message: `size mismatch for ${entry.path}`,
        path: entry.path,
      };
    }
  }

  // No unlisted business files allowed. (manifest.json is excluded from this
  // check because it's not listed in its own file index.)
  for (const name of files.keys()) {
    if (!listed.has(name)) {
      return {
        ok: false,
        code: 'EXTRA_FILE',
        message: `zip has extra file not in manifest: ${name}`,
        path: name,
      };
    }
  }

  return { ok: true };
}
