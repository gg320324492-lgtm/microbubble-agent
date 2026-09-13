@echo off
chcp 65001 >nul
echo === 重启 GPU ASR 服务（隐藏窗口运行，日志写入 logs\）===

echo [1/3] 结束现有 app.gpu_worker 进程...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -match 'app\.gpu_worker' } | ForEach-Object { Write-Host ('  kill PID ' + $_.ProcessId + ' ' + $_.Name); Stop-Process -Id $_.ProcessId -Force }"

echo Waiting for old processes to release ports and GPU...
timeout /t 8 /nobreak >nul

if not exist "E:\microbubble-agent\logs" mkdir "E:\microbubble-agent\logs"

echo [2/3] 启动 gpu-asr-daemon (:8005, 日志 logs\gpu-asr-daemon.log)...
powershell -NoProfile -Command "Start-Process -WindowStyle Hidden -WorkingDirectory 'E:\microbubble-agent' -FilePath 'E:\microbubble-agent\.workbuddy\vibevoice-test\venv-gpu\Scripts\python.exe' -ArgumentList '-m','app.gpu_worker.server' -RedirectStandardOutput 'E:\microbubble-agent\logs\gpu-asr-daemon.log' -RedirectStandardError 'E:\microbubble-agent\logs\gpu-asr-daemon.err.log'"

echo [3/3] 启动 gpu-streaming (:8006, 日志 logs\gpu-streaming.log)...
powershell -NoProfile -Command "Start-Process -WindowStyle Hidden -WorkingDirectory 'E:\microbubble-agent' -FilePath 'E:\microbubble-agent\.workbuddy\vibevoice-test\venv-gpu\Scripts\python.exe' -ArgumentList '-m','app.gpu_worker.streaming_server' -RedirectStandardOutput 'E:\microbubble-agent\logs\gpu-streaming.log' -RedirectStandardError 'E:\microbubble-agent\logs\gpu-streaming.err.log'"

echo 等待 5 秒让服务就绪...
timeout /t 5 /nobreak >nul

echo 健康检查:
powershell -NoProfile -Command "try { '  8005: ' + (Invoke-RestMethod http://127.0.0.1:8005/health | ConvertTo-Json -Compress) } catch { '  8005 未响应: ' + $_.Exception.Message }; try { '  8006: ' + (Invoke-RestMethod http://127.0.0.1:8006/healthz | ConvertTo-Json -Compress) } catch { '  8006 未响应: ' + $_.Exception.Message }"

echo.
echo 完成，服务已在后台隐藏运行。此窗口可以关闭。
pause
