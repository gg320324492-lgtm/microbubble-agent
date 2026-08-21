import { app, BrowserWindow, shell } from 'electron'
import { join } from 'node:path'
import { registerIpcHandlers } from './ipc'
import { APP_CONFIG } from '@shared/config'

const isDev = !app.isPackaged

let mainWindow: BrowserWindow | null = null

function createMainWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 640,
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
      // 拒绝对渲染进程暴露额外能力；只通过 preload contextBridge。
      preload: join(__dirname, '../preload/index.js')
    }
  })

  // 关闭 remote 模块（已被 Electron 12+ 废弃，但显式声明以固化安全姿态）
  win.webContents.on('will-navigate', (event) => {
    // 默认所有外链走系统浏览器，禁止 renderer 内导航
    event.preventDefault()
  })

  win.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url)
    return { action: 'deny' }
  })

  // DevTools 仅在开发模式暴露；生产禁用（详见 security.md）
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

  // 加载 renderer:
  // - dev 由 electron-vite 提供 http://localhost:5173
  // - prod 走 file:// out/renderer/index.html
  const devUrl = process.env['ELECTRON_RENDERER_URL']
  if (isDev && devUrl) {
    void win.loadURL(devUrl)
  } else {
    void win.loadFile(join(__dirname, '../renderer/index.html'))
  }

  return win
}

function bootstrapApp(): void {
  registerIpcHandlers()

  mainWindow = createMainWindow()
}

app.whenReady().then(() => {
  bootstrapApp()

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
