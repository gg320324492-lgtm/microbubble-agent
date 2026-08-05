---
name: w2-replay-meeting-2026-08-04
description: W2 +N 重跑会议 (类 20.146 端到端会议重跑) + 实战发现 3 铁律
metadata: 
  node_type: memory
  type: project
  originSessionId: 3f676532-7417-4633-a1a2-f52dfe398530
  modified: 2026-08-04T15:37:44.045Z
---

# W2 +N 重跑会议 (2026-08-04, 类 20.146)

## 触发 (2026-08-04)

用户今天有听会记录, 音频文件放桌面:
- **文件**: `C:\Users\pc\Desktop\天津大学环境科学与工程学院 4.m4a`
- **大小**: 9.46 MB
- **格式**: Apple iTunes ALAC/AAC-LC (.M4A) Audio
- **创建时间**: 2026-08-04 22:08

**任务**: 端到端重跑会议 (login → start → upload → stop → 后处理 → 验证).

## 3 大发现 (实战沉淀)

### 1. bash 路径特殊字符问题 (类 20.146 准备阶段)

```
bash: file=@"/c/Users/pc/Desktop/天津大学环境科学与工程学院 4.m4a" → 路径中文字符 + 空格, curl HTTP 000
```

**解决**: `scripts/replay_meeting.py` Python 版, 用 `requests` 库 + Windows 路径 (r'C:\...') 直接处理, 绕开 bash 引号.

### 2. silero-vad 模型缺失 (类 20.138 类, 实战发现)

- 错误: `RuntimeError: 无法加载 silero-vad 模型, 请检查网络连接或手动下载模型到 /root/.cache/torch/hub`
- 根因: GitHub 限流 + 容器内 `~/.cache/torch/hub/` 只有 20 字节 trusted_list, **没模型**
- 修复: `models/torch_hub/snakers4_silero-vad_master/` 从主仓库 cp 到 worktree (bind mount 路径在 worktree 下, **不是**主仓库)
- 教训: 任何模型/HF cache 类 bind mount, 都要确认 worktree 路径有数据 (主仓库与 worktree 物理分离)

### 3. UnboundLocalError: polished_segments (类 20.146 核心修复)

`app/services/post_meeting_tasks.py:692-704` 的 polish 块:
```python
try:
    polish_result = await polish_segments_with_lock(...)
    polished_segments = polish_result.get("polished", [])  # ← 只有 try 内赋值
    if polished_segments:
        ...
except Exception as e:
    logger.warning(...)  # ← 这里没初始化 polished_segments!
await _persist_stage(..., metrics={"polished_segments": len(polished_segments) ...})  # ← 抛 UnboundLocalError
```

**根因**: 当 `polish_segments_with_lock` 抛异常 (LLM 401, 404 model not found), polished_segments 未定义. 后续 `_persist_stage` 引用就崩.

**修复** (类 20.146 实战沉淀):
```python
except Exception as e:
    polished_segments = []  # 类 20.146 W2+N 修复: 显式初始化避免 UnboundLocalError
    logger.warning(...)
```

并**加防御**: `polished_segments = polish_result.get("polished", []) or []` (双层防御).

## 实战额外发现

### pyc 缓存遮蔽 .py 改动

`__pycache__/post_meeting_tasks.cpython-311.pyc` 在容器内**比 .py 时间新**但内容不对, Python 不会重新编译. **必须**:
```bash
docker exec <container> bash -c 'find /app -name __pycache__ -type d -exec rm -rf {} +'
docker restart <container>
```

### 多个 celery worker 抢任务

- `celery-worker` (general, 32 prefork) 监听 `celery` 队列
- `celery-meeting-worker` (solo, 1 prefork) 监听 `meeting-processing` 队列
- 重启 `app-1` 后**不一定重启 celery worker**, 代码改动不生效!

**修复**: 重启会议后处理前必须重启 **all 3 容器**: app-1, celery-worker, celery-meeting-worker.

### 端到端完整流程 (实测 252 会议, PID 40)

1. **POST /auth/login** → JWT (限流 5/5min 保护)
2. **POST /meetings/start-recording** → meeting_id 252, status=recording, title="正在听会（ID 252）"
3. **POST /meetings/252/upload-audio** → audio_url 落 MinIO (recordings/{uuid}.webm), last_chunk_index=0, total_chunks=1
4. **POST /meetings/252/stop-recording** → status=processing, 触发 Celery post_meeting_process
5. **Celery 6 阶段**:
   - 阶段 0: 下载音频 + silero-vad 分段 (524 段, 1119.8s)
   - 阶段 1: SenseVoice ASR (524 次 HTTP 转写)
   - 阶段 1.3: 语义断句
   - 阶段 1.5: 低占用过滤 (去 "嗯" 等幻觉)
   - 阶段 2: 说话人聚类 (kmeans)
   - 阶段 2.5: AI 润色 (降级: LLM 401 → 用原文)
   - 阶段 3: 关键点/决议/摘要 (LLM, 401 降级)
   - 阶段 5: AI 标题生成 (替换 "正在听会（ID 252）")
   - 阶段 6: 知识图谱嵌入
6. **GET /meetings/252** 轮询 status=completed (10-20 分钟)

## 沉淀

### 类 20.146 永久铁律

**W2 +N 重跑会议端到端**:
1. 端到端 6 步 API 链 (login → start → upload → stop → 轮询 → verify)
2. bash 路径特殊字符问题 → 用 Python `requests` 库
3. silero-vad 模型必须 `models/torch_hub/snakers4_silero-vad_master/` 存在 (worktree 与主仓库物理分离)
4. 业务代码 polished_segments 类变量必须 `or []` 双层防御 + except 显式初始化
5. 重启容器后必须清 `__pycache__/` 否则 .pyc 缓存遮蔽 .py 改动
6. 多个 celery worker 抢任务 (celery + celery-meeting-worker), 重启**所有 3 容器**才生效
7. LLM 401 失败时阶段 5 降级 (转录仍正确入库), 整会议仍标 completed_with_warnings

## 产物

- `scripts/replay_meeting.py` (Python 版, ~120 行, 6 步端到端)
- `scripts/replay_meeting.sh` (Bash 版备用, 路径不能有特殊字符)
- 修复: `app/services/post_meeting_tasks.py:692-704` (polished_segments 双层防御 + except 初始化)
- 修复: `models/torch_hub/snakers4_silero-vad_master/` 同步到 worktree

## 0 production code 守恒

仅修改 1 个文件 (post_meeting_tasks.py 双层防御, 2 行) + 同步模型目录. 不动 `app/api/` `web/src/` `alembic/versions/`.

## Why

W100 +N 业务数据恢复后, 用户测试 "今天会议" 流程, 暴露了:
1. 端到端会议重跑**无脚本** (类 20.146 缺失)
2. silero-vad 模型**在 worktree 路径缺失** (类 20.138 类问题, 之前主仓库 cp 同步遗漏)
3. polished_segments UnboundLocalError (生产代码 bug, **没保护** polish 异常时的变量初始化)
4. __pycache__ + 多个 celery worker 的代码生效陷阱 (运维级问题)

类 20.146 把这 4 件事沉淀为永久铁律 + 1 个 Python 重跑脚本.