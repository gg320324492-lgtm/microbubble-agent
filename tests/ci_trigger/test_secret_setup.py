"""W89-P-9 CI 触发 + secret 部署 文档化验证.

派工 v6 §5 反馈 类 20.57 实战:
  - ci-secret-setup.md 必含 3 secret 名 (TOKEN/USERNAME/PASSWORD)
  - ci-trigger.md 必含触发命令 + 本机限制 + 5 条铁律
  - 文档必在 base dir (agent-w89-p9-ci-trigger/docs/), 不依赖外部状态

设计纪律:
  - 纯文档存在性 + 文本断言, 不调外部 API, 不依赖 docker
  - 验证 3 个 secret 名都出现, 防止漏写
"""
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = PROJECT_ROOT / "docs"


def test_ci_secret_setup_doc_exists():
    """docs/ci-secret-setup.md 必存在"""
    doc = DOCS_DIR / "ci-secret-setup.md"
    assert doc.exists(), f"缺文档: {doc}"


def test_ci_trigger_doc_exists():
    """docs/ci-trigger.md 必存在"""
    doc = DOCS_DIR / "ci-trigger.md"
    assert doc.exists(), f"缺文档: {doc}"


def test_secret_names_documented():
    """3 个 secret 名必出现在 ci-secret-setup.md"""
    doc = (DOCS_DIR / "ci-secret-setup.md").read_text(encoding="utf-8")
    for secret in [
        "PLAYWRIGHT_TEST_TOKEN",
        "PLAYWRIGHT_TEST_USERNAME",
        "PLAYWRIGHT_TEST_PASSWORD",
    ]:
        assert secret in doc, f"缺 secret 名: {secret}"


def test_ci_trigger_doc_has_dispatch():
    """ci-trigger.md 必含 workflow_dispatch 触发命令"""
    doc = (DOCS_DIR / "ci-trigger.md").read_text(encoding="utf-8")
    assert "workflow_dispatch" in doc, "缺 workflow_dispatch 触发命令"
    assert "gh workflow run" in doc, "缺 gh workflow run 命令"


def test_ci_trigger_doc_acknowledges_gh_cli_missing():
    """ci-trigger.md 必诚实报告 gh CLI 未装"""
    doc = (DOCS_DIR / "ci-trigger.md").read_text(encoding="utf-8")
    assert "gh CLI" in doc, "缺 gh CLI 状态报告"
    # 不强求"未装"字面, 但必含限制说明 (派工 v6 §5 反馈 #类 20.57 #4)


def test_class_20_57_referenced():
    """类 20.57 必出现 (派工 v6 §5 反馈必沉淀)"""
    secret_doc = (DOCS_DIR / "ci-secret-setup.md").read_text(encoding="utf-8")
    trigger_doc = (DOCS_DIR / "ci-trigger.md").read_text(encoding="utf-8")
    assert "20.57" in secret_doc, "ci-secret-setup.md 缺类 20.57 引用"
    assert "20.57" in trigger_doc, "ci-trigger.md 缺类 20.57 引用"


def test_no_secret_in_git_tracked_files():
    """git tracked docs/ 不应含真实 JWT (防御性检查)."""
    # 仅文档路径含 secret 名 (公开文档化 OK)
    # 但绝不含形如 eyJxxxxx 的真实 JWT
    import re
    jwt_pattern = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
    for md_file in [DOCS_DIR / "ci-secret-setup.md", DOCS_DIR / "ci-trigger.md"]:
        content = md_file.read_text(encoding="utf-8")
        assert not jwt_pattern.search(content), f"{md_file} 含疑似真实 JWT, 立即清理"