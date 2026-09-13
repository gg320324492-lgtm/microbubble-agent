// 主进程入口 — 无边框窗口 + 三铁律安全基线（骨架设计 §5）
import { app, BrowserWindow, shell } from 'electron'
import { join } from 'node:path'
import { registerIpc } from './ipc'
import { openDatabase } from './db'
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
  mainWindow.on('closed', () => {
    mainWindow = null
  })

  // 铁律 3 配套 — 禁 renderer 内导航；外链一律走系统浏览器
  mainWindow.webContents.on('will-navigate', (event) => event.preventDefault())
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url)
    return { action: 'deny' }
  })

  if (process.env['ELECTRON_RENDERER_URL']) {
    void mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    void mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(() => {
  const dbPath = join(app.getPath('userData'), 'data', 'workbench.db')
  const db = openDatabase(dbPath)
  registerIpc(db, dbPath, () => mainWindow)
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
