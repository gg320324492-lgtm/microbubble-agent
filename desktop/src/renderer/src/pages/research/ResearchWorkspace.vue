<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useResearchWorkspaceStore } from '../../../../stores/research-workspace.store'
import { ResearchWorkspaceService } from '../../../../services/workspace/research-workspace.service'
import ResearchProgressCard from '../../components/workspace/ResearchProgressCard.vue'
import ModuleStatusCard from '../../components/workspace/ModuleStatusCard.vue'
import ActivityTimeline from '../../components/workspace/ActivityTimeline.vue'
import ProjectSummaryPanel from '../../components/workspace/ProjectSummaryPanel.vue'
import ResearchMilestonePanel from '../../components/workspace/ResearchMilestonePanel.vue'

const store = useResearchWorkspaceStore()
const service = new ResearchWorkspaceService()

onMounted(() => {
  if (!store.workspace) {
    const ws = service.loadWorkspace({
      projectId: 'demo-project',
      title: '微纳米气泡研究项目',
      domain: '环境科学',
      description: 'O3-MNB 降解 + 数字孪生 + 论文生成',
      status: 'active',
      members: 8,
      tasks: { total: 24, completed: 14 },
      experiments: { total: 6, completed: 4 },
      manuscripts: { total: 3, published: 1 },
      knowledge: { total: 80, indexed: 65 },
      moduleStatuses: {
        agent: 'ready',
        knowledge: 'ready',
        'multi-agent': 'running',
        experiment: 'running',
        twin: 'running',
        device: 'ready',
        control: 'ready',
        manuscript: 'paused'
      },
      activities: [
        { kind: 'agent', title: '智能体规划新实验', description: '为 O3-MNB 设计新一轮降解实验', actor: 'ExperimentAgent' },
        { kind: 'experiment', title: '实验执行完成', description: 'exp-7 全部 4 个测量步骤完成', actor: 'ExperimentEngine' },
        { kind: 'twin', title: '数字孪生校准', description: '降解模型 R² 更新至 0.92', actor: 'DigitalTwinEngine' },
        { kind: 'manuscript', title: '论文草稿更新', description: '新增方法章节内容', actor: 'ManuscriptEngine' },
        { kind: 'device', title: '设备数据接入', description: 'ozone-gen 实时流开始', actor: 'DeviceStreamManager' }
      ]
    })
    store.setWorkspace(ws)
  }
})
</script>

<template>
  <div class="research-workspace">
    <header class="research-workspace__header">
      <h1 class="research-workspace__title">科研工作区</h1>
      <p class="research-workspace__subtitle">{{ store.workspace?.overview.description ?? '统一科研项目管理' }}</p>
    </header>

    <section class="research-workspace__dashboard">
      <ProjectSummaryPanel :overview="store.overview" :summary="store.summary" />
      <ResearchProgressCard :progress="store.progress" />
    </section>

    <section class="research-workspace__modules">
      <h2 class="research-workspace__section-title">模块状态</h2>
      <div class="research-workspace__modules-grid">
        <ModuleStatusCard v-for="m in store.modules" :key="m.id" :module="m" />
      </div>
    </section>

    <section class="research-workspace__columns">
      <div class="research-workspace__col">
        <h2 class="research-workspace__section-title">研究里程碑</h2>
        <ResearchMilestonePanel :progress="store.progress" />
      </div>
      <div class="research-workspace__col">
        <h2 class="research-workspace__section-title">活动时间线</h2>
        <ActivityTimeline :activities="store.activities" />
      </div>
    </section>
  </div>
</template>

<style scoped>
.research-workspace {
  padding: 32px;
  max-width: 1400px;
  margin: 0 auto;
}
.research-workspace__header {
  margin-bottom: 32px;
}
.research-workspace__title {
  font-size: 28px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 4px;
}
.research-workspace__subtitle {
  font-size: 14px;
  color: #64748b;
  margin: 0;
}
.research-workspace__dashboard {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 16px;
  margin-bottom: 24px;
}
.research-workspace__section-title {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 12px;
}
.research-workspace__modules {
  margin-bottom: 24px;
}
.research-workspace__modules-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.research-workspace__columns {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 16px;
}
@media (max-width: 1024px) {
  .research-workspace__dashboard,
  .research-workspace__columns {
    grid-template-columns: 1fr;
  }
}
</style>