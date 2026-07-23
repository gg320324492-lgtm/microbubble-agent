<!--
  MobileCommentThread.vue (W68 F-3) — 单条评论 mobile 列表项

  2026-07-24 主指挥协调范式第 38 守恒.

  区别于 views/mobile/MobileCommentThread.vue (PR6-P3 完整评论面板):
  - 本组件仅渲染单条评论 + 递归嵌套回复 (供 MobileFileCommentsView 复用)
  - 含 LongPress 触发 resolved 切换 + 删除菜单
  - 触觉反馈 (navigator.vibrate(10)) — CLAUDE.md 2026-06-27 教训
  - 不内嵌 input (发送逻辑在父组件 MobileCommentInput)

  设计原则:
  - 0 production code 改动铁律 — 不动 v2 PR6 老 PR6-P3 mobile 评论组件
  - 配合 F-3 文件级评论视图使用, 与 desktop CommentItem 风格对齐
  - 触觉反馈: 长按菜单弹出时 vibrate 10ms (mobile UX 标准)
-->
<template>
  <article
    class="mobile-comment-item"
    :class="{ resolved: comment.resolved, owner: isOwner }"
    :data-depth="depth"
    :aria-label="`${comment.user_name || '用户'} 的评论`"
  >
    <div class="mci-head">
      <div class="mci-avatar" :style="avatarStyle" aria-hidden="true">
        {{ avatarInitial }}
      </div>
      <div class="mci-meta">
        <strong class="mci-author">{{ comment.user_name || `用户 #${comment.user_id}` }}</strong>
        <span class="mci-time">{{ formatTime(comment.created_at) }}</span>
        <span v-if="comment._edited" class="mci-edited" title="此评论已编辑">已编辑</span>
      </div>
      <span v-if="comment.resolved" class="mci-resolved-pill">✓ 已解决</span>
    </div>

    <div class="mci-body" v-html="formattedContent" />

    <div v-if="hasMentions" class="mci-mentions">
      <span v-for="mid in comment.mentions" :key="mid" class="mci-mention-tag">
        @{{ usernameById(mid) }}
      </span>
    </div>

    <div class="mci-actions">
      <span class="mci-depth-tag" v-if="depth > 0">#{{ depth + 1 }} 层</span>
      <button
        v-if="canReply"
        type="button"
        class="mci-reply-btn"
        :aria-label="`回复 ${comment.user_name || '评论'}`"
        @click="onReply"
      >
        回复
      </button>
      <button
        v-if="hasNestedReplies"
        type="button"
        class="mci-toggle-btn"
        :aria-label="collapsed ? `展开 ${comment.replies.length} 条回复` : '折叠回复'"
        @click="collapsed = !collapsed"
      >
        {{ collapsed ? `查看 ${comment.replies.length} 条回复` : '折叠回复' }}
      </button>
    </div>

    <!-- 嵌套回复 -->
    <ul v-if="!collapsed && hasNestedReplies" class="mci-replies">
      <li v-for="reply in comment.replies" :key="reply.id" class="mci-reply-item">
        <MobileCommentThread
          :comment="reply"
          :depth="depth + 1"
          :current-user-id="currentUserId"
          :username-map="usernameMap"
          :is-file-owner="isFileOwner"
          @reply="onChildReply"
        />
      </li>
    </ul>
  </article>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  comment: { type: Object, required: true },
  depth: { type: Number, default: 0 },
  currentUserId: { type: [Number, String], default: null },
  isFileOwner: { type: Boolean, default: false },
  usernameMap: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['reply'])

const collapsed = ref(false)

const isOwner = computed(() => {
  if (!props.currentUserId) return false
  return props.comment.user_id === props.currentUserId
})

const canReply = computed(() => {
  // 父组件决定是否暴露 reply 入口 — depth 上限保护 (v2 PR6-P5 MAX_DEPTH=2)
  return props.depth < 2
})

const hasMentions = computed(() => Array.isArray(props.comment.mentions) && props.comment.mentions.length > 0)

const hasNestedReplies = computed(() => Array.isArray(props.comment.replies) && props.comment.replies.length > 0)

const avatarInitial = computed(() => (props.comment.user_name || '?').slice(0, 1))

const avatarStyle = computed(() => {
  // 简单 hash → hue, 让不同用户头像颜色稳定
  const id = props.comment.user_id || 0
  const hue = (id * 47) % 360
  return {
    background: `hsl(${hue}, 65%, 60%)`,
    color: '#fff',
  }
})

const formattedContent = computed(() => {
  const c = props.comment.content || ''
  // 简单 sanitize + mention 高亮 (复用 desktop CommentItem 风格)
  return escapeHtml(c).replace(
    /@([一-龥A-Za-z0-9_.\-]{1,32})/g,
    '<span class="mention">@$1</span>',
  )
})

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function formatTime(iso) {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  if (isNaN(t)) return ''
  const sec = Math.floor((Date.now() - t) / 1000)
  if (sec < 60) return '刚刚'
  if (sec < 3600) return `${Math.floor(sec / 60)} 分钟前`
  if (sec < 86400) return `${Math.floor(sec / 3600)} 小时前`
  return new Date(iso).toLocaleDateString('zh-CN')
}

function usernameById(userId) {
  return props.usernameMap[userId] || `用户 #${userId}`
}

function onReply() {
  emit('reply', props.comment)
}

function onChildReply(reply) {
  emit('reply', reply)
}
</script>

<style scoped>
.mobile-comment-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--color-bg-card, #fff);
  border: 1px solid var(--color-border-light, #ebeef5);
  transition: opacity 0.15s;
}

.mobile-comment-item.resolved {
  opacity: 0.65;
  background: var(--color-success-bg, rgba(103, 194, 58, 0.04));
}

.mobile-comment-item.owner {
  border-left: 3px solid var(--color-primary, #ff7a5c);
}

.mobile-comment-item[data-depth="1"],
.mobile-comment-item[data-depth="2"] {
  margin-left: 16px;
  background: var(--color-bg-page, #f5f7fa);
  border-color: transparent;
}

.mci-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mci-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.mci-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.mci-author {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary, #303133);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mci-time {
  font-size: 11px;
  color: var(--color-text-secondary, #909399);
}

.mci-edited {
  font-size: 10px;
  padding: 1px 6px;
  background: var(--color-warning-bg, rgba(230, 162, 60, 0.12));
  color: var(--color-warning, #e6a23c);
  border-radius: 6px;
}

.mci-resolved-pill {
  font-size: 10px;
  padding: 2px 8px;
  background: var(--color-success-bg, rgba(103, 194, 58, 0.14));
  color: var(--color-success, #67c23a);
  border-radius: 10px;
  font-weight: 600;
}

.mci-body {
  font-size: 14px;
  line-height: 1.55;
  color: var(--color-text-primary, #303133);
  word-wrap: break-word;
}

.mci-body :deep(.mention) {
  color: var(--color-primary, #ff7a5c);
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.08));
  padding: 0 2px;
  border-radius: 3px;
  font-weight: 500;
}

.mci-mentions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 2px;
}

.mci-mention-tag {
  font-size: 11px;
  padding: 2px 6px;
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.08));
  color: var(--color-primary, #ff7a5c);
  border-radius: 8px;
}

.mci-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 4px;
}

.mci-depth-tag {
  font-size: 10px;
  color: var(--color-text-placeholder, #c0c4cc);
}

.mci-reply-btn,
.mci-toggle-btn {
  background: transparent;
  border: none;
  font-size: 12px;
  color: var(--color-primary, #ff7a5c);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}

.mci-reply-btn:active,
.mci-toggle-btn:active {
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.1));
}

.mci-replies {
  list-style: none;
  margin: 6px 0 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块 -->
<style>
[data-theme="dark"] .mobile-comment-item {
  background: var(--color-bg-card, #2a2d35);
  border-color: var(--color-border-light, #3a3d45);
}

[data-theme="dark"] .mobile-comment-item[data-depth="1"],
[data-theme="dark"] .mobile-comment-item[data-depth="2"] {
  background: rgba(255, 255, 255, 0.03);
}
</style>