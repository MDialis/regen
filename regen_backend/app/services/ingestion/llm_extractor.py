# app/services/ingestion/llm_extractor.py
import re
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field

from app.config import settings
from app.domain.ir_schema import (
    AmbiguityStatus,
    BusinessRule,
    DataTypePrimitive,
    EntityDefinition,
    EntityField,
    HITLQuestion,
    HttpMethod,
    RouteDefinition,
    SourceModality,
    SourceReference,
    TargetLanguage,
    TechnicalConstraints,
)
from app.services.ingestion.ast_analyzer import ComplexCodeChunk
from app.services.llm_router import llm_router


class InferredEntityFieldSchema(BaseModel):
    name: str
    data_type: DataTypePrimitive = DataTypePrimitive.STRING
    is_primary_key: bool = False


class InferredEntitySchema(BaseModel):
    name: str = Field(
        ..., description="PascalCase singular entity name, e.g. Customer, Order"
    )
    description: str
    fields: List[InferredEntityFieldSchema] = Field(default_factory=list)


class InferredRuleSchema(BaseModel):
    title: str
    domain_context: str = "Core Domain"
    trigger_condition: str
    expected_behavior: str
    is_ambiguous: bool = False
    clarification_question: Optional[str] = None
    suggested_options: List[str] = Field(default_factory=list)


class InferredWorkloadSchema(BaseModel):
    estimated_rps: int = 200
    io_heavy: bool = True
    cpu_heavy: bool = False
    user_constraint_notes: Optional[str] = Field(
        None,
        description="Any stack/architecture constraints mentioned by user (e.g. 'Only knows C', 'Cannot be hexagonal')",
    )


class HolisticRequirementExtractionSchema(BaseModel):
    entities: List[InferredEntitySchema] = Field(default_factory=list)
    rules: List[InferredRuleSchema] = Field(default_factory=list)
    workload: InferredWorkloadSchema = Field(default_factory=InferredWorkloadSchema)


class LLMExtractorService:
    """
    Phase 1 Requirement Extractor.
    Uses local Ollama (`phi4-mini`) via `llm_router` to analyze complex AST chunks,
    condensed Python document summaries, and plain-text user descriptions.
    Includes deterministic fallback if Ollama is not running.
    """

    async def extract_from_complex_chunks(
        self, chunks: List[ComplexCodeChunk], low_vram_mode: Optional[bool] = None
    ) -> Tuple[List[BusinessRule], List[HITLQuestion]]:
        rules: List[BusinessRule] = []
        questions: List[HITLQuestion] = []

        for chunk in chunks:
            c_rules, c_questions = self._analyze_chunk_heuristically(chunk)
            rules.extend(c_rules)
            questions.extend(c_questions)

        return rules, questions

    async def analyze_documents_and_text(
        self,
        project_name: str,
        plain_text: str,
        doc_summaries: List[str],
        existing_entity_names: List[str],
        low_vram_mode: Optional[bool] = None,
    ) -> Tuple[
        List[EntityDefinition],
        List[RouteDefinition],
        List[BusinessRule],
        List[HITLQuestion],
        TechnicalConstraints,
    ]:
        combined_context = "\n\n".join(
            part for part in [plain_text.strip(), *doc_summaries] if part
        )
        if not combined_context.strip():
            return [], [], [], [], TechnicalConstraints()

        system_prompt = (
            "You are REGEN's Requirements & Domain Architect. "
            "Read the user's plain-text requirements and pre-processed document digests. "
            "1. Extract domain `entities` (with fields) needed for the system. "
            "2. Extract `rules` (business rules); if a requirement is vague or contradicts legacy behavior, "
            "set `is_ambiguous: true` and provide a `clarification_question` and 2-3 `suggested_options`. "
            "3. Infer `workload` (RPS, io_heavy, cpu_heavy) and capture any explicit stack/architecture "
            "constraints (e.g., 'I only know C', 'Must not use hexagonal architecture') in `user_constraint_notes`."
        )
        user_prompt = (
            f"Project: {project_name}\n"
            f"Already Extracted Entities: {', '.join(existing_entity_names) or 'None'}\n\n"
            f"Requirements & Processed Document Digests:\n{combined_context}"
        )

        llm_parsed = await llm_router.generate_structured(
            task="requirement_extraction",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=HolisticRequirementExtractionSchema,
            force_low_vram=low_vram_mode,
        )

        if llm_parsed:
            return self._convert_llm_schema_to_ir(llm_parsed, combined_context)

        # Offline / Zero-Ollama Heuristic Fallback (so text-only projects STILL work even if Ollama is off!)
        return self._heuristic_text_and_doc_fallback(
            project_name, combined_context, existing_entity_names
        )

    def _convert_llm_schema_to_ir(
        self, schema: HolisticRequirementExtractionSchema, raw_context: str
    ) -> Tuple[
        List[EntityDefinition],
        List[RouteDefinition],
        List[BusinessRule],
        List[HITLQuestion],
        TechnicalConstraints,
    ]:
        entities: List[EntityDefinition] = []
        routes: List[RouteDefinition] = []
        rules: List[BusinessRule] = []
        questions: List[HITLQuestion] = []

        for ent_item in schema.entities:
            fields = [
                EntityField(
                    name=f.name,
                    data_type=f.data_type,
                    is_required=True,
                    is_primary_key=f.is_primary_key or f.name.lower() == "id",
                )
                for f in ent_item.fields
            ]
            if not any(f.is_primary_key for f in fields):
                fields.insert(
                    0,
                    EntityField(
                        name="id",
                        data_type=DataTypePrimitive.INTEGER,
                        is_required=True,
                        is_primary_key=True,
                    ),
                )
            ent = EntityDefinition(
                name=ent_item.name,
                description=ent_item.description,
                fields=fields,
                sources=[SourceReference(modality=SourceModality.PLAIN_TEXT_REQ)],
            )
            entities.append(ent)
            slug = ent_item.name.lower() + "s"
            routes.append(
                RouteDefinition(
                    path=f"/{slug}",
                    method=HttpMethod.GET,
                    summary=f"List {ent_item.name} records",
                    response_entity_id=ent.id,
                    sources=[SourceReference(modality=SourceModality.PLAIN_TEXT_REQ)],
                )
            )
            routes.append(
                RouteDefinition(
                    path=f"/{slug}",
                    method=HttpMethod.POST,
                    summary=f"Create {ent_item.name} record",
                    response_entity_id=ent.id,
                    sources=[SourceReference(modality=SourceModality.PLAIN_TEXT_REQ)],
                )
            )

        for r_item in schema.rules:
            rule = BusinessRule(
                title=r_item.title,
                domain_context=r_item.domain_context,
                trigger_condition=r_item.trigger_condition,
                expected_behavior=r_item.expected_behavior,
                is_ambiguous=r_item.is_ambiguous,
                confidence_score=0.7 if r_item.is_ambiguous else 0.95,
                sources=[SourceReference(modality=SourceModality.PLAIN_TEXT_REQ)],
            )
            rules.append(rule)
            if r_item.is_ambiguous:
                questions.append(
                    HITLQuestion(
                        related_rule_id=rule.id,
                        question=r_item.clarification_question
                        or f"Please clarify requirement: '{r_item.title}'",
                        suggested_options=r_item.suggested_options
                        or [
                            "Enforce strictly as a synchronous validation rule",
                            "Make threshold configurable via database settings",
                            "Skip this rule for initial MVP",
                        ],
                        status=AmbiguityStatus.UNRESOLVED,
                    )
                )

        constraints = self._extract_constraints_from_text(
            raw_context,
            default_rps=schema.workload.estimated_rps,
            default_io=schema.workload.io_heavy,
            default_cpu=schema.workload.cpu_heavy,
            extra_notes=schema.workload.user_constraint_notes,
        )
        return entities, routes, rules, questions, constraints

    def _heuristic_text_and_doc_fallback(
        self,
        project_name: str,
        combined_context: str,
        existing_entity_names: List[str],
    ) -> Tuple[
        List[EntityDefinition],
        List[RouteDefinition],
        List[BusinessRule],
        List[HITLQuestion],
        TechnicalConstraints,
    ]:
        entities: List[EntityDefinition] = []
        routes: List[RouteDefinition] = []
        rules: List[BusinessRule] = []
        questions: List[HITLQuestion] = []

        # Extract candidate nouns if no entities exist yet
        if not existing_entity_names:
            common_domain_nouns = [
                "Invoice",
                "Customer",
                "User",
                "Order",
                "Product",
                "Payment",
                "Subscription",
                "Report",
                "Ticket",
                "Employee",
                "Account",
                "Transaction",
            ]
            found_nouns = [
                noun
                for noun in common_domain_nouns
                if re.search(rf"\b{noun}s?\b", combined_context, re.IGNORECASE)
            ]
            if not found_nouns:
                clean_proj = "".join(w.capitalize() for w in project_name.split())
                found_nouns = [f"{clean_proj}Item"]

            for noun in found_nouns[:4]:
                ent = EntityDefinition(
                    name=noun,
                    description=f"Inferred from plain-text specification for {project_name}",
                    fields=[
                        EntityField(
                            name="id",
                            data_type=DataTypePrimitive.INTEGER,
                            is_required=True,
                            is_primary_key=True,
                        ),
                        EntityField(
                            name="name",
                            data_type=DataTypePrimitive.STRING,
                            is_required=True,
                        ),
                        EntityField(
                            name="status",
                            data_type=DataTypePrimitive.STRING,
                            is_required=True,
                        ),
                        EntityField(
                            name="created_at",
                            data_type=DataTypePrimitive.DATETIME,
                            is_required=False,
                        ),
                    ],
                    sources=[SourceReference(modality=SourceModality.PLAIN_TEXT_REQ)],
                )
                entities.append(ent)
                slug = noun.lower() + "s"
                routes.append(
                    RouteDefinition(
                        path=f"/{slug}",
                        method=HttpMethod.GET,
                        summary=f"List {noun} items",
                        response_entity_id=ent.id,
                        sources=[
                            SourceReference(modality=SourceModality.PLAIN_TEXT_REQ)
                        ],
                    )
                )

        lines = [
            ln.strip("- *•\t ")
            for ln in combined_context.splitlines()
            if len(ln.strip()) > 8 and not ln.strip().startswith("[")
        ]
        for idx, line in enumerate(lines):
            # Flag vague words for HITL clarification
            is_vague = any(
                w in line.lower()
                for w in (
                    "maybe",
                    "fast",
                    "some",
                    "special",
                    "custom",
                    "etc",
                    "flexible",
                )
            )
            rule = BusinessRule(
                title=f"Specification Rule #{idx + 1}",
                domain_context="User Requirements",
                trigger_condition="Domain operation",
                expected_behavior=line,
                is_ambiguous=is_vague,
                confidence_score=0.7 if is_vague else 0.95,
                sources=[SourceReference(modality=SourceModality.PLAIN_TEXT_REQ)],
            )
            rules.append(rule)
            if is_vague:
                questions.append(
                    HITLQuestion(
                        related_rule_id=rule.id,
                        question=f"Requirement '{line}' contains open-ended parameters. How should it be enforced?",
                        suggested_options=[
                            "Enforce via strict synchronous validation in the domain service",
                            "Store parameters in a configurable database policy table",
                            "Omit from initial Kick-Starter scope",
                        ],
                        status=AmbiguityStatus.UNRESOLVED,
                    )
                )

        constraints = self._extract_constraints_from_text(combined_context)
        return entities, routes, rules, questions, constraints

    @staticmethod
    def _extract_constraints_from_text(
        text: str,
        default_rps: int = 200,
        default_io: bool = True,
        default_cpu: bool = False,
        extra_notes: Optional[str] = None,
    ) -> TechnicalConstraints:
        lower = text.lower()
        pref_langs: List[TargetLanguage] = []
        if "python" in lower or "fastapi" in lower:
            pref_langs.append(TargetLanguage.PYTHON_FASTAPI)
        if re.search(r"\b(go|golang)\b", lower):
            pref_langs.append(TargetLanguage.GO_FIBER_OR_CHI)
        if "typescript" in lower or "node" in lower or "nestjs" in lower:
            pref_langs.append(TargetLanguage.TYPESCRIPT_NEST_OR_NODE)
        if "c#" in lower or ".net" in lower or "dotnet" in lower:
            pref_langs.append(TargetLanguage.CSHARP_DOTNET)
        if "rust" in lower or re.search(r"\bc\b", lower) or "c++" in lower:
            pref_langs.append(TargetLanguage.RUST_AXUM)

        cpu_heavy = default_cpu or any(
            w in lower
            for w in ("cpu", "math", "video", "crypto", "image processing", "ml")
        )
        rps = default_rps
        if (
            "high concurrency" in lower
            or "millions" in lower
            or "high traffic" in lower
        ):
            rps = 2500

        notes_parts = [extra_notes] if extra_notes else []
        for line in text.splitlines():
            if any(
                k in line.lower()
                for k in (
                    "only know",
                    "cant be",
                    "cannot be",
                    "must be",
                    "no hexagonal",
                    "not hexagonal",
                    "clean architecture",
                    "monolith",
                    "microservice",
                )
            ):
                notes_parts.append(line.strip())

        return TechnicalConstraints(
            preferred_languages=pref_langs,
            expected_concurrency_rps=rps,
            io_heavy=default_io,
            cpu_heavy=cpu_heavy,
            database_preference="postgresql",
            require_frontend="headless" not in lower and "api only" not in lower,
            team_experience_notes=" | ".join(dict.fromkeys(notes_parts)) or None,
        )

    def _analyze_chunk_heuristically(
        self, chunk: ComplexCodeChunk
    ) -> Tuple[List[BusinessRule], List[HITLQuestion]]:
        is_ambiguous = chunk.cyclomatic_complexity >= (
            settings.MIN_CYCLOMATIC_COMPLEXITY_FOR_LLM + 1
        )
        rule = BusinessRule(
            title=f"Legacy Logic in `{chunk.symbol_name}`",
            domain_context=chunk.file_path,
            trigger_condition=f"Invocation of `{chunk.symbol_name}`",
            expected_behavior=(
                f"Executes {chunk.cyclomatic_complexity}-branch control flow "
                f"(lines {chunk.start_line}-{chunk.end_line})."
            ),
            cyclomatic_complexity_score=chunk.cyclomatic_complexity,
            is_ambiguous=is_ambiguous,
            confidence_score=0.65 if is_ambiguous else 0.9,
            sources=[
                SourceReference(
                    modality=SourceModality.AST_STATIC,
                    file_path=chunk.file_path,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    raw_symbol_name=chunk.symbol_name,
                )
            ],
        )

        questions: List[HITLQuestion] = []
        if is_ambiguous:
            questions.append(
                HITLQuestion(
                    related_rule_id=rule.id,
                    question=(
                        f"Function `{chunk.symbol_name}` in `{chunk.file_path}` has a high "
                        f"cyclomatic complexity of {chunk.cyclomatic_complexity} with nested "
                        f"branches/magic values. Should we preserve all legacy branches or simplify?"
                    ),
                    legacy_code_snippet=chunk.source_code[:600],
                    suggested_options=[
                        "Preserve exact branching behavior (strict parity)",
                        "Extract hardcoded thresholds into configuration/DB rules",
                        "Drop deprecated legacy edge cases",
                    ],
                    status=AmbiguityStatus.UNRESOLVED,
                )
            )
        return [rule], questions


llm_extractor = LLMExtractorService()
