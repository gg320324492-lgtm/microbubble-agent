// M6-2 清账② — 托盘图标路径解析（.ico 优先，.png 回退）
import { describe, expect, it } from 'vitest'
import { TRAY_ICON_FILES, resolveTrayIcon } from '@main/services/desktop/tray-icon'

/** 构造只"存在"指定路径的 exists */
const only = (...paths: string[]) => (p: string) => paths.some((x) => p.endsWith(x))

describe('托盘图标解析 — .ico 优先 / .png 回退', () => {
  it('.ico 存在时优先用 .ico（Windows 原生多尺寸）', () => {
    const res = resolveTrayIcon({ resourcesRoot: 'C:\\app\\resources', exists: only('icon.ico', 'icon.png') })
    expect(res.kind).toBe('ico')
    expect(res.missing).toBe(false)
    expect(res.path.endsWith(TRAY_ICON_FILES.ico)).toBe(true)
  })

  it('.ico 缺失时回退 .png（回退保留）', () => {
    const res = resolveTrayIcon({ resourcesRoot: 'C:\\app\\resources', exists: only('icon.png') })
    expect(res.kind).toBe('png')
    expect(res.missing).toBe(false)
    expect(res.path.endsWith(TRAY_ICON_FILES.png)).toBe(true)
  })

  it('两者都不存在 → 返回 png 路径并标记 missing（供上层记日志）', () => {
    const res = resolveTrayIcon({ resourcesRoot: 'C:\\app\\resources', exists: () => false })
    expect(res.missing).toBe(true)
    expect(res.path.endsWith(TRAY_ICON_FILES.png)).toBe(true)
  })

  it('候选固定在 <root>/resources/ 下（与 extraResources 落点一致）', () => {
    const seen: string[] = []
    resolveTrayIcon({
      resourcesRoot: '/opt/app/resources',
      exists: (p) => {
        seen.push(p)
        return false
      }
    })
    expect(seen.length).toBe(2)
    for (const p of seen) expect(p).toContain('resources')
    expect(seen[0].endsWith('icon.ico')).toBe(true)
    expect(seen[1].endsWith('icon.png')).toBe(true)
  })
})
