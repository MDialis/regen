import {
  ArchitectRecommendationResponse,
  ProjectIR,
  ScaffoldManifest,
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

export async function scanLocalDirectory(payload: {
  project_name: string;
  directory_path: string;
  plain_text_requirements?: string;
}): Promise<ProjectIR> {
  const res = await fetch(`${API_BASE}/ingestion/scan-directory`, {
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
): Promise<ArchitectRecommendationResponse> {
  const res = await fetch(`${API_BASE}/architect/recommend-stack`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_ir,
      constraints,
      override_language: override_language || null,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function previewScaffold(
  project_ir: ProjectIR,
): Promise<ScaffoldManifest> {
  const res = await fetch(`${API_BASE}/scaffolder/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(project_ir),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function downloadScaffoldZip(
  project_ir: ProjectIR,
): Promise<void> {
  const res = await fetch(`${API_BASE}/scaffolder/download-zip`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(project_ir),
  });
  if (!res.ok) throw new Error(await res.text());

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  const slug = project_ir.project_name.toLowerCase().replace(/\s+/g, "_");
  link.setAttribute("download", `${slug}_kickstarter.zip`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
