# app/api/architect_router.py
from fastapi import APIRouter

from app.domain.ir_schema import ProjectIR
from app.domain.wizard_state import (
    ArchitectRecommendationRequest,
    ArchitectRecommendationResponse,
    HITLResolutionRequest,
)
from app.services.architect.hitl_resolver import hitl_resolver
from app.services.architect.stack_advisor import stack_advisor

router = APIRouter(
    prefix="/api/v1/architect", tags=["Phase 3: Architect & Constraints Wizard"]
)


@router.post("/resolve-hitl", response_model=ProjectIR)
async def resolve_hitl_questions(request: HITLResolutionRequest) -> ProjectIR:
    """
    Phase 3 Step A: Submit Human-in-the-Loop answers for ambiguous legacy business rules.
    Updates the BusinessRules in the ProjectIR and marks HITLQuestions as resolved.
    """
    return hitl_resolver.resolve_questions(request.project_ir, request.answers)


@router.post("/recommend-stack", response_model=ArchitectRecommendationResponse)
async def recommend_architecture_and_stack(
    request: ArchitectRecommendationRequest,
) -> ArchitectRecommendationResponse:
    """
    Phase 3 Step B: Evaluates technical constraints (concurrency, I/O, CPU, team prefs)
    and populates `architecture_decision` in the ProjectIR.
    Once HITL questions are resolved and this endpoint runs, `ready_for_scaffolding` becomes True.
    """
    decision, ranked = stack_advisor.evaluate_and_recommend(
        ir=request.project_ir,
        constraints=request.constraints,
        override_language=request.override_language,
        override_frontend=request.override_frontend,
    )

    return ArchitectRecommendationResponse(
        project_ir=request.project_ir,
        ready_for_scaffolding=request.project_ir.is_ready_for_scaffolding,
        selected_architecture=decision,
        ranked_alternatives=ranked,
    )
