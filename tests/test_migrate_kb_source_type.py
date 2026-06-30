"""KB source_type 重分类脚本 — 纯函数 + 边界单测 (无 DB / 无 async 依赖)

跑法:
    docker exec microbubble-agent-app-1 bash -c "cd /app && python -m pytest tests/test_migrate_kb_source_type.py -v"
"""

import re
import sys
from pathlib import Path

# 容器内 / 本地都兼容
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
if (Path("/app") / "scripts" / "migrate_kb_source_type.py").exists():
    sys.path.insert(0, "/app/scripts")

from migrate_kb_source_type import (  # noqa: E402
    TARGET_SOURCE_TYPE,
    ReclassifyCandidate,
)

# 与脚本逻辑一致的标题前缀 regex (脚本 SQL 层改用 startswith 避开 PG regex 转义陷阱,
# 纯函数场景用这个 regex 测试匹配行为)
TITLE_PREFIX_PATTERN = re.compile(r"^\[拓展[^\]]*\]\s*")


# ── TITLE_PREFIX_PATTERN: 严格 [拓展-XX] 前缀匹配 ────────────────
def test_pattern_basic_match():
    """title 以 [拓展 开头 → 匹配 (含各种 - 后的字母+数字变体)"""
    for title in [
        "[拓展-V01] 微纳米气泡在液体中",
        "[拓展-AA27] 微纳米气泡 + ESG",
        "[拓展-S05] 实验条件",
        "[拓展-U10] 第三方",
        "[拓展-Z04] 氧化锆",
        "[拓展-] 空",
        "[拓展] 单",
    ]:
        assert TITLE_PREFIX_PATTERN.match(title) is not None, f"应当匹配: {title!r}"


def test_pattern_no_match():
    """title 不以 [拓展 开头 → 不匹配 (避免误伤正文含'拓展'的内容)"""
    for title in [
        "微纳米气泡",
        "拓展性研究",
        "微纳米气泡的拓展应用",
        "(拓展) 不带方括号",
        " [拓展] 前导空格 (前导空格破坏 ^ 锚定)",
        "拓展] 不带左方括号",
    ]:
        assert TITLE_PREFIX_PATTERN.match(title) is None, f"不应当匹配: {title!r}"


def test_pattern_extract_prefix():
    """验证 [拓展-AA27] 后跟空格分隔, 提取 prefix 部分"""
    title = "[拓展-AA27] 微纳米气泡 + ESG"
    m = TITLE_PREFIX_PATTERN.match(title)
    assert m is not None
    # group(0) 包含 [拓展-AA27] 本身, 不包含正文
    assert m.group(0).startswith("[拓展-AA27]")


def test_pattern_handles_no_space_after():
    """[拓展-XX] 后直接接正文 (无空格) 也应匹配"""
    title = "[拓展-V01]多个空格的标题"
    m = TITLE_PREFIX_PATTERN.match(title)
    assert m is not None
    # group(0) 是 [拓展-V01] (不包含正文)
    assert m.group(0) == "[拓展-V01]"
    # '[拓展-V01]' 长度: 1+2+1+2+1+1 = 8 字符 ([ + 拓 + 展 + - + V + 0 + 1 + ])
    assert m.end() == 8


# ── TARGET_SOURCE_TYPE 常量稳定性 ────────────────────────────────
def test_target_source_type_stable():
    """前端 chip '✨ 自动拓展' 走 source_type='auto_expansion' 过滤, 这里必须稳定"""
    assert TARGET_SOURCE_TYPE == "auto_expansion"


# ── ReclassifyCandidate dataclass 字段完整性 ─────────────────────
def test_candidate_dataclass_fields():
    """dataclass 字段完整, scan → apply 透传不丢字段"""
    c = ReclassifyCandidate(
        id=123,
        title="[拓展-V01] 测试标题",
        category="综述",
        current_source_type="NULL",
        created_at="2026-06-15T10:00:00",
    )
    assert c.id == 123
    assert c.title == "[拓展-V01] 测试标题"
    assert c.category == "综述"
    assert c.current_source_type == "NULL"
    assert c.new_source_type == "auto_expansion"  # 自动填充


def test_candidate_default_new_source_type():
    """new_source_type 默认值 = TARGET_SOURCE_TYPE, 防硬编码漂移"""
    c = ReclassifyCandidate(id=1, title="t", category="c", current_source_type="NULL")
    assert c.new_source_type == TARGET_SOURCE_TYPE
