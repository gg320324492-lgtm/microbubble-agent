# Probe what C:\Users\pc\AppData\Local\Docker actually is, from a CLEAN
# (non-MSIX-packaged) process context.
#
# Docker Desktop refuses to start with:
#   creating <HOME>\AppData\Local\Docker: mkdir <HOME>\AppData\Local\Docker:
#   Cannot create a file when that file already exists.
# i.e. the path exists but mkdir will not create it -> it is not a directory
# from the caller's point of view.
#
# Run through Task Scheduler (scripts/ci/run-one-shot-task.ps1) so the
# Claude package's LocalAppData redirection does not distort the view.
$ErrorActionPreference = 'Continue'
$out = 'E:\microbubble-agent\logs\docker-guard\probe-localappdata-docker.log'
$dir = Split-Path -Parent $out
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
function Say { param([string]$m) $line = '{0}  {1}' -f (Get-Date -Format 'HH:mm:ss'), $m; Write-Host $line; Add-Content -Path $out -Value $line -Encoding UTF8 }

$p   = 'C:\Users\pc\AppData\Local\Docker'
$pkg = 'C:\Users\pc\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local'

Say '=== clean-context view of C:\Users\pc\AppData\Local\Docker ==='
Say ("  Test-Path        : {0}" -f (Test-Path $p))
try {
    $i = Get-Item $p -Force
    Say ("  Name             : {0}" -f $i.Name)
    Say ("  FullName        : {0}" -f $i.FullName)
    Say ("  PSIsContainer   : {0}" -f $i.PSIsContainer)
    Say ("  Mode            : {0}" -f $i.Mode)
    Say ("  Attributes      : {0}" -f $i.Attributes)
    Say ("  LinkType        : {0}" -f $i.LinkType)
    Say ("  Target          : {0}" -f ($i.Target -join ' | '))
} catch {
    Say ("  Get-Item failed : {0}" -f $_.Exception.Message)
}
Say ("  FileInfo.Exists : {0}" -f ([System.IO.FileInfo]::new($p)).Exists)
Say ("  DirInfo.Exists  : {0}" -f ([System.IO.DirectoryInfo]::new($p)).Exists)

Say '--- siblings of "Docker" in %LOCALAPPDATA% ---'
Get-ChildItem 'C:\Users\pc\AppData\Local' -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like 'Docker*' } |
    ForEach-Object { Say ("  {0,-24} {1,-10} {2,-28} link={3} target={4}" -f $_.Name, $_.Mode, $_.Attributes, $_.LinkType, ($_.Target -join ' | ')) }

Say '--- package LocalCache view ---'
Get-ChildItem $pkg -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like 'Docker*' } |
    ForEach-Object { Say ("  {0,-24} {1,-10} {2,-28} link={3} target={4}" -f $_.Name, $_.Mode, $_.Attributes, $_.LinkType, ($_.Target -join ' | ')) }

Say '--- can a fresh directory be created at that path? ---'
try { New-Item -ItemType Directory -Path $p -Force -ErrorAction Stop | Out-Null; Say '  mkdir OK' }
catch { Say ("  mkdir FAILED: {0}" -f $_.Exception.Message) }

Say '--- what is inside it (if anything) ---'
Get-ChildItem $p -Force -ErrorAction SilentlyContinue | ForEach-Object { Say ("  {0,-20} {1}" -f $_.Name, $_.Mode) }
Say '=== end ==='
