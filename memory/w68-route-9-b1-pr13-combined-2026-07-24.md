# W68 Route 9 B-1

PR13 establishes combined Drive comment notifications. Five invariants: canonical sorted action lists; SHA-256 action hashes; seven-day dedup retention; exactly one HIGH WS event for a combined action set; and a unique `(user, comment, hash)` database key to make retries safe. Migration 068 is chained after 067.
