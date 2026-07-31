"""app/rag/multimodal_parser.py — 跨模态文档解析增强

LlamaIndex Readers:
- PDFReader: PDF layout 分析 + 表格结构化提取 + 图表描述提取
- ImageReader: 图片描述提取
- UnstructuredReader: 混合文档 (PDF/DOCX/PPTX) 解析

与 file_parser_service.py (fitz 抽文字) + multimodal_extraction_service.py (OCR) 并列,
提供第三条解析通道: 框架 Reader 结构化解析。

使用:
    from app.rag.multimodal_parser import parse_document_enhanced
    result = await parse_document_enhanced(file_path, file_type)
    # {"text": str, "tables": [...], "images": [...], "metadata": {...}}
"""

import asyncio
import logging
import mimetypes
import re
from pathlib import Path
from typing import Dict, List

from app.rag.config import MULTIMODAL_PARSER_ENABLED

logger = logging.getLogger("microbubble.rag.multimodal_parser")

# "Fig. N" / "Figure N" 图表引用模式 (与 file_parser_service 的锚点搜索对齐)
_FIG_RE = re.compile(r"\b(?:Fig\.?|Figure)\s+(\d+[a-z]?)\b", re.IGNORECASE)
# "Table N" / "表格 N" 表格引用模式
_TABLE_RE = re.compile(r"\b(?:Table|表格)\s+(\d+[a-z]?)\b", re.IGNORECASE)


async def parse_document_enhanced(
    file_path: str,
    file_type: str = "pdf",
) -> Dict:
    """LlamaIndex Reader 跨模态解析

    Args:
        file_path: 文件路径
        file_type: pdf / docx / pptx / image

    Returns:
        {
            "text": str,          # 纯文本
            "tables": List[Dict], # 结构化表格
            "images": List[Dict], # 图片描述
            "metadata": Dict,     # 解析元数据
        }

    MULTIMODAL_PARSER_ENABLED=False 或框架未装时回退到现有手写解析。
    """
    if not MULTIMODAL_PARSER_ENABLED:
        return await _fallback_parse(file_path, file_type)
    try:
        if file_type == "pdf":
            return await _parse_pdf_llamaindex(file_path)
        elif file_type in ("docx", "pptx"):
            return await _parse_unstructured(file_path, file_type)
        elif file_type in ("png", "jpg", "jpeg"):
            return await _parse_image(file_path)
        return await _fallback_parse(file_path, file_type)
    except ImportError as e:
        logger.warning(f"llama-index-readers-file 未安装, 回退手写解析: {e}")
        return await _fallback_parse(file_path, file_type)
    except Exception as e:
        logger.error(f"LlamaIndex 解析失败, 回退手写解析: {e}", exc_info=True)
        return await _fallback_parse(file_path, file_type)


async def _parse_pdf_llamaindex(file_path: str) -> Dict:
    """LlamaIndex PDFReader 解析 — layout + 表格 + 图表

    PDFReader 返回按 layout 分块的 Document 列表 (metadata 含 page 信息)。
    表格/图表通过正文引用标记 ("Table N" / "Fig. N") 做结构化提取。
    """
    from llama_index.readers.file import PDFReader

    reader = PDFReader()
    # Reader 是同步 API 且 PDF 解析可能较慢, 放到线程池避免阻塞事件循环
    docs = await asyncio.to_thread(reader.load_data, file_path)

    pages: List[str] = []
    raw_text = ""
    meta_pages: List[int] = []
    for doc in docs:
        text = getattr(doc, "text", "") or ""
        pages.append(text)
        raw_text += text + "\n"
        md = getattr(doc, "metadata", {}) or {}
        if "page" in md:
            meta_pages.append(int(md["page"]))

    tables = _extract_tables_from_text(raw_text)
    images = _extract_figures_from_text(raw_text)

    metadata = {
        "parser": "llamaindex_pdf_reader",
        "source": str(Path(file_path).name),
        "page_count": max(meta_pages) if meta_pages else len(docs),
        "pages": pages,
    }
    return {
        "text": raw_text.strip(),
        "tables": tables,
        "images": images,
        "metadata": metadata,
    }


async def _parse_unstructured(file_path: str, file_type: str) -> Dict:
    """UnstructuredReader 解析 DOCX/PPTX

    Unstructured 提供混合文档 (PDF/DOCX/PPTX) 解析, 输出带 page_number
    与 filetype 元数据的 Document 列表。
    """
    from llama_index.readers.file import UnstructuredReader

    reader = UnstructuredReader()
    docs = await asyncio.to_thread(reader.load_data, file_path)

    raw_text = ""
    meta_pages: List[int] = []
    for doc in docs:
        text = getattr(doc, "text", "") or ""
        raw_text += text + "\n"
        md = getattr(doc, "metadata", {}) or {}
        if "page_number" in md:
            try:
                meta_pages.append(int(md["page_number"]))
            except (TypeError, ValueError):
                pass

    metadata = {
        "parser": "llamaindex_unstructured_reader",
        "source": str(Path(file_path).name),
        "file_type": file_type,
        "page_count": max(meta_pages) if meta_pages else len(docs),
    }
    return {
        "text": raw_text.strip(),
        "tables": _extract_tables_from_text(raw_text),
        "images": _extract_figures_from_text(raw_text),
        "metadata": metadata,
    }


async def _parse_image(file_path: str) -> Dict:
    """ImageReader 图片描述提取

    未配置 OCR text_extractor 时 ImageNode 的 text 为空, 描述取自
    metadata (image_path / image_size)。OCR 描述需要外部 text_extractor,
    由调用方通过 kwargs 注入 (本模块不做硬依赖)。
    """
    from llama_index.readers.file import ImageReader

    reader = ImageReader()
    docs = await asyncio.to_thread(reader.load_data, file_path)

    descriptions: List[Dict] = []
    for doc in docs:
        md = getattr(doc, "metadata", {}) or {}
        descriptions.append(
            {
                "path": str(md.get("image_path", file_path)),
                "size": md.get("image_size"),
                "text": (getattr(doc, "text", "") or "").strip(),
            }
        )

    metadata = {
        "parser": "llamaindex_image_reader",
        "source": str(Path(file_path).name),
        "image_count": len(descriptions),
    }
    return {
        "text": "\n".join(d["text"] for d in descriptions if d["text"]),
        "tables": [],
        "images": descriptions,
        "metadata": metadata,
    }


def _extract_tables_from_text(text: str) -> List[Dict]:
    """从正文中结构化提取表格 — 按 "Table N." 引用 + 跟随块

    LlamaIndex PDFReader 不直接输出表格对象, 这里用引用标记做轻量
    结构化提取: 每个 "Table N" 引用记录所在行 + 其后非空行块作为 raw。
    """
    tables: List[Dict] = []
    seen = set()
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = _TABLE_RE.search(line)
        if not m:
            continue
        table_id = m.group(1).lower()
        if table_id in seen:
            continue
        seen.add(table_id)
        # 引用行 + 至多 8 行跟随内容作为表格块
        block_lines = [line.strip()] if line.strip() else []
        for follow in lines[i + 1 : i + 9]:
            if not follow.strip():
                break
            block_lines.append(follow.strip())
        tables.append(
            {
                "table_id": table_id,
                "caption": line.strip(),
                "raw_lines": block_lines,
                "line": i + 1,
            }
        )
    return tables


def _extract_figures_from_text(text: str) -> List[Dict]:
    """从正文中结构化提取图表描述 — 按 "Fig. N" 引用

    与 file_parser_service 的 Fig. N 锚点对齐, 记录 figure_id + 引用行。
    """
    images: List[Dict] = []
    seen = set()
    for i, line in enumerate(text.splitlines()):
        m = _FIG_RE.search(line)
        if not m:
            continue
        fig_id = m.group(1).lower()
        if fig_id in seen:
            continue
        seen.add(fig_id)
        images.append(
            {
                "figure_id": fig_id,
                "caption": line.strip(),
                "line": i + 1,
            }
        )
    return images


async def _fallback_parse(file_path: str, file_type: str) -> Dict:
    """回退: 现有 file_parser_service 手写解析 (async API)"""
    from app.services.file_parser_service import FileParserService

    svc = FileParserService()
    mime, _ = mimetypes.guess_type(file_path)
    content_type = mime or f"application/{file_type}"
    with open(file_path, "rb") as f:
        result = await svc.extract_content(f.read(), Path(file_path).name, content_type)
    return {
        "text": result.get("text", ""),
        "tables": [],
        "images": result.get("images", {}),
        "metadata": {"fallback": True},
    }
