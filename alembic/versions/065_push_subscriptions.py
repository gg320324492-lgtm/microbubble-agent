"""v3.2 PWA Push — push_subscriptions / push_topics / push_topic_subscriptions 表 (2026-07-24, W68 第 7 批 B-3)

背景:
- W68 第 5 批 #3 已建前端 `useMobilePushNotification` + `MobilePushPermissionDialog`
- 本 PR 补齐后端: VAPID key 生成 + subscription 持久化 + 推送触发 + 主题订阅
- Web Push 协议 (RFC 8030 + RFC 8291 + RFC 8292) 标准实现
- 1 个用户可订阅多端 (PC + iOS Safari + Android Chrome), 每端 1 行 subscription

设计:
- 3 张新表 (同 migration):
  * push_subscriptions: 浏览器推送订阅 (1 用户多端)
    - endpoint: 推送服务 URL (Mozilla/Google/Apple), UNIQUE 约束
    - p256dh: 客户端 ECDH 公钥 (RFC 8291 加密用)
    - auth: 客户端 ECDH auth secret (16 字节)
    - last_seen_at: 心跳时间 (前端定期 POST 更新)
  * push_topics: 推送主题 (例: 'meeting_reminder' / 'file_mention')
    - name UNIQUE: 业务用字符串标识
  * push_topic_subscriptions: 用户订阅 topic 关系 (M:N)
    - 复合 UNIQUE (subscription_id, topic_id)

依赖: members 表 (FK CASCADE)
下接: 未来 PR 可加 VAPID key 轮换 (本表存 old/new vapid)

回滚策略: 直接 DROP TABLE (按 push_topic_subscriptions → push_subscriptions → push_topics 顺序, FK 兜底)

实施纪律:
- 0 production code 改动铁律 (W68 第 7 批): 本表 + 配套 service/API 全部新增, 不动老路径
- W68 第 3 批串单链纪律: down_revision 接 064_drive_documents (W68 第 5 批 PR10 后续)
- 1:N 关系, endpoint UNIQUE 约束 (1 endpoint 只能 1 行)
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "065_push_subscriptions"
down_revision: Union[str, None] = "064_drive_documents"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # ===== push_subscriptions =====
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="CASCADE"),
            nullable=False,
            comment="Member.id — 订阅者 (1 用户多端: PC + iOS + Android)",
        ),
        sa.Column(
            "endpoint",
            sa.String(length=512),
            nullable=False,
            comment="推送服务 URL (Mozilla/Google/Apple push service, 1 浏览器 1 endpoint)",
        ),
        sa.Column(
            "p256dh",
            sa.String(length=255),
            nullable=False,
            comment="客户端 ECDH 公钥 (base64url, 推 payload 加密用)",
        ),
        sa.Column(
            "auth",
            sa.String(length=64),
            nullable=False,
            comment="客户端 ECDH auth secret (16 字节 base64url, 推 payload 加密用)",
        ),
        sa.Column(
            "user_agent",
            sa.String(length=512),
            nullable=True,
            comment="调试用: 浏览器 + 操作系统 (推送失败排查)",
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(),
            nullable=True,
            comment="心跳时间 (前端定期 POST 更新, 判定订阅失效)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "endpoint", name="uq_push_subscriptions_endpoint",
        ),
    )

    # 索引: (user_id, last_seen_at) 复合 — 按用户查最近活跃端
    op.create_index(
        "ix_push_subscriptions_user_seen",
        "push_subscriptions",
        ["user_id", "last_seen_at"],
        unique=False,
    )

    # ===== push_topics =====
    op.create_table(
        "push_topics",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "name",
            sa.String(length=64),
            nullable=False,
            unique=True,
            comment="topic 唯一字符串 (例: 'meeting_reminder')",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="主题描述 (运维用)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # ===== push_topic_subscriptions (M:N) =====
    op.create_table(
        "push_topic_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("push_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
            comment="PushSubscription.id",
        ),
        sa.Column(
            "topic_id",
            sa.Integer(),
            sa.ForeignKey("push_topics.id", ondelete="CASCADE"),
            nullable=False,
            comment="PushTopic.id",
        ),
        sa.Column(
            "subscribed_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="订阅时间",
        ),
        sa.UniqueConstraint(
            "subscription_id", "topic_id",
            name="uq_push_topic_subscriptions_sub_topic",
        ),
    )

    # 索引: subscription_id 已由 FK 自动创建
    # 索引: topic_id 已由 FK 自动创建
    # 复合 UNIQUE 已由 UniqueConstraint 创建


def downgrade() -> None:
    # 按依赖顺序倒序 drop
    op.drop_table("push_topic_subscriptions")
    op.drop_table("push_topics")

    op.drop_index("ix_push_subscriptions_user_seen", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
