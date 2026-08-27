// Demo Mode Toggle — Phase 8-M0-G
// 演示模式开关, 注入到现有 service.setAdapter() 替换 mock.
// 严禁污染真实业务 Store; 仅替换服务层 adapter.
//
// [类 20.201] 2026-08-28: 修复 disableDemoMode 不还原真实 adapter (banner 消失但服务仍用 demo 数据).
//   改为: disable 时重新注册真实 adapter (new SqliteXxxAdapter), 与默认 currentAdapter 一致.

import { computed, ref } from 'vue'
import { dataAnalysisService } from '../services/research/data-analysis.service'
import { manuscriptService } from '../services/research/manuscript.service'
import { knowledgeService } from '../services/research/knowledge.service'
import { literatureService } from '../services/research/literature.service'
import {
  demoDataAnalysisAdapter, demoManuscriptAdapter,
  demoKnowledgeAdapter, demoLiteratureAdapter,
  DEMO_ADAPTER_INFO
} from '../services/demo/demo-adapters'
import { realDataAnalysisAdapter } from '../services/research/data-analysis.service'
import { realManuscriptAdapter } from '../services/research/manuscript.service'
import { realKnowledgeAdapter } from '../services/research/knowledge.service'
import { realLiteratureAdapter } from '../services/research/literature.service'

const isDemoMode = ref(false)

/**
 * 启用 Demo 模式: 把所有现有 service 的 mock adapter 替换为演示专用 fixture.
 * 真实业务 Store 完全不参与, 因为它们只在 page mount 时通过 composable 触发 service 方法.
 */
function enableDemoMode(): void {
  if (isDemoMode.value) return
  dataAnalysisService.setAdapter(demoDataAnalysisAdapter)
  manuscriptService.setAdapter(demoManuscriptAdapter)
  knowledgeService.setAdapter(demoKnowledgeAdapter)
  literatureService.setAdapter(demoLiteratureAdapter)
  isDemoMode.value = true
  DEMO_ADAPTER_INFO.applied = true
}

/**
 * 关闭 Demo 模式: 还原 service 的真实 SQLite adapter.
 * 之前只翻 isDemoMode = false 但不恢复 adapter → banner 消失但所有数据仍 demo.
 * 修复: 显式 setAdapter(realXxxAdapter), 与默认一致.
 */
function disableDemoMode(): void {
  dataAnalysisService.setAdapter(realDataAnalysisAdapter)
  manuscriptService.setAdapter(realManuscriptAdapter)
  knowledgeService.setAdapter(realKnowledgeAdapter)
  literatureService.setAdapter(realLiteratureAdapter)
  isDemoMode.value = false
  DEMO_ADAPTER_INFO.applied = false
}

export function useDemoMode() {
  return {
    isDemoMode: computed(() => isDemoMode.value),
    enableDemoMode,
    disableDemoMode,
    info: DEMO_ADAPTER_INFO
  }
}
