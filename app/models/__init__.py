from app.models.member import Member
from app.models.task import Task, TaskDependency
from app.models.meeting import Meeting, MeetingParticipant
from app.models.project import Project, Milestone
from app.models.folder import Folder  # 2026-07-01 课题组网盘
from app.models.knowledge import Knowledge
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
from app.models.meeting_template import MeetingTemplate  # Wave 3b
from app.models.agent_trace import AgentTrace  # 2026-06-12 可观测性
from app.models.search_log import SearchLog  # v31 检索质量埋点
from app.models.chat_history import ChatSession, ChatMessage, ChatShare  # #043 账号持久化

__all__ = [
    "Member",
    "Task",
    "TaskDependency",
    "Meeting",
    "MeetingParticipant",
    "MeetingTemplate",
    "Project",
    "Milestone",
    "Folder",  # 2026-07-01 课题组网盘
    "Knowledge",
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
]
