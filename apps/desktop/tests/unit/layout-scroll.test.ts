// M7 随车必办① — 滚动缺陷修复的静态契约（矮窗口下内容可滚）
//
// 缺陷复盘（M5-2 遗留）：.shell-main 为 overflow:hidden，而各列表视图根容器是
// min-height:auto 的列向 flex item（不会收缩到内容以下），内容超高即被直接裁掉，
// 且没有任何可滚动的祖先 —— 设置页最先暴露。
import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const RENDERER = join(resolve(__dirname, '../..'), 'src/renderer/src')
const read = (p: string) => readFileSync(join(RENDERER, p), 'utf8')

const shell = read('layouts/ShellLayout.vue')

/** 取某个类名规则块（到下一个顶层 } 为止），并剔除注释（注释里会提到旧写法） */
function ruleOf(css: string, selector: string): string {
  const i = css.indexOf(selector)
  if (i < 0) return ''
  return css
    .slice(i, css.indexOf('}', i) + 1)
    .replace(/\/\*[\s\S]*?\*\//g, '')
}

describe('布局滚动 — .shell-main 必须可滚', () => {
  it('.shell-main 声明 overflow-y: auto（不再裁切超长内容）', () => {
    const rule = ruleOf(shell, '.shell-main {')
    expect(rule).not.toBe('')
    expect(rule).toMatch(/overflow-y:\s*auto/)
    expect(rule).not.toMatch(/overflow:\s*hidden/)
  })

  it('对话页保持内部独立滚动：.workbench 仍 min-height:0（不会与父级双滚动条）', () => {
    const assistant = read('views/AssistantView.vue')
    const rule = ruleOf(assistant, '.workbench {')
    expect(rule).toMatch(/min-height:\s*0/)
    expect(rule).toMatch(/flex:\s*1/)
  })

  it('六个模块 + 设置页的根容器均为内容高度（min-height 不为 0 的固定值，父级可滚）', () => {
    const roots: Array<[string, string]> = [
      ['views/KnowledgeView.vue', '.kb {'],
      ['views/MeetingsView.vue', '.mtg {'],
      ['views/ExperimentView.vue', '.eln {'],
      ['views/ManuscriptsView.vue', '.ms {'],
      ['views/SettingsView.vue', '.settings {']
    ]
    for (const [file, selector] of roots) {
      const rule = ruleOf(read(file), selector)
      expect(rule, `${file} 缺少 ${selector}`).not.toBe('')
      // 不得把根容器锁成固定高度或裁切（否则父级滚动失效）
      expect(rule, `${file} 不应 overflow:hidden`).not.toMatch(/overflow:\s*hidden/)
      expect(rule, `${file} 不应固定 height`).not.toMatch(/height:\s*\d+px/)
    }
  })

  it('状态栏/标题栏高度令牌仍为布局基准（未被换新改动）', () => {
    const appCss = read('assets/app.css')
    expect(appCss).toContain('--wb-titlebar-height: 40px')
    expect(appCss).toContain('--wb-statusbar-height: 26px')
    expect(shell).toContain('grid-template-rows: var(--wb-titlebar-height) 1fr var(--wb-statusbar-height)')
  })
})
