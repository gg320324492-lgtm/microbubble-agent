// 更新适配层（M6-1）— 全仓库**唯一** import electron-updater 的位置。
//
// 隔离理由：electron-updater 依赖 Electron 运行时（electron 模块、app 路径、NSIS 产物），
// 无法在 node 测试环境加载。主进程服务（update.service）只依赖注入的 UpdaterPort，
// 状态机与版本比较是纯函数，因此整条更新链路可以完全离线单测。
//
// feed 注入方案（报告 §7）：不使用 dev-app-update.yml —— 运行时 setFeedURL 同时覆盖
// 「已打包」与「未打包（配合 forceDevUpdateConfig）」两种场景，且便于真机联调时把 feed
// 指向本地静态服务（MNB_UPDATE_FEED），无需改动打包配置。
import { autoUpdater } from 'electron-updater'
import { ENV_UPDATE_FEED } from '@shared/constants'
import { resolveForceDevUpdateConfig } from './feed-config'
import type { UpdaterPort } from './update.service'

/** 更新源 — GitHub Releases（公开仓库，匿名可读） */
export const UPDATE_OWNER = 'gg320324492-lgtm'
export const UPDATE_REPO = 'microbubble-agent'

export { ENV_UPDATE_FEED }

export interface UpdaterAdapterOptions {
  owner?: string
  repo?: string
  /** 显式 feed 覆盖（本地伪造 feed / 联调）；为空则用 GitHub provider */
  feedUrl?: string | null
  /** 未打包环境是否允许检查（配合 feedUrl 使用；生产恒为 false） */
  forceDev?: boolean
  log?: (message: string) => void
}

/**
 * 装配真实 electron-updater 端口。
 * 提示式更新基线：autoDownload / autoInstallOnAppQuit 一律关闭 —— 任何下载与安装动作
 * 都必须由用户在设置页显式触发。
 */
export function createElectronUpdaterPort(options: UpdaterAdapterOptions = {}): UpdaterPort {
  const owner = options.owner ?? UPDATE_OWNER
  const repo = options.repo ?? UPDATE_REPO
  const feedUrl = options.feedUrl?.trim() || null

  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = false
  // 全部版本都是 prerelease（v0.1.x-alpha），不放开该开关会永远"无更新"
  autoUpdater.allowPrerelease = true
  // 未打包环境必须显式放行，否则 isUpdaterActive() 为 false → 检查被整体跳过（M6-1 打回缺陷）
  autoUpdater.forceDevUpdateConfig = resolveForceDevUpdateConfig({ feedUrl, forceDev: options.forceDev })

  if (feedUrl) {
    autoUpdater.setFeedURL(feedUrl)
  } else {
    autoUpdater.setFeedURL({ provider: 'github', owner, repo })
  }

  const log = options.log ?? ((): void => undefined)
  autoUpdater.logger = {
    info: (m?: unknown) => log(`[updater] ${String(m ?? '')}`),
    warn: (m?: unknown) => log(`[updater][warn] ${String(m ?? '')}`),
    error: (m?: unknown) => log(`[updater][error] ${String(m ?? '')}`),
    debug: (m: string) => log(`[updater][debug] ${m}`)
  }

  return {
    checkForUpdates: async () => {
      // 先判闸门：electron-updater 在 isUpdaterActive() 为 false 时会直接返回 null 且**不发任何请求**，
      // 与"确实没有新版本"无法区分。此处显式上报 skipped，交由服务层如实标记为环境不可用，
      // 避免 UI 把"检查被跳过"伪装成"已是最新版本"。
      if (!autoUpdater.isUpdaterActive()) {
        log('[updater][warn] 更新检查被跳过：未打包环境且未放行 dev 更新配置')
        return { skipped: true }
      }
      // 事件与返回值双通道取版本号：部分 provider 在"无更新"时不返回结果对象
      const captured: { version: string | null } = { version: null }
      const onAvailable = (info: { version?: string }): void => {
        captured.version = info?.version ?? null
      }
      autoUpdater.on('update-available', onAvailable)
      try {
        const res = await autoUpdater.checkForUpdates()
        const fromResult = res?.isUpdateAvailable ? (res.updateInfo?.version ?? null) : null
        const version = captured.version ?? fromResult
        return version ? { version } : null
      } finally {
        autoUpdater.removeListener('update-available', onAvailable)
      }
    },
    downloadUpdate: async () => {
      await autoUpdater.downloadUpdate()
    },
    quitAndInstall: () => {
      // isSilent=true：应用内已完成二次确认，安装过程静默执行，避免更新时再弹一次安装向导
      // （oneClick:false 的引导式安装器会停在目录/完成页等待点击，与"安装并重启"语义不符）
      // isForceRunAfter=true：装完自动拉起应用
      autoUpdater.quitAndInstall(true, true)
    },
    onProgress: (cb) => {
      autoUpdater.on('download-progress', (info: { percent?: number }) => cb(Number(info?.percent ?? 0)))
    },
    onDownloaded: (cb) => {
      autoUpdater.on('update-downloaded', () => cb())
    }
  }
}
