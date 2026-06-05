<template>
  <div class="project-view">
    <header class="header">
      <div class="header-left">
        <h2>项目管理</h2>
        <p>管理团队项目和里程碑</p>
      </div>
      <div class="header-right">
        <button class="btn btn-primary">➕ 新建项目</button>
      </div>
    </header>

    <div class="project-grid">
      <div v-for="project in projects" :key="project.id" class="project-card">
        <div class="project-header">
          <h3>{{ project.name }}</h3>
          <span class="tag">{{ project.status }}</span>
        </div>
        <p>{{ project.description }}</p>
        <div class="project-progress">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: project.progress + '%' }"></div>
          </div>
          <span>{{ project.progress }}%</span>
        </div>
        <div class="project-meta">
          <span>{{ project.tasks }} 个任务</span>
          <span>{{ project.members }} 位成员</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const projects = ref([
  {
    id: 1,
    name: '微纳米气泡研究',
    description: '微纳米气泡生成、表征和应用研究',
    status: '进行中',
    progress: 65,
    tasks: 12,
    members: 5
  },
  {
    id: 2,
    name: '实验设备升级',
    description: '实验室设备采购和升级计划',
    status: '计划中',
    progress: 30,
    tasks: 8,
    members: 3
  },
  {
    id: 3,
    name: '论文撰写',
    description: '学术论文撰写和投稿',
    status: '进行中',
    progress: 45,
    tasks: 6,
    members: 4
  }
])
</script>

<style scoped>
.project-view {
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

.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

.project-card {
  background: white;
  border-radius: var(--radius-lg);
  padding: 24px;
  border: 1px solid var(--color-border);
  transition: all var(--duration-normal) var(--ease-out);
}

.project-card:hover {
  box-shadow: var(--shadow-sm);
  transform: translateY(-2px);
}

.project-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.project-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.tag {
  padding: 4px 12px;
  background: var(--color-info-bg);
  color: var(--color-info);
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
}

.project-card p {
  font-size: 14px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin-bottom: 16px;
}

.project-progress {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.progress-bar {
  flex: 1;
  height: 8px;
  background: var(--color-bg-active);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: var(--radius-full);
  transition: width var(--duration-normal) var(--ease-out);
}

.project-progress span {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.project-meta {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--color-text-tertiary);
}
</style>
