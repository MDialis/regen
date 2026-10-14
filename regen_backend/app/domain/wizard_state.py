# app/domain/wizard_state.py
from typing import List, Optional
from pydantic import BaseModel, Field

from app.domain.ir_schema import (
    AmbiguityStatus,
    ArchitecturalPattern,
    ArchitectureDecision,
    ProjectIR,
    TargetFrontend,
    TargetLanguage,
    TechnicalConstraints,
)


class HITLAnswerItem(BaseModel):
    question_id: str = Field(..., examples=["hitl_48a302f1"])
    selected_option_or_custom_answer: str = Field(
        ...,
        examples=["Extract hardcoded thresholds into configuration/DB rules"],
    )
    mark_rule_deprecated: bool = Field(
        default=False,
        description="If True, marks the legacy rule as deprecated so it is omitted from codegen",
    )


class HITLResolutionRequest(BaseModel):
    project_ir: ProjectIR
    answers: List[HITLAnswerItem]


class StackScoreBreakdown(BaseModel):
    language: TargetLanguage
    recommended_pattern: ArchitecturalPattern
    total_score: int = Field(..., ge=0, le=100)
    ai_friendliness_score: int = Field(..., ge=0, le=100)
    performance_fit_score: int = Field(..., ge=0, le=100)
    pros: List[str] = Field(default_factory=list)
    tradeoffs: List[str] = Field(default_factory=list)


class ArchitectRecommendationRequest(BaseModel):
    project_ir: ProjectIR
    constraints: TechnicalConstraints
    override_language: Optional[TargetLanguage] = Field(
        default=None,
        description="Optional explicit backend stack override chosen by the user",
    )
    override_frontend: Optional[TargetFrontend] = Field(
        default=None,
        description="Optional explicit frontend framework chosen by the user",
    )


class ArchitectRecommendationResponse(BaseModel):
    project_ir: ProjectIR
    ready_for_scaffolding: bool
    selected_architecture: ArchitectureDecision
    ranked_alternatives: List[StackScoreBreakdown]
