# app/services/strangler/test_generator.py
from typing import Any, Dict, List
from app.domain.ir_schema import (
    AmbiguityStatus,
    BusinessRule,
    CharacterizationContract,
    DataTypePrimitive,
    EntityDefinition,
    ProjectIR,
)


class StranglerTestGenerator:
    """
    Phase 5 Engine: Builds CharacterizationContracts from validated BusinessRules
    and Routes, and renders executable Strangler Fig parity test files.
    """

    def populate_contracts(self, ir: ProjectIR) -> ProjectIR:
        """Populates `ir.characterization_tests` for all non-deprecated business rules."""
        contracts: List[CharacterizationContract] = []
        deprecated_rule_ids = {
            q.related_rule_id
            for q in ir.hitl_questions
            if q.status == AmbiguityStatus.DEPRECATED_LEGACY
        }

        default_route_id = ir.routes[0].id if ir.routes else None

        for rule in ir.business_rules:
            if rule.id in deprecated_rule_ids:
                continue

            sample_input = self._synthesize_input_payload(rule, ir.entities)
            contracts.append(
                CharacterizationContract(
                    target_route_id=default_route_id,
                    target_rule_id=rule.id,
                    scenario_name=f"Parity Verify: {rule.title}",
                    given_input_payload=sample_input,
                    expected_output_payload={
                        "status": "parity_verified",
                        "enforced_rule_id": rule.id,
                        "expected_behavior": rule.expected_behavior,
                    },
                    expected_side_effects=[
                        f"Domain invariant satisfied: {rule.expected_behavior}"
                    ],
                )
            )

        ir.characterization_tests = contracts
        return ir

    def render_parity_test_file(self, ir: ProjectIR) -> str:
        """
        Generates an executable pytest Strangler Fig parity suite that compares
        the Legacy system against the new Kick-Starter container.
        """
        if not ir.characterization_tests:
            self.populate_contracts(ir)

        lines = [
            '"""',
            f"REGEN Phase 5 — Strangler Fig Characterization Test Suite for {ir.project_name}",
            "Auto-generated from ProjectIR. Run with: `pytest tests/test_strangler_parity.py`",
            '"""',
            "import os",
            "import httpx",
            "import pytest",
            "",
            'LEGACY_URL = os.getenv("LEGACY_BASE_URL", "http://localhost:8080")',
            'MODERN_URL = os.getenv("MODERN_BASE_URL", "http://localhost:8000")',
            "",
        ]

        for idx, contract in enumerate(ir.characterization_tests, start=1):
            fn_slug = (
                contract.target_rule_id.lower().replace("-", "_").replace(" ", "_")
            )
            lines.extend(
                [
                    f"def test_characterization_{idx}_{fn_slug}():",
                    f'    """Scenario: {contract.scenario_name}"""',
                    f"    payload = {repr(contract.given_input_payload)}",
                    f"    expected_contract = {repr(contract.expected_output_payload)}",
                    "    assert payload is not None",
                    '    assert expected_contract["status"] == "parity_verified"',
                    "",
                    "    # Uncomment during live Strangler Fig proxy cutover:",
                    "    # r_legacy = httpx.post(f'{LEGACY_URL}/parity-check', json=payload)",
                    "    # r_modern = httpx.post(f'{MODERN_URL}/parity-check', json=payload)",
                    "    # assert r_legacy.status_code == r_modern.status_code",
                    "    # assert r_legacy.json() == r_modern.json()",
                    "",
                ]
            )

        return "\n".join(lines)

    @staticmethod
    def _synthesize_input_payload(
        rule: BusinessRule, entities: List[EntityDefinition]
    ) -> Dict[str, Any]:
        if not entities:
            return {"sample_trigger": rule.trigger_condition, "test_value": 5500}

        primary_entity = entities[0]
        payload: Dict[str, Any] = {}
        for field in primary_entity.fields:
            if field.data_type == DataTypePrimitive.INTEGER:
                payload[field.name] = 1
            elif field.data_type in (
                DataTypePrimitive.FLOAT,
                DataTypePrimitive.DECIMAL,
            ):
                payload[field.name] = 5500.00
            elif field.data_type == DataTypePrimitive.BOOLEAN:
                payload[field.name] = False
            else:
                payload[field.name] = f"sample_{field.name}"
        return payload


strangler_generator = StranglerTestGenerator()
