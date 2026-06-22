"""论文版面分析服务 — Phase 8: 用视觉模型真正"看"论文结构

设计目标：
1. 把 PDF 每页用 pymupdf 渲染成 PNG
2. vision model 看整页（不仅是单图），输出 page layout JSON
3. layout 包含每个 block 的 type/order/text/position（视觉顺序）
4. paperAdapter 优先消费 layout 数据，不再依赖正则推断

输出 layout 结构（每页）：
{
  "page_number": 8,
  "blocks": [
    {"type": "heading", "level": 2, "order": 1, "text": "2.1 Test system"},
    {"type": "paragraph", "order": 2, "text": "..."},
    {"type": "image", "order": 3, "image_index": 0, "caption": "Fig. 1. ...", "position": "below_paragraph"},
    {"type": "paragraph", "order": 4, "text": "..."},
    {"type": "table", "order": 5, "caption": "Table 1.", "headers": [...], "rows": [[...]]},
    {"type": "formula", "order": 6, "latex": "..."}
  ]
}
"""

import asyncio
import base64
import io
import json
import logging
import re
from typing import Optional, List, Dict, Any

from app.config import settings
from app.core.llm import get_anthropic_client, get_default_model

logger = logging.getLogger("microbubble.paper_layout")


# ============================================================================
# Prompt: 让 vision 真正看懂一页论文，输出结构化 layout
# ============================================================================

PROMPT_PAGE_LAYOUT = """你是学术论文版面分析专家。请仔细"看"这页 PDF 渲染图，按视觉从上到下的顺序识别所有 block。

# 任务
逐个识别页面上的所有内容 block，按视觉顺序排列。每个 block 必须分类到以下 type 之一：

## Block 类型
1. **heading**：标题（章节标题）
   - 输出 `level`: 1=论文主标题 / 2=二级标题（"2.1 Materials"）/ 3=三级 / 4=四级
   - 输出 `text`: 完整标题文字
   - 例: `{"type":"heading","level":2,"text":"2.1 Test system"}`

2. **paragraph**：正文段落（一段连续文字）
   - 输出 `text`: 段落完整文字（保留标点、换行符 `\\n`）
   - 例: `{"type":"paragraph","text":"This study systematically..."}`

3. **image**：图片/插图/示意图
   - **重要**：一张完整的图（含子图 a/b/c/d）算**一个** image block，不要拆分子图
   - 如果一张图有多个子图，整体作为一个 image block 识别
   - 输出 `image_index`: 该图片在**整篇论文**中的全局序号（0, 1, 2...，从首页累积）
   - 输出 `caption`: 图下方/上方的图注文字（如 "Fig. 1. Water treatment..."）
   - 输出 `figure_no`: 图号（如 "Fig. 1" / "Fig. S2" / "Table 1" / "Scheme 1"，无则 null）
   - 输出 `position`: 图片相对于相邻 block 的位置（"between_paragraphs" / "below_paragraph" / "above_paragraph"）
   - 例: `{"type":"image","image_index":0,"caption":"Fig. 1. Water treatment system based on MNBs/UV technology.","figure_no":"Fig. 1","position":"below_paragraph"}`

4. **table**：表格
   - 输出 `caption`: 表标题（如 "Table 1. Description of..."，无则 null）
   - 输出 `headers`: 表头列名数组（如 ["Serial number", "Treatment condition", "Symbol"]）
   - 输出 `rows`: 数据行数组（每行一个字符串数组）
   - 例: `{"type":"table","caption":"Table 1.","headers":["Col1","Col2"],"rows":[["a","b"],["c","d"]]}`

5. **formula**：数学公式
   - 输出 `latex`: LaTeX 代码（不带 $ 包裹）
   - 例: `{"type":"formula","latex":"E = mc^2"}`

6. **reference_list**：参考文献列表
   - 输出 `text`: 完整参考文献内容（多条用 `\\n` 分隔，每条以 `[N]` 开头）
   - 例: `{"type":"reference_list","text":"[1] Smith J, ... 2024. ...\\n[2] Wang T, ..."}`
   - **重要**：参考文献必须用此类型，**不要**当作 paragraph 识别

7. **page_header / page_footer**：页眉/页脚（通常是页码或章节标题）
   - 输出 `text`: 页眉/页脚文字
   - 例: `{"type":"page_header","text":"Chemical Engineering Journal 25 (2026) 142456"}`

# 双列排版识别规则（重要！）

部分论文（如 Elsevier、Wiley 等期刊）使用**双列排版**（左右两栏）：
- **必须按视觉阅读顺序**：先读完**左列**所有内容（从上到下），再读**右列**所有内容（从上到下）
- 跨栏内容（如横向大图）按视觉位置独立识别
- 例：左列 heading "2.1 Methods" → 左列 paragraph → 右列 heading "2.2 Results" → 右列 paragraph

# 输出格式（严格 JSON，不要任何额外文字）

```json
{
  "page_number": 8,
  "blocks": [
    {"type":"heading","level":2,"order":1,"text":"2.1 Test system"},
    {"type":"paragraph","order":2,"text":"This study systematically evaluated..."},
    {"type":"image","order":3,"image_index":0,"caption":"Fig. 1. Water treatment system.","figure_no":"Fig. 1","position":"below_paragraph"},
    {"type":"paragraph","order":4,"text":"The MNBs generator utilized air..."},
    {"type":"table","order":5,"caption":"Table 1. Description of different treatment conditions.","headers":["Serial number","Treatment condition","Symbol"],"rows":[["1","Individual MNBs treatment","MNBs"]]},
    {"type":"reference_list","order":6,"text":"[1] Smith J, 2024. Title here.\\n[2] Wang T, ..."},
    {"type":"page_footer","order":7,"text":"Chemical Engineering Journal 25 (2026) 142456"}
  ]
}
```

# 严格要求
1. **顺序严格按视觉阅读顺序**：单列从上到下；双列先左列后右列
2. **保留完整文字**：不要省略段落，公式，caption，参考文献条目
3. **一张完整图 = 一个 image block**（不要拆分大图为多个子图）
4. **figure_no 必填**：从 caption 文本中提取 "Fig. N" / "Figure N" / "Table N" 等
5. **caption 必填**：图注文字，无图注则 null
6. **没识别到的字段填 null**，不要编造
7. **只输出 JSON**，不要任何解释或前缀
"""


# ============================================================================
# 服务实现
# ============================================================================

class PaperLayoutService:
    """论文版面分析服务 — 用 vision model 看完整 PDF 页面输出结构化 layout"""

    def __init__(self):
        self._client = None

    async def _get_client(self):
        if self._client is None:
            self._client = get_anthropic_client()
        return self._client

    async def _analyze_page_with_vision(
        self,
        page_png_bytes: bytes,
        page_number: int,
    ) -> dict:
        """vision model 看一页 PDF 渲染图，输出 page layout

        带 429 rate limit 重试（指数退避）：vision API rate limit 时等待更长时间再重试
        避免大批量重扫时一次性打爆 vision API。

        Returns:
            {"page_number": int, "blocks": [...]}
        """
        image_b64 = base64.standard_b64encode(page_png_bytes).decode("utf-8")

        client = await self._get_client()
        # 用最强 vision model
        model = getattr(settings, 'VISION_MODEL', None) or get_default_model()

        # 429 rate limit 重试（指数退避：5s → 15s → 30s → 60s，加长以应付 vision API 高峰）
        max_retries = 4
        wait_times = [5, 15, 30, 60]
        last_error = None

        for attempt in range(max_retries):
            try:
                response = await client.messages.create(
                    model=model,
                    max_tokens=16384,  # 双列论文一页可能很多 block + 长段落（v28 step 106 提升）
                    thinking={'type': 'disabled'},
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": PROMPT_PAGE_LAYOUT,
                            }
                        ]
                    }]
                )

                # 提取响应文本
                result_text = ""
                for block in response.content:
                    if hasattr(block, 'text'):
                        result_text += block.text
                    elif isinstance(block, dict) and 'text' in block:
                        result_text += block['text']

                # 解析 JSON（容忍 ```json ... ``` 包裹）
                parsed = self._parse_layout_response(result_text, page_number)
                return parsed
            except Exception as e:
                last_error = e
                error_str = str(e)
                is_rate_limit = '429' in error_str or 'rate' in error_str.lower() or 'Too Many' in error_str
                if is_rate_limit and attempt < max_retries - 1:
                    wait_sec = wait_times[attempt] if attempt < len(wait_times) else 20
                    logger.warning(
                        f"[vision_layout] page {page_number} 触发 429 rate limit, "
                        f"第 {attempt + 1}/{max_retries} 次重试, 等待 {wait_sec}s"
                    )
                    await asyncio.sleep(wait_sec)
                    continue
                # 非 429 错误或重试耗尽
                break

        # 所有重试都失败
        logger.error(f"vision analyze page {page_number} 失败: {last_error}", exc_info=True)
        return {"page_number": page_number, "blocks": [], "error": str(last_error) if last_error else "unknown"}

    def _parse_layout_response(self, text: str, page_number: int) -> dict:
        """解析 vision 返回的 JSON（容忍 markdown 包裹）"""
        if not text:
            return {"page_number": page_number, "blocks": []}

        # 尝试提取 ```json ... ``` 块
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            json_str = m.group(1)
        else:
            # 直接找 JSON 对象
            start = text.find('{')
            if start == -1:
                logger.warning(f"vision response 无 JSON: {text[:200]}")
                return {"page_number": page_number, "blocks": []}
            # 平衡括号
            depth = 0
            end = start
            for i in range(start, len(text)):
                if text[i] == '{':
                    depth += 1
                elif text[i] == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            json_str = text[start:end]

        try:
            data = json.loads(json_str)
        except Exception as e:
            logger.warning(f"vision JSON parse 失败 (page={page_number}): {e}, raw={text[:300]}")
            return {"page_number": page_number, "blocks": []}

        # 校验 + 补字段
        if "page_number" not in data:
            data["page_number"] = page_number
        if "blocks" not in data:
            data["blocks"] = []
        # 给每个 block 加 order（如果 vision 没填，按数组顺序填）
        for i, b in enumerate(data["blocks"]):
            if "order" not in b:
                b["order"] = i
        return data

    async def analyze_page_layout(
        self,
        pdf_bytes: bytes,
        page_number: int,
    ) -> dict:
        """PDF 第 N 页 → vision 看 → 输出 layout

        Args:
            pdf_bytes: PDF 文件二进制
            page_number: 1-indexed 页码

        Returns:
            {"page_number": int, "blocks": [...], "error": Optional[str]}
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("PyMuPDF 未安装")
            return {"page_number": page_number, "blocks": [], "error": "pymupdf_not_installed"}

        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            if page_number < 1 or page_number > len(doc):
                doc.close()
                return {"page_number": page_number, "blocks": [], "error": "page_out_of_range"}
            page = doc[page_number - 1]
            # 渲染为 PNG（150 DPI 平衡质量与 token）
            mat = fitz.Matrix(150 / 72, 150 / 72)
            pix = page.get_pixmap(matrix=mat)
            png_bytes = pix.tobytes("png")
            doc.close()

            return await self._analyze_page_with_vision(png_bytes, page_number)
        except Exception as e:
            logger.error(f"PDF 渲染 page={page_number} 失败: {e}", exc_info=True)
            return {"page_number": page_number, "blocks": [], "error": str(e)}

    async def scan_paper_layout(
        self,
        pdf_bytes: bytes,
        total_pages: Optional[int] = None,
        max_pages: Optional[int] = None,
        concurrency: int = 1,  # v28 step 106.1: 降低并发避免触发 vision API 429 rate limit
    ) -> List[dict]:
        """扫描整篇论文，每页输出 layout

        Args:
            pdf_bytes: PDF 二进制
            total_pages: 总页数（不传则从 PDF 读）
            max_pages: 最多扫描多少页（None=全扫）
            concurrency: 并发数

        Returns:
            [{"page_number": 1, "blocks": [...]}, ...]
        """
        try:
            import fitz
        except ImportError:
            logger.error("PyMuPDF 未安装")
            return []

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if total_pages is None:
            total_pages = len(doc)
        doc.close()

        if max_pages:
            total_pages = min(total_pages, max_pages)

        logger.info(f"[scan_layout] 开始扫描 {total_pages} 页")

        sem = asyncio.Semaphore(concurrency)

        async def _scan_one(page_num):
            async with sem:
                return await self.analyze_page_layout(pdf_bytes, page_num)

        tasks = [_scan_one(p) for p in range(1, total_pages + 1)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常
        clean_results = []
        for i, r in enumerate(results):
            page_num = i + 1
            if isinstance(r, Exception):
                logger.warning(f"page {page_num} scan failed: {r}")
                clean_results.append({"page_number": page_num, "blocks": [], "error": str(r)})
            else:
                clean_results.append(r)

        # 按 page_number 排序（None 排最后）
        def _sort_key(x):
            pn = x.get("page_number") if isinstance(x, dict) else None
            if pn is None:
                return (1, 0)  # None 排后面
            return (0, pn)
        clean_results.sort(key=_sort_key)
        return clean_results


# 全局单例
paper_layout_service = PaperLayoutService()


# ============================================================================
# Celery task: 异步扫描单篇论文
# ============================================================================

# 注意：celery_app 在 app.core.celery 中定义，需要延迟 import 避免循环依赖
# 走与 content_formatter_service 相同的模式

def _make_celery_task():
    """延迟创建 Celery task 函数（避免 import 时循环依赖）"""
    from app.core.celery import celery_app

    @celery_app.task(name="app.services.paper_layout_service.scan_paper_layout_task", bind=True, max_retries=2)
    def scan_paper_layout_task(self, knowledge_id: int):
        """Celery 异步扫描单篇论文的 layout

        流程：
        1. 从 MinIO 下载 PDF bytes
        2. 用 paper_layout_service.scan_paper_layout 扫描所有页
        3. 写回 knowledge_layout 表
        """
        import asyncio
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from sqlalchemy.pool import NullPool
        from sqlalchemy import select
        from app.config import settings
        from app.models.knowledge import Knowledge
        from app.services.file_service import file_service
        from app.models.knowledge_layout import KnowledgeLayout

        async def _run():
            engine = create_async_engine(
                settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
                poolclass=NullPool,
            )
            local_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            try:
                async with local_session_factory() as db:
                    try:
                        result = await db.execute(select(Knowledge).where(Knowledge.id == knowledge_id))
                        knowledge = result.scalar_one_or_none()
                        if not knowledge:
                            logger.error(f"[scan_layout] knowledge_id={knowledge_id} 不存在")
                            return {"status": "error", "reason": "knowledge_not_found"}

                        if not knowledge.file_path:
                            logger.warning(f"[scan_layout] knowledge_id={knowledge_id} 无 file_path")
                            return {"status": "skipped", "reason": "no_file"}

                        # 检查文件类型 — 只支持 PDF，其他类型走 LLM reformat
                        file_type = (knowledge.file_type or '').lower()
                        if 'pdf' not in file_type and knowledge.file_path:
                            # 不是 PDF（docx/pptx/txt 等）— 不能用 vision scan_layout
                            # 标记跳过，让前端走 LLM reformat 路径
                            logger.info(f"[scan_layout] knowledge_id={knowledge_id} 非 PDF（{file_type}），跳过 vision 扫描")
                            return {"status": "skipped", "reason": "not_pdf"}

                        # 下载 PDF
                        pdf_bytes = await file_service.download_file(knowledge.file_path)
                        if not pdf_bytes:
                            logger.error(f"[scan_layout] knowledge_id={knowledge_id} PDF 下载失败: {knowledge.file_path}")
                            return {"status": "error", "reason": "download_failed"}

                        # 扫描 layout
                        try:
                            page_layouts = await paper_layout_service.scan_paper_layout(pdf_bytes)
                        except Exception as scan_err:
                            logger.error(f"[scan_layout] knowledge_id={knowledge_id} scan_paper_layout 异常: {scan_err}", exc_info=True)
                            return {"status": "error", "reason": f"scan_exception: {scan_err}"}

                        if not page_layouts:
                            logger.warning(f"[scan_layout] knowledge_id={knowledge_id} 扫描结果空")
                            return {"status": "error", "reason": "scan_empty"}

                        total_blocks = sum(len(p.get("blocks", [])) for p in page_layouts)
                        total_images = sum(
                            sum(1 for b in p.get("blocks", []) if b.get("type") == "image")
                            for p in page_layouts
                        )
                        logger.info(
                            f"[scan_layout] knowledge_id={knowledge_id} 扫描完成: "
                            f"{len(page_layouts)} 页, {total_blocks} blocks, {total_images} images"
                        )

                        # upsert knowledge_layout
                        existing = await db.execute(
                            select(KnowledgeLayout).where(KnowledgeLayout.knowledge_id == knowledge_id)
                        )
                        layout_row = existing.scalar_one_or_none()
                        if layout_row:
                            layout_row.page_layout = page_layouts
                            layout_row.total_pages = len(page_layouts)
                            layout_row.total_blocks = total_blocks
                            layout_row.vision_model_used = settings.VISION_MODEL
                        else:
                            layout_row = KnowledgeLayout(
                                knowledge_id=knowledge_id,
                                page_layout=page_layouts,
                                total_pages=len(page_layouts),
                                total_blocks=total_blocks,
                                vision_model_used=settings.VISION_MODEL,
                            )
                            db.add(layout_row)
                        # v28 step 108: 同步更新 knowledge.analysis_status = 'completed'
                        #   之前 vision scan 不更新状态，前端一直轮询显示"分析中"
                        if knowledge.analysis_status == 'analyzing':
                            knowledge.analysis_status = 'completed'
                        await db.commit()
                        return {
                            "status": "ok",
                            "knowledge_id": knowledge_id,
                            "total_pages": len(page_layouts),
                            "total_blocks": total_blocks,
                            "total_images": total_images,
                        }
                    except Exception as e:
                        logger.error(f"[scan_layout] knowledge_id={knowledge_id} 失败: {e}", exc_info=True)
                        raise
            finally:
                await engine.dispose()

        try:
            return asyncio.run(_run())
        except Exception as e:
            logger.error(f"[scan_layout] 任务失败 knowledge_id={knowledge_id}: {e}", exc_info=True)
            raise self.retry(exc=e, countdown=60)

    return scan_paper_layout_task


# 模块加载时立即注册 Celery task
scan_paper_layout_task = _make_celery_task()