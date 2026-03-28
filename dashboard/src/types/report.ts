export interface DiagnosisCandidate {
  diagnosis: string
  icd_code?: string
  confidence: number
  reasoning_trace: string[]
  next_steps: string[]
  supporting_evidence: Evidence[]
}

export interface Evidence {
  source: string
  excerpt: string
  relevance_score: number
}

export interface DifferentialReport {
  case_id: string
  status: 'queued' | 'running' | 'complete' | 'failed'
  top_diagnoses: DiagnosisCandidate[]
  consensus_level: number
  divergent_agents: string[]
  vetoed_recommendations: VetoedItem[]
  created_at: string
  completed_at?: string
}

export interface VetoedItem {
  recommendation: string
  reason: string
}
