"""DEBUG 临时 hook: dump LLM 输入到 /tmp/llm_input_dump/

2026-07-02 Phase I.3 取证工具
通过环境变量 DEBUG_DUMP_LLM_INPUT=1 启用。
不会影响正常路径, 默认关闭, 0 开销。

使用:
  1. .env DEBUG_DUMP_LLM_INPUT=1
  2. docker compose restart app
  3. 跑 5 题样本 (用 qa-bench 或 curl)
  4. 检查 /tmp/llm_input_dump/ 每个 dump 文件

每个 dump 文件格式:
{
  "ts": 1782935527934,           # epoch ms
  "phase": "phase1-round0",      # 调用标签
  "model": "mimo-v2.5",
  "system": "...",                # system prompt string
  "messages_count": 15,
  "messages_size_bytes": 12500,
  "messages": [                   # 每个 message 的简化的 {role, content_preview}
    {"role": "user", "len": 5300, "blocks": ["text", "tool_result"], "tool_results_count": 4},
    {"role": "assistant", "len": 200, "blocks": ["text"], "tool_uses_count": 0},
    ...
  ],
  "tools_count": 17              # Number of available tool schemas
}
"""
import os
import json
import time
from pathlib import Path
from typing import List, Optional


def is_enabled() -> bool:
    """检查 DEBUG_DUMP_LLM_INPUT 环境变量是否开启"""
    return bool(os.getenv("DEBUG_DUMP_LLM_INPUT"))


def _content_preview(content):
    """简化 content 结构用于 dump (避免巨大输出)"""
    if isinstance(content, str):
        return {"type": "str", "len": len(content)}
    elif isinstance(content, list):
        blocks = []
        tool_results_count = 0
        tool_uses_count = 0
        total_text_len = 0
        for b in content:
            if not isinstance(b, dict):
                continue
            btype = b.get("type", "unknown")
            blocks.append(btype)
            if btype == "tool_result":
                tool_results_count += 1
                tc = b.get("content", "")
                if isinstance(tc, str):
                    total_text_len += len(tc)
            elif btype == "text":
                total_text_len += len(b.get("text", ""))
            elif btype == "tool_use":
                tool_uses_count += 1
        return {
            "type": "list",
            "len": total_text_len,
            "blocks": blocks[:10],  # 只保留前 10 个 block 类型
            "blocks_total": len(blocks),
            "tool_results_count": tool_results_count,
            "tool_uses_count": tool_uses_count,
        }
    else:
        return {"type": type(content).__name__, "repr": str(content)[:100]}


def maybe_dump(
    messages: Optional[List[dict]],
    system: Optional[str],
    tools: Optional[List[dict]],
    model: str,
    phase_label: str,
    extra: Optional[dict] = None,
) -> None:
    """如果 DEBUG_DUMP_LLM_INPUT=1, dump 到 /tmp/llm_input_dump/{ts}_{phase_label}.json

    Args:
        messages: LLM 收到的 messages 列表
        system: system prompt string
        tools: tool schemas 列表 (Optional)
        model: 模型名 (e.g. "mimo-v2.5")
        phase_label: 调用标签 (e.g. "phase1-round0", "phase2-synth")
        extra: 额外 metadata to include
    """
    if not is_enabled():
        return

    ts = int(time.time() * 1000)
    dump_path = Path(f"/tmp/llm_input_dump/{ts}_{phase_label}.json")
    dump_path.parent.mkdir(parents=True, exist_ok=True)

    # 计算 messages 总大小（用于观察累积趋势）
    messages_count = len(messages) if messages else 0
    total_msg_size = sum(
        len(json.dumps(m, ensure_ascii=False, default=str))
        for m in (messages or [])
    )

    # 简化 messages 预览 (避免 dump 文件过大)
    messages_preview = []
    for m in (messages or []):
        if not isinstance(m, dict):
            continue
        messages_preview.append({
            "role": m.get("role"),
            "content_preview": _content_preview(m.get("content")),
        })

    dump_data = {
        "ts": ts,
        "phase": phase_label,
        "model": model,
        "system_len": len(system) if system else 0,
        "system_preview": (system[:500] + "...") if system and len(system) > 500 else system,
        "messages_count": messages_count,
        "messages_size_bytes": total_msg_size,
        "messages": messages_preview,
        "tools_count": len(tools) if tools else 0,
    }
    if extra:
        dump_data.update(extra)

    try:
        dump_path.write_text(
            json.dumps(dump_data, ensure_ascii=False, default=str, indent=2)
        )
        # 限制 dump 文件总数 (最多 200 个, 超过从旧删新)
        dump_dir = dump_path.parent
        files = sorted(dump_dir.glob("*.json"), key=lambda f: f.stat().st_mtime)
        if len(files) > 200:
            for f in files[:-200]:
                f.unlink()
        print(f"[LLM-DUMP] {dump_path}")
    except Exception as e:
        print(f"[LLM-DUMP] failed: {e}")
