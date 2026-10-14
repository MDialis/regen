# REGEN Backend — AI Agent Guidelines

## Core Architectural Rules

1. **Single Source of Truth:** All pipeline phases must read from and write to `app.domain.ir_schema.ProjectIR`. Never pass untyped dictionaries between pipeline phases.
2. **Deterministic First:** Always use `tree-sitter` and deterministic AST visitors before invoking an LLM. Only send code blocks to OpenAI when `cyclomatic_complexity >= settings.MIN_CYCLOMATIC_COMPLEXITY_FOR_LLM`.
3. **Human-in-the-Loop Gate:** Never guess ambiguous business rules. If a rule has `is_ambiguous=True`, append a `HITLQuestion` to `ProjectIR.hitl_questions`. Phase 4 (`scaffolder`) must refuse to run while `ir.is_ready_for_scaffolding` is `False`.
4. **Agnostic Output:** Do not hardcode target stack assumptions into the IR. Target language specifics belong strictly in `app/services/scaffolder/`.
