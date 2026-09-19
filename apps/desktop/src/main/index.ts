// 主进程入口 — 无边框窗口 + 三铁律安全基线（骨架设计 §5）
import { app, BrowserWindow, shell } from 'electron'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { registerIpc, installDesktopPrimitives, installUpdaterPort } from './ipc'
import { openDatabase } from './db'
import { createElectronUpdaterPort } from './services/update/updater-adapter'
import { resolveEffectiveUpdateFeed, resolveUpdateFeedConfig } from './services/update/feed-config'
import { resolveTrayIcon } from './services/desktop/tray-icon'
import { IPC } from '@shared/ipc-channels'
import { APP_NAME, WINDOW_MIN_HEIGHT, WINDOW_MIN_WIDTH } from '@shared/constants'

let mainWindow: BrowserWindow | null = null

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: WINDOW_MIN_WIDTH,
    minHeight: WINDOW_MIN_HEIGHT,
    title: APP_NAME,
    frame: false, // 无边框 — 自绘标题栏（TitleBar.vue）
    show: false,
    autoHideMenuBar: true,
    // dev 模式窗口/任务栏图标（打包后由 exe 内嵌 icon 提供）
    icon: join(app.getAppPath(), 'resources', 'icon.png'),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true, // 铁律 1
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true
    }
  })

  mainWindow.on('ready-to-show', () => mainWindow?.show())
  // 最大化/还原状态推送给渲染层（标题栏三键图标切换）
  const pushState = (): void => mainWindow?.webContents.send(IPC.WINDOW_STATE_EVENT, mainWindow?.isMaximized() ?? false)
  mainWindow.on('maximize', pushState)
  mainWindow.on('unmaximize', pushState)
  mainWindow.on('closed', () => {
    mainWindow = null
  })

  // 铁律 3 配套 — 禁 renderer 内导航；外链一律走系统浏览器
  mainWindow.webContents.on('will-navigate', (event) => event.preventDefault())
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url)
    return { action: 'deny' }
  })

  // 锁定页面缩放 — 载入完成即复位缩放；拦截 Ctrl +/-/0（触控板/Ctrl+滚轮误触会持久化缩放级别）
  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow?.webContents.setZoomFactor(1)
  })
  mainWindow.webContents.on('before-input-event', (event, input) => {
    if (input.type === 'keyDown' && input.control && ['+', '-', '=', '0'].includes(input.key)) {
      event.preventDefault()
    }
  })

  if (process.env['ELECTRON_RENDERER_URL']) {
    void mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    void mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

// 单实例锁（M4）— 二次启动不产生新实例，聚焦已有窗口
// MNB_USER_DATA：测试/多实例隔离用 userData 覆盖（仅显式设置时生效）
if (process.env['MNB_USER_DATA']) app.setPath('userData', process.env['MNB_USER_DATA'])
const gotTheLock = app.requestSingleInstanceLock()
if (!gotTheLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.show()
      mainWindow.focus()
    }
  })
}

app.whenReady().then(() => {
  const dbPath = join(app.getPath('userData'), 'data', 'workbench.db')
  const db = openDatabase(dbPath)
  installDesktopPrimitives(() => mainWindow)
  // 自动更新适配层装配（M6-1）— 全仓库唯一 import electron-updater 的位置在此装配；
  // 服务层只拿到注入端口，故状态机与版本比较可完全离线单测。
  // feed 覆盖存在时必须同时放行未打包环境（forceDev），否则 electron-updater 会整体跳过检查。
  // R-8：生效 feed 由 resolveEffectiveUpdateFeed 解析——MNB_UPDATE_FEED 覆盖 > 默认 OSS generic
  // > MNB_UPDATE_FEED_PROVIDER=github 回退。forceDev 仍只由显式覆盖驱动（M6-1 语义不变）。
  const feedOverride = resolveUpdateFeedConfig({ env: process.env, isPackaged: app.isPackaged })
  const feed = resolveEffectiveUpdateFeed({ env: process.env, isPackaged: app.isPackaged })
  installUpdaterPort(
    createElectronUpdaterPort({
      feedUrl: feed.url,
      feedSource: feed.source,
      forceDev: feedOverride.forceDev,
      log: (message) => {
        console.log(message)
      }
    })
  )
  const { desktop, update, runExitBackup } = registerIpc(db, dbPath, () => mainWindow)
  createWindow()

  // 托盘常驻 + 关窗行为分流（M4）
  // 图标解析：.ico 优先（多尺寸）、.png 回退；打包态走 process.resourcesPath，
  // 开发态走 app 根目录（见 resolveTrayIcon）
  const trayIcon = resolveTrayIcon({
    resourcesRoot: app.isPackaged ? process.resourcesPath : app.getAppPath(),
    exists: existsSync
  })
  if (trayIcon.missing) console.log('[tray] 图标资源缺失，托盘可能无法显示')
  desktop.setupTray(trayIcon.path)

  // 启动后 5s 后台检查更新（不阻塞启动、失败静默；受「自动检查更新」开关约束）
  update.scheduleAutoCheck()
  let forceQuit = false
  let exitBackupDone = false
  app.on('before-quit', (e) => {
    forceQuit = true
    if (exitBackupDone) return
    // 退出自动备份（M5-2）— 开关关/未登录时立即返回；内部 10s 超时，失败不阻塞退出
    e.preventDefault()
    void runExitBackup()
      .catch(() => null)
      .finally(() => {
        exitBackupDone = true
        app.quit()
      })
  })
  mainWindow!.on('close', (e) => {
    if (forceQuit) return
    if (desktop.handleMainWindowClose() === 'quit') return
    e.preventDefault()
  })

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
