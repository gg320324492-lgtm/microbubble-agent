<#
.SYNOPSIS
  Verify an installed ScientificResearchOS application package.

.DESCRIPTION
  R6 release acceptance script. Validates the post-install state of the
  ScientificResearchOS NSIS installer:

    1. Installer binary exists at the provided path.
    2. Silent install to $InstallDir succeeds (exit 0).
    3. ScientificResearchOS.exe exists in the install directory.
    4. App launches without crashing for >= 5 seconds.
    5. Working directory is left for the operator to inspect.

.PARAMETER InstallerPath
  Path to the electron-builder .exe produced by `build:release-win`,
  e.g. release\1.0.0\ScientificResearchOS-1.0.0-x64.exe.

.PARAMETER InstallDir
  Custom install directory. Defaults to "$env:ProgramFiles\ScientificResearchOS".

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\release\verify-installed-app.ps1 `
    -InstallerPath release\1.0.0\ScientificResearchOS-1.0.0-x64.exe
#>

param(
  [Parameter(Mandatory=$true)][string]$InstallerPath,
  [string]$InstallDir = "$env:ProgramFiles\ScientificResearchOS"
)

$ErrorActionPreference = "Stop"

function Step($n, $msg) {
  Write-Host "[$n] $msg"
}

# 1) Installer must exist
Step "1/5" "Checking installer at $InstallerPath"
if (-not (Test-Path $InstallerPath)) {
  Write-Error "Installer not found: $InstallerPath"
  exit 1
}

# 2) Silent install
Step "2/5" "Installing to $InstallDir (silent mode /S)..."
$installArgs = @("/S", "/D=$InstallDir")
$proc = Start-Process -FilePath $InstallerPath -ArgumentList $installArgs -Wait -PassThru -NoNewWindow
if ($proc.ExitCode -ne 0) {
  Write-Error "Installer exit code: $($proc.ExitCode)"
  exit 2
}

# 3) Executable present
Step "3/5" "Verifying executable..."
$exe = Join-Path $InstallDir "ScientificResearchOS.exe"
if (-not (Test-Path $exe)) {
  Write-Error "Executable not found: $exe"
  exit 3
}

# 4) Smoke launch: keep alive for at least 5 seconds without crashing
Step "4/5" "Smoke launching app..."
$app = Start-Process -FilePath $exe -PassThru
Start-Sleep -Seconds 5
if ($app.HasExited) {
  Write-Error "App exited immediately (code: $($app.ExitCode))"
  exit 4
}

# 5) Surface process info for the operator
Step "5/5" "App launched OK (PID $($app.Id)). Operator can review UI before terminating."
Write-Host "[verify-installed-app] PASS"
exit 0
