<script setup>
/**
 * MemberCardBlock.vue — 成员卡
 *
 * 接收 block.data = {members: [{id, name, grade, research_area, email, role, skills, voice_enrolled, bio}]}
 */
const props = defineProps({ block: { type: Object, required: true } })
const members = (props.block.data || {}).members || []

const roleLabel = (r) => ({ admin: '管理员', leader: '组长', member: '成员' }[r] || r || '成员')
const roleColor = (r) => ({ admin: '#f56c6c', leader: '#e6a23c', member: '#909399' }[r] || '#909399')
</script>

<template>
  <div class="member-card rich-card">
    <div class="card-header">
      <span class="icon">👥</span>
      <span class="title">{{ block.title || '成员列表' }} ({{ members.length }})</span>
    </div>
    <div v-for="m in members" :key="m.id" class="member-item">
      <el-avatar :size="40" :src="m.avatar" class="avatar" :alt="`${m.name || '成员'}的头像`" :title="`${m.name || '成员'}的头像`">
        {{ m.name?.charAt(0) }}
      </el-avatar>
      <div class="member-info">
        <div class="member-row1">
          <span class="member-name">{{ m.name }}</span>
          <span class="role" :style="{ color: roleColor(m.role) }">{{ roleLabel(m.role) }}</span>
          <span v-if="m.voice_enrolled" class="voice-badge">🎙️</span>
        </div>
        <div class="member-row2">
          <span v-if="m.grade" class="meta">{{ m.grade }}</span>
          <span v-if="m.research_area" class="meta research">🔬 {{ m.research_area }}</span>
          <span v-if="m.email" class="meta email">📧 {{ m.email }}</span>
        </div>
        <div v-if="m.skills && m.skills.length" class="skills">
          <span v-for="s in m.skills.slice(0, 5)" :key="s" class="skill">{{ s }}</span>
        </div>
        <div v-if="m.bio" class="bio">{{ m.bio }}</div>
      </div>
    </div>
    <div v-if="!members.length" class="empty">暂无成员</div>
  </div>
</template>

<style scoped>
.rich-card { background: var(--color-bg-card); border: 1px solid #e8eaed; border-radius: 10px; padding: 12px 14px; margin: 8px 0; box-shadow: var(--shadow-xs); }
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 14px; margin-bottom: 10px; color: var(--color-primary); }
.icon { font-size: 18px; }
.member-item { display: flex; gap: 12px; padding: 10px 0; border-top: 1px solid #f0f1f3; }
.member-item:first-of-type { border-top: none; }
.avatar {
  background: linear-gradient(135deg, #FF7A5C, #FFB347);
  /* stylelint-disable-next-line color-named */
  color: white;
  flex-shrink: 0;
}
.member-info { flex: 1; min-width: 0; }
.member-row1 { display: flex; align-items: center; gap: 8px; }
.member-name { font-weight: 500; font-size: 14px; }
.role { font-size: 11px; padding: 1px 8px; border-radius: 10px; background: var(--color-bg-hover); }
.voice-badge { font-size: 14px; }
.member-row2 { display: flex; gap: 12px; font-size: 12px; color: var(--color-text-secondary); margin-top: 4px; flex-wrap: wrap; }
.skills { display: flex; gap: 4px; margin-top: 6px; flex-wrap: wrap; }
.skill { font-size: 11px; background: var(--color-primary-bg); color: var(--color-primary); padding: 1px 6px; border-radius: 8px; }
.bio { font-size: 12px; color: var(--color-text-secondary); margin-top: 4px; line-height: 1.5; }
.empty { text-align: center; color: var(--color-text-secondary); padding: 20px 0; font-size: 13px; }
</style>
