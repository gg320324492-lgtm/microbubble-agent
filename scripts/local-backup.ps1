# MicroBubble Local Database Backup - Run daily at 02:00
# Usage: powershell scripts/local-backup.ps1 [-KeepDays N]
# Mirrors scripts/backup_db.sh (Linux) but uses Windows-native .NET gzip

param(
    [int]$KeepDays = 7
)

$ErrorActionPreference = "Continue"  # Don't throw on native stderr
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$BackupDir = Join-Path $ProjectRoot "backups"
$LogDir = Join-Path $ProjectRoot "logs\backup"
$LogFile = Join-Path $LogDir ("backup-{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
$DBContainer = "microbubble-agent-db-1"
$DBUser = "postgres"
$DBName = "microbubble"
$MinSizeBytes = 100

New-Item -ItemType Directory -Path $BackupDir, $LogDir -Force | Out-Null

function Write-Log {
    param([string]$Level, [string]$Message, [hashtable]$Extra)
    if ($Extra -eq $null) { $Extra = @{} }
    $entry = [ordered]@{
        timestamp = Get-Date -Format "o"
        level = $Level
        script = "local-backup"
        message = $Message
    }
    foreach ($k in $Extra.Keys) { $entry[$k] = $Extra[$k] }
    $json = $entry | ConvertTo-Json -Compress
    Add-Content -Path $LogFile -Value $json -Encoding UTF8
    if ($Level -eq "ERROR") {
        Write-Host "[$Level] $Message" -ForegroundColor Red
    } else {
        Write-Host "[$Level] $Message"
    }
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupFile = Join-Path $BackupDir ("microbubble_{0}.sql.gz" -f $Timestamp)

try {
    Write-Log "INFO" "Starting database backup" @{ container = $DBContainer; output = $BackupFile }

    $containerState = docker inspect --format='{{.State.Running}}' $DBContainer 2>$null
    if ($containerState -ne "true") {
        throw "Database container $DBContainer is not running (state=$containerState)"
    }

    # pg_dump -> temp file (UTF-8)
    $dumpFile = [System.IO.Path]::GetTempFileName()
    docker exec $DBContainer pg_dump -U $DBUser $DBName | Out-File -FilePath $dumpFile -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw "pg_dump failed (exit=$LASTEXITCODE)" }

    # .NET GZipStream compression
    $gzFile = $dumpFile + ".gz"
    $inputStream = [System.IO.File]::OpenRead($dumpFile)
    $outputStream = [System.IO.File]::Create($gzFile)
    $gz = New-Object System.IO.Compression.GZipStream($outputStream, [System.IO.Compression.CompressionLevel]::Optimal)
    $inputStream.CopyTo($gz)
    $gz.Close()
    $outputStream.Close()
    $inputStream.Close()
    Remove-Item $dumpFile -Force

    Move-Item $gzFile $BackupFile -Force

    $fileSize = (Get-Item $BackupFile).Length
    if ($fileSize -le $MinSizeBytes) {
        Remove-Item $BackupFile -Force
        throw "Backup file too small ($fileSize bytes <= $MinSizeBytes), may be empty"
    }

    $sizeMB = [math]::Round($fileSize / 1MB, 2)
    Write-Log "INFO" "Backup successful" @{ file = $BackupFile; size_bytes = $fileSize; size_mb = $sizeMB }

    # Cleanup expired backups
    $expired = Get-ChildItem $BackupDir -Filter "microbubble_*.sql.gz" |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$KeepDays) }
    foreach ($f in $expired) {
        Remove-Item $f.FullName -Force
        Write-Log "INFO" "Cleaned up expired backup" @{ file = $f.Name; age_days = [math]::Round(((Get-Date) - $f.LastWriteTime).TotalDays, 1) }
    }

    # List current backups
    $backups = Get-ChildItem $BackupDir -Filter "microbubble_*.sql.gz" | Sort-Object LastWriteTime -Descending
    $fileList = @()
    foreach ($b in ($backups | Select-Object -First 5)) {
        $fileList += @{ name = $b.Name; size_mb = [math]::Round($b.Length / 1MB, 2) }
    }
    Write-Log "INFO" "Current backup list" @{ count = $backups.Count; recent = $fileList }

    exit 0
}
catch {
    Write-Log "ERROR" "Backup failed" @{ error = $_.Exception.Message }
    exit 1
}
