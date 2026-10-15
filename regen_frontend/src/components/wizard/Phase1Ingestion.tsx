"use client";

import React, { useRef, useState } from "react";
import { Code2, FileSpreadsheet, Play, UploadCloud } from "lucide-react";
import { DocUploadItem } from "@/types/ir";

interface Phase1IngestionProps {
  projectName: string;
  onChangeProjectName: (val: string) => void;
  codeFiles: { file_path: string; content: string }[];
  docFiles: DocUploadItem[];
  onFilesAdded: (files: FileList | File[]) => void;
  onClearFiles: () => void;
  plainTextReqs: string;
  onChangePlainTextReqs: (val: string) => void;
  onRunIngestion: () => void;
  loading: boolean;
}

export function Phase1Ingestion({
  projectName,
  onChangeProjectName,
  codeFiles,
  docFiles,
  onFilesAdded,
  onClearFiles,
  plainTextReqs,
  onChangePlainTextReqs,
  onRunIngestion,
  loading,
}: Phase1IngestionProps) {
  const [isDragging, setIsDragging] = useState(false);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Left: Optional Legacy Code & Requirement Docs */}
      <div className="space-y-4 bg-slate-900/50 border border-slate-800 rounded-xl p-6">
        <h2 className="text-base font-semibold flex items-center gap-2">
          <Code2 className="h-5 w-5 text-emerald-400" />
          Step 1A: Legacy Code or Requirement Files (Optional)
        </h2>
        <p className="text-xs text-slate-400">
          Code files (.py, .ts, .js) are parsed via{" "}
          <code className="text-emerald-300">tree-sitter</code>. Documents
          (.csv, .xlsx, .pdf, .json, .md) are pre-processed by Python into
          compact digests before LLM analysis.
        </p>

        <div>
          <label className="block text-xs text-slate-400 mb-1">
            Project Name
          </label>
          <input
            value={projectName}
            onChange={(e) => onChangeProjectName(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm"
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
            onFilesAdded(e.dataTransfer.files);
          }}
          className={`w-full border-2 border-dashed rounded-xl p-6 flex flex-col items-center justify-center text-center transition-colors ${
            isDragging
              ? "border-emerald-500 bg-emerald-500/10"
              : "border-slate-700 bg-slate-950"
          }`}
        >
          <UploadCloud className="h-9 w-9 mb-2 text-emerald-400" />
          <p className="text-sm font-medium text-slate-200">
            Drag &amp; Drop files/folders here (or use buttons below)
          </p>
          <p className="text-xs text-slate-500 mt-1">
            Supports Code (.py, .ts, .js) &amp; Docs (.csv, .xlsx, .pdf, .json,
            .md, .txt)
          </p>

          <div className="flex gap-3 mt-4">
            <button
              type="button"
              onClick={() => folderInputRef.current?.click()}
              className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-200"
            >
              Select Legacy Folder
            </button>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="px-3 py-1.5 rounded bg-emerald-500/20 border border-emerald-500/40 hover:bg-emerald-500/30 text-xs text-emerald-300"
            >
              Select Files (.csv, .xlsx, .pdf, .py...)
            </button>
          </div>

          <input
            type="file"
            multiple
            // @ts-expect-error - non-standard directory selection attribute
            webkitdirectory="true"
            directory="true"
            ref={folderInputRef}
            onChange={(e) => e.target.files && onFilesAdded(e.target.files)}
            className="hidden"
          />
          <input
            type="file"
            multiple
            accept=".py,.ts,.tsx,.js,.jsx,.csv,.xlsx,.pdf,.json,.md,.txt"
            ref={fileInputRef}
            onChange={(e) => e.target.files && onFilesAdded(e.target.files)}
            className="hidden"
          />
        </div>

        {(codeFiles.length > 0 || docFiles.length > 0) && (
          <div className="space-y-2">
            <div className="flex justify-between text-xs text-slate-400">
              <span>
                Code Files: {codeFiles.length} | Documents: {docFiles.length}
              </span>
              <button
                onClick={onClearFiles}
                className="text-rose-400 hover:underline"
              >
                Clear All
              </button>
            </div>
            <div className="max-h-36 overflow-y-auto bg-slate-950 border border-slate-800 rounded-lg p-2 space-y-1 text-[11px] font-mono">
              {codeFiles.map((f, i) => (
                <div key={`c-${i}`} className="text-emerald-300 truncate">
                  [AST] {f.file_path}
                </div>
              ))}
              {docFiles.map((d, i) => (
                <div
                  key={`d-${i}`}
                  className="text-sky-300 flex items-center gap-1.5 truncate"
                >
                  <FileSpreadsheet className="h-3 w-3 shrink-0" />
                  [DOC] {d.file_path} ({d.sizeKb} KB)
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Right: Plain-Text System Description & Constraints */}
      <div className="space-y-4 bg-slate-900/50 border border-slate-800 rounded-xl p-6 flex flex-col justify-between">
        <div className="space-y-3">
          <h2 className="text-base font-semibold text-slate-200">
            Step 1B: Plain-Text Project Description &amp; Developer Notes
          </h2>
          <p className="text-xs text-slate-400">
            Works standalone even with zero files! Describe new features,
            entities, business rules, or team constraints (e.g.,{" "}
            <em>&quot;I only know C&quot;</em>,{" "}
            <em>&quot;It cant be hexagonal&quot;</em>).
          </p>
          <textarea
            rows={10}
            value={plainTextReqs}
            onChange={(e) => onChangePlainTextReqs(e.target.value)}
            placeholder="Describe what the system does, new modules to add, and any stack/architecture constraints..."
            className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs font-mono leading-relaxed"
          />
        </div>

        <button
          onClick={onRunIngestion}
          disabled={loading}
          className="w-full py-3.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm flex items-center justify-center gap-2 transition disabled:opacity-50"
        >
          <Play className="h-4 w-4 fill-current" />
          {loading
            ? "Running Pre-Processors & Local LLM..."
            : "Analyze Inputs & Extract System Blueprint"}
        </button>
      </div>
    </div>
  );
}
