// 更新 feed 配置解析（M6-1 整改）— 纯函数，零 Electron / 零 electron-updater 依赖，离线可测。
//
// 存在意义（M6-1 打回根因）：装配期"是否有 feed 覆盖 / 是否放行未打包环境"这一决策，
// 必须由服务层与适配层共用同一事实来源。此前装配漏传 forceDev，导致
//   服务层 envSupported = true（放行）而适配层 forceDevUpdateConfig = false（闸门关闭）
// 自相矛盾：electron-updater 的 isUpdaterActive() 在未打包环境返回 false，
// checkForUpdates() 直接 return null 且不发任何请求，UI 误报「已是最新版本」。
import { ENV_UPDATE_FEED } from '@shared/constants'

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
