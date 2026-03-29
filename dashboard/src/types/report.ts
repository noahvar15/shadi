export interface DiagnosisCandidate {
  /** Rank within the differential (1 = highest confidence). */
  rank: number
  /** Human-readable diagnosis name — matches backend DiagnosisCandidate.display. */
  display: string
  /** SNOMED CT code (may be null for evidence-gap entries). */
  snomed_code?: string | null
  confidence: number
  next_steps: string[]
  supporting_evidence: Evidence[]
  /** Metadata flags such as "EVIDENCE_GAP". */
  flags: string[]
}

export interface Evidence {
  source: string
  excerpt: string
  relevance_score: number
}

export interface DifferentialReport {
  case_id: string
  /** Pipeline status — drives polling stop condition in the report page. */
  status: string
  top_diagnoses: DiagnosisCandidate[]
  consensus_level: number
  divergent_agents: string[]
  vetoed_recommendations: VetoedItem[]
  /** ISO timestamp — populated when status is 'complete'. */
  completed_at?: string | null
  /** Error details when the pipeline failed. */
  error_message?: string | null
}

export interface VetoedItem {
  recommendation: string
  vetoed: boolean
  reason?: string | null
  contraindication_codes: string[]
}
