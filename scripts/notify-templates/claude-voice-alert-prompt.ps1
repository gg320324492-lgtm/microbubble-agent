# Claude Code Global Voice Alert — UserPromptSubmit Hook (TEMPLATE)
#
# Purpose: Lightweight audio cue when user submits a prompt (matches Stop's
# "task done" cue). Helps when user toggles to other window mid-think and
# wants to know the prompt was received.
#
# Wired from user-level settings.json hooks.UserPromptSubmit.
# Source-of-truth template: scripts/notify-templates/claude-voice-alert-prompt.ps1
#
# Distinguishes from Stop:
#   - Stop fires AFTER Claude finishes responding -> "task done, please check"
#   - UserPromptSubmit fires AFTER user submits -> "prompt received, processing started"
#
# Strategy:
#   1. Delegate to master wrapper --mode prompt (space-separated, PS 5.1+ binding)
#   2. Wrapper discovers project script via MNB_VOICE_ALERT_PROJECT_DIR
#   3. Project script plays SUBTLE prompt-received cue (different SAPI rate)
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
    & powershell -NoProfile -ExecutionPolicy Bypass -File $Wrapper --mode prompt @HookInput
} catch {
    # Swallow — see stop.ps1 for rationale
}

exit 0
