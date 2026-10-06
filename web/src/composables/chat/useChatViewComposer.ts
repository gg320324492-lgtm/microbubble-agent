/**
 * useChatViewComposer — ChatViewSSE 输入区 / 发送流程 / 附件 / 引用 / 录音 / 重生成
 *
 * L-1 阶段 2 (2026-10-07): 从 ChatViewSSE.vue <script setup> **原样迁出**,
 * 0 行为改动 (行为由 views/chat/__tests__/ChatViewSSE.behavior.test.js 兜底)。
 *
 * 依赖注入铁律: useChatStream 的状态是 per-call 闭包 (函数内 ref), 本模块**不得**
 * 二次调用 useChatStream() —— sessionId / messages / 发送与 TTS/ASR/重发函数、
 * scrollToBottom 全部由视图注入, 便于单测用纯 ref + vi.fn 替身独立驱动。
 */
import { ref, nextTick, type Ref } from 'vue'

import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { useMemo } from '@/composables/useMemo'
import { useChatContextStore } from '@/stores/chatContext'  // 2026-08-15 #P4: 资料库附加文档
import { useUiStore } from '@/stores/useUiStore'
import type { ChatMessage, SendOptions } from '@/composables/chat/useChatStream'

export interface UseChatViewComposerOptions {
  /** 当前会话消息列表 (useChatStream.messages) */
  messages: Ref<ChatMessage[]>
  /** 当前会话 id (useChatStream.sessionId) */
  sessionId: Ref<string>
  /** 当前会话是否流式生成中 (useChatStream.isCurrentSessionSending) */
  isCurrentSessionSending: Ref<boolean>
  /** useChatStream.sendMessage — SSE 发送核心 */
  sendMessageCore: (opts: SendOptions) => Promise<void>
  /** useChatStream.playTTS */
  playTTS: (text: string) => Promise<void>
  /** useChatStream.asrRecognize */
  asrRecognize: (blob: Blob) => Promise<string | null>
  /** useChatStream.resendUserMessage — 编辑消息后重发 */
  resendUserMessage: (opts: {
    userMsgId: string
    serverId: number
    sessionId: string
    newContent: string
  }) => Promise<void>
  /** 视图滚动模块的 scrollToBottom — 发送前后强制滚底 */
  scrollToBottom: (force?: boolean) => Promise<void>
}

export function useChatViewComposer(options: UseChatViewComposerOptions) {
  const {
    messages,
    sessionId,
    isCurrentSessionSending,
    sendMessageCore,
    playTTS,
    asrRecognize,
    resendUserMessage,
    scrollToBottom,
  } = options

  const router = useRouter()
  const uiStore = useUiStore()
  const chatCtx = useChatContextStore()

  // Cache the message-id lookup used by regenerate; unrelated UI updates reuse it.
  const messageIndexById = useMemo(() => new Map(
    messages.value.map((message, index) => [message.id, index]),
  ))

  // ============================================================================
  // UI 状态（仅桌面端）
  // ============================================================================
  const inputText = ref('')
  const isDragging = ref(false)
  const textareaRef = ref<HTMLTextAreaElement | null>(null)
  const selectedImage = ref<File | null>(null)
  const imagePreviewUrl = ref('')
  const selectedFile = ref<File | null>(null)
  const voiceMode = ref(false)
  const imageInputRef = ref<HTMLInputElement | null>(null)
  const fileInputRef = ref<HTMLInputElement | null>(null)
  const loading = ref(false)

  // ChatGPT 风格 "+" 工具面板开关
  const toolPanelOpen = ref(false)
  // 2026-09-03 网页搜索模式 (工具面板开关): 开启后本条消息发送会带 web_search 标记
  const webSearchOn = ref(false)

  // W-N 周期: 图片灯箱
  const lightboxUrl = ref('')
  const showLightbox = ref(false)
  function openLightbox(url: string) {
    lightboxUrl.value = url
    showLightbox.value = true
  }
  function closeLightbox() {
    showLightbox.value = false
    lightboxUrl.value = ''
  }

  // W-N 周期: 引用回复
  const quotedMessage = ref<{ author: string; text: string; card: HTMLElement } | null>(null)
  function quoteMsg(btn: HTMLElement) {
    const card = btn.closest('.card') as HTMLElement | null
    if (!card) return
    const content = card.querySelector('.content')
    const author = card.closest('.msg')?.classList.contains('user') ? '我' : '小气助手'
    const text = content ? content.textContent?.trim().substring(0, 100) || '' : ''
    quotedMessage.value = { author, text, card }
    nextTick(() => {
      const ta = document.querySelector('.input-wrapper textarea') as HTMLTextAreaElement | null
      if (ta) ta.focus()
    })
    addQuoteRef(card)
  }
  function clearQuote() {
    quotedMessage.value = null
  }

  // 2026-08-16 #P5+: 清除已选图片预览 (注意: 不要 revokeObjectURL,
  // 因为 userMsg.imageUrl 引用同一个 URL, 消息气泡需要继续显示)
  function clearSelectedImage() {
    selectedImage.value = null
    imagePreviewUrl.value = ''
  }
  function clearSelectedFile() {
    selectedFile.value = null
  }
  // 2026-08-16 #P5+: 格式化文件大小 (B/KB/MB)
  function formatFileSize(bytes: number): string {
    if (!bytes || bytes <= 0) return ''
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }
  function addQuoteRef(card: HTMLElement) {
    card.classList.add('quote-ref')
    // Activate with delay for CSS animation
    setTimeout(() => card.classList.add('active'), 50)
  }

  // W-N 周期: 从 ChatMessageRow 收到 quote 事件
  function onQuote(payload: any) {
    const card = document.querySelector(`[data-msg-id="${payload?.msg?.id}"] .card`) as HTMLElement | null
    if (card) quoteMsg(card)
  }

  // ============================================================================
  // 发送消息（包装 useChatStream.sendMessage 以处理 UI 副作用）
  // ============================================================================
  // 关键设计：发送消息是**用户主动行为**，意图明确，必须**强制**滚到底（force=true）
  // 不受 sticky scroll 的 autoStick 守卫影响（用户上滚看历史时也要能看到自己发的内容）
  // 注意：scrollToBottom(true) 内部会 autoStick.value = true（scroll 模块内）
  // 后续流式 text_delta 接收时 watch(messages) 仍按 sticky 行为（用户再次上滚可中断）
  async function sendMessage(text?: string) {
    const content = (text ?? inputText.value).trim()
    if (!content && !selectedImage.value && !selectedFile.value) return

    inputText.value = ''
    const file = selectedFile.value
    const img = selectedImage.value
    // 2026-08-16 #P5+: 先读 imagePreviewUrl 再清空 (保留给消息气泡用)
    const currentImageUrl = imagePreviewUrl.value
    selectedImage.value = null
    imagePreviewUrl.value = ''
    selectedFile.value = null
    if (textareaRef.value) textareaRef.value.style.height = 'auto'

    loading.value = true
    // 2026-06-14 修复：发送前**强制**滚到底（force=true），不受 autoStick 守卫
    await scrollToBottom(true)

    try {
      // 2026-08-16 #P5+: 如果带图片, 先上传到 MinIO 拿永久 URL (避免刷新后 blob URL 失效)
      let uploadedImageUrl: string | null = currentImageUrl
      if (img && currentImageUrl && currentImageUrl.startsWith('blob:')) {
        try {
          const formData = new FormData()
          formData.append('image', img)
          const uploadRes = await fetch('/api/v1/chat/upload-image', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
            body: formData,
          })
          if (uploadRes.ok) {
            const data = await uploadRes.json()
            uploadedImageUrl = data.url  // 永久 MinIO URL
            console.log('[P5] 图片已上传到 MinIO:', uploadedImageUrl)
          } else {
            console.warn('[P5] 图片上传失败, 降级用 blob URL:', uploadRes.status)
          }
        } catch (uploadErr) {
          console.error('[P5] 图片上传异常, 降级用 blob URL:', uploadErr)
        }
      }

      await sendMessageCore({
        text: content,
        file,
        image: img,
        // #P5+: 传 imageUrl (MinIO 永久 URL, 刷新后仍有效)
        imageUrl: uploadedImageUrl,
        // 2026-09-03 网页搜索模式 (工具面板开关)
        webSearchOn: webSearchOn.value,
      })
      // #P5+: **立即**清空附加文档 (不等 sendMessageCore 完成, 否则用户看到 AI 回复期间顶部块还显示)
      // 顶部块立即消失, 后端 chat_session_attached_documents 仍存 (供 AI 引用)
      if (chatCtx.count > 0) {
        chatCtx.clear().catch(e => console.warn('[P5] 清空附加失败 (后台清, 不阻塞)', e))
      }
    } catch {
      // 错误已由 useChatStream 内部处理
    } finally {
      loading.value = false
      // 2026-06-14 修复：发送后**强制**滚到底（force=true），确保 assistant 占位可见
      await scrollToBottom(true)
    }
  }

  // ============================================================================
  // 输入栏 / 文件上传 / 拖拽
  // ============================================================================
  const quickActions = [
    { icon: '📋', label: '我的任务', text: '我最近有什么任务？' },
    { icon: '📅', label: '最近会议', text: '上周开了什么会？有什么结论？' },
    { icon: '📊', label: '项目进度', text: '项目进度如何？' },
    { icon: '📚', label: '知识问答', text: 'zeta 电位是什么？' }
  ]

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  function autoResize() {
    const el = textareaRef.value
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }

  function sendQuickMessage(t: string) { inputText.value = t; sendMessage(t) }
  function triggerImageUpload() { imageInputRef.value?.click() }
  function triggerFileUpload() { fileInputRef.value?.click() }

  // [CHAT-P1-E E2] 追问 chip 点击 → 触发新 SSE (复用 sendMessage 同 session)
  function onFollowUpClick(suggestion: string) {
    inputText.value = suggestion
    sendMessage(suggestion)
  }
  function openImage(url: string) { openLightbox(url) }

  function handleImageSelect(e: Event) {
    const f = (e.target as HTMLInputElement).files?.[0]; if (!f) return
    if (!f.type.startsWith('image/')) return ElMessage.error('请选择图片文件')
    if (f.size > 10 * 1024 * 1024) return ElMessage.error('图片不超过10MB')
    selectedImage.value = f
    imagePreviewUrl.value = URL.createObjectURL(f)
    ;(e.target as HTMLInputElement).value = ''
  }

  function handleFileSelect(e: Event) {
    const f = (e.target as HTMLInputElement).files?.[0]; if (!f) return
    if (f.size > 50 * 1024 * 1024) return ElMessage.error('文件不超过50MB')
    selectedFile.value = f
    ;(e.target as HTMLInputElement).value = ''
  }

  function onDragOver() { isDragging.value = true }
  function onDragLeave() { isDragging.value = false }
  function onDrop(e: DragEvent) {
    isDragging.value = false
    const f = e.dataTransfer?.files?.[0]; if (!f) return
    if (f.type.startsWith('image/')) {
      if (f.size > 10 * 1024 * 1024) return ElMessage.error('图片不超过10MB')
      selectedImage.value = f
      imagePreviewUrl.value = URL.createObjectURL(f)
    } else {
      if (f.size > 50 * 1024 * 1024) return ElMessage.error('文件不超过50MB')
      selectedFile.value = f
    }
  }

  // ============================================================================
  // 录音面板
  // ============================================================================
  function toggleVoiceMode() { voiceMode.value = !voiceMode.value }

  // ChatGPT 风格: 单击麦克风触发语音对话入口 — 当前为占位, 提示功能开发中
  // 后续接入: 长按说话 / Web Speech API / 持续对话
  function onVoiceTrigger() {
    ElMessage.info('🎤 语音对话功能开发中，目前可使用下方录音按钮')
    // 保留录音按钮入口, 后续可同时实现长按说话 / 短按占位
    toggleVoiceMode()
  }

  // 2026-08-15 #P4: "从资料库添加" → 跳知识库并启动选择模式
  function onPickFromKnowledge() {
    if (!sessionId.value) {
      // 没 session 时, 让 useChatStream.sendMessage 自己创建一个
      chatCtx.startSelecting('default')
    } else {
      chatCtx.startSelecting(sessionId.value)
    }
    router.push('/knowledge')
  }

  // InputToolPanel 触发但未实现的功能 (placeholder 提示)
  function onToggleWebSearch() {
    webSearchOn.value = !webSearchOn.value
    ElMessage.success(webSearchOn.value ? '🌐 网页搜索已开启' : '🌐 网页搜索已关闭')
  }
  function onSetDeepResearch() {
    uiStore.setThinkingMode('deep')
    ElMessage.success('🔭 已切换到深度研究模式')
  }

  function onRecordStart() {
    ElMessage.info('🎤 录音中...')
  }
  async function onRecordStop(blob: Blob) {
    const text = await asrRecognize(blob)
    if (text) {
      inputText.value = text
      await sendMessage()
    }
  }
  function onRecordError(err: any) {
    ElMessage.error(err?.message || '录音错误')
  }

  // ============================================================================
  // TTS（包装 useChatStream.playTTS）
  // ============================================================================
  async function playTTSWrap(text: string) {
    await playTTS(text)
  }

  // ============================================================================
  // W100 +23: 重生成 + 复制按钮 handler
  // ============================================================================

  /**
   * regenerate(msg): 找到目标 assistant 气泡之前的最后一个 user 消息内容,
   * 重新调 sendMessage(text) 发起新的 SSE 流式.
   *
   * 边界:
   * - 找不到前置 user (e.g. 第一条就是 welcome) → ElMessage 提示, 不发
   * - 当前正在流式生成 → 静默忽略, 让用户先点 ⏹ 停止
   * - sendMessage 内部已自动滚动 + loading 状态 + 持久化, 复用即可
   */
  async function regenerate(msg: ChatMessage) {
    if (isCurrentSessionSending.value) {
      ElMessage.warning('当前正在生成中，请先点 ⏹ 停止')
      return
    }
    // 查找目标 msg 之前的最后一条 user 消息
    const list = messages.value || []
    const idx = messageIndexById.value.get(msg.id) ?? -1
    if (idx === -1) {
      ElMessage.error('找不到原始消息，无法重新生成')
      return
    }
    // 从 idx 往前找最近一条 role='user' 且 content 非空
    let userContent = ''
    for (let i = idx - 1; i >= 0; i--) {
      const m = list[i]
      if (m?.role === 'user' && (m.content || '').trim()) {
        userContent = (m.content || '').trim()
        break
      }
    }
    if (!userContent) {
      ElMessage.warning('找不到对应的用户提问，无法重新生成')
      return
    }
    ElMessage.info('正在重新生成...')
    await sendMessage(userContent)
  }

  /**
   * copyMessage(msg): 调 navigator.clipboard.writeText, 失败降级到 execCommand.
   *
   * 边界:
   * - 内容为空 → 不复制
   * - clipboard API 不可用 (HTTP / 老 Safari) → fallback execCommand
   * - 复制失败 → ElMessage 错误提示
   */
  // 2026-08-16 #71: ChatGPT 风格 — 用户编辑消息后重发
  async function onUserEditSend(payload: { msg: any; newContent: string; serverId: number; sessionId: string }) {
    await resendUserMessage({
      userMsgId: payload.msg.id,
      serverId: payload.serverId,
      sessionId: payload.sessionId,
      newContent: payload.newContent,
    })
  }

  async function copyMessage(msg: ChatMessage) {
    const text = (msg?.content || '').trim()
    if (!text) return
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
        ElMessage.success('已复制')
        return
      }
      // 降级: execCommand
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      const ok = document.execCommand('copy')
      document.body.removeChild(ta)
      if (ok) ElMessage.success('已复制')
      else ElMessage.error('复制失败，请手动选择文本')
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('[copyMessage] failed', e)
      ElMessage.error('复制失败，请手动选择文本')
    }
  }

  return {
    inputText,
    isDragging,
    textareaRef,
    selectedImage,
    imagePreviewUrl,
    selectedFile,
    voiceMode,
    imageInputRef,
    fileInputRef,
    loading,
    toolPanelOpen,
    webSearchOn,
    lightboxUrl,
    showLightbox,
    openLightbox,
    closeLightbox,
    quotedMessage,
    quoteMsg,
    clearQuote,
    onQuote,
    clearSelectedImage,
    clearSelectedFile,
    formatFileSize,
    messageIndexById,
    sendMessage,
    quickActions,
    handleKeydown,
    autoResize,
    sendQuickMessage,
    triggerImageUpload,
    triggerFileUpload,
    onFollowUpClick,
    openImage,
    handleImageSelect,
    handleFileSelect,
    onDragOver,
    onDragLeave,
    onDrop,
    toggleVoiceMode,
    onVoiceTrigger,
    onPickFromKnowledge,
    onToggleWebSearch,
    onSetDeepResearch,
    onRecordStart,
    onRecordStop,
    onRecordError,
    playTTSWrap,
    regenerate,
    onUserEditSend,
    copyMessage,
  }
}

export default useChatViewComposer
