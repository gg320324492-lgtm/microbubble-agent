<template>
  <div class="participant-avatars">
    <template v-if="isAllMembers && totalMemberCount > 0">
      <div class="all-members-badge">
        <el-icon><User /></el-icon>
        <span>全体成员（{{ totalMemberCount }}人）</span>
      </div>
    </template>
    <template v-else-if="displayList.length > 0">
      <el-tooltip
        v-for="(p, idx) in visibleItems"
        :key="p.member_id || idx"
        :content="p.name || '未知'"
        placement="top"
        :show-after="300"
      >
        <el-avatar
          :size="size"
          :src="p.avatar || undefined"
          class="avatar-item"
          :style="{ zIndex: displayList.length - idx }"
        >
          {{ (p.name || '?')[0] }}
        </el-avatar>
      </el-tooltip>
      <div
        v-if="overflowCount > 0"
        class="avatar-overflow"
        :style="{ width: size + 'px', height: size + 'px', fontSize: (size * 0.35) + 'px' }"
      >
        +{{ overflowCount }}
      </div>
    </template>
    <span v-else class="no-participants">暂无参与者</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { User } from '@element-plus/icons-vue'
import { useMemberStore } from '@/stores/member'

const props = defineProps({
  /** 参与者列表 [{member_id, name?, avatar?, role?}] */
  participants: { type: Array, default: () => [] },
  /** 最多显示几个头像 */
  maxDisplay: { type: Number, default: 6 },
  /** 头像尺寸 (px) */
  size: { type: Number, default: 36 },
  /** 是否全体成员（覆盖 participants 显示） */
  allMembers: { type: Boolean, default: false },
})

const memberStore = useMemberStore()

const totalMemberCount = computed(() => memberStore.members.length)

const isAllMembers = computed(() => {
  if (props.allMembers) return true
  const ids = props.participants.map(p => p.member_id).filter(Boolean)
  const allIds = memberStore.members.map(m => m.id)
  return ids.length > 0 && allIds.length > 0 && ids.length === allIds.length && allIds.every(id => ids.includes(id))
})

/** 补全头像 URL + 姓名 */
const displayList = computed(() => {
  return props.participants.map(p => {
    const member = memberStore.members.find(m => m.id === p.member_id)
    return {
      ...p,
      name: p.name || member?.name || '未知',
      avatar: p.avatar || member?.avatar || null,
    }
  })
})

const visibleItems = computed(() => displayList.value.slice(0, props.maxDisplay))
const overflowCount = computed(() => Math.max(0, displayList.value.length - props.maxDisplay))
</script>

<style scoped>
.participant-avatars {
  display: flex;
  align-items: center;
  gap: 0;
}

.avatar-item {
  border: 2px solid #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
  margin-left: -8px;
  cursor: pointer;
  transition: transform 0.2s ease-out, box-shadow 0.2s ease-out;
  flex-shrink: 0;
}

.avatar-item:first-child {
  margin-left: 0;
}

.avatar-item:hover {
  transform: scale(1.12);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  z-index: 100 !important;
}

.avatar-overflow {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--color-bg-page, #f5f7fa);
  border: 2px solid #fff;
  color: var(--color-text-secondary, #909399);
  font-weight: 600;
  margin-left: -8px;
  flex-shrink: 0;
}

.all-members-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: var(--color-primary-bg, #fff0ed);
  color: var(--color-primary, #FF7A5C);
  border-radius: var(--radius-full, 9999px);
  font-size: 13px;
  font-weight: 500;
}

.no-participants {
  font-size: 13px;
  color: var(--color-text-placeholder, #c0c4cc);
}
</style>
