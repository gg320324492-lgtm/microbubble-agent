#!/bin/bash
# 2026-06-30 ASR 迁移: SenseVoice 容器启动脚本
# 与 whisper_entrypoint.sh 同模式: 自动安装 CUDA 运行时库，超时回退 CPU
set -e

# 检查 CUDA 库是否已安装
if python3 -c "import ctypes; ctypes.CDLL('libcublas.so.12')" 2>/dev/null; then
    echo "CUDA 库已就绪"
    export LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.11/site-packages/nvidia/cuda_nvrtc/lib:$LD_LIBRARY_PATH
    exec python3 sensevoice_server.py
fi

# 后台安装 CUDA 库（下次启动即可用）
echo "正在后台安装 CUDA 运行时库..."
pip install --quiet nvidia-cublas-cu12 nvidia-cuda-nvrtc-cu12 &
INSTALL_PID=$!

# 等待最多 120 秒
for i in $(seq 1 120); do
    if ! kill -0 $INSTALL_PID 2>/dev/null; then
        break
    fi
    if python3 -c "import ctypes; ctypes.CDLL('libcublas.so.12')" 2>/dev/null; then
        echo "CUDA 库安装完成"
        export LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.11/site-packages/nvidia/cuda_nvrtc/lib:$LD_LIBRARY_PATH
        exec python3 sensevoice_server.py
    fi
    sleep 1
done

# 超时：回退到 CPU 模式
echo "CUDA 安装超时，回退到 CPU 模式"
export DEVICE=cpu
exec python3 sensevoice_server.py