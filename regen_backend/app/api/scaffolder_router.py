# app/api/scaffolder_router.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import io

from app.domain.ir_schema import ProjectIR
from app.services.scaffolder.engine import ScaffoldManifest, scaffolder_engine
from app.services.strangler.test_generator import strangler_generator

router = APIRouter(
    prefix="/api/v1/scaffolder",
    tags=["Phase 4 & 5: Scaffolder & Strangler Fig Engine"],
)


@router.post("/generate-contracts", response_model=ProjectIR)
async def generate_strangler_contracts(ir: ProjectIR) -> ProjectIR:
    """
    Phase 5 Endpoint: Populates CharacterizationContract items in the ProjectIR
    for Strangler Fig parity verification between Legacy and Kick-Starter.
    """
    return strangler_generator.populate_contracts(ir)


@router.post("/preview", response_model=ScaffoldManifest)
async def preview_scaffolded_codebase(ir: ProjectIR) -> ScaffoldManifest:
    """
    Phase 4 Preview Endpoint: Enforces the HITL gate (`is_ready_for_scaffolding`).
    Returns the virtual file tree of the generated Kick-Starter project (Dockerfile,
    docker-compose.yml, AGENTS.md, Hexagonal domain/application/adapter files, and pytest suite).
    """
    if not ir.is_ready_for_scaffolding:
        raise HTTPException(
            status_code=422,
            detail=(
                "Cannot scaffold project: Unresolved HITL questions remain or "
                "ArchitectureDecision has not been selected."
            ),
        )
    try:
        return scaffolder_engine.generate_manifest(ir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/download-zip")
async def download_scaffolded_zip(ir: ProjectIR) -> StreamingResponse:
    """
    Phase 4 Export Endpoint: Streams a ready-to-run `.zip` archive of the containerized
    Kick-Starter project (`docker compose up --build`).
    """
    if not ir.is_ready_for_scaffolding:
        raise HTTPException(
            status_code=422,
            detail="Cannot export ZIP: Resolve all HITL questions and select a stack first.",
        )

    zip_bytes = scaffolder_engine.build_zip_archive(ir)
    filename = f"{ir.project_name.lower().replace(' ', '_')}_kickstarter.zip"
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
