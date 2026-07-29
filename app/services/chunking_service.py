"""Chunking 策略实现 — PR2 (W88 +10..+12)

3 策略可选 (RAG v1.1 §11.2 chunking_service):
- paragraph: 按 \\n\\n 切, 默认
- heading: 按 Markdown #/##/### 切 (保留 heading 作为 chunk 起始)
- window: 固定字符窗口 + overlap

设计原则:
- 不依赖外部库, 纯 Python 标准库 (re + str)
- 入参: text (str) + config (ChunkConfig), 出参: List[Chunk]
- 每个 Chunk: {content, char_start, char_end, char_count, strategy, chunk_metadata}
- 边界安全: char_start >= 0, char_end > char_start, char_count == char_end - char_start

复用 PR1 truncation:
- 如果 chunking 后任何 chunk 超 MAX_EMBED_INPUT_CHARS (6000), 自动 fallback window 策略

W88 +10: paragraph 策略
W88 +11: window 策略
W88 +12: heading 策略 + 路由入口
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional


# PR1 MAX_EMBED_INPUT_CHARS = 6000 (复用 truncation policy, 见 PR1 §3.0/§11.2)
MAX_EMBED_INPUT_CHARS = 6000

# Window 策略默认参数
DEFAULT_WINDOW_SIZE = 800
DEFAULT_WINDOW_OVERLAP = 100


@dataclass
class Chunk:
    """单个 chunk 切片 (PR2 §11.2 chunking_service output)

    字段对齐 alembic 088 knowledge_chunks 表:
    - content ↔ content (Text)
    - char_start/char_end ↔ 列
    - char_count ↔ 列 (派生 = end - start)
    - strategy ↔ 列
    - chunk_metadata ↔ JSONB 列
    """
    content: str
    char_start: int
    char_end: int
    char_count: int
    strategy: str
    chunk_metadata: dict = field(default_factory=dict)


@dataclass
class ChunkConfig:
    """chunking 配置"""
    strategy: str = "paragraph"  # paragraph | heading | window
    window_size: int = DEFAULT_WINDOW_SIZE
    window_overlap: int = DEFAULT_WINDOW_OVERLAP
    max_chars: int = MAX_EMBED_INPUT_CHARS  # 超此 fallback window


def chunk_text(text: str, config: Optional[ChunkConfig] = None) -> List[Chunk]:
    """策略路由入口 (PR2 §11.2 chunking_service)

    Args:
        text: parent content
        config: 配置 (None = 默认 paragraph)

    Returns:
        List[Chunk] — 每条 char_start/char_end 严格指回 text 偏移
    """
    if not text:
        return []
    if config is None:
        config = ChunkConfig()

    if config.strategy == "paragraph":
        chunks = _chunk_paragraph(text)
    elif config.strategy == "heading":
        chunks = _chunk_heading(text)
    elif config.strategy == "window":
        chunks = _chunk_window(text, config)
    else:
        raise ValueError(f"Unknown chunk strategy: {config.strategy}")

    # 长度安全: 任何 chunk 超 max_chars → fallback window 切片 (PR1 truncation 复用)
    if config.max_chars > 0:
        sanitized: List[Chunk] = []
        for c in chunks:
            if c.char_count > config.max_chars:
                # 单 chunk 过长, 用 window 二次切
                sub_chunks = _chunk_window(c.content, ChunkConfig(strategy="window"))
                for s in sub_chunks:
                    # 重新计算偏移 (相对 text)
                    new_start = c.char_start + s.char_start
                    new_end = c.char_start + s.char_end
                    s.chunk_metadata.setdefault("parent_strategy", c.strategy)
                    s.chunk_metadata.setdefault("split_reason", "max_chars_exceeded")
                    sanitized.append(Chunk(
                        content=s.content,
                        char_start=new_start,
                        char_end=new_end,
                        char_count=new_end - new_start,
                        strategy="window",  # fallback 后用 window 标注
                        chunk_metadata=s.chunk_metadata,
                    ))
            else:
                sanitized.append(c)
        chunks = sanitized

    return chunks


def _chunk_paragraph(text: str) -> List[Chunk]:
    """按 \\n\\n 切段落 (PR2 §11.2 paragraph 策略)

    - 切点: \\n\\n (连续 2 换行, 中间允许空白)
    - 不切: \\n 单换行 (软换行)
    - 严格保证: char_count == char_end - char_start (派生一致)
    """
    chunks: List[Chunk] = []
    # split 保留分隔符信息
    # 用 lookahead 找 \\n\\n 切点
    boundaries = [0]
    for m in re.finditer(r"\n\s*\n", text):
        # chunk 结束在分隔符起始处 (不要包含分隔符)
        boundaries.append(m.start())
    boundaries.append(len(text))

    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1]
        if start == end:
            continue
        content = text[start:end]
        if not content.strip():
            continue
        chunks.append(Chunk(
            content=content,
            char_start=start,
            char_end=end,
            char_count=end - start,
            strategy="paragraph",
            chunk_metadata={"section_title": None},
        ))

    return chunks


def _chunk_heading(text: str) -> List[Chunk]:
    """按 Markdown heading 切 (#/##/###) (PR2 §11.2 heading 策略)

    - 切点: 行首 ^#{1,3} + 空格 + 标题
    - 每个 chunk 包含 heading 起始行
    - chunk_metadata.section_title = 该 heading 文本
    """
    heading_pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
    headings = list(heading_pattern.finditer(text))
    if not headings:
        # 无 heading fallback paragraph
        return _chunk_paragraph(text)

    chunks: List[Chunk] = []
    for i, h in enumerate(headings):
        start = h.start()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        content = text[start:end]
        if not content.strip():
            continue
        chunks.append(Chunk(
            content=content,
            char_start=start,
            char_end=end,
            char_count=end - start,
            strategy="heading",
            chunk_metadata={"section_title": h.group(2).strip()},
        ))
    return chunks


def _chunk_window(text: str, config: ChunkConfig) -> List[Chunk]:
    """固定窗口 + overlap (PR2 §11.2 window 策略)

    - window_size: 每 chunk 字符数 (默认 800)
    - overlap: 相邻 chunk 重叠字符数 (默认 100)
    - 保证 char_count == window_size (最后一块可能较短)
    """
    step = config.window_size - config.window_overlap
    if step <= 0:
        raise ValueError("window_overlap must be < window_size")

    chunks: List[Chunk] = []
    pos = 0
    while pos < len(text):
        end = min(pos + config.window_size, len(text))
        chunks.append(Chunk(
            content=text[pos:end],
            char_start=pos,
            char_end=end,
            char_count=end - pos,
            strategy="window",
            chunk_metadata={"window_size": config.window_size, "overlap": config.window_overlap},
        ))
        if end >= len(text):
            break
        pos += step

    return chunks