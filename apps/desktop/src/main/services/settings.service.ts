// 设置服务 — key-value 存储，支持全局（user_id=''）与按用户隔离两个作用域。
// 值统一 JSON 序列化落 TEXT 列。
import type { SqlDatabase } from '../db/adapters'

export class SettingsService {
  constructor(private readonly db: SqlDatabase) {}

  get(key: string, userId: string | null = null): unknown {
    const row = this.db
      .prepare('SELECT value FROM settings WHERE user_id = ? AND key = ?')
      .get(userId ?? '', key) as { value: string } | undefined
    if (!row) return null
    try {
      return JSON.parse(row.value)
    } catch {
      return null
    }
  }

  set(key: string, value: unknown, userId: string | null = null): void {
    this.db
      .prepare(
        `INSERT INTO settings (user_id, key, value, updated_at) VALUES (?, ?, ?, ?)
         ON CONFLICT (user_id, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at`
      )
      .run(userId ?? '', key, JSON.stringify(value ?? null), Date.now())
  }
}
