"""141: ZB-2 备份隐私收口 — 根目录存量备份行刷 private + 清除已泄露的 kb 孪生密钥明文

背景 (ZB-1 验收发现): 桌面端 uploadFile 曾丢弃目录信息, 零感托管备份产物
(<name>.mnbbak 容器 + <name>.mnbbak.key.json 解密钥匙) 全部落根目录且 team 可见;
且服务端自动入库为每个备份建了 kb 孪生行 (source_type='drive_extracted'), 旧实现
把 private 源行翻成 team, content 是密钥信封明文 → 已进 knowledge_chunks 向量索引。

本迁移 (与 app/services/drive_ingest_tasks.is_backup_artifact_name 同语义):
1. drive 行回填: storage_mode='drive' 且 (folder_id IS NULL 且文件名为备份形态)
   或 (位于 backups/ 保留区子树, 同 140 口径) → visibility='private'
2. kb 孪生行清除 (安全强制项, 用户裁决): source_type='drive_extracted' 且文件名
   为备份形态的 kb 行 → 删除, 并同步删除 knowledge_chunks 关联行 (向量索引中的
   密钥片段一并清除)。**只删备份形态**, 其他 drive_extracted (真实文档入库) 不碰。
   删除前完整清单由执行端先 SELECT 存档交总指挥过目 (id/file_name/created_by/
   content 长度), 归档于指挥部仓库。
3. 归档表 knowledge_zb2_removed_kb_rows: 记录被删行 id/file_name/created_by/
   visibility/removed_at —— **不含 content 与 chunk**(密钥明文/片段必须从库里消失,
   归档保留它们即违背本迁移目的)。

downgrade(): 把归档表中未被重建的行以占位 content 重新 INSERT (恢复「行还在」;
原始明文内容无法也**不应**恢复), knowledge_chunks 不恢复; 归档表保留作审计。
注意: 若 downgrade 前应用已按新逻辑运行, 恢复的行不会再被自动抽取 (ZB-2 入口
跳过), 它们仅作为「行存在过」的痕迹。

Revision ID: 141_zb2_backup_kb_purge
Revises: 140_backup_reserved_private
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op

revision: str = "141_zb2_backup_kb_purge"
down_revision: Union[str, None] = "140_backup_reserved_private"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 备份形态文件名判定 (与 drive_ingest_tasks.BACKUP_ARTIFACT_SUFFIXES 对齐, 小写不敏感)
_BACKUP_NAME = "(lower(k.file_name) LIKE '%%.mnbbak' OR lower(k.file_name) LIKE '%%.key.json')"

# backups/ 保留区子树 (与 140 同口径)
_RESERVED_CTE = """
WITH RECURSIVE reserved_folders AS (
    SELECT id FROM folders
    WHERE parent_id IS NULL AND deleted_at IS NULL AND lower(btrim(name)) = 'backups'
    UNION ALL
    SELECT f.id FROM folders f
    JOIN reserved_folders rf ON f.parent_id = rf.id
    WHERE f.deleted_at IS NULL
)
SELECT id FROM reserved_folders
"""

_ARCHIVE_TABLE = "knowledge_zb2_removed_kb_rows"


def upgrade() -> None:
    # 1) drive 行回填: 根目录备份形态 + 保留区子树内 drive 行 → private (区外不碰)
    op.execute(
        f"""
        UPDATE knowledge k
        SET visibility = 'private'
        WHERE k.storage_mode = 'drive'
          AND (
            (k.folder_id IS NULL AND {_BACKUP_NAME})
            OR k.folder_id IN ({_RESERVED_CTE})
          )
        """
    )

    # 2) 归档表 (无 content —— 密钥明文必须从库里消失)
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_ARCHIVE_TABLE} (
            id integer PRIMARY KEY,
            file_name character varying(500),
            created_by integer,
            visibility character varying(20),
            removed_at timestamp without time zone DEFAULT now()
        )
        """
    )
    op.execute(
        f"""
        INSERT INTO {_ARCHIVE_TABLE} (id, file_name, created_by, visibility)
        SELECT k.id, k.file_name, k.created_by, k.visibility
        FROM knowledge k
        WHERE k.source_type = 'drive_extracted'
          AND {_BACKUP_NAME}
          AND NOT EXISTS (SELECT 1 FROM {_ARCHIVE_TABLE} a WHERE a.id = k.id)
        """
    )

    # 3) 删孪生行的向量 chunk (密钥片段) + 行本体
    op.execute(
        f"""
        DELETE FROM knowledge_chunks c
        USING knowledge k
        WHERE c.knowledge_id = k.id
          AND k.source_type = 'drive_extracted'
          AND {_BACKUP_NAME}
        """
    )
    op.execute(
        f"""
        DELETE FROM knowledge k
        WHERE k.source_type = 'drive_extracted'
          AND {_BACKUP_NAME}
        """
    )


def downgrade() -> None:
    # 恢复「行还在」: 占位 content (原始密钥明文无法也不应还原), chunks 不恢复。
    # id 已被重建占用的跳过 (应用侧可能已产生新行)。
    # created_at/updated_at 无 server_default (TimestampMixin 为 python 侧默认), 用 now() 补。
    op.execute(
        f"""
        INSERT INTO knowledge (id, title, content, source_type, source, file_name,
                               file_type, file_size, created_by, storage_mode,
                               visibility, folder_id, analysis_status,
                               created_at, updated_at)
        SELECT a.id, a.file_name,
               '[ZB-2 迁移 141: 备份形态知识库行已删除 (原文含密钥信封明文, 不可还原)]',
               'drive_extracted', '', a.file_name, 'bin', 0, a.created_by,
               'kb', a.visibility, NULL, 'skipped',
               now(), now()
        FROM {_ARCHIVE_TABLE} a
        WHERE NOT EXISTS (SELECT 1 FROM knowledge k WHERE k.id = a.id)
        """
    )
