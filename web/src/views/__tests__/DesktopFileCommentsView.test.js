/**
 * DesktopFileCommentsView.test.js — W85 B-2 P1-1 Step 1 view 层 UI 适配提取回归
 *
 * 2026-07-29 W85 第 1 批 B-2 P1 冗余重构 batch 3.
 *
 * 验证 UI 适配 (ElMessage wrapper) 已从 useFileCommentsDesktop composable
 * 提取到本 view 层, composable 侧只消费 base 核心 action.
 *
 * 采用与 MobileKnowledgeView.test.js / KnowledgeView.filter-reset.test.js
 * 同款的静态源码检查模式 (mount 需 mock EP + axios + router + Pinia, 成本高
 * 且易 false positive; 静态检查关键变更 100% 可靠).
 */

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { join } from 'path'

const VIEW_PATH = join(__dirname, '../desktop/DesktopFileCommentsView.vue')
const COMPOSABLE_PATH = join(
  __dirname,
  '../../composables/useFileCommentsDesktop.ts',
)

function readView() {
  return readFileSync(VIEW_PATH, 'utf-8')
}

function readComposable() {
  return readFileSync(COMPOSABLE_PATH, 'utf-8')
}

describe('DesktopFileCommentsView — W85 B-2 P1-1 UI 适配提取到 view 层', () => {
  it('view 源码可加载', () => {
    expect(readView().length).toBeGreaterThan(0)
  })

  it('view 从 composable 解构核心 action (updateComment/toggleResolved/deleteComment), 不再解构 UI wrapper', () => {
    const src = readView()
    // [^}]* 防止跨越前面别的解构块 (useCommentTree / useCommentReactions 等)
    const destructureMatch = src.match(
      /const\s*\{([^}]*)\}\s*=\s*useFileCommentsDesktop\(/,
    )
    expect(destructureMatch, 'useFileCommentsDesktop 解构必须存在').toBeTruthy()
    const destructured = destructureMatch[1]
    // 核心 action 必须直接消费
    expect(destructured).toMatch(/\bupdateComment\b/)
    expect(destructured).toMatch(/\btoggleResolved\b/)
    expect(destructured).toMatch(/\bdeleteComment\b/)
    // UI wrapper 不再从 composable 解构 (已在 view 层本地定义)
    expect(destructured).not.toMatch(/\bonEditComment\b/)
    expect(destructured).not.toMatch(/\bonToggleResolved\b/)
    expect(destructured).not.toMatch(/\bonDeleteComment\b/)
    expect(destructured).not.toMatch(/\bonReplyPrefix\b/)
  })

  it('view 层本地定义 4 个 UI 适配函数 (onEditComment/onToggleResolved/onDeleteComment/onReplyPrefix)', () => {
    const src = readView()
    expect(src).toMatch(/async function onEditComment\(/)
    expect(src).toMatch(/async function onToggleResolved\(/)
    expect(src).toMatch(/async function onDeleteComment\(/)
    expect(src).toMatch(/function onReplyPrefix\(/)
  })

  it('view 层 UI 适配函数委派核心 action (非重复实现 axios 调用)', () => {
    const src = readView()
    const scriptMatch = src.match(/<script setup>([\s\S]*?)<\/script>/)
    expect(scriptMatch).toBeTruthy()
    const script = scriptMatch[1]
    // onEditComment 体内调 updateComment
    const editFn = script.match(/async function onEditComment\([\s\S]*?\n\}/)
    expect(editFn, 'onEditComment 必须存在').toBeTruthy()
    expect(editFn[0]).toMatch(/await updateComment\(/)
    // onToggleResolved 体内调 toggleResolved
    const toggleFn = script.match(/async function onToggleResolved\([\s\S]*?\n\}/)
    expect(toggleFn[0]).toMatch(/await toggleResolved\(/)
    // onDeleteComment 体内调 deleteComment
    const delFn = script.match(/async function onDeleteComment\([\s\S]*?\n\}/)
    expect(delFn[0]).toMatch(/await deleteComment\(/)
    // view 层不得自建 axios 评论 API 调用 (核心仍在 composable)
    expect(script).not.toMatch(/axios\.(get|post|patch|delete)\([^)]*comments/)
  })

  it('模板事件绑定保持不变 (toggle-resolved / delete / save-edit 回归)', () => {
    const src = readView()
    const templateMatch = src.match(/<template>([\s\S]*?)<\/template>/)
    expect(templateMatch).toBeTruthy()
    const tpl = templateMatch[1]
    expect(tpl).toMatch(/@toggle-resolved="onToggleResolved"/)
    expect(tpl).toMatch(/@delete="onDeleteCommentWithConfirm"/)
    expect(tpl).toMatch(/@save-edit="onSaveEdit"/)
    expect(tpl).toMatch(/@reply="onReply"/)
  })

  it('composable 侧: 老 UI wrapper 保留为 @deprecated 兼容层 (W86 Step 2 前不删)', () => {
    const src = readComposable()
    // 兼容导出仍在 (分步走拦截铁律: Step 1 不删老)
    expect(src).toMatch(/function onEditComment\(/)
    expect(src).toMatch(/function onToggleResolved\(/)
    expect(src).toMatch(/function onDeleteComment\(/)
    expect(src).toMatch(/function onReplyPrefix\(/)
    // 已标 @deprecated
    const deprecatedCount = (src.match(/@deprecated W85 B-2 P1-1/g) || []).length
    expect(deprecatedCount).toBeGreaterThanOrEqual(4)
  })

  it('composable 侧: 核心 CRUD 委派 base (thin-shell), 无重复 axios 评论实现', () => {
    const src = readComposable()
    expect(src).toMatch(/useFileComments\(_fileIdRef\)/)
    expect(src).toMatch(/listComments:\s*base\.listComments/)
    expect(src).toMatch(/postComment:\s*base\.postComment/)
    expect(src).toMatch(/updateComment:\s*base\.updateComment/)
    expect(src).toMatch(/deleteComment:\s*base\.deleteComment/)
    expect(src).toMatch(/toggleResolved:\s*base\.toggleResolved/)
    // composable 内不得出现 /comments API 直调 (核心全在 useFileComments)
    expect(src).not.toMatch(/axios\.(get|post|patch|delete)\(`?[^)`]*\/comments/)
  })
})
