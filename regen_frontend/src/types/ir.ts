export type TargetLanguage =
  | "python_fastapi"
  | "go"
  | "typescript"
  | "rust"
  | "csharp_dotnet";

export type ArchitecturalPattern =
  | "hexagonal"
  | "clean"
  | "modular_monolith"
  | "event_driven";

export type AmbiguityStatus = "unresolved" | "resolved" | "deprecated";

export interface IngestionMetrics {
  total_files_scanned: number;
  ast_nodes_parsed_deterministically: number;
  complex_chunks_sent_to_llm: number;
  estimated_tokens_saved: number;
  llm_tokens_consumed: number;
}

export interface EntityField {
  name: string;
  data_type: string;
  is_required: boolean;
  is_unique: boolean;
  is_primary_key: boolean;
}

export interface EntityDefinition {
  id: string;
  name: string;
  description: string;
  fields: EntityField[];
}

export interface BusinessRule {
  id: string;
  title: string;
  domain_context: string;
  trigger_condition: string;
  expected_behavior: string;
  cyclomatic_complexity_score?: number | null;
  is_ambiguous: boolean;
  confidence_score: number;
}

export interface RouteDefinition {
  id: string;
  path: string;
  method: string;
  summary: string;
}

export interface HITLQuestion {
  id: string;
  related_rule_id: string;
  question: string;
  legacy_code_snippet?: string | null;
  suggested_options: string[];
  user_response?: string | null;
  status: AmbiguityStatus;
}

export interface TechnicalConstraints {
  preferred_languages: TargetLanguage[];
  expected_concurrency_rps: number;
  io_heavy: boolean;
  cpu_heavy: boolean;
  database_preference: string;
  require_frontend: boolean;
  team_experience_notes?: string | null;
}

export interface ArchitectureDecision {
  chosen_backend_language: TargetLanguage;
  chosen_pattern: ArchitecturalPattern;
  chosen_database: string;
  chosen_frontend_stack?: string | null;
  ai_friendliness_score: number;
  rationale: string;
  container_services: string[];
}

export interface CharacterizationContract {
  id: string;
  target_route_id?: string | null;
  target_rule_id: string;
  scenario_name: string;
  given_input_payload: Record<string, unknown>;
  expected_output_payload: Record<string, unknown>;
  expected_side_effects: string[];
}

export interface ProjectIR {
  project_id: string;
  project_name: string;
  version: string;
  created_at: string;
  ingestion_metrics: IngestionMetrics;
  entities: EntityDefinition[];
  relationships: unknown[];
  business_rules: BusinessRule[];
  routes: RouteDefinition[];
  ui_views: unknown[];
  hitl_questions: HITLQuestion[];
  technical_constraints: TechnicalConstraints;
  architecture_decision?: ArchitectureDecision | null;
  characterization_tests: CharacterizationContract[];
}

export interface StackScoreBreakdown {
  language: TargetLanguage;
  recommended_pattern: ArchitecturalPattern;
  total_score: number;
  ai_friendliness_score: number;
  performance_fit_score: number;
  pros: string[];
  tradeoffs: string[];
}

export interface ArchitectRecommendationResponse {
  project_ir: ProjectIR;
  ready_for_scaffolding: boolean;
  selected_architecture: ArchitectureDecision;
  ranked_alternatives: StackScoreBreakdown[];
}

export interface GeneratedFile {
  path: string;
  language: string;
  category: string;
  content: string;
}

export interface ScaffoldManifest {
  project_id: string;
  project_name: string;
  chosen_stack: TargetLanguage;
  chosen_pattern: string;
  total_files_generated: number;
  files: GeneratedFile[];
}
