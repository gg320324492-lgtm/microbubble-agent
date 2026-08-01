"""用户反馈模型"""

from sqlalchemy import Column, BigInteger, Integer, String, Text, ForeignKey
from app.core.database import Base
from app.models.base import TimestampMixin


class Feedback(Base, TimestampMixin):
    """用户对 AI 回复的反馈

    字段说明:
    - id: 主键 (Integer 沿用老 schema, 005 迁移定义)
    - user_id: ForeignKey members.id, 用户销户时 CASCADE 删除
    - session_id: 可选 session 关联 (老字段, 兼容历史会话级反馈)
    - rating: 评分 (1=👍 / -1=👎, W98 CHAT-P1-D3 扩展 1-5 → 简化为 2 档)
    - comment: 用户评语 (Text, 可选)
    - agent_reply: 被评价的 AI 回复内容 (截断 500 字, W98 派工 v3 写入时被实际回复内容填充)
    - message_id: ForeignKey chat_messages.id (W98 CHAT-P1-D3 新加, BigInt FK)
      - 用于按消息聚合反馈与 e2e 跨回复质量回归
      - nullable=True: 旧数据无 message_id; 新前端必填 (ChatViewSSE FeedbackButtons 触发)
      - CASCADE: chat_message 删除时连带清反馈 (与 chat_messages.session_id CASCADE 对齐)
    """
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(String(100))
    rating = Column(Integer, nullable=False)  # 1=👍 / -1=👎 (W98 CHAT-P1-D3 简化)
    comment = Column(Text)  # 用户反馈内容
    agent_reply = Column(Text)  # 被评价的 AI 回复内容（截取前500字）
    # W98 CHAT-P1-D3: message_id 关联具体 AI 回复 (BigInt, FK chat_messages.id)
    message_id = Column(
        BigInteger,
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    def __repr__(self):
        return (
            f"<Feedback(id={self.id}, user_id={self.user_id}, "
            f"rating={self.rating}, message_id={self.message_id})>"
        )
