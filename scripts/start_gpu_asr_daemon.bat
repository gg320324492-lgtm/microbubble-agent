@echo off
rem GPU ASR daemon auto-start (VibeVoice-ASR-7B worker daemon, 0.0.0.0:8005)
rem 2026-09-30 S2.1 前置: 根目录/venv/日志路径收敛到 VIBEVOICE_HOME (默认同历史硬编码)
cd /d E:/microbubble-agent
if "%VIBEVOICE_HOME%"=="" set "VIBEVOICE_HOME=E:\microbubble-agent\.workbuddy\vibevoice-test"
start "gpu-asr-daemon" /min "%VIBEVOICE_HOME%\venv-gpu\Scripts\python.exe" -m app.gpu_worker.server >> "%VIBEVOICE_HOME%\daemon.log" 2>&1
rem Streaming-7B realtime ASR (model lazy-loads on demand, auto-unloads after 10min idle, 0.0.0.0:8006)
start "gpu-streaming" /min "%VIBEVOICE_HOME%\venv-gpu\Scripts\python.exe" -m app.gpu_worker.streaming_server >> "%VIBEVOICE_HOME%\streaming_server.log" 2>&1
