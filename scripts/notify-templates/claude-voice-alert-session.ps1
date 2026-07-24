# Claude Code Global Voice Alert — SessionStart Hook (TEMPLATE)
#
# Purpose: Fire voice alert when Claude Code SESSION STARTS (resumes or begins).
# Helps user confirm Claude Code is ready, useful when launching from terminal
# then alt-tabbing while waiting for the spinner to clear.
#
# Wired from user-level settings.json hooks.SessionStart.
# Source-of-truth template: scripts/notify-templates/claude-voice-alert-session.ps1
#
# Distinguishes from UserPromptSubmit:
#   - UserPromptSubmit fires AFTER user submits a prompt (each turn)
#   - SessionStart      fires ONCE when session begins / resumes (cold start)
#
# Strategy:
#   1. Delegate to master wrapper --mode session (space-separated, PS 5.1+ binding)
#   2. Wrapper discovers project script via MNB_VOICE_ALERT_PROJECT_DIR
#   3. Project script plays subtle "session ready" cue
#   4. On failure: silent SAPI fallback
#
# Per Claude Code docs (2026-07), SessionStart fires on:
#   - Startup (fresh `claude` invocation)
#   - Resume (after /resume or `--continue`)
#   - Clear (after /clear)
#   Skip on /compact — use Notification for that.
#
# Design principles (mirror of stop.ps1):
#   - Never throw to stderr
#   - Always exit 0
#   - No Set-Location
#   - No mutation outside user-level logs
#
# W68 第 13 批 B-1 (2026-07-24): repo-level template.

[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    $HookInput
)

$ErrorActionPreference = "Continue"

$Wrapper = "C:\Users\pc\bin\claude-voice-alert.ps1"
if (-not (Test-Path $Wrapper)) {
    exit 0
}

try {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $Wrapper --mode session @HookInput
} catch {
    # Swallow — see stop.ps1 for rationale
}

exit 0
