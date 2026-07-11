"""
tests/test_drive_file_type_predicate.py — DriveService._build_file_type_predicate 单测

v2.22 (2026-07-11) 新增拆分 office → word/ppt/excel 后, 完整覆盖所有 chip 分类.
该方法是 staticmethod, 无需 DB / 无需 fixture, 直接调 + 验证生成的 SQLAlchemy 表达式.

关键验证:
- 8 类 chip (pdf/image/video/audio/word/ppt/excel/text) 全部命中
- office alias 仍兼容, 覆盖全部 6 扩展名
- 无效 type 返 None (不过滤, frontend chip fallback)
- 谓词包含所有期望的扩展名 LIKE 模式
"""
import pytest
from sqlalchemy import Column

from app.services.drive_service import DriveService


def _extracted_extensions(predicate):
    """从 SQLAlchemy ColumnElement 提取 ILIKE 模式中的扩展名列表.

    谓词形如: OR(file_name ILIKE '%.pdf', file_name ILIKE '%.doc', ...)
    编译 dialect 时拿 string repr, 提取所有 .xxx 后缀.
    """
    from sqlalchemy.dialects import postgresql
    compiled = predicate.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    sql = str(compiled)
    # 提取所有 %.xxx 模式
    import re
    matches = re.findall(r"%(\.[a-z0-9]+)", sql)
    return sorted(set(matches))


@pytest.mark.parametrize("file_type,expected_exts", [
    # === v2 PR2 原有 6 类 ===
    ("pdf",   [".pdf"]),
    ("image", [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"]),
    ("video", [".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv"]),
    ("audio", [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".opus"]),
    # === v2.22 新增 3 类 (拆分 office) ===
    ("word",  [".doc", ".docx"]),
    ("ppt",   [".ppt", ".pptx"]),
    ("excel", [".xls", ".xlsx"]),
    # === text 仍保留 ===
    ("text",  [".txt", ".md", ".log", ".csv"]),
    # === office 仍兼容 (alias 覆盖全部 6 扩展名) ===
    ("office", [".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"]),
])
def test_valid_file_types(file_type, expected_exts):
    pred = DriveService._build_file_type_predicate(file_type)
    assert pred is not None, f"{file_type!r} 应返回有效谓词"
    actual = _extracted_extensions(pred)
    assert actual == sorted(expected_exts), \
        f"{file_type!r} 期望 {expected_exts}, 实际 {actual}"


def test_office_alias_still_compatible():
    """office alias 必须仍兼容, 覆盖 word/ppt/excel 全部 6 扩展名."""
    pred = DriveService._build_file_type_predicate("office")
    actual = _extracted_extensions(pred)
    assert ".doc" in actual and ".docx" in actual
    assert ".ppt" in actual and ".pptx" in actual
    assert ".xls" in actual and ".xlsx" in actual
    assert len(actual) == 6, f"office 应覆盖 6 扩展名, 实际 {actual}"


def test_invalid_file_type_returns_none():
    """无效 type 返 None (frontend chip 友好 fallback: 不过滤)."""
    assert DriveService._build_file_type_predicate("xyz") is None
    assert DriveService._build_file_type_predicate("") is None
    assert DriveService._build_file_type_predicate("unknown_legacy_type") is None


def test_case_insensitive():
    """type 参数应 case-insensitive (前端传 'PDF' 也命中 'pdf')."""
    pred_upper = DriveService._build_file_type_predicate("PDF")
    pred_lower = DriveService._build_file_type_predicate("pdf")
    assert _extracted_extensions(pred_upper) == _extracted_extensions(pred_lower)
    assert _extracted_extensions(pred_upper) == [".pdf"]


def test_no_overlap_between_new_categories():
    """v2.22 拆分后 word/ppt/excel 互不重叠 (每个有独有扩展名)."""
    word = set(_extracted_extensions(DriveService._build_file_type_predicate("word")))
    ppt = set(_extracted_extensions(DriveService._build_file_type_predicate("ppt")))
    excel = set(_extracted_extensions(DriveService._build_file_type_predicate("excel")))
    assert not (word & ppt), f"word ∩ ppt 不应重叠, 实际 {word & ppt}"
    assert not (word & excel), f"word ∩ excel 不应重叠, 实际 {word & excel}"
    assert not (ppt & excel), f"ppt ∩ excel 不应重叠, 实际 {ppt & excel}"
    assert word | ppt | excel == {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}


def test_word_ppt_excel_combined_equals_office():
    """word + ppt + excel 全部扩展名 union == office alias 覆盖范围."""
    combined = set()
    for t in ["word", "ppt", "excel"]:
        combined |= set(_extracted_extensions(DriveService._build_file_type_predicate(t)))
    office = set(_extracted_extensions(DriveService._build_file_type_predicate("office")))
    assert combined == office, f"合并 {combined} 应等于 office alias {office}"