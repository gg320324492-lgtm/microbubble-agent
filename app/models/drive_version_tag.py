"""Drive v2 PR15 — 文件版本标签 (Version Tags) ORM 模型 (2026-07-24)

设计背景:
- Drive v2 PR9 文件版本历史 (commit 21a1906a8) 已实现 version_number 自动递增
- **Drive v2 PR15**: 文件版本标签 (semantic tag, 给特定版本打标签)
  - 12 个内置白名单: release / stable / deprecated / security / auto-save / manual /
    breaking / experimental / legacy / featured / archived / final
  - 用户可给任何版本打标签, 例如 v3 → 'release-2024.10' 或 'stable' 或 'deprecated'
  - UNIQUE 约束 (version_id, tag_name) — 同一 version 同一 tag 唯一 (幂等 add)
  - WS 推送 tag_added / tag_removed 给 file owner + folder admin (协同通知)
- 锚点范式第 149 守恒 (W68 第 12 批 B-2)

为何 tag 关联到 version_id 而非 file_id:
- 标签是**版本**的属性, 不是文件的属性 (语义上)
- 同一 file_id 不同 version 可有不同 tag (v1=stable, v2=deprecated, v3=experimental)
- 例如: v1.0 stable → v1.1 deprecated → v2.0 release — 标签随版本切换
- 跨文件: 用户可按 tag_name 反查所有文件的' release' 标签 (e.g. "本周发布的所有版本")

字段设计 (与 GitHub release tags 的差异):
- GitHub release: tag_name (string) + target_commitish + name + body + draft + prerelease
- 本项目: 12 个白名单 (短命名 + 语义化) + tag_description (text) + color (16 进制)
- 不冗余 release date (Knowledge.created_at + DriveFileVersion.created_at 已够)
- 不冗余 draft/prerelease (业务上 version tags 概念不重叠)

调用方 (service / API):
- drive_version_tag_service.add_tag(version_id, tag_name, description, color, member_id) → DriveVersionTag (幂等)
- drive_version_tag_service.remove_tag(version_id, tag_name, member_id) → bool
- drive_version_tag_service.list_tags(version_id) → List[DriveVersionTag]
- drive_version_tag_service.list_tags_by_file(file_id) → {version_id → List[tag]}
- drive_version_tag_service.get_file_by_tag(file_id, tag_name) → Optional[DriveFileVersion]

权限模型:
- add_tag: 文件创建人 OR folder 管理员 OR 平台管理员 (与 upload_new_version 一致)
- remove_tag: 创建人 (member_id == current_user.id) — admin 不 override (类似 reaction)
- list_tags: 文件可见者 (与 list_versions 一致)
- get_file_by_tag: 文件可见者

内置 tag 白名单 (12 个):
- 'release' 正式发布版 / 'stable' 稳定版 / 'deprecated' 已废弃
- 'security' 安全更新 / 'auto-save' 自动保存 / 'manual' 手动存档
- 'breaking' 破坏性变更 / 'experimental' 实验性 / 'legacy' 遗留兼容
- 'featured' 推荐版本 / 'archived' 已归档 / 'final' 最终版

注意:
- tag_name 列 VARCHAR(64) — 容纳白名单 + 用户自定义 (e.g. "release-2024.10")
  * 12 个内置白名单最长 'release-2024.10' 约 16 字符
  * 用户自定义如 'reviewed-by-prof-wang' (21 字符) 也可
- UNIQUE 约束 (version_id, tag_name) — 同一 version 同一 tag 幂等 (重复 add 直接 IntegrityError 吞掉返 None)
- version_id ON DELETE CASCADE — 删 DriveFileVersion → 关联 tags 全清
- member_id (created_by) ON DELETE RESTRICT — 用户注销不允许有悬挂 tag
- color VARCHAR(16) — 16 进制 hex e.g. '#FF7A5C' (主色) / '#FFB347' (accent) / '#909399' (灰)
- 不在 DB 层强制 tag_name 白名单 (业务层 service + schema 双重校验)
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
from typing import List, Optional

from app.core.database import Base
from app.models.base import TimestampMixin


# ==========================================================================
# 内置 Tag 白名单 (12 个)
# ==========================================================================
# 设计: 与 GitHub release tags 对齐 + 课题组场景补充 (auto-save / manual / featured / final)
# 落地: Pydantic schema + service add_tag 双重校验
ALLOWED_TAG_NAMES: frozenset[str] = frozenset({
    "release",        # 正式发布版
    "stable",         # 稳定版
    "deprecated",     # 已废弃
    "security",       # 安全更新
    "auto-save",      # 自动保存
    "manual",         # 手动存档
    "breaking",       # 破坏性变更
    "experimental",   # 实验性
    "legacy",         # 遗留兼容
    "featured",       # 推荐版本
    "archived",       # 已归档
    "final",          # 最终版
})


# 默认色 (NULL 时 fallback) — 与项目设计令牌对齐 (CSS 变量 --color-primary / --color-accent)
DEFAULT_TAG_COLOR: str = "#FF7A5C"  # 珊瑚橙 (主色)


class DriveVersionTag(Base, TimestampMixin):
    """Drive v2 PR15 — 文件版本标签 (Version Tag)

    关系:
    - N:1 with DriveFileVersion (version_id FK, ON DELETE CASCADE)
      * 标签是版本的属性, 同一 file_id 不同 version 可有不同 tag
    - N:1 with Member (created_by FK, ON DELETE RESTRICT)
      * 标签创建者审计

    使用方式 (DriveVersionTagService):
    - add_tag(version_id, tag_name, description, color, member_id):
      * 校验 tag_name 在白名单 (或长度 ≤ 64)
      * 校验 version 存在 + 用户有 modify 权限
      * INSERT (UNIQUE 约束保证幂等 — 重复 add 直接 IntegrityError 吞掉返 None)
    - remove_tag(version_id, tag_name, member_id):
      * 校验当前用户是 tag 创建者 (admin 不 override)
      * DELETE WHERE (version_id=?, tag_name=?)
    - list_tags(version_id):
      * SELECT * WHERE version_id=? ORDER BY created_at desc
    - list_tags_by_file(file_id):
      * JOIN drive_file_versions WHERE file_id=? 拿 version_id → tags 聚合
    - get_file_by_tag(file_id, tag_name):
      * JOIN drive_file_versions WHERE file_id=? AND tag_name=? 拿首个版本
    """
    __tablename__ = "drive_version_tags"

    id = Column(Integer, primary_key=True, index=True)

    # === 版本关联 ===
    version_id = Column(
        Integer,
        ForeignKey("drive_file_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="DriveFileVersion.id — 标签关联的具体版本 (FK ON DELETE CASCADE)",
    )

    # === 标签 ===
    tag_name = Column(
        String(64),
        nullable=False,
        comment="标签名称 (12 个内置白名单 + 用户自定义, 长度 ≤ 64)",
    )
    tag_description = Column(
        Text,
        nullable=True,
        comment="标签描述 (用户输入, 可选, e.g. '2024 年 10 月发布版 - 论文终稿')",
    )
    color = Column(
        String(16),
        nullable=True,
        comment="标签颜色 (16 进制 hex e.g. '#FF7A5C', NULL 用默认色 #FF7A5C 珊瑚橙)",
    )

    # === 创建者 ===
    created_by = Column(
        Integer,
        ForeignKey("members.id", ondelete="RESTRICT"),
        nullable=False,
        comment="标签创建者 member.id (RESTRICT: 用户注销需先清其创建的 tags)",
    )

    # === 关系 ===
    version = relationship("DriveFileVersion", foreign_keys=[version_id])
    creator = relationship("Member", foreign_keys=[created_by])

    # === 索引 + 约束 ===
    __table_args__ = (
        # UNIQUE: 同一 version 同一 tag 唯一 (幂等 add)
        UniqueConstraint(
            "version_id", "tag_name",
            name="uq_drive_version_tags_version_tag",
        ),
        # 索引: version_id 单列 — list_tags_by_version 高频
        Index(
            "ix_drive_version_tags_version",
            "version_id",
            unique=False,
        ),
        # 索引: tag_name 单列 — get_file_by_tag 跨文件反查高频
        Index(
            "ix_drive_version_tags_tag_name",
            "tag_name",
            unique=False,
        ),
        # 索引: created_by 单列 — 按标签创建者查询 (审计)
        Index(
            "ix_drive_version_tags_created_by",
            "created_by",
            unique=False,
        ),
    )

    def __repr__(self):
        return (
            f"<DriveVersionTag(id={self.id}, version_id={self.version_id}, "
            f"tag='{self.tag_name}', color='{self.color}')>"
        )

    @property
    def display_color(self) -> str:
        """UI 渲染用颜色 (NULL 时 fallback 默认色)"""
        return self.color if self.color else DEFAULT_TAG_COLOR


__all__ = [
    "DriveVersionTag",
    "ALLOWED_TAG_NAMES",
    "DEFAULT_TAG_COLOR",
]