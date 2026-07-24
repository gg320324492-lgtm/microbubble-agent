# Claude Code Global Voice Alert — Notification Hook (TEMPLATE)
#
# Purpose: Fire voice alert when Claude Code sends a desktop notification
# (e.g., long-running task completes in background). The Notification event
# fires OUTSIDE the active conversation flow — typically when the user has
# toggled to another window mid-task.
#
# Wired from user-level settings.json hooks.Notification.
# Source-of-truth template: scripts/notify-templates/claude-voice-alert-notify.ps1
#
# Distinguishes from Stop:
#   - Stop     fires when claude FINISHES the current turn -> "task done"
#   - Notification fires for BACKGROUND events (background tasks, idle alerts)
#
# Strategy:
#   1. Delegate to master wrapper --mode notify (space-separated, PS 5.1+ binding)
#   2. Wrapper discovers project script via MNB_VOICE_ALERT_PROJECT_DIR
#   3. Project script plays "background notification arrived" cue
#   4. On failure: silent SAPI fallback
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
    & powershell -NoProfile -ExecutionPolicy Bypass -File $Wrapper --mode notify @HookInput
} catch {
    # Swallow — see stop.ps1 for rationale
}

exit 0
