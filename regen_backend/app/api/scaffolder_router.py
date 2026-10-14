# app/api/scaffolder_router.py
import io
import uuid
from typing import Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.domain.ir_schema import ProjectIR
from app.services.scaffolder.engine import ScaffoldManifest, scaffolder_engine
from app.services.strangler.test_generator import strangler_generator

router = APIRouter(
    prefix="/api/v1/scaffolder",
    tags=["Phase 4 & 5: Scaffolder & Strangler Fig Engine"],
)


class ScaffoldJobStatus(BaseModel):
    job_id: str
    status: str = Field(..., description="processing | ready | failed")
    progress_pct: int = 0
    current_step: str = "Queued..."
    logs: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    manifest: Optional[ScaffoldManifest] = None


# In-memory store for background build jobs and pre-built ZIP archives
_JOBS: Dict[str, ScaffoldJobStatus] = {}
_ZIP_CACHE: Dict[str, bytes] = {}
_FILENAME_CACHE: Dict[str, str] = {}


def _run_background_scaffold_job(job_id: str, ir: ProjectIR) -> None:
    """Runs the CLI project initializers and ZIP compression in a worker thread."""
    job = _JOBS[job_id]

    def on_progress(step_msg: str, pct: int) -> None:
        job.current_step = step_msg
        job.progress_pct = pct
        job.logs.append(step_msg)

    try:
        manifest, zip_bytes = scaffolder_engine.build_project_and_zip(
            ir, on_progress=on_progress
        )
        slug = ir.project_name.lower().replace(" ", "_")
        _ZIP_CACHE[job_id] = zip_bytes
        _FILENAME_CACHE[job_id] = f"{slug}_kickstarter.zip"
        job.manifest = manifest
        job.progress_pct = 100
        job.current_step = "Kick-Starter ready for download!"
        job.status = "ready"
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        job.logs.append(f"[ERROR] {exc}")


@router.post("/start-job", response_model=ScaffoldJobStatus)
async def start_scaffold_job(
    ir: ProjectIR, background_tasks: BackgroundTasks
) -> ScaffoldJobStatus:
    """
    Phase 4 Async Entrypoint: Immediately returns a `job_id` while running
    official language/framework CLI initializers and building the `.zip` in the background.
    """
    if not ir.is_ready_for_scaffolding:
        raise HTTPException(
            status_code=422,
            detail=(
                "Cannot scaffold project: Resolve all HITL questions and "
                "run the Stack Advisor first."
            ),
        )

    job_id = f"job_{uuid.uuid4().hex[:10]}"
    job_state = ScaffoldJobStatus(
        job_id=job_id,
        status="processing",
        progress_pct=5,
        current_step="Initializing isolated build workspace...",
        logs=["Initializing isolated build workspace..."],
    )
    _JOBS[job_id] = job_state
    background_tasks.add_task(_run_background_scaffold_job, job_id, ir)
    return job_state


@router.get("/jobs/{job_id}", response_model=ScaffoldJobStatus)
async def get_scaffold_job_status(job_id: str) -> ScaffoldJobStatus:
    """Polled by the frontend loading screen to display live CLI progress."""
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job `{job_id}` not found.")
    return job


@router.get("/jobs/{job_id}/download")
async def download_prebuilt_job_zip(job_id: str) -> StreamingResponse:
    """
    Instantly streams the pre-built `.zip` archive from memory once `status == 'ready'`.
    Zero CLI wait time on click!
    """
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job `{job_id}` not found.")
    if job.status != "ready" or job_id not in _ZIP_CACHE:
        raise HTTPException(
            status_code=400,
            detail=f"ZIP archive is not ready yet (current status: {job.status}).",
        )

    zip_bytes = _ZIP_CACHE[job_id]
    filename = _FILENAME_CACHE.get(job_id, "kickstarter.zip")
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ============================================================================
# SYNCHRONOUS ENDPOINTS (KEPT FOR BACKWARD COMPATIBILITY & AUTOMATED TESTS)
# ============================================================================


@router.post("/generate-contracts", response_model=ProjectIR)
async def generate_strangler_contracts(ir: ProjectIR) -> ProjectIR:
    return strangler_generator.populate_contracts(ir)


@router.post("/preview", response_model=ScaffoldManifest)
async def preview_scaffolded_codebase(ir: ProjectIR) -> ScaffoldManifest:
    if not ir.is_ready_for_scaffolding:
        raise HTTPException(
            status_code=422,
            detail="Cannot scaffold project: Unresolved HITL questions or missing ArchitectureDecision.",
        )
    return scaffolder_engine.generate_manifest(ir)


@router.post("/download-zip")
async def download_scaffolded_zip(ir: ProjectIR) -> StreamingResponse:
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
