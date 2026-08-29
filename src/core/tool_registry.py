from dataclasses import dataclass, field
from typing import Dict, List, Callable, Optional, Any
from .tool_kind import ToolKind, ToolNamespace, ToolDefinition, ToolIdentity
from .template_renderer import TemplateRenderer


@dataclass
class ToolRegistration:
    definition: ToolDefinition
    handler: Callable
    param_names: Dict[str, str] = field(default_factory=dict)


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolRegistration] = {}
        self._renderer: Optional[TemplateRenderer] = None

    def register(
        self,
        name: str,
        kind: ToolKind,
        handler: Callable,
        description: str,
        params_schema: dict,
        namespace: ToolNamespace = ToolNamespace.GROK_BUILD,
        param_names: Optional[Dict[str, str]] = None,
    ) -> "ToolRegistry":
        self._tools[name] = ToolRegistration(
            definition=ToolDefinition(
                name=name,
                description=description,
                kind=kind,
                namespace=namespace,
                params_schema=params_schema,
            ),
            handler=handler,
            param_names=param_names or {},
        )
        return self

    def finalize(self) -> "ToolRegistry":
        tools_map: Dict[ToolKind, str] = {}
        params_map: Dict[ToolKind, Dict[str, str]] = {}

        for name, reg in self._tools.items():
            tools_map[reg.definition.kind] = name
            if reg.param_names:
                params_map[reg.definition.kind] = reg.param_names
            else:
                params_map[reg.definition.kind] = {
                    p: p for p in reg.definition.params_schema.get("properties", {}).keys()
                }

        self._renderer = TemplateRenderer(tools_map, params_map)

        for name, reg in self._tools.items():
            rendered_desc = self._renderer.render(reg.definition.description)
            reg.definition.description = rendered_desc
            schema = dict(reg.definition.params_schema)
            self._renderer.render_schema_descriptions(schema)
            reg.definition.params_schema = schema

        return self

    @property
    def renderer(self) -> Optional[TemplateRenderer]:
        return self._renderer

    def get_renderer(self) -> TemplateRenderer:
        if self._renderer is None:
            raise RuntimeError("Registry not finalized. Call .finalize() first.")
        return self._renderer

    def get_tool(self, name: str) -> Optional[ToolRegistration]:
        return self._tools.get(name)

    def get_definitions(self) -> List[ToolDefinition]:
        return [reg.definition for reg in self._tools.values()]

    def get_openai_functions(self) -> List[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": reg.definition.name,
                    "description": reg.definition.description,
                    "parameters": reg.definition.params_schema,
                },
            }
            for reg in self._tools.values()
        ]

    def call(self, name: str, params: dict) -> Any:
        reg = self._tools.get(name)
        if not reg:
            raise ValueError(f"Unknown tool: {name}")

        ok, cleaned, error = self.validate_call(name, params)
        if not ok:
            raise ValueError(error)
        return reg.handler(**cleaned)

    def validate_call(self, name: str, params: dict):
        """Valide les parametres contre le schema de l'outil.

        Retourne (ok, cleaned_params, error):
        - Les cles inconnues sont supprimees (jamais passees au handler).
        - Les parametres requis manquants provoquent une erreur explicite.
        """
        reg = self._tools.get(name)
        if not reg:
            return False, {}, f"Outil inconnu: {name}"

        if not isinstance(params, dict):
            return False, {}, f"Parametres invalides pour '{name}' (dict attendu)."

        schema = reg.definition.params_schema or {}
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        cleaned = {}
        for key, value in params.items():
            if key in properties:
                cleaned[key] = value

        missing = [r for r in required if r not in cleaned]
        if missing:
            return (
                False,
                {},
                f"Parametres requis manquants pour '{name}': {', '.join(missing)}",
            )

        return True, cleaned, ""

    def tool_for_kind(self, kind: ToolKind) -> Optional[str]:
        if self._renderer:
            return self._renderer.tool_for_kind(kind)
        for name, reg in self._tools.items():
            if reg.definition.kind == kind:
                return name
        return None

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def __iter__(self):
        return iter(self._tools.items())
