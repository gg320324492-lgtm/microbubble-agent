<template>
  <div class="knowledge-formulas">
    <header class="header">
      <div class="header-left">
        <h3>公式库</h3>
        <p>管理和查阅科学公式</p>
      </div>
      <div class="header-right">
        <button class="btn btn-primary">➕ 添加公式</button>
      </div>
    </header>

    <div class="formula-grid">
      <div v-for="formula in formulas" :key="formula.id" class="formula-card">
        <div class="formula-content">
          <h4>{{ formula.name }}</h4>
          <div class="formula-expression">{{ formula.expression }}</div>
          <p>{{ formula.description }}</p>
        </div>
        <div class="formula-meta">
          <span class="tag">{{ formula.category }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const formulas = ref([
  {
    id: 1,
    name: '理想气体状态方程',
    expression: 'PV = nRT',
    description: '描述理想气体状态的方程',
    category: '热力学'
  },
  {
    id: 2,
    name: '表面张力公式',
    expression: 'γ = F/L',
    description: '表面张力的定义公式',
    category: '流体力学'
  },
  {
    id: 3,
    name: '雷诺数',
    expression: 'Re = ρvL/μ',
    description: '判断流体流动状态的无量纲数',
    category: '流体力学'
  }
])
</script>

<style scoped>
.knowledge-formulas {
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

.formula-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.formula-card {
  background: white;
  border-radius: var(--radius-lg);
  padding: 20px;
  border: 1px solid var(--color-border);
  transition: all var(--duration-normal) var(--ease-out);
}

.formula-card:hover {
  box-shadow: var(--shadow-sm);
  transform: translateY(-2px);
}

.formula-content h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.formula-expression {
  background: var(--color-bg-page);
  padding: 12px 16px;
  border-radius: var(--radius-md);
  font-family: 'Courier New', monospace;
  font-size: 16px;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.formula-content p {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.5;
}

.formula-meta {
  margin-top: 12px;
}

.tag {
  padding: 4px 12px;
  background: var(--color-bg-active);
  border-radius: var(--radius-full);
  font-size: 12px;
  color: var(--color-text-secondary);
}
</style>
