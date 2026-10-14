# app/services/ingestion/pipeline.py
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.domain.ir_schema import (
    IngestionMetrics,
    ProjectIR,
    SourceModality,
    SourceReference,
    UIViewComponent,
)
from app.services.ingestion.ast_analyzer import ComplexCodeChunk, ast_analyzer
from app.services.ingestion.llm_extractor import llm_extractor


class CodeFileInput(BaseModel):
    file_path: str = Field(..., examples=["legacy_billing.py"])
    content: str


class ScreenshotInput(BaseModel):
    screenshot_id: str = Field(..., examples=["screen_checkout_01.png"])
    screen_name: str = Field(..., examples=["Legacy Checkout Screen"])
    route_path: str = Field(default="/checkout")
    detected_elements_hint: List[str] = Field(
        default_factory=lambda: ["DataTable", "Form", "SubmitButton"]
    )


class IngestionRequest(BaseModel):
    project_name: str = Field(..., examples=["BillingModernization"])
    code_files: List[CodeFileInput] = Field(default_factory=list)
    plain_text_requirements: Optional[str] = Field(
        default=None,
        examples=[
            "- Invoices above $10,000 require dual manager approval.\n"
            "- All legacy tax codes must support multi-currency."
        ],
    )
    screenshots: List[ScreenshotInput] = Field(default_factory=list)


class IngestionPipeline:
    """
    Phase 1 & Phase 2 Bridge:
    Ingests multi-modal legacy inputs, runs deterministic AST gatekeeping,
    routes complex chunks to the LLM/heuristic extractor, and outputs a ProjectIR.
    """

    async def run(self, payload: IngestionRequest) -> ProjectIR:
        ir = ProjectIR(project_name=payload.project_name)
        all_complex_chunks: List[ComplexCodeChunk] = []

        # 1. Modality A: Legacy Codebase (Deterministic AST + Complexity Gatekeeper)
        for code_file in payload.code_files:
            ast_res = ast_analyzer.analyze_file(code_file.file_path, code_file.content)
            ir.entities.extend(ast_res.entities)
            ir.routes.extend(ast_res.routes)
            all_complex_chunks.extend(ast_res.complex_chunks)

            ir.ingestion_metrics.total_files_scanned += 1
            ir.ingestion_metrics.ast_nodes_parsed_deterministically += (
                ast_res.nodes_parsed_deterministically
            )
            ir.ingestion_metrics.estimated_tokens_saved += ast_res.tokens_saved
            ir.ingestion_metrics.llm_tokens_consumed += ast_res.tokens_queued_for_llm

        ir.ingestion_metrics.complex_chunks_sent_to_llm = len(all_complex_chunks)

        # Extract Business Rules & HITL Ambiguities from complex AST chunks
        if all_complex_chunks:
            extracted_rules, hitl_questions = (
                await llm_extractor.extract_from_complex_chunks(all_complex_chunks)
            )
            ir.business_rules.extend(extracted_rules)
            ir.hitl_questions.extend(hitl_questions)

        # 2. Modality B: Plain Text Requirements
        if payload.plain_text_requirements:
            text_rules = llm_extractor.extract_from_plain_text(
                payload.plain_text_requirements
            )
            ir.business_rules.extend(text_rules)

        # 3. Modality C: Visual Inputs (Screenshots -> UIViewComponents)
        for shot in payload.screenshots:
            ir.ui_views.append(
                UIViewComponent(
                    screen_name=shot.screen_name,
                    route_path=shot.route_path,
                    detected_components=shot.detected_elements_hint,
                    sources=[
                        SourceReference(
                            modality=SourceModality.VISION_SCREENSHOT,
                            screenshot_id=shot.screenshot_id,
                        )
                    ],
                )
            )

        return ir


ingestion_pipeline = IngestionPipeline()
