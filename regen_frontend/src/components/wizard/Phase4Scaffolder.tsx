"use client";

import React from "react";
import { CheckCircle2, Download, FileCode, Loader2 } from "lucide-react";
import { GeneratedFile, ScaffoldJobStatus, ScaffoldManifest } from "@/types/ir";

interface Phase4ScaffolderProps {
  buildJob: ScaffoldJobStatus | null;
  manifest: ScaffoldManifest | null;
  selectedFile: GeneratedFile | null;
  onSelectFile: (file: GeneratedFile) => void;
  onDownloadZip: (jobId: string) => void;
}

export function Phase4Scaffolder({
  buildJob,
  manifest,
  selectedFile,
  onSelectFile,
  onDownloadZip,
}: Phase4ScaffolderProps) {
  return (
    <div className="space-y-6">
      {buildJob && buildJob.status === "processing" && (
        <div className="max-w-2xl mx-auto my-12 p-8 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-6 text-center">
          <Loader2 className="h-12 w-12 text-emerald-400 animate-spin mx-auto" />
          <div className="space-y-2">
            <h2 className="text-lg font-bold">
              Running Official Language CLIs &amp; Building Archive...
            </h2>
            <p className="text-xs font-mono text-emerald-400">
              {buildJob.current_step}
            </p>
          </div>
          <div className="w-full bg-slate-950 rounded-full h-3 overflow-hidden border border-slate-800">
            <div
              className="bg-emerald-500 h-full transition-all duration-500"
              style={{ width: `${buildJob.progress_pct}%` }}
            />
          </div>
          <div className="text-left bg-slate-950 border border-slate-800 rounded-lg p-3 font-mono text-[11px] text-slate-400 space-y-1 max-h-40 overflow-y-auto">
            {buildJob.logs.map((logItem: string, idx: number) => (
              <div key={idx}>&gt; {logItem}</div>
            ))}
          </div>
        </div>
      )}

      {manifest && buildJob?.status === "ready" && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-900/70 border border-slate-800 rounded-xl p-5">
            <div>
              <h2 className="text-lg font-bold text-emerald-400 flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5" />
                {manifest.project_name} — Ready for Download
              </h2>
              <p className="text-xs font-mono text-slate-400 mt-1">
                Backend: {manifest.chosen_stack} | Pattern:{" "}
                {manifest.chosen_pattern} | Frontend: {manifest.chosen_frontend}{" "}
                | {manifest.total_files_generated} files
              </p>
            </div>
            <button
              onClick={() => onDownloadZip(buildJob.job_id)}
              className="px-6 py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm flex items-center gap-2"
            >
              <Download className="h-5 w-5" />
              Instant Download (.zip)
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 h-[520px]">
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3 overflow-y-auto space-y-1">
              {manifest.files.map((file: GeneratedFile) => (
                <button
                  key={file.path}
                  onClick={() => onSelectFile(file)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-xs font-mono flex items-center gap-2 ${
                    selectedFile?.path === file.path
                      ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                      : "text-slate-300 hover:bg-slate-800"
                  }`}
                >
                  <FileCode className="h-3.5 w-3.5 shrink-0 text-slate-500" />
                  <span className="truncate">{file.path}</span>
                </button>
              ))}
            </div>
            <div className="lg:col-span-3 bg-slate-950 border border-slate-800 rounded-xl flex flex-col overflow-hidden">
              {selectedFile && (
                <>
                  <div className="px-4 py-2.5 border-b border-slate-800 bg-slate-900/80 flex justify-between text-xs font-mono">
                    <span className="text-emerald-300">
                      {selectedFile.path}
                    </span>
                    <span className="text-slate-500">
                      {selectedFile.language}
                    </span>
                  </div>
                  <pre className="p-5 text-xs font-mono text-slate-300 overflow-auto flex-1">
                    <code>{selectedFile.content}</code>
                  </pre>
                </>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
