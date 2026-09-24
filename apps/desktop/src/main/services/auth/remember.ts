// DL-2：记住账号密码 —— 载荷编解码（纯函数，可离线测）
//
// 凭据落盘形态：settings['auth.remembered'] = cipher.encrypt(JSON.stringify(RememberPayload))
//   · cipher 由 safeStorage（Windows DPAPI）驱动，**加密不可用时返回空串** → 绝不落明文
//   · 解密失败（换机 / 系统凭据变更）→ 视为「未记住」，登录窗保持空表单
//
// 本模块只管「载荷的形状与校验」，不碰加密与存储 —— 故可纯离线测。

export interface RememberPayload {
  username: string
  password: string
}

/** 构造载荷；用户名空则不构成有效载荷（返回 null，调用方应清除记录） */
export function buildRememberPayload(input: { username?: string; password?: string }): RememberPayload | null {
  const username = String(input?.username ?? '').trim()
  if (!username) return null
  return { username, password: String(input?.password ?? '') }
}

/** 序列化（供加密前使用） */
export function serializeRemember(payload: RememberPayload): string {
  return JSON.stringify(payload)
}

/**
 * 解析已解密的明文。
 * 畸形（非 JSON / 缺 username / 类型不对）→ null，调用方按「未记住」处理。
 */
export function parseRemember(plain: string | null | undefined): RememberPayload | null {
  if (!plain) return null
  try {
    const o = JSON.parse(plain) as Record<string, unknown>
    if (!o || typeof o !== 'object') return null
    if (typeof o.username !== 'string' || !o.username.trim()) return null
    return { username: o.username, password: typeof o.password === 'string' ? o.password : '' }
  } catch {
    return null
  }
}

/**
 * 是否应当保存本次凭据。
 * 规则：勾选记住 **且** 载荷有效 **且** 加密成功（encrypted 非空）才保存。
 * ★ 任何一环不满足 → 返回 false，调用方**清除**既有记录（不残留旧凭据）。
 */
export function shouldPersistRemember(input: {
  remember: boolean
  payload: RememberPayload | null
  encrypted: string | null
}): boolean {
  if (!input.remember) return false
  if (!input.payload) return false
  if (!input.encrypted) return false // 加密不可用 → 不落明文
  return true
}

/**
 * 退出登录时是否应清除。
 * 按工单要求：**退出登录即清除**（下次登录窗不预填）。
 */
export function shouldClearOnLogout(): boolean {
  return true
}
