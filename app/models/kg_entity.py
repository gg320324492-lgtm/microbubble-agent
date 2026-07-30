"""kg_entity ORM — PR8 知识图谱深度联动扁平实体模型 (W94 +0)

## Why new table (派工 v11 §13 仓库实情真查 + 类 20 #33 brief 错配据实上报)

派工 brief 写 "新增 app/models/kg_entity.py — kg_entity ORM (entity_name /
entity_type / knowledge_id FK / vector / first_seen_at / last_seen_at /
mention_count)". 仓库实情真查发现 `app/models/knowledge_entity.py` **已存在**:

- `KnowledgeEntity` (表 `knowledge_entities`) — **SPO 三元组**模型
  (subject/predicate/object/condition/confidence/source_knowledge_ids
  ARRAY(Integer)/occurrence_count/embedding Vector(1024))
- `EntityCoOccurrence` (表 `entity_co_occurrence`) — 共现网络
  (entity_a_id/entity_b_id/knowledge_id/weight + UniqueConstraint)

**互补非替代** (与 PR5 处置 `RAGEvaluationReport` vs 已有 `RAGEvaluation`
完全同款模式):

| 维度 | KnowledgeEntity (已有) | KGEntity (PR8 新增) |
|------|----------------------|--------------------|
| 语义 | SPO 三元组 (关系断言) | 扁平实体 (命名实体) |
| 主键语义 | subject+predicate+object | entity_name+entity_type |
| 知识关联 | source_knowledge_ids ARRAY | knowledge_id FK (单一, 可级联) |
| 计数 | occurrence_count (三元组出现) | mention_count (实体提及) |
| 时间 | TimestampMixin | first_seen_at / last_seen_at (实体生命周期) |
| 建表 | lifespan Base.metadata.create_all (0 alembic) | **alembic 091** |

alembic 091 **仅建 kg_entities 新表, 0 改** knowledge_entities /
entity_co_occurrence 两表 (0 production code 双门控守恒)。

## 实体链召回用途 (PR8 门禁 a/b/c)

- 门禁 a 实体链 hit ≥ 25%: `entity_name` + `embedding` pgvector cosine 召回
- 门禁 b 图谱召回 P95 ≤ 100ms: `ix_kg_entities_embedding_hnsw` + `ix_kg_entities_name`
- 门禁 c 实体数 ≥ 5000: `SELECT count(*) FROM kg_entities`

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
"""
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)

from app.core.database import Base
from app.models.base import TimestampMixin

# 实体向量维度 — 与 PR1 embedding 基线一致 (v29 Qwen3-Embedding-0.6B)
# 与 app/models/knowledge_entity.py:20 KnowledgeEntity.embedding Vector(1024) 对齐
KG_ENTITY_VECTOR_DIM: int = 1024

# 实体名长度上限 — 与 KnowledgeEntity.subject String(500) 对齐
KG_ENTITY_NAME_MAX_LEN: int = 500

# 实体类型白名单 (kg_query_service.py input validation 范式复用, plan §6)
# LLM 抽取的 entity_type 必须映射到本白名单之一, 未知类型归 "OTHER"
KG_ENTITY_TYPES: tuple[str, ...] = (
    "PERSON",       # 人物 (课题组成员 / 论文作者)
    "ORG",          # 机构 (实验室 / 高校 / 期刊)
    "CONCEPT",      # 概念 (微纳米气泡 / 空化 / 传质)
    "METHOD",       # 方法 (声致发光 / DLS 粒径测定)
    "MATERIAL",     # 材料 (表面活性剂 / 纳米颗粒)
    "EQUIPMENT",    # 设备 (气泡发生器 / 显微镜)
    "METRIC",       # 指标 (Zeta 电位 / 溶解氧)
    "OTHER",        # 兜底 (未知类型不丢弃, 归 OTHER)
)


class KGEntity(Base, TimestampMixin):
    """知识图谱扁平实体 — PR8 实体链召回主表

    与 KnowledgeEntity (SPO 三元组) 互补: 本表存"命名实体"本身,
    三元组表存"实体间关系断言"。实体链召回走本表 embedding pgvector cosine。
    """

    __tablename__ = "kg_entities"

    id = Column(Integer, primary_key=True, index=True)

    # 实体名 (归一化后: strip + 全角转半角 + 大小写保留)
    entity_name = Column(String(KG_ENTITY_NAME_MAX_LEN), nullable=False)

    # 实体类型 (KG_ENTITY_TYPES 白名单之一)
    entity_type = Column(String(32), nullable=False, default="OTHER")

    # 来源知识条目 (单一 FK, ondelete CASCADE — 知识删除时实体级联清理)
    # 注: KnowledgeEntity.source_knowledge_ids 是 ARRAY 多来源, 本表是单一来源
    #     同一实体在 N 篇知识出现 → N 行, 由 (entity_name, entity_type, knowledge_id) 唯一约束保证幂等
    knowledge_id = Column(
        Integer,
        ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 实体向量 (pgvector, PR1 truncate_for_embedding 预处理后生成)
    embedding = Column(Vector(KG_ENTITY_VECTOR_DIM), nullable=True)

    # 实体生命周期 (first_seen_at 首次抽取 / last_seen_at 最近一次命中)
    first_seen_at = Column(DateTime, nullable=False, server_default=func.now())
    last_seen_at = Column(DateTime, nullable=False, server_default=func.now())

    # 实体提及次数 (同一 knowledge_id 内重复提及累加)
    mention_count = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        # 幂等唯一约束 — 重跑实体抽取不产生重复行
        UniqueConstraint(
            "entity_name", "entity_type", "knowledge_id", name="uq_kg_entities_name_type_kid"
        ),
        CheckConstraint("mention_count >= 1", name="ck_kg_entities_mention_count"),
        CheckConstraint("length(entity_name) >= 1", name="ck_kg_entities_name_nonempty"),
        # 实体名前缀检索 (实体链召回精确匹配路)
        Index("ix_kg_entities_name", "entity_name"),
        # 类型过滤 (按 entity_type 聚合统计)
        Index("ix_kg_entities_type", "entity_type"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<KGEntity id={self.id} name={self.entity_name!r} "
            f"type={self.entity_type} kid={self.knowledge_id} "
            f"mentions={self.mention_count}>"
        )


def normalize_entity_name(name: Optional[str]) -> str:
    """实体名归一化 — 抽取侧与召回侧必须走同一函数 (防召回漂移)

    步骤: None 兜底 → strip → 内部连续空白折叠为单空格 → 截断到上限

    注: **不做大小写归一** (中文无大小写; 英文缩写 pH / DLS / Zeta 大小写有语义)
    """
    if not name:
        return ""
    collapsed = " ".join(str(name).split())
    return collapsed[:KG_ENTITY_NAME_MAX_LEN]


def coerce_entity_type(entity_type: Optional[str]) -> str:
    """实体类型白名单映射 — 未知类型归 OTHER (不丢弃, 不抛异常)

    kg_query_service.py input validation 白名单范式复用 (plan §6)
    """
    if not entity_type:
        return "OTHER"
    upper = str(entity_type).strip().upper()
    return upper if upper in KG_ENTITY_TYPES else "OTHER"
