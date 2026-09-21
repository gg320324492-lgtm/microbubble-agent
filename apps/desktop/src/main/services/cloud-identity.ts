// 统一登录：云端身份 ↔ 本地数据归属的认领决策（工单 M2-3a+ §2）— 纯函数，零依赖。
//
// 背景：此前「本地账号 + 手动绑定」两套身份。改造后父级账号即登录身份，
// 本机既有数据（挂在旧本地账号名下）需要在**首次**云端登录时**认领**到该身份名下，不丢失。
//
// 关键约束（工单硬要求）：
//   · 认领**一次性**完成（重复登录不得重复认领、不得抢别人的数据）
//   · **多云端账号同机登录按账号隔离**（A 认领过的数据，B 登录时不得拿走）
//   · 本地 users 行**保留**（向前兼容），仅新增「云端身份映射」列
//
// 数据模型：users 行 = 「云端账号缓存」
//   cloud_user_id 有值 → 该行代表某个云端身份在本机的缓存
//   cloud_user_id 为 NULL → 旧的本地账号行（其名下数据是「无主数据」，可被认领）
//
// 为「零感托管备份」（通道 A · 服务器 API 直传）预留：映射以 cloud_user_id 为主键口径，
// 后续托管密钥/组织配置按同一口径存取（本单不实现托管本身）。

export interface CloudIdentity {
  /** 父级账号 id（字符串化，来自 /api/v1/auth/me 的 id） */
  cloudUserId: string
  /** 父级用户名（用于展示与排查） */
  cloudUsername: string
}

export interface LocalUserRow {
  id: string
  username: string
  /** 已有的云端映射（NULL = 旧本地账号） */
  cloudUserId: string | null
}

export interface ClaimPlan {
  /** 需要复用已有缓存行（返回其 local id）；为 null 表示需要新建 */
  reuseLocalUserId: string | null
  /** 需要新建缓存行时给出建议 username（与云端同名，冲突时加后缀） */
  createUsername: string | null
  /** 需要把数据认领过来的旧本地账号 id 列表（仅首次认领时非空） */
  orphanUserIds: string[]
  /** 是否本次为「首次认领」（决定要不要写 claimed_at 与提示用户） */
  firstClaim: boolean
}

/** 生成不冲突的本地用户名（与云端同名优先，冲突加 -2 / -3 …） */
export function pickLocalUsername(desired: string, taken: readonly string[]): string {
  const base = desired.trim() || 'cloud-user'
  if (!taken.includes(base)) return base
  for (let i = 2; i < 1000; i += 1) {
    const candidate = `${base}-${i}`
    if (!taken.includes(candidate)) return candidate
  }
  return `${base}-${Date.now()}`
}

/**
 * 决策：该云端身份本次登录要做什么（纯函数）。
 *
 * 分支：
 *   1. 已有 `cloud_user_id === 本身份` 的行 → **复用，不认领**（一次性；多账号隔离）
 *   2. 没有该身份的行，但**存在无主旧账号行**（cloudUserId=null）→ 新建缓存行 + **认领这些旧账号的数据**
 *   3. 没有该身份的行，且**无任何无主行**（例如第二台机器/全新安装）→ 新建缓存行，不认领
 *
 * 注意：分支 2 只认领 `cloudUserId === null` 的行；**已被别的云端账号认领过的行绝不参与**
 * （多账号隔离的硬保证）。
 */
export function planClaim(identity: CloudIdentity, localUsers: readonly LocalUserRow[]): ClaimPlan {
  const cloudId = String(identity.cloudUserId)

  // 1) 本身份的缓存行已存在 → 复用，零认领
  const existing = localUsers.find((u) => u.cloudUserId === cloudId)
  if (existing) {
    return { reuseLocalUserId: existing.id, createUsername: null, orphanUserIds: [], firstClaim: false }
  }

  // 2) 新建缓存行；无主行 = cloudUserId 为 null 的旧本地账号
  const taken = localUsers.map((u) => u.username)
  const orphanUserIds = localUsers.filter((u) => u.cloudUserId === null).map((u) => u.id)
  return {
    reuseLocalUserId: null,
    createUsername: pickLocalUsername(identity.cloudUsername, taken),
    orphanUserIds,
    firstClaim: true
  }
}

/** 认领后给用户看的一句话（中性、含条数；不含任何文档内容） */
export function claimSummary(claimedCounts: Record<string, number>): string {
  const total = Object.values(claimedCounts).reduce((a, b) => a + b, 0)
  if (total === 0) return '已接入云端账号，本机无历史数据需要认领。'
  const parts = Object.entries(claimedCounts)
    .filter(([, n]) => n > 0)
    .map(([label, n]) => `${label} ${n} 条`)
    .join('、')
  return `已接入云端账号，并认领本机历史数据：${parts}。`
}

/**
 * 可被认领的数据表（表名 → 展示标签）。
 * 这些表都按 `user_id` 归属，认领即把 user_id 从旧本地账号改为云端缓存行。
 */
export const CLAIMABLE_TABLES: readonly { table: string; label: string }[] = [
  { table: 'chat_sessions', label: '会话' },
  { table: 'knowledge_documents', label: '知识' },
  { table: 'meetings', label: '会议' },
  { table: 'manuscripts', label: '稿件' },
  { table: 'experiments', label: '实验' }
]
