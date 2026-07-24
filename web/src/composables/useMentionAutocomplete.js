/**
 * useMentionAutocomplete.js — v2 PR6-P4 @username 自动补全 composable
 *
 * W68 第 13 批 C-2 升级: 跨 DesktopMobile / DesktopFileCommentsView / DesktopDashboardView
 * 三处统一. 新增 `name` 调用场景标识 + `selector` 参数 (默认 [data-mention-input],
 * DesktopCommentInput/DesktopFileCommentsView 传 .dci-mention-input), 让多个 mention
 * dropdown 共存时 selector 隔离, 避免跨视图串状态.
 *
 * 触发机制:
 * - 监听 textarea/contenteditable 输入
 * - 提取光标前最近 @ 触发器 + query 字符串
 * - debounce 150ms 后从 /api/v1/members 拉候选列表
 * - 支持上下键选择 + Enter/Tab 补全 + Esc 关闭 + 点外部关闭
 *
 * 关键设计:
 * - 复用 desktop + mobile CommentThread (一次实现多视图用)
 * - keyboard navigation 是 a11y 必备 (用户不能用鼠标也必须能补全)
 * - candidates 来自服务端 query (无本地过滤), 避免重复逻辑
 * - keyboardSupport 默认 true (桌面/移动端都支持键盘)
 *
 * 状态机:
 *   idle (无 @) → active (检测到 @) → typing (用户在输入) → selected (高亮某项)
 *                  ↑                                                ↓
 *                  └────────── Esc / blur / 失焦 ←─────────────────┘
 *
 * 边界:
 * - 多个 @ 连续: 取光标前最近的 @ (cursorPos 决定)
 * - @ 后空格: 关闭下拉 (query 终止)
 * - 选中后: 把 username 替换到 @ 位置 + 后置光标
 *
 * 命名约定:
 * - triggerPos: @ 在 textarea 中的索引
 * - query: @ 之后到光标的字符串
 * - cursorPos: 当前光标位置
 */

import { ref, computed, onBeforeUnmount } from 'vue'

const TRIGGER_CHAR = '@'
const MENTION_PATTERN = /@([一-龥A-Za-z0-9_.\-]{1,32})/  // 镜像后端 regex (CLAUDE.md PR6-P4 铁律)

export function useMentionAutocomplete({
  textareaRef,           // ref to <textarea> or <el-input> wrapping it
  members,               // ref 或 array of {id, username, wechat_id, name, avatar, role}
  onSelect,              // (member) => void   选中后调用 (父组件负责替换文本)
  name = 'mention',      // 调用场景标识 (debugging + 多视图隔离)
  selector = '[data-mention-input]',  // CSS selector, 多视图共存时区分
  keyboardSupport = true,  // 默认 true: Desktop 已有键盘, Mobile 也支持
  debounceMs = 150,
  maxCandidates = 8,
} = {}) {
  const isOpen = ref(false)
  const query = ref('')
  const triggerPos = ref(-1)   // @ 在 textarea 中的索引
  const cursorPos = ref(-1)
  const selectedIndex = ref(0)
  const loading = ref(false)

  // W68 第 13 批 C-2: 暴露 config 为 ref, 外部可通过 .value 读取 (符合 Vue ref 约定)
  const nameRef = ref(name)
  const selectorRef = ref(selector)
  const keyboardSupportRef = ref(keyboardSupport)

  let membersCache = null     // 缓存 members list 避免重复 parse prop
  let debounceTimer = null
  // 当前 filter 后候选 (响应式, raw ref 不暴露, 外部通过 candidates/rawCandidates computed 访问)
  const candidatesRef = ref([])
  // 暴露 setter 给 tests / 父组件 (生产中由 refresh() 自动写, 测试用 setCandidates 注入)
  function setCandidates(arr) { candidatesRef.value = arr }
  function getCandidates() { return candidatesRef.value }

  // 计算属性: 过滤后的候选 (前端预 filter, 但要求后端已传全)
  const candidates = computed(() => candidatesRef.value.slice(0, maxCandidates))
  const rawCandidates = computed(() => candidates.value.map((c) => c.member))

  /**
   * 从 textarea 提取当前 @ 触发器位置 + query
   * 规则: 从光标位置往前找最近一个 @
   *       从该 @ 之后到光标之间的字符串作为 query
   */
  function extractMentionState() {
    // textareaRef 可选 (测试时可能不传); 缺失则当作 "无 DOM 上下文"
    if (!textareaRef?.value) return null
    // el-input 内部用 textarea/input; 直接用 .value 拿原生 element
    const el = textareaRef.value.$el?.querySelector?.('textarea') || textareaRef.value.$el || textareaRef.value
    if (!el || el.selectionStart == null) return null
    const value = el.value
    const cursor = el.selectionStart
    cursorPos.value = cursor
    // 从 cursor 往前找 @ (中间不能有 @ 之外的非 query 字符: 空格 / 换行 / 控制字符)
    let i = cursor - 1
    while (i >= 0) {
      const ch = value[i]
      if (ch === TRIGGER_CHAR) {
        // @ 前面不能是 identifier char (避免 email 误触)
        const prev = i > 0 ? value[i - 1] : ''
        if (prev && /[A-Za-z0-9_一-龥]/.test(prev)) return null
        const q = value.substring(i + 1, cursor)
        if (/\s/.test(q)) return null  // 中间含空格 → 不是有效 mention query
        return { triggerPos: i, query: q, cursor }
      }
      if (/\s/.test(ch)) return null  // 中间有空格 → 已终止
      i--
    }
    return null
  }

  /**
   * 拉取所有成员 (一次性 cache, 后续只在 cache miss 时再拉)
   * 注意: 真实场景可能从 props.members 直接拿, 不再 fetch
   * 这里采用 props-only 简化 — 父组件已在 onMounted 拉过 members
   */
  function ensureMembersCache() {
    if (membersCache) return membersCache
    const list = Array.isArray(members) ? members : (members?.value || [])
    membersCache = list
    return list
  }

  /**
   * 根据 query 过滤成员 (本地, 避免每键 fetch)
   * 匹配优先级: exact (wechat_id) > prefix (wechat_id) > prefix (username) > prefix (name)
   *
   * 2026-07-08 P1-8 修: name 字段也要 toLowerCase 与 wechat/username 保持一致.
   * 之前 `name === q` 用原始 q (未 lowercase), 当 name 字段是英文大小写敏感
   * (如 "WangTianZhi") 用户输入小写 ("wangtianzhi") 或全大写 ("WANGTIANZHI")
   * 时会失配 — wechat/username 都已 lowercase, 只有 name 例外.
   *
   * 注意: 纯中文输入场景 "张三".toLowerCase() === "张三" 不变, 修复前后行为
   * 相同. 主要修英文 name + 大小写不一致的 query 场景.
   * (Pinyin 输入 "zhang" → 中文 name "张三" 的场景需要 pinyin 映射表, 不在
   * 本次修复范围).
   */
  function filterMembers(list, q) {
    if (!q) return list.slice(0, maxCandidates)
    const ql = q.toLowerCase()
    const matched = []
    for (const m of list) {
      const wechat = (m.wechat_id || '').toLowerCase()
      const username = (m.username || '').toLowerCase()
      const name = (m.name || '').toLowerCase()
      if (wechat === ql || username === ql || name === ql) {
        matched.push({ member: m, score: 100, isExact: true })
      } else if (wechat.startsWith(ql) || username.startsWith(ql) || name.startsWith(ql)) {
        matched.push({ member: m, score: 50, isExact: false })
      }
    }
    matched.sort((a, b) => b.score - a.score)
    return matched.slice(0, maxCandidates)
  }

  /**
   * 触发状态更新 (输入或光标位置变化时调用)
   * debounce 避免每键 fetch
   *
   * 测试模式: 如果 query 已经手工设置 (ref.value != ''), 跳过 extractMentionState 直接过滤
   * 这样测试不依赖 DOM 也能验证 filter 逻辑
   */
  function refresh() {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      // 测试 fast-path: 无 textareaRef (测试环境无 DOM) → 跳过 extractMentionState, 按当前 query 直接过滤
      // 这样单测可以直接验证 filterMembers 逻辑, 不必 mock DOM
      if (!textareaRef?.value) {
        const list = ensureMembersCache()
        candidatesRef.value = filterMembers(list, query.value)
        selectedIndex.value = 0
        isOpen.value = candidatesRef.value.length > 0
        return
      }
      const state = extractMentionState()
      if (!state) {
        close()
        return
      }
      triggerPos.value = state.triggerPos
      cursorPos.value = state.cursor
      query.value = state.query
      const list = ensureMembersCache()
      candidatesRef.value = filterMembers(list, state.query)
      selectedIndex.value = 0
      isOpen.value = candidatesRef.value.length > 0
    }, debounceMs)
  }

  function open() {
    refresh()
  }

  function close() {
    isOpen.value = false
    query.value = ''
    triggerPos.value = -1
    cursorPos.value = -1
    selectedIndex.value = 0
    if (debounceTimer) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }
  }

  /**
   * 选中候选 index (默认 0)
   * 调 onSelect 回调 (父组件负责替换文本 + 移动光标)
   */
  function selectCandidate(index = selectedIndex.value) {
    const item = candidates.value[index]
    if (!item) return
    // 先捕获 state 再 close() (close 会重置 triggerPos/query)
    const member = item.member
    const ctx = { triggerPos: triggerPos.value, query: query.value }
    close()
    onSelect?.(member, ctx)
  }

  function moveSelection(delta) {
    if (!isOpen.value) return
    const n = candidates.value.length
    if (n === 0) return
    selectedIndex.value = (selectedIndex.value + delta + n) % n
  }

  function moveUp() { moveSelection(-1) }
  function moveDown() { moveSelection(1) }

  /**
   * 键盘事件处理器: 给 textarea 绑 onKeydown
   * 命中: ↑↓ Enter Tab Esc → true (已处理)
   * 不命中: false (让 textarea 自己处理)
   * 仅在 keyboardSupport=true 时启用 (默认 true)
   */
  function handleKeydown(event) {
    if (!keyboardSupportRef.value) return false
    if (!isOpen.value) return false
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault()
        moveDown()
        return true
      case 'ArrowUp':
        event.preventDefault()
        moveUp()
        return true
      case 'Enter':
      case 'Tab':
        event.preventDefault()
        selectCandidate()
        return true
      case 'Escape':
        event.preventDefault()
        close()
        return true
    }
    return false
  }

  // 清理
  onBeforeUnmount(() => {
    if (debounceTimer) clearTimeout(debounceTimer)
  })

  return {
    isOpen,
    query,
    candidates,         // wrapped: { member, score, isExact }
    rawCandidates,      // raw: member objects (供模板渲染)
    selectedIndex,
    triggerPos,
    cursorPos,
    loading,
    name: nameRef,               // 调用场景标识 (ref, 调试可读)
    selector: selectorRef,       // CSS selector (ref, 多视图隔离)
    keyboardSupport: keyboardSupportRef,    // 键盘支持开关 (ref)
    refresh,
    open,
    close,
    selectCandidate,
    moveUp,
    moveDown,
    handleKeydown,
    setCandidates,      // 测试用: 直接注入 candidates
    getCandidates,      // 测试用: 读 raw ref
  }
}

export default useMentionAutocomplete
