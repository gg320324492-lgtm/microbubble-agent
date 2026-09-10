@echo off
rem GPU ASR daemon auto-start (VibeVoice-ASR-7B worker daemon, 0.0.0.0:8005)
cd /d E:/microbubble-agent
start "gpu-asr-daemon" /min "E:/microbubble-agent/.workbuddy/vibevoice-test/venv-gpu/Scripts/python.exe" -m app.gpu_worker.server >> "E:/microbubble-agent/.workbuddy/vibevoice-test/daemon.log" 2>&1
rem Streaming-7B realtime ASR (model lazy-loads on demand, auto-unloads after 10min idle, 0.0.0.0:8006)
start "gpu-streaming" /min "E:/microbubble-agent/.workbuddy/vibevoice-test/venv-gpu/Scripts/python.exe" -m app.gpu_worker.streaming_server >> "E:/microbubble-agent/.workbuddy/vibevoice-test/streaming_server.log" 2>&1
