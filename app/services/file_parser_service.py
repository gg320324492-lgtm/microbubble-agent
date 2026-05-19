"""文件内容提取服务 — 支持 PDF/Word/Excel/TXT/Markdown"""

import asyncio
import io
import logging
from typing import Dict

logger = logging.getLogger("microbubble.file_parser")


class FileParserService:
    """从各类文件中提取文本内容"""

    SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.xlsx', '.xls', '.txt', '.md'}

    async def extract_text(self, file_data: bytes, filename: str, content_type: str) -> str:
        """提取文件文本，路由到对应解析器"""
        ext = ''
        if '.' in filename:
            ext = '.' + filename.rsplit('.', 1)[-1].lower()

        if ext == '.pdf' or 'pdf' in content_type:
            return await self._parse_pdf(file_data)
        elif ext in ('.docx',) or 'wordprocessingml' in content_type:
            return await self._parse_docx(file_data)
        elif ext in ('.xlsx',) or 'spreadsheetml' in content_type:
            return await self._parse_xlsx(file_data)
        elif ext in ('.txt', '.md') or content_type.startswith('text/'):
            return file_data.decode('utf-8', errors='replace')
        else:
            raise ValueError(f"不支持的文件类型: {ext}")

    async def _parse_pdf(self, data: bytes) -> str:
        """解析 PDF 文件"""
        def _extract():
            import pdfplumber
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                pages = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
                return '\n'.join(pages)
        return await asyncio.to_thread(_extract)

    async def _parse_docx(self, data: bytes) -> str:
        """解析 Word 文档"""
        def _extract():
            from docx import Document
            doc = Document(io.BytesIO(data))
            return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())
        return await asyncio.to_thread(_extract)

    async def _parse_xlsx(self, data: bytes) -> str:
        """解析 Excel 文件"""
        def _extract():
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(data), read_only=True)
            texts = []
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    row_text = ' '.join(str(c) for c in row if c is not None)
                    if row_text.strip():
                        texts.append(row_text)
            return '\n'.join(texts)
        return await asyncio.to_thread(_extract)


file_parser_service = FileParserService()
