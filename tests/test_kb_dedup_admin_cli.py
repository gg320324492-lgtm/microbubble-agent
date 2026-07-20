"""KB dedup admin CLI 纯函数单测 — 不需要 DB

覆盖 scripts/kb_dedup_admin_cli.py 的:
- validate_cleanup_plan (空 group / < 2 records / user-created 拒绝)
- group_duplicate_records (过滤 user-created + non-kb)
- content_hash (SHA-256)
- argparse 互斥组

跑法 (无 DB 依赖):
    docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 bash -c 'cd /app && python -m pytest tests/test_kb_dedup_admin_cli.py -v'

E2E 真写库测试在 tests/scripts/test_kb_dedup_admin_cli_e2e.py (需非 SKIP 模式)。
"""
import sys
from pathlib import Path

import pytest

# 让 scripts/ 可 import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from scripts.kb_dedup_admin_cli import (  # noqa: E402
    CleanupPlan,
    DuplicateGroup,
    KbRecord,
    _build_parser,
    content_hash,
    group_duplicate_records,
    validate_cleanup_plan,
)


def _rec(id: int, title: str, content: str = "default", quality: float = 0.5,
         created_by=None, storage_mode: str = "kb") -> KbRecord:
    return KbRecord(
        id=id,
        title=title,
        content_hash=content_hash(content),
        quality_score=quality,
        created_by=created_by,
        storage_mode=storage_mode,
    )


# ============================================================================
# TestValidateCleanupPlan — 纯函数校验
# ============================================================================

class TestValidateCleanupPlan:
    """validate_cleanup_plan 拒绝不合法 group (PR6-P18 范式)"""

    def test_rejects_single_record_group(self):
        """< 2 records 不构成重复组"""
        plan = CleanupPlan(groups=[
            DuplicateGroup(title="only-one", content_hash="abc", records=[
                _rec(1, "only-one"),
            ]),
        ])
        result = validate_cleanup_plan(plan)
        assert result.valid is False
        assert any("fewer than two records" in err for err in result.errors)

    def test_rejects_user_created_record_in_group(self):
        """用户创建 (created_by 非 None) 不能进 dedup group"""
        plan = CleanupPlan(groups=[
            DuplicateGroup(title="user-dup", content_hash="abc", records=[
                _rec(1, "user-dup", created_by=42),  # user!
                _rec(2, "user-dup", created_by=42),  # user!
            ]),
        ])
        result = validate_cleanup_plan(plan)
        assert result.valid is False
        assert any("user-created record" in err for err in result.errors)

    def test_rejects_non_kb_storage_mode(self):
        """非 kb storage_mode (drive) 不能进 dedup group"""
        plan = CleanupPlan(groups=[
            DuplicateGroup(title="drive-dup", content_hash="abc", records=[
                _rec(1, "drive-dup", storage_mode="drive"),
                _rec(2, "drive-dup", storage_mode="drive"),
            ]),
        ])
        result = validate_cleanup_plan(plan)
        assert result.valid is False
        assert any("non-KB record" in err for err in result.errors)

    def test_accepts_valid_group(self):
        """合法 group (kb + created_by=None + >= 2 records) 应 valid=True"""
        plan = CleanupPlan(groups=[
            DuplicateGroup(title="valid-dup", content_hash="abc", records=[
                _rec(1, "valid-dup", quality=0.3),
                _rec(2, "valid-dup", quality=0.7),  # keep
            ]),
        ])
        result = validate_cleanup_plan(plan)
        assert result.valid is True
        assert result.errors == ()
        assert result.delete_ids == (1,)  # keep id=2, delete id=1

    def test_detects_cross_group_id_collision(self):
        """同一 id 出现在多个 group → 报错"""
        # 同一 id=5 在两个 group 里出现
        plan = CleanupPlan(groups=[
            DuplicateGroup(title="g1", content_hash="h1", records=[
                _rec(5, "g1", quality=0.5),
                _rec(6, "g1", quality=0.7),
            ]),
            DuplicateGroup(title="g2", content_hash="h2", records=[
                _rec(5, "g2", quality=0.5),  # ← collision!
                _rec(7, "g2", quality=0.7),
            ]),
        ])
        result = validate_cleanup_plan(plan)
        assert result.valid is False
        assert any("multiple cleanup groups" in err for err in result.errors)


# ============================================================================
# TestGroupDuplicateRecords — 过滤逻辑
# ============================================================================

class TestGroupDuplicateRecords:
    """group_duplicate_records 过滤 user-created + non-kb"""

    def test_groups_by_title_and_hash(self):
        """相同 (title, content_hash) 分到同组"""
        records = [
            _rec(1, "t1", content="A", quality=0.3),
            _rec(2, "t1", content="A", quality=0.7),  # 同组
            _rec(3, "t2", content="B", quality=0.5),
        ]
        groups = group_duplicate_records(records)
        assert len(groups) == 1  # 只有 t1/A 重复
        assert groups[0].title == "t1"
        assert sorted(r.id for r in groups[0].records) == [1, 2]

    def test_excludes_user_created(self):
        """created_by 非 None 不进组"""
        records = [
            _rec(1, "t1", content="A", created_by=42),  # user
            _rec(2, "t1", content="A", created_by=42),  # user
        ]
        groups = group_duplicate_records(records)
        assert len(groups) == 0  # user 创建的不算重复组

    def test_excludes_non_kb_storage(self):
        """storage_mode != 'kb' 不进组"""
        records = [
            _rec(1, "t1", content="A", storage_mode="drive"),
            _rec(2, "t1", content="A", storage_mode="drive"),
        ]
        groups = group_duplicate_records(records)
        assert len(groups) == 0

    def test_single_record_not_grouped(self):
        """单条记录不构成 group"""
        records = [_rec(1, "lonely", content="A")]
        groups = group_duplicate_records(records)
        assert len(groups) == 0

    def test_different_content_not_grouped(self):
        """content 不同 → hash 不同 → 不进同组"""
        records = [
            _rec(1, "t1", content="A"),
            _rec(2, "t1", content="B"),  # hash 不同
        ]
        groups = group_duplicate_records(records)
        assert len(groups) == 0


# ============================================================================
# TestContentHash — SHA-256 工具
# ============================================================================

class TestContentHash:
    """content_hash 工具函数"""

    def test_same_content_same_hash(self):
        """相同 content 相同 hash"""
        assert content_hash("hello") == content_hash("hello")

    def test_different_content_different_hash(self):
        """不同 content 不同 hash"""
        assert content_hash("hello") != content_hash("world")

    def test_empty_content_returns_zero_hash(self):
        """None / 空字符串 → SHA-256('') 确定性 hash"""
        assert content_hash("") == content_hash(None)
        # SHA-256 of empty string
        import hashlib
        assert content_hash("") == hashlib.sha256(b"").hexdigest()

    def test_unicode_content(self):
        """中文 content 也能 hash"""
        h1 = content_hash("微纳米气泡研究")
        h2 = content_hash("微纳米气泡研究")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex


# ============================================================================
# TestArgparse — 互斥组
# ============================================================================

class TestArgparse:
    """_build_parser argparse 配置"""

    def test_scan_validate_apply_mutually_exclusive(self):
        """--scan 与 --validate 与 --apply 互斥"""
        parser = _build_parser()
        # 同时传 --scan 和 --validate → SystemExit
        with pytest.raises(SystemExit):
            parser.parse_args(["--scan", "--validate"])

    def test_scan_alone_works(self):
        """仅 --scan 合法"""
        parser = _build_parser()
        args = parser.parse_args(["--scan"])
        assert args.scan is True
        assert args.validate is False
        assert args.apply is False
        assert args.confirm is False

    def test_apply_without_confirm_flag(self):
        """--apply 不带 --confirm (confirm 默认 False)"""
        parser = _build_parser()
        args = parser.parse_args(["--apply"])
        assert args.apply is True
        assert args.confirm is False

    def test_apply_with_confirm_flag(self):
        """--apply --confirm (confirm=True)"""
        parser = _build_parser()
        args = parser.parse_args(["--apply", "--confirm"])
        assert args.apply is True
        assert args.confirm is True

    def test_no_mode_rejected(self):
        """没传任何 mode → SystemExit"""
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])