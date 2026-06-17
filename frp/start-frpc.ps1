# 启动 frpc 客户端（隐藏窗口）
$existing = Get-Process -Name "frpc" -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "frpc 已在运行 (PID: $($existing.Id))"
    exit 0
}

$proc = Start-Process -FilePath "E:\microbubble-agent\frp\frpc.exe" `
    -ArgumentList "-c","E:\microbubble-agent\frp\frpc.toml" `
    -WorkingDirectory "E:\microbubble-agent\frp" `
    -WindowStyle Hidden -PassThru
Write-Host "frpc 已启动 (PID: $($proc.Id))"
