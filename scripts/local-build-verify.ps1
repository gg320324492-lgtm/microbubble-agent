# MicroBubble Frontend Build Verifier - Run after npm run build
# Usage: powershell scripts/local-build-verify.ps1
# Purpose: Catch dist issues locally before pushing to GitHub

param(
    [switch]$Strict = $false
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DistDir = Join-Path $ProjectRoot "web\dist"
$MinSizeBytes = 500 * 1024  # 500KB minimum

function Write-Line {
    param([string]$Text, [string]$Color = "White")
    Write-Host $Text -ForegroundColor $Color
}

if (-not (Test-Path $DistDir)) {
    Write-Line "[ERROR] dist directory not found: $DistDir" "Red"
    Write-Line "Please run: cd web && npm run build" "Yellow"
    exit 1
}

# 1. index.html
$indexFile = Join-Path $DistDir "index.html"
if (-not (Test-Path $indexFile)) {
    Write-Line "[ERROR] Missing index.html" "Red"
    exit 1
}

# 2. assets/ directory
$assetsDir = Join-Path $DistDir "assets"
if (-not (Test-Path $assetsDir)) {
    Write-Line "[ERROR] Missing assets/ directory" "Red"
    exit 1
}

# 3. JS files
$jsFiles = @(Get-ChildItem $assetsDir -Filter "*.js" -ErrorAction SilentlyContinue)
if ($jsFiles.Count -eq 0) {
    Write-Line "[ERROR] No .js files in assets/" "Red"
    exit 1
}

# 4. CSS files
$cssFiles = @(Get-ChildItem $assetsDir -Filter "*.css" -ErrorAction SilentlyContinue)
if ($cssFiles.Count -eq 0) {
    Write-Line "[WARN] No .css files in assets/" "Yellow"
}

# 5. Total size
$totalSize = (Get-ChildItem $DistDir -Recurse -File | Measure-Object -Property Length -Sum).Sum
$totalSizeMB = [math]::Round($totalSize / 1MB, 2)

if ($totalSize -lt $MinSizeBytes) {
    Write-Line ("[ERROR] dist total size too small: {0} MB (min {1} MB)" -f $totalSizeMB, [math]::Round($MinSizeBytes / 1MB, 2)) "Red"
    if ($Strict) { exit 1 }
}

# 6. Report
$indexExists = Test-Path $indexFile
$indexTime = (Get-Item $indexFile).LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')
$largestJs = $jsFiles | Sort-Object Length -Descending | Select-Object -First 1
$largestJsSize = if ($largestJs) { [math]::Round($largestJs.Length / 1KB, 1) } else { 0 }
$largestJsName = if ($largestJs) { $largestJs.Name } else { "(none)" }

Write-Host ""
Write-Line "========================================" "Cyan"
Write-Line "  MicroBubble Frontend Build Verify" "Cyan"
Write-Line "========================================" "Cyan"
Write-Line ("  index.html:        {0}" -f $(if ($indexExists) { "OK" } else { "MISSING" }))
Write-Line ("  JS files:          {0}" -f $jsFiles.Count)
Write-Line ("  CSS files:         {0}" -f $cssFiles.Count)
Write-Line ("  Total size:        {0} MB" -f $totalSizeMB)
Write-Line ("  Build time:        {0}" -f $indexTime)
Write-Line ("  Main entry:        {0} ({1} KB)" -f $largestJsName, $largestJsSize)
Write-Line "========================================" "Cyan"
Write-Host ""

Write-Line "[OK] Verification passed. You can now:" "Green"
Write-Line "  git add -f web/dist/" "White"
Write-Line "  git commit -m 'build: update frontend dist'" "White"
Write-Line "  git push origin main" "White"
Write-Host ""

exit 0
