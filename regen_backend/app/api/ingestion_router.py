# app/api/ingestion_router.py
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.domain.ir_schema import ProjectIR
from app.services.ingestion.pipeline import (
    CodeFileInput,
    IngestionRequest,
    ingestion_pipeline,
)

router = APIRouter(prefix="/api/v1/ingestion", tags=["Phase 1: Ingestion Engine"])


class DirectoryScanRequest(BaseModel):
    project_name: str = Field(..., examples=["LegacyMonolith"])
    directory_path: str = Field(
        ..., description="Local path to legacy source directory"
    )
    plain_text_requirements: Optional[str] = None


IGNORE_DIRS = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    ".next",
    "dist",
    "build",
}
SUPPORTED_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx"}


@router.post("/analyze", response_model=ProjectIR)
async def analyze_multimodal_inputs(request: IngestionRequest) -> ProjectIR:
    """
    Phase 1 Entrypoint: Accepts code files, plain-text specs, and UI screenshot metadata.
    Returns a populated Phase 2 ProjectIR with token-saving metrics and HITL questions.
    """
    return await ingestion_pipeline.run(request)


@router.post("/scan-directory", response_model=ProjectIR)
async def scan_local_directory(request: DirectoryScanRequest) -> ProjectIR:
    """
    Scans a local folder on disk, filters out ignored directories, and runs
    the deterministic tree-sitter + token gatekeeper pipeline.
    """
    root = Path(request.directory_path)
    if not root.exists() or not root.is_dir():
        raise HTTPException(
            status_code=400, detail=f"Directory not found: {request.directory_path}"
        )

    code_files: List[CodeFileInput] = []
    for path in root.rglob("*"):
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                rel_path = str(path.relative_to(root))
                code_files.append(CodeFileInput(file_path=rel_path, content=content))
            except Exception:
                continue

    ingestion_req = IngestionRequest(
        project_name=request.project_name,
        code_files=code_files,
        plain_text_requirements=request.plain_text_requirements,
    )
    return await ingestion_pipeline.run(ingestion_req)
