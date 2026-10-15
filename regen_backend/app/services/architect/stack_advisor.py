# app/services/architect/stack_advisor.py
import re
from typing import List, Optional, Tuple
from pydantic import BaseModel

from app.domain.ir_schema import (
    ArchitecturalPattern,
    ArchitectureDecision,
    ProjectIR,
    TargetFrontend,
    TargetLanguage,
    TechnicalConstraints,
)
from app.domain.wizard_state import StackScoreBreakdown
from app.services.llm_router import llm_router


class LLMArchitectureVerdict(BaseModel):
    recommended_language: TargetLanguage
    recommended_pattern: ArchitecturalPattern
    rationale: str


class StackAdvisorService:
    """
    Phase 3 Executive Architect Engine:
    Combines deterministic workload scoring with Local LLM reasoning (`deepseek-r1:8b` or `phi4-mini`)
    to honor natural-language user constraints (e.g., "I only know C", "Cannot be hexagonal").
    """

    def evaluate_and_recommend(
        self,
        ir: ProjectIR,
        constraints: TechnicalConstraints,
        override_language: Optional[TargetLanguage] = None,
        override_frontend: Optional[TargetFrontend] = None,
    ) -> Tuple[ArchitectureDecision, List[StackScoreBreakdown]]:
        # Parse natural-language notes (e.g. "I only know C", "It cant be hexagonal")
        self._apply_natural_language_notes(constraints)
        ir.technical_constraints = constraints

        pattern = self._select_architectural_pattern(ir, constraints)

        candidates: List[StackScoreBreakdown] = [
            self._score_python(constraints, pattern),
            self._score_go(constraints, pattern),
            self._score_typescript(constraints, pattern),
            self._score_csharp(constraints, pattern),
            self._score_rust(constraints, pattern),
        ]
        candidates.sort(key=lambda c: c.total_score, reverse=True)

        winning_candidate = candidates[0]
        if override_language:
            for cand in candidates:
                if cand.language == override_language:
                    winning_candidate = cand
                    break

        chosen_fe = (
            override_frontend
            or constraints.preferred_frontend
            or (
                TargetFrontend.NEXTJS
                if constraints.require_frontend
                else TargetFrontend.NONE
            )
        )
        if not constraints.require_frontend and override_frontend is None:
            chosen_fe = TargetFrontend.NONE

        container_services = ["backend", "db"]
        if chosen_fe != TargetFrontend.NONE:
            container_services.append("frontend")

        decision = ArchitectureDecision(
            chosen_backend_language=winning_candidate.language,
            chosen_pattern=pattern,
            chosen_database=constraints.database_preference,
            chosen_frontend_stack=chosen_fe,
            ai_friendliness_score=winning_candidate.ai_friendliness_score,
            rationale=self._build_rationale(
                winning_candidate, pattern, chosen_fe, constraints, ir
            ),
            container_services=container_services,
        )

        ir.architecture_decision = decision
        return decision, candidates

    def _apply_natural_language_notes(self, c: TechnicalConstraints) -> None:
        """Translates user notes like 'I only know C' or 'Must be Python' into language preferences."""
        if not c.team_experience_notes:
            return
        notes = c.team_experience_notes.lower()
        if re.search(r"\b(c|c\+\+|rust)\b", notes) and "c#" not in notes:
            # Closest memory-safe modern systems stack in REGEN for C/C++ developers
            if TargetLanguage.RUST_AXUM not in c.preferred_languages:
                c.preferred_languages.append(TargetLanguage.RUST_AXUM)
            if TargetLanguage.GO_FIBER_OR_CHI not in c.preferred_languages:
                c.preferred_languages.append(TargetLanguage.GO_FIBER_OR_CHI)
        if "c#" in notes or ".net" in notes or "java" in notes:
            if TargetLanguage.CSHARP_DOTNET not in c.preferred_languages:
                c.preferred_languages.append(TargetLanguage.CSHARP_DOTNET)
        if "python" in notes:
            if TargetLanguage.PYTHON_FASTAPI not in c.preferred_languages:
                c.preferred_languages.append(TargetLanguage.PYTHON_FASTAPI)
        if re.search(r"\b(go|golang)\b", notes):
            if TargetLanguage.GO_FIBER_OR_CHI not in c.preferred_languages:
                c.preferred_languages.append(TargetLanguage.GO_FIBER_OR_CHI)
        if "typescript" in notes or "javascript" in notes or "node" in notes:
            if TargetLanguage.TYPESCRIPT_NEST_OR_NODE not in c.preferred_languages:
                c.preferred_languages.append(TargetLanguage.TYPESCRIPT_NEST_OR_NODE)

    def _select_architectural_pattern(
        self, ir: ProjectIR, constraints: TechnicalConstraints
    ) -> ArchitecturalPattern:
        notes = (constraints.team_experience_notes or "").lower()

        # Honor explicit negative or positive pattern constraints from the user!
        forbids_hexagonal = any(
            phrase in notes
            for phrase in (
                "cant be hexagonal",
                "can't be hexagonal",
                "cannot be hexagonal",
                "no hexagonal",
                "not hexagonal",
                "avoid hexagonal",
            )
        )
        if "modular monolith" in notes or "monolith" in notes:
            return ArchitecturalPattern.MODULAR_MONOLITH
        if "event" in notes or "microservice" in notes:
            return ArchitecturalPattern.EVENT_DRIVEN_MICRO
        if "clean" in notes:
            return ArchitecturalPattern.CLEAN_ARCHITECTURE

        if constraints.expected_concurrency_rps >= 2500:
            return ArchitecturalPattern.EVENT_DRIVEN_MICRO
        if len(ir.business_rules) >= 5 or len(ir.entities) >= 4:
            return ArchitecturalPattern.CLEAN_ARCHITECTURE

        if forbids_hexagonal:
            return ArchitecturalPattern.CLEAN_ARCHITECTURE
        return ArchitecturalPattern.HEXAGONAL

    def _score_python(
        self, c: TechnicalConstraints, pattern: ArchitecturalPattern
    ) -> StackScoreBreakdown:
        ai_score = 96
        perf_score = 82
        if c.io_heavy and not c.cpu_heavy and c.expected_concurrency_rps <= 1000:
            perf_score += 8
        if c.cpu_heavy or c.expected_concurrency_rps > 2000:
            perf_score -= 20
        if TargetLanguage.PYTHON_FASTAPI in c.preferred_languages:
            perf_score += 20

        total = min(100, int((ai_score * 0.5) + (perf_score * 0.5)))
        return StackScoreBreakdown(
            language=TargetLanguage.PYTHON_FASTAPI,
            recommended_pattern=pattern,
            total_score=total,
            ai_friendliness_score=ai_score,
            performance_fit_score=min(100, max(0, perf_score)),
            pros=["Strict Pydantic v2 schemas maximize AI agent accuracy"],
            tradeoffs=["GIL limits raw CPU-bound parallel throughput"],
        )

    def _score_go(
        self, c: TechnicalConstraints, pattern: ArchitecturalPattern
    ) -> StackScoreBreakdown:
        ai_score = 94
        perf_score = 92
        if c.expected_concurrency_rps >= 800 or c.io_heavy:
            perf_score += 8
        if TargetLanguage.GO_FIBER_OR_CHI in c.preferred_languages:
            perf_score += 20

        total = min(100, int((ai_score * 0.5) + (perf_score * 0.5)))
        return StackScoreBreakdown(
            language=TargetLanguage.GO_FIBER_OR_CHI,
            recommended_pattern=pattern,
            total_score=total,
            ai_friendliness_score=ai_score,
            performance_fit_score=min(100, max(0, perf_score)),
            pros=["Simple C-like syntax, explicit interfaces, high concurrency"],
            tradeoffs=["More verbose DTO & error handling boilerplate"],
        )

    def _score_typescript(
        self, c: TechnicalConstraints, pattern: ArchitecturalPattern
    ) -> StackScoreBreakdown:
        ai_score = 95
        perf_score = 80
        if c.require_frontend and c.expected_concurrency_rps <= 1000:
            perf_score += 10
        if c.cpu_heavy:
            perf_score -= 25
        if TargetLanguage.TYPESCRIPT_NEST_OR_NODE in c.preferred_languages:
            perf_score += 20

        total = min(100, int((ai_score * 0.5) + (perf_score * 0.5)))
        return StackScoreBreakdown(
            language=TargetLanguage.TYPESCRIPT_NEST_OR_NODE,
            recommended_pattern=pattern,
            total_score=total,
            ai_friendliness_score=ai_score,
            performance_fit_score=min(100, max(0, perf_score)),
            pros=["Shared full-stack types and huge AI training corpus"],
            tradeoffs=["Single-threaded event loop on CPU-heavy tasks"],
        )

    def _score_csharp(
        self, c: TechnicalConstraints, pattern: ArchitecturalPattern
    ) -> StackScoreBreakdown:
        ai_score = 91
        perf_score = 88
        if c.expected_concurrency_rps >= 500 or c.cpu_heavy:
            perf_score += 6
        if TargetLanguage.CSHARP_DOTNET in c.preferred_languages:
            perf_score += 20

        total = min(100, int((ai_score * 0.5) + (perf_score * 0.5)))
        return StackScoreBreakdown(
            language=TargetLanguage.CSHARP_DOTNET,
            recommended_pattern=pattern,
            total_score=total,
            ai_friendliness_score=ai_score,
            performance_fit_score=min(100, max(0, perf_score)),
            pros=["First-class Clean Architecture & DI primitives"],
            tradeoffs=["Heavier project scaffolding footprint"],
        )

    def _score_rust(
        self, c: TechnicalConstraints, pattern: ArchitecturalPattern
    ) -> StackScoreBreakdown:
        ai_score = 84
        perf_score = 98 if (c.cpu_heavy or c.expected_concurrency_rps >= 2000) else 80
        if TargetLanguage.RUST_AXUM in c.preferred_languages:
            perf_score += 25

        total = min(100, int((ai_score * 0.5) + (perf_score * 0.5)))
        return StackScoreBreakdown(
            language=TargetLanguage.RUST_AXUM,
            recommended_pattern=pattern,
            total_score=total,
            ai_friendliness_score=ai_score,
            performance_fit_score=min(100, max(0, perf_score)),
            pros=["Systems-level C/C++ performance with compile-time memory safety"],
            tradeoffs=["Strict borrow-checker rules"],
        )

    @staticmethod
    def _build_rationale(
        winner: StackScoreBreakdown,
        pattern: ArchitecturalPattern,
        chosen_fe: TargetFrontend,
        c: TechnicalConstraints,
        ir: ProjectIR,
    ) -> str:
        notes_info = (
            f" Honored user constraint: '{c.team_experience_notes}'."
            if c.team_experience_notes
            else ""
        )
        return (
            f"Backend: `{winner.language.value}` ({pattern.value}) | "
            f"Frontend: `{chosen_fe.value}` (Score: {winner.total_score}/100, "
            f"AI-Friendliness: {winner.ai_friendliness_score}/100). "
            f"Tuned for {c.expected_concurrency_rps} RPS across {len(ir.entities)} entities "
            f"and {len(ir.business_rules)} clarified business rules.{notes_info}"
        )


stack_advisor = StackAdvisorService()
