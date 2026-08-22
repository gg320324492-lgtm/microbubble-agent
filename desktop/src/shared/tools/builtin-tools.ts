// Built-in Tool Catalog (Phase 7-T1: Tool Registry Implementation).
//
// Phase 7-T1: example tool metadata only — declarations, NOT connected to real
// functions. Phase 7-T+ (Adapter phase) wires each built-in tool to an
// actual executor via application-adapter-design.md.
//
// Phase 7-T1 strict:
//   - NO function bodies
//   - NO real wiring to existing application
//   - NO execution paths
//   - These are pure metadata for discovery + future adapter registration

// Phase 7-T1 strict: import ToolFieldType so literal types narrow correctly.
import type { ToolDefinition, ToolFieldType } from './tool-schema'

// Phase 7-T1: a small helper to narrow `type` literal strings to ToolFieldType
const t = (s: ToolFieldType): ToolFieldType => s

/**
 * Phase 7-T1: example kinetic-analysis tool declaration.
 *
 * Adapter contract: a future `kinetic-analysis.ts` adapter (Phase 7-T+) will
 * wrap an existing kinetics function and register with the Tool Registry.
 */
export const KINETIC_ANALYSIS_TOOL: ToolDefinition = {
  id: 'tool:kinetic-analysis',
  name: 'Kinetic Analysis',
  description: 'Fit kinetic models to time-series concentration data',
  category: 'analysis',
  version: '1.0.0',
  inputSchema: {
    fields: [
      { name: 'dataset', type: t('object'), required: true,
        description: 'A Dataset entity from the Knowledge Layer' },
      { name: 'model', type: t('string'), required: false,
        enum: ['first-order', 'second-order', 'zero-order'],
        description: 'Kinetic model to fit' }
    ],
    required: ['dataset'],
    validationRules: ['dataset must be a valid Dataset entity (isValidDataset)']
  },
  outputSchema: {
    description: 'KineticResult { k_obs, r_squared, half_life }',
    fields: ['k_obs', 'r_squared', 'half_life']
  },
  executionTarget: 'local-service',
  permission: 'research',
  tags: ['kinetics', 'ozone', 'microbubble']
}

/**
 * Phase 7-T1: example data-visualization tool declaration.
 */
export const DATA_VISUALIZATION_TOOL: ToolDefinition = {
  id: 'tool:data-visualization',
  name: 'Data Visualization',
  description: 'Render scientific plots (kinetic curves, CFD contours, particle distributions)',
  category: 'visualization',
  version: '1.0.0',
  inputSchema: {
    fields: [
      { name: 'dataset', type: t('object'), required: true,
        description: 'A Dataset entity from the Knowledge Layer' },
      { name: 'plotType', type: t('string'), required: true,
        enum: ['kinetic-curve', 'CFD-contour', 'particle-distribution', 'spectrum'] },
      { name: 'outputPath', type: t('string'), required: false,
        description: 'Optional absolute path under <userData>/exports/' }
    ],
    required: ['dataset', 'plotType'],
    validationRules: ['outputPath must start with <userData>/exports/ (Phase 7-T+)']
  },
  outputSchema: {
    description: 'VisualizationResult { figureId, format, path }',
    fields: ['figureId', 'format', 'path']
  },
  executionTarget: 'local-service',
  permission: 'public',
  tags: ['visualization', 'plot', 'figure']
}

/**
 * Phase 7-T1: example dataset-export tool declaration.
 */
export const DATASET_EXPORT_TOOL: ToolDefinition = {
  id: 'tool:dataset-export',
  name: 'Dataset Export',
  description: 'Export a Dataset entity to CSV / JSON / Parquet',
  category: 'export',
  version: '1.0.0',
  inputSchema: {
    fields: [
      { name: 'dataset', type: t('object'), required: true,
        description: 'A Dataset entity from the Knowledge Layer' },
      { name: 'format', type: t('string'), required: true,
        enum: ['csv', 'json', 'parquet'] },
      { name: 'outputPath', type: t('string'), required: true,
        description: 'Absolute path under <userData>/exports/' }
    ],
    required: ['dataset', 'format', 'outputPath'],
    validationRules: ['outputPath must start with <userData>/exports/ (Phase 7-T+)']
  },
  outputSchema: {
    description: 'ExportResult { path, rowCount, format }',
    fields: ['path', 'rowCount', 'format']
  },
  executionTarget: 'application',
  permission: 'public',
  tags: ['export', 'csv', 'parquet']
}

/**
 * Phase 7-T1: array of all built-in tool declarations.
 * `initializeBuiltinTools()` registers each of these with the registry.
 */
export const BUILTIN_TOOLS: readonly ToolDefinition[] = Object.freeze([
  KINETIC_ANALYSIS_TOOL,
  DATA_VISUALIZATION_TOOL,
  DATASET_EXPORT_TOOL
])
