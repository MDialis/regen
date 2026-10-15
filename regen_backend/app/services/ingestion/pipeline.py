# app/services/ingestion/pipeline.py
from typing import List, Optional
from pydantic import BaseModel, Field

from app.domain.ir_schema import (
    ProjectIR,
    SourceModality,
    SourceReference,
    UIViewComponent,
)
from app.services.ingestion.ast_analyzer import ComplexCodeChunk, ast_analyzer
from app.services.ingestion.doc_processor import doc_processor
from app.services.ingestion.llm_extractor import llm_extractor


class CodeFileInput(BaseModel):
    file_path: str = Field(..., examples=["legacy_billing.py"])
    content: str


class DocumentFileInput(BaseModel):
    file_path: str = Field(..., examples=["requirements.csv", "spec.pdf"])
    text_content: Optional[str] = None
    base64_content: Optional[str] = None


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
    document_files: List[DocumentFileInput] = Field(default_factory=list)
    plain_text_requirements: Optional[str] = Field(default=None)
    screenshots: List[ScreenshotInput] = Field(default_factory=list)
    low_vram_mode: Optional[bool] = Field(
        default=None,
        description="If True, forces phi4-mini for all local LLM tasks",
    )


class IngestionPipeline:
    """
    3-Stage Hybrid Ingestion Pipeline:
    1. Code files -> Deterministic `tree-sitter` AST parser.
    2. Non-code files (.csv, .xlsx, .pdf, .json, .md) -> Deterministic Python `doc_processor`.
    3. Condensed digests + Plain Text -> Local LLM (`phi4-mini`) to infer missing Entities,
       Routes, Business Rules, HITL questions, and pre-filled TechnicalConstraints.
    """

    async def run(self, payload: IngestionRequest) -> ProjectIR:
        ir = ProjectIR(project_name=payload.project_name)
        all_complex_chunks: List[ComplexCodeChunk] = []
        doc_summaries: List[str] = []

        # 1. Legacy Code Files -> tree-sitter AST
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

        if all_complex_chunks:
            extracted_rules, hitl_questions = (
                await llm_extractor.extract_from_complex_chunks(
                    all_complex_chunks, low_vram_mode=payload.low_vram_mode
                )
            )
            ir.business_rules.extend(extracted_rules)
            ir.hitl_questions.extend(hitl_questions)

        # 2. Non-Code Document Files (.csv, .xlsx, .pdf, .json, .md, .txt) -> Python Pre-Processor
        for doc in payload.document_files:
            doc_res = doc_processor.process_file(
                file_path=doc.file_path,
                text_content=doc.text_content,
                base64_content=doc.base64_content,
            )
            ir.entities.extend(doc_res.inferred_entities)
            if doc_res.condensed_summary_for_llm:
                doc_summaries.append(doc_res.condensed_summary_for_llm)

            ir.ingestion_metrics.total_files_scanned += 1
            ir.ingestion_metrics.ast_nodes_parsed_deterministically += len(
                doc_res.inferred_entities
            )
            ir.ingestion_metrics.estimated_tokens_saved += doc_res.tokens_saved
            ir.ingestion_metrics.llm_tokens_consumed += doc_res.condensed_tokens_count

        # 3. Plain-Text Requirements + Condensed Document Summaries -> Local LLM (`phi4-mini`)
        if (
            payload.plain_text_requirements and payload.plain_text_requirements.strip()
        ) or doc_summaries:
            existing_names = [e.name for e in ir.entities]
            (
                inferred_entities,
                inferred_routes,
                inferred_rules,
                inferred_questions,
                inferred_constraints,
            ) = await llm_extractor.analyze_documents_and_text(
                project_name=payload.project_name,
                plain_text=payload.plain_text_requirements or "",
                doc_summaries=doc_summaries,
                existing_entity_names=existing_names,
                low_vram_mode=payload.low_vram_mode,
            )
            ir.entities.extend(inferred_entities)
            ir.routes.extend(inferred_routes)
            ir.business_rules.extend(inferred_rules)
            ir.hitl_questions.extend(inferred_questions)
            ir.technical_constraints = inferred_constraints

        # 4. Visual Inputs (Screenshots)
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
