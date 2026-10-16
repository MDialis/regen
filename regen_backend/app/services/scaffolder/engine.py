import re
import io
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Callable, List, Optional
from pydantic import BaseModel, Field

from app.domain.ir_schema import (
    DataTypePrimitive,
    EntityDefinition,
    ProjectIR,
    TargetFrontend,
    TargetLanguage,
)
from app.services.strangler.test_generator import strangler_generator

IGNORE_DIRS = {
    "node_modules",
    ".git",
    ".next",
    "dist",
    "build",
    "target",
    "bin",
    "obj",
    "__pycache__",
    ".venv",
    "venv",
}

IGNORE_EXTENSIONS = {".pyc", ".exe", ".dll", ".so", ".dylib", ".lock"}


class GeneratedFile(BaseModel):
    path: str = Field(
        ..., description="Relative file path inside the Kick-Starter repo"
    )
    language: str = Field(..., description="Syntax highlighting hint")
    category: str = Field(..., description="File architectural layer")
    content: str


class ScaffoldManifest(BaseModel):
    project_id: str
    project_name: str
    chosen_stack: TargetLanguage
    chosen_frontend: TargetFrontend
    chosen_pattern: str
    cli_commands_executed: List[str] = Field(default_factory=list)
    total_files_generated: int
    files: List[GeneratedFile]


ProgressCallback = Callable[[str, int], None]


class ScaffolderEngine:
    """
    Phase 4 CLI-Driven Scaffolding Engine.
    1. Runs official language/framework CLI initializers in a temporary workspace
       (with --skip-install so configs are always up-to-date without downloading GBs of packages).
    2. Layers REGEN's Hexagonal/Clean Architecture & Componentized Domain UI on top.
    3. Strips ignored directories (.git, node_modules, bin, target) like GitHub.
    4. Packages both a browsable ScaffoldManifest and a pre-built ZIP byte stream.
    """

    _RESERVED_KEYWORDS = {
        "class",
        "struct",
        "interface",
        "enum",
        "record",
        "namespace",
        "using",
        "public",
        "private",
        "protected",
        "internal",
        "static",
        "void",
        "int",
        "string",
        "bool",
        "float",
        "double",
        "decimal",
        "object",
        "event",
        "delegate",
        "params",
        "ref",
        "out",
        "in",
        "is",
        "as",
        "base",
        "this",
        "new",
        "override",
        "virtual",
        "abstract",
        "sealed",
        "readonly",
        "const",
        "try",
        "catch",
        "finally",
        "throw",
        "return",
        "if",
        "else",
        "switch",
        "case",
        "default",
        "for",
        "foreach",
        "while",
        "do",
        "break",
        "continue",
        "goto",
        "lock",
        "checked",
        "unchecked",
        "fixed",
        "unsafe",
        "operator",
        "implicit",
        "explicit",
        "typeof",
        "sizeof",
        "stackalloc",
        "volatile",
        "extern",
        "null",
        "true",
        "false",
        "type",
        "func",
        "package",
        "import",
        "var",
        "let",
        "fn",
        "mut",
        "impl",
        "trait",
        "mod",
        "pub",
        "use",
        "where",
        "match",
        "loop",
        "move",
        "async",
        "await",
        "yield",
        "def",
        "from",
        "pass",
        "global",
        "nonlocal",
        "lambda",
        "with",
        "del",
        "assert",
    }

    @classmethod
    def _sanitize_identifier(
        cls, raw: str, pascal: bool = False, fallback: str = "field"
    ) -> str:
        """
        Strips illegal characters ($, spaces, hyphens, quotes, dots) and escapes
        language reserved keywords so generated C#, Go, Rust, Python, and TS always compile.
        """
        cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", (raw or "").strip())
        tokens = [t for t in cleaned.split("_") if t]
        if not tokens:
            tokens = [fallback]

        if pascal:
            ident = "".join(t[:1].upper() + t[1:] for t in tokens)
        else:
            ident = "_".join(t.lower() for t in tokens)

        if ident[0].isdigit():
            ident = f"{'Entity' if pascal else 'f_'}{ident}"

        if ident.lower() in cls._RESERVED_KEYWORDS:
            ident = f"{ident}{'Entity' if pascal else '_val'}"

        return ident

    def _sanitize_ir_identifiers(self, ir: ProjectIR) -> None:
        """Cleans all Entity and Field names in-place before any code is generated."""
        for idx, ent in enumerate(ir.entities, start=1):
            ent.name = self._sanitize_identifier(
                ent.name, pascal=True, fallback=f"Entity{idx}"
            )
            seen_fields: set[str] = set()
            clean_fields = []
            for f_idx, f in enumerate(ent.fields, start=1):
                f.name = self._sanitize_identifier(
                    f.name, pascal=False, fallback=f"field_{f_idx}"
                )
                if f.name not in seen_fields:
                    seen_fields.add(f.name)
                    clean_fields.append(f)
            ent.fields = clean_fields

    def build_project_and_zip(
        self,
        ir: ProjectIR,
        on_progress: Optional[ProgressCallback] = None,
    ) -> tuple[ScaffoldManifest, bytes]:
        if not ir.is_ready_for_scaffolding or ir.architecture_decision is None:
            raise ValueError(
                "ProjectIR is not ready for scaffolding. Resolve all HITL questions "
                "and run the Stack Advisor first."
            )

        # ====================================================================
        # GLOBAL DEDUPLICATION: Prevent compiler/import errors across all layers
        # ====================================================================

        # Deduplicate Entities by Name
        unique_entities = {e.name: e for e in ir.entities}
        ir.entities = list(unique_entities.values())

        # Sanitize entity and field names across all layers
        self._sanitize_ir_identifiers(ir)

        # Deduplicate Routes by Method + Path (e.g., "GET_/invoices")
        unique_routes = {f"{r.method.value}_{r.path}": r for r in ir.routes}
        ir.routes = list(unique_routes.values())

        # Deduplicate Business Rules by ID
        unique_rules = {r.id: r for r in ir.business_rules}
        ir.business_rules = list(unique_rules.values())

        # ====================================================================

        def report(step_msg: str, pct: int) -> None:
            if on_progress:
                on_progress(step_msg, pct)

        report("Generating Phase 5 Strangler Fig characterization contracts...", 10)
        strangler_generator.populate_contracts(ir)

        arch = ir.architecture_decision
        backend_stack = arch.chosen_backend_language
        frontend_stack = arch.chosen_frontend_stack
        pattern = arch.chosen_pattern.value
        cli_log: List[str] = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            slug = ir.project_name.lower().replace(" ", "_")
            root_dir = Path(tmp_dir) / slug
            root_dir.mkdir(parents=True, exist_ok=True)

            backend_dir = root_dir / "backend"
            backend_dir.mkdir(parents=True, exist_ok=True)

            # ----------------------------------------------------------------
            # STEP 1: Run Official Backend CLI Initializer
            # ----------------------------------------------------------------
            report(
                f"Initializing backend project via `{backend_stack.value}` CLI...", 25
            )
            self._init_backend_via_cli(backend_dir, slug, backend_stack, cli_log)

            # ----------------------------------------------------------------
            # STEP 2: Overlay Hexagonal / Clean Backend Architecture from IR
            # ----------------------------------------------------------------
            report(f"Layering {pattern} domain entities, ports, and HITL rules...", 45)
            self._overlay_backend_architecture(backend_dir, ir, backend_stack)

            # ----------------------------------------------------------------
            # STEP 3: Run Official Frontend CLI Initializer (if enabled)
            # ----------------------------------------------------------------
            if frontend_stack != TargetFrontend.NONE:
                report(
                    f"Bootstrapping frontend via official `{frontend_stack.value}` CLI...",
                    65,
                )
                self._init_frontend_via_cli(root_dir, slug, frontend_stack, cli_log)

                report(
                    f"Injecting componentized domain UI & typed API client into `{frontend_stack.value}`...",
                    80,
                )
                self._overlay_frontend_architecture(
                    root_dir / "frontend", ir, frontend_stack
                )

            # ----------------------------------------------------------------
            # STEP 4: Write Root Container Infrastructure & AI Documentation
            # ----------------------------------------------------------------
            report(
                "Generating Docker Compose, Makefile, AGENTS.md, and Parity Tests...",
                90,
            )
            self._write_root_infrastructure_and_docs(
                root_dir, ir, backend_stack, frontend_stack, cli_log
            )

            # ----------------------------------------------------------------
            # STEP 5: Prune Ignored Folders (node_modules, .git, bin, obj) & Pack ZIP
            # ----------------------------------------------------------------
            report("Pruning build artifacts and compressing ZIP archive...", 95)
            self._prune_ignored_directories(root_dir)
            manifest, zip_bytes = self._package_workspace(
                root_dir, ir, backend_stack, frontend_stack, pattern, cli_log
            )

        report("Kick-Starter ZIP archive ready for instant download!", 100)
        return manifest, zip_bytes

    def generate_manifest(self, ir: ProjectIR) -> ScaffoldManifest:
        manifest, _ = self.build_project_and_zip(ir)
        return manifest

    def build_zip_archive(self, ir: ProjectIR) -> bytes:
        _, zip_bytes = self.build_project_and_zip(ir)
        return zip_bytes

    # ========================================================================
    # CLI EXECUTION HELPER (SAFE, NON-INTERACTIVE, TIMEOUT-BOUNDED)
    # ========================================================================

    def _run_cli(
        self, cmd: List[str], cwd: Path, cli_log: List[str], timeout_sec: int = 35
    ) -> bool:
        """
        Executes a native CLI command with stdin=DEVNULL so interactive CLIs
        (like create-vite / clack prompts) never hang waiting for user input.
        """
        cmd_str = " ".join(cmd)
        env = {
            **os.environ,
            "CI": "true",
            "NEXT_TELEMETRY_DISABLED": "1",
            " npm_config_yes": "true",
            "NPM_CONFIG_YES": "true",
        }
        use_shell = os.name == "nt"
        try:
            proc = subprocess.run(
                cmd_str if use_shell else cmd,
                cwd=str(cwd),
                env=env,
                stdin=subprocess.DEVNULL,  # <-- CRITICAL: Prevents interactive CLI hangs!
                shell=use_shell,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
            if (
                proc.returncode == 0
                and (cwd / "frontend").exists()
                or proc.returncode == 0
            ):
                cli_log.append(f"[OK] {cmd_str}")
                return True
            cli_log.append(
                f"[WARN: exit {proc.returncode}] {cmd_str} -> {(proc.stderr or proc.stdout)[:160].strip()}"
            )
            return False
        except subprocess.TimeoutExpired:
            cli_log.append(
                f"[TIMEOUT after {timeout_sec}s - using fast fallback] {cmd_str}"
            )
            return False
        except Exception as exc:
            cli_log.append(f"[SKIPPED - CLI error] {cmd_str} ({exc})")
            return False

    # ========================================================================
    # BACKEND CLI INITIALIZERS + HEXAGONAL OVERLAY
    # ========================================================================

    def _init_backend_via_cli(
        self,
        backend_dir: Path,
        slug: str,
        stack: TargetLanguage,
        cli_log: List[str],
    ) -> None:
        if stack == TargetLanguage.GO_FIBER_OR_CHI:
            ok = self._run_cli(["go", "mod", "init", slug], backend_dir, cli_log)
            if not ok:
                (backend_dir / "go.mod").write_text(
                    f"module {slug}\n\ngo 1.23\n", encoding="utf-8"
                )

        elif stack == TargetLanguage.TYPESCRIPT_NEST_OR_NODE:
            self._run_cli(
                ["npm", "cache", "clean", "--force"],
                backend_dir,
                cli_log,
                timeout_sec=20,
            )

            ok = self._run_cli(["npm", "init", "-y"], backend_dir, cli_log)
            pkg_path = backend_dir / "package.json"
            pkg_data = (
                json.loads(pkg_path.read_text(encoding="utf-8"))
                if pkg_path.exists()
                else {"name": f"{slug}-backend", "version": "1.0.0"}
            )
            pkg_data["scripts"] = {
                "dev": "tsx watch src/adapters/api/server.ts",
                "start": "tsx src/adapters/api/server.ts",
            }
            pkg_data["devDependencies"] = {
                "typescript": "^5.7.0",
                "tsx": "^4.19.0",
                "@types/node": "^22.0.0",
            }
            pkg_path.write_text(json.dumps(pkg_data, indent=2), encoding="utf-8")
            self._run_cli(["npx", "--yes", "tsc", "--init"], backend_dir, cli_log)

        elif stack == TargetLanguage.RUST_AXUM:
            ok = self._run_cli(
                ["cargo", "init", "--bin", "--name", slug.replace("_", "-")],
                backend_dir,
                cli_log,
            )
            if not ok:
                (backend_dir / "Cargo.toml").write_text(
                    f'[package]\nname = "{slug.replace("_", "-")}"\nversion = "0.1.0"\nedition = "2021"\n\n'
                    '[dependencies]\naxum = "0.7"\ntokio = { version = "1", features = ["full"] }\n'
                    'serde = { version = "1", features = ["derive"] }\nserde_json = "1"\n',
                    encoding="utf-8",
                )

        elif stack == TargetLanguage.CSHARP_DOTNET:
            ok = self._run_cli(
                [
                    "dotnet",
                    "new",
                    "webapi",
                    "-n",
                    "KickStarterApi",
                    "-o",
                    ".",
                    "--no-restore",
                ],
                backend_dir,
                cli_log,
            )
            if not ok:
                (backend_dir / "KickStarterApi.csproj").write_text(
                    '<Project Sdk="Microsoft.NET.Sdk.Web">\n'
                    "  <PropertyGroup>\n"
                    "    <TargetFramework>net8.0</TargetFramework>\n"
                    "    <Nullable>enable</Nullable>\n"
                    "    <ImplicitUsings>enable</ImplicitUsings>\n"
                    "  </PropertyGroup>\n"
                    "</Project>\n",
                    encoding="utf-8",
                )

        else:
            # Python FastAPI: Create modern PEP-621 pyproject.toml + requirements.txt
            (backend_dir / "pyproject.toml").write_text(
                f'[project]\nname = "{slug}-backend"\nversion = "0.1.0"\n'
                'requires-python = ">=3.12"\n'
                'dependencies = ["fastapi>=0.115.0", "uvicorn[standard]>=0.30.6", "pydantic>=2.10.0", "httpx>=0.27.2", "pytest>=8.3.0"]\n',
                encoding="utf-8",
            )
            (backend_dir / "requirements.txt").write_text(
                "fastapi>=0.115.0\nuvicorn[standard]>=0.30.6\npydantic>=2.10.0\nhttpx>=0.27.2\npytest>=8.3.0\n",
                encoding="utf-8",
            )
            cli_log.append("[OK] Initialized PEP-621 pyproject.toml for Python FastAPI")

    def _overlay_backend_architecture(
        self, backend_dir: Path, ir: ProjectIR, stack: TargetLanguage
    ) -> None:
        entities = ir.entities or [
            EntityDefinition(name="SampleItem", description="Default entity", fields=[])
        ]

        if stack == TargetLanguage.GO_FIBER_OR_CHI:
            self._write_go_layers(backend_dir, ir, entities)
        elif stack == TargetLanguage.TYPESCRIPT_NEST_OR_NODE:
            self._write_ts_backend_layers(backend_dir, ir, entities)
        elif stack == TargetLanguage.RUST_AXUM:
            self._write_rust_layers(backend_dir, ir, entities)
        elif stack == TargetLanguage.CSHARP_DOTNET:
            self._write_csharp_layers(backend_dir, ir, entities)
        else:
            self._write_python_layers(backend_dir, ir, entities)

        # Always add Phase 5 Strangler Fig Parity Test Suite
        tests_dir = backend_dir / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_strangler_parity.py").write_text(
            strangler_generator.render_parity_test_file(ir), encoding="utf-8"
        )

    # ========================================================================
    # FRONTEND CLI INITIALIZERS (NEXT.JS, REACT+VITE, VUE+VITE, SVELTEKIT, ANGULAR)
    # ========================================================================

    def _init_frontend_via_cli(
        self,
        root_dir: Path,
        slug: str,
        fe_stack: TargetFrontend,
        cli_log: List[str],
    ) -> None:
        fe_dir = root_dir / "frontend"

        if fe_stack == TargetFrontend.NEXTJS:
            ok = self._run_cli(
                [
                    "npx",
                    "--yes",
                    "create-next-app@latest",
                    "frontend",
                    "--ts",
                    "--tailwind",
                    "--app",
                    "--src-dir",
                    "--import-alias",
                    "@/*",
                    "--use-npm",
                    "--skip-install",
                    "--yes",
                ],
                root_dir,
                cli_log,
                timeout_sec=45,
            )
            if not ok or not (fe_dir / "package.json").exists():
                self._write_fallback_nextjs_base(fe_dir, slug)

        elif fe_stack == TargetFrontend.REACT_VITE:
            ok = self._run_cli(
                [
                    "npx",
                    "--yes",
                    "create-vite@latest",
                    "frontend",
                    "--template",
                    "react-ts",
                    "--no-interactive",
                ],
                root_dir,
                cli_log,
                timeout_sec=20,
            )
            if not ok or not (fe_dir / "package.json").exists():
                self._write_fallback_vite_base(fe_dir, slug, "react")

        elif fe_stack == TargetFrontend.VUE_VITE:
            ok = self._run_cli(
                [
                    "npx",
                    "--yes",
                    "create-vite@latest",
                    "frontend",
                    "--template",
                    "vue-ts",
                    "--no-interactive",
                ],
                root_dir,
                cli_log,
                timeout_sec=20,
            )
            if not ok or not (fe_dir / "package.json").exists():
                self._write_fallback_vite_base(fe_dir, slug, "vue")

        elif fe_stack == TargetFrontend.SVELTEKIT:
            ok = self._run_cli(
                [
                    "npx",
                    "--yes",
                    "sv",
                    "create",
                    "frontend",
                    "--template",
                    "minimal",
                    "--types",
                    "ts",
                    "--no-install",
                    "--no-add-ons",
                ],
                root_dir,
                cli_log,
                timeout_sec=25,
            )
            if not ok or not (fe_dir / "package.json").exists():
                self._write_fallback_vite_base(fe_dir, slug, "sveltekit")

        elif fe_stack == TargetFrontend.ANGULAR:
            ok = self._run_cli(
                [
                    "npx",
                    "--yes",
                    "@angular/cli@latest",
                    "new",
                    "frontend",
                    "--skip-install",
                    "--skip-git",
                    "--defaults",
                    "--style=css",
                    "--routing=true",
                ],
                root_dir,
                cli_log,
                timeout_sec=45,
            )
            if not ok or not (fe_dir / "package.json").exists():
                self._write_fallback_vite_base(fe_dir, slug, "angular")

    def _overlay_frontend_architecture(
        self, fe_dir: Path, ir: ProjectIR, fe_stack: TargetFrontend
    ) -> None:
        """
        Injects modular, high-cohesion Domain Types, API Service Client,
        and per-Entity UI components into whichever frontend framework was chosen.
        """
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
        entities = ir.entities or [
            EntityDefinition(name="SampleItem", description="Default entity", fields=[])
        ]

        src_dir = fe_dir / "src"
        types_dir = src_dir / "types"
        services_dir = src_dir / "services"
        types_dir.mkdir(parents=True, exist_ok=True)
        services_dir.mkdir(parents=True, exist_ok=True)

        # 1. Universal TypeScript Domain Contracts (`src/types/domain.ts`)
        type_lines = ["// Auto-generated by REGEN from ProjectIR Entities.\n"]
        for ent in entities:
            type_lines.append(f"export interface {ent.name} {{")
            if not ent.fields:
                type_lines.append("  id: number;")
            for f in ent.fields:
                ts_t = ts_type_map.get(f.data_type, "string")
                opt = "" if f.is_required else "?"
                type_lines.append(f"  {f.name}{opt}: {ts_t};")
            type_lines.append("}\n")
        (types_dir / "domain.ts").write_text("\n".join(type_lines), encoding="utf-8")

        # 2. Universal Typed API Client (`src/services/apiClient.ts`)
        entity_imports = ", ".join(ent.name for ent in entities)
        api_lines = [
            f'import type {{ {entity_imports} }} from "../types/domain";',
            "",
            'const API_BASE_URL = "http://localhost:8000";',
            "",
            "async function request<T>(path: string, options?: RequestInit): Promise<T> {",
            "  const response = await fetch(`${API_BASE_URL}${path}`, {",
            '    headers: { "Content-Type": "application/json" },',
            "    ...options,",
            "  });",
            "  if (!response.ok) throw new Error(`API Error ${response.status}`);",
            "  return response.json() as Promise<T>;",
            "}",
            "",
            "export const apiClient = {",
            '  checkHealth: () => request<{ status: string }>("/health"),',
        ]
        for ent in entities:
            api_lines.append(
                f'  list{ent.name}s: () => request<{ent.name}[]>("/{ent.name.lower()}s"),'
            )
        api_lines.append("};\n")
        (services_dir / "apiClient.ts").write_text(
            "\n".join(api_lines), encoding="utf-8"
        )

        # 3. Framework-Specific Componentized Domain Views
        if fe_stack in (TargetFrontend.NEXTJS, TargetFrontend.REACT_VITE):
            comp_dir = src_dir / "components" / "domain"
            layout_dir = src_dir / "components" / "layout"
            comp_dir.mkdir(parents=True, exist_ok=True)
            layout_dir.mkdir(parents=True, exist_ok=True)

            (layout_dir / "AppShell.tsx").write_text(
                self._render_react_app_shell(), encoding="utf-8"
            )
            for ent in entities:
                (comp_dir / f"{ent.name}Table.tsx").write_text(
                    self._render_react_entity_table(ent), encoding="utf-8"
                )
                (comp_dir / f"{ent.name}Card.tsx").write_text(
                    self._render_react_entity_card(ent), encoding="utf-8"
                )

            if fe_stack == TargetFrontend.NEXTJS:
                app_dir = src_dir / "app"
                app_dir.mkdir(parents=True, exist_ok=True)
                (app_dir / "page.tsx").write_text(
                    self._render_react_dashboard_page(ir.project_name, entities),
                    encoding="utf-8",
                )
            else:
                (src_dir / "App.tsx").write_text(
                    self._render_react_dashboard_page(
                        ir.project_name, entities, is_vite=True
                    ),
                    encoding="utf-8",
                )

        elif fe_stack == TargetFrontend.VUE_VITE:
            comp_dir = src_dir / "components" / "domain"
            comp_dir.mkdir(parents=True, exist_ok=True)
            for ent in entities:
                (comp_dir / f"{ent.name}Table.vue").write_text(
                    self._render_vue_entity_table(ent), encoding="utf-8"
                )

    # ========================================================================
    # BACKEND LAYER WRITERS
    # ========================================================================

    def _write_python_layers(
        self, backend_dir: Path, ir: ProjectIR, entities: List[EntityDefinition]
    ) -> None:
        src = backend_dir / "src"
        for sub in ("domain", "ports", "application", "adapters/db", "adapters/api"):
            d = src / sub
            d.mkdir(parents=True, exist_ok=True)
            (d / "__init__.py").write_text("", encoding="utf-8")
        (src / "__init__.py").write_text("", encoding="utf-8")

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

        ent_lines = [
            "from typing import Optional",
            "from pydantic import BaseModel",
            "",
        ]
        port_lines = [
            "from abc import ABC, abstractmethod",
            "from typing import List",
            "from src.domain.entities import *",
            "",
        ]
        repo_lines = [
            "from typing import List",
            "from src.domain.entities import *",
            "from src.ports.repositories import *",
            "",
        ]

        for ent in entities:
            ent_lines.append(f"class {ent.name}(BaseModel):")
            ent_lines.append(f'    """{ent.description}"""')
            if not ent.fields:
                ent_lines.append("    id: int")
            for f in ent.fields:
                py_t = py_type_map.get(f.data_type, "str")
                ent_lines.append(
                    f"    {f.name}: {py_t}"
                    if f.is_required
                    else f"    {f.name}: Optional[{py_t}] = None"
                )
            ent_lines.append("")

            port_lines.extend(
                [
                    f"class {ent.name}RepositoryPort(ABC):",
                    "    @abstractmethod",
                    f"    def list_all(self) -> List[{ent.name}]: ...",
                    "",
                ]
            )
            repo_lines.extend(
                [
                    f"class InMemory{ent.name}Repository({ent.name}RepositoryPort):",
                    "    def __init__(self) -> None:",
                    f"        self._items: List[{ent.name}] = []",
                    f"    def list_all(self) -> List[{ent.name}]:",
                    "        return self._items",
                    "",
                ]
            )

        uc_lines = [
            "from typing import Any, Dict",
            "",
            "class DomainRuleEngine:",
        ]
        if not ir.business_rules:
            uc_lines.append("    pass")
        for idx, rule in enumerate(ir.business_rules, start=1):
            uc_lines.extend(
                [
                    f"    def enforce_rule_{idx}_{rule.id}(self, context: Dict[str, Any]) -> Dict[str, Any]:",
                    f'        """{rule.title}: {rule.expected_behavior}"""',
                    f'        return {{"rule_id": "{rule.id}", "enforced": True, "context": context}}',
                    "",
                ]
            )

        api_lines = [
            "from fastapi import FastAPI",
            "from fastapi.middleware.cors import CORSMiddleware",
            "from src.domain.entities import *",
            "from src.application.use_cases import DomainRuleEngine",
            "",
            f'app = FastAPI(title="{ir.project_name} API")',
            'app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])',
            "rule_engine = DomainRuleEngine()",
            "",
            '@app.get("/health")',
            "def health():",
            f'    return {{"status": "ok", "project": "{ir.project_name}"}}',
            "",
        ]
        for route in ir.routes:
            m = route.method.value.lower()
            fn = (
                route.path.strip("/")
                .replace("/", "_")
                .replace("{", "")
                .replace("}", "")
                or "root"
            )
            api_lines.extend(
                [
                    f'@app.{m}("{route.path}")',
                    f"def handle_{m}_{fn}():",
                    f'    """{route.summary}"""',
                    "    return []",
                    "",
                ]
            )

        (src / "domain/entities.py").write_text("\n".join(ent_lines), encoding="utf-8")
        (src / "ports/repositories.py").write_text(
            "\n".join(port_lines), encoding="utf-8"
        )
        (src / "application/use_cases.py").write_text(
            "\n".join(uc_lines), encoding="utf-8"
        )
        (src / "adapters/db/repositories.py").write_text(
            "\n".join(repo_lines), encoding="utf-8"
        )
        (src / "adapters/api/main.py").write_text(
            "\n".join(api_lines), encoding="utf-8"
        )

    def _write_go_layers(
        self, backend_dir: Path, ir: ProjectIR, entities: List[EntityDefinition]
    ) -> None:
        for sub in (
            "internal/domain",
            "internal/ports",
            "internal/application",
            "cmd/api",
        ):
            (backend_dir / sub).mkdir(parents=True, exist_ok=True)

        go_type_map = {
            DataTypePrimitive.STRING: "string",
            DataTypePrimitive.INTEGER: "int64",
            DataTypePrimitive.FLOAT: "float64",
            DataTypePrimitive.DECIMAL: "float64",
            DataTypePrimitive.BOOLEAN: "bool",
        }
        dom = ["package domain\n"]
        for ent in entities:
            dom.append(f"type {ent.name} struct {{")
            for f in ent.fields:
                go_t = go_type_map.get(f.data_type, "string")
                pascal = "".join(w.capitalize() for w in f.name.split("_"))
                dom.append(f'\t{pascal} {go_t} `json:"{f.name}"`')
            dom.append("}\n")
        (backend_dir / "internal/domain/entities.go").write_text(
            "\n".join(dom), encoding="utf-8"
        )

        rules_comments = "\n".join(
            f"// Rule [{r.id}]: {r.title} -> {r.expected_behavior}"
            for r in ir.business_rules
        )
        (backend_dir / "internal/application/usecases.go").write_text(
            f"package application\n\n{rules_comments}\n\ntype RuleEngine struct{{}}\n",
            encoding="utf-8",
        )

        main_go = (
            'package main\n\nimport (\n\t"encoding/json"\n\t"log"\n\t"net/http"\n)\n\n'
            "func main() {\n"
            '\thttp.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {\n'
            '\t\tw.Header().Set("Content-Type", "application/json")\n'
            f'\t\tjson.NewEncoder(w).Encode(map[string]string{{"status": "ok", "project": "{ir.project_name}"}})\n'
            "\t})\n"
            '\tlog.Println("Go Hexagonal Server listening on :8000")\n'
            '\tlog.Fatal(http.ListenAndServe(":8000", nil))\n}\n'
        )
        (backend_dir / "cmd/api/main.go").write_text(main_go, encoding="utf-8")

    def _write_ts_backend_layers(
        self, backend_dir: Path, ir: ProjectIR, entities: List[EntityDefinition]
    ) -> None:
        for sub in ("src/domain", "src/ports", "src/application", "src/adapters/api"):
            (backend_dir / sub).mkdir(parents=True, exist_ok=True)

        ent_lines = ["// Strict Hexagonal Domain Entities\n"]
        for ent in entities:
            ent_lines.append(f"export interface {ent.name} {{")
            for f in ent.fields:
                ent_lines.append(f"  {f.name}: string | number | boolean;")
            ent_lines.append("}\n")
        (backend_dir / "src/domain/entities.ts").write_text(
            "\n".join(ent_lines), encoding="utf-8"
        )

        server_ts = (
            'import http from "node:http";\n\n'
            "const server = http.createServer((req, res) => {\n"
            '  res.setHeader("Content-Type", "application/json");\n'
            f'  res.end(JSON.stringify({{ status: "ok", project: "{ir.project_name}" }}));\n'
            "});\n"
            'server.listen(8000, () => console.log("TS Hexagonal Server on :8000"));\n'
        )
        (backend_dir / "src/adapters/api/server.ts").write_text(
            server_ts, encoding="utf-8"
        )

    def _write_rust_layers(
        self, backend_dir: Path, ir: ProjectIR, entities: List[EntityDefinition]
    ) -> None:
        src = backend_dir / "src"
        src.mkdir(parents=True, exist_ok=True)
        ent_lines = ["use serde::{Serialize, Deserialize};\n"]
        for ent in entities:
            ent_lines.append("#[derive(Debug, Clone, Serialize, Deserialize)]")
            ent_lines.append(f"pub struct {ent.name} {{")
            for f in ent.fields:
                ent_lines.append(f"    pub {f.name}: String,")
            ent_lines.append("}\n")
        (src / "domain.rs").write_text("\n".join(ent_lines), encoding="utf-8")

    def _write_csharp_layers(
        self, backend_dir: Path, ir: ProjectIR, entities: List[EntityDefinition]
    ) -> None:
        dom = backend_dir / "Domain"
        dom.mkdir(parents=True, exist_ok=True)
        cs_type_map = {
            DataTypePrimitive.STRING: "string",
            DataTypePrimitive.INTEGER: "long",
            DataTypePrimitive.FLOAT: "double",
            DataTypePrimitive.DECIMAL: "decimal",
            DataTypePrimitive.BOOLEAN: "bool",
            DataTypePrimitive.DATETIME: "DateTime",
            DataTypePrimitive.UUID: "Guid",
            DataTypePrimitive.JSON: "object",
        }
        lines = ["using System;\n\nnamespace KickStarterApi.Domain;\n"]
        for ent in entities:
            safe_ent_name = self._sanitize_identifier(
                ent.name, pascal=True, fallback="DomainEntity"
            )
            props = []
            for idx, f in enumerate(ent.fields, start=1):
                cs_t = cs_type_map.get(f.data_type, "string")
                prop_name = self._sanitize_identifier(
                    f.name, pascal=True, fallback=f"Field{idx}"
                )
                if prop_name == safe_ent_name:
                    prop_name = f"{prop_name}Value"
                props.append(f"{cs_t} {prop_name}")
            fields_cs = ", ".join(props) or "long Id"
            lines.append(f"public record {safe_ent_name}({fields_cs});\n")
        (dom / "Entities.cs").write_text("\n".join(lines), encoding="utf-8")

    # ========================================================================
    # FRONTEND COMPONENT TEMPLATES & FALLBACKS
    # ========================================================================

    def _write_fallback_nextjs_base(self, fe_dir: Path, slug: str) -> None:
        (fe_dir / "src/app").mkdir(parents=True, exist_ok=True)
        pkg = {
            "name": f"{slug}-frontend",
            "version": "0.1.0",
            "private": True,
            "scripts": {
                "dev": "next dev",
                "build": "next build",
                "start": "next start",
            },
            "dependencies": {
                "next": "^15.1.0",
                "react": "^19.0.0",
                "react-dom": "^19.0.0",
            },
            "devDependencies": {
                "typescript": "^5",
                "@types/react": "^19",
                "tailwindcss": "^4",
                "@tailwindcss/postcss": "^4",
            },
        }
        (fe_dir / "package.json").write_text(
            json.dumps(pkg, indent=2), encoding="utf-8"
        )
        (fe_dir / "src/app/globals.css").write_text(
            '@import "tailwindcss";\n', encoding="utf-8"
        )
        (fe_dir / "src/app/layout.tsx").write_text(
            'import "./globals.css";\nexport default function RootLayout({ children }: { children: React.ReactNode }) {\n'
            '  return <html lang="en"><body className="bg-slate-950 text-slate-100">{children}</body></html>;\n}\n',
            encoding="utf-8",
        )

    def _write_fallback_vite_base(
        self, fe_dir: Path, slug: str, framework: str
    ) -> None:
        (fe_dir / "src").mkdir(parents=True, exist_ok=True)
        pkg = {
            "name": f"{slug}-{framework}",
            "version": "0.1.0",
            "private": True,
            "scripts": {"dev": "vite", "build": "vite build"},
        }
        (fe_dir / "package.json").write_text(
            json.dumps(pkg, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _render_react_app_shell() -> str:
        return (
            'import React from "react";\n\n'
            "export function AppShell({ title, children }: { title: string; children: React.ReactNode }) {\n"
            "  return (\n"
            '    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">\n'
            '      <header className="border-b border-slate-800 bg-slate-900 px-6 py-4 flex justify-between items-center">\n'
            '        <h1 className="text-lg font-bold text-emerald-400">{title}</h1>\n'
            '        <span className="text-xs font-mono text-slate-400">Generated by REGEN</span>\n'
            "      </header>\n"
            '      <main className="flex-1 max-w-6xl w-full mx-auto p-6 space-y-6">{children}</main>\n'
            "    </div>\n"
            "  );\n"
            "}\n"
        )

    @staticmethod
    def _render_react_entity_table(ent: EntityDefinition) -> str:
        headers = (
            "\n              ".join(
                f'<th className="px-4 py-2 text-left text-xs text-slate-400">{f.name}</th>'
                for f in ent.fields
            )
            or '<th className="px-4 py-2">ID</th>'
        )
        cells = (
            "\n                ".join(
                f'<td className="px-4 py-2 text-sm font-mono">{{String(item.{f.name})}}</td>'
                for f in ent.fields
            )
            or '<td className="px-4 py-2">{item.id}</td>'
        )

        return (
            'import React from "react";\n'
            f'import type {{ {ent.name} }} from "../../types/domain";\n\n'
            f"export function {ent.name}Table({{ items }}: {{ items: {ent.name}[] }}) {{\n"
            "  return (\n"
            '    <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden">\n'
            '      <div className="px-4 py-3 border-b border-slate-800 flex justify-between">\n'
            f'        <h2 className="text-sm font-semibold">{ent.name} Records</h2>\n'
            '        <span className="text-xs text-slate-400">{items.length} items</span>\n'
            "      </div>\n"
            '      <table className="w-full border-collapse">\n'
            "        <thead><tr>\n"
            f"              {headers}\n"
            "        </tr></thead>\n"
            "        <tbody>\n"
            "          {items.map((item, idx) => (\n"
            '            <tr key={idx} className="border-t border-slate-800">\n'
            f"                {cells}\n"
            "            </tr>\n"
            "          ))}\n"
            "        </tbody>\n"
            "      </table>\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        )

    @staticmethod
    def _render_react_entity_card(ent: EntityDefinition) -> str:
        rows = "\n        ".join(
            f'<div className="flex justify-between text-xs"><span className="text-slate-400">{f.name}</span><span>{{String(data.{f.name})}}</span></div>'
            for f in ent.fields
        )
        return (
            'import React from "react";\n'
            f'import type {{ {ent.name} }} from "../../types/domain";\n\n'
            f"export function {ent.name}Card({{ data }}: {{ data: {ent.name} }}) {{\n"
            "  return (\n"
            '    <div className="p-4 rounded-xl border border-slate-800 bg-slate-900 space-y-2">\n'
            f'      <h3 className="text-sm font-bold text-emerald-400">{ent.name}</h3>\n'
            f'      <div className="space-y-1">{rows}</div>\n'
            "    </div>\n"
            "  );\n"
            "}\n"
        )

    @staticmethod
    def _render_react_dashboard_page(
        project_name: str, entities: List[EntityDefinition], is_vite: bool = False
    ) -> str:
        rel_prefix = "./components" if is_vite else "../components"
        imports = "\n".join(
            f'import {{ {e.name}Table }} from "{rel_prefix}/domain/{e.name}Table";'
            for e in entities
        )
        mounts = "\n        ".join(f"<{e.name}Table items={{[]}} />" for e in entities)
        return (
            'import React from "react";\n'
            f'import {{ AppShell }} from "{rel_prefix}/layout/AppShell";\n'
            f"{imports}\n\n"
            "export default function DashboardPage() {\n"
            "  return (\n"
            f'    <AppShell title="{project_name} Workspace">\n'
            '      <section className="space-y-6">\n'
            f"        {mounts}\n"
            "      </section>\n"
            "    </AppShell>\n"
            "  );\n"
            "}\n"
        )

    @staticmethod
    def _render_vue_entity_table(ent: EntityDefinition) -> str:
        return (
            '<script setup lang="ts">\n'
            f'import type {{ {ent.name} }} from "../../types/domain";\n'
            f"defineProps<{{ items: {ent.name}[] }}>();\n"
            "</script>\n\n"
            "<template>\n"
            '  <div class="domain-table">\n'
            f"    <h2>{ent.name} ({{ items.length }})</h2>\n"
            "  </div>\n"
            "</template>\n"
        )

    # ========================================================================
    # ROOT INFRASTRUCTURE, PRUNING & ZIP PACKAGING
    # ========================================================================

    def _write_root_infrastructure_and_docs(
        self,
        root_dir: Path,
        ir: ProjectIR,
        backend_stack: TargetLanguage,
        frontend_stack: TargetFrontend,
        cli_log: List[str],
    ) -> None:
        # Backend Dockerfile
        backend_dir = root_dir / "backend"
        slug = root_dir.name.replace("_", "-")

        if backend_stack == TargetLanguage.GO_FIBER_OR_CHI:
            b_docker = (
                "FROM golang:alpine AS builder\nWORKDIR /app\nCOPY . .\n"
                "RUN go build -o server ./cmd/api/main.go\n"
                "FROM alpine:latest\nWORKDIR /app\nCOPY --from=builder /app/server .\n"
                'EXPOSE 8000\nCMD ["./server"]\n'
            )
        elif backend_stack == TargetLanguage.TYPESCRIPT_NEST_OR_NODE:
            b_docker = (
                "FROM node:alpine\nWORKDIR /app\nCOPY package*.json ./\n"
                "RUN npm install\nCOPY . .\nEXPOSE 8000\n"
                'CMD ["npm", "start"]\n'
            )
        elif backend_stack == TargetLanguage.CSHARP_DOTNET:
            b_docker = (
                "FROM mcr.microsoft.com/dotnet/sdk:8.0 AS builder\nWORKDIR /app\nCOPY . .\n"
                "RUN dotnet publish -c Release -o out\n"
                "FROM mcr.microsoft.com/dotnet/aspnet:8.0\nWORKDIR /app\n"
                "COPY --from=builder /app/out .\nEXPOSE 8000\n"
                "ENV ASPNETCORE_URLS=http://+:8000\n"
                'CMD ["dotnet", "KickStarterApi.dll"]\n'
            )
        elif backend_stack == TargetLanguage.RUST_AXUM:
            b_docker = (
                "FROM rust:alpine AS builder\nWORKDIR /app\nCOPY . .\n"
                "RUN apk add --no-cache musl-dev && cargo build --release\n"
                "FROM alpine:latest\nWORKDIR /app\n"
                f"COPY --from=builder /app/target/release/{slug} ./server\n"
                'EXPOSE 8000\nCMD ["./server"]\n'
            )
        else:
            # Python FastAPI
            b_docker = (
                "FROM python:slim\nWORKDIR /app\nCOPY requirements.txt .\n"
                "RUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\n"
                'EXPOSE 8000\nCMD ["uvicorn", "src.adapters.api.main:app", "--host", "0.0.0.0", "--port", "8000"]\n'
            )

        (backend_dir / ".dockerignore").write_text(
            "node_modules\nbin\nobj\ntarget\n__pycache__\n.venv\n.git\n",
            encoding="utf-8",
        )

        fe_compose_block = ""
        if frontend_stack != TargetFrontend.NONE:
            fe_dir = root_dir / "frontend"
            fe_dir.mkdir(parents=True, exist_ok=True)
            (root_dir / "frontend" / ".dockerignore").write_text(
                "node_modules\n.next\ndist\n.git\n",
                encoding="utf-8",
            )
            (fe_dir / "Dockerfile").write_text(
                "FROM node:alpine\nWORKDIR /app\nCOPY package*.json ./\n"
                'RUN npm install\nCOPY . .\nEXPOSE 3000\nCMD ["npm", "run", "dev"]\n',
                encoding="utf-8",
            )
            fe_compose_block = (
                "  frontend:\n"
                "    build: ./frontend\n"
                '    ports:\n      - "3000:3000"\n'
                "    environment:\n      - NEXT_PUBLIC_API_URL=http://localhost:8000\n"
                "    depends_on:\n      - backend\n\n"
            )

        compose = (
            "services:\n"
            "  backend:\n"
            "    build: ./backend\n"
            '    ports:\n      - "8000:8000"\n'
            "    environment:\n      - DATABASE_URL=postgresql://postgres:postgres@db:5432/kickstarter\n"
            "    depends_on:\n      db:\n        condition: service_healthy\n\n"
            f"{fe_compose_block}"
            "  db:\n"
            "    image: postgres:alpine\n"
            "    environment:\n"
            "      - POSTGRES_USER=postgres\n"
            "      - POSTGRES_PASSWORD=postgres\n"
            "      - POSTGRES_DB=kickstarter\n"
            '    ports:\n      - "5432:5432"\n'
            "    healthcheck:\n"
            '      test: ["CMD-SHELL", "pg_isready -U postgres"]\n'
            "      interval: 5s\n      timeout: 5s\n      retries: 5\n"
        )
        (root_dir / "docker-compose.yml").write_text(compose, encoding="utf-8")
        (root_dir / ".gitignore").write_text(
            "node_modules/\n.next/\ndist/\ntarget/\nbin/\nobj/\n__pycache__/\n.venv/\n.env\n",
            encoding="utf-8",
        )

        cli_summary = "\n".join(f"- `{entry}`" for entry in cli_log)
        rules_summary = "\n".join(
            f"- **{r.title}** (`{r.id}`): {r.expected_behavior}"
            for r in ir.business_rules
        )
        (root_dir / "AGENTS.md").write_text(
            f"# {ir.project_name} — AI Agent Guide (AGENTS.md)\n\n"
            f"## 1. Selected Stack\n"
            f"- **Backend:** `{backend_stack.value}`\n"
            f"- **Frontend:** `{frontend_stack.value}`\n\n"
            f"## 2. CLI Bootstrapper Log\n{cli_summary}\n\n"
            f"## 3. HITL-Verified Domain Rules\n{rules_summary or '- None'}\n",
            encoding="utf-8",
        )
        (root_dir / "regen_blueprint.ir.json").write_text(
            json.dumps(ir.model_dump(mode="json"), indent=2), encoding="utf-8"
        )

    def _prune_ignored_directories(self, root_dir: Path) -> None:
        """Removes heavy dependency/VCS folders (.git, node_modules, target, bin, obj) just like GitHub."""
        for dirpath, dirnames, _ in os.walk(root_dir, topdown=True):
            for d in list(dirnames):
                if d in IGNORE_DIRS:
                    shutil.rmtree(Path(dirpath) / d, ignore_errors=True)
                    dirnames.remove(d)

    def _package_workspace(
        self,
        root_dir: Path,
        ir: ProjectIR,
        backend_stack: TargetLanguage,
        frontend_stack: TargetFrontend,
        pattern: str,
        cli_log: List[str],
    ) -> tuple[ScaffoldManifest, bytes]:
        files_list: List[GeneratedFile] = []
        zip_buffer = io.BytesIO()
        slug = root_dir.name

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(root_dir.rglob("*")):
                if not file_path.is_file():
                    continue
                if file_path.suffix.lower() in IGNORE_EXTENSIONS:
                    continue

                rel_path = file_path.relative_to(root_dir).as_posix()
                zf.write(file_path, f"{slug}/{rel_path}")

                # Read text files (<= 150 KB) into the frontend preview manifest
                try:
                    if file_path.stat().st_size <= 150_000:
                        content = file_path.read_text(encoding="utf-8")
                        files_list.append(
                            GeneratedFile(
                                path=rel_path,
                                language=self._infer_language(file_path),
                                category=self._infer_category(rel_path),
                                content=content,
                            )
                        )
                except UnicodeDecodeError:
                    # Binary asset (like favicon.ico) stays in the ZIP, skipped in text viewer
                    continue

        zip_buffer.seek(0)
        manifest = ScaffoldManifest(
            project_id=ir.project_id,
            project_name=ir.project_name,
            chosen_stack=backend_stack,
            chosen_frontend=frontend_stack,
            chosen_pattern=pattern,
            cli_commands_executed=cli_log,
            total_files_generated=len(files_list),
            files=files_list,
        )
        return manifest, zip_buffer.getvalue()

    @staticmethod
    def _infer_language(file_path: Path) -> str:
        ext_map = {
            ".py": "python",
            ".go": "go",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".mjs": "javascript",
            ".vue": "vue",
            ".svelte": "svelte",
            ".rs": "rust",
            ".cs": "csharp",
            ".json": "json",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".md": "markdown",
            ".css": "css",
            ".html": "html",
        }
        return ext_map.get(file_path.suffix.lower(), "text")

    @staticmethod
    def _infer_category(rel_path: str) -> str:
        if rel_path.startswith("frontend/src/components"):
            return "frontend-ui"
        if rel_path.startswith("frontend/src/"):
            return "frontend-data"
        if rel_path.startswith("frontend/"):
            return "frontend-config"
        if "domain" in rel_path.lower():
            return "domain"
        if "ports" in rel_path.lower():
            return "ports"
        if "application" in rel_path.lower():
            return "application"
        if "tests" in rel_path.lower():
            return "tests"
        if rel_path.endswith(".md") or rel_path.endswith(".ir.json"):
            return "docs"
        return "infrastructure"


scaffolder_engine = ScaffolderEngine()
