"use client";

import { useState } from "react";
import {
  ArchitectRecommendationResponse,
  DocUploadItem,
  GeneratedFile,
  HITLQuestion,
  ProjectIR,
  ScaffoldJobStatus,
  ScaffoldManifest,
  TargetFrontend,
  TargetLanguage,
  TechnicalConstraints,
} from "@/types/ir";
import {
  analyzeInputs,
  pollScaffoldJob,
  recommendStack,
  resolveHITLQuestions,
  startScaffoldJob,
  triggerInstantJobZipDownload,
} from "@/lib/api";
import { useDeviceCapacity } from "./useDeviceCapacity";

export function useRegenWizard() {
  const [activePhase, setActivePhase] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Hardware Auto-Detection Hook
  const { lowVramMode, setLowVramMode } = useDeviceCapacity(true);

  // Step 1 State
  const [projectName, setProjectName] = useState("ModernizedBillingPlatform");
  const [codeFiles, setCodeFiles] = useState<
    { file_path: string; content: string }[]
  >([]);
  const [docFiles, setDocFiles] = useState<DocUploadItem[]>([]);
  const [plainTextReqs, setPlainTextReqs] = useState(
    "- Customers have Invoices and Payments.\n- Invoices above $10,000 require dual manager approval.\n- I only know how to code in C and it cant be hexagonal structure.",
  );

  // Step 2 State
  const [projectIR, setProjectIR] = useState<ProjectIR | null>(null);
  const [hitlAnswers, setHitlAnswers] = useState<Record<string, string>>({});
  const [deprecatedFlags, setDeprecatedFlags] = useState<
    Record<string, boolean>
  >({});

  // Step 3 State
  const [constraints, setConstraints] = useState<TechnicalConstraints>({
    preferred_languages: [],
    preferred_frontend: "nextjs",
    expected_concurrency_rps: 200,
    io_heavy: true,
    cpu_heavy: false,
    database_preference: "postgresql",
    require_frontend: true,
    team_experience_notes: "",
  });
  const [overrideLang, setOverrideLang] = useState<TargetLanguage | "">("");
  const [selectedFrontend, setSelectedFrontend] =
    useState<TargetFrontend>("nextjs");
  const [archRec, setArchRec] =
    useState<ArchitectRecommendationResponse | null>(null);

  // Step 4 State
  const [buildJob, setBuildJob] = useState<ScaffoldJobStatus | null>(null);
  const [manifest, setManifest] = useState<ScaffoldManifest | null>(null);
  const [selectedFile, setSelectedFile] = useState<GeneratedFile | null>(null);

  // --- Helpers ---
  const fileToBase64 = (file: File): Promise<string> =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const res = String(reader.result || "");
        resolve(res.includes(",") ? res.split(",")[1] : res);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });

  const handleFilesAdded = async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    const newCode: { file_path: string; content: string }[] = [];
    const newDocs: DocUploadItem[] = [];

    for (const file of fileArray) {
      const path = file.webkitRelativePath || file.name;
      if (
        path.includes("/node_modules/") ||
        path.includes("/.git/") ||
        path.includes("/venv/") ||
        path.includes("/.venv/") ||
        path.includes("/__pycache__/") ||
        path.includes("/.next/") ||
        path.includes("/dist/") ||
        path.includes("/build/")
      ) {
        continue;
      }

      if (path.match(/\.(py|ts|tsx|js|jsx)$/i)) {
        const content = await file.text();
        newCode.push({ file_path: path, content });
      } else if (path.match(/\.(csv|json|md|txt)$/i)) {
        const text = await file.text();
        newDocs.push({
          file_path: path,
          text_content: text,
          sizeKb: (file.size / 1024).toFixed(1),
        });
      } else if (path.match(/\.(pdf|xlsx)$/i)) {
        const b64 = await fileToBase64(file);
        newDocs.push({
          file_path: path,
          base64_content: b64,
          sizeKb: (file.size / 1024).toFixed(1),
        });
      }
    }

    if (newCode.length > 0) setCodeFiles((prev) => [...prev, ...newCode]);
    if (newDocs.length > 0) setDocFiles((prev) => [...prev, ...newDocs]);
  };

  const handleClearFiles = () => {
    setCodeFiles([]);
    setDocFiles([]);
  };

  // --- API Orchestration ---
  const handleRunIngestion = async () => {
    if (
      codeFiles.length === 0 &&
      docFiles.length === 0 &&
      !plainTextReqs.trim()
    ) {
      setError(
        "Provide at least one input: legacy code files, a requirement document (.csv/.xlsx/.pdf), or a plain-text description.",
      );
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const ir = await analyzeInputs({
        project_name: projectName,
        code_files: codeFiles,
        document_files: docFiles,
        plain_text_requirements: plainTextReqs,
        low_vram_mode: lowVramMode,
      });
      setProjectIR(ir);

      const initialAnswers: Record<string, string> = {};
      ir.hitl_questions.forEach((q: HITLQuestion) => {
        if (q.suggested_options.length > 0) {
          initialAnswers[q.id] = q.suggested_options[0];
        }
      });
      setHitlAnswers(initialAnswers);
      setConstraints(ir.technical_constraints);
      setActivePhase(2);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to run ingestion");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmHITLAndProceed = async () => {
    if (!projectIR) return;
    setLoading(true);
    setError(null);
    try {
      if (projectIR.hitl_questions.length > 0) {
        const formattedAnswers = projectIR.hitl_questions.map(
          (q: HITLQuestion) => ({
            question_id: q.id,
            selected_option_or_custom_answer:
              hitlAnswers[q.id] || "Preserve legacy behavior",
            mark_rule_deprecated: Boolean(deprecatedFlags[q.id]),
          }),
        );
        const resolved = await resolveHITLQuestions(
          projectIR,
          formattedAnswers,
        );
        setProjectIR(resolved);
      }
      setActivePhase(3);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to resolve HITL rules",
      );
    } finally {
      setLoading(false);
    }
  };

  const handleRecommendStack = async () => {
    if (!projectIR) return;
    setLoading(true);
    setError(null);
    try {
      const chosenBe = overrideLang ? (overrideLang as TargetLanguage) : null;
      const updatedConstraints: TechnicalConstraints = {
        ...constraints,
        preferred_frontend: selectedFrontend,
        require_frontend: selectedFrontend !== "none",
      };

      const rec = await recommendStack(
        projectIR,
        updatedConstraints,
        chosenBe,
        selectedFrontend,
      );
      setProjectIR(rec.project_ir);
      setArchRec(rec);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed in Stack Advisor");
    } finally {
      setLoading(false);
    }
  };

  const handleStartAsyncScaffold = async () => {
    if (!projectIR) return;
    setError(null);
    setManifest(null);
    setActivePhase(4);

    try {
      const initialJob = await startScaffoldJob(projectIR);
      setBuildJob(initialJob);

      const interval = setInterval(async () => {
        try {
          const status = await pollScaffoldJob(initialJob.job_id);
          setBuildJob(status);

          if (status.status === "ready" && status.manifest) {
            clearInterval(interval);
            setManifest(status.manifest);
            if (status.manifest.files.length > 0) {
              setSelectedFile(status.manifest.files[0]);
            }
          } else if (status.status === "failed") {
            clearInterval(interval);
            setError(status.error || "Background project build failed.");
          }
        } catch (pollErr: unknown) {
          clearInterval(interval);
          setError(
            pollErr instanceof Error
              ? pollErr.message
              : "Lost connection to build job",
          );
        }
      }, 1000);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to start build job",
      );
    }
  };

  return {
    // General State
    activePhase,
    setActivePhase,
    loading,
    error,
    setError,
    lowVramMode,
    setLowVramMode,

    // Phase 1
    projectName,
    setProjectName,
    codeFiles,
    docFiles,
    plainTextReqs,
    setPlainTextReqs,
    handleFilesAdded,
    handleClearFiles,
    handleRunIngestion,

    // Phase 2
    projectIR,
    hitlAnswers,
    setHitlAnswers,
    deprecatedFlags,
    setDeprecatedFlags,
    handleConfirmHITLAndProceed,

    // Phase 3
    constraints,
    setConstraints,
    overrideLang,
    setOverrideLang,
    selectedFrontend,
    setSelectedFrontend,
    archRec,
    handleRecommendStack,

    // Phase 4
    buildJob,
    manifest,
    selectedFile,
    setSelectedFile,
    handleStartAsyncScaffold,
    triggerInstantJobZipDownload,
  };
}
