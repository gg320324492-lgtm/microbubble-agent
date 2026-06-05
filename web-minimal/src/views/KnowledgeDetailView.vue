<template>
  <div class="knowledge-detail-view">
    <header class="header">
      <div class="header-left">
        <button class="btn btn-ghost" @click="$router.back()">← 返回</button>
        <h2>知识详情</h2>
      </div>
      <div class="header-right">
        <button class="btn btn-secondary">编辑</button>
        <button class="btn btn-danger">删除</button>
      </div>
    </header>

    <div class="knowledge-content">
      <div class="content-header">
        <h1>{{ knowledge.title }}</h1>
        <div class="content-meta">
          <span class="tag">{{ knowledge.category }}</span>
          <span class="date">{{ knowledge.created_at }}</span>
          <span class="author">{{ knowledge.author }}</span>
        </div>
      </div>
      <div class="content-body">
        <p>{{ knowledge.content }}</p>
      </div>
      <div class="content-tags">
        <span v-for="tag in knowledge.tags" :key="tag" class="tag">{{ tag }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const knowledge = ref({
  title: '微纳米气泡基础知识',
  category: '基础知识',
  created_at: '2026-06-01',
  author: '张三',
  content: '微纳米气泡是指直径在微米到纳米级别的气泡。它们具有独特的物理化学性质，如高比表面积、长寿命、表面电荷等，在环境治理、生物医药、农业等领域有广泛的应用前景。\n\n微纳米气泡的生成方法主要包括：\n1. 文丘里管法\n2. 微孔曝气法\n3. 电解法\n4. 超声波法\n\n每种方法都有其优缺点，选择合适的生成方法需要根据具体应用场景来决定。',
  tags: ['微纳米气泡', '基础知识', '气泡生成']
})
</script>

<style scoped>
.knowledge-detail-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.header-right {
  display: flex;
  gap: 12px;
}

.knowledge-content {
  background: white;
  border-radius: var(--radius-lg);
  padding: 32px;
  border: 1px solid var(--color-border);
}

.content-header {
  margin-bottom: 24px;
}

.content-header h1 {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin-bottom: 12px;
}

.content-meta {
  display: flex;
  gap: 16px;
  align-items: center;
}

.tag {
  padding: 4px 12px;
  background: var(--color-bg-active);
  border-radius: var(--radius-full);
  font-size: 12px;
  color: var(--color-text-secondary);
}

.date,
.author {
  font-size: 13px;
  color: var(--color-text-tertiary);
}

.content-body {
  margin-bottom: 24px;
}

.content-body p {
  font-size: 15px;
  color: var(--color-text-secondary);
  line-height: 1.8;
  white-space: pre-wrap;
}

.content-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 24px;
  border-top: 1px solid var(--color-border);
}
</style>
