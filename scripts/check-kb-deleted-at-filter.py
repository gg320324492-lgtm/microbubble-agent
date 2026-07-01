#!/usr/bin/env python3
"""2026-07-01 PR1.7 课题组网盘 lint 审计

扫描 app/ 所有 select(Knowledge...) 语句, 检测是否缺少 deleted_at IS NULL 过滤。

背景:
- Knowledge 表新增 deleted_at 列 (软删除时间戳)
- 软删除条目在回收站保留 3 天后被 Celery beat 物理清除
- 在被物理清除前, 所有 SELECT 必须过滤 deleted_at IS NULL 否则显示已删条目

用法:
  python scripts/check-kb-deleted-at-filter.py

退出码:
  0 = 全部通过 (或仅豁免的代码)
  1 = 发现需要修复的 SELECT (输出详细列表)
"""
import re
import sys
from pathlib import Path

# 扫描范围
APP_DIR = Path(__file__).parent.parent / "app"

# 豁免规则 (按 file:line 精确豁免)
# 这些地方 select(Knowledge) 是有意为之, 不需要 deleted_at 过滤
EXEMPT_PATTERNS = [
    # 软删除清理任务本身就是查 deleted_at IS NOT NULL, 自然豁免
    r"app/services/drive_cleanup_tasks\.py",
    r"app/services/task_service\.py",  # task trash 清理类似模式
    r"app/services/chat_history_tasks\.py",  # chat 清理类似模式
    # Alembic migration 文件不需要 lint
    r"alembic/versions/",
]

# select(Knowledge...) 模式 (主表, 不含 KnowledgeEntity/Formula/Relation/Image/Gap)
SELECT_KNOWLEDGE_RE = re.compile(
    r"select\(\s*Knowledge\b[^)]*\)",
    re.MULTILINE | re.DOTALL,
)


def audit_file(filepath: Path) -> list[dict]:
    """审计单个文件, 返回缺少 deleted_at 过滤的 select 列表"""
    content = filepath.read_text(encoding="utf-8")
    rel_path = str(filepath.relative_to(filepath.parent.parent))

    # 豁免检查
    for pattern in EXEMPT_PATTERNS:
        if re.search(pattern, rel_path):
            return []

    issues = []

    # 多行 select 检测 (跨行匹配)
    # 因为 select 可能跨越多行, 我们用滑动窗口查找 select 后 30 行内是否含 deleted_at
    lines = content.split("\n")
    for i, line in enumerate(lines):
        # 仅匹配 select(Knowledge...) (主表), 不匹配 KnowledgeEntity/Formula/Relation
        # 用 word boundary 确保不会误判 select(KnowledgeEntity)
        if re.search(r"\bselect\(\s*Knowledge\b[^(]", line) and "select(KnowledgeEntity" not in line \
           and "select(KnowledgeFormula" not in line \
           and "select(KnowledgeRelation" not in line \
           and "select(KnowledgeImage" not in line \
           and "select(KnowledgeHypothesis" not in line \
           and "select(KnowledgeGap" not in line \
           and "select(KnowledgeLayout" not in line \
           and "select(KnowledgeExtraction" not in line:
            # 检查后续 30 行 (含 select 内部的多行 where 子句)
            window_end = min(i + 30, len(lines))
            window_text = "\n".join(lines[i:window_end])

            # 必须满足以下任一条件:
            # 1. 包含 deleted_at IS NULL
            # 2. 是 drive 清理任务 (drive_cleanup_tasks.py 已豁免)
            # 3. 是 SELECT for soft-delete restore (deleted_at IS NOT NULL)

            has_deleted_at_null = re.search(
                r"deleted_at\.is_\(\s*None\s*\)|deleted_at\s+IS\s+NULL", window_text
            )
            has_deleted_at_not_null = re.search(
                r"deleted_at\.isnot\(\s*None\s*\)|deleted_at\s+IS\s+NOT\s+NULL", window_text
            )

            # 注释行 (-- 开头) 不算
            # 简化: 只要在窗口内找到 deleted_at IS NULL/NOT NULL 都视为已过滤
            if not has_deleted_at_null and not has_deleted_at_not_null:
                issues.append({
                    "file": rel_path,
                    "line": i + 1,
                    "snippet": line.strip()[:120],
                })

    return issues


def main():
    print("🔍 扫描 app/ 所有 select(Knowledge...) 语句...")
    print(f"   扫描范围: {APP_DIR}")
    print(f"   豁免规则: {len(EXEMPT_PATTERNS)} 个")
    print()

    all_issues = []

    # 递归扫描 .py 文件
    py_files = list(APP_DIR.rglob("*.py"))
    print(f"   发现 {len(py_files)} 个 Python 文件")
    print()

    for filepath in py_files:
        issues = audit_file(filepath)
        all_issues.extend(issues)

    # 按文件分组
    by_file = {}
    for issue in all_issues:
        by_file.setdefault(issue["file"], []).append(issue)

    if not all_issues:
        print("✅ 全部通过! 所有 select(Knowledge...) 都已包含 deleted_at 过滤")
        return 0

    print(f"⚠️  发现 {len(all_issues)} 处需要修复:")
    print()
    for filepath, issues in sorted(by_file.items()):
        print(f"📄 {filepath} ({len(issues)} 处)")
        for issue in issues:
            print(f"   L{issue['line']}: {issue['snippet']}")
        print()

    print("=" * 60)
    print("💡 修复方式:")
    print("   在 WHERE 子句追加: .where(Knowledge.deleted_at.is_(None))")
    print("   如果是清理任务的 SELECT (查 deleted_at IS NOT NULL),")
    print("   在豁免规则 EXEMPT_PATTERNS 中添加该文件路径。")
    print()

    return 1


if __name__ == "__main__":
    sys.exit(main())