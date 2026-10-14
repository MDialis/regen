# app/services/scaffolder/engine.py
import io
import json
import zipfile
from typing import Dict, List
from pydantic import BaseModel, Field

from app.domain.ir_schema import (
    DataTypePrimitive,
    EntityDefinition,
    ProjectIR,
    TargetLanguage,
)
from app.services.strangler.test_generator import strangler_generator


class GeneratedFile(BaseModel):
    path: str = Field(
        ..., description="Relative file path inside the Kick-Starter repo"
    )
    language: str = Field(
        ..., description="Syntax highlighting hint, e.g., python, go, yaml"
    )
    category: str = Field(
        ...,
        description="infrastructure | domain | application | adapter | tests | docs",
    )
    content: str


class ScaffoldManifest(BaseModel):
    project_id: str
    project_name: str
    chosen_stack: TargetLanguage
    chosen_pattern: str
    total_files_generated: int
    files: List[GeneratedFile]


class ScaffolderEngine:
    """
    Phase 4 Deterministic Scaffolding Engine.
    Transforms a validated ProjectIR into a containerized, AI-friendly Kick-Starter codebase.
    """

    def generate_manifest(self, ir: ProjectIR) -> ScaffoldManifest:
        if not ir.is_ready_for_scaffolding or ir.architecture_decision is None:
            raise ValueError(
                "ProjectIR is not ready for scaffolding. Resolve all HITL questions "
                "and run the Stack Advisor first."
            )

        # Ensure Phase 5 characterization tests are populated
        strangler_generator.populate_contracts(ir)

        stack = ir.architecture_decision.chosen_backend_language
        pattern = ir.architecture_decision.chosen_pattern.value
        files: List[GeneratedFile] = []

        # 1. Container-First Infrastructure (Dockerfile, docker-compose.yml, Makefile)
        files.extend(self._generate_infrastructure_files(ir, stack))

        # 2. AI-Friendliness Documentation (AGENTS.md + Blueprint IR snapshot)
        files.extend(self._generate_ai_documentation_files(ir))

        # 3. Stack-Specific Hexagonal / Clean Architecture Source Tree
        if stack == TargetLanguage.GO_FIBER_OR_CHI:
            files.extend(self._generate_go_hexagonal_stack(ir))
        elif stack == TargetLanguage.TYPESCRIPT_NEST_OR_NODE:
            files.extend(self._generate_ts_hexagonal_stack(ir))
        else:
            # Default rich generator for Python FastAPI (and extensible fallback for Rust/C#)
            files.extend(self._generate_python_hexagonal_stack(ir))

        # 4. Phase 5: Strangler Fig Characterization Test Suite
        files.append(
            GeneratedFile(
                path="tests/test_strangler_parity.py",
                language="python",
                category="tests",
                content=strangler_generator.render_parity_test_file(ir),
            )
        )

        return ScaffoldManifest(
            project_id=ir.project_id,
            project_name=ir.project_name,
            chosen_stack=stack,
            chosen_pattern=pattern,
            total_files_generated=len(files),
            files=files,
        )

    def build_zip_archive(self, ir: ProjectIR) -> bytes:
        """Packages all generated Kick-Starter files into an in-memory .zip archive."""
        manifest = self.generate_manifest(ir)
        buffer = io.BytesIO()
        root_folder = ir.project_name.lower().replace(" ", "_")

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for gen_file in manifest.files:
                zf.writestr(f"{root_folder}/{gen_file.path}", gen_file.content)

        buffer.seek(0)
        return buffer.getvalue()

    # ========================================================================
    # INFRASTRUCTURE & AI-FRIENDLINESS TEMPLATES
    # ========================================================================

    def _generate_infrastructure_files(
        self, ir: ProjectIR, stack: TargetLanguage
    ) -> List[GeneratedFile]:
        if stack == TargetLanguage.GO_FIBER_OR_CHI:
            dockerfile = (
                "FROM golang:1.23-alpine AS builder\n"
                "WORKDIR /app\n"
                "COPY . .\n"
                "RUN go mod init kickstarter || true && go build -o server ./cmd/api/main.go\n\n"
                "FROM alpine:3.20\n"
                "WORKDIR /app\n"
                "COPY --from=builder /app/server .\n"
                "EXPOSE 8000\n"
                'CMD ["./server"]\n'
            )
        elif stack == TargetLanguage.TYPESCRIPT_NEST_OR_NODE:
            dockerfile = (
                "FROM node:22-alpine\n"
                "WORKDIR /app\n"
                "COPY package.json .\n"
                "RUN npm install\n"
                "COPY . .\n"
                "EXPOSE 8000\n"
                'CMD ["npm", "start"]\n'
            )
        else:
            dockerfile = (
                "FROM python:3.13-slim\n"
                "WORKDIR /app\n"
                "COPY requirements.txt .\n"
                "RUN pip install --no-cache-dir -r requirements.txt\n"
                "COPY . .\n"
                "EXPOSE 8000\n"
                'CMD ["uvicorn", "src.adapters.api.main:app", "--host", "0.0.0.0", "--port", "8000"]\n'
            )

        compose = (
            "services:\n"
            "  backend:\n"
            "    build: .\n"
            "    ports:\n"
            '      - "8000:8000"\n'
            "    environment:\n"
            "      - DATABASE_URL=postgresql://postgres:postgres@db:5432/kickstarter\n"
            "    depends_on:\n"
            "      db:\n"
            "        condition: service_healthy\n\n"
            "  db:\n"
            "    image: postgres:16-alpine\n"
            "    environment:\n"
            "      - POSTGRES_USER=postgres\n"
            "      - POSTGRES_PASSWORD=postgres\n"
            "      - POSTGRES_DB=kickstarter\n"
            "    ports:\n"
            '      - "5432:5432"\n'
            "    healthcheck:\n"
            '      test: ["CMD-SHELL", "pg_isready -U postgres"]\n'
            "      interval: 5s\n"
            "      timeout: 5s\n"
            "      retries: 5\n"
        )

        makefile = (
            ".PHONY: up down test\n\n"
            "up:\n"
            "\tdocker compose up --build -d\n\n"
            "down:\n"
            "\tdocker compose down\n\n"
            "test:\n"
            "\tpytest tests/\n"
        )

        return [
            GeneratedFile(
                path="Dockerfile",
                language="dockerfile",
                category="infrastructure",
                content=dockerfile,
            ),
            GeneratedFile(
                path="docker-compose.yml",
                language="yaml",
                category="infrastructure",
                content=compose,
            ),
            GeneratedFile(
                path="Makefile",
                language="makefile",
                category="infrastructure",
                content=makefile,
            ),
        ]

    def _generate_ai_documentation_files(self, ir: ProjectIR) -> List[GeneratedFile]:
        arch = ir.architecture_decision
        assert arch is not None

        rules_md = "\n".join(
            f"- **{r.title}** (`{r.id}`): {r.expected_behavior}"
            for r in ir.business_rules
        )
        agents_md = (
            f"# {ir.project_name} — AI Agent Maintenance Guide (AGENTS.md)\n\n"
            f"## 1. Architecture Overview\n"
            f"- **Pattern:** `{arch.chosen_pattern.value}`\n"
            f"- **Stack:** `{arch.chosen_backend_language.value}` + `{arch.chosen_database}`\n"
            f"- **AI-Friendliness Score:** `{arch.ai_friendliness_score}/100`\n"
            f"- **Rationale:** {arch.rationale}\n\n"
            f"## 2. Strict Boundary Rules for AI Coding Assistants (Cursor / Copilot)\n"
            f"1. **Domain Purity:** `src/domain/` must NEVER import from `src/adapters/` or HTTP frameworks.\n"
            f"2. **Dependency Inversion:** Use Cases in `src/application/` depend strictly on Repository Ports.\n"
            f"3. **Verified Business Rules (HITL Approved):**\n"
            f"{rules_md or '- No custom rules extracted.'}\n"
        )

        ir_snapshot = json.dumps(ir.model_dump(mode="json"), indent=2)

        return [
            GeneratedFile(
                path="AGENTS.md",
                language="markdown",
                category="docs",
                content=agents_md,
            ),
            GeneratedFile(
                path="regen_blueprint.ir.json",
                language="json",
                category="docs",
                content=ir_snapshot,
            ),
        ]

    # ========================================================================
    # STACK GENERATORS (HEXAGONAL / CLEAN ARCHITECTURE)
    # ========================================================================

    def _generate_python_hexagonal_stack(self, ir: ProjectIR) -> List[GeneratedFile]:
        py_type_map = {
            DataTypePrimitive.STRING: "str",
            DataTypePrimitive.INTEGER: "int",
            DataTypePrimitive.FLOAT: "float",
            DataTypePrimitive.DECIMAL: "float",
            DataTypePrimitive.BOOLEAN: "bool",
            DataTypePrimitive.DATETIME: "str",
            DataTypePrimitive.UUID: "str",
            DataTypePrimitive.JSON: "dict",
        }

        # 1. Domain Entities
        entity_lines = [
            "from typing import Optional",
            "from pydantic import BaseModel",
            "",
        ]
        for ent in ir.entities:
            entity_lines.append(f"class {ent.name}(BaseModel):")
            entity_lines.append(f'    """{ent.description}"""')
            if not ent.fields:
                entity_lines.append("    id: int")
            for f in ent.fields:
                py_t = py_type_map.get(f.data_type, "str")
                if not f.is_required:
                    entity_lines.append(f"    {f.name}: Optional[{py_t}] = None")
                else:
                    entity_lines.append(f"    {f.name}: {py_t}")
            entity_lines.append("")

        # 2. Application Use Cases (incorporating HITL-clarified Business Rules)
        use_case_lines = [
            '"""Application Use Cases enforcing HITL-verified Business Rules."""',
            "from typing import Any, Dict",
            "",
            "class DomainRuleEngine:",
        ]
        if not ir.business_rules:
            use_case_lines.append("    pass")
        for idx, rule in enumerate(ir.business_rules, start=1):
            use_case_lines.extend(
                [
                    f"    def enforce_rule_{idx}_{rule.id}(self, context: Dict[str, Any]) -> Dict[str, Any]:",
                    f'        """',
                    f"        Rule: {rule.title}",
                    f"        Trigger: {rule.trigger_condition}",
                    f"        Verified Behavior: {rule.expected_behavior}",
                    f'        """',
                    f'        return {{"rule_id": "{rule.id}", "enforced": True, "context": context}}',
                    "",
                ]
            )

        # 3. FastAPI Adapter (Routes)
        api_lines = [
            "from fastapi import FastAPI",
            "from src.domain.entities import *",
            "from src.application.use_cases import DomainRuleEngine",
            "",
            f'app = FastAPI(title="{ir.project_name} - Kick-Starter API")',
            "rule_engine = DomainRuleEngine()",
            "",
            '@app.get("/health")',
            "def health():",
            f'    return {{"status": "ok", "project": "{ir.project_name}"}}',
            "",
        ]
        for route in ir.routes:
            method_lower = route.method.value.lower()
            fn_name = (
                route.path.strip("/")
                .replace("/", "_")
                .replace("{", "")
                .replace("}", "")
                or "root"
            )
            api_lines.extend(
                [
                    f'@app.{method_lower}("{route.path}")',
                    f"def handle_{method_lower}_{fn_name}():",
                    f'    """{route.summary}"""',
                    "    return []",
                    "",
                ]
            )

        return [
            GeneratedFile(
                path="requirements.txt",
                language="text",
                category="infrastructure",
                content="fastapi>=0.115.0\nuvicorn[standard]>=0.30.6\npydantic>=2.10.0\nhttpx>=0.27.2\npytest>=8.3.0\n",
            ),
            GeneratedFile(
                path="src/domain/entities.py",
                language="python",
                category="domain",
                content="\n".join(entity_lines),
            ),
            GeneratedFile(
                path="src/application/use_cases.py",
                language="python",
                category="application",
                content="\n".join(use_case_lines),
            ),
            GeneratedFile(
                path="src/adapters/api/main.py",
                language="python",
                category="adapter",
                content="\n".join(api_lines),
            ),
        ]

    def _generate_go_hexagonal_stack(self, ir: ProjectIR) -> List[GeneratedFile]:
        go_type_map = {
            DataTypePrimitive.STRING: "string",
            DataTypePrimitive.INTEGER: "int64",
            DataTypePrimitive.FLOAT: "float64",
            DataTypePrimitive.DECIMAL: "float64",
            DataTypePrimitive.BOOLEAN: "bool",
        }

        domain_lines = ["package domain", ""]
        for ent in ir.entities:
            domain_lines.append(f"// {ent.name} - {ent.description}")
            domain_lines.append(f"type {ent.name} struct {{")
            for f in ent.fields:
                go_t = go_type_map.get(f.data_type, "string")
                pascal_field = "".join(w.capitalize() for w in f.name.split("_"))
                domain_lines.append(f'\t{pascal_field} {go_t} `json:"{f.name}"`')
            domain_lines.append("}\n")

        rules_comments = "\n".join(
            f"// Rule [{r.id}]: {r.title} -> {r.expected_behavior}"
            for r in ir.business_rules
        )
        usecase_go = (
            "package application\n\n"
            "// Verified Business Rules from REGEN HITL Wizard:\n"
            f"{rules_comments}\n\n"
            "type RuleService struct{}\n\n"
            "func NewRuleService() *RuleService {\n"
            "\treturn &RuleService{}\n"
            "}\n"
        )

        main_go = (
            "package main\n\n"
            "import (\n"
            '\t"encoding/json"\n'
            '\t"log"\n'
            '\t"net/http"\n'
            ")\n\n"
            "func main() {\n"
            '\thttp.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {\n'
            '\t\tw.Header().Set("Content-Type", "application/json")\n'
            f'\t\tjson.NewEncoder(w).Encode(map[string]string{{"status": "ok", "project": "{ir.project_name}"}})\n'
            "\t})\n"
        )
        for route in ir.routes:
            main_go += (
                f'\thttp.HandleFunc("{route.path}", func(w http.ResponseWriter, r *http.Request) {{\n'
                '\t\tw.Header().Set("Content-Type", "application/json")\n'
                '\t\tw.Write([]byte("[]"))\n'
                "\t})\n"
            )
        main_go += (
            '\tlog.Println("Kick-Starter Go Hexagonal Server listening on :8000")\n'
            '\tlog.Fatal(http.ListenAndServe(":8000", nil))\n'
            "}\n"
        )

        return [
            GeneratedFile(
                path="internal/domain/entities.go",
                language="go",
                category="domain",
                content="\n".join(domain_lines),
            ),
            GeneratedFile(
                path="internal/application/usecases.go",
                language="go",
                category="application",
                content=usecase_go,
            ),
            GeneratedFile(
                path="cmd/api/main.go",
                language="go",
                category="adapter",
                content=main_go,
            ),
        ]

    def _generate_ts_hexagonal_stack(self, ir: ProjectIR) -> List[GeneratedFile]:
        ts_type_map = {
            DataTypePrimitive.STRING: "string",
            DataTypePrimitive.INTEGER: "number",
            DataTypePrimitive.FLOAT: "number",
            DataTypePrimitive.DECIMAL: "number",
            DataTypePrimitive.BOOLEAN: "boolean",
        }
        entity_lines = ["// Strict Domain Entities generated by REGEN\n"]
        for ent in ir.entities:
            entity_lines.append(f"export interface {ent.name} {{")
            for f in ent.fields:
                ts_t = ts_type_map.get(f.data_type, "string")
                opt = "" if f.is_required else "?"
                entity_lines.append(f"  {f.name}{opt}: {ts_t};")
            entity_lines.append("}\n")

        return [
            GeneratedFile(
                path="src/domain/entities.ts",
                language="typescript",
                category="domain",
                content="\n".join(entity_lines),
            ),
            GeneratedFile(
                path="package.json",
                language="json",
                category="infrastructure",
                content=json.dumps(
                    {
                        "name": ir.project_name.lower(),
                        "version": "1.0.0",
                        "scripts": {"start": "node dist/main.js"},
                    },
                    indent=2,
                ),
            ),
        ]


scaffolder_engine = ScaffolderEngine()
