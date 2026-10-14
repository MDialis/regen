// src/lib/api.ts
import {
  ArchitectRecommendationResponse,
  ProjectIR,
  ScaffoldJobStatus,
  TargetFrontend,
  TargetLanguage,
  TechnicalConstraints,
} from "@/types/ir";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function analyzeInputs(payload: {
  project_name: string;
  code_files: { file_path: string; content: string }[];
  plain_text_requirements?: string;
}): Promise<ProjectIR> {
  const res = await fetch(`${API_BASE}/ingestion/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function resolveHITLQuestions(
  project_ir: ProjectIR,
  answers: {
    question_id: string;
    selected_option_or_custom_answer: string;
    mark_rule_deprecated: boolean;
  }[],
): Promise<ProjectIR> {
  const res = await fetch(`${API_BASE}/architect/resolve-hitl`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_ir, answers }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function recommendStack(
  project_ir: ProjectIR,
  constraints: TechnicalConstraints,
  override_language?: TargetLanguage | null,
  override_frontend?: TargetFrontend | null,
): Promise<ArchitectRecommendationResponse> {
  const res = await fetch(`${API_BASE}/architect/recommend-stack`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_ir,
      constraints,
      override_language: override_language || null,
      override_frontend: override_frontend || null,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function startScaffoldJob(
  project_ir: ProjectIR,
): Promise<ScaffoldJobStatus> {
  const res = await fetch(`${API_BASE}/scaffolder/start-job`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(project_ir),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function pollScaffoldJob(
  jobId: string,
): Promise<ScaffoldJobStatus> {
  const res = await fetch(`${API_BASE}/scaffolder/jobs/${jobId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function triggerInstantJobZipDownload(jobId: string): void {
  // Hits the pre-built in-memory ZIP endpoint directly for an instant browser download
  window.location.href = `${API_BASE}/scaffolder/jobs/${jobId}/download`;
}
