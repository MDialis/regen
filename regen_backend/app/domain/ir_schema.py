# app/domain/ir_schema.py
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field

# ============================================================================
# 1. ENUMS & TAXONOMY (Stack-Agnostic Primitives)
# ============================================================================


class SourceModality(str, Enum):
    AST_STATIC = "ast_static"  # Deterministic tree-sitter extraction
    LLM_CODE_INFERENCE = "llm_code"  # Complex AST chunk analyzed by LLM
    VISION_SCREENSHOT = "vision_ui"  # Reverse-engineered from UI image
    PLAIN_TEXT_REQ = "plain_text"  # User-provided business description
    HITL_INTERVIEW = "hitl_interview"  # Clarified by user during Phase 3


class DataTypePrimitive(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    UUID = "uuid"
    JSON = "json"
    ENUM = "enum"
    BINARY = "binary"


class RelationshipType(str, Enum):
    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:N"
    MANY_TO_MANY = "N:M"


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class ArchitecturalPattern(str, Enum):
    HEXAGONAL = "hexagonal"  # Ports & Adapters (High AI-friendliness)
    CLEAN_ARCHITECTURE = "clean"  # Domain / UseCases / Interfaces / Infra
    MODULAR_MONOLITH = "modular_monolith"  # Strict domain boundaries, single deployable
    EVENT_DRIVEN_MICRO = "event_driven"  # High concurrency / async decoupling


class TargetLanguage(str, Enum):
    PYTHON_FASTAPI = "python_fastapi"
    GO_FIBER_OR_CHI = "go"
    TYPESCRIPT_NEST_OR_NODE = "typescript"
    RUST_AXUM = "rust"
    CSHARP_DOTNET = "csharp_dotnet"


class AmbiguityStatus(str, Enum):
    UNRESOLVED = "unresolved"  # Blocks scaffolding until user answers
    RESOLVED = "resolved"  # Clarified via HITL Wizard
    DEPRECATED_LEGACY = "deprecated"  # User chose to drop this legacy behavior


# ============================================================================
# 2. PROVENANCE & TOKEN METRICS (Phase 1 Tracking)
# ============================================================================


class SourceReference(BaseModel):
    """Traces where an IR node originated for auditability and Strangler Fig tests."""

    modality: SourceModality
    file_path: Optional[str] = Field(
        None, description="Legacy file path if from codebase"
    )
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    screenshot_id: Optional[str] = Field(None, description="Image ref if from Vision")
    raw_symbol_name: Optional[str] = Field(
        None, description="Original legacy class/fn name"
    )


class IngestionMetrics(BaseModel):
    """Tracks deterministic vs. generative efficiency (Token Saver philosophy)."""

    total_files_scanned: int = 0
    ast_nodes_parsed_deterministically: int = 0
    complex_chunks_sent_to_llm: int = 0
    estimated_tokens_saved: int = 0
    llm_tokens_consumed: int = 0


# ============================================================================
# 3. DOMAIN ENTITIES & RELATIONSHIPS (Phase 2 Core Data Blueprint)
# ============================================================================


class EntityField(BaseModel):
    name: str = Field(..., description="Normalized snake_case or camelCase field name")
    data_type: DataTypePrimitive
    is_required: bool = True
    is_unique: bool = False
    is_primary_key: bool = False
    default_value: Optional[Any] = None
    enum_values: Optional[List[str]] = None
    description: Optional[str] = None


class EntityDefinition(BaseModel):
    id: str = Field(default_factory=lambda: f"ent_{uuid4().hex[:8]}")
    name: str = Field(
        ..., description="PascalCase singular domain entity name, e.g., Invoice"
    )
    description: str
    fields: List[EntityField] = Field(default_factory=list)
    sources: List[SourceReference] = Field(default_factory=list)


class RelationshipDefinition(BaseModel):
    id: str = Field(default_factory=lambda: f"rel_{uuid4().hex[:8]}")
    source_entity_id: str
    target_entity_id: str
    relationship_type: RelationshipType
    foreign_key_field: Optional[str] = None
    cascade_delete: bool = False
    description: Optional[str] = None


# ============================================================================
# 4. BUSINESS RULES & HUMAN-IN-THE-LOOP (HITL) AMBIGUITY ISOLATION
# ============================================================================


class HITLQuestion(BaseModel):
    """Generated when legacy code is spaghetti/ambiguous or contradicts requirements."""

    id: str = Field(default_factory=lambda: f"hitl_{uuid4().hex[:8]}")
    related_rule_id: str
    question: str = Field(
        ..., description="Clear question for the developer/domain expert"
    )
    legacy_code_snippet: Optional[str] = Field(
        None, description="Isolated legacy snippet causing ambiguity"
    )
    suggested_options: List[str] = Field(
        default_factory=list,
        description="Possible interpretations for quick user selection",
    )
    user_response: Optional[str] = None
    status: AmbiguityStatus = AmbiguityStatus.UNRESOLVED


class BusinessRule(BaseModel):
    id: str = Field(default_factory=lambda: f"rule_{uuid4().hex[:8]}")
    title: str
    domain_context: str = Field(..., description="Bounded context or module name")
    trigger_condition: str = Field(
        ..., description="When this rule executes (Precondition)"
    )
    expected_behavior: str = Field(..., description="What must happen (Postcondition)")
    affected_entity_ids: List[str] = Field(default_factory=list)
    cyclomatic_complexity_score: Optional[int] = None
    is_ambiguous: bool = Field(
        default=False,
        description="If True, triggers a HITLQuestion in Phase 3 before codegen",
    )
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    sources: List[SourceReference] = Field(default_factory=list)


# ============================================================================
# 5. APPLICATION ROUTES, UI VIEWS & CHARACTERIZATION TESTS
# ============================================================================


class RouteDefinition(BaseModel):
    """Agnostic API/Controller contract extracted from legacy routes or UI flows."""

    id: str = Field(default_factory=lambda: f"rt_{uuid4().hex[:8]}")
    path: str = Field(
        ..., description="Normalized route path, e.g., /api/v1/orders/{id}"
    )
    method: HttpMethod
    summary: str
    request_schema_fields: Dict[str, DataTypePrimitive] = Field(default_factory=dict)
    response_entity_id: Optional[str] = None
    enforced_rule_ids: List[str] = Field(
        default_factory=list, description="BusinessRules executed by this endpoint"
    )
    requires_auth: bool = True
    sources: List[SourceReference] = Field(default_factory=list)


class UIViewComponent(BaseModel):
    """Extracted from Screenshots (Vision) or Frontend AST."""

    id: str = Field(default_factory=lambda: f"ui_{uuid4().hex[:8]}")
    screen_name: str
    route_path: str
    detected_components: List[str] = Field(
        default_factory=list,
        description="e.g., ['DataTable', 'FilterBar', 'CreateModal']",
    )
    bound_entity_ids: List[str] = Field(default_factory=list)
    triggered_route_ids: List[str] = Field(default_factory=list)
    sources: List[SourceReference] = Field(default_factory=list)


class CharacterizationContract(BaseModel):
    """Phase 5: Strangler Fig test case verifying parity between legacy and Kick-Starter."""

    id: str = Field(default_factory=lambda: f"test_{uuid4().hex[:8]}")
    target_route_id: Optional[str] = None
    target_rule_id: str
    scenario_name: str
    given_input_payload: Dict[str, Any]
    expected_output_payload: Dict[str, Any]
    expected_side_effects: List[str] = Field(default_factory=list)


# ============================================================================
# 6. PHASE 3: ARCHITECT CONSTRAINTS & STACK RECOMMENDATION
# ============================================================================


class TechnicalConstraints(BaseModel):
    """User-defined constraints gathered during the Phase 3 Wizard."""

    preferred_languages: List[TargetLanguage] = Field(default_factory=list)
    expected_concurrency_rps: int = Field(
        default=100, description="Requests per second"
    )
    io_heavy: bool = True
    cpu_heavy: bool = False
    database_preference: str = Field(default="postgresql")
    require_frontend: bool = True
    team_experience_notes: Optional[str] = None


class ArchitectureDecision(BaseModel):
    """The Architect Engine's output explaining the chosen stack and structure."""

    chosen_backend_language: TargetLanguage
    chosen_pattern: ArchitecturalPattern
    chosen_database: str = "postgresql"
    chosen_frontend_stack: Optional[str] = "nextjs_shadcn"
    ai_friendliness_score: int = Field(
        default=95,
        ge=0,
        le=100,
        description="How easily future AI agents (Cursor/Copilot) can navigate this output",
    )
    rationale: str = Field(
        ..., description="Why this stack/pattern fits the constraints"
    )
    container_services: List[str] = Field(
        default_factory=lambda: ["backend", "db", "frontend"],
        description="Services to generate in docker-compose.yml",
    )


# ============================================================================
# 7. ROOT BLUEPRINT: THE MASTER PROJECT IR
# ============================================================================


class ProjectIR(BaseModel):
    """
    The Single Source of Truth across all 5 phases of REGEN.
    Serialized to JSON/YAML to drive deterministic scaffolding.
    """

    model_config = ConfigDict(validate_assignment=True)

    project_id: str = Field(default_factory=lambda: f"proj_{uuid4().hex[:10]}")
    project_name: str
    version: str = "1.0.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Phase 1 Metrics
    ingestion_metrics: IngestionMetrics = Field(default_factory=IngestionMetrics)

    # Phase 2 Core Blueprint
    entities: List[EntityDefinition] = Field(default_factory=list)
    relationships: List[RelationshipDefinition] = Field(default_factory=list)
    business_rules: List[BusinessRule] = Field(default_factory=list)
    routes: List[RouteDefinition] = Field(default_factory=list)
    ui_views: List[UIViewComponent] = Field(default_factory=list)

    # Phase 3 HITL & Architecture
    hitl_questions: List[HITLQuestion] = Field(default_factory=list)
    technical_constraints: TechnicalConstraints = Field(
        default_factory=TechnicalConstraints
    )
    architecture_decision: Optional[ArchitectureDecision] = None

    # Phase 5 Strangler Fig Parity Tests
    characterization_tests: List[CharacterizationContract] = Field(default_factory=list)

    @property
    def is_ready_for_scaffolding(self) -> bool:
        """
        Enforces the HITL constraint: Cannot scaffold Phase 4 if any
        critical business rule ambiguity remains unresolved or architecture isn't chosen.
        """
        has_unresolved = any(
            q.status == AmbiguityStatus.UNRESOLVED for q in self.hitl_questions
        )
        return (not has_unresolved) and (self.architecture_decision is not None)
