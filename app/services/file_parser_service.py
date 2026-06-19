"""文件内容提取服务 — 支持 PDF/Word/Excel/PPT/TXT/Markdown"""

import asyncio
import io
import logging

logger = logging.getLogger("microbubble.file_parser")


class FileParserService:
    """从各类文件中提取文本和图片"""

    SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.pptx', '.txt', '.md'}

    async def extract_content(self, file_data: bytes, filename: str, content_type: str) -> dict:
        """提取文件文本+图片，返回 {text, images: {placeholder: bytes}}"""
        ext = ''
        if '.' in filename:
            ext = '.' + filename.rsplit('.', 1)[-1].lower()

        if ext == '.pdf' or 'pdf' in content_type:
            return await self._parse_pdf(file_data)
        elif ext in ('.docx',) or 'wordprocessingml' in content_type:
            return {"text": await self._parse_docx(file_data), "images": {}}
        elif ext in ('.xlsx',) or 'spreadsheetml' in content_type:
            return {"text": await self._parse_xlsx(file_data), "images": {}}
        elif ext in ('.pptx',) or 'presentationml' in content_type:
            return {"text": await self._parse_pptx(file_data), "images": {}}
        elif ext in ('.txt', '.md') or content_type.startswith('text/'):
            return {"text": file_data.decode('utf-8', errors='replace'), "images": {}}
        else:
            raise ValueError(f"不支持的文件类型: {ext}")

    async def _parse_pdf(self, data: bytes) -> dict:
        """解析 PDF — 用 PyMuPDF 提取文本和嵌入图片

        2026-06-19 Phase 7 v2: 在页间插入 [PAGE:N] 标记，便于多模态 inline
        按页码精确定位插入点（LLM 启发式对页内 anchor 太保守）
        """
        def _extract():
            import fitz  # PyMuPDF

            doc = fitz.open(stream=data, filetype="pdf")
            if doc.needs_pass:
                doc.close()
                raise ValueError("PDF 已加密，无法解析")

            pages_text = []
            images = {}  # placeholder -> image_bytes
            fig_idx = 0

            for page_num in range(len(doc)):
                page = doc[page_num]

                # 2026-06-19 Phase 7: 页间插入 [PAGE:N] 标记
                # multimodal_extraction_service.inline_extractions_to_content 用此
                # 把图片按 page_number 精确插到对应页的开头
                pages_text.append(f"[PAGE:{page_num + 1}]")

                # 提取文本
                text = page.get_text()
                if text:
                    pages_text.append(text)

                # 提取嵌入图片
                img_list = page.get_images(full=True)
                for img_info in img_list:
                    xref = img_info[0]
                    try:
                        base_image = doc.extract_image(xref)
                        img_bytes = base_image["image"]
                        ext_lower = base_image["ext"].lower()
                        # 跳过极小图片（< 2KB，通常是图标或装饰元素）
                        if len(img_bytes) < 2048:
                            continue
                        fig_idx += 1
                        placeholder = f"\n[FIGURE:{fig_idx}]\n"
                        images[placeholder] = {
                            "bytes": img_bytes,
                            "ext": ext_lower if ext_lower in ("png", "jpeg", "jpg") else "png",
                            "page": page_num + 1,
                        }
                        # 在文本中插入占位符
                        pages_text.append(placeholder)
                    except Exception as e:
                        logger.warning(f"PDF 图片提取失败(page={page_num}, xref={xref}): {e}")

            doc.close()

            text = '\n'.join(pages_text).strip()
            if not text:
                raise ValueError("PDF 为扫描件或图片型文档，无文字层")
            return {"text": text, "images": images}
        try:
            return await asyncio.to_thread(_extract)
        except ValueError:
            raise
        except Exception as e:
            logger.exception("PDF 解析失败")
            raise ValueError(f"PDF 解析失败: {str(e)}")

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

    async def _parse_pptx(self, data: bytes) -> str:
        """解析 PPT 文件

        2026-06-19 Phase 7 v2: 每页前插入 [PAGE:N] 标记，便于多模态 inline 按页定位
        """
        def _extract():
            from pptx import Presentation
            prs = Presentation(io.BytesIO(data))
            texts = []
            for slide_num, slide in enumerate(prs.slides, 1):
                # 2026-06-19 Phase 7: 每页前加 [PAGE:N] 标记
                texts.append(f"[PAGE:{slide_num}]")
                slide_texts = []
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        for para in shape.text_frame.paragraphs:
                            text = para.text.strip()
                            if text:
                                slide_texts.append(text)
                    if shape.has_table:
                        for row in shape.table.rows:
                            row_text = ' '.join(cell.text.strip() for cell in row.cells if cell.text.strip())
                            if row_text:
                                slide_texts.append(row_text)
                if slide_texts:
                    texts.append(f"--- 第{slide_num}页 ---")
                    texts.extend(slide_texts)
            return '\n'.join(texts)
        return await asyncio.to_thread(_extract)


file_parser_service = FileParserService()
