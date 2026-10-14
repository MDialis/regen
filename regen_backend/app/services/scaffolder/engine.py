# app/services/scaffolder/engine.py
import io
import json
import zipfile
from typing import List
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
        ..., description="Syntax highlighting hint, e.g., python, go, typescript"
    )
    category: str = Field(
        ...,
        description="infrastructure | domain | application | adapter | frontend-ui | frontend-data | tests | docs",
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
    Transforms a validated ProjectIR into a containerized, full-stack,
    componentized Kick-Starter monorepo (`backend/` + `frontend/`).
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
        include_frontend = (
            ir.technical_constraints.require_frontend
            or ir.architecture_decision.chosen_frontend_stack is not None
        )

        files: List[GeneratedFile] = []

        # 1. Root Container-First Infrastructure (docker-compose.yml, Makefile, Dockerfiles)
        files.extend(self._generate_infrastructure_files(ir, stack, include_frontend))

        # 2. Root AI-Friendliness Documentation (AGENTS.md + Blueprint IR snapshot)
        files.extend(self._generate_ai_documentation_files(ir, include_frontend))

        # 3. Backend Stack (Scoped cleanly inside `backend/`)
        if stack == TargetLanguage.GO_FIBER_OR_CHI:
            files.extend(self._generate_go_hexagonal_stack(ir))
        elif stack == TargetLanguage.TYPESCRIPT_NEST_OR_NODE:
            files.extend(self._generate_ts_hexagonal_stack(ir))
        else:
            files.extend(self._generate_python_hexagonal_stack(ir))

        # 4. Frontend Stack (Scoped inside `frontend/` with strict componentization)
        if include_frontend:
            files.extend(self._generate_componentized_nextjs_frontend(ir))

        # 5. Phase 5: Strangler Fig Characterization Test Suite
        files.append(
            GeneratedFile(
                path="backend/tests/test_strangler_parity.py",
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
    # 1. INFRASTRUCTURE & AI-FRIENDLINESS TEMPLATES
    # ========================================================================

    def _generate_infrastructure_files(
        self, ir: ProjectIR, stack: TargetLanguage, include_frontend: bool
    ) -> List[GeneratedFile]:
        if stack == TargetLanguage.GO_FIBER_OR_CHI:
            backend_dockerfile = (
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
            backend_dockerfile = (
                "FROM node:22-alpine\n"
                "WORKDIR /app\n"
                "COPY package.json .\n"
                "RUN npm install\n"
                "COPY . .\n"
                "EXPOSE 8000\n"
                'CMD ["npm", "start"]\n'
            )
        else:
            backend_dockerfile = (
                "FROM python:3.13-slim\n"
                "WORKDIR /app\n"
                "COPY requirements.txt .\n"
                "RUN pip install --no-cache-dir -r requirements.txt\n"
                "COPY . .\n"
                "EXPOSE 8000\n"
                'CMD ["uvicorn", "src.adapters.api.main:app", "--host", "0.0.0.0", "--port", "8000"]\n'
            )

        frontend_service_yaml = ""
        if include_frontend:
            frontend_service_yaml = (
                "  frontend:\n"
                "    build: ./frontend\n"
                "    ports:\n"
                '      - "3000:3000"\n'
                "    environment:\n"
                "      - NEXT_PUBLIC_API_URL=http://localhost:8000\n"
                "    depends_on:\n"
                "      - backend\n\n"
            )

        compose = (
            "services:\n"
            "  backend:\n"
            "    build: ./backend\n"
            "    ports:\n"
            '      - "8000:8000"\n'
            "    environment:\n"
            "      - DATABASE_URL=postgresql://postgres:postgres@db:5432/kickstarter\n"
            "    depends_on:\n"
            "      db:\n"
            "        condition: service_healthy\n\n"
            f"{frontend_service_yaml}"
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
            "\tpytest backend/tests/\n"
        )

        infra_files = [
            GeneratedFile(
                path="backend/Dockerfile",
                language="dockerfile",
                category="infrastructure",
                content=backend_dockerfile,
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

        if include_frontend:
            frontend_dockerfile = (
                "FROM node:22-alpine\n"
                "WORKDIR /app\n"
                "COPY package.json .\n"
                "RUN npm install\n"
                "COPY . .\n"
                "EXPOSE 3000\n"
                'CMD ["npm", "run", "dev"]\n'
            )
            infra_files.append(
                GeneratedFile(
                    path="frontend/Dockerfile",
                    language="dockerfile",
                    category="infrastructure",
                    content=frontend_dockerfile,
                )
            )

        return infra_files

    def _generate_ai_documentation_files(
        self, ir: ProjectIR, include_frontend: bool
    ) -> List[GeneratedFile]:
        arch = ir.architecture_decision
        assert arch is not None

        rules_md = "\n".join(
            f"- **{r.title}** (`{r.id}`): {r.expected_behavior}"
            for r in ir.business_rules
        )
        frontend_note = (
            "\n## 3. Frontend Componentization Rules (`frontend/`)\n"
            "1. **No Monolithic Pages:** Pages in `src/app/` must only compose components and hooks (< 60 lines).\n"
            "2. **Domain Component Isolation:** Each Entity has its own `<Entity>Card.tsx` and `<Entity>Table.tsx` inside `src/components/domain/`.\n"
            "3. **Strict API Layer:** Components must never call `fetch()` directly; use `src/services/apiClient.ts`.\n"
            if include_frontend
            else ""
        )

        agents_md = (
            f"# {ir.project_name} — AI Agent Maintenance Guide (AGENTS.md)\n\n"
            f"## 1. Architecture Overview\n"
            f"- **Pattern:** `{arch.chosen_pattern.value}`\n"
            f"- **Backend Stack:** `{arch.chosen_backend_language.value}` + `{arch.chosen_database}`\n"
            f"- **Frontend Stack:** `{arch.chosen_frontend_stack or 'None'}`\n"
            f"- **AI-Friendliness Score:** `{arch.ai_friendliness_score}/100`\n"
            f"- **Rationale:** {arch.rationale}\n\n"
            f"## 2. Backend Boundary Rules (`backend/`)\n"
            f"1. **Domain Purity:** `src/domain/` must NEVER import from `src/adapters/` or HTTP frameworks.\n"
            f"2. **Dependency Inversion:** Use Cases in `src/application/` depend strictly on Repository Ports.\n"
            f"3. **Verified Business Rules (HITL Approved):**\n"
            f"{rules_md or '- No custom rules extracted.'}\n"
            f"{frontend_note}"
        )

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
                content=json.dumps(ir.model_dump(mode="json"), indent=2),
            ),
        ]

    # ========================================================================
    # 2. COMPONENTIZED NEXT.JS FRONTEND GENERATOR (HIGH COHESION / LOOSE COUPLING)
    # ========================================================================

    def _generate_componentized_nextjs_frontend(
        self, ir: ProjectIR
    ) -> List[GeneratedFile]:
        ts_type_map = {
            DataTypePrimitive.STRING: "string",
            DataTypePrimitive.INTEGER: "number",
            DataTypePrimitive.FLOAT: "number",
            DataTypePrimitive.DECIMAL: "number",
            DataTypePrimitive.BOOLEAN: "boolean",
            DataTypePrimitive.DATETIME: "string",
            DataTypePrimitive.UUID: "string",
            DataTypePrimitive.JSON: "Record<string, unknown>",
        }

        files: List[GeneratedFile] = []

        # A. frontend/package.json & tsconfig.json
        pkg_json = {
            "name": f"{ir.project_name.lower().replace(' ', '-')}-frontend",
            "version": "0.1.0",
            "private": True,
            "scripts": {
                "dev": "next dev",
                "build": "next build",
                "start": "next start",
            },
            "dependencies": {
                "next": "^15.0.0",
                "react": "^19.0.0",
                "react-dom": "^19.0.0",
                "lucide-react": "^0.454.0",
            },
        }
        files.append(
            GeneratedFile(
                path="frontend/package.json",
                language="json",
                category="infrastructure",
                content=json.dumps(pkg_json, indent=2),
            )
        )

        # B. frontend/src/types/domain.ts (Strict TS Interfaces per IR Entity)
        type_lines = [
            "// Auto-generated by REGEN from ProjectIR Entities.",
            "// Do not untype or use `any` — AI agents rely on these strict contracts.",
            "",
        ]
        entities_to_render = ir.entities or [
            EntityDefinition(name="SampleItem", description="Default entity", fields=[])
        ]

        for ent in entities_to_render:
            type_lines.append(f"/** {ent.description} */")
            type_lines.append(f"export interface {ent.name} {{")
            if not ent.fields:
                type_lines.append("  id: number;")
            for f in ent.fields:
                ts_t = ts_type_map.get(f.data_type, "string")
                opt = "" if f.is_required else "?"
                type_lines.append(f"  {f.name}{opt}: {ts_t};")
            type_lines.append("}\n")

        files.append(
            GeneratedFile(
                path="frontend/src/types/domain.ts",
                language="typescript",
                category="frontend-data",
                content="\n".join(type_lines),
            )
        )

        # C. frontend/src/services/apiClient.ts (Decoupled Data Fetching Service)
        entity_imports = ", ".join(ent.name for ent in entities_to_render)
        api_client_lines = [
            f'import {{ {entity_imports} }} from "../types/domain";',
            "",
            'const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";',
            "",
            "async function request<T>(path: string, options?: RequestInit): Promise<T> {",
            "  const response = await fetch(`${API_BASE_URL}${path}`, {",
            '    headers: { "Content-Type": "application/json" },',
            "    ...options,",
            "  });",
            "  if (!response.ok) {",
            "    throw new Error(`API Error ${response.status}: ${response.statusText}`);",
            "  }",
            "  return response.json() as Promise<T>;",
            "}",
            "",
            "export const apiClient = {",
            '  checkHealth: () => request<{ status: string }>("/health"),',
        ]
        for ent in entities_to_render:
            slug = ent.name.lower() + "s"
            api_client_lines.append(
                f'  list{ent.name}s: () => request<{ent.name}[]>("/{slug}"),'
            )
        api_client_lines.append("};\n")

        files.append(
            GeneratedFile(
                path="frontend/src/services/apiClient.ts",
                language="typescript",
                category="frontend-data",
                content="\n".join(api_client_lines),
            )
        )

        # D. frontend/src/components/layout/AppShell.tsx (Reusable Layout Shell)
        app_shell_tsx = (
            'import React from "react";\n\n'
            "interface AppShellProps {\n"
            "  title: string;\n"
            "  children: React.ReactNode;\n"
            "}\n\n"
            "export function AppShell({ title, children }: AppShellProps) {\n"
            "  return (\n"
            '    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">\n'
            '      <header className="border-b border-slate-800 bg-slate-900 px-6 py-4 flex items-center justify-between">\n'
            '        <h1 className="text-lg font-bold tracking-tight text-emerald-400">{title}</h1>\n'
            '        <span className="text-xs font-mono text-slate-400">REGEN Kick-Starter</span>\n'
            "      </header>\n"
            '      <main className="flex-1 max-w-6xl w-full mx-auto p-6 space-y-6">\n'
            "        {children}\n"
            "      </main>\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        )
        files.append(
            GeneratedFile(
                path="frontend/src/components/layout/AppShell.tsx",
                language="typescript",
                category="frontend-ui",
                content=app_shell_tsx,
            )
        )

        # E. Dedicated Domain Components per Entity (<Entity>Table.tsx & <Entity>Card.tsx)
        for ent in entities_to_render:
            files.append(self._build_entity_table_component(ent))
            files.append(self._build_entity_card_component(ent))

        # F. Clean, Modular `frontend/src/app/page.tsx` (< 45 lines, pure composition)
        table_imports = "\n".join(
            f'import {{ {ent.name}Table }} from "../components/domain/{ent.name}Table";'
            for ent in entities_to_render
        )
        table_mounts = "\n      ".join(
            f"<{ent.name}Table items={{[]}} />" for ent in entities_to_render
        )

        clean_page_tsx = (
            'import React from "react";\n'
            'import { AppShell } from "../components/layout/AppShell";\n'
            f"{table_imports}\n\n"
            f"export default function {ir.project_name.replace(' ', '')}DashboardPage() {{\n"
            "  return (\n"
            f'    <AppShell title="{ir.project_name} Workspace">\n'
            '      <section className="space-y-6">\n'
            f"        {table_mounts}\n"
            "      </section>\n"
            "    </AppShell>\n"
            "  );\n"
            "}\n"
        )
        files.append(
            GeneratedFile(
                path="frontend/src/app/page.tsx",
                language="typescript",
                category="frontend-ui",
                content=clean_page_tsx,
            )
        )

        return files

    @staticmethod
    def _build_entity_table_component(ent: EntityDefinition) -> GeneratedFile:
        headers = (
            "\n              ".join(
                f'<th className="px-4 py-2 text-left text-xs font-semibold text-slate-400">{f.name}</th>'
                for f in ent.fields
            )
            or '<th className="px-4 py-2 text-left">ID</th>'
        )

        cells = (
            "\n                ".join(
                f'<td className="px-4 py-2 text-sm font-mono">{{String(item.{f.name})}}</td>'
                for f in ent.fields
            )
            or '<td className="px-4 py-2">{item.id}</td>'
        )

        pk_field = next((f.name for f in ent.fields if f.is_primary_key), None)
        row_key = f"String(item.{pk_field})" if pk_field else "idx"

        content = (
            'import React from "react";\n'
            f'import {{ {ent.name} }} from "../../types/domain";\n\n'
            f"interface {ent.name}TableProps {{\n"
            f"  items: {ent.name}[];\n"
            "}\n\n"
            f"export function {ent.name}Table({{ items }}: {ent.name}TableProps) {{\n"
            "  return (\n"
            '    <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden">\n'
            '      <div className="px-4 py-3 border-b border-slate-800 flex justify-between items-center">\n'
            f'        <h2 className="text-sm font-semibold text-slate-200">{ent.name} Records</h2>\n'
            '        <span className="text-xs text-slate-400">{items.length} total</span>\n'
            "      </div>\n"
            '      <table className="w-full border-collapse">\n'
            '        <thead className="bg-slate-950/60 border-b border-slate-800">\n'
            "          <tr>\n"
            f"              {headers}\n"
            "          </tr>\n"
            "        </thead>\n"
            "        <tbody>\n"
            "          {items.map((item, idx) => (\n"
            f'            <tr key={{{row_key}}} className="border-b border-slate-800/50">\n'
            f"                {cells}\n"
            "            </tr>\n"
            "          ))}\n"
            "        </tbody>\n"
            "      </table>\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        )
        return GeneratedFile(
            path=f"frontend/src/components/domain/{ent.name}Table.tsx",
            language="typescript",
            category="frontend-ui",
            content=content,
        )

    @staticmethod
    def _build_entity_card_component(ent: EntityDefinition) -> GeneratedFile:
        field_rows = "\n        ".join(
            f'<div className="flex justify-between text-xs">'
            f'<span className="text-slate-400">{f.name}:</span>'
            f'<span className="font-mono text-slate-200">{{String(data.{f.name})}}</span>'
            f"</div>"
            for f in ent.fields
        )
        content = (
            'import React from "react";\n'
            f'import {{ {ent.name} }} from "../../types/domain";\n\n'
            f"interface {ent.name}CardProps {{\n"
            f"  data: {ent.name};\n"
            "}\n\n"
            f"export function {ent.name}Card({{ data }}: {ent.name}CardProps) {{\n"
            "  return (\n"
            '    <div className="p-4 rounded-xl border border-slate-800 bg-slate-900 space-y-2">\n'
            f'      <h3 className="text-sm font-bold text-emerald-400">{ent.name}</h3>\n'
            '      <div className="space-y-1">\n'
            f"        {field_rows}\n"
            "      </div>\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        )
        return GeneratedFile(
            path=f"frontend/src/components/domain/{ent.name}Card.tsx",
            language="typescript",
            category="frontend-ui",
            content=content,
        )

    # ========================================================================
    # 3. BACKEND STACK GENERATORS (SCOPED TO `backend/`)
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
                path="backend/requirements.txt",
                language="text",
                category="infrastructure",
                content="fastapi>=0.115.0\nuvicorn[standard]>=0.30.6\npydantic>=2.10.0\nhttpx>=0.27.2\npytest>=8.3.0\n",
            ),
            GeneratedFile(
                path="backend/src/domain/entities.py",
                language="python",
                category="domain",
                content="\n".join(entity_lines),
            ),
            GeneratedFile(
                path="backend/src/application/use_cases.py",
                language="python",
                category="application",
                content="\n".join(use_case_lines),
            ),
            GeneratedFile(
                path="backend/src/adapters/api/main.py",
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
                path="backend/internal/domain/entities.go",
                language="go",
                category="domain",
                content="\n".join(domain_lines),
            ),
            GeneratedFile(
                path="backend/internal/application/usecases.go",
                language="go",
                category="application",
                content=usecase_go,
            ),
            GeneratedFile(
                path="backend/cmd/api/main.go",
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
                path="backend/src/domain/entities.ts",
                language="typescript",
                category="domain",
                content="\n".join(entity_lines),
            ),
            GeneratedFile(
                path="backend/package.json",
                language="json",
                category="infrastructure",
                content=json.dumps(
                    {
                        "name": f"{ir.project_name.lower()}-backend",
                        "version": "1.0.0",
                        "scripts": {"start": "node dist/main.js"},
                    },
                    indent=2,
                ),
            ),
        ]


scaffolder_engine = ScaffolderEngine()
