// Workflow Service Singleton — Phase 9-B
// Bootstrap + lazy getter.

import { bootstrapWorkflowService, getWorkflowService, resetWorkflowService } from './workflow/workflow-engine'
import type { WorkflowService } from './workflow/types'

export { getWorkflowService, resetWorkflowService, bootstrapWorkflowService }
export type { WorkflowService }
