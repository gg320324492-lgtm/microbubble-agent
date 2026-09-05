"""file_parser_service 纯文本族扩展单元测试 (2026-09-05 网盘全格式入库)

不依赖 DB / MinIO / Celery, 纯解析逻辑; 本地直接跑:
    python -m pytest tests/test_file_parser_formats.py -v
"""
import pytest

from app.services.file_parser_service import file_parser_service as fps


@pytest.mark.asyncio
async def test_csv_parsed_as_rows():
    r = await fps.extract_content("a,b,c\n1,2,3\n".encode(), "data.csv", "text/csv")
    assert r["text"].splitlines() == ["a b c", "1 2 3"]


@pytest.mark.asyncio
async def test_tsv_delimiter():
    r = await fps.extract_content("a\tb\n1\t2".encode(), "d.tsv", "text/tab-separated-values")
    assert r["text"].splitlines() == ["a b", "1 2"]


@pytest.mark.asyncio
async def test_json_object_pretty():
    r = await fps.extract_content(b'{"k": "v", "n": 1}', "x.json", "application/json")
    assert '"k": "v"' in r["text"]


@pytest.mark.asyncio
async def test_json_list_expanded_per_line():
    r = await fps.extract_content(b'[1, {"a": 2}]', "y.json", "application/json")
    assert r["text"].splitlines() == ["1", '{"a": 2}']


@pytest.mark.asyncio
async def test_invalid_json_falls_back_to_raw_text():
    r = await fps.extract_content(b"not json at all {", "bad.json", "application/json")
    assert "not json at all" in r["text"]


@pytest.mark.asyncio
async def test_html_strips_tags_and_style():
    html = (b"<html><head><style>x{color:red}</style></head>"
            b"<body><h1>Title</h1><p>Body &amp; text</p><!-- c --></body></html>")
    r = await fps.extract_content(html, "p.html", "text/html")
    assert "Title" in r["text"]
    assert "Body & text" in r["text"]
    assert "color:red" not in r["text"]


@pytest.mark.asyncio
async def test_xml_strips_tags():
    r = await fps.extract_content(b"<root><a>1</a><b>2</b></root>", "d.xml", "application/xml")
    assert "1" in r["text"] and "2" in r["text"] and "<root>" not in r["text"]


@pytest.mark.asyncio
async def test_code_file_decoded():
    r = await fps.extract_content(b"def f():\n    return 42\n", "m.py", "text/x-python")
    assert "def f():" in r["text"]


@pytest.mark.asyncio
async def test_gbk_text_decoded():
    r = await fps.extract_content("微纳米气泡实验数据".encode("gb18030"), "note.txt", "text/plain")
    assert "微纳米气泡" in r["text"]


@pytest.mark.asyncio
async def test_yaml_tex_srt_plain_decode():
    for name, ct in [("c.yaml", "application/yaml"), ("t.tex", "application/x-tex"),
                     ("s.srt", "application/x-subrip"), ("q.sql", "application/sql")]:
        r = await fps.extract_content("hello content".encode(), name, ct)
        assert "hello content" in r["text"], name


@pytest.mark.asyncio
async def test_ipynb_code_and_markdown():
    nb = (b'{"cells":[{"cell_type":"markdown","source":["# T"]},'
          b'{"cell_type":"code","source":["print(1)"]}]}')
    r = await fps.extract_content(nb, "n.ipynb", "application/json")
    assert "# T" in r["text"] and "print(1)" in r["text"]


@pytest.mark.asyncio
async def test_legacy_txt_md_unchanged():
    r = await fps.extract_content(b"# hello", "r.md", "text/markdown")
    assert r["text"] == "# hello"
    r = await fps.extract_content(b"plain", "f.txt", "text/plain")
    assert r["text"] == "plain"


@pytest.mark.asyncio
async def test_unsupported_binary_still_raises_for_generic_callers():
    """旧契约保持: 通用 extract_content 对二进制仍抛错 (drive_to_kb 层负责兜底)"""
    with pytest.raises(ValueError):
        await fps.extract_content(b"\x00\x01binary", "a.exe", "application/x-msdownload")
