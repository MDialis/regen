import re
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.services.architect.industry_benchmarks import (
    BACKEND_INDUSTRY_BASE,
    BACKEND_PROXIMITY_MATRIX,
    FRONTEND_INDUSTRY_BASE,
    FRONTEND_PROXIMITY_MATRIX,
)

from app.domain.ir_schema import (
    ArchitecturalPattern,
    ArchitectureDecision,
    ProjectIR,
    TargetFrontend,
    TargetLanguage,
    TechnicalConstraints,
)
from app.domain.wizard_state import (
    AHPWeightsBreakdown,
    FrontendScoreBreakdown,
    StackScoreBreakdown,
)
from app.services.llm_router import llm_router

# ============================================================================
# 1. VERIFIABLE INDUSTRY BENCHMARK MATRICES (0-100)
# ============================================================================

BENCHMARK_SOURCES: Dict[str, str] = {
    "performance": "TechEmpower Web Framework Benchmarks (Round 22/23 Composite Throughput & Latency) - [https://www.techempower.com/benchmarks/](https://www.techempower.com/benchmarks/)",
    "ecosystem": "Stack Overflow Developer Survey (2024/2025 Professional Adoption) & GitHub Octoverse - [https://survey.stackoverflow.co/2024/technology](https://survey.stackoverflow.co/2024/technology)",
    "velocity": "JetBrains State of Developer Ecosystem & CRUD Boilerplate Token Ratio - [https://www.jetbrains.com/lp/devecosystem-2024/](https://www.jetbrains.com/lp/devecosystem-2024/)",
    "ai_friendliness": "MultiPL-E & BigCodeBench / EvalPlus LLM pass@1 Code Synthesis Accuracy - [https://huggingface.co/spaces/bigcode/bigcode-models-leaderboard](https://huggingface.co/spaces/bigcode/bigcode-models-leaderboard)",
    "frontend": "State of JS 2024 & HTTP Archive Core Web Vitals (CrUX) Report - [https://2024.stateofjs.com/](https://2024.stateofjs.com/)",
}

# ============================================================================
# 2. PARADIGM PROXIMITY MATRICES (APPLIED ONLY TO POSITIVE SENTIMENT!)
# ============================================================================


class SentimentItem(BaseModel):
    tech_key: str = Field(
        ...,
        description="One of: python, go, typescript, csharp, rust, c_cpp, nextjs, react_vite, vue_vite, sveltekit, angular",
    )
    polarity: str = Field(..., description="'positive' or 'negative'")
    intensity: float = Field(
        ...,
        ge=0.1,
        le=1.0,
        description="1.0 = 'only know/must use/hate', 0.6 = 'know better/prefer/dislike', 0.35 = 'slightly familiar'",
    )


class LLMSentimentExtractionSchema(BaseModel):
    sentiments: List[SentimentItem] = Field(default_factory=list)


class StackAdvisorService:
    """
    MCDM / Analytic Hierarchy Process (AHP) Recommendation Engine.
    1. Computes dynamic AHP priority weights from project characteristics.
    2. Scores both Backend and Frontend stacks against verifiable industry data.
    3. Applies graduated familiarity boosts (+10 max with AI / +20 max without AI) with proximity bleed.
    4. Applies graduated negative penalties (-5 max with AI / -10 max without AI) with ZERO proximity bleed.
    """

    def evaluate_and_recommend(
        self,
        ir: ProjectIR,
        constraints: TechnicalConstraints,
        override_language: Optional[TargetLanguage] = None,
        override_frontend: Optional[TargetFrontend] = None,
    ) -> Tuple[
        ArchitectureDecision,
        AHPWeightsBreakdown,
        List[StackScoreBreakdown],
        List[FrontendScoreBreakdown],
    ]:
        ir.technical_constraints = constraints
        pattern = self._select_architectural_pattern(ir, constraints)
        ahp_weights = self._compute_dynamic_ahp_weights(ir, constraints)

        # Extract graduated positive/negative sentiments from notes
        sentiments = self._extract_sentiments_deterministic(
            constraints.team_experience_notes or ""
        )

        # Score Backend Stacks
        backend_candidates = self._score_all_backends(
            constraints, pattern, ahp_weights, sentiments
        )
        backend_candidates.sort(key=lambda c: c.total_score, reverse=True)

        winning_backend = backend_candidates[0]
        if override_language:
            for cand in backend_candidates:
                if cand.language == override_language:
                    winning_backend = cand
                    break

        # Score Frontend Frameworks
        frontend_candidates = self._score_all_frontends(ir, constraints, sentiments)
        frontend_candidates.sort(key=lambda f: f.total_score, reverse=True)

        if not constraints.require_frontend and override_frontend is None:
            chosen_fe = TargetFrontend.NONE
        elif override_frontend is not None:
            chosen_fe = override_frontend
        else:
            chosen_fe = frontend_candidates[0].framework

        container_services = ["backend", "db"]
        if chosen_fe != TargetFrontend.NONE:
            container_services.append("frontend")

        decision = ArchitectureDecision(
            chosen_backend_language=winning_backend.language,
            chosen_pattern=pattern,
            chosen_database=constraints.database_preference,
            chosen_frontend_stack=chosen_fe,
            ai_friendliness_score=winning_backend.ai_friendliness_score,
            rationale=self._build_rationale(
                winning_backend,
                frontend_candidates[0] if frontend_candidates else None,
                pattern,
                chosen_fe,
                ahp_weights,
                constraints,
            ),
            container_services=container_services,
        )

        ir.architecture_decision = decision
        return decision, ahp_weights, backend_candidates, frontend_candidates

    # ========================================================================
    # PHASE A: DYNAMIC AHP PRIORITY WEIGHTS
    # ========================================================================

    def _compute_dynamic_ahp_weights(
        self, ir: ProjectIR, c: TechnicalConstraints
    ) -> AHPWeightsBreakdown:
        """
        Dynamically shifts priority between CRUD Velocity, TechEmpower Performance,
        StackOverflow Ecosystem, and AI Maintainability based on project profile.
        """
        rps = c.expected_concurrency_rps
        is_crud_dominant = len(ir.entities) >= 1 and not c.cpu_heavy and rps <= 400

        if is_crud_dominant:
            # Typical CRUD / Business App: Velocity & Ecosystem dominate over raw RPS
            w_vel = 0.40
            w_eco = 0.25
            w_perf = 0.15
            w_ai = 0.20 if c.will_use_ai_coding_assistants else 0.10
        elif c.cpu_heavy or rps >= 1500:
            # High-load / Compute-heavy system: TechEmpower Performance dominates
            w_vel = 0.15
            w_eco = 0.15
            w_perf = 0.55
            w_ai = 0.15 if c.will_use_ai_coding_assistants else 0.05
        else:
            # Balanced mid-scale service (400 - 1499 RPS)
            w_vel = 0.28
            w_eco = 0.22
            w_perf = 0.32
            w_ai = 0.18 if c.will_use_ai_coding_assistants else 0.08

        total = w_vel + w_eco + w_perf + w_ai
        return AHPWeightsBreakdown(
            velocity_weight=round(w_vel / total, 2),
            performance_weight=round(w_perf / total, 2),
            ecosystem_weight=round(w_eco / total, 2),
            ai_weight=round(w_ai / total, 2),
        )

    # ========================================================================
    # PHASE B & C: GRADUATED SENTIMENT & PROXIMITY MODIFIERS
    # ========================================================================

    def _extract_sentiments_deterministic(self, notes: str) -> List[SentimentItem]:
        """
        Parses natural-language skill & preference statements and assigns
        graduated intensity (1.0 for 'only/must/never', 0.6 for 'better/prefer/don't like',
        0.35 for 'familiar/some experience').
        """
        if not notes.strip():
            return []

        clauses = re.split(r"[.;,\n]|(?:\band\b)|(?:\bbut\b)", notes.lower())
        tech_patterns = {
            "python": r"\b(python|fastapi|django|flask)\b",
            "go": r"\b(go|golang)\b",
            "typescript": r"\b(typescript|javascript|node|nodejs|nestjs|ts|js)\b",
            "csharp": r"(?:\bc#|\b\.net|\bdotnet|\bjava\b)",
            "rust": r"\brust\b",
            "c_cpp": r"(?:\bc\b|\bc\+\+|\bcpp\b)",
            "nextjs": r"\b(nextjs|next\.js|next)\b",
            "react_vite": r"\b(react|vite)\b",
            "vue_vite": r"\b(vue|vuejs)\b",
            "sveltekit": r"\b(svelte|sveltekit)\b",
            "angular": r"\bangular\b",
        }

        extracted: List[SentimentItem] = []

        for clause in clauses:
            clause = clause.strip()
            if not clause:
                continue

            is_neg = any(
                neg in clause
                for neg in (
                    "don't like",
                    "dont like",
                    "dislike",
                    "hate",
                    "never",
                    "avoid",
                    "not ",
                    "no ",
                    "tired of",
                    "something different",
                    "sick of",
                )
            )

            # Determine graduated intensity (0.35 to 1.0)
            if is_neg:
                if any(w in clause for w in ("hate", "never", "strictly no", "refuse")):
                    intensity = 1.0
                elif any(
                    w in clause
                    for w in (
                        "don't like",
                        "dont like",
                        "dislike",
                        "avoid",
                        "something different",
                        "tired",
                    )
                ):
                    intensity = 0.7
                else:
                    intensity = 0.5
            else:
                if any(
                    w in clause
                    for w in ("only", "exclusively", "must", "strictly", "all we know")
                ):
                    intensity = 1.0
                elif any(
                    w in clause
                    for w in (
                        "better",
                        "prefer",
                        "strong",
                        "experienced",
                        "main",
                        "love",
                        "best",
                    )
                ):
                    intensity = 0.6
                else:
                    intensity = 0.4

            for tech_key, pattern in tech_patterns.items():
                if re.search(pattern, clause):
                    extracted.append(
                        SentimentItem(
                            tech_key=tech_key,
                            polarity="negative" if is_neg else "positive",
                            intensity=intensity,
                        )
                    )

        return extracted

    def _compute_backend_modifiers(
        self,
        c: TechnicalConstraints,
        sentiments: List[SentimentItem],
    ) -> Tuple[Dict[TargetLanguage, float], Dict[TargetLanguage, float]]:
        """
        Returns (direct_familiarity_modifiers, proximity_modifiers).
        - Positive cap: +10.0 (if will_use_ai_coding_assistants=True) else +20.0
        - Negative cap: -5.0 (if will_use_ai_coding_assistants=True) else -10.0
        - Negative sentiments NEVER bleed into similar languages!
        """
        max_pos = 10.0 if c.will_use_ai_coding_assistants else 20.0
        max_neg = 5.0 if c.will_use_ai_coding_assistants else 10.0

        direct_mods: Dict[TargetLanguage, float] = {
            lang: 0.0 for lang in TargetLanguage
        }
        prox_mods: Dict[TargetLanguage, float] = {lang: 0.0 for lang in TargetLanguage}

        key_to_enum: Dict[str, TargetLanguage] = {
            "python": TargetLanguage.PYTHON_FASTAPI,
            "go": TargetLanguage.GO_FIBER_OR_CHI,
            "typescript": TargetLanguage.TYPESCRIPT_NEST_OR_NODE,
            "csharp": TargetLanguage.CSHARP_DOTNET,
            "rust": TargetLanguage.RUST_AXUM,
        }

        for item in sentiments:
            if item.polarity == "positive":
                boost = round(max_pos * item.intensity, 1)
                if item.tech_key in key_to_enum:
                    target_lang = key_to_enum[item.tech_key]
                    direct_mods[target_lang] = max(direct_mods[target_lang], boost)

                # Apply paradigm proximity bleed for positive skills (including c_cpp)
                prox_table = BACKEND_PROXIMITY_MATRIX.get(item.tech_key, {})
                for neighbor_lang, factor in prox_table.items():
                    bleed = round(boost * factor, 1)
                    prox_mods[neighbor_lang] = max(prox_mods[neighbor_lang], bleed)

            elif item.polarity == "negative":
                # Negative penalty applies strictly to the named language (ZERO proximity bleed)
                if item.tech_key in key_to_enum:
                    target_lang = key_to_enum[item.tech_key]
                    penalty = -round(max_neg * item.intensity, 1)
                    direct_mods[target_lang] = min(direct_mods[target_lang], penalty)

        # Ensure a language doesn't simultaneously get its own proximity bleed if directly boosted
        for lang in TargetLanguage:
            if direct_mods[lang] != 0.0:
                prox_mods[lang] = 0.0

        return direct_mods, prox_mods

    def _compute_frontend_modifiers(
        self,
        c: TechnicalConstraints,
        sentiments: List[SentimentItem],
    ) -> Tuple[Dict[TargetFrontend, float], Dict[TargetFrontend, float]]:
        max_pos = 10.0 if c.will_use_ai_coding_assistants else 20.0
        max_neg = 5.0 if c.will_use_ai_coding_assistants else 10.0

        direct_mods: Dict[TargetFrontend, float] = {fe: 0.0 for fe in TargetFrontend}
        prox_mods: Dict[TargetFrontend, float] = {fe: 0.0 for fe in TargetFrontend}

        key_to_fe: Dict[str, TargetFrontend] = {
            "nextjs": TargetFrontend.NEXTJS,
            "react_vite": TargetFrontend.REACT_VITE,
            "vue_vite": TargetFrontend.VUE_VITE,
            "sveltekit": TargetFrontend.SVELTEKIT,
            "angular": TargetFrontend.ANGULAR,
        }

        for item in sentiments:
            if item.tech_key not in key_to_fe:
                continue
            target_fe = key_to_fe[item.tech_key]

            if item.polarity == "positive":
                boost = round(max_pos * item.intensity, 1)
                direct_mods[target_fe] = max(direct_mods[target_fe], boost)
                for neighbor_fe, factor in FRONTEND_PROXIMITY_MATRIX.get(
                    target_fe, {}
                ).items():
                    prox_mods[neighbor_fe] = max(
                        prox_mods[neighbor_fe], round(boost * factor, 1)
                    )
            else:
                penalty = -round(max_neg * item.intensity, 1)
                direct_mods[target_fe] = min(direct_mods[target_fe], penalty)

        for fe in TargetFrontend:
            if direct_mods[fe] != 0.0:
                prox_mods[fe] = 0.0

        return direct_mods, prox_mods

    # ========================================================================
    # SCORING & RANKING CALCULATORS
    # ========================================================================

    def _score_all_backends(
        self,
        c: TechnicalConstraints,
        pattern: ArchitecturalPattern,
        w: AHPWeightsBreakdown,
        sentiments: List[SentimentItem],
    ) -> List[StackScoreBreakdown]:
        direct_mods, prox_mods = self._compute_backend_modifiers(c, sentiments)
        results: List[StackScoreBreakdown] = []

        pros_map = {
            TargetLanguage.PYTHON_FASTAPI: [
                "Highest CRUD velocity & #1 LLM code synthesis pass@1 (MultiPL-E)",
                "Massive Stack Overflow & data/AI library ecosystem",
            ],
            TargetLanguage.TYPESCRIPT_NEST_OR_NODE: [
                "#1 largest developer talent pool & shared full-stack types with frontend",
                "High async I/O CRUD velocity",
            ],
            TargetLanguage.CSHARP_DOTNET: [
                "Top-tier enterprise balance: 88/100 TechEmpower speed + rich ORM/DI",
                "First-class Clean Architecture boundaries",
            ],
            TargetLanguage.GO_FIBER_OR_CHI: [
                "91/100 TechEmpower throughput with minimal memory footprint",
                "Simple explicit control flow prevents AI hallucinations",
            ],
            TargetLanguage.RUST_AXUM: [
                "99/100 TechEmpower benchmark leader & zero-GC tail latency",
                "Compile-time memory safety for CPU-critical workloads",
            ],
        }

        tradeoffs_map = {
            TargetLanguage.PYTHON_FASTAPI: [
                "Lower raw RPS (44/100 TechEmpower) under heavy CPU/concurrency"
            ],
            TargetLanguage.TYPESCRIPT_NEST_OR_NODE: [
                "Single-threaded event loop penalizes CPU-bound tasks"
            ],
            TargetLanguage.CSHARP_DOTNET: ["Heavier solution & project boilerplate"],
            TargetLanguage.GO_FIBER_OR_CHI: [
                "Lower CRUD velocity (68/100) due to explicit DTO/error boilerplate"
            ],
            TargetLanguage.RUST_AXUM: [
                "Lowest CRUD velocity (45/100) & borrow-checker slows AI coding loops"
            ],
        }

        for lang, metrics in BACKEND_INDUSTRY_BASE.items():
            base_score = (
                metrics["velocity"] * w.velocity_weight
                + metrics["performance"] * w.performance_weight
                + metrics["ecosystem"] * w.ecosystem_weight
                + metrics["ai_friendliness"] * w.ai_weight
            )
            base_rounded = round(base_score, 1)
            f_mod = direct_mods.get(lang, 0.0)
            p_mod = prox_mods.get(lang, 0.0)
            final_score = round(min(100.0, max(0.0, base_rounded + f_mod + p_mod)), 1)

            results.append(
                StackScoreBreakdown(
                    language=lang,
                    recommended_pattern=pattern,
                    total_score=final_score,
                    base_industry_score=base_rounded,
                    familiarity_modifier=f_mod,
                    proximity_modifier=p_mod,
                    velocity_score=metrics["velocity"],
                    performance_fit_score=metrics["performance"],
                    ecosystem_score=metrics["ecosystem"],
                    ai_friendliness_score=metrics["ai_friendliness"],
                    pros=pros_map[lang],
                    tradeoffs=tradeoffs_map[lang],
                )
            )

        return results

    def _score_all_frontends(
        self,
        ir: ProjectIR,
        c: TechnicalConstraints,
        sentiments: List[SentimentItem],
    ) -> List[FrontendScoreBreakdown]:
        direct_mods, prox_mods = self._compute_frontend_modifiers(c, sentiments)
        notes = (c.team_experience_notes or "").lower()

        # Determine if SEO/SSR or pure internal SPA dashboard is more appropriate
        needs_seo = any(
            w in notes
            for w in (
                "seo",
                "public",
                "ecommerce",
                "e-commerce",
                "landing",
                "marketing",
                "blog",
            )
        )
        w_seo = 0.40 if needs_seo else 0.15
        w_spa = 0.20 if needs_seo else 0.45
        w_eco = 0.25
        w_ai = 0.15

        rationales = {
            TargetFrontend.NEXTJS: "Best for SSR/SEO, full-stack routing, and shadcn/ui AI friendliness.",
            TargetFrontend.REACT_VITE: "Fastest SPA build velocity & #1 component ecosystem for internal dashboards.",
            TargetFrontend.VUE_VITE: "Clean template/script separation and gentle learning curve for CRUD apps.",
            TargetFrontend.SVELTEKIT: "Compiler-driven minimal bundle size with high interactivity.",
            TargetFrontend.ANGULAR: "Strict dependency injection & enterprise OOP structure.",
        }

        results: List[FrontendScoreBreakdown] = []
        for fe, metrics in FRONTEND_INDUSTRY_BASE.items():
            base = (
                metrics["seo_ssr"] * w_seo
                + metrics["interactivity_spa"] * w_spa
                + metrics["ecosystem"] * w_eco
                + metrics["ai_friendliness"] * w_ai
            )
            base_rounded = round(base, 1)
            f_mod = direct_mods.get(fe, 0.0)
            p_mod = prox_mods.get(fe, 0.0)
            final_score = round(min(100.0, max(0.0, base_rounded + f_mod + p_mod)), 1)

            results.append(
                FrontendScoreBreakdown(
                    framework=fe,
                    total_score=final_score,
                    base_industry_score=base_rounded,
                    familiarity_modifier=f_mod,
                    proximity_modifier=p_mod,
                    seo_ssr_score=metrics["seo_ssr"],
                    interactivity_spa_score=metrics["interactivity_spa"],
                    ecosystem_score=metrics["ecosystem"],
                    ai_friendliness_score=metrics["ai_friendliness"],
                    rationale=rationales[fe],
                )
            )

        return results

    def _select_architectural_pattern(
        self, ir: ProjectIR, constraints: TechnicalConstraints
    ) -> ArchitecturalPattern:
        notes = (constraints.team_experience_notes or "").lower()
        forbids_hexagonal = any(
            p in notes
            for p in (
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

    @staticmethod
    def _build_rationale(
        winner_be: StackScoreBreakdown,
        winner_fe: Optional[FrontendScoreBreakdown],
        pattern: ArchitecturalPattern,
        chosen_fe: TargetFrontend,
        w: AHPWeightsBreakdown,
        c: TechnicalConstraints,
    ) -> str:
        ai_mode_str = (
            "AI-Assisted Coding ON (Familiarity cap: +10/-5)"
            if c.will_use_ai_coding_assistants
            else "AI-Free Coding (Familiarity cap: +20/-10)"
        )
        mod_details = ""
        if winner_be.familiarity_modifier != 0 or winner_be.proximity_modifier != 0:
            mod_details = (
                f" [Base: {winner_be.base_industry_score}, "
                f"Direct Skill Mod: {winner_be.familiarity_modifier:+.1f}, "
                f"Proximity Mod: {winner_be.proximity_modifier:+.1f}]"
            )
        fe_score_info = (
            f"{chosen_fe.value} ({winner_fe.total_score}/100)"
            if winner_fe and chosen_fe != TargetFrontend.NONE
            else chosen_fe.value
        )
        return (
            f"Recommended Backend: `{winner_be.language.value}` ({winner_be.total_score}/100){mod_details} "
            f"with `{pattern.value}` architecture | Recommended Frontend: `{fe_score_info}`. "
            f"AHP Weights -> Velocity: {int(w.velocity_weight*100)}%, "
            f"Performance: {int(w.performance_weight*100)}%, "
            f"Ecosystem: {int(w.ecosystem_weight*100)}%, "
            f"AI: {int(w.ai_weight*100)}% ({ai_mode_str})."
        )


stack_advisor = StackAdvisorService()
