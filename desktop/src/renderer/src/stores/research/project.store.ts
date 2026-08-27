// Project Store — 当前科研项目状态管理。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { projectsService } from '../../services/research/projects.service'

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
  // 真实数据来源: 1) 真实后端 /api/v1/projects (待实现), 2) 本地 SQLite (projects / experiments / samples / desktop_knowledge)
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

  // [类 20.191] 2026-08-27: 真实数据拉取 action.
  // 调 projectsService.listProjects() (走 window.api.database IPC 查本地 SQLite).
  // 失败时保持 currentProject = null, UI 显示空态.
  async function loadProjects(): Promise<void> {
    try {
      const list = await projectsService.listProjects()
      projectList.value = list
      // 默认选第一个 (按 updated_at DESC 排序, 最近更新的在前面)
      if (list.length > 0 && !currentProject.value) {
        currentProject.value = list[0]
      }
    } catch (e) {
      console.warn('[project.store] loadProjects failed:', e instanceof Error ? e.message : String(e))
      projectList.value = []
    }
  }

  return { currentProject, projectList, projectName, projectDomain, setCurrentProject, setProjectList, updateProgress, updateStats, loadProjects }
})
