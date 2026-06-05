<template>
  <div class="member-view">
    <header class="header">
      <div class="header-left">
        <h2>成员管理</h2>
        <p>管理团队成员信息</p>
      </div>
      <div class="header-right">
        <button class="btn btn-primary">➕ 添加成员</button>
      </div>
    </header>

    <div class="member-grid">
      <div v-for="member in members" :key="member.id" class="member-card">
        <div class="member-avatar">
          <span>{{ member.name.charAt(0) }}</span>
        </div>
        <div class="member-info">
          <h3>{{ member.name }}</h3>
          <p>{{ member.role || '成员' }}</p>
        </div>
        <div class="member-actions">
          <button class="btn btn-ghost btn-small">编辑</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useMemberStore } from '@/stores/member'

const memberStore = useMemberStore()
const { members } = memberStore

onMounted(() => {
  memberStore.fetchMembers()
})
</script>

<style scoped>
.member-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.header-left p {
  font-size: 14px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

.member-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.member-card {
  background: white;
  border-radius: var(--radius-lg);
  padding: 24px;
  border: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  gap: 16px;
  transition: all var(--duration-normal) var(--ease-out);
}

.member-card:hover {
  box-shadow: var(--shadow-sm);
  transform: translateY(-2px);
}

.member-avatar {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-full);
  background: linear-gradient(135deg, var(--color-accent), #FFB347);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 24px;
  font-weight: 600;
}

.member-info {
  flex: 1;
}

.member-info h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.member-info p {
  font-size: 13px;
  color: var(--color-text-tertiary);
}
</style>
