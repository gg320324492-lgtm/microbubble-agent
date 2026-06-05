<template>
  <div class="voiceprint-view">
    <header class="header">
      <div class="header-left">
        <h2>声纹库中心</h2>
        <p>管理团队成员的声纹信息</p>
      </div>
      <div class="header-right">
        <button class="btn btn-primary">➕ 录入声纹</button>
      </div>
    </header>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-value">{{ members.length }}</div>
        <div class="stat-label">已录入成员</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ totalSamples }}</div>
        <div class="stat-label">总样本数</div>
      </div>
    </div>

    <div class="voiceprint-grid">
      <div v-for="member in members" :key="member.id" class="voiceprint-card">
        <div class="member-avatar">
          <span>{{ member.name.charAt(0) }}</span>
        </div>
        <div class="member-info">
          <h3>{{ member.name }}</h3>
          <p>{{ member.samples }} 个样本</p>
        </div>
        <div class="member-actions">
          <button class="btn btn-ghost btn-small">查看详情</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const members = ref([
  { id: 1, name: '张三', samples: 5 },
  { id: 2, name: '李四', samples: 3 },
  { id: 3, name: '王五', samples: 4 }
])

const totalSamples = computed(() => {
  return members.value.reduce((sum, m) => sum + m.samples, 0)
})
</script>

<style scoped>
.voiceprint-view {
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

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.stat-card {
  background: white;
  border-radius: var(--radius-lg);
  padding: 24px;
  border: 1px solid var(--color-border);
  text-align: center;
}

.stat-value {
  font-size: 36px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.stat-label {
  font-size: 13px;
  color: var(--color-text-tertiary);
}

.voiceprint-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.voiceprint-card {
  background: white;
  border-radius: var(--radius-lg);
  padding: 24px;
  border: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  gap: 16px;
  transition: all var(--duration-normal) var(--ease-out);
}

.voiceprint-card:hover {
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
