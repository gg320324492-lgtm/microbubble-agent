---
name: w2-qwen3-8b-model-restore-2026-08-04
description: W2 +N 拉取 qwen3:8b 模型 + 重跑会议 253 验证本地 LLM 修复 (类 20.148)
metadata: 
  node_type: memory
  type: project
  originSessionId: 3f676532-7417-4633-a1a2-f52dfe398530
  modified: 2026-08-04T16:28:39.893Z
---

# W2 +N qwen3:8b 模型恢复 (2026-08-04, 类 20.148)

## 触发 (2026-08-04)

用户报告"qwen3:8b 之前能正常使用, 现在 252 失败 (404 model not found)".

## 根因

- 实际 `LLM_BACKEND=ollama` (.env 配置正确)
- ollama 容器 healthy, `/api/tags` 返回 `{"models":[]}` — **空**
- worktree + 主仓库的 `data/ollama/models/{blobs,manifests}` 全部空目录
- 之前 docker restart 后模型被清空（没 mount 进 data 目录或者 model 下载后没保存到挂载点）

## 模型选型核实 (WebSearch)

| 模型 | Size | 备注 |
|---|---|---|
| Qwen3 (原版 2025-04) | 0.6B-32B | 8B 是 `.env` 配置, 5.2GB |
| Qwen3-Max (2025-09) | >1T | 太大本地跑不了 |
| Qwen3.5 (2026-02) | **397B** (MoE) | ollama 库 `qwen3.5:397b`, 太大 |
| Qwen3.8 (传闻 2.4T) | **不存在** | 之前搜索的 2.4T 实际是 Kimi K2, 阿里最大仍是 Qwen3-Max |

**结论**: `qwen3:8b` 仍是当前 ollama 库**最适合本地的选择**。

## 修复

```bash
docker exec microbubble-agent-ollama-1 ollama pull qwen3:8b
# 5.2 GB, 5-10 分钟下载
```

实测:
- NAME: qwen3:8b
- ID: 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41
- SIZE: 5.2 GB
- format: gguf, quantization: Q4_K_M, context: 40960, params: 8.2B
- capabilities: completion, tools, thinking

## 端到端验证 (会议 253)

为避免覆盖 252 已入库的转录, 重建会议 253 用 `replay_meeting.py`:
1. start-recording → 253
2. upload-audio → `recordings/10e2953ff824490f9b8c133ba802d6d3.webm`
3. stop-recording → status=processing
4. Celery 后处理 6 阶段 (silero + SenseVoice + LLM polish + LLM title + embedding)

**期望**: 这次 AI 标题生成 / 摘要 / 关键点应该**正常** (qwen3:8b 在 ollama 容器里), 不再 401/404 降级.

## 类 20.148 永久铁律

**本地 ollama 模型持久化纪律**:
1. **模型必须显式 pull** — `docker restart` 不会自动恢复 ollama 模型 (除非正确 bind mount)
2. **bind mount 验证**: `ls data/ollama/models/{blobs,manifests}` 必须有内容 (空 = 模型丢失)
3. **环境检查命令**: `docker exec ollama ollama list` + `curl /api/tags` 双确认
4. **.env 切换 LLM_BACKEND 时同步**:
   - `ollama` → 本地 ollama 容器 (需要 `ollama pull <model>`)
   - `openai_compat` → 走 token-plan / mimo /v1 (需要有效 API key)
   - 切到 `ollama` 但没 pull 模型 = 100% 404 model not found
5. **auto-recovery 链路** 应加入 ollama 模型 pull (Winlogon 触发后确保 ollama 也有模型)

## 0 production code 守恒

- 无代码改动
- 仅 `docker exec ollama pull qwen3:8b` + 端到端验证

## Why

W2 +N 之前的重跑 (会议 252) 因为 LLM 404 失败, status=error, 后续 status schema 修复 (类 20.147) 让前端显示 completed_with_warnings 但 AI 标题仍是 "正在听会（ID X）". 这次 qwen3:8b 拉取后, 会议 253 端到端应能生成**真实 AI 标题** + 摘要 + 关键点.

## How to apply

未来任何"LLM 401/404" 场景:
1. `curl /api/tags` 查 ollama 库 (空 = 重新 pull)
2. `docker exec ollama ollama list` 查已下载模型
3. 检查 .env `LLM_BACKEND` (ollama vs openai_compat)
4. ollama 路径: `docker exec ollama ollama pull <model>` (5-10 分钟)
5. 端到端验证: replay_meeting.py 跑一遍会议, 看 title 是否 AI 生成 (非 "正在听会（ID X）")