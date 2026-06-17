<template>
  <el-avatar
    v-if="avatarUrl"
    :size="size"
    :src="avatarUrl"
    :alt="`${memberName}的头像`"
  />
  <el-avatar
    v-else
    :size="size"
    :style="{ background: bgColor }"
    :alt="`${memberName}的头像`"
  >
    {{ memberName?.charAt(0) || '?' }}
  </el-avatar>
</template>

<script setup>
/**
 * MemberAvatar.vue — 移动端成员头像组件
 *
 * 接收 memberId，从 memberStore 自动查 avatar + name 渲染。
 * 与桌面端 MemberView line 67-71 等价，但自动从 store 拿数据。
 *
 * 字段 fallback（avatar 缺失）：
 * - 字母首字符（与桌面端一致）
 * - 背景色按用户名 hash 生成（与桌面 getAvatarColor 逻辑一致）
 */

import { computed } from 'vue'
import { useMemberStore } from '@/stores/member'

const props = defineProps({
  memberId: { type: [Number, String, null], default: null },
  memberName: { type: String, default: '' },
  /** 直接传 avatar URL（绕过 store 查询，用于不依赖 memberId 的场景） */
  src: { type: String, default: null },
  size: { type: Number, default: 40 },
})

const memberStore = useMemberStore()

// 优先用直接传的 src，否则从 store 查
const avatarUrl = computed(() => {
  if (props.src) return props.src
  if (!props.memberId) return null
  return memberStore.getMemberAvatar(props.memberId)
})

const memberName = computed(() => {
  if (props.memberName) return props.memberName
  if (props.memberId) return memberStore.getMemberName(props.memberId)
  return ''
})

// 头像背景色（按用户名 hash 选）
const AVATAR_COLORS = [
  '#FF7A5C', '#FFB347', '#67C23A', '#409EFF', '#E6A23C',
  '#F56C6C', '#909399', '#9B59B6', '#1ABC9C', '#3498DB',
]
const bgColor = computed(() => {
  const name = memberName.value || '?'
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]
})
</script>
