"use client";

import React, { useState, useRef } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Code2,
  Cpu,
  Download,
  FileCode,
  Layers,
  Loader2,
  Play,
  ShieldCheck,
  Sparkles,
  Terminal,
  UploadCloud,
} from "lucide-react";
import {
  ArchitectRecommendationResponse,
  GeneratedFile,
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

export default function RegenWizardPage() {
  const [activePhase, setActivePhase] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Phase 1 State
  const [projectName, setProjectName] = useState("LegacyBillingApp");
  const [localFiles, setLocalFiles] = useState<
    { file_path: string; content: string }[]
  >([]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [plainTextReqs, setPlainTextReqs] = useState(
    "- Invoices above $10,000 require dual manager approval.\n- Support multi-currency tax calculation.",
  );

  // Phase 2 & 3 State (Separate Backend & Frontend Selectors!)
  const [projectIR, setProjectIR] = useState<ProjectIR | null>(null);
  const [hitlAnswers, setHitlAnswers] = useState<Record<string, string>>({});
  const [deprecatedFlags, setDeprecatedFlags] = useState<
    Record<string, boolean>
  >({});
  const [constraints, setConstraints] = useState<TechnicalConstraints>({
    preferred_languages: [],
    preferred_frontend: "nextjs",
    expected_concurrency_rps: 1200,
    io_heavy: true,
    cpu_heavy: false,
    database_preference: "postgresql",
    require_frontend: true,
  });
  const [overrideLang, setOverrideLang] = useState<TargetLanguage | "">("");
  const [selectedFrontend, setSelectedFrontend] =
    useState<TargetFrontend>("nextjs");
  const [archRec, setArchRec] =
    useState<ArchitectRecommendationResponse | null>(null);

  // Phase 4 Async Build Job & Explorer State
  const [buildJob, setBuildJob] = useState<ScaffoldJobStatus | null>(null);
  const [manifest, setManifest] = useState<ScaffoldManifest | null>(null);
  const [selectedFile, setSelectedFile] = useState<GeneratedFile | null>(null);

  const handleFilesAdded = async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    const validFiles: { file_path: string; content: string }[] = [];

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
      if (path.match(/\.(py|ts|tsx|js|jsx)$/)) {
        const content = await file.text();
        validFiles.push({ file_path: path, content });
      }
    }
    setLocalFiles((prev) => [...prev, ...validFiles]);
  };

  async function handleRunIngestion() {
    if (localFiles.length === 0) {
      setError(
        "Please drop at least one legacy code file or folder to analyze.",
      );
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const ir = await analyzeInputs({
        project_name: projectName,
        code_files: localFiles,
        plain_text_requirements: plainTextReqs,
      });
      setProjectIR(ir);

      const initialAnswers: Record<string, string> = {};
      ir.hitl_questions.forEach((q) => {
        if (q.suggested_options.length > 0) {
          initialAnswers[q.id] = q.suggested_options[0];
        }
      });
      setHitlAnswers(initialAnswers);
      setActivePhase(2);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to run ingestion");
    } finally {
      setLoading(false);
    }
  }

  async function handleResolveAndRecommend(
    customBackend?: TargetLanguage,
    customFrontend?: TargetFrontend,
  ) {
    if (!projectIR) return;
    setLoading(true);
    setError(null);
    try {
      const formattedAnswers = projectIR.hitl_questions.map((q) => ({
        question_id: q.id,
        selected_option_or_custom_answer:
          hitlAnswers[q.id] || "Preserve legacy behavior",
        mark_rule_deprecated: Boolean(deprecatedFlags[q.id]),
      }));

      const resolvedIR = await resolveHITLQuestions(
        projectIR,
        formattedAnswers,
      );
      const chosenBe =
        customBackend !== undefined
          ? customBackend
          : overrideLang
            ? (overrideLang as TargetLanguage)
            : null;
      const chosenFe =
        customFrontend !== undefined ? customFrontend : selectedFrontend;

      const updatedConstraints: TechnicalConstraints = {
        ...constraints,
        preferred_frontend: chosenFe,
        require_frontend: chosenFe !== "none",
      };

      const rec = await recommendStack(
        resolvedIR,
        updatedConstraints,
        chosenBe,
        chosenFe,
      );
      setProjectIR(rec.project_ir);
      setArchRec(rec);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed in Architect phase",
      );
    } finally {
      setLoading(false);
    }
  }

  // Starts the Async CLI Background Builder & Polls Progress until ZIP is Ready
  async function handleStartAsyncScaffold() {
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
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur px-6 py-4 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-emerald-500/10 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight flex items-center gap-2">
              REGEN
              <span className="text-xs font-mono uppercase px-2 py-0.5 rounded bg-slate-800 text-emerald-400 border border-slate-700">
                CLI-Driven Pipeline
              </span>
            </h1>
            <p className="text-xs text-slate-400">
              Deterministic AST & Official CLI Legacy Modernization Scaffolder
            </p>
          </div>
        </div>

        <nav className="flex items-center gap-2 text-xs font-medium">
          {[
            { step: 1, label: "1. Ingestion" },
            { step: 2, label: "2. IR Blueprint" },
            { step: 3, label: "3. HITL & Tech Stacks" },
            { step: 4, label: "4 & 5. Builder & ZIP" },
          ].map((item) => (
            <button
              key={item.step}
              onClick={() => projectIR && setActivePhase(item.step)}
              disabled={item.step > 1 && !projectIR}
              className={`px-3 py-1.5 rounded-md border transition ${
                activePhase === item.step
                  ? "bg-emerald-500/20 border-emerald-500 text-emerald-300"
                  : "bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700 disabled:opacity-40"
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </header>

      {error && (
        <div className="mx-6 mt-4 p-3 rounded-lg bg-red-950/60 border border-red-800 text-red-200 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-xs underline ml-4"
          >
            Dismiss
          </button>
        </div>
      )}

      <main className="flex-1 p-6 max-w-7xl w-full mx-auto">
        {/* PHASE 1: DRAG & DROP FOLDER INGESTION */}
        {activePhase === 1 && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4 bg-slate-900/50 border border-slate-800 rounded-xl p-6">
              <h2 className="text-base font-semibold flex items-center gap-2">
                <Code2 className="h-5 w-5 text-emerald-400" />
                Phase 1: Legacy Repository Ingestion
              </h2>

              <div>
                <label className="block text-xs text-slate-400 mb-1">
                  Project Name
                </label>
                <input
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  className="w-full max-w-sm bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm"
                />
              </div>

              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragging(false);
                  handleFilesAdded(e.dataTransfer.files);
                }}
                onClick={() => fileInputRef.current?.click()}
                className={`w-full mt-4 border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-colors ${
                  isDragging
                    ? "border-emerald-500 bg-emerald-500/10"
                    : "border-slate-700 bg-slate-950 hover:border-slate-500"
                }`}
              >
                <UploadCloud className="h-10 w-10 mb-3 text-emerald-400" />
                <p className="text-sm font-medium text-slate-200">
                  Drag & Drop your legacy project folder here (or click to
                  browse)
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  Automatically filters out node_modules, .git, venv, and build
                  artifacts
                </p>
                <input
                  type="file"
                  multiple
                  // @ts-expect-error - non-standard directory selection attribute
                  webkitdirectory="true"
                  directory="true"
                  ref={fileInputRef}
                  onChange={(e) => {
                    if (e.target.files) handleFilesAdded(e.target.files);
                  }}
                  className="hidden"
                />
              </div>

              {localFiles.length > 0 && (
                <div className="mt-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-slate-400">
                      Loaded Source Files ({localFiles.length})
                    </span>
                    <button
                      onClick={() => setLocalFiles([])}
                      className="text-xs text-rose-400 hover:underline"
                    >
                      Clear All
                    </button>
                  </div>
                  <div className="max-h-40 overflow-y-auto bg-slate-950 border border-slate-800 rounded-lg p-2 space-y-1">
                    {localFiles.map((f, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between text-[11px] font-mono text-slate-300 bg-slate-900/50 px-2 py-1 rounded"
                      >
                        <span className="truncate">{f.file_path}</span>
                        <span className="text-slate-500 ml-4">
                          {(f.content.length / 1024).toFixed(1)} KB
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="space-y-4 bg-slate-900/50 border border-slate-800 rounded-xl p-6 flex flex-col justify-between">
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-slate-200">
                  Plain-Text Business Requirements
                </h3>
                <textarea
                  rows={8}
                  value={plainTextReqs}
                  onChange={(e) => setPlainTextReqs(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs font-mono"
                />
              </div>

              <button
                onClick={handleRunIngestion}
                disabled={loading || localFiles.length === 0}
                className="w-full py-3 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold text-sm flex items-center justify-center gap-2 disabled:opacity-50"
              >
                <Play className="h-4 w-4 fill-current" />
                {loading
                  ? "Running tree-sitter & tiktoken..."
                  : "Run Phase 1 AST Analysis"}
              </button>
            </div>
          </div>
        )}

        {/* PHASE 2: IR BLUEPRINT */}
        {activePhase === 2 && projectIR && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-4">
                <span className="text-xs text-slate-400">
                  AST Nodes Parsed Deterministically
                </span>
                <p className="text-2xl font-bold text-emerald-400 mt-1">
                  {
                    projectIR.ingestion_metrics
                      .ast_nodes_parsed_deterministically
                  }
                </p>
              </div>
              <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-4">
                <span className="text-xs text-slate-400">
                  Complex Chunks Routed to LLM
                </span>
                <p className="text-2xl font-bold text-amber-400 mt-1">
                  {projectIR.ingestion_metrics.complex_chunks_sent_to_llm}
                </p>
              </div>
              <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-4">
                <span className="text-xs text-slate-400">Tokens Saved</span>
                <p className="text-2xl font-bold text-emerald-300 mt-1">
                  {projectIR.ingestion_metrics.estimated_tokens_saved.toLocaleString()}
                </p>
              </div>
              <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-4">
                <span className="text-xs text-slate-400">
                  Unresolved HITL Ambiguities
                </span>
                <p className="text-2xl font-bold text-rose-400 mt-1">
                  {
                    projectIR.hitl_questions.filter(
                      (q) => q.status === "unresolved",
                    ).length
                  }
                </p>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => setActivePhase(3)}
                className="px-6 py-3 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm"
              >
                Proceed to Phase 3: HITL & Separate Stack Selection
              </button>
            </div>
          </div>
        )}

        {/* PHASE 3: HITL + SEPARATE BACKEND & FRONTEND STACK SELECTION */}
        {activePhase === 3 && projectIR && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Step 3A: HITL */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 space-y-4">
              <h3 className="text-base font-semibold flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-amber-400" />
                Step 3A: Human-in-the-Loop Ambiguity Resolution
              </h3>
              {projectIR.hitl_questions.map((q) => (
                <div
                  key={q.id}
                  className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-3"
                >
                  <p className="text-sm font-medium text-slate-200">
                    {q.question}
                  </p>
                  {q.legacy_code_snippet && (
                    <pre className="p-3 rounded bg-slate-900 border border-slate-800 text-[11px] font-mono text-amber-200 overflow-x-auto">
                      {q.legacy_code_snippet}
                    </pre>
                  )}
                  <div className="space-y-1.5">
                    {q.suggested_options.map((opt) => (
                      <label
                        key={opt}
                        className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer"
                      >
                        <input
                          type="radio"
                          name={q.id}
                          checked={hitlAnswers[q.id] === opt}
                          onChange={() =>
                            setHitlAnswers({ ...hitlAnswers, [q.id]: opt })
                          }
                        />
                        {opt}
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Step 3B: Decoupled Backend & Frontend Tech Selection */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 space-y-5">
              <h3 className="text-base font-semibold flex items-center gap-2">
                <Cpu className="h-5 w-5 text-sky-400" />
                Step 3B: Independent Backend & Frontend Stack Selection
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div>
                  <label className="block text-slate-400 mb-1 font-semibold">
                    1. Backend Stack (Auto or Override)
                  </label>
                  <select
                    value={overrideLang}
                    onChange={(e) =>
                      setOverrideLang(e.target.value as TargetLanguage | "")
                    }
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs"
                  >
                    <option value="">Auto-Recommend from Workload</option>
                    <option value="python_fastapi">Python (FastAPI)</option>
                    <option value="go">Go (go mod + Hexagonal HTTP)</option>
                    <option value="typescript">TypeScript (Node/tsx)</option>
                    <option value="csharp_dotnet">
                      C# (.NET 8 WebAPI CLI)
                    </option>
                    <option value="rust">Rust (Cargo + Axum)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 font-semibold">
                    2. Frontend Framework (Independent)
                  </label>
                  <select
                    value={selectedFrontend}
                    onChange={(e) =>
                      setSelectedFrontend(e.target.value as TargetFrontend)
                    }
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-emerald-300 font-medium"
                  >
                    <option value="nextjs">
                      Next.js (create-next-app CLI)
                    </option>
                    <option value="react_vite">
                      React + Vite (create-vite CLI)
                    </option>
                    <option value="vue_vite">
                      Vue 3 + Vite (create-vite CLI)
                    </option>
                    <option value="sveltekit">SvelteKit (sv create CLI)</option>
                    <option value="angular">Angular (@angular/cli new)</option>
                    <option value="none">
                      None (Headless Backend API Only)
                    </option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-xs">
                <div>
                  <label className="block text-slate-400 mb-1">
                    Concurrency:{" "}
                    <span className="text-emerald-400 font-mono">
                      {constraints.expected_concurrency_rps} RPS
                    </span>
                  </label>
                  <input
                    type="range"
                    min={50}
                    max={3000}
                    step={50}
                    value={constraints.expected_concurrency_rps}
                    onChange={(e) =>
                      setConstraints({
                        ...constraints,
                        expected_concurrency_rps: Number(e.target.value),
                      })
                    }
                    className="w-full"
                  />
                </div>
                <div className="flex items-center gap-4 pt-4">
                  <label className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={constraints.io_heavy}
                      onChange={(e) =>
                        setConstraints({
                          ...constraints,
                          io_heavy: e.target.checked,
                        })
                      }
                    />
                    I/O Heavy
                  </label>
                  <label className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={constraints.cpu_heavy}
                      onChange={(e) =>
                        setConstraints({
                          ...constraints,
                          cpu_heavy: e.target.checked,
                        })
                      }
                    />
                    CPU Heavy
                  </label>
                </div>
              </div>

              <button
                onClick={() => handleResolveAndRecommend()}
                disabled={loading}
                className="w-full py-3 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-sm"
              >
                {loading
                  ? "Evaluating Architecture..."
                  : "Save HITL & Lock Tech Stacks"}
              </button>

              {archRec && (
                <div className="space-y-3 pt-4 border-t border-slate-800">
                  <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-500/30 text-xs space-y-1.5">
                    <div className="font-bold text-emerald-400 text-sm flex justify-between">
                      <span>
                        Backend:{" "}
                        {archRec.selected_architecture.chosen_backend_language}{" "}
                        | Frontend:{" "}
                        {archRec.selected_architecture.chosen_frontend_stack}
                      </span>
                      <span>
                        AI:{" "}
                        {archRec.selected_architecture.ai_friendliness_score}
                        /100
                      </span>
                    </div>
                    <p className="text-slate-300">
                      {archRec.selected_architecture.rationale}
                    </p>
                  </div>

                  {archRec.ready_for_scaffolding && (
                    <button
                      onClick={handleStartAsyncScaffold}
                      className="w-full py-4 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-base flex items-center justify-center gap-2 shadow-xl shadow-emerald-500/20"
                    >
                      <ShieldCheck className="h-5 w-5" />
                      Run CLI Project Builder & Pre-Build ZIP
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* PHASE 4 & 5: ASYNC LOADING SCREEN -> CODE EXPLORER & INSTANT ZIP DOWNLOAD */}
        {activePhase === 4 && (
          <div className="space-y-6">
            {/* LOADING SCREEN WHILE BACKGROUND CLI BUILDER RUNS */}
            {buildJob && buildJob.status === "processing" && (
              <div className="max-w-2xl mx-auto my-12 p-8 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-6 text-center shadow-2xl">
                <Loader2 className="h-12 w-12 text-emerald-400 animate-spin mx-auto" />
                <div className="space-y-2">
                  <h2 className="text-lg font-bold text-slate-100">
                    Building Your Kick-Starter Project in Background...
                  </h2>
                  <p className="text-xs font-mono text-emerald-400">
                    {buildJob.current_step}
                  </p>
                </div>

                {/* Progress Bar */}
                <div className="w-full bg-slate-950 rounded-full h-3 overflow-hidden border border-slate-800">
                  <div
                    className="bg-emerald-500 h-full transition-all duration-500"
                    style={{ width: `${buildJob.progress_pct}%` }}
                  />
                </div>

                {/* Live Step Log */}
                <div className="text-left bg-slate-950 border border-slate-800 rounded-lg p-3 font-mono text-[11px] text-slate-400 space-y-1 max-h-40 overflow-y-auto">
                  {buildJob.logs.map((logItem, idx) => (
                    <div key={idx}>&gt; {logItem}</div>
                  ))}
                </div>
              </div>
            )}

            {/* READY STATE: PRE-BUILT ZIP DOWNLOAD + FILE EXPLORER */}
            {manifest && buildJob?.status === "ready" && (
              <>
                <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-900/70 border border-slate-800 rounded-xl p-5">
                  <div>
                    <h2 className="text-lg font-bold text-emerald-400 flex items-center gap-2">
                      <CheckCircle2 className="h-5 w-5" />
                      {manifest.project_name} — Pre-Built & Ready
                    </h2>
                    <div className="flex items-center gap-3 mt-2 text-xs text-slate-400 font-mono">
                      <span className="bg-slate-800 px-2 py-1 rounded">
                        Backend:{" "}
                        <span className="text-slate-200">
                          {manifest.chosen_stack}
                        </span>
                      </span>
                      <span className="bg-slate-800 px-2 py-1 rounded">
                        Frontend:{" "}
                        <span className="text-emerald-300">
                          {manifest.chosen_frontend}
                        </span>
                      </span>
                      <span className="bg-slate-800 px-2 py-1 rounded text-sky-300">
                        {manifest.total_files_generated} files
                      </span>
                    </div>
                  </div>

                  <button
                    onClick={() =>
                      triggerInstantJobZipDownload(buildJob.job_id)
                    }
                    className="px-6 py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm flex items-center gap-2 shadow-xl shadow-emerald-500/20"
                  >
                    <Download className="h-5 w-5" />
                    Instant Download (.zip)
                  </button>
                </div>

                {/* File Explorer */}
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 h-[560px]">
                  <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3 overflow-y-auto space-y-1">
                    <span className="block text-xs font-bold text-slate-400 px-2 py-1 uppercase">
                      Project Files ({manifest.files.length})
                    </span>
                    {manifest.files.map((file) => (
                      <button
                        key={file.path}
                        onClick={() => setSelectedFile(file)}
                        className={`w-full text-left px-3 py-2 rounded-lg text-xs font-mono flex items-center justify-between transition ${
                          selectedFile?.path === file.path
                            ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                            : "text-slate-300 hover:bg-slate-800"
                        }`}
                      >
                        <span className="truncate flex items-center gap-2">
                          <FileCode className="h-3.5 w-3.5 shrink-0 text-slate-500" />
                          {file.path}
                        </span>
                      </button>
                    ))}
                  </div>

                  <div className="lg:col-span-3 bg-slate-950 border border-slate-800 rounded-xl flex flex-col overflow-hidden">
                    {selectedFile && (
                      <>
                        <div className="px-4 py-2.5 border-b border-slate-800 bg-slate-900/80 flex items-center justify-between text-xs font-mono">
                          <span className="text-emerald-300">
                            {selectedFile.path}
                          </span>
                          <span className="text-slate-500 uppercase text-[10px]">
                            {selectedFile.language} | {selectedFile.category}
                          </span>
                        </div>
                        <pre className="p-5 text-xs font-mono text-slate-300 overflow-auto flex-1 leading-relaxed">
                          <code>{selectedFile.content}</code>
                        </pre>
                      </>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
