// 托盘图标路径解析（M6-2 清账②）— 纯函数，exists 注入，离线可测。
//
// 托盘优先使用 .ico（Windows 原生多尺寸，任务栏/托盘在高 DPI 下不再拉伸模糊）；
// .png 回退保留（.ico 缺失或非 Windows 场景）。
// 运行时根目录：打包态 = process.resourcesPath；开发态 = app.getAppPath()。
// 两个候选均由 electron-builder 的 extraResources 落在 <root>/resources/ 下。
import { join } from 'node:path'

export interface TrayIconResolution {
  /** 最终交给 Tray 构造器的路径 */
  path: string
  /** 实际命中的候选类型 */
  kind: 'ico' | 'png'
  /** 所有候选都不存在（托盘创建会失败，调用方应记日志） */
  missing: boolean
}

export const TRAY_ICON_FILES = { ico: 'icon.ico', png: 'icon.png' } as const

/** 解析托盘图标：.ico 优先，.png 回退 */
export function resolveTrayIcon(input: { resourcesRoot: string; exists: (p: string) => boolean }): TrayIconResolution {
  const ico = join(input.resourcesRoot, 'resources', TRAY_ICON_FILES.ico)
  if (input.exists(ico)) return { path: ico, kind: 'ico', missing: false }
  const png = join(input.resourcesRoot, 'resources', TRAY_ICON_FILES.png)
  if (input.exists(png)) return { path: png, kind: 'png', missing: false }
  // 两者都不存在：返回 png 路径让上层报错更直观（Tray 构造会抛 ENOENT）
  return { path: png, kind: 'png', missing: true }
}
