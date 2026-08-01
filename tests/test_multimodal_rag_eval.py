"""W99 P3 跨模态 RAG 评估测试。

8 cases: 5 image OCR comparisons, 2 HTML table comparisons, 1 LaTeX formula
comparison. The guard keeps optional evaluator dependencies from making the suite
fail during lightweight environments.
"""

import pytest

pytest.importorskip("app.services.rag_evaluator", reason="RAG evaluator dependencies unavailable")

from app.services.rag_evaluator import RAGEvaluator


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "asset_id,ocr_text,expected,minimum",
    [
        ("img-1", "气泡平均直径：42 μm", "气泡平均直径：42 μm", 1.0),
        ("img-2", "气泡数量：128 个", "气泡数量：128 个", 1.0),
        ("img-3", "ζ 电位：-31.5 mV", "ζ 电位：-31.5 mV", 1.0),
        ("img-4", "处理时间：30 min", "处理时间：30 min", 1.0),
        ("img-5", "溶解氧提升：2.4 mg/L（重复测量）", "溶解氧提升：2.4 mg/L", 0.8),
    ],
)
async def test_image_ref_ocr_recall_and_comparison(asset_id, ocr_text, expected, minimum):
    """Image references compare OCR text and preserve partial recall."""
    result = await RAGEvaluator().evaluate_multimodal(
        question="图片评估",
        multimodal_refs=[{"type": "image_ref", "asset_id": asset_id, "ocr_text": ocr_text}],
        ground_truth=[{"asset_id": asset_id, "ocr_text": expected}],
    )
    assert result["evaluated"] == 1
    assert result["modalities"][0]["type"] == "image_ref"
    assert result["modalities"][0]["score"] >= minimum
    assert result["overall"] >= minimum


@pytest.mark.asyncio
async def test_table_ref_html_cell_comparison():
    """Table references compare semantic cells rather than HTML formatting."""
    result = await RAGEvaluator().evaluate_multimodal(
        question="最佳流量",
        multimodal_refs=[
            {
                "type": "table_ref",
                "asset_id": "table-1",
                "html": "<table><tr><th>流量</th><th>去除率</th></tr><tr><td>2 L/min</td><td>91%</td></tr></table>",
            }
        ],
        ground_truth=[
            {
                "asset_id": "table-1",
                "html": "<table> <tr><th>流量</th><th>去除率</th></tr> <tr><td>2 L/min</td><td>91%</td></tr> </table>",
            }
        ],
    )
    assert result["modalities"][0]["matched"] is True
    assert result["modalities"][0]["score"] == 1.0


@pytest.mark.asyncio
async def test_table_ref_partial_cell_recall():
    """Table scores expose missing cells instead of falsely returning exact match."""
    result = await RAGEvaluator().evaluate_multimodal(
        question="样品 pH",
        multimodal_refs=[
            {
                "type": "table_ref",
                "asset_id": "table-2",
                "html": "<table><tr><th>样品</th><th>pH</th></tr><tr><td>A</td><td>7.1</td></tr></table>",
            }
        ],
        ground_truth=[
            {
                "asset_id": "table-2",
                "html": "<table><tr><th>样品</th><th>pH</th></tr><tr><td>A</td><td>7.1</td></tr><tr><td>B</td><td>7.4</td></tr></table>",
            }
        ],
    )
    assert result["modalities"][0]["matched"] is False
    assert 0.0 < result["modalities"][0]["score"] < 1.0


@pytest.mark.asyncio
async def test_formula_ref_latex_comparison():
    """Formula references normalize delimiters and cdot before comparison."""
    result = await RAGEvaluator().evaluate_multimodal(
        question="Laplace 压差公式",
        multimodal_refs=[
            {
                "type": "formula_ref",
                "asset_id": "formula-1",
                "latex": r"$\Delta P = \frac{2\gamma}{r}$",
            }
        ],
        ground_truth=[
            {
                "asset_id": "formula-1",
                "latex": r"\Delta P = \frac{2\gamma}{r}",
            }
        ],
    )
    assert result["modalities"][0]["matched"] is True
    assert result["modalities"][0]["score"] == 1.0
    assert result["overall"] == 1.0
