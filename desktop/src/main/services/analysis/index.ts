// Analysis index — Phase 8-M1-D
export * from './types'
export { computeStatistics } from './statistics.service'
export { fitKinetic } from './kinetics.service'
export { fitRegression } from './regression.service'
export { computeCorrelation } from './correlation.service'
export { fitCurve } from './curve-fitting.service'
export { createAnalysisEngine, type AnalysisEngine } from './analysis-engine'
export { createLocalAnalysisEngineAdapter, type AnalysisEngineAdapter } from './adapter'