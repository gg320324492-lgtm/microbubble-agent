# Drive v2 PR13 combined notifications

Mention and emoji reactions on the same comment use one HIGH `comment_combined` push. Actions are canonicalized (deduplicated and sorted) before SHA-256 hashing; `(user_id, comment_id, actions_hash)` is persisted with a seven-day retention window. The 068 migration follows `067_drive_reactions`; deploy with `alembic upgrade head` and restart app/worker. The dedup insert uses PostgreSQL `ON CONFLICT DO NOTHING`, so concurrent retries cannot duplicate a notification.
