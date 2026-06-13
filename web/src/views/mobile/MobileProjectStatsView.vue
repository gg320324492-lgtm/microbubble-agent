<template>
  <div class="mobile-project-stats">
    <PageHeader title="项目动态" show-back @back="$router.back()" />

    <main
      class="stats-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <!-- 概览统计 -->
      <section class="stats-overview">
        <div class="overview-grid">
          <div class="overview-card primary">
            <div class="overview-num">{{ stats.active || 0 }}</div>
            <div class="overview-label">进行中</div>
          </div>
          <div class="overview-card success">
            <div class="overview-num">{{ stats.completed || 0 }}</div>
            <div class="overview-label">已完成</div>
          </div>
          <div class="overview-card warning">
            <div class="overview-num">{{ stats.paused || 0 }}</div>
            <div class="overview-label">已暂停</div>
          </div>
          <div class="overview-card info">
            <div class="overview-num">{{ stats.total || 0 }}</div>
            <div class="overview-label">总计</div>
          </div>
        </div>
      </section>

      <!-- 图表区（用 MobileECharts 移动端优化版） -->
      <section v-if="chartOption" class="chart-section">
        <h3 class="section-title">📊 项目状态分布</h3>
        <div class="chart-card">
          <MobileECharts :option="chartOption" height="280px" />
        </div>
      </section>

      <!-- 活跃项目列表 -->
      <section class="projects-section">
        <h3 class="section-title">🚀 活跃项目</h3>
        <div v-if="activeProjects.length === 0" class="empty-state">
          <div class="empty-icon">📁</div>
          <div class="empty-title">暂无活跃项目</div>
        </div>
        <div v-else class="projects-list">
          <div
            v-for="p in activeProjects"
            :key="p.id"
            class="project-item"
          >
            <div class="item-row">
              <span class="item-name">{{ p.name }}</span>
              <span class="item-progress">{{ p.progress || 0 }}%</span>
            </div>
            <div class="progress-bar-wrap">
              <div class="progress-bar" :style="{ width: (p.progress || 0) + '%' }" />
            </div>
            <div class="item-meta">
              <span>{{ p.members?.length || 0 }} 人</span>
              <span>{{ p.research_area || '未指定' }}</span>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
/**
 * MobileProjectStatsView.vue — 移动端项目动态
 *
 * PR #8b: 用 MobileECharts 渲染图表（pinch + 触摸优化）
 */

import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import PageHeader from '@/components/mobile/PageHeader.vue'
import MobileECharts from '@/components/mobile/MobileECharts.vue'

const stats = ref({})
const projects = ref([])

const activeProjects = computed(() => {
  return projects.value
    .filter((p) => p.status === 'active')
    .sort((a, b) => (b.progress || 0) - (a.progress || 0))
    .slice(0, 10)
})

const chartOption = computed(() => {
  if (!stats.value.total) return null
  return {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [
      {
        name: '项目状态',
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '45%'],
        data: [
          { value: stats.value.active || 0, name: '进行中', itemStyle: { color: '#FF7A5C' } },
          { value: stats.value.paused || 0, name: '已暂停', itemStyle: { color: '#E6A23C' } },
          { value: stats.value.completed || 0, name: '已完成', itemStyle: { color: '#67C23A' } },
        ],
        label: {
          fontSize: 11,
          formatter: '{b}\n{c}',
        },
      },
    ],
  }
})

async function loadData() {
  try {
    const [projectsRes] = await Promise.all([
      axios.get('/api/v1/projects', { params: { page_size: 100 } }),
    ])
    const list = projectsRes.data?.items || []
    projects.value = list
    stats.value = {
      total: list.length,
      active: list.filter((p) => p.status === 'active').length,
      paused: list.filter((p) => p.status === 'paused').length,
      completed: list.filter((p) => p.status === 'completed').length,
    }
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.mobile-project-stats {
  min-height: 100vh;
  background: var(--color-bg-page);
}

.stats-main {
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

/* 概览 */
.stats-overview {
  margin-bottom: 16px;
}
.overview-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}
.overview-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  padding: 16px 12px;
  text-align: center;
  border-left: 4px solid;
}
.overview-card.primary { border-color: var(--color-primary); }
.overview-card.success { border-color: var(--color-success, #67C23A); }
.overview-card.warning { border-color: var(--color-warning, #E6A23C); }
.overview-card.info { border-color: var(--color-info, #909399); }
.overview-num {
  font-size: 28px;
  font-weight: var(--font-weight-bold, 700);
  font-variant-numeric: tabular-nums;
  margin-bottom: 4px;
}
.overview-card.primary .overview-num { color: var(--color-primary); }
.overview-card.success .overview-num { color: var(--color-success, #67C23A); }
.overview-card.warning .overview-num { color: var(--color-warning, #E6A23C); }
.overview-card.info .overview-num { color: var(--color-text-regular); }
.overview-label {
  font-size: 12px;
  color: var(--color-text-secondary);
}

/* 图表 */
.chart-section {
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  padding: 16px;
  margin-bottom: 16px;
}
.section-title {
  font-size: 14px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
  margin: 0 0 12px;
  padding-left: 8px;
  border-left: 3px solid var(--color-primary);
}
.chart-card {
  margin: 0 -8px;
}

/* 活跃项目 */
.projects-section {
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  padding: 16px;
}
.projects-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.project-item {
  padding: 10px 12px;
  background: var(--color-bg-page);
  border-radius: var(--radius-sm);
}
.item-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.item-name {
  font-size: 13px;
  font-weight: var(--font-weight-medium, 500);
  color: var(--color-text-primary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-progress {
  font-size: 12px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-primary);
  margin-left: 8px;
}
.progress-bar-wrap {
  height: 4px;
  background: var(--color-border);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 6px;
}
.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--color-primary), var(--color-primary-light));
  transition: width 0.3s;
}
.item-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: var(--color-text-secondary);
}

/* 空态 */
.empty-state {
  text-align: center;
  padding: 40px 20px;
}
.empty-icon {
  font-size: 36px;
  margin-bottom: 8px;
}
.empty-title {
  font-size: 13px;
  color: var(--color-text-regular);
}
</style>