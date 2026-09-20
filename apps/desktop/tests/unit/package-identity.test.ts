// R-9 A2 打包身份守护 — userData 归属回归防线
//
// 事故背景：打包产物 `app.getName()` 回退到 package.json 的 `name`（"@mb/desktop"），
// 导致首启 userData 落到 `%APPDATA%\@mb\desktop`，与开发模式共用目录，真机首装用户被
// 历史残留账号锁在登录页。根因是 electron-builder **不会**把 productName 注入 asar 内的
// package.json（它只用配置里的 productName 命名产物/写元数据）。
//
// 因此修复必须落在 package.json 的 `productName` 字段上（Electron 优先读它）。
// 本测试把这条约束锁死：一旦有人删掉该字段或与 electron-builder 配置不一致，立即失败。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const APP = resolve(__dirname, '../..')
const pkg = JSON.parse(readFileSync(resolve(APP, 'package.json'), 'utf8')) as { name: string; productName?: string }
const builderYml = readFileSync(resolve(APP, 'electron-builder.yml'), 'utf8')

describe('A2 打包身份 — productName 必须存在且合法', () => {
  it('package.json 声明 productName（否则 app.getName() 回退到 name）', () => {
    expect(pkg.productName, 'package.json 缺少 productName —— app.getName() 会回退到 name').toBeTruthy()
    expect(pkg.productName).toBe('MicroBubbleWorkbench')
  })

  it('与 electron-builder.yml 的 productName 一致（避免产物名与运行期身份分叉）', () => {
    const m = /^productName:\s*(.+)$/m.exec(builderYml)
    expect(m, 'electron-builder.yml 缺少 productName').toBeTruthy()
    expect(m![1].trim()).toBe(pkg.productName)
  })

  it('productName 不含路径分隔符与 npm scope 字符（否则 userData 会落到子目录）', () => {
    const p = String(pkg.productName)
    expect(p).not.toMatch(/[/\\@]/)
    expect(p).not.toBe(pkg.name)
  })
})
