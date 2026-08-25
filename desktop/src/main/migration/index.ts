/**
 * mbrp/index.ts — barrel export for the `.mbrp` package format library.
 *
 * Public surface used by R2 (exporter), R3 (semantic transformer) and
 * R4 (importer). Keep this file thin — implementation lives in the sibling
 * modules so they can be unit-tested in isolation.
 */

export type {
  MbrpFormatVersion,
  MbrpFileEntry,
  MbrpSourceSnapshot,
  MbrpManifest,
  MbrpInput,
  VerifyResult,
  MbrpErrorCode,
} from './mbrp-types';

export { createMbrp, openMbrp, verifyMbrp, MbrpArchiveError } from './mbrp-archive';
export { buildManifest, validateManifestShape } from './mbrp-manifest';

// R3: semantic snapshot → .mbrp conversion entry points.
export {
  convertSnapshotToMbrp,
  loadSnapshotFromDir,
  type SnapshotPayload,
  type ConvertOptions,
} from './semantic-converter';
