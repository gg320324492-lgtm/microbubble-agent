@echo off
rem GPU ASR daemon auto-start (VibeVoice-ASR-7B worker daemon, 0.0.0.0:8005)
rem 2026-09-30 S2.1: 41GB 生产依赖从隐藏的 .workbuddy\vibevoice-test 归位到
rem data\vibevoice-test (data/ 是本项目运行时数据区, gitignore 内, 不被 compose 挂载)。
rem 显式 VIBEVOICE_HOME 仍优先; 未设时用新位置。
cd /d E:/microbubble-agent
if "%VIBEVOICE_HOME%"=="" set "VIBEVOICE_HOME=E:\microbubble-agent\data\vibevoice-test"
start "gpu-asr-daemon" /min "%VIBEVOICE_HOME%\venv-gpu\Scripts\python.exe" -m app.gpu_worker.server >> "%VIBEVOICE_HOME%\daemon.log" 2>&1
rem Streaming-7B realtime ASR (model lazy-loads on demand, auto-unloads after 10min idle, 0.0.0.0:8006)
start "gpu-streaming" /min "%VIBEVOICE_HOME%\venv-gpu\Scripts\python.exe" -m app.gpu_worker.streaming_server >> "%VIBEVOICE_HOME%\streaming_server.log" 2>&1
