# Claude Code Global Voice Alert — Stop Hook (TEMPLATE)
#
# Purpose: Fire voice alert AFTER Claude Code finishes responding to user.
# Wired from user-level settings.json hooks.Stop.
# Source-of-truth template lives at:
#   E:\microbubble-agent\scripts\notify-templates\claude-voice-alert-stop.ps1
# setup.sh copies this file to the user-level hook bin (e.g.
# C:/Users/pc/bin/claude-voice-alert-stop.ps1) and wires it via settings.json.
#
# Strategy:
#   1. Delegate to master wrapper claude-voice-alert.ps1 --mode stop
#      (NOTICE: must use space-separated "--mode stop", PS 5.1+ does NOT
#       recognize `--key=value` for [string] parameters — that syntax is
#       reserved for switch parameters and gets routed to $RestArgs)
#   2. Wrapper discovers project script (e:\microbubble-agent\scripts\voice-alert.ps1)
#      via MNB_VOICE_ALERT_PROJECT_DIR env var set in settings.json env block
#   3. Project script plays high-quality XiaoxiaoNeural voice
#   4. On failure (no project script, TTS backend down): silent SAPI fallback
#
# Distinguishes Stop (claude finished) from UserPromptSubmit (user submitted prompt).
# Stop = "task done, come check"; UserPromptSubmit = "submitted, awaiting processing"
#
# Design principles (universal across all 6 triggers):
#   - Never throw to stderr (hook failure pollutes Claude Code behavior)
#   - Always exit 0
#   - No Set-Location (hook context cwd is irrelevant)
#   - No file mutation outside user-level logs
#
# W68 第 13 批 B-1 (2026-07-24): repo-level template (W68 第 12 批 B-4 was
# user-level implementation). New machines run setup.sh --apply to deploy.

[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    $HookInput
)

$ErrorActionPreference = "Continue"

# Resolve wrapper absolute path (user-level wrapper installed by setup.sh)
$Wrapper = "C:\Users\pc\bin\claude-voice-alert.ps1"
if (-not (Test-Path $Wrapper)) {
    # Wrapper missing — silent exit (setup.sh not run yet)
    exit 0
}

# Forward everything to wrapper with --mode stop
# NOTE: use SPACE-separated `--mode stop`, NOT `--mode=stop`
# Rest of args (TaskDone preset etc.) are passed through
try {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $Wrapper --mode stop @HookInput
} catch {
    # Wrapper raised — swallow to avoid polluting Claude Code stderr
}

exit 0
