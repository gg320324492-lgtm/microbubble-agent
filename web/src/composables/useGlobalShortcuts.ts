/**
 * useGlobalShortcuts — 全局键盘快捷键 composable
 *
 * #043 Phase 6 UI 升级配套：Cmd/Ctrl+K 弹 SearchPalette，Esc 关闭等
 *
 * 用法：
 *   useGlobalShortcuts({
 *     'mod+k': () => showSearch.value = true,
 *     'escape': () => showSearch.value = false,
 *   })
 *
 * 关键纪律（CLAUDE.md 2026-06-12 全局 listener 内存泄漏铁律）：
 * - onBeforeUnmount 必须 removeEventListener
 * - mod+k 在输入框里也允许（与 Notion/Slack 习惯一致）
 * - 单 esc 在输入框不触发（用户想清空内容）
 */
import { onMounted, onBeforeUnmount } from 'vue'

type ShortcutMap = Record<string, () => void>

export function useGlobalShortcuts(handlers: ShortcutMap) {
  function onKeydown(e: KeyboardEvent) {
    const target = e.target as HTMLElement | null
    const tag = target?.tagName || ''
    const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || !!target?.isContentEditable

    const mod = e.metaKey || e.ctrlKey
    // 统一小写：e.key.toLowerCase() 让 'K' 和 'k' 都命中 'mod+k'
    const baseKey = e.key.toLowerCase()
    const fullKey = `${mod ? 'mod+' : ''}${baseKey}`

    const handler = handlers[fullKey]
    if (!handler) return

    // mod 组合在输入框里也允许触发（Cmd+K 全局习惯）
    // 非 mod 快捷键在输入框里不触发（让用户正常打字）
    if (isInput && !fullKey.startsWith('mod+')) return

    e.preventDefault()
    handler()
  }

  onMounted(() => {
    window.addEventListener('keydown', onKeydown)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('keydown', onKeydown)
  })
}

export default useGlobalShortcuts
