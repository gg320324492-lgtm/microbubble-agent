// Demo Mode Toggle — Phase 8-M0-G
// 演示模式开关, 注入到现有 service.setAdapter() 替换 mock.
// 严禁污染真实业务 Store; 仅替换服务层 adapter.

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
 * 关闭 Demo 模式: 调用方需要自行重置 adapter 为 mock 或生产实现.
 * 为避免破坏现有 mock 链路, 此处不调用 setAdapter, 仅翻转开关.
 */
function disableDemoMode(): void {
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
