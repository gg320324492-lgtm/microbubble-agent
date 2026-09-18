// 主进程入口 — 无边框窗口 + 三铁律安全基线（骨架设计 §5）
import { app, BrowserWindow, shell } from 'electron'
import { join } from 'node:path'
import { registerIpc, installDesktopPrimitives, installUpdaterPort } from './ipc'
import { openDatabase } from './db'
import { createElectronUpdaterPort } from './services/update/updater-adapter'
import { IPC } from '@shared/ipc-channels'
import { APP_NAME, ENV_UPDATE_FEED, WINDOW_MIN_HEIGHT, WINDOW_MIN_WIDTH } from '@shared/constants'

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
  installUpdaterPort(
    createElectronUpdaterPort({
      feedUrl: process.env[ENV_UPDATE_FEED] ?? null,
      log: (message) => {
        console.log(message)
      }
    })
  )
  const { desktop, update, runExitBackup } = registerIpc(db, dbPath, () => mainWindow)
  createWindow()

  // 托盘常驻 + 关窗行为分流（M4）
  // 打包后 app.getAppPath() 指向 app.asar（内部无 resources/），图标由 extraResources 落在
  // <install>/resources/resources/，故打包态改用 process.resourcesPath；开发态仍走 app 根目录
  const trayIcon = app.isPackaged
    ? join(process.resourcesPath, 'resources', 'icon.png')
    : join(app.getAppPath(), 'resources', 'icon.png')
  desktop.setupTray(trayIcon)

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
