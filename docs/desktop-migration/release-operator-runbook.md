# MicroBubble Desktop Release Operator Runbook

This runbook describes how the release engineer produces, validates, and ships a new **ScientificResearchOS** desktop release. It covers the end-to-end pipeline from snapshot export (R2) through signed installer rollout (R6).

## 1. Prerequisites

- Windows 10/11 with admin shell (PowerShell 5.1+).
- `node@20` and `npm@10` available on `PATH`.
- `python@3.12` available for the R2 snapshot tooling.
- Access to the desktop release signing certificate (CI only — see §3).
- Access to the **read-only** PostgreSQL role for snapshot export (R2).
- A clean git worktree on `claude/desktop-conversion-plan-12aa22` with no uncommitted changes.

## 2. Pre-release checklist

- [ ] `git status` is clean (no `M` or `??` entries on tracked release paths).
- [ ] `npm run release:guard` exits 0 with the R6 change list.
- [ ] All migration releases R0–R6 merged to `main`.
- [ ] Web server is reachable for the R2 snapshot export.
- [ ] `desktop/resources/release-protected-baseline.json` matches HEAD for every protected path.

## 3. Build the installer

```powershell
# In worktree root
git checkout main
git pull --ff-only
cd desktop
npm ci
npm run build:release-win
```

The signed installer lands in `desktop/release/${version}\ScientificResearchOS-${version}-x64.exe`.

### 3.1 CI signing

CI must set the following environment variables before invoking `electron-builder`:

| Variable | Description |
| --- | --- |
| `CSC_LINK` | Base64-encoded Windows code-signing PFX. `electron-builder` decodes it and signs both the NSIS installer and the EXE payload. |
| `CSC_KEY_PASSWORD` | Password that unlocks the PFX. |
| `GH_TOKEN` | GitHub PAT — required for the `github` provider declared in `electron-builder.yml`'s `publish:` block. |

`electron-builder.yml` no longer hard-codes `sign: null` (R6 hardening). When `CSC_LINK` is unset (local dev build), `signAndEditExecutable` remains `false` and the unsigned binary is produced for smoke testing only — **never ship this build**.

`verifyUpdateCodeSignature: true` is enabled in `win:` so `electron-updater` validates the server-side signature before applying an update.

## 4. Capture a web snapshot (R2)

```powershell
python -m scripts.desktop_migration.export_web_snapshot `
  --database-url 'postgres://readonly_ro:***@db.example.com:5432/microbubble' `
  --minio-endpoint 'https://minio.example.com' `
  --minio-access-key 'readonly-key' `
  --minio-secret-key '***' `
  --output-dir C:\snapshots\snap-2026-08-26 `
  --snapshot-id snap-2026-08-26-001
```

Verify `snapshot-manifest.json` contains correct SHA-256 entries for every file in the snapshot directory.

## 5. Convert snapshot to .mbrp (R3 + R4)

Use the desktop CLI / dev tooling to convert the snapshot into a `.mbrp` package. Verify `verifyMbrp` returns `{ ok: true }` before promoting the package to the import queue.

## 6. Install + verify (R6)

```powershell
powershell -ExecutionPolicy Bypass -File desktop\scripts\release\verify-installed-app.ps1 `
  -InstallerPath desktop\release\${version}\ScientificResearchOS-${version}-x64.exe
```

Expected: silent install OK, executable present, app stays alive ≥ 5 seconds.

## 7. Run the full rehearsal (R7)

See `docs/desktop-migration/release-acceptance-report.md` for the final rehearsal procedure and the JSON report schema.

## 8. Rollback

If the release has a critical defect:

1. **Do not** delete the installer or `release/${version}` directory; preserve them for forensics.
2. Revert `main` to the previous green commit:
   ```powershell
   git revert <bad-commit-sha>
   git push
   ```
3. Trigger the existing webhook deploy to roll the web install script back.
4. Open a post-mortem with the desktop migration squad.

## 9. Common failure modes

| Symptom | Likely cause | Mitigation |
| --- | --- | --- |
| Installer runs but app crashes immediately | Missing native module (`better-sqlite3`, etc.) | Rebuild with `npm run postinstall` to invoke `electron-builder install-app-deps`. |
| `npm run release:guard` fails on `web/dist/assets/*.js` | Pre-existing colleague work included by mistake | Use `git add -f` only on the R-batch's own files; verify the change list with `git diff --name-only HEAD~1 HEAD`. |
| Backup restore writes to wrong directory | R6 not applied (still uses `process.cwd()/.microbubble-data`) | Re-apply R6 commit `release(desktop): harden backup and signed distribution`. |
| Update check returns `MANUAL_UPDATE_REQUIRED` | Publish config missing or invalid | Verify `electron-builder.yml` `publish:` block is present and the HTTPS manifest URL is reachable. |
| `npm run build:release-win` OOMs the build host | Cloud servers with 2C/2G cannot build Next.js bundles | Always build on a beefy local Windows host; upload `release/${version}` to the server instead of building there. |
| NSIS installer signed but `verifyUpdateCodeSignature` rejects updates | `CSC_LINK` rotated and previous cert revoked | Roll the signing certificate on the server's auto-update feed; the in-app updater caches the public cert hash. |

## 10. Reference

- Plan source: `docs/superpowers/plans/2026-08-26-desktop-formal-release-program.md` (R0–R7)
- Guard script: `desktop/scripts/release/verify-web-unchanged.mjs`
- Operator export SOP: `docs/desktop-migration/operator-readonly-export.md`
- Backup service R6 tests: `desktop/tests/release/backup-restore.test.ts`
- Config service R6 tests: `desktop/tests/release/config-persistence.test.ts`
