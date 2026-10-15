"use client";

import React from "react";
import { AlertTriangle, Layers } from "lucide-react";
import {
  BusinessRule,
  EntityDefinition,
  EntityField,
  HITLQuestion,
  ProjectIR,
} from "@/types/ir";

interface Phase2BlueprintHITLProps {
  projectIR: ProjectIR;
  hitlAnswers: Record<string, string>;
  onSelectAnswer: (questionId: string, answer: string) => void;
  deprecatedFlags: Record<string, boolean>;
  onToggleDeprecated: (questionId: string, val: boolean) => void;
  onConfirmAndProceed: () => void;
  loading: boolean;
}

export function Phase2BlueprintHITL({
  projectIR,
  hitlAnswers,
  onSelectAnswer,
  deprecatedFlags,
  onToggleDeprecated,
  onConfirmAndProceed,
  loading,
}: Phase2BlueprintHITLProps) {
  return (
    <div className="space-y-6">
      {/* Telemetry Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-4">
          <span className="text-xs text-slate-400">Entities Extracted</span>
          <p className="text-2xl font-bold text-emerald-400 mt-1">
            {projectIR.entities.length}
          </p>
        </div>
        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-4">
          <span className="text-xs text-slate-400">Business Rules</span>
          <p className="text-2xl font-bold text-sky-400 mt-1">
            {projectIR.business_rules.length}
          </p>
        </div>
        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-4">
          <span className="text-xs text-slate-400">
            Tokens Saved by Pre-Processing
          </span>
          <p className="text-2xl font-bold text-emerald-300 mt-1">
            {projectIR.ingestion_metrics.estimated_tokens_saved.toLocaleString()}
          </p>
        </div>
        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-4">
          <span className="text-xs text-slate-400">
            HITL Clarifications Needed
          </span>
          <p className="text-2xl font-bold text-amber-400 mt-1">
            {projectIR.hitl_questions.length}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Extracted Entities & Routes */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 space-y-4">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Layers className="h-4 w-4 text-emerald-400" />
            Extracted Entities ({projectIR.entities.length}) &amp; Routes (
            {projectIR.routes.length})
          </h3>
          <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
            {projectIR.entities.map((ent: EntityDefinition) => (
              <div
                key={ent.id}
                className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1.5"
              >
                <div className="flex justify-between">
                  <span className="font-mono font-bold text-emerald-300 text-sm">
                    {ent.name}
                  </span>
                  <span className="text-[11px] text-slate-500">
                    {ent.description}
                  </span>
                </div>
                <div className="flex flex-wrap gap-2 text-xs font-mono text-slate-300">
                  {ent.fields.map((f: EntityField) => (
                    <span
                      key={f.name}
                      className="bg-slate-900 px-2 py-0.5 rounded border border-slate-800"
                    >
                      {f.name}:{" "}
                      <span className="text-sky-400">{f.data_type}</span>
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: HITL Business Rule Interview */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 space-y-4">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-400" />
            Step 2B: Business Rule Clarity Interview (HITL)
          </h3>
          {projectIR.hitl_questions.length === 0 ? (
            <div className="p-6 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300 space-y-2">
              <p className="text-emerald-400 font-semibold">
                All extracted business rules are clear!
              </p>
              {projectIR.business_rules.map((r: BusinessRule) => (
                <div key={r.id} className="border-t border-slate-800 pt-2">
                  <span className="font-semibold">{r.title}:</span>{" "}
                  {r.expected_behavior}
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
              {projectIR.hitl_questions.map((q: HITLQuestion) => (
                <div
                  key={q.id}
                  className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-2.5"
                >
                  <p className="text-xs font-medium text-slate-200">
                    {q.question}
                  </p>
                  {q.legacy_code_snippet && (
                    <pre className="p-2 rounded bg-slate-900 text-[11px] font-mono text-amber-200 overflow-x-auto">
                      {q.legacy_code_snippet}
                    </pre>
                  )}
                  <div className="space-y-1">
                    {q.suggested_options.map((opt: string) => (
                      <label
                        key={opt}
                        className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer"
                      >
                        <input
                          type="radio"
                          name={q.id}
                          checked={hitlAnswers[q.id] === opt}
                          onChange={() => onSelectAnswer(q.id, opt)}
                        />
                        {opt}
                      </label>
                    ))}
                  </div>
                  <label className="flex items-center gap-2 text-xs text-rose-400 pt-2">
                    <input
                      type="checkbox"
                      checked={Boolean(deprecatedFlags[q.id])}
                      onChange={(e) =>
                        onToggleDeprecated(q.id, e.target.checked)
                      }
                    />
                    Mark rule as deprecated (exclude from new project)
                  </label>
                </div>
              ))}
            </div>
          )}

          <button
            onClick={onConfirmAndProceed}
            disabled={loading}
            className="w-full py-3 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm"
          >
            Confirm Business Rules &amp; Proceed to Step 3 (AI Architect)
          </button>
        </div>
      </div>
    </div>
  );
}
