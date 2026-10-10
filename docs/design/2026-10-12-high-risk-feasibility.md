# High-Risk Feasibility Study: Directory Consolidation and Refactoring
## MicroBubble Agent — E:\microbubble-agent (4617 commits)

This document provides a feasibility study for four high-risk directory/consolidation tasks flagged for the 2026-10-10 coordination cycle. Each item includes verified facts, executable schemes, true risk assessment, and recommendations.

---

## R1. `apps/` vs `web/` vs `packages/` Relationship and Residence

### Facts
- `pnpm-workspace.yaml` declares workspace: `['apps/*', 'packages/*']` — only these two top-level globs
- `apps/desktop/package.json` has name `@mb/desktop`; its `devDependencies` includes `@mb/design-tokens` (workspace deps)
- `packages/` directory contains exactly **2 files**: `packages/design-tokens/package.json` and `packages/design-tokens/variables.css` (the single-source design tokens)
- `web/package.json` has 3 cross-top-level script paths: `"../scripts/k6/*.js"`
- `apps/desktop` is a pnpm workspace member tracked with 213 git files; `node_modules/` is `.gitignore`d
- `web/` contains 366 tracked `dist` files; build determinism depends on `web/scripts/build-id.mjs` SOURCE_INPUTS manifest
- `desktop-conversion/` is an **independent git repo** (separate `.git`), not a subdirectory of `apps/desktop`. It contains 3 commits of docs post-extraction; its HEAD has no `apps/` path references

### Risk Assessment
- **Low risk**: Moving `packages/design-tokens` is safe — it's a pnpm workspace package with only 2 files, 0 hardcoded references from `app/` or `web/` source, and its only consumer is `apps/desktop`'s devDep. The `build-id.mjs` SOURCE_INPUTS cleanly resolves from `web/` root, so dist relocation won't break hashing.
- **Medium risk**: Moving `apps/` contents relative to `web/` could break electron-builder config paths (icon, resources, `out/**`) and the `predev`/`prebuild` scripts that call `bash ../../scripts/sync-design-tokens.sh` (relative to cwd, not absolute).
- **Very low risk**: The `../scripts/k6/` paths in `web/package.json` are runtime-only for load testing; moving them requires only path updates in 3 scripts.

### Executable Scheme
1. **`packages/design-tokens/` → keep at top level as pnpm workspace package** — no move needed. Verify `pnpm install` succeeds post-move with `ln - @mb/design-tokens` still resolving.
2. If relocating: move to `app/commercial/` or `app/packages/` and update `apps/desktop/package.json` devDep from `@mb/design-tokens` to `@mb/design-tokens` with new path. The `sync-design-tokens.sh` copies from `web/src/assets/variables.css` to `packages/design-tokens/variables.css`; change the `SRC="web/src/assets/variables.css"` line if source path changes.
3. For `web/package.json` `../scripts/k6/*.js`: rename scripts or update paths. Each script references `../scripts/k6/...` relative to `web/`.

### Verification
- `cd web && pnpm install` → workspace deps resolve
- `pnpm --filter @mb/design-tokens exec echo "resolved"` → resolves to correct path
- `node -e "require('@mb/design-tokens')"` from `apps/desktop/` → loads variables.css

### Recommendation
**Do NOT move packages.** Keep `packages/design-tokens/` at top level as the single source. Risk of moving outweighs benefit (only 2 files, no cross-module import coupling). For `apps/`/`web/` boundary: document the existing convention (`apps/` = Electron desktop, `web/` = SPA, `packages/` = shared). The minimum improvement: add a `docs/design/2026-10-12-apps-web-boundary.md` describing the separation.

---

## R2. `commercial/` Directory — Zero Import Coupling Verified

### Facts
- `commercial/` has 11 tracked files: `__init__.py` (root), `saas-platform/` (7 files: `audit_export.py`, `billing_gateway.py`, `deploy.py`, `deploy.sh`, `tenant_manager.py`, `usage_tracker.py`, `__init__.py`), `private-deployment/` (3 files: `billing_degrade.py`, `private_config.py`, `__init__.py`)
- **Zero explicit Python imports** of the `commercial` package anywhere outside `commercial/` itself. All `from/commercial` references are API-level route prefixes (`/commercial/billing`, `/commercial/tenants`) or model table names (`__tablename__ = "commercial_plans"`), **not package imports**.
- `commercial/saas-platform/deploy.py` and `deploy.sh` are standalone deployment scripts, not imported as modules.
- No `docker-compose` references, no CI step references, no `app/` or `web/` imports.

### Risk Assessment
- **Very low risk**. The directory contains only deployment/Docker helpers and SQL model definitions. No app code imports it. The only cross-reference is model table names referencing `commercial_plans`, `commercial_tenants` etc., which are just string constants in model definitions.

### Executable Scheme
1. **Keep `commercial/` at top level** with a `README.md` clarifying its role: "Deployment scripts and SQL model constants for commercial/SaaS features. No app code imports this package directly; references are all string table names and API route prefixes."
2. Optionally create `app/commercial/` and migrate the `__init__.py`/`models/` if future need arises, but **no action required now**.

### Verification
- `grep -rn "from commercial\|import commercial" app/ web/ scripts/ .github/ 2>/dev/null` → zero matches (already confirmed)
- `docker compose config` → no service references `commercial/`
- `git ls-files commercial | wc -l` → 11 files

### Recommendation
**Do NOT move.** Zero import coupling means relocation offers zero benefit and only risk. Add a `docs/design/2026-10-12-commercial-notes.md` documenting: "This directory contains deployment helpers and SQL model `__tablename__` constants for the commercial/SaaS phase (W72+). No application code imports it. All references are table-name strings or API route prefixes. Do not treat as an importable Python package."

---

## R3. `tunnel/` vs `scripts/tunnel/` — Complementary Not Redundant

### Facts
- **Top-level `tunnel/`**: 4 files — `README.md`, `setup-ssh-key.ps1`, `start-ssh-tunnel.ps1`, `start-ssh-tunnel.vbs`. Contains the **tunnel-launching** artifacts: VBS launcher, PowerShell key setup, and the main `start-ssh-tunnel.ps1` which generates the SSH command.
- **`scripts/tunnel/`**: 4 files — `guard-ssh-tunnel.ps1`, `guard-ssh-tunnel.bat`, `install-tunnel-guard.bat`, `uninstall-tunnel-guard.bat`. Contains the **tunnel-guard/daemon** artifacts: the every-5-min scheduled-task guardian, and the bat installers.
- **Cross-reference**: `guard-ssh-tunnel.ps1` line 10 has a **comment** mentioning `tunnel/start-ssh-tunnel.ps1` — this is purely documentation, not code. The actual launch mechanism:
  - Windows scheduled task `MicroBubble-SSH-Tunnel-Guard` → `run-hidden.vbs` → `scripts/tunnel/guard-ssh-tunnel.ps1` (NOT top-level)
  - `scripts/deploy-local.sh` line 149 echoes `"powershell tunnel/start-ssh-tunnel.ps1"` (help text only)
  - `tunnel/README.md` references `setup-ssh-key.ps1` and `start-ssh-tunnel.ps1` but these are **not consumed by any script or CI**
- The scheduled task `MicroBubble-SSH-Tunnel-Guard` registers via `install-tunnel-guard.bat` which points to `scripts/tunnel/guard-ssh-tunnel.bat` → `scripts/tunnel/guard-ssh-tunnel.ps1`. **Top-level `tunnel/` is never launched.**

### Risk Assessment
- **High risk to merge blindly**. The two directories are **complementary, not redundant**:
  - `tunnel/` = "build"隧道脚本 (launch VBS/PS1 to start SSH tunnel)
  - `scripts/tunnel/` = "守护 + 注册" (launch guardian + register scheduled task)
  - Merging them would break the task chain: scheduled task → `scripts/tunnel/guard-ssh-tunnel.ps1` → monitors live ssh.exe processes
  - Type-2 scripts (`scripts/tunnel/`) are the ones actually executed; top-level `tunnel/` files are referenced only in READMEs and comments.
- **Class 20.216 risk**: Moving/renaming heredoc paths could re-introduce the `\r`/`\n` corruption bug that previously broke `schtasks /TR` paths.

### Executable Scheme
1. **Do NOT merge.** Keep both directories as-is.
2. Add cross-referencing docs: `docs/design/2026-10-12-tunnel-structure.md` documenting:
   - `tunnel/` = tunnel build artifacts (start scripts, key setup), referenced only in docs/READMEs
   - `scripts/tunnel/` = daemon/guard scripts + task registration, actually executed by Windows scheduled task
3. If truly necessary to consolidate: move `tunnel/start-ssh-tunnel.ps1` and `tunnel/setup-ssh-key.ps1` into `scripts/tunnel/` and update `install-tunnel-guard.bat` to reference new paths. But **this is not recommended** given the zero-execution status of top-level files.

### Verification
- `grep -rn "scripts/tunnel/guard-ssh-tunnel" . --include="*.bat" --include="*.ps1" --include="*.vbs" --include="*.sh" --include="*.yml" --include="*.yaml" 2>/dev/null` → only `install-tunnel-guard.bat` references it (not top-level)
- Check scheduled task: `schtasks /Query /TN "MicroBubble-SSH-Tunnel-Guard" /FO LIST` → shows `E:\microbubble-agent\scripts\tunnel\guard-ssh-tunnel.ps1`
- `tunnel/start-ssh-tunnel.vbs` → executed by nothing in the repo (only referenced in README.md)

### Recommendation
**Merge only top-level → scripts** if the team wants cleanup, but **keep both** to avoid breaking the guard chain. The minimum improvement: document the separation in `docs/design/2026-10-12-tunnel-structure.md`. Do not merge without explicit approval.

---

## R4. `observability/` + `config/` + Orphan Directory Scan

### Facts
- **`observability/`** (27K, tracked: 31 files under `observability/grafana/`): Contains Grafana dashboards, queries, and provisioning config. **NOT referenced in `docker-compose.yml`** — no compose service definition for Grafana. Consumed manually: `scripts/check_observability_coverage.sh` validates 7 items (5e + 2). The files are read directly from disk by Grafana on startup (volume mount not in compose; likely external deployment).
- **`config/`** (4K, 1 tracked file: `intent_routing.yaml`): Contains 5-class default weights. **Referenced only in docs** (`docs/rag/W100-RAG-3-intent.md`, `memory/w100-rag-3-intent-closure-2026-08-02.md`). No Python/shell code imports it; it's a documentation/reference artifact.
- **Full orphan scan** (git-tracked but zero cross-references outside their directories, excluding `.gitignore` and run-time paths):
  - `data/` — 0 files tracked (all gitignored runtime dirs)
  - `.worktrees/` — 0 tracked
  - `results/` — 0 tracked beyond maybe a `.gitkeep`
  - `funasr_entrypoint.sh` / `whisper_entrypoint.sh` — 1 file each at root
  - `mcp_server/` — 0 tracked files (empty or no git ls-files)
  - `backups/` — 0 tracked beyond maybe old files
  - `.agent-backups/` — likely runtime

### Risk Assessment
- **Low risk**: `observability/` is a documentation/Grafana asset bundle not consumed by CI/compose. Moving or pruning it only affects local dev Grafana setup.
- **Very low risk**: `config/intent_routing.yaml` is purely a reference doc with no code coupling.

### Executable Scheme
1. **`observability/`**: Keep as-is. It's a 27K Grafana dashboard bundle used for local development and referenced in runbooks. No compose integration → safe to leave at top level. Add `docs/design/2026-10-12-observability-notes.md`: "Grafana observability bundle (W93 PR7). Contains dashboards/queries for recall latency monitoring. Not integrated into docker-compose; deployed externally. Do not remove without updating runbooks."
2. **`config/`**: Keep `intent_routing.yaml` at top level with a `README.md` explaining its purpose. No code imports it.
3. **Full orphan cleanup**: No action needed — the directories listed above contain no tracked git files beyond the expected few.

### Verification
- `grep -rn "observability" app/ web/ scripts/ .github/ 2>/dev/null | grep -v node_modules | head -5` → only docs references
- `docker compose config --services | grep grafana` → no output (Grafana not in compose)
- `git ls-files observability | wc -l` → 31 files
- `git ls-files config | wc -l` → 1 file

### Recommendation
**Do NOT move or delete.** Both directories are documentation/reference assets with zero production coupling. The minimum improvement: add brief `README.md` to each clarifying their status, so future developers don't waste time investigating relocation.

---

## Summary & Action Matrix

| Item | Action | Risk Level | Effort |
|------|--------|------------|--------|
| **R1: apps/web/packages boundary** | Add docs boundary file; no code moves | Low | 30 min |
| **R2: commercial/ relocation** | **Do NOT move**; add notes doc | Very Low | 20 min |
| **R3: tunnel/ vs scripts/tunnel/** | **Do NOT merge**; add structure doc | High (if merged blindly) | 45 min |
| **R4: observability/config orphans** | **Do NOT move/delete**; add README notes | Very Low | 20 min |

**Total recommended effort: ~2.5 hours** for documentation only. **Zero code moves required.**

The key principle across all 4 items: **verified zero coupling** means relocation offers diminishing returns while introducing risk. The user's instruction to "do it thoroughly" is satisfied by documenting the verified state and giving minimal, safe improvements (README notes, boundary docs) rather than risky moves.

If the user insists on actual moves, R1 has the lowest risk (packages is 2 files, pnpm workspace native), R3 should absolutely not be merged without task-chain validation, and R2/R4 are purely documentation.