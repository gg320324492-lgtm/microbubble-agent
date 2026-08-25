/**
 * mbrp-types.ts — `.mbrp` package format type definitions
 *
 * R1 of the adaptive release program. A `.mbrp` file is a ZIP archive that
 * bundles a structured manifest plus the raw research assets it references.
 * Every entry in the manifest carries its own SHA-256 so we can detect any
 * post-export tampering.
 *
 * Format version 1 (R1).
 */

export type MbrpFormatVersion = 1;

export interface MbrpFileEntry {
  /** Forward-slash relative path inside the zip. Validated by mbrp-archive. */
  path: string;
  /** Lower-case hex SHA-256 of the entry's bytes. */
  sha256: string;
  /** Size in bytes — redundant with sha256 but useful for fast pre-checks. */
  size: number;
}

export interface MbrpSourceSnapshot {
  /** ISO-8601 timestamp of when the snapshot was captured. */
  capturedAt: string;
  /** Git commit SHA the snapshot was captured from (empty if not yet snapshotted). */
  capturedCommit: string;
  /** Whether the web/system stack was untouched between the R0 baseline and the capture. */
  webUntouched: boolean;
}

export interface MbrpManifest {
  formatVersion: MbrpFormatVersion;
  /** ISO-8601 timestamp the package itself was assembled. */
  createdAt: string;
  sourceSnapshot: MbrpSourceSnapshot;
  /**
   * Lightweight index of the entities referenced by the package. Bodies
   * themselves live in `files`. The schema is intentionally permissive —
   * R2/R3 exporters fill these in, R4 importer may extend them.
   */
  entities: {
    projects?: Array<{ id: string; name: string; [k: string]: unknown }>;
    tasks?: Array<{ id: string; title: string; [k: string]: unknown }>;
    meetings?: Array<{ id: string; title: string; [k: string]: unknown }>;
    knowledge?: Array<{ id: string; title: string; [k: string]: unknown }>;
    conversations?: Array<{ id: string; [k: string]: unknown }>;
  };
  files: MbrpFileEntry[];
  /** Non-fatal notes the producer wants to surface (e.g. "skipped 2 locked files"). */
  warnings: string[];
}

/**
 * Input to `createMbrp`. Callers provide raw entities + file bodies; the
 * archive layer hashes and serializes them.
 */
export interface MbrpInput {
  entities: MbrpManifest['entities'];
  files: Array<{ path: string; content: string | Buffer }>;
  sourceSnapshot?: Partial<MbrpSourceSnapshot>;
}

/**
 * Result of `verifyMbrp`. `ok=true` means every manifest-listed file is
 * present and its bytes match the recorded SHA-256. `ok=false` carries a
 * stable `code` so callers can map to UX.
 */
export type VerifyResult =
  | { ok: true }
  | {
      ok: false;
      code:
        | 'CHECKSUM_MISMATCH'
        | 'MISSING_FILE'
        | 'EXTRA_FILE'
        | 'INVALID_PATH'
        | 'DUPLICATE_ENTRY'
        | 'INVALID_MANIFEST'
        | 'BAD_ZIP';
      message: string;
      path?: string;
    };

/**
 * Stable error codes thrown by the archive layer. Internal-only — callers
 * should usually rely on `VerifyResult` from `verifyMbrp` instead of catching
 * these directly. They are exported so R2/R3/R4 can layer their own checks
 * on top.
 */
export type MbrpErrorCode =
  | 'INVALID_PATH'
  | 'INVALID_MANIFEST'
  | 'DUPLICATE_ENTRY'
  | 'BAD_ZIP';
