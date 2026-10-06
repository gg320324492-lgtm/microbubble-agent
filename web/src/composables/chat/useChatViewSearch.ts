/**
 * useChatViewSearch — ChatViewSSE 对话内搜索 (Ctrl+F / 头部搜索胶囊) + 全局快捷键
 *
 * L-1 阶段 2 (2026-10-07): 从 ChatViewSSE.vue <script setup> **原样迁出**,
 * 0 行为改动 (行为由 views/chat/__tests__/ChatViewSSE.behavior.test.js 兜底)。
 *
 * 本模块自管生命周期: document keydown (Ctrl+F) 在 onMounted 挂、onUnmounted 摘,
 * 与原实现 (挂在视图 onMounted/onUnmounted) 语义等价。
 * showSearchPalette + mod+k/escape 快捷键也住这里 (它们只服务全局搜索面板)。
 */
import { ref, nextTick, onMounted, onUnmounted, type Ref } from 'vue'

import { useGlobalShortcuts } from '@/composables/useGlobalShortcuts'

export function useChatViewSearch() {
  // ============================================================================
  // W-N 周期: 对话内搜索栏
  // ============================================================================
  const searchQuery = ref('')
  const searchMatches: Ref<HTMLElement[]> = ref([])
  const searchIndex = ref(-1)
  const searchInputRef = ref<HTMLInputElement | null>(null)

  // #043 Phase 6 UI 升级：全局搜索面板 (SearchPalette)
  const showSearchPalette = ref(false)

  // 全局快捷键（Cmd/Ctrl+K 弹搜索，Esc 关搜索）
  useGlobalShortcuts({
    'mod+k': () => { showSearchPalette.value = true },
    'escape': () => { if (showSearchPalette.value) showSearchPalette.value = false },
  })

  // ============================================================================
  // W-N 周期: 对话内搜索逻辑
  // ============================================================================
  function toggleChatSearch() {
    nextTick(() => {
      searchInputRef.value?.focus()
      searchInputRef.value?.select()
    })
  }
  function onHeaderSearchInput(e: Event) {
    searchQuery.value = (e.target as HTMLInputElement).value
    doSearch(searchQuery.value)
  }
  function onHeaderSearchClear() {
    searchQuery.value = ''
    clearSearchHighlights()
    searchInputRef.value?.focus()
  }
  function clearSearchHighlights() {
    document.querySelectorAll('.search-highlight').forEach(el => {
      const parent = el.parentNode
      if (parent) parent.replaceChild(document.createTextNode(el.textContent || ''), el)
    })
    searchMatches.value = []
    searchIndex.value = -1
    // 2026-09-03: 不再清 searchQuery — 旧逻辑在 doSearch 开头清词导致
    // 头部搜索胶囊每敲一键就被清空 (用户消息重复修复同轮发现)
  }
  function doSearch(query: string) {
    clearSearchHighlights()
    if (!query.trim()) return
    const lower = query.toLowerCase()
    const textNodes: Text[] = []
    const messagesEl = document.querySelector('.messages')
    if (!messagesEl) return
    const walker = document.createTreeWalker(messagesEl, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => {
        const el = n.parentElement
        if (!el) return NodeFilter.FILTER_ACCEPT
        if (el.closest('.chat-search-bar, .jump-to-bottom, .jump-to-top, .typing-indicator'))
          return NodeFilter.FILTER_REJECT
        return NodeFilter.FILTER_ACCEPT
      },
    })
    let node: Text | null
    while ((node = walker.nextNode() as Text | null)) textNodes.push(node)
    textNodes.forEach(tn => {
      const text = tn.textContent || ''
      const idx = text.toLowerCase().indexOf(lower)
      if (idx === -1) return
      const span = document.createElement('span')
      span.className = 'search-highlight'
      span.textContent = text.substring(idx, idx + query.length)
      const range = document.createRange()
      range.setStart(tn, idx)
      range.setEnd(tn, idx + query.length)
      range.deleteContents()
      range.insertNode(span)
      searchMatches.value.push(span)
    })
    searchIndex.value = searchMatches.value.length > 0 ? 0 : -1
  }
  function updateSearchNav() {
    searchMatches.value.forEach((el, i) => {
      el.classList.toggle('active', i === searchIndex.value)
      if (i === searchIndex.value) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    })
  }
  function searchNav(dir: number) {
    if (searchMatches.value.length === 0) return
    searchIndex.value = (searchIndex.value + dir + searchMatches.value.length) % searchMatches.value.length
    updateSearchNav()
  }

  // W-N 周期: Ctrl+F 快捷键 (原挂在视图 onMounted/onUnmounted, L-1 迁入本模块)
  function handleSearchKeydown(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
      e.preventDefault()
      toggleChatSearch()
    }
  }

  onMounted(() => {
    document.addEventListener('keydown', handleSearchKeydown)
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', handleSearchKeydown)
  })

  return {
    searchQuery,
    searchMatches,
    searchIndex,
    searchInputRef,
    showSearchPalette,
    toggleChatSearch,
    onHeaderSearchInput,
    onHeaderSearchClear,
    clearSearchHighlights,
    doSearch,
    searchNav,
  }
}

export default useChatViewSearch
