"""长期记忆 ORM 模型 —— 补上 `memories` 表缺失的模型层 (2026-11-04 C 档)

## 这张表此前的状态: 孤儿表

- 建表: `alembic/versions/004_add_memory_table.py` (2026-05)，向量维度改 1024 见 `030`
- 现有数据的 `source_session` 全是 `wechat_wwd…` —— **企业微信已于 2026-09-12 整体下线**，
  写入方随之消失
- 全仓对该表的引用只剩 `member_cleanup.py` 的级联清理
- **没有 ORM 模型、没有写入方、没有读取方**
- 而 `app/agent/prompts.py:381` 至今还在告诉模型「下方"长期记忆"section 给出的
  姓名/方向是历史对话里提取的，只作为参考」—— 那段 section 实际并不存在
  (类 20.220 的变体: 提示词在描述一个不存在的注入块)

C 档把这条断链接回来: 本模型 + `conversation_memory_service` (写/召回) +
`_build_system_prompt` 里的注入块，让 prompts.py 的承诺变成真的。

## 为什么不新建表

`memories` 的列已完整覆盖需要 (`user_id / memory_type / key / content / importance /
source_session / is_active / embedding vector(1024)`)。复用它的最大收益是
**零 alembic 迁移** —— 不动迁移链就没有多 head 风险 (类 20.171 / 类 20.219 那一族)，
也不占 revision id 的 32 字符预算 (类 20.227 ③)。

## ⚠️ 库里这张表的实际形态 (2026-11-04 psql 实测，与迁移文件不一致)

`SELECT conname FROM pg_constraint WHERE conrelid='memories'::regclass` → **0 行**：

| 迁移文件说 | 库里实际 |
|---|---|
| `id` 主键 | **无主键** (只有 `nextval('memories_id_seq')` 默认值) |
| `user_id` → FK `members.id` | **无外键** |
| `ix_memories_user_type` / `ix_memories_user_active` | **两个索引都不存在** |
| `created_at/updated_at` 有 `server_default=now()` | **NOT NULL 且无默认值** |

这正是 **类 20.256** 记录的形态 —— 该库由 `pg_dump --data-only` 恢复过，
**数据活着、schema 约束全丢**。两条对代码的直接要求:

1. **`TimestampMixin` 不是装饰**：DB 没有 `server_default`，插入时必须由 ORM 填
   `created_at/updated_at`，否则 `NOT NULL` 直接报错。
2. **本模型故意不声明 `index=True` / `ForeignKey`** —— 写了就是在代码里谎称库里有
   它们 (类 20.220)。索引与主键的补齐应走独立迁移，不在 C 档范围内顺手做。

无主键意味着**唯一性只能靠应用层保证**：episode 记忆以内容 sha256 前 16 位存进
`key` 列，写入前先查该 key 是否已存在 (见 `conversation_memory_service`)。
"""
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from pgvector.sqlalchemy import Vector

from app.core.database import Base
from app.models.base import TimestampMixin


class Memory(Base, TimestampMixin):
    """长期记忆条目。

    `memory_type` 取值 (varchar(20)，新增值务必控制长度):
      - `entity`      成员/项目等实体事实 (企业微信时代遗留)
      - `preference`  用户偏好 (企业微信时代遗留)
      - `episode`     **C 档新增**: 被上下文预算裁掉的历史对话轮次 (只存 user 轮)
    """

    __tablename__ = "memories"

    # 逻辑主键: 库里**没有** PRIMARY KEY 约束，唯一性由 memories_id_seq + 应用层
    # key 去重保证 (见模块 docstring)。
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    memory_type = Column(String(20), nullable=False)
    # episode 类型下存内容 sha256 前 16 位，用于幂等去重
    # (同一条历史被多轮重复裁到时不重复入库)
    key = Column(String(200), nullable=True)
    content = Column(Text, nullable=False)
    importance = Column(Float, nullable=True, default=0.5)
    access_count = Column(Integer, nullable=True, default=0)
    last_accessed_at = Column(DateTime, nullable=True)
    source_session = Column(String(100), nullable=True)
    is_active = Column(Boolean, nullable=True, default=True)
    # 该列是 pgvector 的 vector(1024) (不是 knowledge 表用的 halfvec)
    embedding = Column(Vector(1024), nullable=True)

    def __repr__(self) -> str:
        return "<Memory id=%s user=%s type=%s key=%s>" % (
            self.id, self.user_id, self.memory_type, (self.key or "")[:16])
