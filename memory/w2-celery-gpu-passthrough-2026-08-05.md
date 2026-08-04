---
name: w2-celery-gpu-passthrough-2026-08-05
description: W2 +N celery-worker GPU 资源 + 端到端会议重跑指南 (类 20.149)
metadata: 
  node_type: memory
  type: project
  originSessionId: 3f676532-7417-4633-a1a2-f52dfe398530
  modified: 2026-08-04T23:45:46.290Z
---

# W2 +N celery-worker GPU (2026-08-05, 类 20.149)

## 触发 (2026-08-04)

会议 252/253/254 重跑时 3D-Speaker 阶段卡死:
- celery worker CPU 99.97% 单核 100% 卡 5+ 分钟无进展
- 524 段 ERes2Net 声纹嵌入 CPU 推理极慢
- sensevoice ASR 50s 完成 + 3D-Speaker 无进展

## 根因

`docker-compose.yml` celery-worker + celery-meeting-worker **没 GPU 资源**:
```yaml
celery-worker:
  command: celery -A app.core.celery worker ...
  mem_limit: 4g
  # ❌ 没 deploy.resources.reservations.devices
```

而 `app` 容器有 `driver: nvidia, count: 1, capabilities: [gpu]` (SenseVoice ASR 用 GPU)。

## 修复 (class 20.149)

```yaml
celery-worker:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]

celery-meeting-worker:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

**`celery-beat` 不需要 GPU** (只调度不跑任务, 保持现状)。

## 端到端验证 (用户操作后)

### 1. 启用 Docker Desktop GPU passthrough (用户操作)

**Windows**:
1. 系统托盘 → 右键 Docker Desktop 图标 → Dashboard
2. 右上角 ⚙ Settings → Resources → WSL Integration
3. 勾选 "Enable integration with my default WSL distro"
4. (Docker Desktop 4.40+) Resources → GPU 也确认开启
5. Apply & Restart

**前置条件**:
- Windows 11 + WSL2 kernel 5.15+
- NVIDIA driver 525+

### 2. 验证容器内 GPU 可见

```bash
# 重启 celery worker 应用新 compose
docker compose -f docker-compose.yml -f docker-compose.dev.yml -p microbubble-agent up -d

# 验证 GPU
MSYS_NO_PATHCONV=1 docker exec microbubble-agent-celery-worker-1 nvidia-smi 2>&1 | head -10
# 应输出 NVIDIA-SMI with driver version, GPU 列表, 利用率
```

### 3. 重跑会议验证 3D-Speaker 几秒完成

```bash
# 用 zhanghongkui (created_by 之前我们确认的)
TOKEN=$(curl -sk -X POST "https://agent.mnb-lab.cn/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"zhanghongkui","password":"123456"}' \
  | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# 6 步端到端:
# 1. start-recording → meeting_id
# 2. upload-audio → MinIO
# 3. SQL 修 last_chunk_index=0 (一次性上传)
# 4. stop-recording → Celery post_meeting
# 5. 轮询 status=completed
# 6. 验证 AI 标题 (qwen3:8b 生成) + transcript + polished
```

**期望**:

| 阶段 | 无 GPU (CPU) | 有 GPU |
|---|---|---|
| VAD (silero) | 10s | 10s |
| SenseVoice ASR | 50s | 50s |
| 3D-Speaker 524 段 | **5+ 分钟卡死** | **几秒** |
| AI Polish (qwen3:8b) | 30s | 30s |
| AI 标题生成 | 5s | 5s |
| **总耗时** | **永远 processing** | **~2-3 分钟** |

如果在 GPU 启用后 3D-Speaker 仍跑 5+ 分钟, 排查:
- 容器内 `nvidia-smi` 是否能列出 GPU (driver/passthrough 问题)
- `voiceprint_service.py` 是否实际用了 GPU (检查 `device='cuda'`)

### 4. 验证完清状态

```bash
# 清理测试会议
TOKEN=$(...)
curl -sk -X DELETE "https://agent.mnb-lab.cn/api/v1/meetings/<meeting_id>" -H "Authorization: Bearer $TOKEN"
```

## 0 production code 守恒

仅 docker-compose.yml 改 2 服务 + GPU 资源。**无 app 代码改动**。

## Why

会议 252/253/254 重跑失败直接根因是 3D-Speaker CPU 推理慢, 之前被误诊为 LLM 401 (类 20.147)。GPU 启用后整会议流水线应在 2-3 分钟内完成, 印证**类 20.152 自愈 + 类 20.149 GPU + 类 20.147 status schema** 整个修复链生效。

## How to apply

未来"会议重跑卡 3D-Speaker"场景:
1. 检查 `docker exec celery-worker nvidia-smi` 看 GPU 是否可见
2. 若无, 让用户在 Docker Desktop 设置启用 WSL2 GPU passthrough
3. 若有但仍慢, 改 `app/services/voiceprint_service.py` 的 batch_size 看 CPU vs GPU 平衡
4. 类 20.149 dispatch: 大批量 (>100 段) 必须 GPU, 小批量 (<50 段) CPU 也快

## 关联沉淀

- **类 20.143** (Winlogon 7002 自动恢复)
- **类 20.147** (status schema 长度)
- **类 20.148** (qwen3:8b 模型 pull)
- **类 20.149** (celery GPU 资源) ← 本次
- **类 20.152** (init_db 自愈增强)