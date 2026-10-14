from typing import List, Optional, Tuple
from app.domain.ir_schema import (
    ArchitecturalPattern,
    ArchitectureDecision,
    ProjectIR,
    TargetFrontend,
    TargetLanguage,
    TechnicalConstraints,
)

from app.domain.wizard_state import StackScoreBreakdown


class StackAdvisorService:
    """
    Deterministic multi-criteria decision engine that evaluates I/O profile,
    concurrency requirements, domain complexity, and AI-Friendliness to recommend
    an architecture and tech stack.
    """

    # Inside StackAdvisorService.evaluate_and_recommend:
    def evaluate_and_recommend(
        self,
        ir: ProjectIR,
        constraints: TechnicalConstraints,
        override_language: Optional[TargetLanguage] = None,
        override_frontend: Optional[TargetFrontend] = None,
    ) -> Tuple[ArchitectureDecision, List[StackScoreBreakdown]]:
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

        # Determine Frontend Stack independently
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
            chosen_pattern=winning_candidate.recommended_pattern,
            chosen_database=constraints.database_preference,
            chosen_frontend_stack=chosen_fe,
            ai_friendliness_score=winning_candidate.ai_friendliness_score,
            rationale=self._build_rationale(
                winning_candidate, chosen_fe, constraints, ir
            ),
            container_services=container_services,
        )

        ir.architecture_decision = decision
        return decision, candidates

    def _select_architectural_pattern(
        self, ir: ProjectIR, constraints: TechnicalConstraints
    ) -> ArchitecturalPattern:
        rule_count = len(ir.business_rules)
        entity_count = len(ir.entities)

        if constraints.expected_concurrency_rps >= 2500:
            return ArchitecturalPattern.EVENT_DRIVEN_MICRO
        if rule_count >= 5 or entity_count >= 4:
            return ArchitecturalPattern.CLEAN_ARCHITECTURE
        return ArchitecturalPattern.HEXAGONAL

    def _score_python(
        self, c: TechnicalConstraints, pattern: ArchitecturalPattern
    ) -> StackScoreBreakdown:
        ai_score = (
            96  # Pydantic v2 + FastAPI type hints are top-tier for Copilot/Cursor
        )
        perf_score = 82
        if c.io_heavy and not c.cpu_heavy and c.expected_concurrency_rps <= 1000:
            perf_score += 8
        if c.cpu_heavy or c.expected_concurrency_rps > 2000:
            perf_score -= 20
        if TargetLanguage.PYTHON_FASTAPI in c.preferred_languages:
            perf_score += 15

        total = min(100, int((ai_score * 0.5) + (perf_score * 0.5)))
        return StackScoreBreakdown(
            language=TargetLanguage.PYTHON_FASTAPI,
            recommended_pattern=pattern,
            total_score=total,
            ai_friendliness_score=ai_score,
            performance_fit_score=min(100, max(0, perf_score)),
            pros=[
                "Strict Pydantic v2 schemas maximize AI coding agent accuracy",
                "Rapid async I/O development with FastAPI and SQLAlchemy 2.0",
            ],
            tradeoffs=[
                "GIL limits raw CPU-bound parallel throughput compared to Go/Rust"
            ],
        )

    def _score_go(
        self, c: TechnicalConstraints, pattern: ArchitecturalPattern
    ) -> StackScoreBreakdown:
        ai_score = 94  # Explicit interfaces, minimal magic, flat control flow
        perf_score = 92
        if c.expected_concurrency_rps >= 800 or c.io_heavy:
            perf_score += 8
        if TargetLanguage.GO_FIBER_OR_CHI in c.preferred_languages:
            perf_score += 15

        total = min(100, int((ai_score * 0.5) + (perf_score * 0.5)))
        return StackScoreBreakdown(
            language=TargetLanguage.GO_FIBER_OR_CHI,
            recommended_pattern=ArchitecturalPattern.HEXAGONAL,
            total_score=total,
            ai_friendliness_score=ai_score,
            performance_fit_score=min(100, max(0, perf_score)),
            pros=[
                "Explicit interfaces and zero decorator magic prevent AI hallucinations",
                "Goroutines handle high concurrency with minimal memory footprint",
            ],
            tradeoffs=["More verbose error handling and DTO mapping boilerplate"],
        )

    def _score_typescript(
        self, c: TechnicalConstraints, pattern: ArchitecturalPattern
    ) -> StackScoreBreakdown:
        ai_score = 95  # Shared types across full-stack + massive LLM training corpus
        perf_score = 80
        if c.require_frontend and c.expected_concurrency_rps <= 1000:
            perf_score += 10
        if c.cpu_heavy:
            perf_score -= 25
        if TargetLanguage.TYPESCRIPT_NEST_OR_NODE in c.preferred_languages:
            perf_score += 15

        total = min(100, int((ai_score * 0.5) + (perf_score * 0.5)))
        return StackScoreBreakdown(
            language=TargetLanguage.TYPESCRIPT_NEST_OR_NODE,
            recommended_pattern=pattern,
            total_score=total,
            ai_friendliness_score=ai_score,
            performance_fit_score=min(100, max(0, perf_score)),
            pros=[
                "End-to-end type safety with Next.js frontend and NestJS DI containers",
                "Largest training corpus for Cursor/Copilot code completion",
            ],
            tradeoffs=["Single-threaded event loop struggles on CPU-intensive rules"],
        )

    def _score_csharp(
        self, c: TechnicalConstraints, pattern: ArchitecturalPattern
    ) -> StackScoreBreakdown:
        ai_score = 91  # Strong enterprise DI & interfaces
        perf_score = 88
        if c.expected_concurrency_rps >= 500 or c.cpu_heavy:
            perf_score += 6
        if TargetLanguage.CSHARP_DOTNET in c.preferred_languages:
            perf_score += 15

        total = min(100, int((ai_score * 0.5) + (perf_score * 0.5)))
        return StackScoreBreakdown(
            language=TargetLanguage.CSHARP_DOTNET,
            recommended_pattern=ArchitecturalPattern.CLEAN_ARCHITECTURE,
            total_score=total,
            ai_friendliness_score=ai_score,
            performance_fit_score=min(100, max(0, perf_score)),
            pros=[
                "First-class Clean Architecture & Dependency Injection primitives",
                "High JIT throughput for enterprise domain modeling",
            ],
            tradeoffs=["Heavier solution/project scaffolding footprint"],
        )

    def _score_rust(
        self, c: TechnicalConstraints, pattern: ArchitecturalPattern
    ) -> StackScoreBreakdown:
        ai_score = 82  # Borrow checker can require extra iterations for AI agents
        perf_score = 98 if (c.cpu_heavy or c.expected_concurrency_rps >= 2000) else 78
        if TargetLanguage.RUST_AXUM in c.preferred_languages:
            perf_score += 15

        total = min(100, int((ai_score * 0.5) + (perf_score * 0.5)))
        return StackScoreBreakdown(
            language=TargetLanguage.RUST_AXUM,
            recommended_pattern=ArchitecturalPattern.HEXAGONAL,
            total_score=total,
            ai_friendliness_score=ai_score,
            performance_fit_score=min(100, max(0, perf_score)),
            pros=[
                "Compile-time memory safety and unmatched tail-latency performance",
                "Exhaustive pattern matching guarantees business rule completeness",
            ],
            tradeoffs=[
                "Async lifetimes and borrow-checker rules increase AI iteration cycles"
            ],
        )

    @staticmethod
    def _build_rationale(
        winner: StackScoreBreakdown,
        chosen_fe: TargetFrontend,
        c: TechnicalConstraints,
        ir: ProjectIR,
    ) -> str:
        return (
            f"Backend: `{winner.language.value}` ({winner.recommended_pattern.value}) | "
            f"Frontend: `{chosen_fe.value}` (Score: {winner.total_score}/100, AI-Friendliness: "
            f"{winner.ai_friendliness_score}/100). Tuned for {c.expected_concurrency_rps} RPS "
            f"across {len(ir.entities)} entities and {len(ir.business_rules)} business rules."
        )


stack_advisor = StackAdvisorService()
