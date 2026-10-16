from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.domain.ir_schema import (
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
    mark_rule_deprecated: bool = Field(default=False)


class HITLResolutionRequest(BaseModel):
    project_ir: ProjectIR
    answers: List[HITLAnswerItem]


class AHPWeightsBreakdown(BaseModel):
    velocity_weight: float = Field(
        ..., description="Weight for CRUD/Time-to-Market (0-1)"
    )
    performance_weight: float = Field(
        ..., description="Weight for TechEmpower RPS/CPU (0-1)"
    )
    ecosystem_weight: float = Field(
        ..., description="Weight for StackOverflow talent/packages (0-1)"
    )
    ai_weight: float = Field(
        ..., description="Weight for MultiPL-E AI pass@1 accuracy (0-1)"
    )


class StackScoreBreakdown(BaseModel):
    language: TargetLanguage
    recommended_pattern: ArchitecturalPattern
    total_score: float = Field(..., ge=0, le=100)
    base_industry_score: float = Field(..., ge=0, le=100)
    familiarity_modifier: float = Field(
        default=0.0, description="Direct boost (+10/+20 max) or penalty (-5/-10 max)"
    )
    proximity_modifier: float = Field(
        default=0.0,
        description="Paradigm similarity bonus from positively rated languages",
    )
    velocity_score: int
    performance_fit_score: int
    ecosystem_score: int
    ai_friendliness_score: int
    pros: List[str] = Field(default_factory=list)
    tradeoffs: List[str] = Field(default_factory=list)


class FrontendScoreBreakdown(BaseModel):
    framework: TargetFrontend
    total_score: float = Field(..., ge=0, le=100)
    base_industry_score: float = Field(..., ge=0, le=100)
    familiarity_modifier: float = 0.0
    proximity_modifier: float = 0.0
    seo_ssr_score: int
    interactivity_spa_score: int
    ecosystem_score: int
    ai_friendliness_score: int
    rationale: str


class ArchitectRecommendationRequest(BaseModel):
    project_ir: ProjectIR
    constraints: TechnicalConstraints
    override_language: Optional[TargetLanguage] = None
    override_frontend: Optional[TargetFrontend] = None


class ArchitectRecommendationResponse(BaseModel):
    project_ir: ProjectIR
    ready_for_scaffolding: bool
    selected_architecture: ArchitectureDecision
    ahp_weights: AHPWeightsBreakdown
    ranked_alternatives: List[StackScoreBreakdown]
    ranked_frontend_alternatives: List[FrontendScoreBreakdown] = Field(
        default_factory=list
    )
    benchmark_sources: Dict[str, str] = Field(default_factory=dict)
