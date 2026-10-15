"use client";

import React from "react";
import { Sparkles } from "lucide-react";

interface WizardHeaderProps {
  activePhase: number;
  hasProjectIR: boolean;
  lowVramMode: boolean;
  onToggleLowVram: (val: boolean) => void;
  onSelectPhase: (phase: number) => void;
}

const STEPS = [
  { step: 1, label: "1. Raw Ingestion" },
  { step: 2, label: "2. Business Rules (HITL)" },
  { step: 3, label: "3. Tech Stack & Arch" },
  { step: 4, label: "4. Builder & ZIP" },
];

export function WizardHeader({
  activePhase,
  hasProjectIR,
  lowVramMode,
  onToggleLowVram,
  onSelectPhase,
}: WizardHeaderProps) {
  return (
    <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur px-6 py-4 flex flex-wrap items-center justify-between gap-4 sticky top-0 z-10">
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-lg bg-emerald-500/10 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
          <Sparkles className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight flex items-center gap-2">
            REGEN
            <span className="text-xs font-mono uppercase px-2 py-0.5 rounded bg-slate-800 text-emerald-400 border border-slate-700">
              Hybrid AST + Local LLM
            </span>
          </h1>
          <p className="text-xs text-slate-400">
            1. Raw Ingestion &rarr; 2. Business Rule Clarity &rarr; 3. Stack
            Advisor &rarr; 4. CLI Scaffolder
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2 text-xs bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg cursor-pointer">
          <input
            type="checkbox"
            checked={lowVramMode}
            onChange={(e) => onToggleLowVram(e.target.checked)}
            className="accent-emerald-500"
          />
          <span className="text-slate-300 font-mono">
            Low-End PC Mode (phi4-mini only)
          </span>
        </label>

        <nav className="flex items-center gap-1.5 text-xs font-medium">
          {STEPS.map((item) => (
            <button
              key={item.step}
              onClick={() => hasProjectIR && onSelectPhase(item.step)}
              disabled={item.step > 1 && !hasProjectIR}
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
      </div>
    </header>
  );
}
