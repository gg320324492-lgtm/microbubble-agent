"""145: knowledge_page_transcripts 全文检索列 (content_tsvector + GIN) — agent45

**Revision ID**: 145_kpt_content_tsvector
**Revises**: 144_knowledge_page_transcripts
**Create Date**: 2026-10-10

为什么
----
agent44 给整页视觉转写接了**语义路** (``PageTranscriptRetriever.search_pages``,
纯余弦), 但它的严格验收 (``scripts/a44_verify_probe_rank.py``) 暴露一个边界:

    用「只存在于页面转写的罕见拉丁词」(物种名 subgroup 名等) 做探针,
    **0/6 命中 top-5** —— 整页 embedding 把罕见词**稀释**进了整页语义,
    字面页排不进去 (实测 ``air-nanobubble`` 排到第 10, 其余 rank=None)。

现有全站**没有任何**读 ``knowledge_page_transcripts`` 的词法路。该表的正文
**不在**任何既有索引里 (实测 ``knowledge.id=2651`` 的 ``content`` 不含
``air-nanobubble`` —— 那是 pptx, 原生解析拿不到, 只有整页视觉转写有), 所以
单靠既有文本四路 + 语义路都补不上。本迁移加这一列 + GIN, 由本批新写的
``PageTranscriptRetriever.search_pages_lexical`` **当场读取** (不是"建一个没人
读的列" —— 与 ``knowledge.content_tsvector`` 的教训不同, 那条列的读者从未落地)。

为什么用 ``to_tsvector('simple', ...)`` 而不是 jieba
--------------------------------------------------
实测对比 (2061 页候选池, 探针 ground-truth 行):

    probe                          jieba BM25 rank   PG simple tsvector
    acidobacteria_subgroup_6_ge    1   ✓             命中 1 行 ✓
    algoriphagus_aquatilis         1   ✓             命中 1 行 ✓
    anaerotruncus                  1   ✓             命中 1 行 ✓
    alphafold                      1   ✓             命中 1 行 ✓
    air-nanobubble                 **10 ✗**          命中 1 行 ✓

``air-nanobubble`` 是决定性反例: jieba 按 ````-````/````_```` 把整词劈成
``air`` + ``nanobubble``, 而 ``air`` 是高频词, 分数被稀释 → 字面页掉出 top-5。
PG ``simple`` 保留**整个连字符词** ``'air-nanobubble'`` 为独立 lexeme
(实测 ``to_tsvector('simple','air-nanobubble')`` = ``'air':9 'air-nanobubble':8
'nanobubble':10``), 于是罕见词整词命中, 不被高频子串污染。

代价: PG ``simple`` **不切中文** (整个中文串 = 1 token, 实测
``to_tsvector('simple','亚硝化单胞菌 纳米气泡')`` = ``'亚硝化单胞菌':1
'纳米气泡':2``), 所以中文只能**整串命中**。``search_pages_lexical`` 因此配一条
**ILIKE 子串兜底** (实测 ``纳米气泡`` ILIKE 命中 476 行), 由 ILIKE 补中文子串、
tsvector 补罕见拉丁整词。

immutability
------------
``to_tsvector('simple', text)`` 带 regconfig 字面量是 IMMUTABLE, 满足
GENERATED ... STORED 的必要条件 (容器实测 ``CREATE TABLE ... GENERATED
ALWAYS AS (to_tsvector('simple', coalesce(x,''))) STORED`` 成功)。

安全性
------
- 存量 2061 行正文由 PG 在 ``ALTER TABLE`` 时自动回填 (GENERATED STORED),
  不写任何业务行、不动 ``content``。
- GIN 索引名 ``ix_kpt_content_tsvector`` 避开既有 ``ix_kpt_embedding_hnsw``。
- 反向迁移 drop 索引 + drop 列, 完全恢复 144 表形态。
"""

from typing import Sequence, Union

from alembic import op


revision: str = "145_kpt_content_tsvector"
down_revision: Union[str, None] = "144_knowledge_page_transcripts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 幂等守卫 (类 20.220): 列/索引已存在时跳过。
    op.execute(
        """
        ALTER TABLE knowledge_page_transcripts
        ADD COLUMN IF NOT EXISTS content_tsvector tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', coalesce(content, ''))) STORED
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_kpt_content_tsvector "
        "ON knowledge_page_transcripts USING gin (content_tsvector)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_kpt_content_tsvector")
    op.execute(
        "ALTER TABLE knowledge_page_transcripts DROP COLUMN IF EXISTS content_tsvector"
    )
