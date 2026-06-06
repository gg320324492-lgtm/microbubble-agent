param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"

$services = @("celery-worker", "celery-beat")

Write-Host "Stopping Celery services..."
docker compose stop $services

Write-Host "Removing Celery containers..."
docker compose rm -f $services

$upArgs = @("compose", "up", "-d")
if ($Build) {
    $upArgs += "--build"
}
$upArgs += $services

Write-Host "Starting Celery services..."
docker @upArgs

Write-Host "Celery services recreated. Checking status..."
docker compose ps celery-worker celery-beat
