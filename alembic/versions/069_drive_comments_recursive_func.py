"""v2 PR11 recursive fallback: PostgreSQL function 兜底 (2026-07-24, W68 第 9 批 B-2)

背景:
- W68 第 8 批 B-1 PR11 (commit a2a00ad73) 用 GIN trgm 索引 + path LIKE 替代 N+1 递归
  * drive_comments.path 物化列 (066_drive_comments_path, PR11 引入)
  * GIN trgm 索引 (走 path LIKE '%/X/%' 高效)
  * get_breadcrumb 1 query 拿祖先链
  * list_by_path_prefix 1 query 拿子评论

- fallback 缺失: 极深嵌套 (>50 层) 或 GIN 索引失效 (DB 故障 / 索引重建中) 时
  * 应自动 fallback 到 PostgreSQL 函数 recursive CTE
  * 保证 breadcrumb 永远返回祖先链 (不能 500)

设计:
- 2 个 PostgreSQL function (PL/pgSQL):
  * get_comment_ancestors_recursive(p_comment_id INT) RETURNS TABLE
    - WITH RECURSIVE 从 comment_id 沿 parent_id chain 向上走
    - 返回 id / parent_id / file_id / folder_id / author_id / content / depth
      + is_resolved / created_at / updated_at 全列
    - depth 从 0 开始 (目标评论自己 = 0, 顶层祖先 = N)
    - 不依赖 path 列 (column 可能尚未物化, fallback 必须 self-contained)
  * get_comment_descendants_recursive(p_root_id INT, p_max_depth INT DEFAULT 100) RETURNS TABLE
    - WITH RECURSIVE 从 root_id 沿 id → parent_id 反向走 (子树)
    - 包含 max_depth 限制防无限递归 (默认 100, 上下限 0~1000)
    - 返回同上全列

- GRANTS: EXECUTE ON FUNCTION ... TO app_user (PostgreSQL 应用账号)

依赖:
- 062_drive_comments: drive_comments 表 + parent_id 列必须存在 (上游 PR9)
- 068_drive_notification_dedup: PR13 (上游 PR, 串单链接续)

下接: PR14+ 继续 (comment edit history / soft delete / mention dedup)

实施纪律:
- 0 production code 改动铁律 (W68 第 9 批): 纯新功能, 不动 PR11 老逻辑
- W68 第 4 批 串单链纪律: down_revision 接 068_drive_notification_dedup
  merge 后 verify ScriptDirectory.get_heads() == ['069_drive_comments_recursive_func']
  期望只 1 个 head (CLAUDE.md W68 第 4 批纪律 + memory/w68-alembic-chain-discipline-2026-07-24.md)
- PostgreSQL function 用 STABLE 标记 (只读, 可被优化器缓存)
- GRANT EXECUTE TO app_user (生产账号, 不是 superuser)
- 嵌套深度默认 max_depth=100 (防 DoS / 误用)
- 不创建新索引 (不破坏现有 GIN trgm 索引)
- 不引用 path 列 (兼容 PR11 前后两种 schema — fallback 必须 self-contained)
"""
from typing import Union

from alembic import op


revision: str = "069_drive_comments_recursive_func"
down_revision: Union[str, None] = "068_drive_notification_dedup"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # === 1. get_comment_ancestors_recursive (向上: 祖先链) ===
    # 输入: p_comment_id (目标评论 id)
    # 输出: 祖先链 + 自己, 按 depth 升序 (目标评论 = depth 0, 最远祖先 = depth N)
    # 兼容: 不引用 path 列 (PR11 前 schema 也能跑)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION get_comment_ancestors_recursive(
            p_comment_id INT
        )
        RETURNS TABLE (
            id INT,
            parent_id INT,
            depth INT,
            file_id INT,
            folder_id INT,
            author_id INT,
            content TEXT,
            is_resolved BOOLEAN,
            created_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ
        )
        LANGUAGE plpgsql
        STABLE
        AS $$
        BEGIN
            -- 边界: comment 不存在直接返回空
            IF NOT EXISTS (SELECT 1 FROM drive_comments WHERE drive_comments.id = p_comment_id) THEN
                RETURN;
            END IF;

            -- WITH RECURSIVE: 从自己开始, 沿 parent_id chain 向上
            RETURN QUERY
            WITH RECURSIVE ancestor_chain AS (
                -- 基例: 目标评论自己 (depth=0)
                SELECT
                    c.id,
                    c.parent_id,
                    0 AS depth,
                    c.file_id,
                    c.folder_id,
                    c.author_id,
                    c.content::text,
                    c.is_resolved,
                    c.created_at,
                    c.updated_at
                FROM drive_comments c
                WHERE c.id = p_comment_id

                UNION ALL

                -- 递归: 找 parent
                SELECT
                    p.id,
                    p.parent_id,
                    ac.depth + 1 AS depth,
                    p.file_id,
                    p.folder_id,
                    p.author_id,
                    p.content::text,
                    p.is_resolved,
                    p.created_at,
                    p.updated_at
                FROM drive_comments p
                INNER JOIN ancestor_chain ac ON p.id = ac.parent_id
            )
            SELECT
                ac.id,
                ac.parent_id,
                ac.depth,
                ac.file_id,
                ac.folder_id,
                ac.author_id,
                ac.content,
                ac.is_resolved,
                ac.created_at,
                ac.updated_at
            FROM ancestor_chain ac
            ORDER BY ac.depth ASC;
        END;
        $$;
        """
    )

    # === 2. get_comment_descendants_recursive (向下: 子树) ===
    # 输入: p_root_id (起始评论 id) + p_max_depth (嵌套深度上限, 防 DoS)
    # 输出: root + 全部后代, 按 depth 升序, 同 depth 按 created_at 升序
    op.execute(
        """
        CREATE OR REPLACE FUNCTION get_comment_descendants_recursive(
            p_root_id INT,
            p_max_depth INT DEFAULT 100
        )
        RETURNS TABLE (
            id INT,
            parent_id INT,
            depth INT,
            file_id INT,
            folder_id INT,
            author_id INT,
            content TEXT,
            is_resolved BOOLEAN,
            created_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ
        )
        LANGUAGE plpgsql
        STABLE
        AS $$
        DECLARE
            v_root_exists BOOLEAN;
        BEGIN
            -- 边界: root_id 不存在直接返回空
            SELECT EXISTS (
                SELECT 1 FROM drive_comments WHERE drive_comments.id = p_root_id
            ) INTO v_root_exists;
            IF NOT v_root_exists THEN
                RETURN;
            END IF;

            -- max_depth 边界 (防无限递归 / DoS)
            IF p_max_depth < 0 THEN
                p_max_depth := 0;
            END IF;
            IF p_max_depth > 1000 THEN
                p_max_depth := 1000;
            END IF;

            -- WITH RECURSIVE: 从 root 开始, 沿 id → parent_id 反向走 (子树)
            RETURN QUERY
            WITH RECURSIVE descendant_tree AS (
                -- 基例: root 节点 (depth=0)
                SELECT
                    c.id,
                    c.parent_id,
                    0 AS depth,
                    c.file_id,
                    c.folder_id,
                    c.author_id,
                    c.content::text,
                    c.is_resolved,
                    c.created_at,
                    c.updated_at
                FROM drive_comments c
                WHERE c.id = p_root_id

                UNION ALL

                -- 递归: 找 children (parent_id = 自己的 id)
                SELECT
                    child.id,
                    child.parent_id,
                    dt.depth + 1 AS depth,
                    child.file_id,
                    child.folder_id,
                    child.author_id,
                    child.content::text,
                    child.is_resolved,
                    child.created_at,
                    child.updated_at
                FROM drive_comments child
                INNER JOIN descendant_tree dt ON child.parent_id = dt.id
                WHERE dt.depth < p_max_depth  -- 深度限制
            )
            SELECT
                dt.id,
                dt.parent_id,
                dt.depth,
                dt.file_id,
                dt.folder_id,
                dt.author_id,
                dt.content,
                dt.is_resolved,
                dt.created_at,
                dt.updated_at
            FROM descendant_tree dt
            ORDER BY dt.depth ASC, dt.created_at ASC;
        END;
        $$;
        """
    )

    # === 3. GRANT EXECUTE TO app_user (生产账号) ===
    # 注意: app_user 必须存在 (CLAUDE.md 752 行铁律 — 部署必做清单)
    op.execute(
        "GRANT EXECUTE ON FUNCTION get_comment_ancestors_recursive(INT) TO app_user"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION get_comment_descendants_recursive(INT, INT) TO app_user"
    )

    # === 4. 注释 (pg_description, 帮助 DBA 理解函数用途) ===
    op.execute(
        """
        COMMENT ON FUNCTION get_comment_ancestors_recursive(INT) IS
        'v2 PR11 fallback (W68 第 9 批 B-2): 拿评论祖先链 (WITH RECURSIVE 沿 parent_id 向上).
        用于 GIN trgm 索引失效时自动 fallback. 不依赖 path 列物化, 兼容 PR11 前后 schema.'
        """
    )
    op.execute(
        """
        COMMENT ON FUNCTION get_comment_descendants_recursive(INT, INT) IS
        'v2 PR11 fallback (W68 第 9 批 B-2): 拿评论子树 (WITH RECURSIVE 沿 parent_id 反向).
        用于按 root 拿全部后代, max_depth 默认 100 防无限递归.'
        """
    )


def downgrade() -> None:
    # 顺序: 先 revoke (如果有其他对象引用), 再 drop function
    op.execute(
        "REVOKE EXECUTE ON FUNCTION get_comment_ancestors_recursive(INT) FROM app_user"
    )
    op.execute(
        "REVOKE EXECUTE ON FUNCTION get_comment_descendants_recursive(INT, INT) FROM app_user"
    )
    op.execute("DROP FUNCTION IF EXISTS get_comment_ancestors_recursive(INT)")
    op.execute("DROP FUNCTION IF EXISTS get_comment_descendants_recursive(INT, INT)")