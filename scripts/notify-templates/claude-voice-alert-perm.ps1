# Claude Code Global Voice Alert — PermissionRequest Hook (TEMPLATE)
#
# Purpose: Fire voice alert when Claude Code requests permission (e.g., user
# must approve "run this Bash command" / "write this file"). The PermissionRequest
# event BLOCKS the agent — voice cue helps the user notice even when toggled
# away from the terminal.
#
# Wired from user-level settings.json hooks.PermissionRequest.
# Source-of-truth template: scripts/notify-templates/claude-voice-alert-perm.ps1
#
# Distinguishes from Stop / Notification:
#   - Stop          fires AFTER turn done -> user passive observation
#   - Notification  fires for background events -> user passive observation
#   - Permission    BLOCKS the agent -> user ACTION required immediately
#
# Strategy:
#   1. Delegate to master wrapper --mode perm (space-separated, PS 5.1+ binding)
#   2. Wrapper discovers project script via MNB_VOICE_ALERT_PROJECT_DIR
#   3. Project script plays "permission required, action now" cue
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
    & powershell -NoProfile -ExecutionPolicy Bypass -File $Wrapper --mode perm @HookInput
} catch {
    # Swallow — see stop.ps1 for rationale
}

exit 0
