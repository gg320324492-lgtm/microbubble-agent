# Project-level Voice Alert (now delegated via global hook)

> The project-level `scripts/voice-alert.ps1` is **no longer wired as a project-level Stop hook** (since W68 D-3, 2026-07-24). It is now **delegated via the user-level global hook**.

## State (2026-07-24, post W68 第 7 批 D-3)

- `scripts/voice-alert.ps1` exists and works (high-quality XiaoxiaoNeural via edge-tts 3-layer fallback: ChatTTS → edge-tts → SAPI).
- It is **not** invoked by `.claude/settings.json` directly.
- It IS invoked indirectly by the user-level global wrapper, which finds it via the `MNB_VOICE_ALERT_PROJECT_DIR` env var (set in `C:\Users\pc\.claude\settings.json` env block).

## What changed

| Component | Before W68 D-3 | After W68 D-3 |
|-----------|---------------|---------------|
| `.claude/settings.json` (project) | (none, no hooks) | (none, no hooks) |
| `C:\Users\pc\.claude\settings.json` (user) | no `hooks` block | Stop + UserPromptSubmit hooks |
| `scripts/voice-alert.ps1` | standalone, only manual invocation | delegated via wrapper |

## Why this design

- **Single source of truth**: any Claude Code window (any cwd) gets the same alert behavior.
- **No double-fire**: project-level `.claude/settings.json` deliberately has no `hooks` block — we want one hook per window, not two.
- **Project-aware but cwd-agnostic**: the env var resolves to this project's voice script even if the user runs claude code from a different directory.

## Manual invocation still works

The script can be invoked manually in any of these ways:

```powershell
# From project cwd
scripts\voice-alert.ps1 -TaskDone -ShowToast

# Direct path
powershell -ExecutionPolicy Bypass -File scripts\voice-alert.ps1 -OnError "后端 500 了"
```

The wrapper **only** delegates when the env var points here. From a different cwd, the wrapper falls back to inline SAPI.

## Future options (not currently wired)

The project-level voice alert could in principle be wired as:

1. **Standalone CLI for cron** — e.g. nightly "did the meeting get processed?" reminder
2. **Celery task hook** — e.g. post-meeting-analysis completion alert
3. **Task complete event listener** — e.g. long-running task finish cue

These would require separate wrangling (not via the global Stop hook, since Stop fires on every Claude response). For now, manual invocation is the recommended path for non-Claude-Code triggers.
