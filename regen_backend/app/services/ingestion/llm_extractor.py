# app/services/ingestion/llm_extractor.py
import json
from typing import List, Optional, Tuple
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.domain.ir_schema import (
    AmbiguityStatus,
    BusinessRule,
    HITLQuestion,
    SourceModality,
    SourceReference,
    UIViewComponent,
)
from app.services.ingestion.ast_analyzer import ComplexCodeChunk


class ExtractedRuleItem(BaseModel):
    title: str
    domain_context: str
    trigger_condition: str
    expected_behavior: str
    is_ambiguous: bool = Field(
        default=False,
        description="True if magic numbers, undocumented flags, or spaghetti conditions exist",
    )
    confidence_score: float = 0.85
    clarification_question: Optional[str] = None
    suggested_options: List[str] = Field(default_factory=list)


class BatchRuleExtractionResponse(BaseModel):
    rules: List[ExtractedRuleItem] = Field(default_factory=list)


class LLMExtractorService:
    """
    Processes high-complexity AST chunks, plain text requirements, and UI screenshots.
    Uses GPT-4o when OPENAI_API_KEY is present, or a local heuristic analyzer when offline.
    """

    def __init__(self) -> None:
        self.client: Optional[AsyncOpenAI] = (
            AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            if settings.OPENAI_API_KEY
            else None
        )

    async def extract_from_complex_chunks(
        self, chunks: List[ComplexCodeChunk]
    ) -> Tuple[List[BusinessRule], List[HITLQuestion]]:
        rules: List[BusinessRule] = []
        questions: List[HITLQuestion] = []

        for chunk in chunks:
            if self.client:
                c_rules, c_questions = await self._analyze_chunk_with_gpt4o(chunk)
            else:
                c_rules, c_questions = self._analyze_chunk_heuristically(chunk)
            rules.extend(c_rules)
            questions.extend(c_questions)

        return rules, questions

    async def _analyze_chunk_with_gpt4o(
        self, chunk: ComplexCodeChunk
    ) -> Tuple[List[BusinessRule], List[HITLQuestion]]:
        assert self.client is not None
        system_prompt = (
            "You are REGEN's Legacy Code Archaeologist. Analyze the provided high-complexity "
            "legacy function. Extract explicit business rules. CRITICAL: Never guess magic "
            "numbers, hardcoded status codes, or ambiguous nested conditions. Mark them with "
            "`is_ambiguous: true` and provide a clear `clarification_question` and "
            "2-3 `suggested_options` for the Human-in-the-Loop interview."
        )
        user_prompt = (
            f"File: {chunk.file_path} (Lines {chunk.start_line}-{chunk.end_line})\n"
            f"Function: {chunk.symbol_name} (Cyclomatic Complexity: {chunk.cyclomatic_complexity})\n\n"
            f"```\n{chunk.source_code}\n```"
        )

        completion = await self.client.beta.chat.completions.parse(
            model=settings.OPENAI_REASONING_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=BatchRuleExtractionResponse,
            temperature=0.1,
        )

        parsed = completion.choices[0].message.parsed
        if not parsed:
            return self._analyze_chunk_heuristically(chunk)

        out_rules: List[BusinessRule] = []
        out_questions: List[HITLQuestion] = []

        for item in parsed.rules:
            rule = BusinessRule(
                title=item.title,
                domain_context=item.domain_context,
                trigger_condition=item.trigger_condition,
                expected_behavior=item.expected_behavior,
                cyclomatic_complexity_score=chunk.cyclomatic_complexity,
                is_ambiguous=item.is_ambiguous,
                confidence_score=item.confidence_score,
                sources=[
                    SourceReference(
                        modality=SourceModality.LLM_CODE_INFERENCE,
                        file_path=chunk.file_path,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        raw_symbol_name=chunk.symbol_name,
                    )
                ],
            )
            out_rules.append(rule)

            if item.is_ambiguous and item.clarification_question:
                out_questions.append(
                    HITLQuestion(
                        related_rule_id=rule.id,
                        question=item.clarification_question,
                        legacy_code_snippet=chunk.source_code[:600],
                        suggested_options=item.suggested_options
                        or [
                            "Keep legacy behavior as-is",
                            "Refactor into configurable domain parameter",
                            "Deprecate this legacy branch",
                        ],
                        status=AmbiguityStatus.UNRESOLVED,
                    )
                )

        return out_rules, out_questions

    def _analyze_chunk_heuristically(
        self, chunk: ComplexCodeChunk
    ) -> Tuple[List[BusinessRule], List[HITLQuestion]]:
        """
        Zero-cost local fallback when OPENAI_API_KEY is not set.
        Flags high-complexity chunks for HITL verification automatically.
        """
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

    def extract_from_plain_text(self, plain_text: str) -> List[BusinessRule]:
        """Converts plain-text user requirements into explicit BusinessRules."""
        if not plain_text.strip():
            return []
        lines = [
            line.strip("- *•\t ")
            for line in plain_text.splitlines()
            if len(line.strip()) > 10
        ]
        return [
            BusinessRule(
                title=f"Requirement #{idx + 1}",
                domain_context="User Specification",
                trigger_condition="System domain operation",
                expected_behavior=line,
                is_ambiguous=False,
                confidence_score=1.0,
                sources=[SourceReference(modality=SourceModality.PLAIN_TEXT_REQ)],
            )
            for idx, line in enumerate(lines)
        ]


llm_extractor = LLMExtractorService()
