// Research Workspace Store — Pinia store for unified workspace.

import { defineStore } from 'pinia'
import type {
  ResearchWorkspace, WorkspaceModule, ResearchProgress, WorkspaceActivity,
  WorkspaceSummary, ProjectOverview
} from '../shared/workspace/research-workspace-schema'

export const useResearchWorkspaceStore = defineStore('research-workspace', {
  state: () => ({
    workspace: null as ResearchWorkspace | null,
    modules: [] as WorkspaceModule[],
    progress: null as ResearchProgress | null,
    activities: [] as WorkspaceActivity[],
    summary: null as WorkspaceSummary | null,
    overview: null as ProjectOverview | null,
    isLoading: false,
    errorMessage: '' as string
  }),

  getters: {
    moduleCount: (state) => state.modules.length,
    activeModuleCount: (state) => state.modules.filter((m) => m.enabled && (m.status === 'ready' || m.status === 'running')).length,
    progressPercent: (state) => state.progress?.percent ?? 0,
    recentActivityCount: (state) => state.activities.length,
    title: (state) => state.workspace?.title ?? '',
    projectId: (state) => state.workspace?.projectId ?? ''
  },

  actions: {
    setWorkspace(w: ResearchWorkspace) {
      this.workspace = w
      this.modules = [...w.modules]
      this.progress = { ...w.progress }
      this.activities = [...w.activities]
      this.summary = { ...w.summary }
      this.overview = { ...w.overview }
      this.errorMessage = ''
    },
    clear() {
      this.workspace = null
      this.modules = []
      this.progress = null
      this.activities = []
      this.summary = null
      this.overview = null
      this.errorMessage = ''
    },
    setLoading(b: boolean) { this.isLoading = b },
    setError(msg: string) { this.errorMessage = msg },
    updateModuleStatus(moduleId: string, status: WorkspaceModule['status']) {
      const m = this.modules.find((x) => x.id === moduleId)
      if (m) m.status = status
    },
    appendActivity(activity: WorkspaceActivity) {
      this.activities.push(activity)
    }
  }
})