"use client";

import React from "react";
import { BookOpen, Cpu, ShieldCheck } from "lucide-react";
import {
  ArchitectRecommendationResponse,
  FrontendScoreBreakdown,
  StackScoreBreakdown,
  TargetFrontend,
  TargetLanguage,
  TechnicalConstraints,
} from "@/types/ir";

interface Phase3ArchitectProps {
  constraints: TechnicalConstraints;
  onChangeConstraints: (updated: TechnicalConstraints) => void;
  overrideLang: TargetLanguage | "";
  onChangeOverrideLang: (val: TargetLanguage | "") => void;
  selectedFrontend: TargetFrontend | "";
  onChangeSelectedFrontend: (val: TargetFrontend | "") => void;
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
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 space-y-5">
        <div>
          <h2 className="text-base font-semibold flex items-center gap-2">
            <Cpu className="h-5 w-5 text-sky-400" />
            Step 3: Multi-Criteria (AHP) Backend &amp; Frontend Advisor
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Evaluates TechEmpower, Stack Overflow, JetBrains, and MultiPL-E
            benchmarks with graduated familiarity boosts and paradigm proximity.
          </p>
        </div>

        {/* Team Skill & Sentiment Input */}
        <div>
          <label className="block text-xs text-slate-400 mb-1 font-semibold">
            Team Skills, Preferences &amp; Dislikes (Graduated Sentiment +
            Proximity Engine)
          </label>
          <input
            value={constraints.team_experience_notes || ""}
            onChange={(e) =>
              onChangeConstraints({
                ...constraints,
                team_experience_notes: e.target.value,
              })
            }
            placeholder="e.g. 'The team only programs in Python', 'I know Python better', 'I don't like Python', 'Need SEO'"
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-amber-300"
          />
        </div>

        {/* Workload & AI Usage Controls */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs bg-slate-950 p-4 rounded-xl border border-slate-800">
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
              className="w-full accent-sky-500"
            />
          </div>

          <div className="flex flex-wrap items-center gap-5">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={constraints.will_use_ai_coding_assistants}
                onChange={(e) =>
                  onChangeConstraints({
                    ...constraints,
                    will_use_ai_coding_assistants: e.target.checked,
                  })
                }
                className="accent-emerald-500"
              />
              <span className="text-emerald-300 font-medium">
                Team Uses AI Coding Assistants (Max +10 / -5)
              </span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer">
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
            <label className="flex items-center gap-2 cursor-pointer">
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

        {/* Optional Overrides */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div>
            <label className="block text-slate-400 mb-1 font-semibold">
              Backend Stack (Auto-Recommend or Override)
            </label>
            <select
              value={overrideLang}
              onChange={(e) =>
                onChangeOverrideLang(e.target.value as TargetLanguage | "")
              }
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2"
            >
              <option value="">
                Auto-Recommend Best Backend from Benchmarks
              </option>
              <option value="python_fastapi">Python (FastAPI)</option>
              <option value="typescript">TypeScript (Node/tsx)</option>
              <option value="csharp_dotnet">C# (.NET 8 WebAPI)</option>
              <option value="go">Go (Hexagonal / Clean HTTP)</option>
              <option value="rust">Rust (Cargo + Axum)</option>
            </select>
          </div>

          <div>
            <label className="block text-slate-400 mb-1 font-semibold">
              Frontend Stack (Auto-Recommend or Override)
            </label>
            <select
              value={selectedFrontend}
              onChange={(e) =>
                onChangeSelectedFrontend(e.target.value as TargetFrontend | "")
              }
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-emerald-300"
            >
              <option value="">
                Auto-Recommend Best Frontend from Benchmarks
              </option>
              <option value="react_vite">React + Vite (SPA Dashboard)</option>
              <option value="nextjs">Next.js (SSR / SEO App Router)</option>
              <option value="vue_vite">Vue 3 + Vite</option>
              <option value="sveltekit">SvelteKit</option>
              <option value="angular">Angular</option>
              <option value="none">None (Headless API Only)</option>
            </select>
          </div>
        </div>

        <button
          onClick={onRecommendStack}
          disabled={loading}
          className="w-full py-3 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-sm"
        >
          {loading
            ? "Calculating AHP Matrix & Modifiers..."
            : "Run Evidence-Based Stack & Frontend Advisor"}
        </button>

        {/* Results */}
        {archRec && (
          <div className="space-y-5 pt-4 border-t border-slate-800">
            {/* Winner Banner */}
            <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-xs space-y-1.5">
              <div className="font-bold text-emerald-300 text-sm flex flex-wrap justify-between gap-2">
                <span>
                  Recommended Backend:{" "}
                  {archRec.selected_architecture.chosen_backend_language} (
                  {archRec.selected_architecture.chosen_pattern}) | Frontend:{" "}
                  {archRec.selected_architecture.chosen_frontend_stack}
                </span>
                <span>
                  Dynamic AHP Weights: Vel{" "}
                  {Math.round(archRec.ahp_weights.velocity_weight * 100)}% |
                  Perf{" "}
                  {Math.round(archRec.ahp_weights.performance_weight * 100)}% |
                  Eco {Math.round(archRec.ahp_weights.ecosystem_weight * 100)}%
                  | AI {Math.round(archRec.ahp_weights.ai_weight * 100)}%
                </span>
              </div>
              <p className="text-slate-300 leading-relaxed">
                {archRec.selected_architecture.rationale}
              </p>
            </div>

            {/* Dual Leaderboards: Backend & Frontend */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Backend Leaderboard */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Backend Stack Leaderboard
                </h4>
                {archRec.ranked_alternatives.map((b: StackScoreBreakdown) => (
                  <div
                    key={b.language}
                    className={`p-3 rounded-lg border text-xs space-y-1 ${
                      archRec.selected_architecture.chosen_backend_language ===
                      b.language
                        ? "bg-slate-800/90 border-emerald-500"
                        : "bg-slate-950 border-slate-800"
                    }`}
                  >
                    <div className="flex justify-between font-mono font-bold">
                      <span className="text-slate-100">{b.language}</span>
                      <span className="text-emerald-400">{b.total_score}</span>
                    </div>
                    <div className="flex flex-wrap gap-2 text-[11px] font-mono text-slate-400">
                      <span>Base: {b.base_industry_score}</span>
                      {b.familiarity_modifier !== 0 && (
                        <span
                          className={
                            b.familiarity_modifier > 0
                              ? "text-emerald-300"
                              : "text-rose-400"
                          }
                        >
                          Skill:{" "}
                          {b.familiarity_modifier > 0
                            ? `+${b.familiarity_modifier}`
                            : b.familiarity_modifier}
                        </span>
                      )}
                      {b.proximity_modifier > 0 && (
                        <span className="text-sky-300">
                          Proximity: +{b.proximity_modifier}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Frontend Leaderboard */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Frontend Framework Leaderboard
                </h4>
                {archRec.ranked_frontend_alternatives.map(
                  (fe: FrontendScoreBreakdown) => (
                    <div
                      key={fe.framework}
                      className={`p-3 rounded-lg border text-xs space-y-1 ${
                        archRec.selected_architecture.chosen_frontend_stack ===
                        fe.framework
                          ? "bg-slate-800/90 border-emerald-500"
                          : "bg-slate-950 border-slate-800"
                      }`}
                    >
                      <div className="flex justify-between font-mono font-bold">
                        <span className="text-slate-100">{fe.framework}</span>
                        <span className="text-emerald-400">
                          {fe.total_score}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-2 text-[11px] font-mono text-slate-400">
                        <span>Base: {fe.base_industry_score}</span>
                        {fe.familiarity_modifier !== 0 && (
                          <span
                            className={
                              fe.familiarity_modifier > 0
                                ? "text-emerald-300"
                                : "text-rose-400"
                            }
                          >
                            Skill:{" "}
                            {fe.familiarity_modifier > 0
                              ? `+${fe.familiarity_modifier}`
                              : fe.familiarity_modifier}
                          </span>
                        )}
                        {fe.proximity_modifier > 0 && (
                          <span className="text-sky-300">
                            Proximity: +{fe.proximity_modifier}
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-slate-400">
                        {fe.rationale}
                      </p>
                    </div>
                  ),
                )}
              </div>
            </div>

            {/* Verifiable Industry Sources Footer */}
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-400 space-y-1">
              <div className="font-semibold text-slate-300 flex items-center gap-1.5">
                <BookOpen className="h-3.5 w-3.5 text-sky-400" />
                Auditable Benchmark Sources Used in Calculation:
              </div>
              {Object.entries(archRec.benchmark_sources || {}).map(
                ([k, src]) => (
                  <div key={k} className="truncate">
                    <span className="font-mono text-sky-300">{k}:</span> {src}
                  </div>
                ),
              )}
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
