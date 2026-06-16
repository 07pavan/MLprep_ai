import {
  getProfile, getQualityReport, getMLReadiness,
  listDatasets, activateDataset, deleteDataset,
  getIntelligentPlan, getIntelligentPlanForDataset, getCleaningSummary,
  executeCleaningPlan, resetCleaningSession,
} from '../api/client'

export {
  // ML dashboard (Phase 1.5A)
  getProfile,
  getQualityReport,
  getMLReadiness,
  // Dataset registry
  listDatasets,
  activateDataset,
  deleteDataset,
  // Cleaning — Phase 2B executor
  executeCleaningPlan,
  resetCleaningSession,
  // Cleaning — Phase 2A planner (read-only)
  getIntelligentPlan,
  getIntelligentPlanForDataset,
  getCleaningSummary,
}
