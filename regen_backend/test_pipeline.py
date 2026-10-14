# test_pipeline.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def run_e2e_pipeline_verification() -> None:
    print("=== [STEP 1] Testing GET /api/v1/health ===")
    r1 = client.get("/api/v1/health")
    assert r1.status_code == 200
    print("Health Check Passed:", r1.json()["status"])

    print("\n=== [STEP 2] Testing POST /api/v1/ingestion/analyze ===")
    ingest_payload = {
        "project_name": "LegacyBillingApp",
        "code_files": [
            {
                "file_path": "billing.py",
                "content": (
                    "class Invoice:\n"
                    "    id: int\n"
                    "    customer_email: str\n"
                    "    total_amount: float\n"
                    "    is_paid: bool = False\n\n"
                    "@app.get('/invoices')\n"
                    "def list_invoices():\n"
                    "    return []\n\n"
                    "def calculate_legacy_discount(amount, tier, region, promo_code, is_holiday):\n"
                    "    if amount > 5000:\n"
                    "        if tier == 'GOLD' and region != 'EU':\n"
                    "            return amount * 0.82\n"
                    "        elif promo_code == 'X99_LEGACY' or is_holiday:\n"
                    "            return amount * 0.88\n"
                    "    elif amount > 1000 and tier == 'SILVER':\n"
                    "        return amount * 0.95\n"
                    "    return amount\n"
                ),
            }
        ],
        "plain_text_requirements": "- Invoices above $10,000 require dual manager approval.",
    }
    r2 = client.post("/api/v1/ingestion/analyze", json=ingest_payload)
    assert r2.status_code == 200
    ir = r2.json()
    question_id = ir["hitl_questions"][0]["id"]
    print(
        f"Ingestion Passed! Extracted {len(ir['entities'])} entity, {len(ir['routes'])} route."
    )
    print(f"Token Saver Metrics: {ir['ingestion_metrics']}")
    print(
        f"Isolated Ambiguous Question ID: {question_id} (status: {ir['hitl_questions'][0]['status']})"
    )

    print("\n=== [STEP 3] Testing POST /api/v1/ir/validate (Pre-HITL Gate) ===")
    r3 = client.post("/api/v1/ir/validate", json=ir)
    assert r3.status_code == 200
    val_pre = r3.json()
    assert val_pre["ready_for_scaffolding"] is False
    print(
        f"Gate Verification Passed! ready_for_scaffolding = {val_pre['ready_for_scaffolding']} (Blocked by {val_pre['unresolved_hitl_questions']} unresolved question)"
    )

    print("\n=== [STEP 4] Testing POST /api/v1/architect/resolve-hitl ===")
    resolve_payload = {
        "project_ir": ir,
        "answers": [
            {
                "question_id": question_id,
                "selected_option_or_custom_answer": "Extract hardcoded thresholds into configuration/DB rules",
                "mark_rule_deprecated": False,
            }
        ],
    }
    r4 = client.post("/api/v1/architect/resolve-hitl", json=resolve_payload)
    assert r4.status_code == 200
    resolved_ir = r4.json()
    assert resolved_ir["hitl_questions"][0]["status"] == "resolved"
    print(
        "HITL Resolution Passed! Question status is now:",
        resolved_ir["hitl_questions"][0]["status"],
    )

    print("\n=== [STEP 5] Testing POST /api/v1/architect/recommend-stack ===")
    recommend_payload = {
        "project_ir": resolved_ir,
        "constraints": {
            "preferred_languages": [],
            "expected_concurrency_rps": 1200,
            "io_heavy": True,
            "cpu_heavy": False,
            "database_preference": "postgresql",
            "require_frontend": True,
        },
        "override_language": None,
    }
    r5 = client.post("/api/v1/architect/recommend-stack", json=recommend_payload)
    assert r5.status_code == 200
    rec_data = r5.json()
    assert rec_data["ready_for_scaffolding"] is True
    arch = rec_data["selected_architecture"]
    print(
        f"Stack Advisor Passed! ready_for_scaffolding = {rec_data['ready_for_scaffolding']}"
    )
    print(
        f"Selected Stack: {arch['chosen_backend_language']} | Pattern: {arch['chosen_pattern']}"
    )
    print(f"Rationale: {arch['rationale']}")

    print("\n=== [STEP 6] Testing Phase 4 Guardrail (Reject Unresolved IR) ===")
    r6_blocked = client.post("/api/v1/scaffolder/preview", json=ir)
    assert r6_blocked.status_code == 422
    print(
        "Guardrail Passed! Unresolved IR properly rejected with 422:",
        r6_blocked.json()["detail"],
    )

    print(
        "\n=== [STEP 7] Testing Phase 4 & 5 Codebase Preview (/api/v1/scaffolder/preview) ==="
    )
    final_ir = rec_data["project_ir"]
    r7 = client.post("/api/v1/scaffolder/preview", json=final_ir)
    assert r7.status_code == 200
    manifest = r7.json()
    print(
        f"Scaffolder Preview Passed! Generated {manifest['total_files_generated']} files for stack `{manifest['chosen_stack']}`:"
    )
    for f in manifest["files"]:
        print(f"  - [{f['category'].upper()}] {f['path']} ({f['language']})")

    print(
        "\n=== [STEP 8] Testing Phase 4 Container ZIP Export (/api/v1/scaffolder/download-zip) ==="
    )
    r8 = client.post("/api/v1/scaffolder/download-zip", json=final_ir)
    assert r8.status_code == 200
    assert r8.headers["content-type"] == "application/zip"
    print(f"ZIP Export Passed! Archive size: {len(r8.content)} bytes")

    # Save the ZIP to disk inside regen_backend
    output_zip = "legacybillingapp_kickstarter.zip"
    with open(output_zip, "wb") as f:
        f.write(r8.content)
    print(f"Saved archive to: {output_zip}")


if __name__ == "__main__":
    run_e2e_pipeline_verification()
