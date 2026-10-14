# app/services/ingestion/ast_analyzer.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tree_sitter_javascript as tsjavascript
import tree_sitter_python as tspython
import tree_sitter_typescript as tstypescript
from tree_sitter import Language, Node, Parser

from app.config import settings
from app.domain.ir_schema import (
    DataTypePrimitive,
    EntityDefinition,
    EntityField,
    HttpMethod,
    RouteDefinition,
    SourceModality,
    SourceReference,
)
from app.services.ingestion.token_gatekeeper import token_gatekeeper

# Initialize tree-sitter 0.23+ Language bindings
PY_LANGUAGE = Language(tspython.language())
JS_LANGUAGE = Language(tsjavascript.language())
TS_LANGUAGE = Language(tstypescript.language_typescript())
TSX_LANGUAGE = Language(tstypescript.language_tsx())

LANGUAGE_MAP: Dict[str, Language] = {
    ".py": PY_LANGUAGE,
    ".js": JS_LANGUAGE,
    ".jsx": JS_LANGUAGE,
    ".ts": TS_LANGUAGE,
    ".tsx": TSX_LANGUAGE,
}

# AST node types that add a branching path (+1 to Cyclomatic Complexity)
BRANCHING_NODE_TYPES = {
    # Python
    "if_statement",
    "elif_clause",
    "for_statement",
    "while_statement",
    "except_clause",
    "with_statement",
    "conditional_expression",
    "boolean_operator",
    "match_statement",
    "case_clause",
    # JS / TS
    "for_in_statement",
    "do_statement",
    "switch_case",
    "catch_clause",
    "ternary_expression",
}

TYPE_MAPPING: Dict[str, DataTypePrimitive] = {
    "str": DataTypePrimitive.STRING,
    "string": DataTypePrimitive.STRING,
    "int": DataTypePrimitive.INTEGER,
    "integer": DataTypePrimitive.INTEGER,
    "number": DataTypePrimitive.FLOAT,
    "float": DataTypePrimitive.FLOAT,
    "decimal": DataTypePrimitive.DECIMAL,
    "bool": DataTypePrimitive.BOOLEAN,
    "boolean": DataTypePrimitive.BOOLEAN,
    "datetime": DataTypePrimitive.DATETIME,
    "date": DataTypePrimitive.DATETIME,
    "uuid": DataTypePrimitive.UUID,
    "dict": DataTypePrimitive.JSON,
    "object": DataTypePrimitive.JSON,
    "bytes": DataTypePrimitive.BINARY,
}


@dataclass
class ComplexCodeChunk:
    """Represents a high-complexity function isolated for LLM business rule extraction."""

    symbol_name: str
    file_path: str
    start_line: int
    end_line: int
    cyclomatic_complexity: int
    token_count: int
    source_code: str


@dataclass
class DeterministicASTResult:
    """Output of local static analysis before any LLM is called."""

    entities: List[EntityDefinition] = field(default_factory=list)
    routes: List[RouteDefinition] = field(default_factory=list)
    complex_chunks: List[ComplexCodeChunk] = field(default_factory=list)
    nodes_parsed_deterministically: int = 0
    tokens_saved: int = 0
    tokens_queued_for_llm: int = 0


class DeterministicASTAnalyzer:
    """Walks source code ASTs using tree-sitter to extract structure and filter boilerplate."""

    def analyze_file(self, file_path: str, source_code: str) -> DeterministicASTResult:
        ext = Path(file_path).suffix.lower()
        language = LANGUAGE_MAP.get(ext)
        result = DeterministicASTResult()

        total_file_tokens = token_gatekeeper.count_tokens(source_code)
        if not language:
            # Unsupported extension: skip AST parsing and mark tokens saved from blind dump
            result.tokens_saved = total_file_tokens
            return result

        parser = Parser(language)
        source_bytes = source_code.encode("utf-8")
        tree = parser.parse(source_bytes)

        self._walk_tree(tree.root_node, source_bytes, file_path, result)

        # Tokens saved = total file tokens minus the specific complex chunks sent to LLM
        result.tokens_saved = max(0, total_file_tokens - result.tokens_queued_for_llm)
        return result

    def _walk_tree(
        self,
        node: Node,
        source_bytes: bytes,
        file_path: str,
        result: DeterministicASTResult,
    ) -> None:
        # 1. Extract Classes / Interfaces deterministically as Entities
        if node.type in (
            "class_definition",
            "class_declaration",
            "interface_declaration",
        ):
            entity = self._extract_entity(node, source_bytes, file_path)
            if entity:
                result.entities.append(entity)
                result.nodes_parsed_deterministically += 1

        # 2. Extract Decorated Functions (Routes) or Evaluate Function Complexity
        if node.type == "decorated_definition":
            route = self._extract_python_route(node, source_bytes, file_path)
            if route:
                result.routes.append(route)
                result.nodes_parsed_deterministically += 1

        if node.type in (
            "function_definition",
            "function_declaration",
            "method_definition",
        ):
            self._evaluate_function_node(node, source_bytes, file_path, result)

        # Recurse children
        for child in node.children:
            self._walk_tree(child, source_bytes, file_path, result)

    def _extract_entity(
        self, node: Node, source_bytes: bytes, file_path: str
    ) -> Optional[EntityDefinition]:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        class_name = self._node_text(name_node, source_bytes)
        # Skip obvious non-entity boilerplate classes (e.g., Config, Controller, Service)
        if class_name.endswith(
            ("Controller", "Service", "Router", "Middleware", "Config")
        ):
            return None

        fields: List[EntityField] = []
        body_node = node.child_by_field_name("body")
        if body_node:
            for item in body_node.children:
                extracted_field = self._extract_field_from_node(item, source_bytes)
                if extracted_field:
                    fields.append(extracted_field)

        return EntityDefinition(
            name=class_name,
            description=f"Deterministically extracted from {file_path}",
            fields=fields,
            sources=[
                SourceReference(
                    modality=SourceModality.AST_STATIC,
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    raw_symbol_name=class_name,
                )
            ],
        )

    def _extract_field_from_node(
        self, node: Node, source_bytes: bytes
    ) -> Optional[EntityField]:
        """Extracts typed attributes from Python class bodies or TS interfaces."""
        text = self._node_text(node, source_bytes).strip()
        if ":" not in text or text.startswith(("def ", "async ", "#", "//")):
            return None

        # Parse simple `field_name: type = default`
        left_side = text.split("=")[0].strip().rstrip(";,")
        parts = left_side.split(":", 1)
        if len(parts) != 2:
            return None

        field_name = parts[0].strip()
        raw_type = parts[1].strip().lower()

        if not field_name.isidentifier():
            return None

        mapped_type = DataTypePrimitive.STRING
        for key, primitive in TYPE_MAPPING.items():
            if key in raw_type:
                mapped_type = primitive
                break

        is_optional = "optional" in raw_type or "none" in raw_type or "?" in parts[0]
        return EntityField(
            name=field_name.rstrip("?"),
            data_type=mapped_type,
            is_required=not is_optional,
            is_primary_key=field_name.lower() in ("id", "uuid", "pk"),
        )

    def _extract_python_route(
        self, node: Node, source_bytes: bytes, file_path: str
    ) -> Optional[RouteDefinition]:
        """Detects @app.get('/path') or @router.post('/path') decorators deterministically."""
        for child in node.children:
            if child.type == "decorator":
                dec_text = self._node_text(child, source_bytes)
                for method in ("get", "post", "put", "patch", "delete"):
                    if f".{method}(" in dec_text.lower():
                        path = (
                            self._extract_first_string_literal(dec_text) or "/unknown"
                        )
                        fn_node = node.child_by_field_name("definition")
                        fn_name = "route_handler"
                        if fn_node and fn_node.child_by_field_name("name"):
                            fn_name = self._node_text(
                                fn_node.child_by_field_name("name"), source_bytes
                            )
                        return RouteDefinition(
                            path=path,
                            method=HttpMethod(method.upper()),
                            summary=f"Extracted handler `{fn_name}` from {file_path}",
                            sources=[
                                SourceReference(
                                    modality=SourceModality.AST_STATIC,
                                    file_path=file_path,
                                    start_line=node.start_point[0] + 1,
                                    end_line=node.end_point[0] + 1,
                                    raw_symbol_name=fn_name,
                                )
                            ],
                        )
        return None

    def _evaluate_function_node(
        self,
        node: Node,
        source_bytes: bytes,
        file_path: str,
        result: DeterministicASTResult,
    ) -> None:
        name_node = node.child_by_field_name("name")
        fn_name = self._node_text(name_node, source_bytes) if name_node else "anonymous"
        fn_code = self._node_text(node, source_bytes)
        complexity = self._calculate_cyclomatic_complexity(node, source_bytes)
        token_count = token_gatekeeper.count_tokens(fn_code)

        # Gatekeeper check: Only send to LLM if complexity meets or exceeds threshold
        if complexity >= settings.MIN_CYCLOMATIC_COMPLEXITY_FOR_LLM:
            truncated_code = token_gatekeeper.truncate_to_budget(
                fn_code, settings.MAX_CHUNK_TOKENS
            )
            chunk_tokens = token_gatekeeper.count_tokens(truncated_code)
            result.complex_chunks.append(
                ComplexCodeChunk(
                    symbol_name=fn_name,
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    cyclomatic_complexity=complexity,
                    token_count=chunk_tokens,
                    source_code=truncated_code,
                )
            )
            result.tokens_queued_for_llm += chunk_tokens
        else:
            # Boilerplate / simple CRUD / getter / setter -> handled deterministically
            result.nodes_parsed_deterministically += 1

    def _calculate_cyclomatic_complexity(self, node: Node, source_bytes: bytes) -> int:
        """
        McCabe Cyclomatic Complexity: starts at 1, increments by 1 for every
        decision branch in the function's AST subtree.
        """
        complexity = 1
        stack = [node]
        while stack:
            current = stack.pop()
            if current.type in BRANCHING_NODE_TYPES:
                complexity += 1
            elif current.type == "binary_expression":
                text = self._node_text(current, source_bytes)
                if "&&" in text or "||" in text:
                    complexity += 1
            stack.extend(current.children)
        return complexity

    @staticmethod
    def _node_text(node: Optional[Node], source_bytes: bytes) -> str:
        if not node:
            return ""
        return source_bytes[node.start_byte : node.end_byte].decode(
            "utf-8", errors="replace"
        )

    @staticmethod
    def _extract_first_string_literal(text: str) -> Optional[str]:
        for quote in ('"', "'"):
            if quote in text:
                parts = text.split(quote)
                if len(parts) >= 3:
                    return parts[1]
        return None


ast_analyzer = DeterministicASTAnalyzer()
