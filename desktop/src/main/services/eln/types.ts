// ELN Types — Phase 9-C

export type ELNEntryType = 'observation' | 'measurement' | 'calculation' | 'protocol' | 'conclusion' | 'note'

export type ELNReviewStatus = 'draft' | 'submitted' | 'approved' | 'rejected' | 'archived'

export interface ELNEntry {
  id: string
  experimentId: string
  type: ELNEntryType
  title: string
  content: string
  authorId: string | null
  status: ELNReviewStatus
  metadata: Record<string, unknown>
  version: number
  createdAt: number
  updatedAt: number
}

export interface ELNEntryVersion {
  version: number
  content: string
  authorId: string | null
  createdAt: number
}

export interface ELNReview {
  id: string
  entryId: string
  reviewerId: string | null
  decision: 'approve' | 'reject'
  comment: string | null
  createdAt: number
}

export type WorkflowTemplateSource = 'built-in' | 'user-template'

export interface WorkflowTemplateRecord {
  id: string
  name: string
  description: string
  category: string
  stepsJson: string
  schemaVersion: number
  builtIn: boolean
  createdBy: string | null
  version: number
  createdAt: number
  updatedAt: number
}

export interface RunRecord {
  id: string
  templateId: string
  templateName: string
  status: string
  currentStepId: string | null
  startedAt: number
  finishedAt: number | null
  startedBy: string | null
  parameters: Record<string, unknown>
  results: Record<string, unknown>
  source: WorkflowTemplateSource
}

export interface StepRecord {
  runId: string
  stepId: string
  state: string
  startedAt: number | null
  finishedAt: number | null
  result: unknown
  error: string | null
  attempt: number
}

export interface RunEventRecord {
  id: string
  runId: string
  stepId: string | null
  type: string
  at: number
  message: string
  payload: unknown
  sequence: number
}

export interface ELNService {
  createEntry(input: { experimentId: string; type: ELNEntryType; title: string; content: string; authorId?: string; metadata?: Record<string, unknown> }): ELNEntry
  getEntry(id: string): { entry: ELNEntry; history: ELNEntryVersion[]; reviews: ELNReview[] } | null
  listByExperiment(experimentId: string): ELNEntry[]
  updateEntry(id: string, content: string, authorId?: string): ELNEntry
  submitEntry(id: string, authorId?: string): ELNEntry
  approveEntry(id: string, reviewerId?: string, comment?: string): ELNEntry
  rejectEntry(id: string, reviewerId?: string, comment?: string): ELNEntry
  exportEntry(id: string, format: 'md'): string
}

export interface TemplateStoreService {
  createTemplate(input: { name: string; description: string; category: string; stepsJson: string; createdBy?: string }): WorkflowTemplateRecord
  listTemplates(userId?: string): WorkflowTemplateRecord[]
  getTemplate(id: string): WorkflowTemplateRecord | null
  updateTemplate(id: string, name: string, stepsJson: string): WorkflowTemplateRecord
  deleteTemplate(id: string): boolean
}

export interface RunStoreService {
  insertRun(run: Omit<RunRecord, never>): void
  updateRunStatus(runId: string, status: string, currentStepId: string | null, finishedAt: number | null): void
  upsertStep(step: StepRecord): void
  insertEvent(event: Omit<RunEventRecord, 'id' | 'sequence'>): void
  getRun(runId: string): { run: RunRecord; steps: StepRecord[]; events: RunEventRecord[] } | null
  listRuns(filter?: { startedBy?: string; templateId?: string; status?: string; limit?: number }): RunRecord[]
  recoverRunningRuns(): number
  pruneOldRuns(olderThanMs: number): number
}
