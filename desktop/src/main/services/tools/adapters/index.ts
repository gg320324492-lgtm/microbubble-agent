// Scientific Adapters Index (Phase 7-T6: Scientific Tool Adapters).
//
// Phase 7-T6 strict: this is the public catalog of the built-in scientific
// adapters. NO registration happens here — that's initializeScientificAdapters().

import type { ToolAdapter } from '@shared/tools/tool-adapter-schema'

import { KINETIC_ANALYSIS_ADAPTER } from './kinetic-analysis'
import { DATASET_ANALYSIS_ADAPTER } from './dataset-analysis'
import { DATA_VISUALIZATION_ADAPTER } from './data-visualization'

export const SCIENTIFIC_ADAPTERS: readonly ToolAdapter[] = Object.freeze([
  KINETIC_ANALYSIS_ADAPTER,
  DATASET_ANALYSIS_ADAPTER,
  DATA_VISUALIZATION_ADAPTER
])

export {
  KINETIC_ANALYSIS_ADAPTER,
  DATASET_ANALYSIS_ADAPTER,
  DATA_VISUALIZATION_ADAPTER
}
