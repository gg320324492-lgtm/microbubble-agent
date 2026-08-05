---
name: w2-qwen3-thinking-mode-title-fix-2026-08-05
description: W2 +N qwen3:8b thinking mode 修复 + 4 个 placeholder 会议标题生成 (类 20.151)
metadata:
  type: project
---

# W2 +N qwen3:8b thinking mode 修复 (2026-08-05, 类 20.151)

## 触发 (2026-08-05)

用户报告 "会议标题 + 242 会议转录内容有问题":
- 4 个会议 ID 12/64/68/70/71/83/85/95/120/121/135/137/151/167/203/202/229/242/260 全部 "正在听会（ID X）" 占位符
- 之前 18 个会议 reprocess 触发了 title 重生成 (ollama 401 失败)
- 4 个 ID 202/229/242/260 一直没改

## 根因: qwen3:8b thinking mode

**实测现象**:
```python
curl -s http://ollama:11434/api/chat -d '{"model": "qwen3:8b", "messages": [...]}'
# 响应: content=""  thinking="好的, 我需要根据用户提供的会议内容..."
# done_reason="length"  eval_count=100
```

**100 token 全用于 thinking 过程, content 字段空字符串**—— qwen3:8b 默认开启 thinking mode (类似 o1 / R1 风格), 必须用 `think: false` 或 `thinking: {type: "disabled"}` 关闭.

后端 `meeting_analysis_service.generate_title` 实际生产代码用 `thinking={"type": "disabled"}` ✓, 但我的修复脚本漏了这个参数.

## 修复 (类 20.151)

**scripts/regen_meeting_titles.py** 新增:

```python
data=json.dumps({
    "model": "qwen3:8b",
    "messages": [...],
    "stream": False,
    "think": False,  # 关键: 禁用 thinking mode (qwen3:8b 默认开启)
    "options": {
        "temperature": 0.3,
        "num_predict": 100,
    },
}).encode("utf-8")
```

**SQL UPDATE 路径**:
- bash 中文引号转义陷阱 → 用 `repr(sql)` 写临时文件 + `psql -f file.sql` 避免命令行引号

## 实测结果

为 4 个会议生成 AI 标题:

| ID | 旧标题 | AI 新标题 |
|---|---|---|
| 229 | 正在听会（ID 229） | 会议讨论地图截图与区域展示事宜 |
| 202 | 正在听会（ID 202） | 臭氧纳米气泡对污染物竞争反应研究 |
| 242 | 正在听会（ID 242） | 设备尺寸调整与安装问题讨论 |
| 260 | 正在听会（ID 260） | 水处理实验：有鱼与无鱼对比观察 |

## 类 20.151 永久铁律

**qwen3:8b 本地调用必加 `think: false`**:
- ❌ 默认 thinking mode → 100 token 全用于思考过程 → content 空字符串
- ✅ `think: false` 或 `thinking: {type: "disabled"}` → 直接输出 content
- 后端 `meeting_analysis_service.py` 已用 `thinking={"type": "disabled"}` ✓
- 任何**直接 curl ollama** 或自写脚本必须加 `think: false`

## 0 production code 守恒

仅 `scripts/regen_meeting_titles.py` 新增 (~110 行), **没改 app 代码** (后端 service 已正确).

## Why

W2 +N 阶段 2.5 (AI 润色) / 阶段 5 (标题生成) 之前失败:
- 老 LLM key 401 (token-plan 失效)
- 拉 qwen3:8b 后, **thinking mode 让 content 空** → 熔断 fallback "未命名会议"

类 20.151 修复后, 直接 ollama 调用正常工作.

## How to apply

未来任何"直接调 ollama"场景:
1. 必须 `think: false` 或 `thinking: {type: "disabled"}`
2. bash 中文引号 → 写临时 SQL 文件 + `psql -f`
3. 验证 `content` 字段非空再写 DB

## 关联沉淀

- **类 20.148** qwen3:8b 模型 pull
- **类 20.149** celery GPU 资源
- **类 20.151** (新) qwen3 thinking mode 关闭
