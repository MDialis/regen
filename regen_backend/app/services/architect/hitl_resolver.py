# app/services/architect/hitl_resolver.py
from typing import Dict, List
from app.domain.ir_schema import (
    AmbiguityStatus,
    ProjectIR,
    SourceModality,
    SourceReference,
)
from app.domain.wizard_state import HITLAnswerItem


class HITLResolverService:
    """
    Applies Human-in-the-Loop interview answers to the ProjectIR,
    updating business rules and clearing ambiguity gates.
    """

    def resolve_questions(
        self, ir: ProjectIR, answers: List[HITLAnswerItem]
    ) -> ProjectIR:
        answer_map: Dict[str, HITLAnswerItem] = {
            ans.question_id: ans for ans in answers
        }
        rule_map = {rule.id: rule for rule in ir.business_rules}

        for question in ir.hitl_questions:
            if question.id not in answer_map:
                continue

            ans = answer_map[question.id]
            question.user_response = ans.selected_option_or_custom_answer

            linked_rule = rule_map.get(question.related_rule_id)

            if ans.mark_rule_deprecated:
                question.status = AmbiguityStatus.DEPRECATED_LEGACY
                if linked_rule:
                    linked_rule.is_ambiguous = False
                    linked_rule.expected_behavior = (
                        f"[DEPRECATED BY USER] {linked_rule.expected_behavior}"
                    )
                    linked_rule.confidence_score = 1.0
            else:
                question.status = AmbiguityStatus.RESOLVED
                if linked_rule:
                    linked_rule.is_ambiguous = False
                    linked_rule.expected_behavior = (
                        f"{linked_rule.expected_behavior} | "
                        f"HITL Clarified Policy: {ans.selected_option_or_custom_answer}"
                    )
                    linked_rule.confidence_score = 1.0
                    linked_rule.sources.append(
                        SourceReference(modality=SourceModality.HITL_INTERVIEW)
                    )

        return ir


hitl_resolver = HITLResolverService()
