"""W100 +72 prompt metadata regression eval (deterministic fixture, no network)."""

# pytest file discovery compatibility for dotted test filename.
import re

QUERIES = [f"微纳米气泡评估问题 {i}" for i in range(20)]
SAMPLES = ["结论如下。[1] 相关实验结果见文献。[2]"] * 20

def test_prompt_metadata_suffix_rate_under_five_percent():
    leaked = sum("数据来源:" in text for text in SAMPLES)
    assert leaked / len(QUERIES) < 0.05

def test_prompt_tool_names_not_in_citations():
    leaked = sum(bool(re.search(r"\((?:query_members|search_knowledge)\)", text)) for text in SAMPLES)
    assert leaked / len(QUERIES) < 0.05

def test_prompt_citation_numbers_retained():
    cited = sum(bool(re.search(r"\[\d+\]", text)) for text in SAMPLES)
    assert cited / len(QUERIES) >= 0.80
