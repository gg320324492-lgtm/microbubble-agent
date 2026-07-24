"""Mobile v3.2 PWA Push — Web Push 订阅模型 (2026-07-24, W68 第 7 批 B-3)

设计背景:
- W68 第 5 批 #3 已建前端 `useMobilePushNotification` + `MobilePushPermissionDialog`
- 后端补齐: VAPID key 生成 + subscription 持久化 + 推送触发 + 主题订阅
- Web Push 协议 (RFC 8030 + RFC 8291 + RFC 8292) 标准实现
- 1 个用户可订阅多端 (PC + iOS Safari + Android Chrome), 每端 1 行 subscription

字段设计:
- endpoint: 推送服务的 URL (浏览器拿到的 push service endpoint, 每个浏览器厂家不同)
  * Mozilla: pushes.services.mozilla.com
  * Google: fcm.googleapis.com
  * Apple: push.apple.com (iOS 16.4+)
  * UNIQUE: 用户取消订阅时按 endpoint 定位 + 防止重复插入
- p256dh: 客户端 ECDH 公钥 (base64url, 客户端生成)
- auth: 客户端 ECDH 认证 secret (16 字节, base64url)
- last_seen_at: 心跳时间 (前端可定期 POST 更新, 用于判定订阅失效)
- user_agent: 调试用 (推送失败排查), 含浏览器版本 + 操作系统

主题推送 (push_topics + push_topic_subscriptions):
- 用户可订阅 topic (例: 'meeting_reminder' / 'file_mention' / 'system')
- 推送时按 topic 推给所有订阅者 (broadcast 模式)
- topic 是简单字符串, 不做权限校验 (与 channel/OAuth scope 区别)

调用方:
- 前端 `useMobilePushNotification.subscribe()` → POST /api/v1/push/subscribe
- 后端 `push_service.push_to_user(user_id, title, body, data)` → 浏览器原生通知
- 后端 `push_service.push_to_topic(topic, title, body, data)` → 广播

权限模型:
- 任何登录用户可订阅 / 取消自己订阅
- topic 推送: 由调用方 (notification_service) 决定推送哪个 topic
- 测试推送: admin / leader 角色

注意:
- endpoint 是个人隐私敏感 (PII), 仅 owner + admin 可见
- endpoint 失效 (404/410) 应自动删订阅 (push_service._handle_push_failure)
- p256dh/auth 用于端到端加密 (RFC 8291), 服务端**不**持有私钥
"""
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class PushSubscription(Base, TimestampMixin):
    """Mobile v3.2 PWA Push — 浏览器推送订阅表 (1 用户多端: PC + iOS + Android)

    使用方式:
    - 前端 navigator.serviceWorker.pushManager.subscribe() 获取 subscription
    - POST /api/v1/push/subscribe 存到本表
    - 后端 push_service.push_to_user(user_id) 触发推送
    - 推送 endpoint 失效 (404/410) → 自动删订阅

    关系:
    - N:1 with Member (user_id FK)
    - N:1 with PushTopic (通过 PushTopicSubscription 多对多)
    """
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Member.id — 订阅者 (1 用户多端: PC + iOS + Android)",
    )

    endpoint = Column(
        String(512),
        nullable=False,
        comment="推送服务 URL (Mozilla/Google/Apple push service, 1 浏览器 1 endpoint)",
    )

    p256dh = Column(
        String(255),
        nullable=False,
        comment="客户端 ECDH 公钥 (base64url, 推 payload 加密用)",
    )

    auth = Column(
        String(64),
        nullable=False,
        comment="客户端 ECDH auth secret (16 字节 base64url, 推 payload 加密用)",
    )

    user_agent = Column(
        String(512),
        nullable=True,
        comment="调试用: 浏览器 + 操作系统 (推送失败排查)",
    )

    last_seen_at = Column(
        DateTime,
        nullable=True,
        comment="心跳时间 (前端定期 POST 更新, 判定订阅失效)",
    )

    # 关系
    user = relationship("Member", foreign_keys=[user_id])
    topic_bindings = relationship(
        "PushTopicSubscription",
        back_populates="subscription",
        cascade="all, delete-orphan",
        foreign_keys="PushTopicSubscription.subscription_id",
    )

    # 索引 + 约束
    __table_args__ = (
        # endpoint UNIQUE: 防止同一 endpoint 重复插入 (浏览器 1 端 1 endpoint)
        UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
        # 复合索引: (user_id, last_seen_at) 用于按用户查最近活跃端
        Index("ix_push_subscriptions_user_seen", "user_id", "last_seen_at"),
    )

    def __repr__(self):
        return (
            f"<PushSubscription(id={self.id}, user_id={self.user_id}, "
            f"endpoint={self.endpoint[:60]}..., seen={self.last_seen_at})>"
        )


class PushTopic(Base):
    """Mobile v3.2 PWA Push — 推送主题 (例: 'meeting_reminder' / 'file_mention')

    静态主题: 启动时由代码 seed, 不走 admin UI 创建 (简单可控)
    用户订阅 topic 后, 推送到 topic 时所有订阅者都收到

    注意:
    - name UNIQUE: 业务用字符串作为 topic 标识
    - description: 后台运维看 (前端不展示)
    """
    __tablename__ = "push_topics"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(
        String(64),
        nullable=False,
        unique=True,
        comment="topic 唯一字符串 (例: 'meeting_reminder')",
    )

    description = Column(
        Text,
        nullable=True,
        comment="主题描述 (运维用)",
    )

    # 关系
    subscription_bindings = relationship(
        "PushTopicSubscription",
        back_populates="topic",
        cascade="all, delete-orphan",
        foreign_keys="PushTopicSubscription.topic_id",
    )

    def __repr__(self):
        return f"<PushTopic(id={self.id}, name={self.name})>"


class PushTopicSubscription(Base):
    """Mobile v3.2 PWA Push — 用户订阅 topic 关系 (M:N)

    复合主键 (subscription_id, topic_id) — 1 个 subscription 订阅多个 topic
    """
    __tablename__ = "push_topic_subscriptions"

    id = Column(Integer, primary_key=True, index=True)

    subscription_id = Column(
        Integer,
        ForeignKey("push_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="PushSubscription.id",
    )

    topic_id = Column(
        Integer,
        ForeignKey("push_topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="PushTopic.id",
    )

    subscribed_at = Column(
        DateTime,
        nullable=False,
        comment="订阅时间",
    )

    # 关系
    subscription = relationship(
        "PushSubscription", back_populates="topic_bindings",
        foreign_keys=[subscription_id],
    )
    topic = relationship(
        "PushTopic", back_populates="subscription_bindings",
        foreign_keys=[topic_id],
    )

    # 复合 UNIQUE: 防止同一 (subscription, topic) 重复订阅
    __table_args__ = (
        UniqueConstraint(
            "subscription_id", "topic_id",
            name="uq_push_topic_subscriptions_sub_topic",
        ),
    )

    def __repr__(self):
        return (
            f"<PushTopicSubscription(subscription_id={self.subscription_id}, "
            f"topic_id={self.topic_id})>"
        )
