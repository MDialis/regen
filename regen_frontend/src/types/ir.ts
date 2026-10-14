// Add to src/types/ir.ts
export type TargetFrontend =
  | "nextjs"
  | "react_vite"
  | "vue_vite"
  | "sveltekit"
  | "angular"
  | "none";

// Update TechnicalConstraints:
export interface TechnicalConstraints {
  preferred_languages: TargetLanguage[];
  preferred_frontend?: TargetFrontend | null;
  expected_concurrency_rps: number;
  io_heavy: boolean;
  cpu_heavy: boolean;
  database_preference: string;
  require_frontend: boolean;
  team_experience_notes?: string | null;
}

// Update ArchitectureDecision:
export interface ArchitectureDecision {
  chosen_backend_language: TargetLanguage;
  chosen_pattern: ArchitecturalPattern;
  chosen_database: string;
  chosen_frontend_stack: TargetFrontend;
  ai_friendliness_score: number;
  rationale: string;
  container_services: string[];
}

// Update ScaffoldManifest:
export interface ScaffoldManifest {
  project_id: string;
  project_name: string;
  chosen_stack: TargetLanguage;
  chosen_frontend: TargetFrontend;
  chosen_pattern: string;
  cli_commands_executed: string[];
  total_files_generated: number;
  files: GeneratedFile[];
}

export interface ScaffoldJobStatus {
  job_id: string;
  status: "processing" | "ready" | "failed";
  progress_pct: number;
  current_step: string;
  logs: string[];
  error?: string | null;
  manifest?: ScaffoldManifest | null;
}
