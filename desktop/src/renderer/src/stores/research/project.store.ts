// Project Store — 当前科研项目状态管理。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface ResearchProject {
  id: string
  name: string
  description: string
  domain: string
  progress: number
  status: 'active' | 'planning' | 'completed' | 'paused'
  stats: {
    experiments: number
    datasets: number
    documents: number
    manuscriptStatus: string
  }
}

export const useProjectStore = defineStore('research-project', () => {
  const currentProject = ref<ResearchProject>({
    id: 'p1',
    name: 'O₃-MNBs 强化四环素降解研究',
    description: '探索微纳米气泡臭氧技术对四环素类抗生素的降解效率与机理',
    domain: '环境科学',
    progress: 0.68,
    status: 'active',
    stats: { experiments: 28, datasets: 12, documents: 156, manuscriptStatus: '撰写中' }
  })

  const projectList = ref<ResearchProject[]>([currentProject.value])
  const projectName = computed(() => currentProject.value.name)
  const projectDomain = computed(() => currentProject.value.domain)

  function updateProgress(p: number) { currentProject.value.progress = Math.max(0, Math.min(1, p)) }
  function updateStats(stats: Partial<ResearchProject['stats']>) {
    Object.assign(currentProject.value.stats, stats)
  }

  return { currentProject, projectList, projectName, projectDomain, updateProgress, updateStats }
})
