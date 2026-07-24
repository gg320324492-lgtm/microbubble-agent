from app.models.member import Member
from app.models.task import Task, TaskDependency
from app.models.meeting import Meeting, MeetingParticipant
from app.models.project import Project, Milestone
from app.models.folder import Folder  # 2026-07-01 课题组网盘
from app.models.knowledge import Knowledge, KnowledgeVersion, ChunkedUploadSession, FileMention, ActivityEvent, FileComment  # PR4: 秒传+版本; PR5: 断点续传; PR6: 通知+活动+评论
from app.models.knowledge_entity import KnowledgeEntity, EntityCoOccurrence
from app.models.knowledge_hypothesis import KnowledgeHypothesis
from app.models.knowledge_formula import KnowledgeFormula
from app.models.formula_category import FormulaCategory
from app.models.knowledge_multimodal import KnowledgeImage, KnowledgeExtraction  # Phase 7
from app.models.knowledge_layout import KnowledgeLayout  # Phase 8 vision 看整篇
from app.models.reminder import Reminder
from app.models.memory import Memory
from app.models.feedback import Feedback
from app.models.prompt_template import PromptTemplate
from app.models.voiceprint_history import VoiceprintHistory
from app.models.agent_trace import AgentTrace  # 2026-06-12 可观测性
from app.models.search_log import SearchLog  # v31 检索质量埋点
from app.models.chat_history import ChatSession, ChatMessage, ChatShare  # #043 账号持久化
from app.models.drive_share import DriveFolderShare, DriveFolderMember  # v2 PR7 文件夹分享/成员
from app.models.drive_comment import DriveComment  # v2 PR9 评论 thread
from app.models.drive_file_version import DriveFileVersion  # v2 PR9 文件版本历史
from app.models.drive_version_tag import DriveVersionTag  # v2 PR15 文件版本标签 (W68 第 12 批 B-2)
from app.models.push_subscription import PushSubscription, PushTopic, PushTopicSubscription  # v3.2 PWA Push
from app.models.team_folder import TeamFolder, TeamFolderAuditLog  # v2 PR18 团队共享盘 + 4 维审计 (W68 第 14 批 B-2)

__all__ = [
    "Member",
    "Task",
    "TaskDependency",
    "Meeting",
    "MeetingParticipant",
    # 2026-07-03 模板管理删除 — MeetingTemplate 已下架 (模型 + endpoint + service + alembic 016+038 全部清空)
    "Project",
    "Milestone",
    "Folder",  # 2026-07-01 课题组网盘
    "Knowledge",
    "KnowledgeVersion",  # PR4: 秒传 + 版本历史
    "ChunkedUploadSession",  # PR5: 分片断点续传 session
    "FileMention",           # PR6: @ 提醒
    "ActivityEvent",         # PR6: 活动动态流
    "FileComment",           # PR6: 文件评论
    "Reminder",
    "Memory",
    "Feedback",
    "PromptTemplate",
    "VoiceprintHistory",
    "AgentTrace",
    "KnowledgeImage",       # Phase 7 多模态
    "KnowledgeExtraction",  # Phase 7 多模态
    "KnowledgeLayout",      # Phase 8 vision 看整篇
    "SearchLog",             # v31 检索质量埋点
    "ChatSession",           # #043 账号持久化
    "ChatMessage",           # #043 账号持久化
    "ChatShare",             # #043 账号持久化
    "DriveFolderShare",      # v2 PR7 文件夹公开分享
    "DriveFolderMember",     # v2 PR7 文件夹邀请成员
    "DriveComment",          # v2 PR9 评论 thread
    "DriveFileVersion",      # v2 PR9 文件版本历史
    "DriveVersionTag",       # v2 PR15 文件版本标签 (W68 第 12 批 B-2)
    "PushSubscription",      # v3.2 PWA 推送订阅
    "PushTopic",             # v3.2 PWA 推送主题
    "PushTopicSubscription", # v3.2 PWA 推送主题订阅
    "TeamFolder",            # v2 PR18 团队共享盘 (W68 第 14 批 B-2)
    "TeamFolderAuditLog",    # v2 PR18 4 维审计日志 (W68 第 14 批 B-2)
]   # noqa