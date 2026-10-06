/**
 * useChatViewScroll — ChatViewSSE 智能 sticky scroll + 跳到最新/最早 + 虚拟列表降级
 *
 * L-1 阶段 2 (2026-10-07): 从 ChatViewSSE.vue <script setup> **原样迁出**,
 * 0 行为改动 (行为由 views/chat/__tests__/ChatViewSSE.behavior.test.js 兜底)。
 *
 * 依赖注入: messages / sessionId 由视图从 useChatStream 传入 —— useChatStream 的
 * 状态是 per-call 闭包 (函数内 ref), composable 里二次调用会拿到断开的新状态,
 * 绝不能在本模块内部再调 useChatStream()。
 */
import { ref, watch, nextTick, type Ref } from 'vue'

import { useVirtualList } from '@/composables/useVirtualList'  // W100 +45 虚拟滚动
import type { ChatMessage } from '@/composables/chat/useChatStream'

// ============================================================================
// 模块常量 (Plan v1 Step 6 重做: 集中 magic 值, 后续重构 + 测试容易)
// ============================================================================

/**
 * 虚拟滚动阈值 (消息数 > VIRTUAL_THRESHOLD 启用 absolute positioning 渲染)
 *
 * 2026-09-01 修复 (用户截图实证): 50 条即启用的虚拟定位以固定估高
 * VIRTUAL_ITEM_HEIGHT=120px 绝对定位消息, 而聊天消息实际高度 80~2000px+
 * (工具卡片/长文/markdown 列表), 长对话全部叠罗汉。聊天消息高度差异 20 倍,
 * 固定估高虚拟化根本不适用 (类 20.187 sidebar 同病灶)。
 * 处置: 阈值提到 1000 — 实际等于禁用虚拟定位, 走正常流式布局 (永不错位);
 * 真超长会话 (>1000 条) 的极端兜底场景估高同步修正为 360。
 */
const VIRTUAL_THRESHOLD = 1000

// ============================================================================
// 滚动到底部（智能 sticky scroll）
// ============================================================================
// 行为：
// 1. 任何消息变化（流式 text_delta / rich_block / 新消息）时，若 autoStick=true 则滚到底
// 2. 用户手动往上滚（scroll 位置 < 阈值）→ 取消 autoStick，停止自动滚
//    （避免用户看历史消息时被打扰）
// 3. 显示"↓ 跳到最新"按钮：点了恢复 autoStick + 滚到底
export interface UseChatViewScrollOptions {
  messages: Ref<ChatMessage[]>
  sessionId: Ref<string>
}

export function useChatViewScroll(options: UseChatViewScrollOptions) {
  const { messages, sessionId } = options

  const messagesRef = ref<HTMLElement | null>(null)
  const autoStick = ref(true)  // 是否自动贴底
  const showJumpToBottom = ref(false)  // 是否显示"跳到最新"按钮
  const showJumpToTop = ref(false)  // P0-#2 (2026-07-12): 是否显示"跳到最早"按钮
  const STICK_THRESHOLD_PX = 80  // 距底 < 80px 算"贴底"
  const USER_SCROLL_UP_THRESHOLD = 120  // 距底 > 120px 视为"用户主动上滚"
  const TOP_THRESHOLD_PX = 100  // P0-#2: 距顶 < 100px 算"贴顶"

  // ===== W100 +45 P3-VIRTUAL RETRY: 虚拟滚动 (仅 > VIRTUAL_THRESHOLD 的极端长会话) =====
  // 单一 composable 实例, items 用 readonly messages, 容器挂在 messagesRef
  // 2026-09-01: 估高 120 → 360 — 长会话兜底场景下含富内容的消息平均高度更接近此值;
  // 聊天消息高度天然不可预估, 虚拟化仅作为 >1000 条的极端降级, 常态走流式布局
  const VIRTUAL_ITEM_HEIGHT = 360
  const virtualList = useVirtualList({
    containerRef: messagesRef,
    items: messages as unknown as Ref<readonly ChatMessage[]>,
    itemHeight: VIRTUAL_ITEM_HEIGHT,
    threshold: VIRTUAL_THRESHOLD,
    overscan: 5,
  })

  const scrollToBottom = async (force = false) => {
    await nextTick()
    if (messagesRef.value) {
      if (force || autoStick.value) {
        messagesRef.value.scrollTop = messagesRef.value.scrollHeight
        autoStick.value = true
        showJumpToBottom.value = false
        refreshJumpToTop()
      }
    }
  }

  // P0-#2 修正 (2026-09-20): "跳到最早"只在内容真正可滚动 (溢出 > 阈值) 且当前
  // 离顶部足够远时显示。事故: 新会话仅 2 条消息, 流式自动滚底把 showJumpToTop
  // 硬置 true, 而短会话 scrollTop 赋值不产生真实滚动 → scroll 事件不触发 →
  // onMessagesScroll 的修正逻辑永远不跑, 按钮卡显。
  const refreshJumpToTop = () => {
    if (!messagesRef.value) {
      showJumpToTop.value = false
      return
    }
    const { scrollTop, scrollHeight, clientHeight } = messagesRef.value
    showJumpToTop.value =
      scrollHeight - clientHeight > TOP_THRESHOLD_PX && scrollTop > TOP_THRESHOLD_PX
  }

  // 2026-09-20 同族修正: "跳到最新"同样只在内容可滚动且离底部足够远时显示
  // (事故截图: 短会话贴顶时"跳到最新"也误显, 与"跳到最早"同一无条件置 true 病根)
  const refreshJumpToBottom = () => {
    if (!messagesRef.value) {
      showJumpToBottom.value = false
      return
    }
    const { scrollTop, scrollHeight, clientHeight } = messagesRef.value
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight
    showJumpToBottom.value =
      scrollHeight - clientHeight > STICK_THRESHOLD_PX && distanceFromBottom > STICK_THRESHOLD_PX
  }

  // P0-#2 新增: 滚到顶部 (用于"跳到最早"按钮)
  const scrollToTop = async () => {
    await nextTick()
    if (messagesRef.value) {
      messagesRef.value.scrollTop = 0
    }
  }

  // 监听用户手动滚动:用户往上滚 → 取消 autoStick
  const onMessagesScroll = () => {
    if (!messagesRef.value) return
    const { scrollTop, scrollHeight, clientHeight } = messagesRef.value
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight
    const distanceFromTop = scrollTop

    // W100 +45: 同步 scrollTop 到虚拟列表 (内部用其切片 visibleItems)
    virtualList._updateScroll(scrollTop, clientHeight)

    if (distanceFromBottom < STICK_THRESHOLD_PX) {
      // 接近底部 → 重新启用 autoStick
      autoStick.value = true
      showJumpToBottom.value = false
      // P0-#2: 离顶部 > 100px 时仍显示"跳到最早"按钮
      showJumpToTop.value = distanceFromTop > TOP_THRESHOLD_PX
    } else if (distanceFromTop < TOP_THRESHOLD_PX) {
      // P0-#2: 接近顶部 → 关闭"跳到最早"按钮 (已在顶部无需按钮)
      autoStick.value = false
      refreshJumpToBottom()  // 2026-09-20: 无溢出时不显示"跳到最新" (同族事故修正)
      showJumpToTop.value = false
    } else {
      // P0-#2: 中间区域 → 两个按钮都显示 (用户可自由跳到任一端)
      autoStick.value = false
      showJumpToBottom.value = true
      showJumpToTop.value = true
    }
  }

  const jumpToBottom = () => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
    autoStick.value = true
    showJumpToBottom.value = false
    refreshJumpToTop()  // P0-#2 修正: 不再无条件置 true (同 scrollToBottom 事故注释)
  }

  // P0-#2 新增: 跳到最早 (历史起点)
  const jumpToTop = () => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = 0
    }
    refreshJumpToBottom()  // 2026-09-20: 不再无条件置 true
    showJumpToTop.value = false
  }

  // ============================================================================
  // 智能 sticky scroll：监听 messages 变化自动滚到底（除非用户已上滚）
  // ============================================================================
  // 2026-06-14 方案 C 增强：之前只在 sendMessage 前后滚，流式生成中不滚，
  // 用户必须手动滚轮才能看新内容。改为 watch messages 实时滚。
  //
  // ★ 2026-07-01 修复 bug 2.2: sessionId watcher 改 rAF,避免与 messages watcher
  // 同一 tick 竞争 → 同一 .messages 容器连续两次 scrollTop 赋值 → 引起
  // 父级 flex 容器 (含侧边栏) 短暂 reflow → 侧边栏 scroll 跳变。
  watch(
    () => messages.value,
    () => {
      // 强制模式下永远滚；autoStick 模式下用户已上滚则不滚
      scrollToBottom(false)
    },
    { deep: true, flush: 'post' },
  )

  // 新 session 切换时也滚到底
  watch(
    () => sessionId.value,
    (newId, oldId) => {
      if (newId === oldId) return
      // rAF 推迟一帧,避免与 messages watcher 同步触发造成的 layout thrash
      requestAnimationFrame(() => scrollToBottom(true))
    },
  )

  return {
    messagesRef,
    autoStick,
    showJumpToBottom,
    showJumpToTop,
    virtualList,
    scrollToBottom,
    scrollToTop,
    onMessagesScroll,
    jumpToBottom,
    jumpToTop,
  }
}

export default useChatViewScroll
