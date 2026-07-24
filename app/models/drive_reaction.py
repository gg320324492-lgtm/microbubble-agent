"""Drive v2 PR12 — 表情反应 (Emoji Reactions) ORM 模型 (2026-07-24)

设计背景:
- Drive v2 PR9 已实现评论 thread (drive_comments), W68 PR10 实现 mention 提醒
- Drive v2 PR10 实现 CRDT 协同编辑, PR11 实现 path materialized
- **Drive v2 PR12**: 表情反应 (GitHub / GitLab / Slack 风格的轻量反馈)
  - 用户对 comment / file / note 任意一个加 emoji (👍❤️🎉😂😮😢 等)
  - 同一 user 对同一 target 同一 emoji 只能 1 次 (UNIQUE 约束)
  - WS 推送 reaction_added / reaction_removed 给在线协作用户
- 锚点范式第 94 守恒 (W68 第 8 批 B-2)

为何 polymorphic FK:
- 表情反应需支持 comment / file / note 3 类目标
- 用 ENUM + INTEGER 比 3 个 FK 列 + 3 个 nullable 索引更紧凑
- 验证 FK 合法性由 service 层负责 (调对应 service 验证 target 存在 + 权限)
- 删 comment / file → service 显式 CASCADE 清 reactions (避免 FK NULL 污染)

字段设计 (与 GitHub reactions 表的差异):
- GitHub reactions: target_type (Issue/IssueComment/PR/PRReviewComment) + target_id + user_id + content + created_at
  - 本项目: 同样 4 字段 (target_type / target_id / member_id / emoji) + updated_at
- GitHub content: 固定 6 个 emoji (+1/-1/laugh/confused/heart/hooray/rocket/eyes)
  - 本项目: 12 个内置白名单 (更符合中文组群习惯: +1/love/celebrate/laugh/surprise/cry/fire/100/spark/thanks/thinking/think)

调用方 (service / API):
- drive_reaction_service.add_reaction(target_type, target_id, member_id, emoji) → DriveReaction (幂等)
- drive_reaction_service.remove_reaction(target_type, target_id, member_id, emoji) → bool
- drive_reaction_service.list_reactions(target_type, target_id) → {emoji → count + members list}
- drive_reaction_service.list_my_reactions(target_type, target_id, member_id) → emoji list

权限模型:
- add_reaction: 任何能访问 target (read 权限) 都能 add (类似 GitHub)
- remove_reaction: 仅反应者本人 (member_id == current_user.id)
- admin 不 override (类似 comment 的 author 主权)

内置 emoji 白名单 (12 个, 与 GitHub reactions 表对齐 + 中文场景):
- '👍' '+1' / '❤️' 'heart' / '🎉' 'celebrate' / '😂' 'laugh'
- '😮' 'surprise' / '😢' 'cry' / '🔥' 'fire' / '💯' '100'
- '✨' 'spark' / '🙏' 'thanks' / '🤔' 'thinking' / '👀' 'eyes'

注意:
- emoji 列 VARCHAR(16) — 容纳 4 个全宽度 emoji (实际 1-2 为主)
- UNIQUE 约束 (target_type, target_id, member_id, emoji) — 防重复
- member_id ON DELETE CASCADE — 用户注销 → 关联 reactions 全清
- polymorphic FK 故意不在 DB 层强制 (CHECK 约束 + service 层 validate 联合兜底)
  - 理由: comment/file/note 物理表存在性 / soft-delete 状态由 service 统一管
"""
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


# ==========================================================================
# 内置 Emoji 白名单 (12 个)
# ==========================================================================
# 设计: 与 GitHub reactions 对齐 + 中文场景补充 (fire/100/spark/thanks/thinking/eyes)
# 落地: Pydantic schema + service add_reaction 双重校验
ALLOWED_EMOJIS: frozenset[str] = frozenset({
    "👍",  # +1 / thumbs up
    "❤️",  # heart / love
    "🎉",  # celebrate / tada
    "😂",  # laugh / joy
    "😮",  # surprise / open_mouth
    "😢",  # cry
    "🔥",  # fire
    "💯",  # 100
    "✨",  # sparkles
    "🙏",  # thanks / pray
    "🤔",  # thinking
    "👀",  # eyes
})


class DriveReaction(Base, TimestampMixin):
    """Drive v2 PR12 — 表情反应 (Emoji Reaction)

    关系:
    - polymorphic target: (target_type, target_id) → comment / file / note
      * 'comment' → drive_comments.id (CASCADE 删 comment 时 service 显式清 reactions)
      * 'file'    → knowledge.id (CASCADE 删 file 时 service 显式清 reactions)
      * 'note'    → drive_notes.id (未来 PR 引入, 当前 schema 不存在, DB 层 CHECK 仅字符串限制)
    - N:1 with Member (member_id FK, ON DELETE CASCADE)

    使用方式 (DriveReactionService):
    - add_reaction(target_type, target_id, member_id, emoji):
      * 校验 emoji 在白名单
      * 校验 target 存在 + 用户有 read 权限
      * INSERT (UNIQUE 约束保证幂等 — 重复 add 直接 IntegrityError 吞掉返 None)
    - remove_reaction(target_type, target_id, member_id, emoji):
      * DELETE WHERE (member_id=?, emoji=?)
    - list_reactions(target_type, target_id):
      * SELECT * WHERE (target_type=?, target_id=?) GROUP BY emoji
      * 聚合: {emoji: {count, members: [{id, name, avatar_url}]}}
    - list_my_reactions(target_type, target_id, member_id):
      * SELECT emoji WHERE (target_type=?, target_id=?, member_id=?)
      * 返 List[str] emoji 列表
    """
    __tablename__ = "drive_reactions"

    id = Column(Integer, primary_key=True, index=True)

    # === polymorphic target ===
    target_type = Column(
        String(16),
        nullable=False,
        comment="目标类型: 'comment' / 'file' / 'note' (DB CHECK 约束兜底)",
    )
    target_id = Column(
        Integer,
        nullable=False,
        comment="polymorphic target ID (FK 由 service 层验证, 不在 DB 层强制)",
    )

    # === 反应者 ===
    member_id = Column(
        Integer,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="反应者 member.id (NOT NULL, CASCADE: 用户注销 → 反应全清)",
    )

    # === emoji 字面值 ===
    emoji = Column(
        String(16),
        nullable=False,
        comment="emoji 字面值 (Unicode, 12 个内置白名单 — service + schema 双重校验)",
    )

    # === 关系 ===
    member = relationship("Member", foreign_keys=[member_id])

    # === 索引 + 约束 ===
    __table_args__ = (
        # UNIQUE: 同一 user 对同一 target 同一 emoji 不能重复 (toggle 语义)
        UniqueConstraint(
            "target_type", "target_id", "member_id", "emoji",
            name="uq_drive_reactions_target_member_emoji",
        ),
        # CHECK: target_type 白名单 (DB 层兜底, 防未来 schema drift)
        CheckConstraint(
            "target_type IN ('comment', 'file', 'note')",
            name="ck_drive_reactions_target_type",
        ),
        # 索引: (target_type, target_id) — list_reactions 聚合高频
        Index(
            "ix_drive_reactions_target",
            "target_type", "target_id",
            unique=False,
        ),
        # 索引: (member_id) 单列 — list_my_reactions 高频
        Index(
            "ix_drive_reactions_member",
            "member_id",
            unique=False,
        ),
    )

    def __repr__(self):
        return (
            f"<DriveReaction(id={self.id}, {self.target_type}:{self.target_id}, "
            f"member={self.member_id}, emoji='{self.emoji}')>"
        )

    @property
    def target_kind(self) -> str:
        """target_type 别名 (UI 渲染用)"""
        return self.target_type


__all__ = [
    "DriveReaction",
    "ALLOWED_EMOJIS",
]