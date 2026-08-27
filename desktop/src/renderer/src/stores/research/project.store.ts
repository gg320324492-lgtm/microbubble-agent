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
  // [类 20.191] 2026-08-27: 删硬编码默认 project (id 'p1', fake stats 28/12/156).
  // 改为: currentProject 初始 null, projectList 初始 [].
  // 真实数据来源: 1) 真实后端 /api/v1/projects (待实现), 2) 本地 desktop_projects 表
  // 调 loadProjects() 主动拉取; 在没拉到数据前, UI 显示空态.
  const currentProject = ref<ResearchProject | null>(null)
  const projectList = ref<ResearchProject[]>([])

  const projectName = computed(() => currentProject.value?.name ?? null)
  const projectDomain = computed(() => currentProject.value?.domain ?? null)

  function setCurrentProject(project: ResearchProject | null) {
    currentProject.value = project
  }
  function setProjectList(list: ResearchProject[]) {
    projectList.value = list
  }
  function updateProgress(p: number) {
    if (!currentProject.value) return
    currentProject.value.progress = Math.max(0, Math.min(1, p))
  }
  function updateStats(stats: Partial<ResearchProject['stats']>) {
    if (!currentProject.value) return
    Object.assign(currentProject.value.stats, stats)
  }

  return { currentProject, projectList, projectName, projectDomain, setCurrentProject, setProjectList, updateProgress, updateStats }
})
