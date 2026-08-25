// Manuscript Loader Composable — Phase 8-M0-C 适配层.
// 包装 manuscriptService, 让页面不直接接触 service 路径.
import { manuscriptService, type ManuscriptSection } from '../services/research/manuscript.service'
import type { Manuscript, WritingIssue } from '../../../shared/science/manuscript-schema'

export function useManuscriptLoader() {
  return {
    fetchManuscript: () => manuscriptService.getManuscript() as unknown as Promise<Manuscript>,
    fetchIssues: () => manuscriptService.getWritingIssues() as unknown as Promise<WritingIssue[]>
  }
}

export type { ManuscriptSection }