import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// 双击文件行的全屏入口由 FULLSCREEN_PREVIEW_EXTS 决定。
// .rar 漏掉时右栏有压缩包清单、双击却没反应（2026-11-13 实测）。
describe('DesktopDriveView 双击全屏扩展名清单', () => {
  it('包含 zip 和 rar', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'src/views/DesktopDriveView.vue'),
      'utf8',
    )
    const match = source.match(/const FULLSCREEN_PREVIEW_EXTS\s*=\s*\/(.+)\/i/)
    expect(match).toBeTruthy()
    expect(match[1]).toContain('zip|rar')
  })
})
