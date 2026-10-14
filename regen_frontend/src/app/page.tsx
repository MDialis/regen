// src/app/page.tsx
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
  Play,
  ShieldCheck,
  Sparkles,
  Terminal,
  UploadCloud,
  X,
} from "lucide-react";
import {
  ArchitectRecommendationResponse,
  GeneratedFile,
  ProjectIR,
  ScaffoldManifest,
  TargetLanguage,
  TechnicalConstraints,
} from "@/types/ir";
import {
  analyzeInputs,
  downloadScaffoldZip,
  previewScaffold,
  recommendStack,
  resolveHITLQuestions,
} from "@/lib/api";

export default function RegenWizardPage() {
  const [activePhase, setActivePhase] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Phase 1 State (Upgraded UX)
  const [projectName, setProjectName] = useState("LegacyBillingApp");
  const [localFiles, setLocalFiles] = useState<
    { file_path: string; content: string }[]
  >([]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [plainTextReqs, setPlainTextReqs] = useState(
    "- Invoices above $10,000 require dual manager approval.\n- Support multi-currency tax calculation.",
  );

  // Phase 2 & 3 State
  const [projectIR, setProjectIR] = useState<ProjectIR | null>(null);
  const [hitlAnswers, setHitlAnswers] = useState<Record<string, string>>({});
  const [deprecatedFlags, setDeprecatedFlags] = useState<
    Record<string, boolean>
  >({});
  const [constraints, setConstraints] = useState<TechnicalConstraints>({
    preferred_languages: [],
    expected_concurrency_rps: 1200,
    io_heavy: true,
    cpu_heavy: false,
    database_preference: "postgresql",
    require_frontend: true,
  });
  const [overrideLang, setOverrideLang] = useState<TargetLanguage | "">("");
  const [archRec, setArchRec] =
    useState<ArchitectRecommendationResponse | null>(null);

  // Phase 4 & 5 State
  const [manifest, setManifest] = useState<ScaffoldManifest | null>(null);
  const [selectedFile, setSelectedFile] = useState<GeneratedFile | null>(null);

  // =====================================================================
  // Upgraded Folder Reading Logic
  // =====================================================================
  const handleFilesAdded = async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    const validFiles: { file_path: string; content: string }[] = [];

    for (const file of fileArray) {
      // webkitRelativePath contains the folder structure if a folder was selected
      const path = file.webkitRelativePath || file.name;

      // Filter out common build/dependency folders to save memory
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

      // Only parse supported code extensions
      if (path.match(/\.(py|ts|tsx|js|jsx)$/)) {
        const content = await file.text();
        validFiles.push({ file_path: path, content });
      }
    }
    setLocalFiles((prev) => [...prev, ...validFiles]);
  };

  // =====================================================================
  // Pipeline Handlers
  // =====================================================================
  async function handleRunIngestion() {
    if (localFiles.length === 0) {
      setError("Please add at least one legacy code file to analyze.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      // Use the unified analyze endpoint with the files we read into browser memory
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

  async function handleResolveAndRecommend(customOverride?: TargetLanguage) {
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
      const chosenOverride =
        customOverride !== undefined
          ? customOverride
          : overrideLang
            ? (overrideLang as TargetLanguage)
            : null;

      const rec = await recommendStack(resolvedIR, constraints, chosenOverride);
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

  async function handleGenerateScaffold() {
    if (!projectIR) return;
    setLoading(true);
    setError(null);
    try {
      const res = await previewScaffold(projectIR);
      setManifest(res);
      if (res.files.length > 0) {
        setSelectedFile(res.files[0]);
      }
      setActivePhase(4);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to scaffold project",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleDownloadZip() {
    if (!projectIR) return;
    setLoading(true);
    try {
      await downloadScaffoldZip(projectIR);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "ZIP download failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Header */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur px-6 py-4 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-emerald-500/10 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight flex items-center gap-2">
              REGEN
              <span className="text-xs font-mono uppercase px-2 py-0.5 rounded bg-slate-800 text-emerald-400 border border-slate-700">
                v0.1.0 Pipeline
              </span>
            </h1>
            <p className="text-xs text-slate-400">
              Deterministic AST & AI-Driven Legacy Modernization Scaffolder
            </p>
          </div>
        </div>

        {/* Phase Stepper */}
        <nav className="flex items-center gap-2 text-xs font-medium">
          {[
            { step: 1, label: "1. Ingestion" },
            { step: 2, label: "2. IR Blueprint" },
            { step: 3, label: "3. HITL & Architect" },
            { step: 4, label: "4 & 5. Kick-Starter" },
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

      {/* Error Banner */}
      {error && (
        <div className="mx-6 mt-4 p-3 rounded-lg bg-red-950/60 border border-red-800 text-red-200 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-xs underline ml-4 hover:text-white"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main Content Container */}
      <main className="flex-1 p-6 max-w-7xl w-full mx-auto">
        {/* ================================================================
            PHASE 1: MULTI-MODAL INGESTION
           ================================================================ */}
        {activePhase === 1 && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4 bg-slate-900/50 border border-slate-800 rounded-xl p-6">
              <h2 className="text-base font-semibold flex items-center gap-2">
                <Code2 className="h-5 w-5 text-emerald-400" />
                Phase 1: Legacy Source Ingestion
              </h2>

              <div>
                <label className="block text-xs text-slate-400 mb-1">
                  Project Name
                </label>
                <input
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  className="w-full max-w-sm bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none"
                />
              </div>

              {/* Drag and Drop Zone */}
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
                    : "border-slate-700 bg-slate-950 hover:border-slate-500 hover:bg-slate-900"
                }`}
              >
                <UploadCloud
                  className={`h-10 w-10 mb-3 ${
                    isDragging ? "text-emerald-400" : "text-slate-500"
                  }`}
                />
                <p className="text-sm font-medium text-slate-200">
                  Drag & Drop legacy folder or files here
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  Supports .py, .ts, .tsx, .js, .jsx (Ignores node_modules,
                  .git, etc.)
                </p>
                <input
                  type="file"
                  multiple
                  // @ts-expect-error - webkitdirectory is a non-standard but widely supported attribute
                  webkitdirectory="true"
                  directory="true"
                  ref={fileInputRef}
                  onChange={(e) => {
                    if (e.target.files) handleFilesAdded(e.target.files);
                  }}
                  className="hidden"
                />
              </div>

              {/* Loaded Files Preview List */}
              {localFiles.length > 0 && (
                <div className="mt-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-slate-400">
                      Loaded Files ({localFiles.length})
                    </span>
                    <button
                      onClick={() => setLocalFiles([])}
                      className="text-xs text-rose-400 hover:text-rose-300"
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
                        <span className="text-slate-500 shrink-0 ml-4">
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
                <p className="text-xs text-slate-400">
                  Add new rules or domain invariants to merge into the Phase 2
                  Intermediate Representation (IR).
                </p>
                <textarea
                  rows={8}
                  value={plainTextReqs}
                  onChange={(e) => setPlainTextReqs(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs font-mono focus:border-emerald-500 focus:outline-none"
                />
              </div>

              <button
                onClick={handleRunIngestion}
                disabled={loading || localFiles.length === 0}
                className="w-full py-3 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold text-sm flex items-center justify-center gap-2 transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Play className="h-4 w-4 fill-current" />
                {loading
                  ? "Running tree-sitter & tiktoken..."
                  : "Run Phase 1 AST Analysis"}
              </button>
            </div>
          </div>
        )}

        {/* ================================================================
            PHASE 2: INTERMEDIATE REPRESENTATION (IR) BLUEPRINT
           ================================================================ */}
        {activePhase === 2 && projectIR && (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Token Saver Telemetry Cards */}
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
                <span className="text-xs text-slate-400">
                  Tokens Saved (Boilerplate Filtered)
                </span>
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

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Extracted Entities */}
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 space-y-3">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <Layers className="h-4 w-4 text-emerald-400" />
                  Extracted Domain Entities ({projectIR.entities.length})
                </h3>
                {projectIR.entities.length === 0 && (
                  <p className="text-xs text-slate-500">
                    No entities detected.
                  </p>
                )}
                <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                  {projectIR.entities.map((ent) => (
                    <div
                      key={ent.id}
                      className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2"
                    >
                      <div className="flex justify-between items-center">
                        <span className="font-mono font-semibold text-emerald-300 text-sm">
                          {ent.name}
                        </span>
                        <span className="text-[10px] text-slate-500">
                          {ent.id.substring(0, 8)}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-1 text-xs font-mono text-slate-300">
                        {ent.fields.map((f) => (
                          <div key={f.name}>
                            {f.name}:{" "}
                            <span className="text-sky-400">{f.data_type}</span>
                            {f.is_primary_key && (
                              <span className="ml-1 text-[10px] text-amber-400">
                                [PK]
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Extracted Routes & Rules */}
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 space-y-3">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <Terminal className="h-4 w-4 text-sky-400" />
                  Business Rules ({projectIR.business_rules.length}) & Routes (
                  {projectIR.routes.length})
                </h3>
                <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                  {projectIR.business_rules.map((r) => (
                    <div
                      key={r.id}
                      className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-200">
                          {r.title}
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] ${
                            r.is_ambiguous
                              ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                              : "bg-emerald-500/20 text-emerald-300"
                          }`}
                        >
                          {r.is_ambiguous ? "Needs HITL" : "Verified"}
                        </span>
                      </div>
                      <p className="text-slate-400 leading-relaxed">
                        {r.expected_behavior}
                      </p>
                    </div>
                  ))}
                  {projectIR.routes.map((rt) => (
                    <div
                      key={rt.id}
                      className="p-2 border-l-2 border-slate-700 pl-3 bg-slate-900/30 text-xs font-mono text-slate-300 flex justify-between"
                    >
                      <span>
                        <span className="text-sky-400">{rt.method}</span>{" "}
                        {rt.path}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-4">
              <button
                onClick={() => setActivePhase(3)}
                className="px-6 py-3 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm shadow-lg shadow-emerald-500/10 transition"
              >
                Proceed to Phase 3: HITL Interview & Stack Advisor
              </button>
            </div>
          </div>
        )}

        {/* ================================================================
            PHASE 3: HITL INTERVIEW & AGNOSTIC STACK ADVISOR
           ================================================================ */}
        {activePhase === 3 && projectIR && (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Left Column: HITL Ambiguity Interview */}
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 space-y-4">
                <h3 className="text-base font-semibold flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-amber-400" />
                  Step 3A: Human-in-the-Loop Ambiguity Resolution
                </h3>
                {projectIR.hitl_questions.length === 0 ? (
                  <div className="p-8 text-center text-slate-400 flex flex-col items-center gap-3">
                    <CheckCircle2 className="h-8 w-8 text-emerald-500" />
                    <p className="text-sm">No ambiguous functions detected!</p>
                  </div>
                ) : (
                  <div className="space-y-4 max-h-[600px] overflow-y-auto pr-2">
                    {projectIR.hitl_questions.map((q) => (
                      <div
                        key={q.id}
                        className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-3"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-mono text-amber-400">
                            ID: {q.id}
                          </span>
                          <span
                            className={`text-[10px] px-2 py-0.5 rounded ${q.status === "resolved" ? "bg-emerald-900/40 text-emerald-400" : "bg-slate-800 text-slate-300"}`}
                          >
                            Status: {q.status}
                          </span>
                        </div>
                        <p className="text-sm font-medium text-slate-200">
                          {q.question}
                        </p>
                        {q.legacy_code_snippet && (
                          <pre className="p-3 rounded bg-slate-900 border border-slate-800 text-[11px] font-mono text-amber-200 overflow-x-auto">
                            {q.legacy_code_snippet}
                          </pre>
                        )}
                        <div className="space-y-2 pt-2 border-t border-slate-800">
                          <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                            Resolution Action
                          </label>
                          {q.suggested_options.map((opt) => (
                            <label
                              key={opt}
                              className="flex items-start gap-2 text-xs text-slate-300 cursor-pointer p-2 rounded hover:bg-slate-900 transition"
                            >
                              <input
                                type="radio"
                                name={q.id}
                                className="mt-0.5 accent-emerald-500"
                                checked={hitlAnswers[q.id] === opt}
                                onChange={() =>
                                  setHitlAnswers({
                                    ...hitlAnswers,
                                    [q.id]: opt,
                                  })
                                }
                              />
                              <span className="leading-snug">{opt}</span>
                            </label>
                          ))}
                          <input
                            placeholder="Or type custom domain rule resolution..."
                            value={hitlAnswers[q.id] || ""}
                            onChange={(e) =>
                              setHitlAnswers({
                                ...hitlAnswers,
                                [q.id]: e.target.value,
                              })
                            }
                            className="w-full mt-2 bg-slate-900 border border-slate-800 rounded px-3 py-2 text-xs focus:border-emerald-500 focus:outline-none"
                          />
                        </div>
                        <label className="flex items-center gap-2 text-xs text-rose-400 pt-3">
                          <input
                            type="checkbox"
                            className="accent-rose-500 rounded"
                            checked={Boolean(deprecatedFlags[q.id])}
                            onChange={(e) =>
                              setDeprecatedFlags({
                                ...deprecatedFlags,
                                [q.id]: e.target.checked,
                              })
                            }
                          />
                          Mark legacy rule as deprecated (exclude from new repo)
                        </label>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Right Column: Technical Constraints & Stack Advisor */}
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 space-y-5">
                <h3 className="text-base font-semibold flex items-center gap-2">
                  <Cpu className="h-5 w-5 text-sky-400" />
                  Step 3B: Workload Constraints & Stack Advisor
                </h3>

                <div className="grid grid-cols-2 gap-4 text-xs">
                  <div>
                    <label className="block text-slate-400 mb-2 font-medium">
                      Expected Concurrency:{" "}
                      <span className="text-emerald-400 font-mono text-sm ml-1">
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
                      className="w-full accent-sky-500"
                    />
                  </div>

                  <div>
                    <label className="block text-slate-400 mb-1 font-medium">
                      Explicit Stack Override
                    </label>
                    <select
                      value={overrideLang}
                      onChange={(e) =>
                        setOverrideLang(e.target.value as TargetLanguage | "")
                      }
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs focus:border-sky-500 focus:outline-none"
                    >
                      <option value="">Auto-Recommend Best Fit</option>
                      <option value="python_fastapi">Python (FastAPI)</option>
                      <option value="go">Go (Hexagonal HTTP)</option>
                      <option value="typescript">TypeScript (Node/Nest)</option>
                      <option value="csharp_dotnet">C# (.NET 8 Clean)</option>
                      <option value="rust">Rust (Axum)</option>
                    </select>
                  </div>
                </div>

                <div className="flex gap-6 text-xs bg-slate-950 p-3 rounded-lg border border-slate-800">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      className="accent-sky-500 w-4 h-4"
                      checked={constraints.io_heavy}
                      onChange={(e) =>
                        setConstraints({
                          ...constraints,
                          io_heavy: e.target.checked,
                        })
                      }
                    />
                    <span className="font-medium text-slate-300">
                      I/O Heavy Workload
                    </span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      className="accent-sky-500 w-4 h-4"
                      checked={constraints.cpu_heavy}
                      onChange={(e) =>
                        setConstraints({
                          ...constraints,
                          cpu_heavy: e.target.checked,
                        })
                      }
                    />
                    <span className="font-medium text-slate-300">
                      CPU Intensive
                    </span>
                  </label>
                </div>

                <button
                  onClick={() => handleResolveAndRecommend()}
                  disabled={
                    loading ||
                    (projectIR.hitl_questions.length > 0 &&
                      Object.keys(hitlAnswers).length === 0)
                  }
                  className="w-full py-3 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-sm transition disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-sky-500/10"
                >
                  {loading
                    ? "Evaluating Matrix..."
                    : "Save Resolutions & Run Stack Advisor"}
                </button>

                {/* Ranked Stack Results */}
                {archRec && (
                  <div className="space-y-3 pt-4 border-t border-slate-800 animate-in fade-in">
                    <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-500/30 text-xs space-y-2">
                      <div className="flex items-center justify-between font-bold text-emerald-400 text-sm">
                        <span className="flex items-center gap-2">
                          <CheckCircle2 className="h-5 w-5" />
                          Winner:{" "}
                          {
                            archRec.selected_architecture
                              .chosen_backend_language
                          }
                        </span>
                        <span className="bg-emerald-900/50 px-2 py-1 rounded">
                          AI Score:{" "}
                          {archRec.selected_architecture.ai_friendliness_score}
                          /100
                        </span>
                      </div>
                      <p className="text-emerald-100/70 text-[13px] leading-relaxed">
                        {archRec.selected_architecture.rationale}
                      </p>
                    </div>

                    <div className="space-y-2 pt-2">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 px-1">
                        Alternative Architecture Scores
                      </span>
                      {archRec.ranked_alternatives.map((alt) => (
                        <div
                          key={alt.language}
                          onClick={() => {
                            setOverrideLang(alt.language);
                            handleResolveAndRecommend(alt.language);
                          }}
                          className={`p-3 rounded-lg border text-xs flex items-center justify-between cursor-pointer transition ${
                            archRec.selected_architecture
                              .chosen_backend_language === alt.language
                              ? "bg-slate-800 border-sky-500 ring-1 ring-sky-500/50"
                              : "bg-slate-950 border-slate-800 hover:border-slate-600 hover:bg-slate-900"
                          }`}
                        >
                          <span className="font-mono font-semibold text-slate-200">
                            {alt.language}
                          </span>
                          <div className="flex gap-4 text-[11px] font-mono text-slate-400">
                            <span>
                              AI:{" "}
                              <span className="text-slate-300">
                                {alt.ai_friendliness_score}
                              </span>
                            </span>
                            <span>
                              Perf:{" "}
                              <span className="text-slate-300">
                                {alt.performance_fit_score}
                              </span>
                            </span>
                            <span className="text-emerald-400 font-bold ml-2">
                              {alt.total_score}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>

                    {archRec.ready_for_scaffolding && (
                      <button
                        onClick={handleGenerateScaffold}
                        className="w-full mt-6 py-4 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-base flex items-center justify-center gap-2 shadow-xl shadow-emerald-500/20 transform hover:scale-[1.01] transition-all"
                      >
                        <ShieldCheck className="h-5 w-5" />
                        Scaffold Containerized Kick-Starter
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ================================================================
            PHASE 4 & 5: KICK-STARTER CODE EXPLORER & ZIP DOWNLOAD
           ================================================================ */}
        {activePhase === 4 && manifest && projectIR && (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-900/70 border border-slate-800 rounded-xl p-5 shadow-lg">
              <div>
                <h2 className="text-lg font-bold text-emerald-400 flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5" />
                  {manifest.project_name} — Ready for Development
                </h2>
                <div className="flex items-center gap-3 mt-2 text-xs text-slate-400 font-mono">
                  <span className="bg-slate-800 px-2 py-1 rounded">
                    Stack:{" "}
                    <span className="text-slate-200">
                      {manifest.chosen_stack}
                    </span>
                  </span>
                  <span className="bg-slate-800 px-2 py-1 rounded">
                    Pattern:{" "}
                    <span className="text-slate-200">
                      {manifest.chosen_pattern}
                    </span>
                  </span>
                  <span className="bg-slate-800 px-2 py-1 rounded text-sky-300">
                    {manifest.total_files_generated} files generated
                  </span>
                </div>
              </div>

              <button
                onClick={handleDownloadZip}
                disabled={loading}
                className="px-6 py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm flex items-center gap-2 shadow-xl shadow-emerald-500/20 hover:scale-105 transition-transform"
              >
                <Download className="h-5 w-5" />
                Download Source Code (.zip)
              </button>
            </div>

            {/* Split-Pane File Explorer & Code Viewer */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 h-[600px]">
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3 overflow-y-auto space-y-1 custom-scrollbar">
                <span className="block text-xs font-bold text-slate-400 px-3 py-2 uppercase tracking-wider mb-2 border-b border-slate-800">
                  Project Explorer
                </span>
                {manifest.files.map((file) => (
                  <button
                    key={file.path}
                    onClick={() => setSelectedFile(file)}
                    className={`w-full text-left px-3 py-2.5 rounded-lg text-xs font-mono flex items-center justify-between transition group ${
                      selectedFile?.path === file.path
                        ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                        : "text-slate-300 hover:bg-slate-800 border border-transparent"
                    }`}
                  >
                    <span className="truncate flex items-center gap-2.5">
                      <FileCode
                        className={`h-4 w-4 shrink-0 ${selectedFile?.path === file.path ? "text-emerald-400" : "text-slate-500 group-hover:text-slate-400"}`}
                      />
                      {file.path.split("/").pop()}
                    </span>
                    <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-slate-950 text-slate-500 border border-slate-800">
                      {file.category}
                    </span>
                  </button>
                ))}
              </div>

              <div className="lg:col-span-3 bg-slate-950 border border-slate-800 rounded-xl flex flex-col overflow-hidden shadow-inner">
                {selectedFile ? (
                  <>
                    <div className="px-5 py-3 border-b border-slate-800 bg-slate-900/80 flex items-center justify-between text-xs font-mono backdrop-blur">
                      <div className="flex items-center gap-2 text-emerald-300">
                        <FileCode className="h-4 w-4 text-emerald-500" />
                        {selectedFile.path}
                      </div>
                      <span className="text-slate-500 uppercase tracking-widest text-[10px]">
                        {selectedFile.language}
                      </span>
                    </div>
                    <pre className="p-6 text-[13px] font-mono text-slate-300 overflow-auto flex-1 leading-relaxed custom-scrollbar">
                      <code className="block whitespace-pre">
                        {selectedFile.content}
                      </code>
                    </pre>
                  </>
                ) : (
                  <div className="flex flex-col items-center justify-center h-full text-slate-500">
                    <Code2 className="h-12 w-12 mb-4 opacity-20" />
                    <p>Select a file from the explorer to view contents</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
