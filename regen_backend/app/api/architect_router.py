from fastapi import APIRouter

from app.domain.ir_schema import ProjectIR
from app.domain.wizard_state import (
    ArchitectRecommendationRequest,
    ArchitectRecommendationResponse,
    HITLResolutionRequest,
)
from app.services.architect.hitl_resolver import hitl_resolver
from app.services.architect.stack_advisor import BENCHMARK_SOURCES, stack_advisor

router = APIRouter(
    prefix="/api/v1/architect", tags=["Phase 3: Architect & Constraints Wizard"]
)


@router.post("/resolve-hitl", response_model=ProjectIR)
async def resolve_hitl_questions(request: HITLResolutionRequest) -> ProjectIR:
    return hitl_resolver.resolve_questions(request.project_ir, request.answers)


@router.post("/recommend-stack", response_model=ArchitectRecommendationResponse)
async def recommend_architecture_and_stack(
    request: ArchitectRecommendationRequest,
) -> ArchitectRecommendationResponse:
    (
        decision,
        ahp_weights,
        ranked_backends,
        ranked_frontends,
    ) = stack_advisor.evaluate_and_recommend(
        ir=request.project_ir,
        constraints=request.constraints,
        override_language=request.override_language,
        override_frontend=request.override_frontend,
    )
    return ArchitectRecommendationResponse(
        project_ir=request.project_ir,
        ready_for_scaffolding=request.project_ir.is_ready_for_scaffolding,
        selected_architecture=decision,
        ahp_weights=ahp_weights,
        ranked_alternatives=ranked_backends,
        ranked_frontend_alternatives=ranked_frontends,
        benchmark_sources=BENCHMARK_SOURCES,
    )
