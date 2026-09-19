// 更新 feed 配置解析（M6-1 整改）— 纯函数，零 Electron / 零 electron-updater 依赖，离线可测。
//
// 存在意义（M6-1 打回根因）：装配期"是否有 feed 覆盖 / 是否放行未打包环境"这一决策，
// 必须由服务层与适配层共用同一事实来源。此前装配漏传 forceDev，导致
//   服务层 envSupported = true（放行）而适配层 forceDevUpdateConfig = false（闸门关闭）
// 自相矛盾：electron-updater 的 isUpdaterActive() 在未打包环境返回 false，
// checkForUpdates() 直接 return null 且不发任何请求，UI 误报「已是最新版本」。
import { ENV_UPDATE_FEED, ENV_UPDATE_FEED_PROVIDER, UPDATE_FEED_BASE } from '@shared/constants'

export interface UpdateFeedConfig {
  /** feed 覆盖地址（环境变量 MNB_UPDATE_FEED），未设置或纯空白为 null */
  feedUrl: string | null
  /** 是否放行未打包环境（映射 electron-updater 的 forceDevUpdateConfig） */
  forceDev: boolean
}

export interface UpdateEnvInput {
  env: Record<string, string | undefined>
  isPackaged: boolean
}

/** 解析 feed 覆盖配置。有 feed 即必须放行未打包环境，否则检查会被静默跳过。 */
export function resolveUpdateFeedConfig(input: UpdateEnvInput): UpdateFeedConfig {
  const raw = input.env[ENV_UPDATE_FEED]
  const feedUrl = typeof raw === 'string' && raw.trim() ? raw.trim() : null
  return { feedUrl, forceDev: feedUrl !== null }
}

/**
 * 更新通道在该环境下是否可用。
 * 打包版恒可用；未打包时必须显式提供 feed 覆盖（否则 electron-updater 拒绝运行）。
 */
export function isUpdateChannelAvailable(input: UpdateEnvInput): boolean {
  return input.isPackaged || resolveUpdateFeedConfig(input).feedUrl !== null
}

/**
 * 适配层最终写入 autoUpdater.forceDevUpdateConfig 的值。
 * 单独抽出以便离线断言"装配 → 适配层"这条链，避免再次出现只改一侧的接线断裂。
 */
export function resolveForceDevUpdateConfig(options: { feedUrl: string | null; forceDev?: boolean }): boolean {
  return Boolean(options.forceDev && options.feedUrl)
}

// ============================================================
// R-8：生效 feed 解析（默认 OSS generic，GitHub 保留为可配置回退）
// ============================================================

/** feed 来源：env 覆盖 / 默认 OSS / GitHub 回退 */
export type UpdateFeedSource = 'env' | 'oss' | 'github'

export interface EffectiveUpdateFeed {
  /** 最终 feed 地址；null 表示交给 GitHub provider（回退路径） */
  url: string | null
  source: UpdateFeedSource
}

/** feed 地址归一化：去空白、补末位斜杠（electron-updater generic 要求目录形式） */
export function normalizeFeedUrl(raw: string): string {
  const t = String(raw ?? '').trim()
  if (!t) return ''
  return t.endsWith('/') ? t : `${t}/`
}

/**
 * 解析"实际生效"的 feed。
 * 优先级（高 → 低）：
 *   ① MNB_UPDATE_FEED 显式覆盖（M6-1 测试缝隙；本地联调/定向验证用）
 *   ② MNB_UPDATE_FEED_PROVIDER=github → 回退 GitHub provider（应急开关）
 *   ③ 默认：OSS generic（国内直连，R-8 起为常规路径）
 *
 * 注意与 resolveUpdateFeedConfig 的分工：后者只回答"有没有显式覆盖"（供 forceDev 判定，
 * 语义保持 M6-1 不变），本函数回答"最终打到哪个地址"。拆开是为了不动既有契约。
 */
export function resolveEffectiveUpdateFeed(input: UpdateEnvInput): EffectiveUpdateFeed {
  const override = resolveUpdateFeedConfig(input).feedUrl
  if (override) return { url: normalizeFeedUrl(override), source: 'env' }

  const provider = String(input.env[ENV_UPDATE_FEED_PROVIDER] ?? '')
    .trim()
    .toLowerCase()
  if (provider === 'github') return { url: null, source: 'github' }

  return { url: UPDATE_FEED_BASE, source: 'oss' }
}

/**
 * 是否放开预发布版本（R-8 起 stable 频道不再需要）。
 * 仅当**当前应用版本本身**带预发布后缀（如 1.0.1-beta.1）时才放开——既保留回退能力，
 * 又让正式版（1.0.1）不会被 alpha/beta 误拉走。v0.1.x-alpha 时期恒为 true，行为不变。
 */
export function resolveAllowPrerelease(appVersion: string): boolean {
  return /-[0-9A-Za-z]/.test(String(appVersion ?? ''))
}
