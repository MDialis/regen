# app/main.py
from typing import Any, Dict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.domain.ir_schema import ProjectIR
from app.api.ingestion_router import router as ingestion_router
from app.api.architect_router import router as architect_router
from app.api.scaffolder_router import router as scaffolder_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-Driven Legacy Modernization & Architecture Scaffolder API",
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health", tags=["System"])
async def health_check() -> Dict[str, Any]:
    """Verify backend status and hybrid LLM configuration."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "llm_configured": bool(settings.OPENAI_API_KEY),
        "ollama_url": settings.OLLAMA_BASE_URL,
    }


@app.get("/api/v1/ir/schema", tags=["Phase 2: IR Blueprint"])
async def get_ir_json_schema() -> Dict[str, Any]:
    """
    Exports the standardized JSON Schema of ProjectIR.
    Used by the frontend wizard and LLM structured-output prompts.
    """
    return ProjectIR.model_json_schema()


@app.post(
    "/api/v1/ir/validate", response_model=Dict[str, Any], tags=["Phase 2: IR Blueprint"]
)
async def validate_project_ir(ir: ProjectIR) -> Dict[str, Any]:
    """
    Validates a ProjectIR payload and checks if it passes the HITL gate
    to proceed to Phase 4 (Intelligent Scaffolding).
    """
    unresolved_count = sum(1 for q in ir.hitl_questions if q.status == "unresolved")
    return {
        "valid": True,
        "project_id": ir.project_id,
        "ready_for_scaffolding": ir.is_ready_for_scaffolding,
        "unresolved_hitl_questions": unresolved_count,
        "summary": {
            "entities": len(ir.entities),
            "business_rules": len(ir.business_rules),
            "routes": len(ir.routes),
            "tokens_saved": ir.ingestion_metrics.estimated_tokens_saved,
        },
    }


app.include_router(ingestion_router)
app.include_router(architect_router)
app.include_router(scaffolder_router)
