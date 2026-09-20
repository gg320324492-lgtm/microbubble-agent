// 工具权限三值模型 + 作用域梯度（工单 M8-3 §1/§2）— 纯函数，零 Electron / 零依赖。
//
// 要解决的问题：C-3 时代的确认流是「写操作全局一刀切」—— 无记忆（每次都问）、
// 无作用域（不能「此工作区永久允许」）、无证据（事后说不清某次为何被放行）。
//
// 本模块给出：
//   ① 三值：allow（直接执行）/ ask（弹确认）/ deny（直接拒绝，不走确认）
//   ② 三层作用域：session（内存，本次会话）> workspace（工作区配置）> global（设置键）
//   ③ 判定优先级（安全优先）：
//        · **任一作用域出现 deny → 一律 deny**（deny 是不可被更近作用域 allow 掉的否决权）
//        · 否则取**最近作用域**给出的值（session > workspace > global）
//        · 都没有 → 类别默认值（= 现行为：只读 allow、写类 ask）→ 零行为变更
//
// 对标出处（报告 §7）：模式借鉴 minimax-code 的权限三值 + 作用域记忆思路；
// 本实现为独立编写（本项目无其类型体系），判定优先级与默认值按本项目现行为重写。

/** 权限三值 */
export type PermissionValue = 'allow' | 'ask' | 'deny'
/** 作用域（由近及远） */
export type PermissionScope = 'session' | 'workspace' | 'global'
/** 工具类别（沿用现确认流分组：只读类 = auto、写类 = confirm） */
export type ToolCategory = 'readonly' | 'write'

export const PERMISSION_VALUES: readonly PermissionValue[] = ['allow', 'ask', 'deny']
/** 由近及远的作用域顺序（判定时按此顺序取最近命中） */
export const SCOPE_ORDER: readonly PermissionScope[] = ['session', 'workspace', 'global']

/** 类别默认值 = 现行为（只读直接执行、写操作弹确认）——零行为变更 */
export const DEFAULT_CATEGORY_VALUES: Record<ToolCategory, PermissionValue> = {
  readonly: 'allow',
  write: 'ask'
}

export const TOOL_CATEGORIES: readonly ToolCategory[] = ['readonly', 'write']

export interface PermissionRule {
  category: ToolCategory
  value: PermissionValue
  scope: PermissionScope
  /** 记录时间（证据链用） */
  at: number
}

/** 三层规则存储（缺省 = 该层无规则） */
export interface PermissionStore {
  session: Partial<Record<ToolCategory, PermissionValue>>
  workspace: Partial<Record<ToolCategory, PermissionValue>>
  global: Partial<Record<ToolCategory, PermissionValue>>
}

export const EMPTY_STORE: PermissionStore = { session: {}, workspace: {}, global: {} }

export interface ResolvedPermission {
  value: PermissionValue
  /** 命中来源：'default' 表示三层都无规则，落到类别默认值 */
  scope: PermissionScope | 'default'
  /** 若因 deny 否决而生效，这里给出「否决来自哪个作用域」 */
  deniedBy?: PermissionScope
  /** 是否为类别默认值 */
  isDefault: boolean
}

/** 工具 → 类别（沿用现确认流分组：confirm → write，auto → readonly） */
export function categoryOfPermissionLevel(level: 'auto' | 'confirm'): ToolCategory {
  return level === 'confirm' ? 'write' : 'readonly'
}

/** 归一化存储（非法值/未知键一律丢弃，避免坏配置把权限算歪） */
export function normalizeStore(raw: unknown): PermissionStore {
  const out: PermissionStore = { session: {}, workspace: {}, global: {} }
  const src = (raw ?? {}) as Record<string, unknown>
  for (const scope of SCOPE_ORDER) {
    const layer = src[scope]
    if (!layer || typeof layer !== 'object') continue
    for (const cat of TOOL_CATEGORIES) {
      const v = (layer as Record<string, unknown>)[cat]
      if (typeof v === 'string' && (PERMISSION_VALUES as readonly string[]).includes(v)) {
        out[scope][cat] = v as PermissionValue
      }
    }
  }
  return out
}

/**
 * 判定某类别当前生效的权限值（纯函数）。
 *
 * 优先级（安全优先，两条规则同时满足）：
 *   1. **deny 否决**：任一作用域为 deny → 结果 deny（deniedBy 指出最先命中的作用域）
 *   2. **近覆盖远**：否则按 session > workspace > global 取最近一个有规则的层
 *   3. 三层都无规则 → 类别默认值（现行为）
 */
export function resolvePermission(store: PermissionStore, category: ToolCategory): ResolvedPermission {
  const normalized = normalizeStore(store)

  // 1) deny 否决（按由近及远找「谁否决的」，仅用于证据展示）
  for (const scope of SCOPE_ORDER) {
    if (normalized[scope][category] === 'deny') {
      return { value: 'deny', scope, deniedBy: scope, isDefault: false }
    }
  }

  // 2) 近覆盖远
  for (const scope of SCOPE_ORDER) {
    const v = normalized[scope][category]
    if (v !== undefined) return { value: v, scope, isDefault: false }
  }

  // 3) 类别默认值
  return { value: DEFAULT_CATEGORY_VALUES[category], scope: 'default', isDefault: true }
}

/** 写入一条规则（不可变：返回新 store） */
export function applyRule(
  store: PermissionStore,
  rule: { category: ToolCategory; value: PermissionValue; scope: PermissionScope }
): PermissionStore {
  const normalized = normalizeStore(store)
  return {
    session: { ...normalized.session },
    workspace: { ...normalized.workspace },
    global: { ...normalized.global },
    [rule.scope]: { ...normalized[rule.scope], [rule.category]: rule.value }
  } as PermissionStore
}

/** 清除某作用域某类别的规则（不可变） */
export function clearRule(store: PermissionStore, category: ToolCategory, scope: PermissionScope): PermissionStore {
  const normalized = normalizeStore(store)
  const layer = { ...normalized[scope] }
  delete layer[category]
  return { ...normalized, [scope]: layer }
}

/**
 * 确认弹窗的「记住」选项 → 落库规则。
 * 三选项：仅本次（不落库）/ 此工作区记住 / 全局记住；拒绝侧同理。
 */
export type RememberChoice = 'once' | 'workspace' | 'global'

export function ruleFromChoice(
  category: ToolCategory,
  value: 'allow' | 'deny',
  choice: RememberChoice
): { category: ToolCategory; value: PermissionValue; scope: PermissionScope } | null {
  if (choice === 'once') return null // 仅本次：不落库，只影响当前这次调用
  return { category, value, scope: choice === 'workspace' ? 'workspace' : 'global' }
}

/** 面向用户的中性文案（deny 直接拒绝时回喂给模型） */
export function denyMessage(category: ToolCategory, name: string): string {
  const label = category === 'write' ? '写操作' : '只读操作'
  return `工具 ${name}（${label}）已被当前权限设置禁止执行。如需使用，请在「设置 · 工具权限」中调整，或换一种不需要该工具的方式完成。`
}

/** 权限值的用户可见标签（设置页用） */
export function permissionLabel(value: PermissionValue): string {
  return value === 'allow' ? '允许' : value === 'ask' ? '每次询问' : '禁止'
}

export function scopeLabel(scope: PermissionScope | 'default'): string {
  return scope === 'session' ? '本次会话' : scope === 'workspace' ? '此工作区' : scope === 'global' ? '全局' : '默认'
}
