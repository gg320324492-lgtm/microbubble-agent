"""Phase 7 OCR 服务单元测试

覆盖：
- _clean_latex_response 各种清洗场景
- _clean_ocr_text thinking block 剥除
- 后端路由（端到端最少覆盖）
- 异常类型

不依赖 DB / 真实 LLM（mock），纯逻辑测试。
"""
import os
import pytest

os.environ.setdefault("SKIP_DB_SETUP", "1")


class TestCleanLatex:
    """_clean_latex_response 函数测试"""

    def test_strip_markdown_fence(self):
        from app.services.ocr_service import _clean_latex_response
        result = _clean_latex_response("```latex\nE = mc^2\n```")
        assert result == "E = mc^2"

    def test_strip_dollar_wrapping(self):
        from app.services.ocr_service import _clean_latex_response
        assert _clean_latex_response("$E = mc^2$") == "E = mc^2"
        assert _clean_latex_response("$$E = mc^2$$") == "E = mc^2"

    def test_no_formula_marker(self):
        from app.services.ocr_service import _clean_latex_response
        assert _clean_latex_response("NO_FORMULA") == ""
        assert _clean_latex_response("no_formula") == ""
        assert _clean_latex_response(" NO_FORMULA ") == ""

    def test_empty(self):
        from app.services.ocr_service import _clean_latex_response
        assert _clean_latex_response("") == ""
        assert _clean_latex_response(None) == ""

    def test_passthrough(self):
        from app.services.ocr_service import _clean_latex_response
        assert _clean_latex_response("E = mc^2") == "E = mc^2"


class TestCleanOcrText:
    """_clean_ocr_text 函数测试 — 关键：thinking 块剥除"""

    def test_strip_thinking_block_full(self):
        from app.services.ocr_service import _clean_ocr_text
        text = """Some real content
ThinkingBlock(signature='abc123def456', thinking='I need to analyze this image carefully and consider all the visual elements present. First, I will look at the chart and identify the axes, the legend, and the data points...', type='thinking')
More real content"""
        result = _clean_ocr_text(text)
        assert "Some real content" in result
        assert "More real content" in result
        assert "ThinkingBlock" not in result
        assert "thinking='" not in result

    def test_strip_thinking_block_empty_signature(self):
        """空 signature 也得剥除（mimo-v2.5 实际遇到的情形）"""
        from app.services.ocr_service import _clean_ocr_text
        text = """Real OCR text
ThinkingBlock(signature='', thinking='User provided an image that I need to analyze carefully. The image contains several scientific charts and diagrams that I will describe in detail.', type='thinking')
End of OCR"""
        result = _clean_ocr_text(text)
        assert "Real OCR text" in result
        assert "End of OCR" in result
        assert "ThinkingBlock" not in result

    def test_strip_meta_thinking_prefix(self):
        from app.services.ocr_service import _clean_ocr_text
        text = "我需要先分析这张图片。\n这是图表内容：..."
        result = _clean_ocr_text(text)
        # 元话语前缀被剥除
        assert "我需要先分析" not in result
        assert "图表内容" in result

    def test_strip_category_instruction_leak(self):
        """LLM 把 system prompt 的 category 指令泄露到内容"""
        from app.services.ocr_service import _clean_ocr_text
        text = """category: 必须是 "formula"、"table"、"chart"、"figure" 或 "mixed"
Real content here"""
        result = _clean_ocr_text(text)
        assert "category" not in result
        assert "Real content here" in result

    def test_collapse_excess_newlines(self):
        from app.services.ocr_service import _clean_ocr_text
        text = "line1\n\n\n\n\nline2"
        result = _clean_ocr_text(text)
        assert "\n\n\n" not in result

    def test_empty_input(self):
        from app.services.ocr_service import _clean_ocr_text
        assert _clean_ocr_text("") == ""
        assert _clean_ocr_text(None) == ""

    def test_normal_text_unchanged(self):
        from app.services.ocr_service import _clean_ocr_text
        text = "Line 1\nLine 2\nLine 3"
        assert _clean_ocr_text(text) == text


class TestConfigMultimodal:
    """多模态配置测试"""

    def test_multimodal_settings_exist(self):
        from app.config import settings
        assert hasattr(settings, "MULTIMODAL_OCR_BACKEND")
        assert settings.MULTIMODAL_OCR_BACKEND in ("llm_vision", "tesseract")
        assert settings.MULTIMODAL_MAX_IMAGES_PER_DOC > 0
        assert settings.MULTIMODAL_OCR_CONCURRENCY >= 1
        assert settings.MULTIMODAL_MIN_IMAGE_PIXELS > 0
        assert settings.MULTIMODAL_MAX_IMAGE_PIXELS > settings.MULTIMODAL_MIN_IMAGE_PIXELS

    def test_ocr_service_init(self):
        """OCR 服务可初始化（不需要 LLM 调用）"""
        from app.services.ocr_service import ocr_service
        assert ocr_service is not None
        assert ocr_service.semaphore is not None
        # 异步 semaphore 不能直接 get_running_loop().running 但能拿到对象


class TestImageResize:
    """_resize_image_if_needed 工具函数测试"""

    def test_small_image_passthrough(self):
        from app.services.multimodal_extraction_service import _resize_image_if_needed
        # 1x1 像素 PNG（67 字节）
        png_1x1 = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
            b'\x00\x00\x00\rIDATx\x9cc\xfc\xff\xff?\x00\x05\xfe\x02'
            b'\xfe\xa6\x86\xc6\x1e\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        result_bytes, dimensions = _resize_image_if_needed(png_1x1, 1000 * 1000)
        assert result_bytes == png_1x1  # 不缩放
        assert dimensions == (1, 1)

    def test_mime_detection(self):
        from app.services.multimodal_extraction_service import _detect_mime
        # PNG 魔数
        assert _detect_mime(b'\x89PNG\r\n\x1a\n' + b'\x00' * 10) == "image/png"
        # JPEG 魔数
        assert _detect_mime(b'\xff\xd8' + b'\x00' * 10) == "image/jpeg"
        # GIF 魔数
        assert _detect_mime(b'GIF89a' + b'\x00' * 10) == "image/gif"
        # WEBP 魔数
        assert _detect_mime(b'RIFF' + b'\x00\x00\x00\x00' + b'WEBP' + b'\x00' * 10) == "image/webp"
        # 未知魔数 → fallback png
        assert _detect_mime(b'\x00\x00\x00\x00' + b'\x00' * 10) == "image/png"


class TestShouldSkipImage:
    """_should_skip_image 测试"""

    def test_tiny_image_skipped(self):
        from app.services.multimodal_extraction_service import _should_skip_image
        # 1x1 PNG（10x10 = 100 像素，< 100*100=10000）
        png_1x1 = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
            b'\x00\x00\x00\rIDATx\x9cc\xfc\xff\xff?\x00\x05\xfe\x02'
            b'\xfe\xa6\x86\xc6\x1e\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        assert _should_skip_image(png_1x1) is True

    def test_garbage_data_skipped(self):
        from app.services.multimodal_extraction_service import _should_skip_image
        assert _should_skip_image(b"not an image at all") is True


class TestParseMarkdownTable:
    """_parse_markdown_table 测试"""

    def test_basic_table(self):
        from app.services.multimodal_extraction_service import _parse_markdown_table
        md = "| col1 | col2 |\n|---|---|\n| a | b |\n| c | d |"
        result = _parse_markdown_table(md)
        assert result["headers"] == ["col1", "col2"]
        assert result["rows"] == [["a", "b"], ["c", "d"]]
        assert result["caption"] is None

    def test_table_with_caption(self):
        from app.services.multimodal_extraction_service import _parse_markdown_table
        md = "**表 3-1 实验结果**\n| A | B |\n|---|---|\n| 1 | 2 |"
        result = _parse_markdown_table(md)
        assert result["caption"] == "表 3-1 实验结果"
        assert result["headers"] == ["A", "B"]
        assert result["rows"] == [["1", "2"]]

    def test_empty_table(self):
        from app.services.multimodal_extraction_service import _parse_markdown_table
        assert _parse_markdown_table("")["rows"] == []
        assert _parse_markdown_table(None)["rows"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
