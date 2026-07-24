#!/usr/bin/env bash
# claude-code-notify-setup.sh — Repo-level template deployer for Claude Code
#                               6-trigger voice-alert notification system.
#
# Purpose:
#   W68 第 12 批 B-4 implemented the system at user-level (C:/Users/pc/) only.
#   This script lets a NEW machine or NEW user deploy the WHOLE setup in one
#   command, by copying repo templates to user-level hooks bin +
#   merging settings.json hooks block.
#
# Usage:
#   bash scripts/claude-code-notify-setup.sh --dry-run           # default: show what would happen
#   bash scripts/claude-code-notify-setup.sh --apply             # actually copy + wire
#   bash scripts/claude-code-notify-setup.sh --rollback          # restore settings.json backup, remove deployed wrappers
#   bash scripts/claude-code-notify-setup.sh --verify            # check current installation status
#
# Cross-platform:
#   Linux / WSL / macOS  : pure bash + cp
#   Windows (Git Bash)   : uses cp; on native Windows run via WSL or pwsh wrapper
#
# Idempotency:
#   --apply is safe to re-run. Existing files are overwritten. settings.json is
#   backed up to settings.json.bak.<timestamp> BEFORE merge. Rollback target
#   stored at .claude-notify-install-state in user home.
#
# Exit codes:
#   0 = success
#   1 = invalid args
#   2 = missing template files
#   3 = jq missing (cannot parse settings.json)
#   4 = user declined safety prompt (only with --apply and stdin not tty)
#
# W68 第 13 批 B-1 (2026-07-24): declarative repo-level template deployment.

set -uo pipefail

# ---------- constants ----------
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TEMPLATE_DIR="${SCRIPT_DIR}/notify-templates"
PROJECT_ROOT="$( cd "${SCRIPT_DIR}/.." && pwd )"

# Detect platform — default to user-level bin path per OS
if [[ "${OS:-}" == "Windows_NT" ]] || uname -r 2>/dev/null | grep -qi "microsoft"; then
    USER_BIN="/c/Users/$(whoami)/bin"
    USER_SETTINGS="/c/Users/$(whoami)/.claude/settings.json"
else
    USER_BIN="${HOME}/bin"
    USER_SETTINGS="${HOME}/.claude/settings.json"
fi

# Allow override via env (CI / non-standard layout)
USER_BIN="${MNB_USER_BIN:-${USER_BIN}}"
USER_SETTINGS="${MNB_USER_SETTINGS:-${USER_SETTINGS}}"

STATE_FILE="${HOME}/.claude-notify-install-state"
BACKUP_DIR="${HOME}/.claude-notify-backups"

# 6 trigger wrappers (must match templates dir + hook block keys in settings.json)
TRIGGER_NAMES=("stop" "prompt" "notify" "perm" "session" "tool")

# ---------- logging ----------
_log() {
    local level="$1"; shift
    local color_reset="\033[0m"
    local color=""
    case "${level}" in
        INFO)  color="\033[0;36m" ;;  # cyan
        OK)    color="\033[0;32m" ;;  # green
        WARN)  color="\033[0;33m" ;;  # yellow
        ERROR) color="\033[0;31m" ;;  # red
        STEP)  color="\033[0;35m" ;;  # magenta
    esac
    # shellcheck disable=SC2059
    printf "${color}[%s]${color_reset} %s\n" "${level}" "$*"
}

die() { _log ERROR "$*"; exit "${2:-1}"; }

# ---------- arg parsing ----------
MODE="dry-run"   # default

usage() {
    cat <<EOF
Usage: bash $0 [OPTIONS]

Options:
  --dry-run       Show what would happen (DEFAULT — safe to run anytime)
  --apply         Actually copy templates + write settings.json
  --rollback      Undo last --apply (restore from backup + remove deployed files)
  --verify        Check current installation (read-only, exit 0=PASS, 1=incomplete)
  --bin PATH      Override user bin path (default: ${USER_BIN})
  --settings PATH Override settings.json path (default: ${USER_SETTINGS})
  -h, --help      Show this help

Examples:
  bash scripts/claude-code-notify-setup.sh --dry-run
  bash scripts/claude-code-notify-setup.sh --apply
  bash scripts/claude-code-notify-setup.sh --rollback
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)  MODE="dry-run"; shift ;;
        --apply)    MODE="apply"; shift ;;
        --rollback) MODE="rollback"; shift ;;
        --verify)   MODE="verify"; shift ;;
        --bin)      USER_BIN="$2"; shift 2 ;;
        --settings) USER_SETTINGS="$2"; shift 2 ;;
        -h|--help)  usage ;;
        *) die "Unknown arg: $1 (try --help)" 1 ;;
    esac
done

# ---------- pre-flight ----------
[[ -d "${TEMPLATE_DIR}" ]] || die "Template dir missing: ${TEMPLATE_DIR}" 2
for t in "${TRIGGER_NAMES[@]}"; do
    [[ -f "${TEMPLATE_DIR}/claude-voice-alert-${t}.ps1" ]] || die "Missing template: claude-voice-alert-${t}.ps1" 2
done
[[ -f "${TEMPLATE_DIR}/settings.json.template" ]] || die "Missing settings.json.template" 2

# jq is optional but recommended
HAS_JQ=0
command -v jq >/dev/null 2>&1 && HAS_JQ=1

# ---------- dry-run ----------
do_dry_run() {
    _log STEP "DRY RUN — no filesystem changes"
    echo
    _log INFO "Project root:    ${PROJECT_ROOT}"
    _log INFO "Template dir:    ${TEMPLATE_DIR}"
    _log INFO "Target user bin: ${USER_BIN}"
    _log INFO "Target settings: ${USER_SETTINGS}"
    echo
    _log STEP "Would copy 6 PowerShell triggers to ${USER_BIN}/:"
    for t in "${TRIGGER_NAMES[@]}"; do
        printf "          - claude-voice-alert-%s.ps1\n" "${t}"
    done
    echo
    _log STEP "Would merge hooks block from settings.json.template → ${USER_SETTINGS}"
    if [[ -f "${USER_SETTINGS}" ]]; then
        _log INFO "Existing settings.json detected — will back up first"
    else
        _log WARN "No existing settings.json — would create new"
    fi
    echo
    _log STEP "State file: ${STATE_FILE}"
    echo
    _log OK "Dry-run complete. Re-run with --apply to actually deploy."
    exit 0
}

[[ "${MODE}" == "dry-run" ]] && do_dry_run

# ---------- verify ----------
do_verify() {
    local missing=0
    _log STEP "VERIFY — checking current installation"
    echo
    for t in "${TRIGGER_NAMES[@]}"; do
        if [[ -f "${USER_BIN}/claude-voice-alert-${t}.ps1" ]]; then
            _log OK "  ${USER_BIN}/claude-voice-alert-${t}.ps1 exists"
        else
            _log WARN "  ${USER_BIN}/claude-voice-alert-${t}.ps1 MISSING"
            missing=1
        fi
    done
    echo
    if [[ -f "${USER_SETTINGS}" ]]; then
        _log INFO "settings.json: ${USER_SETTINGS}"
        if [[ "${HAS_JQ}" == "1" ]]; then
            local hook_count
            hook_count=$(jq -r '[.hooks // {} | to_entries[] | .value | length] | add // 0' "${USER_SETTINGS}" 2>/dev/null || echo "?")
            _log INFO "  hooks entries (total across 6 triggers): ${hook_count}"
        fi
    else
        _log WARN "settings.json: ${USER_SETTINGS} MISSING"
        missing=1
    fi
    echo
    if [[ "${missing}" == "0" ]]; then
        _log OK "All 6 triggers installed. Verify complete."
        exit 0
    else
        _log WARN "Some components missing — run --apply to install."
        exit 1
    fi
}

[[ "${MODE}" == "verify" ]] && do_verify

# ---------- apply ----------
do_apply() {
    _log STEP "APPLY — installing Claude Code 6-trigger voice-alert"

    # Create target dirs
    mkdir -p "${USER_BIN}" || die "Cannot create ${USER_BIN}" 2
    mkdir -p "${BACKUP_DIR}" || die "Cannot create ${BACKUP_DIR}" 2
    mkdir -p "$(dirname "${USER_SETTINGS}")" || die "Cannot create $(dirname "${USER_SETTINGS}")" 2

    # Backup existing settings.json
    if [[ -f "${USER_SETTINGS}" ]]; then
        local ts
        ts="$(date -u +%Y%m%dT%H%M%SZ)"
        local backup="${BACKUP_DIR}/settings.json.bak.${ts}"
        cp "${USER_SETTINGS}" "${backup}" || die "Backup failed: ${backup}" 2
        _log INFO "Backed up → ${backup}"
    fi

    # Copy 6 trigger wrappers
    for t in "${TRIGGER_NAMES[@]}"; do
        cp "${TEMPLATE_DIR}/claude-voice-alert-${t}.ps1" \
           "${USER_BIN}/claude-voice-alert-${t}.ps1" \
            || die "Copy failed: claude-voice-alert-${t}.ps1" 2
        _log OK "  copied: claude-voice-alert-${t}.ps1"
    done

    # Merge settings.json hooks block
    merge_settings

    # Save install state
    cat > "${STATE_FILE}" <<EOF
# claude-code-notify-setup.sh install state (W68 第 13 批 B-1, 2026-07-24)
mode=apply
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
user_bin=${USER_BIN}
user_settings=${USER_SETTINGS}
backup_dir=${BACKUP_DIR}
triggers=${TRIGGER_NAMES[@]}
EOF
    _log INFO "State saved: ${STATE_FILE}"

    echo
    _log OK "Apply complete. 6 triggers installed + settings.json merged."
    _log INFO "Test by: sending a prompt to claude → should hear 'Prompt received, Claude is processing' from SAPI"
    _log INFO "If audio fails: see docs/claude-code-notify-system-setup-guide-2026-07-24.md §4"
    exit 0
}

# Merge settings.json.template into user settings (preserves user-defined keys)
merge_settings() {
    _log INFO "Merging hooks block from settings.json.template → ${USER_SETTINGS}"

    if [[ "${HAS_JQ}" != "1" ]]; then
        # Fallback: overwrite if no existing settings.json, else warn
        if [[ ! -f "${USER_SETTINGS}" ]]; then
            cp "${TEMPLATE_DIR}/settings.json.template" "${USER_SETTINGS}"
            _log WARN "jq missing — wrote template as-is (no merge). Install jq for safe merge."
            return 0
        else
            die "jq missing AND settings.json exists — install jq (apt/brew/choco install jq) for safe merge" 3
        fi
    fi

    # jq merge: take everything from template, then overlay user keys (env, model, etc.)
    # Template serves as base (hooks block always from template, env from user)
    local merged
    merged=$(jq -s '
        .[0] as $tmpl | .[1] as $user |
        $tmpl * $user |
        # Hooks block always from template
        .hooks = $tmpl.hooks |
        # env: keep user keys but add template MNB_VOICE_ALERT_PROJECT_DIR if missing
        .env = ($user.env // {}) * ($tmpl.env // {})
    ' "${TEMPLATE_DIR}/settings.json.template" "${USER_SETTINGS}" 2>/dev/null) \
        || die "jq merge failed — check template + settings.json validity" 3

    echo "${merged}" | jq . > "${USER_SETTINGS}" 2>/dev/null \
        || die "Failed to write merged settings.json" 3

    _log OK "settings.json merged (hooks from template, env/user keys preserved)"
}

[[ "${MODE}" == "apply" ]] && do_apply

# ---------- rollback ----------
do_rollback() {
    _log STEP "ROLLBACK — restoring from backup"

    if [[ ! -f "${STATE_FILE}" ]]; then
        _log WARN "No state file at ${STATE_FILE} — cannot auto-rollback"
        _log INFO "Manual rollback: delete ${USER_BIN}/claude-voice-alert-*.ps1 (6 files)"
        exit 1
    fi

    # Find latest backup
    local latest_backup
    latest_backup=$(ls -1t "${BACKUP_DIR}"/settings.json.bak.* 2>/dev/null | head -1)
    if [[ -z "${latest_backup}" ]]; then
        die "No backup files in ${BACKUP_DIR}" 2
    fi

    # Restore settings.json
    cp "${latest_backup}" "${USER_SETTINGS}" \
        && _log OK "Restored settings.json from ${latest_backup}" \
        || die "Restore failed" 2

    # Remove 6 deployed wrappers
    for t in "${TRIGGER_NAMES[@]}"; do
        local target="${USER_BIN}/claude-voice-alert-${t}.ps1"
        if [[ -f "${target}" ]]; then
            rm -f "${target}"
            _log OK "  removed: claude-voice-alert-${t}.ps1"
        fi
    done

    rm -f "${STATE_FILE}"
    echo
    _log OK "Rollback complete. Backup kept at: ${latest_backup}"
    exit 0
}

[[ "${MODE}" == "rollback" ]] && do_rollback

# should not reach here
die "Unknown mode: ${MODE}" 1
