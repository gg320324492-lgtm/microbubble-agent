// 渲染进程 window.api 类型声明。
// 由 preload 通过 contextBridge.exposeInMainWorld('api', ...) 注入。

import type { DesktopApi } from '@shared/preload-api'

declare global {
  interface Window {
    readonly api: DesktopApi
  }
}

export {}
