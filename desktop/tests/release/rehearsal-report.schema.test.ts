import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import Ajv from 'ajv';

const SCHEMA_PATH = resolve(__dirname, 'rehearsal-report.schema.json');

describe('Rehearsal report schema (R7)', () => {
  const schema = JSON.parse(readFileSync(SCHEMA_PATH, 'utf8'));
  const ajv = new Ajv({ allErrors: true, strict: false });
  const validate = ajv.compile(schema);

  it('accepts a fully-populated green report', () => {
    const report = makeGreenReport();
    const ok = validate(report);
    if (!ok) console.error(validate.errors);
    expect(ok).toBe(true);
  });

  it('rejects a report missing required field', () => {
    const report: any = makeGreenReport();
    delete report.signedBy;
    expect(validate(report)).toBe(false);
  });

  it('rejects a report missing releaseCommit', () => {
    const report: any = makeGreenReport();
    delete report.releaseCommit;
    expect(validate(report)).toBe(false);
  });

  it('rejects a report missing webUntouched', () => {
    const report: any = makeGreenReport();
    delete report.webUntouched;
    expect(validate(report)).toBe(false);
  });
});

function makeGreenReport() {
  return {
    sourceSnapshot: {
      snapshotId: 'snap-2026-08-26-001',
      capturedAt: '2026-08-26T01:00:00Z',
      tableCounts: { members: 5, projects: 3, tasks: 10 },
      objectCount: 50,
      manifestSha256: 'a'.repeat(64),
      passed: true,
    },
    mbrpVerification: {
      packagePath: 'C:/snapshots/snap.mbrp',
      packageSha256: 'b'.repeat(64),
      filesVerified: 20,
      passed: true,
    },
    importResult: {
      dataDir: 'C:/Users/test/AppData/Roaming/ScientificResearchOS',
      runId: 'run-123',
      filesWritten: 20,
      warningCount: 0,
      passed: true,
    },
    offlineChecks: {
      networkDisconnected: true,
      itemsOpened: [
        { type: 'task', id: 't-1', passed: true },
        { type: 'meeting', id: 'm-1', passed: true },
        { type: 'file', id: 'f-1', passed: true },
        { type: 'conversation', id: 'c-1', passed: true },
      ],
    },
    backupRestore: {
      backupId: 'bk-123',
      backupSha256: 'c'.repeat(64),
      restoredSha256: 'c'.repeat(64),
      passed: true,
    },
    installer: {
      installerPath: 'C:/release/ScientificResearchOS-1.0.0-x64.exe',
      installerSha256: 'd'.repeat(64),
      installPath: 'C:/Program Files/ScientificResearchOS',
      smokeLaunchPassed: true,
      passed: true,
    },
    webUntouched: {
      passed: true,
      offendingPaths: [],
    },
    signedBy: {
      signed: true,
      certificateSubject: 'CN=MicroBubble Lab',
      certificateThumbprint: 'E'.repeat(40),
      signatureTimestamp: '2026-08-26T02:00:00Z',
    },
    releaseCommit: {
      sha: '93bbe818f712dcc3f6ac906a34714432075d1ec2',
      shortSha: '93bbe818',
      subject: 'release(desktop): harden backup and signed distribution',
      passed: true,
    },
  };
}
