# Claude Code Global Voice Alert — PreToolUse Hook (TEMPLATE)
#
# Purpose: Fire SUBTLE audio cue RIGHT BEFORE Claude Code calls the Bash tool.
# Helps user notice when claude is about to run a long-running command, so
# they can check progress or watch for unexpected side effects.
#
# Wired from user-level settings.json hooks.PreToolUse with matcher "Bash"
# (only fires for Bash tool invocations, not every tool).
# Source-of-truth template: scripts/notify-templates/claude-voice-alert-tool.ps1
#
# Distinguishes from other hooks:
#   - Stop / Notification / PermissionRequest: about USER-FACING events
#   - PreToolUse                            : about TOOL INVOCATION prelude
#   Cues are SUBTLE (rate=+2, lower volume) so they don't drown out other hooks.
#
# Strategy:
#   1. Delegate to master wrapper --mode tool (space-separated, PS 5.1+ binding)
#   2. Wrapper discovers project script via MNB_VOICE_ALERT_PROJECT_DIR
#   3. Project script plays brief "running bash command" cue
#   4. On failure: silent SAPI fallback
#
# Limitation: PreToolUse fires for EVERY tool by default. We use matcher "Bash"
# to scope to ONLY Bash invocations. Other tools (Read/Write/Edit/etc.) stay
# silent — too noisy otherwise. If user wants more tools, add additional
# PreToolUse blocks with different matchers in settings.json.
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
    & powershell -NoProfile -ExecutionPolicy Bypass -File $Wrapper --mode tool @HookInput
} catch {
    # Swallow — see stop.ps1 for rationale
}

exit 0
