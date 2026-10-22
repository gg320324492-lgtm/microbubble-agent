# Repair the WSL-VM app-container ACLs on Docker Desktop's system disk.
#
# Symptom (2026-10-22, same class as the 2026-10-19 incident):
#   Docker Desktop's backend crashes within ~4 seconds of start with
#     "starting services: initializing Ingest server: listening on
#      unix://<HOME>/AppData/Local/Docker/run/sailor-ingest.sock:
#      AF_UNIX listen ... bind: Only one usage of each socket address ..."
#   and the daemon never becomes reachable (docker info -> npipe ... not found).
#
# Root cause:
#   WSL grants the per-VM app-container SID (S-1-5-83-1-<...>) FullControl
#   DIRECTLY on each .vhdx file it owns - not inherited from the parent dir.
#   Docker Desktop's system disk
#     <dataRoot>\appdata\wsl\main\ext4.vhdx
#   loses those ACEs whenever it is recreated / relocated, while the data disk
#     <dataRoot>\appdata\wsl\disk\docker_data.vhdx
#   keeps them. WSL then fails to attach the distro:
#     Wsl/Service/CreateInstance/MountDisk/HCS/E_ACCESSDENIED
#   the Ingest server cannot start, and the backend dies.
#
# Why not "wsl --unregister docker-desktop" (the old L3 of docker-guard.ps1):
#   that is the destructive path that PRODUCES this state in the first place
#   (unregister -> recreate -> new vhdx without the ACEs). It also churns the
#   62 GB data disk. Repairing the ACL is non-destructive and idempotent.
#
# Template source: the ACEs already present on docker_data.vhdx (the data disk
# is known-good, so its SID set contains the current VM's SID).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\ci\fix-docker-wsl-vhdx-acl.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\ci\fix-docker-wsl-vhdx-acl.ps1 -Check
#
# This file is ASCII-only on purpose: PowerShell 5.1 decodes a .ps1 without a
# BOM as GBK and mangles non-ASCII text.
param(
    [switch]$Check,           # report only, do not modify
    [string]$DataRoot = 'E:\microbubble-agent\data\docker\appdata'
)

$ErrorActionPreference = 'Stop'

$systemDisk = Join-Path $DataRoot 'wsl\main\ext4.vhdx'
$template   = Join-Path $DataRoot 'wsl\disk\docker_data.vhdx'

Write-Host '=== docker wsl vhdx acl repair ==='
Write-Host ("  system disk : {0}" -f $systemDisk)
Write-Host ("  template    : {0}" -f $template)

if (-not (Test-Path $systemDisk)) { throw "system disk not found: $systemDisk" }
if (-not (Test-Path $template))   { throw "template not found: $template" }

function Get-WslSids {
    param([string]$Path)
    $acl = Get-Acl $Path
    return @($acl.Access |
        Where-Object { $_.IdentityReference.Value -like 'S-1-5-83-1-*' } |
        ForEach-Object { $_.IdentityReference.Value } |
        Sort-Object -Unique)
}

$templateSids = Get-WslSids $template
$targetSids   = Get-WslSids $systemDisk
Write-Host ("  template SIDs : {0}" -f $templateSids.Count)
Write-Host ("  target SIDs   : {0}" -f $targetSids.Count)

$missing = @($templateSids | Where-Object { $targetSids -notcontains $_ })

if ($missing.Count -eq 0) {
    Write-Host '  RESULT: ACL already complete - nothing to do.'
    exit 0
}

Write-Host ("  MISSING {0} SID(s):" -f $missing.Count)
foreach ($s in $missing) { Write-Host ("    {0}" -f $s) }

if ($Check) {
    Write-Host '  RESULT: -Check specified, no changes made.'
    exit 2
}

$acl = Get-Acl $systemDisk
$existing = @{}
$acl.Access | ForEach-Object { $existing[$_.IdentityReference.Value] = $true }
$added = 0
foreach ($sid in $missing) {
    # A raw "S-1-5-83-1-..." string is NOT accepted by the string overload of
    # FileSystemAccessRule: it tries to translate it as an NTAccount and fails
    # with IdentityNotMappedException. Build a SecurityIdentifier explicitly.
    $sidObj = New-Object System.Security.Principal.SecurityIdentifier($sid)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $sidObj,
        [System.Security.AccessControl.FileSystemRights]::FullControl,
        [System.Security.AccessControl.AccessControlType]::Allow)
    $acl.AddAccessRule($rule)
    $added++
}
Set-Acl -Path $systemDisk -AclObject $acl
Write-Host ("  granted {0} SID(s) on the system disk" -f $added)

$after = Get-WslSids $systemDisk
Write-Host ("  RESULT: system disk now has {0} SID(s) (template has {1})" -f $after.Count, $templateSids.Count)
if ($after.Count -lt $templateSids.Count) { throw 'repair did not take effect' }
Write-Host '  OK'
