"""OCR 服务抽象层 — Phase 7: 知识库多模态入库

设计目标：
1. 统一接口：业务层只调 ocr_service.extract_*()，不关心后端
2. 主后端：LLM-Vision（复用 vision_service.analyze_image()），零本地依赖
3. 备后端：Tesseract（pytesseract + 系统 tesseract 二进制），按 settings 开关启用
4. Prompt 体系：按"提取目标"分（text/formula/table/chart/figure_caption）

调用模式（业务层）：
    text = await ocr_service.extract_text(image_bytes, mime="image/png")
    latex = await ocr_service.extract_formula(image_bytes, mime="image/png")
    table = await ocr_service.extract_table(image_bytes, mime="image/png")
    info = await ocr_service.classify_and_extract(image_bytes, mime="image/png")

注意：
- LLM-Vision 走的是 settings.VISION_MODEL（默认 mimo-v2.5），与微信截图共用客户端
- 单次调用 2-5s，多图必须并发（asyncio.Semaphore 控制）
- 失败回退：LLM 抛错 → 重试 1 次 → 仍失败抛 OCRBackendError 由调用方决定
"""

import asyncio
import base64
import io
import logging
import re
from typing import Optional, Protocol

from app.config import settings

logger = logging.getLogger("microbubble.ocr")


# ============================================================================
# 异常
# ============================================================================


class OCRBackendError(Exception):
    """OCR 后端调用失败（网络/解析/超时）"""


class OCRUnsupportedError(Exception):
    """请求的 OCR 类型不被支持（如选了 tesseract 但没装）"""


# ============================================================================
# Prompt 模板（按提取目标分）
# ============================================================================

PROMPT_GENERAL_OCR = """你是 OCR 助手。请精确识别图片中的所有文字内容，按原文顺序输出。

要求：
1. 保留原始段落结构（空行分隔）
2. 数学符号用 Unicode（α/β/γ/π/Σ/∫/≈/≤/≥ 等）保留
3. 表格区域输出"（表格：<简要描述>）"，不强行解析
4. 公式区域输出"（公式：<LaTeX 形式>）"
5. 只输出识别出的文字，不要任何解释或前缀

图片内容如下："""

PROMPT_FORMULA = """你是公式识别专家。请把图片中的数学公式识别为 LaTeX 格式。

要求：
1. 只输出 LaTeX 代码本身（不要 $...$ 包裹），多行公式用 \\begin{{equation}}...\\end{{equation}} 或 align*
2. 中文符号保留（μmol/L 等）
3. 希腊字母用 \\alpha \\beta 等 LaTeX 命令
4. 上下标用 ^ _ 正确表达
5. 分数用 \\frac{{a}}{{b}}
6. 如果图中有多个公式，每个公式用空行分隔
7. 复杂公式可加简要说明（"// 注释"），但 LaTeX 必须完整
8. 没有任何公式时输出"NO_FORMULA"

请只输出 LaTeX 代码："""

PROMPT_TABLE = """你是表格识别专家。请把图片中的表格识别为 Markdown 表格格式。

要求：
1. 第一行是表头（用 | 分隔列）
2. 第二行是分隔行（|---|---|---|）
3. 后续每行是一个数据行
4. 单元格内容如果包含换行，用 <br> 替代
5. 合并单元格：横向合并在内容里重复值；纵向合并用 † 标记后说明
6. 复杂表格可加 caption（前一行用 "**表标题：xxx**"）
7. 如果图片不是表格（是图、公式等），输出"NO_TABLE"
8. 表格前如有标题/编号（如"表 3-1"），输出为 "**{标题}**" 单独一行

请只输出 Markdown 表格："""

PROMPT_CHART = """你是图表识别专家。请描述图片中的图表内容。

要求：
1. 图表类型（柱状图/折线图/饼图/散点图/流程图/示意图 等）
2. 标题/坐标轴标签
3. 关键数据点（如果有数字标签）
4. 趋势/对比/结论
5. 控制在 200 字以内

请输出图表描述："""

PROMPT_FIGURE_CAPTION = """你是图注识别助手。请识别图片下方的图注/说明文字。

要求：
1. 图注通常以"图 N"、"Figure N"、"Fig. N" 开头
2. 保留完整文字，包括公式编号
3. 如果图片没有图注，输出"NO_CAPTION"

请只输出图注文字："""


# ============================================================================
# 后端协议
# ============================================================================


class OCRBackend(Protocol):
    """OCR 后端必须实现的接口"""
    name: str

    async def analyze(
        self,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
        timeout: int,
    ) -> str:
        """分析图片并返回文本（OCR 文字 / LaTeX / Markdown table / 描述）"""
        ...


# ============================================================================
# 主后端：LLM-Vision
# ============================================================================


class LLMVisionBackend:
    """LLM-Vision 后端（复用 vision_service.analyze_image）

    优势：零本地依赖、识别中文 + 公式 + 表格都好、可与 vision-mcp 复用
    劣势：单次 2-5s、API 成本、按 token 收费
    """

    name = "llm_vision"

    def __init__(self):
        from app.services.vision_service import vision_service
        self._vision = vision_service

    async def analyze(
        self,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
        timeout: int,
    ) -> str:
        # 直接复用 vision_service.analyze_image
        # 它会处理 MCP vs 直连 + base64 编码 + 媒体类型检测
        try:
            result = await asyncio.wait_for(
                self._vision.analyze_image(image_bytes, prompt),
                timeout=timeout,
            )
            return (result or "").strip()
        except asyncio.TimeoutError:
            raise OCRBackendError(f"LLM-Vision OCR 超时（{timeout}s）")
        except Exception as e:
            raise OCRBackendError(f"LLM-Vision OCR 失败: {e}")


# ============================================================================
# 备后端：Tesseract（可选，需 apt-get install tesseract-ocr tesseract-ocr-chi-sim）
# ============================================================================


class TesseractBackend:
    """Tesseract 本地 OCR 后端（仅支持 text 提取，不擅长公式/表格）"""

    name = "tesseract"

    def __init__(self):
        self._available = self._check_available()

    def _check_available(self) -> bool:
        try:
            import pytesseract  # noqa: F401
            from PIL import Image  # noqa: F401
            # 检查 tesseract 二进制
            pytesseract.get_tesseract_version()
            return True
        except Exception as e:
            logger.warning(f"Tesseract 后端不可用: {e}")
            return False

    async def analyze(
        self,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
        timeout: int,
    ) -> str:
        if not self._available:
            raise OCRUnsupportedError("Tesseract 未安装或不可用（需 pytesseract + 系统 tesseract 二进制）")
        if "formula" in prompt.lower() or "table" in prompt.lower() or "chart" in prompt.lower():
            raise OCRUnsupportedError("Tesseract 后端仅支持通用 OCR（text），不支持公式/表格/图表识别")

        def _sync_ocr():
            import pytesseract
            from PIL import Image
            img = Image.open(io.BytesIO(image_bytes))
            # 中文 + 英文（需要 tesseract-ocr-chi-sim）
            return pytesseract.image_to_string(img, lang="chi_sim+eng", timeout=timeout)

        try:
            text = await asyncio.to_thread(_sync_ocr)
            return text.strip()
        except Exception as e:
            raise OCRBackendError(f"Tesseract OCR 失败: {e}")


# ============================================================================
# 路由
# ============================================================================


class OCRService:
    """OCR 服务统一入口

    按 settings.MULTIMODAL_OCR_BACKEND 选择后端，
    自动注入 prompt 模板 + 超时 + 重试逻辑。
    """

    def __init__(self):
        self._backend: Optional[OCRBackend] = None
        self._init_lock = asyncio.Lock()
        # 并发控制（业务层也要用，但这里存一个默认）
        self._semaphore = asyncio.Semaphore(settings.MULTIMODAL_OCR_CONCURRENCY)
        logger.info(
            f"OCRService 初始化: backend={settings.MULTIMODAL_OCR_BACKEND}, "
            f"concurrency={settings.MULTIMODAL_OCR_CONCURRENCY}, "
            f"max_images/doc={settings.MULTIMODAL_MAX_IMAGES_PER_DOC}"
        )

    async def _get_backend(self) -> OCRBackend:
        if self._backend is not None:
            return self._backend
        async with self._init_lock:
            if self._backend is not None:
                return self._backend
            name = settings.MULTIMODAL_OCR_BACKEND
            if name == "llm_vision":
                self._backend = LLMVisionBackend()
            elif name == "tesseract":
                self._backend = TesseractBackend()
            else:
                logger.warning(f"未知 OCR 后端 {name}，回退 llm_vision")
                self._backend = LLMVisionBackend()
            return self._backend

    @property
    def semaphore(self) -> asyncio.Semaphore:
        return self._semaphore

    async def _analyze_with_retry(
        self, image_bytes: bytes, mime_type: str, prompt: str, max_retries: int = 1
    ) -> str:
        """调用后端 + 1 次重试（不重试 OCRUnsupportedError）"""
        backend = await self._get_backend()
        last_exc: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            try:
                return await backend.analyze(
                    image_bytes, mime_type, prompt,
                    settings.MULTIMODAL_OCR_TIMEOUT_SEC,
                )
            except OCRUnsupportedError:
                raise  # 永久性，不重试
            except Exception as e:
                last_exc = e
                if attempt < max_retries:
                    logger.warning(f"OCR 失败重试 {attempt + 1}/{max_retries}: {e}")
                    await asyncio.sleep(1.0)
        raise last_exc or OCRBackendError("OCR 失败：未知错误")

    # ── 业务 API ─────────────────────────────────────────────────────────

    async def extract_text(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """通用 OCR：提取图片中的所有文字"""
        return await self._analyze_with_retry(image_bytes, mime_type, PROMPT_GENERAL_OCR)

    async def extract_formula(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """公式识别：返回 LaTeX 字符串（无公式时为 NO_FORMULA）"""
        result = await self._analyze_with_retry(image_bytes, mime_type, PROMPT_FORMULA)
        # 清洗 markdown 围栏
        return _clean_latex_response(result)

    async def extract_table(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """表格识别：返回 Markdown 表格字符串（无表格时为 NO_TABLE）"""
        return await self._analyze_with_retry(image_bytes, mime_type, PROMPT_TABLE)

    async def extract_chart_description(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """图表描述：返回图表说明文字"""
        return await self._analyze_with_retry(image_bytes, mime_type, PROMPT_CHART)

    async def extract_figure_caption(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """图注识别：返回图注文字（无图注时为 NO_CAPTION）"""
        return await self._analyze_with_retry(image_bytes, mime_type, PROMPT_FIGURE_CAPTION)

    async def classify_and_extract(
        self,
        image_bytes: bytes,
        mime_type: str = "image/png",
    ) -> dict:
        """分类 + 提取：一次调用 LLM 分类图片类型（公式/表格/图表/普通图）并提取内容

        适合大多数场景：节省 OCR 调用次数（一次 vs 三次）

        Returns:
            {
                "category": "formula" | "table" | "chart" | "figure" | "mixed",
                "text": "通用 OCR 文本",
                "latex": "公式 LaTeX" or None,
                "table_md": "Markdown 表格" or None,
                "chart_description": "图表描述" or None,
                "caption": "图注" or None,
            }
        """
        prompt = """你是图片内容分类与提取专家。请分析图片并提取所有可识别的内容。

按以下 JSON 格式输出（严格 JSON，不要任何额外文字）：
{
  "category": "formula|table|chart|figure|mixed",
  "text": "图片中所有可见文字（OCR 结果），保留原始顺序和段落结构",
  "latex": "如果图中有数学公式，输出 LaTeX 代码（不带 $ 包裹），否则 null",
  "table_md": "如果图中有表格，输出 Markdown 表格，否则 null",
  "chart_description": "如果图是图表，输出图表类型+标题+关键数据点+趋势（200字内），否则 null",
  "caption": "如果图下方有图注（图 N: ...），输出图注文字，否则 null"
}

要求：
1. 严格按 JSON 格式输出（不要 ```json``` 包裹）
2. 没识别到的字段填 null，不要编造
3. category 必填：formula=只有公式 / table=只有表格 / chart=图表 / figure=普通插图 / mixed=多种"""
        try:
            result_text = await self._analyze_with_retry(image_bytes, mime_type, prompt)
        except Exception as e:
            logger.error(f"classify_and_extract 失败: {e}")
            return {
                "category": "figure",
                "text": "",
                "latex": None,
                "table_md": None,
                "chart_description": None,
                "caption": None,
                "error": str(e),
            }

        # 解析 JSON（容忍 ```json``` 包裹）
        from app.core.llm import parse_llm_json
        try:
            parsed = parse_llm_json(result_text)
        except Exception as e:
            logger.warning(f"classify_and_extract JSON 解析失败: {e}, raw={result_text[:200]}")
            # fallback: 当作普通图
            return {
                "category": "figure",
                "text": result_text,
                "latex": None,
                "table_md": None,
                "chart_description": None,
                "caption": None,
            }

        # 清洗 LaTeX
        if parsed.get("latex"):
            parsed["latex"] = _clean_latex_response(parsed["latex"])
        return parsed


def _clean_latex_response(latex: str) -> str:
    """清洗 LLM 输出的 LaTeX：去除 markdown 围栏、$ 包裹、NO_FORMULA 标记"""
    if not latex:
        return ""
    s = latex.strip()
    # 去 ```...``` 围栏
    if s.startswith("```"):
        lines = s.split("\n")
        if lines and lines[-1].strip() == "```":
            s = "\n".join(lines[1:-1])
        else:
            s = "\n".join(lines[1:])
    # 去首尾 $（先剥 $$ 再剥 $，处理嵌套）
    s = s.strip()
    if s.startswith("$$") and s.endswith("$$"):
        s = s[2:-2].strip()
    if s.startswith("$") and s.endswith("$"):
        s = s[1:-1].strip()
    # NO_FORMULA 标记
    if re.match(r"^\s*NO_FORMULA\s*$", s, re.IGNORECASE):
        return ""
    return s


def _clean_ocr_text(text: str) -> str:
    """清洗 OCR 文本：去除 ThinkingBlock 序列化残留、thinking 元话语

    背景：vision_service.analyze_image() 走 LLM API，如果模型是思考型（mimo-v2.5），
    即便 thinking:disabled 仍可能在 content 里输出 ThinkingBlock(signature='', thinking='...') 序列化字符串。
    这种情况需要正则剥除。
    """
    if not text:
        return ""
    s = text
    # 1) 完整 ThinkingBlock(... 任意非 ) 字符 ...) — 用平衡括号不现实，改用 .+? 跨非 \n 边界
    s = re.sub(
        r"ThinkingBlock\([^)]*\)",
        "",
        s,
        flags=re.DOTALL,
    )
    # 2) 单独 "thinking='...'" 残留（signature 可能为空也要剥）
    s = re.sub(r"signature=['\"][^'\"]*['\"]", "", s, flags=re.DOTALL)
    s = re.sub(r"type=['\"]thinking['\"]", "", s, flags=re.DOTALL)
    s = re.sub(r"thinking=['\"][^'\"]{10,}['\"]", "", s, flags=re.DOTALL)
    # 3) 元话语前缀（"我需要..."、"用户问的是..."、"首先..."、"让我..."）
    s = re.sub(
        r"^(首先|我需要|让我|我先|用户问的是|开始|好的|我看到|分析图片|让我先).{0,80}?[。！？\n]",
        "",
        s,
    )
    # 4) 短前缀"category: 必须是 X ..." (LLM 把系统 prompt category 指令泄露到内容)
    #    限制为单行（不含 \n）以免误杀多行内容
    s = re.sub(
        r"^category:\s*必须[^\n]*\n?",
        "",
        s,
        flags=re.IGNORECASE,
    )
    # 5) 连续空行压缩
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# 全局单例
ocr_service = OCRService()
