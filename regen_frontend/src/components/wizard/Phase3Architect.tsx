"use client";

import React from "react";
import { Cpu, ShieldCheck } from "lucide-react";
import {
  ArchitectRecommendationResponse,
  TargetFrontend,
  TargetLanguage,
  TechnicalConstraints,
} from "@/types/ir";

interface Phase3ArchitectProps {
  constraints: TechnicalConstraints;
  onChangeConstraints: (updated: TechnicalConstraints) => void;
  overrideLang: TargetLanguage | "";
  onChangeOverrideLang: (val: TargetLanguage | "") => void;
  selectedFrontend: TargetFrontend;
  onChangeSelectedFrontend: (val: TargetFrontend) => void;
  archRec: ArchitectRecommendationResponse | null;
  onRecommendStack: () => void;
  onStartScaffold: () => void;
  loading: boolean;
}

export function Phase3Architect({
  constraints,
  onChangeConstraints,
  overrideLang,
  onChangeOverrideLang,
  selectedFrontend,
  onChangeSelectedFrontend,
  archRec,
  onRecommendStack,
  onStartScaffold,
  loading,
}: Phase3ArchitectProps) {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 space-y-5">
        <div>
          <h2 className="text-base font-semibold flex items-center gap-2">
            <Cpu className="h-5 w-5 text-sky-400" />
            Step 3: Executive Stack &amp; Architecture Recommendation
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Pre-filled from your Step 1 requirements &amp; code profile. Adjust
            any constraint below or evaluate directly.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div>
            <label className="block text-slate-400 mb-1 font-semibold">
              Backend Stack (Auto or Override)
            </label>
            <select
              value={overrideLang}
              onChange={(e) =>
                onChangeOverrideLang(e.target.value as TargetLanguage | "")
              }
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2"
            >
              <option value="">Auto-Select Best Fit from Constraints</option>
              <option value="python_fastapi">Python (FastAPI)</option>
              <option value="go">Go (Hexagonal / Clean HTTP)</option>
              <option value="typescript">TypeScript (Node/tsx)</option>
              <option value="csharp_dotnet">C# (.NET 8 WebAPI)</option>
              <option value="rust">Rust (Cargo + Axum)</option>
            </select>
          </div>

          <div>
            <label className="block text-slate-400 mb-1 font-semibold">
              Frontend Stack (Independent)
            </label>
            <select
              value={selectedFrontend}
              onChange={(e) =>
                onChangeSelectedFrontend(e.target.value as TargetFrontend)
              }
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-emerald-300"
            >
              <option value="nextjs">Next.js (create-next-app)</option>
              <option value="react_vite">React + Vite</option>
              <option value="vue_vite">Vue 3 + Vite</option>
              <option value="sveltekit">SvelteKit</option>
              <option value="angular">Angular</option>
              <option value="none">None (Backend API Only)</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-xs text-slate-400 mb-1 font-semibold">
            Developer Skill &amp; Architecture Constraints (Pre-filled from Step
            1)
          </label>
          <input
            value={constraints.team_experience_notes || ""}
            onChange={(e) =>
              onChangeConstraints({
                ...constraints,
                team_experience_notes: e.target.value,
              })
            }
            placeholder="e.g. 'I only know C', 'It cant be hexagonal', 'Prefer modular monolith'"
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-amber-300"
          />
        </div>

        <div className="grid grid-cols-2 gap-4 text-xs">
          <div>
            <label className="block text-slate-400 mb-1">
              Expected Concurrency:{" "}
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
                onChangeConstraints({
                  ...constraints,
                  expected_concurrency_rps: Number(e.target.value),
                })
              }
              className="w-full"
            />
          </div>
          <div className="flex items-center gap-6 pt-4">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={constraints.io_heavy}
                onChange={(e) =>
                  onChangeConstraints({
                    ...constraints,
                    io_heavy: e.target.checked,
                  })
                }
              />
              I/O Heavy
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={constraints.cpu_heavy}
                onChange={(e) =>
                  onChangeConstraints({
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
          onClick={onRecommendStack}
          disabled={loading}
          className="w-full py-3 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-sm"
        >
          {loading
            ? "Running AI Architect Evaluation..."
            : "Evaluate Constraints & Recommend Architecture"}
        </button>

        {archRec && (
          <div className="space-y-4 pt-4 border-t border-slate-800">
            <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-xs space-y-1.5">
              <div className="font-bold text-emerald-300 text-sm flex justify-between">
                <span>
                  Winner:{" "}
                  {archRec.selected_architecture.chosen_backend_language} (
                  {archRec.selected_architecture.chosen_pattern}) +{" "}
                  {archRec.selected_architecture.chosen_frontend_stack}
                </span>
                <span>
                  AI Friendliness:{" "}
                  {archRec.selected_architecture.ai_friendliness_score}/100
                </span>
              </div>
              <p className="text-slate-300">
                {archRec.selected_architecture.rationale}
              </p>
            </div>

            {archRec.ready_for_scaffolding && (
              <button
                onClick={onStartScaffold}
                className="w-full py-4 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-base flex items-center justify-center gap-2 shadow-xl shadow-emerald-500/20"
              >
                <ShieldCheck className="h-5 w-5" />
                Step 4: Run CLI Project Builder &amp; Pre-Build ZIP
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
