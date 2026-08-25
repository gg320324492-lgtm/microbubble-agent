// ELN Service Singleton — Phase 9-C
// Bootstrap + lazy getter for ELN engine + template store + run store.

import { createTemplateStoreService, type TemplateStoreService } from './eln/template-store'
import { createRunStoreService, type RunStoreService } from './eln/run-store'
import { createELNEngine, type ELNService } from './eln/eln-engine'
import type { DatabaseService } from './database.service'

export interface ELNProductService {
  eln: ELNService
  templates: TemplateStoreService
  runs: RunStoreService
}

class ELNProductServiceImpl implements ELNProductService {
  readonly eln: ELNService
  readonly templates: TemplateStoreService
  readonly runs: RunStoreService

  constructor(getService: () => DatabaseService | null) {
    this.eln = createELNEngine(getService)
    this.templates = createTemplateStoreService(getService)
    this.runs = createRunStoreService(getService)
  }
}

let serviceInstance: ELNProductService | null = null

export function bootstrapELNProductService(getService: () => DatabaseService | null): ELNProductService {
  if (serviceInstance) return serviceInstance
  serviceInstance = new ELNProductServiceImpl(getService)
  return serviceInstance
}

export function getELNProductService(): ELNProductService | null {
  return serviceInstance
}

export function resetELNProductService(): void {
  serviceInstance = null
}
