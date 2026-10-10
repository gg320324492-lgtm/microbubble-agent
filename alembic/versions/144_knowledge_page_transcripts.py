"""144: PPT 整页视觉转写独立表 (2026-10-10, agent44)

背景:
agent43 跑完 native<143 档, 得到 2317 页整页视觉转写 (2062 页可入库 / 255 页
blocked), 其中 A 类 = 「未被现有索引覆盖且非装饰非噪声」的新增字符 352,311 字,
是现有索引的 5.97 倍 —— 这批内容此前**完全检索不到**。

为什么不塞进 ``knowledge_images`` (agent44 实测否决):
1. ``knowledge_images.image_url`` 是 **NOT NULL**, 而整页转写没有图片 URL
   (入池的是纯文本, 不是渲染图) —— 只能造假 URL 骗过约束。
2. 该表既有语义是「从文档里抽出的某张**图**」: ``figure_type`` /
   ``is_core_figure`` / ``section_hint`` / ``anchor_paragraph_index`` /
   ``visual_summary`` 全是图表级字段, 前端 RightImageRail 按 ``figure_no`` +
   ``is_core_figure`` 渲染。混入 2062 条整页转写会污染既有 5446 行的语义,
   让「按图检索/按图分类」功能把整页当图处理。
3. ``multimodal_retriever._load_candidates`` 的 ``_not_banner_predicate()``
   依赖 ``width``/``height``/``page_number`` 三列, 整页转写没有前两列 ——
   落进去等于让一个基于图元数据的判据在 NULL 上跑。

为什么不塞进 ``knowledge_chunks`` (实测否决):
``ck_knowledge_chunks_char_range`` (char_end > char_start) +
``ck_knowledge_chunks_char_count`` (char_count = char_end - char_start)
把每条 chunk 钉死在 ``parent.content`` 的精确切片上。整页转写正文**不在**
孪生行的 ``content`` 里, 要落进去就得改写 ``parent.content`` ——
那会连带作废孪生行已有的 11367 条 chunk / 295 条 parent embedding,
且破坏「原生解析文本 vs 视觉转写」的来源可分性, 回滚成本极高。

落点 (agent44 dry-run 实测):
``drive_to_kb_service._create_kb_row`` 建的 kb 孪生行带
``meta->>'drive_source_file_id'`` = drive 行 id。295 个 drive 文件
**100% 有且仅有 1 个**孪生行 (meta 口径实测, 非 file_name 模糊匹配),
且全部 ``deleted_at IS NULL`` + ``visibility IN ('team','public')``。
因此本表 ``knowledge_id`` 指向 **kb 孪生行**而不是 drive 行 —— 孪生行
本就是 ``storage_mode='kb'``, 于是 ``multimodal_retriever:185`` 的
``storage_mode == 'kb'`` 硬过滤**完全不需要放开**, 既有第 5 路一行不改。

blocked 页: 只存 metadata (``content IS NULL`` + 判定理由), 正文不入池,
供人工复核。CHECK 约束把这个不变量钉死在数据库层。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = "144_knowledge_page_transcripts"
down_revision: Union[str, None] = "143_ocr_status_done_no_text"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 幂等守卫 (CLAUDE.md 2026-07-24 alembic 纪律): IF NOT EXISTS 全部
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_page_transcripts (
            id SERIAL PRIMARY KEY,

            -- 指向 kb 孪生行 (storage_mode='kb'), 不是 drive 行
            knowledge_id INTEGER NOT NULL
                REFERENCES knowledge(id) ON DELETE CASCADE,

            -- 溯源: 生成该页转写的 drive 文件行 id
            source_drive_file_id INTEGER NULL,

            -- 页码 (pptx 幻灯片序号 / 文档页号), 从 1 起
            page_number INTEGER NOT NULL,

            -- 净化后正文 (page_transcript_filter.filter_page_transcript 的 .text)
            -- blocked 行恒为 NULL —— 正文不入池, 只留 metadata 供人工复核
            content TEXT NULL,
            char_count INTEGER NULL,

            -- blocked 判定溯源
            blocked BOOLEAN NOT NULL DEFAULT FALSE,
            block_reasons JSONB NULL,
            chrome_ratio DOUBLE PRECISION NULL,

            -- A/B/C/D 字符分类 (agent43 pipeline 口径, 仅统计用)
            a_chars INTEGER NULL,
            b_chars INTEGER NULL,
            c_chars INTEGER NULL,
            d_chars INTEGER NULL,

            -- 反查用 (孪生行已有 file_name, 这里冗余一份便于人工复核时不 JOIN)
            file_name VARCHAR(300) NULL,

            -- 转写产出批次 (哪一次 agent43/a43 跑的)
            ingest_batch VARCHAR(60) NULL,

            embedding vector(1024),

            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),

            -- 不变量: blocked 有 metadata 无正文 / 未 blocked 必须有正文且非空
            CONSTRAINT ck_kpt_blocked_no_body CHECK (
                (blocked = TRUE  AND content IS NULL)
                OR
                (blocked = FALSE AND content IS NOT NULL AND char_count > 0)
            ),
            -- 一篇文档的同一页码只允许一条 (重跑幂等)
            CONSTRAINT uq_kpt_knowledge_page UNIQUE (knowledge_id, page_number)
        )
        """
    )

    # 候选加载: WHERE blocked = FALSE AND content IS NOT NULL
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kpt_kb_page "
        "ON knowledge_page_transcripts (knowledge_id, page_number)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kpt_blocked "
        "ON knowledge_page_transcripts (blocked)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kpt_source_drive "
        "ON knowledge_page_transcripts (source_drive_file_id)"
    )
    # HNSW: vector_cosine_ops 必须匹配 vector 列类型 (类 20.162)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_kpt_embedding_hnsw
        ON knowledge_page_transcripts USING hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_kpt_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS idx_kpt_source_drive")
    op.execute("DROP INDEX IF EXISTS idx_kpt_blocked")
    op.execute("DROP INDEX IF EXISTS idx_kpt_kb_page")
    op.execute("DROP TABLE IF EXISTS knowledge_page_transcripts")
