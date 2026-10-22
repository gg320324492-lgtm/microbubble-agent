# Verify that a freshly launched process picks up the redirected TEMP/TMP.
# Run through Task Scheduler: the Task Scheduler service composes the
# environment from the registry at process creation, so this is the same
# path a user-launched app would take.
$out = 'E:\microbubble-agent\logs\docker-guard\probe-new-temp.log'
$dir = Split-Path -Parent $out
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add(('{0}  TEMP = {1}' -f (Get-Date -Format 'HH:mm:ss'), $env:TEMP))
$lines.Add(('{0}  TMP  = {1}' -f (Get-Date -Format 'HH:mm:ss'), $env:TMP))
$lines.Add(('{0}  TEMP exists = {1}' -f (Get-Date -Format 'HH:mm:ss'), (Test-Path $env:TEMP)))
try {
    $p = Join-Path $env:TEMP ('probe-' + [guid]::NewGuid().ToString('N') + '.tmp')
    Set-Content -Path $p -Value 'x' -ErrorAction Stop
    $lines.Add(('{0}  writable = True' -f (Get-Date -Format 'HH:mm:ss')))
    Remove-Item $p -Force
} catch {
    $lines.Add(('{0}  writable = False: {1}' -f (Get-Date -Format 'HH:mm:ss'), $_.Exception.Message))
}
$lines | Set-Content -Path $out -Encoding UTF8
