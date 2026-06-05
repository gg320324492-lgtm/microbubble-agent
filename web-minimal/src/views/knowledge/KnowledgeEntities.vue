<template>
  <div class="knowledge-entities">
    <header class="header">
      <div class="header-left">
        <h3>实体管理</h3>
        <p>管理知识库中的实体和概念</p>
      </div>
      <div class="header-right">
        <button class="btn btn-primary">➕ 添加实体</button>
      </div>
    </header>

    <div class="entity-grid">
      <div v-for="entity in entities" :key="entity.id" class="entity-card">
        <div class="entity-icon">🏷️</div>
        <div class="entity-content">
          <h4>{{ entity.name }}</h4>
          <p>{{ entity.description }}</p>
          <div class="entity-meta">
            <span class="tag">{{ entity.type }}</span>
            <span class="count">{{ entity.connections }} 个关联</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const entities = ref([
  {
    id: 1,
    name: '微纳米气泡',
    description: '直径在微米到纳米级别的气泡',
    type: '概念',
    connections: 12
  },
  {
    id: 2,
    name: '文丘里管',
    description: '利用文丘里效应生成气泡的装置',
    type: '设备',
    connections: 8
  },
  {
    id: 3,
    name: '表面张力',
    description: '液体表面分子间的相互作用力',
    type: '物理量',
    connections: 15
  }
])
</script>

<style scoped>
.knowledge-entities {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.header-left p {
  font-size: 13px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

.entity-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.entity-card {
  background: white;
  border-radius: var(--radius-lg);
  padding: 20px;
  border: 1px solid var(--color-border);
  display: flex;
  gap: 16px;
  transition: all var(--duration-normal) var(--ease-out);
}

.entity-card:hover {
  box-shadow: var(--shadow-sm);
  transform: translateY(-2px);
}

.entity-icon {
  font-size: 24px;
}

.entity-content {
  flex: 1;
}

.entity-content h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.entity-content p {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.5;
  margin-bottom: 8px;
}

.entity-meta {
  display: flex;
  gap: 12px;
  align-items: center;
}

.tag {
  padding: 2px 10px;
  background: var(--color-bg-active);
  border-radius: var(--radius-full);
  font-size: 12px;
  color: var(--color-text-secondary);
}

.count {
  font-size: 12px;
  color: var(--color-text-tertiary);
}
</style>
