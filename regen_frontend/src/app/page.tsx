"use client";

import React from "react";
import { WizardHeader } from "@/components/wizard/WizardHeader";
import { Phase1Ingestion } from "@/components/wizard/Phase1Ingestion";
import { Phase2BlueprintHITL } from "@/components/wizard/Phase2BlueprintHITL";
import { Phase3Architect } from "@/components/wizard/Phase3Architect";
import { Phase4Scaffolder } from "@/components/wizard/Phase4Scaffolder";
import { useRegenWizard } from "@/hooks/useRegenWizard";

export default function RegenWizardPage() {
  const wizard = useRegenWizard();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <WizardHeader
        activePhase={wizard.activePhase}
        hasProjectIR={Boolean(wizard.projectIR)}
        lowVramMode={wizard.lowVramMode}
        onToggleLowVram={wizard.setLowVramMode}
        onSelectPhase={wizard.setActivePhase}
      />

      {wizard.error && (
        <div className="mx-6 mt-4 p-3 rounded-lg bg-red-950/60 border border-red-800 text-red-200 text-sm flex items-center justify-between">
          <span>{wizard.error}</span>
          <button
            onClick={() => wizard.setError(null)}
            className="text-xs underline ml-4 hover:text-white"
          >
            Dismiss
          </button>
        </div>
      )}

      <main className="flex-1 p-6 max-w-7xl w-full mx-auto">
        {wizard.activePhase === 1 && (
          <Phase1Ingestion
            projectName={wizard.projectName}
            onChangeProjectName={wizard.setProjectName}
            codeFiles={wizard.codeFiles}
            docFiles={wizard.docFiles}
            onFilesAdded={wizard.handleFilesAdded}
            onClearFiles={wizard.handleClearFiles}
            plainTextReqs={wizard.plainTextReqs}
            onChangePlainTextReqs={wizard.setPlainTextReqs}
            onRunIngestion={wizard.handleRunIngestion}
            loading={wizard.loading}
          />
        )}

        {wizard.activePhase === 2 && wizard.projectIR && (
          <Phase2BlueprintHITL
            projectIR={wizard.projectIR}
            hitlAnswers={wizard.hitlAnswers}
            onSelectAnswer={(qId, ans) =>
              wizard.setHitlAnswers((prev) => ({ ...prev, [qId]: ans }))
            }
            deprecatedFlags={wizard.deprecatedFlags}
            onToggleDeprecated={(qId, val) =>
              wizard.setDeprecatedFlags((prev) => ({ ...prev, [qId]: val }))
            }
            onConfirmAndProceed={wizard.handleConfirmHITLAndProceed}
            loading={wizard.loading}
          />
        )}

        {wizard.activePhase === 3 && wizard.projectIR && (
          <Phase3Architect
            constraints={wizard.constraints}
            onChangeConstraints={wizard.setConstraints}
            overrideLang={wizard.overrideLang}
            onChangeOverrideLang={wizard.setOverrideLang}
            selectedFrontend={wizard.selectedFrontend}
            onChangeSelectedFrontend={wizard.setSelectedFrontend}
            archRec={wizard.archRec}
            onRecommendStack={wizard.handleRecommendStack}
            onStartScaffold={wizard.handleStartAsyncScaffold}
            loading={wizard.loading}
          />
        )}

        {wizard.activePhase === 4 && (
          <Phase4Scaffolder
            buildJob={wizard.buildJob}
            manifest={wizard.manifest}
            selectedFile={wizard.selectedFile}
            onSelectFile={wizard.setSelectedFile}
            onDownloadZip={wizard.triggerInstantJobZipDownload}
          />
        )}
      </main>
    </div>
  );
}
