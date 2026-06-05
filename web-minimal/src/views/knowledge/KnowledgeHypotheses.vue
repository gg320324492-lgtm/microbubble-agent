<template>
  <div class="knowledge-hypotheses">
    <header class="header">
      <div class="header-left">
        <h3>假设管理</h3>
        <p>管理科研假设和验证状态</p>
      </div>
      <div class="header-right">
        <button class="btn btn-primary">➕ 添加假设</button>
      </div>
    </header>

    <div class="hypothesis-grid">
      <div v-for="hypothesis in hypotheses" :key="hypothesis.id" class="hypothesis-card">
        <div class="hypothesis-header">
          <h4>{{ hypothesis.title }}</h4>
          <span class="tag" :class="hypothesis.status">{{ getStatusLabel(hypothesis.status) }}</span>
        </div>
        <p>{{ hypothesis.description }}</p>
        <div class="hypothesis-meta">
          <span class="date">{{ hypothesis.created_at }}</span>
          <span class="author">{{ hypothesis.author }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const hypotheses = ref([
  {
    id: 1,
    title: '微纳米气泡可提高水处理效率',
    description: '假设微纳米气泡能够显著提高污水处理中的氧化效率',
    status: 'validated',
    created_at: '2026-05-15',
    author: '张三'
  },
  {
    id: 2,
    title: '气泡尺寸与稳定性相关',
    description: '假设气泡尺寸越小，其在水中的稳定性越高',
    status: 'proposed',
    created_at: '2026-06-01',
    author: '李四'
  },
  {
    id: 3,
    title: '表面活性剂影响气泡生成',
    description: '假设表面活性剂浓度会影响气泡的生成效率和尺寸分布',
    status: 'rejected',
    created_at: '2026-04-20',
    author: '王五'
  }
])

const getStatusLabel = (status) => {
  const labels = {
    proposed: '待验证',
    validated: '已验证',
    rejected: '已否定'
  }
  return labels[status] || status
}
</script>

<style scoped>
.knowledge-hypotheses {
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

.hypothesis-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.hypothesis-card {
  background: white;
  border-radius: var(--radius-lg);
  padding: 20px;
  border: 1px solid var(--color-border);
  transition: all var(--duration-normal) var(--ease-out);
}

.hypothesis-card:hover {
  box-shadow: var(--shadow-sm);
  transform: translateY(-2px);
}

.hypothesis-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}

.hypothesis-header h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.tag {
  padding: 4px 12px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
}

.tag.proposed {
  background: var(--color-info-bg);
  color: var(--color-info);
}

.tag.validated {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.tag.rejected {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}

.hypothesis-card p {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin-bottom: 12px;
}

.hypothesis-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--color-text-tertiary);
}
</style>
