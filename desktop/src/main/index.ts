import { app, BrowserWindow, shell } from 'electron'
import { join } from 'node:path'
import { bootstrap } from './bootstrap'
import { registerIpcHandlers, setAppConfig } from './ipc'
import { APP_CONFIG, resolveAppConfig } from '@shared/config'

const isDev = !app.isPackaged

let mainWindow: BrowserWindow | null = null

function createMainWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: APP_CONFIG.windowMinWidth,
    minHeight: APP_CONFIG.windowMinHeight,
    show: false,
    autoHideMenuBar: true,
    title: APP_CONFIG.appName,
    backgroundColor: '#0f172a',
    webPreferences: {
      // Electron 安全基线（Phase 0 冻结，详见 docs/desktop-conversion/security.md）
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
      preload: join(__dirname, '../preload/index.js')
    }
  })

  win.webContents.on('will-navigate', (event) => {
    event.preventDefault()
  })

  win.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url)
    return { action: 'deny' }
  })

  if (isDev) {
    win.webContents.openDevTools({ mode: 'detach' })
  }

  win.once('ready-to-show', () => {
    win.show()
  })

  win.on('closed', () => {
    if (mainWindow === win) {
      mainWindow = null
    }
  })

  const devUrl = process.env['ELECTRON_RENDERER_URL']
  if (isDev && devUrl) {
    void win.loadURL(devUrl)
  } else {
    void win.loadFile(join(__dirname, '../renderer/index.html'))
  }

  return win
}

async function bootstrapApp(): Promise<void> {
  try {
    // 0. 解析应用配置 (含 dataDir / logDir / cacheDir), 注入 IPC 供 renderer 读取
    const appConfig = resolveAppConfig()
    setAppConfig(appConfig)

    // 1. 初始化 storage + auth (无 token 时 restore 自然失败，无影响)
    await bootstrap()

    // 2. 注册 IPC handlers
    registerIpcHandlers()

    // 3. 创建窗口
    mainWindow = createMainWindow()
  } catch (err) {
    // 启动阶段 fatal 错误: 标记 failed, 写日志, 创建窗口并展示 RecoveryCard
    const { reportBootstrapFailure } = await import('./bootstrap')
    reportBootstrapFailure(err instanceof Error ? err : new Error(String(err)))
    mainWindow = createMainWindow()
  }
}

app.whenReady().then(() => {
  void bootstrapApp()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      mainWindow = createMainWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// Electron 32+: 阻止创建新的 webContents（防 webview/iframe 跳出沙箱）
app.on('web-contents-created', (_, contents) => {
  contents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url)
    return { action: 'deny' }
  })
})
