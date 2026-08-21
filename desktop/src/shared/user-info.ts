// UserInfo Pydantic → TS 直译镜像。
// 来自 app/schemas/auth.py UserInfo (Phase 1-Impl-2 verified)。
//
// 任何字段改动必须先改 docs/desktop-conversion/auth-api-contract.md §3,
// 然后本文件 + 所有引用方同步。

export interface UserInfo {
  id: number
  name: string
  role: string
  grade: string | null
  research_area: string | null
  email: string | null
  phone: string | null
  bio: string | null
  avatar: string | null
  is_active: boolean
}

/**
 * 派生：role 字符串 → 是否管理员。
 * 后端约定 `"admin"` / `"ADMIN"` 都视作 admin，大小写不敏感。
 */
export function isAdminRole(role: string | undefined | null): boolean {
  return typeof role === 'string' && role.toLowerCase() === 'admin'
}
