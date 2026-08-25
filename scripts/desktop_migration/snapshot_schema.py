"""Snapshot schema constants and field allow-list.

Each NDJSON record MUST contain: source_type, source_id, source_updated_at.
Password hashes, JWT, refresh tokens, payment keys, wechat secrets, webhook
secrets and voiceprint vectors MUST NOT be selected from the source tables.
"""

from __future__ import annotations

ALLOWED_SOURCE_TYPES = (
    "members", "projects", "milestones", "tasks", "meetings",
    "knowledge", "drive", "chat", "audit",
)

# 必须在所有 SELECT 中排除的字段（这些列不能进入 NDJSON）
FORBIDDEN_FIELDS = frozenset({
    "password_hash", "hashed_password", "password",
    "jwt_token", "refresh_token", "session_token", "api_key",
    "payment_key", "payment_secret", "wechat_secret", "webhook_secret",
    "voice_embedding", "voiceprint_embedding",
})

# 表 → 允许导出的字段（白名单）
TABLE_FIELDS = {
    "members": ("id", "name", "email", "role", "department", "avatar_url", "created_at", "updated_at"),
    "projects": ("id", "name", "description", "owner_id", "status", "start_date", "end_date", "created_at", "updated_at"),
    "milestones": ("id", "project_id", "name", "description", "due_date", "status", "created_at", "updated_at"),
    "tasks": ("id", "project_id", "milestone_id", "title", "description", "status", "priority", "assignee_id", "due_date", "created_at", "updated_at"),
    "meetings": ("id", "title", "agenda", "scheduled_at", "started_at", "ended_at", "created_by", "created_at", "updated_at"),
    "knowledge": ("id", "title", "summary", "category", "tags", "source", "created_at", "updated_at"),
    "drive": ("id", "name", "mime_type", "size", "owner_id", "folder_id", "created_at", "updated_at"),
    "chat": ("id", "user_id", "role", "content", "session_id", "created_at"),
    "audit": ("id", "actor_id", "action", "target_type", "target_id", "metadata", "created_at"),
}


def select_clause(table: str) -> str:
    """Build a SELECT clause using only allowed fields for the given table."""
    if table not in TABLE_FIELDS:
        raise ValueError(f"Unknown table: {table}")
    cols = ", ".join(TABLE_FIELDS[table])
    return f"SELECT {cols} FROM {table}"


def validate_record(table: str, record: dict) -> dict:
    """Strip forbidden fields and inject source_* fields."""
    clean: dict = {}
    for k, v in record.items():
        if k in FORBIDDEN_FIELDS:
            continue
        clean[k] = v
    clean["source_type"] = table
    if "id" not in clean:
        raise ValueError(f"Record for {table} missing id field: {record}")
    clean["source_id"] = clean["id"]
    if "updated_at" in clean:
        clean["source_updated_at"] = clean["updated_at"]
    elif "created_at" in clean:
        clean["source_updated_at"] = clean["created_at"]
    else:
        clean["source_updated_at"] = ""
    return clean
