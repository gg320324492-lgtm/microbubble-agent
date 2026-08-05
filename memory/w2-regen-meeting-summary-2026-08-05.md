# W2 +N 老会议补 AI summary + key_points (类 20.156, 2026-08-05)

## 事故

用户报告: 3 个 6 月份的会议 ("臭氧微纳米气泡实验条件的影响"、"实验数据可靠性排查与实验条件分析"、"臭氧气泡实验变量分析") 没有"转录内容"。

## 排查

DB 实测:
- 3 个会议都有 `transcript_polished` (17/15/21 段, 字符 6672/3505/4200)
- 但 `summary` = 0, `key_points` = NULL, `audio_url` = 空
- 状态 `completed`

**根因**: 历史会议 (6 月份) 后处理只跑了 transcript polish, 但 **AI summary + key_points 生成阶段失败** (可能当时 LLM API key 失效或阶段 5 降级)。这导致前端"会议纪要"模块空白。

## 修复

1. 写 `regen_summary.py` (54 行) 用 ollama qwen3:8b 直接调, 给 3 个会议重生成 summary + key_points
2. 模型用 qwen3:8b + `think: False` + `format: "json"` (类 20.151 永久铁律)
3. 容器内跑 (`docker exec ... PYTHONPATH=/app python /tmp/regen_summary.py`)
4. 写入 DB: `m.summary = res["summary"]` + `m.key_points = res["key_points"]` + `m.updated_at = now()`

## 结果 (实测)

| ID | 会议标题 | summary 字符 | key_points 数量 |
|---|---|---|---|
| 68 | 臭氧气泡实验变量分析 | 116 | 7 |
| 70 | 实验数据可靠性排查与实验条件分析 | 182 | 5 |
| 71 | 臭氧微纳米气泡实验条件的影响 | 166 | 7 |

## 永久铁律 (类 20.156)

**历史会议"transcript 有但 summary 无"**是常见数据漂移模式, **必须用 direct ollama + format:json 重生成**, 不能用 LLMClient (auth 复杂)。`scripts/regen_meeting_titles.py` (类 20.151) 用同样模式, 沿用即可。

**部署纪律**: 任何会议后处理流水线 (5/6 阶段) 跑完后, 必须验证 4 个字段全部有值:
1. `transcript` (raw)
2. `transcript_polished` (润色)
3. `summary` (AI 摘要)
4. `key_points` (AI 关键点)

任一字段 NULL 即视为该会议"未完成", 不能标 `completed`。

## 0 production code 守恒

- 仅写 `regen_summary.py` (54 行, 临时脚本)
- 不动 app/ / alembic / docker-compose
- regen 完成后可保留供未来"补生成"使用
