import re
import os
import platform
from typing import Dict, Optional
from .tool_kind import ToolKind


class TemplateRenderer:
    """Renders ${{ tools.by_kind.xxx }} and ${% if ... %} templates.

    Template syntax:
        ${{ tools.by_kind.read }}     -> client-facing Read tool name
        ${{ params.edit.old_string }}  -> client-facing param name
        ${% if tools.by_kind.search %}...${% endif %}  -> conditional

    Fast-path: templates without ${{ or ${% are returned unchanged.
    """

    _TOOLS_VAR = re.compile(r"\$\{\{\s*tools\.by_kind\.(\w+)\s*\}\}")
    _PARAMS_VAR = re.compile(r"\$\{\{\s*params\.(\w+)\.(\w+)\s*\}\}")
    _IF_BLOCK = re.compile(
        r"\$\{%\s*-?\s*if\s+(\S+)\s*-?%\}\s*(.*?)\s*\$\{%\s*-?\s*endif\s*-?%\}",
        re.DOTALL,
    )

    def __init__(
        self,
        tools: Dict[ToolKind, str],
        params: Optional[Dict[ToolKind, Dict[str, str]]] = None,
    ):
        self._tools = tools
        self._params = params or {}
        self._is_windows = os.name == "nt"
        self._has_unix_utilities = not self._is_windows

    def render(self, template: str) -> str:
        if "${{" not in template and "${%" not in template:
            return template

        result = template

        result = self._TOOLS_VAR.sub(self._resolve_tool, result)
        result = self._PARAMS_VAR.sub(self._resolve_param, result)
        result = self._resolve_conditionals(result)

        return result

    def _resolve_tool(self, m: re.Match) -> str:
        key = m.group(1)
        for kind in ToolKind:
            if kind.value == key:
                return self._tools.get(kind, key)
        return key

    def _resolve_param(self, m: re.Match) -> str:
        kind_key = m.group(1)
        param_key = m.group(2)
        for kind in ToolKind:
            if kind.value == kind_key:
                param_map = self._params.get(kind, {})
                return param_map.get(param_key, param_key)
        return param_key

    def _resolve_conditionals(self, template: str) -> str:
        def repl(m: re.Match) -> str:
            expr = m.group(1).strip()
            body = m.group(2)
            negate = False
            if expr.startswith("not "):
                negate = True
                expr = expr[4:].strip()
            if expr.startswith("tools.by_kind."):
                kind_key = expr[len("tools.by_kind."):]
                present = any(k.value == kind_key for k in self._tools)
                if negate:
                    present = not present
                return body if present else ""
            if expr in ("is_windows",):
                val = bool(getattr(self, f"_{expr}", False))
                if negate:
                    val = not val
                return body if val else ""
            if expr in ("has_unix_utilities",):
                val = bool(getattr(self, f"_{expr}", False))
                if negate:
                    val = not val
                return body if val else ""
            if expr in ("is_non_interactive",):
                return "" if negate else body
            return body
        return self._IF_BLOCK.sub(repl, template)

    def tool_for_kind(self, kind: ToolKind) -> Optional[str]:
        return self._tools.get(kind)

    def param_for_kind(self, kind: ToolKind, canonical: str) -> Optional[str]:
        param_map = self._params.get(kind, {})
        return param_map.get(canonical)

    def render_schema_descriptions(self, schema: dict) -> None:
        def walk(obj):
            if isinstance(obj, dict):
                if "description" in obj and isinstance(obj["description"], str):
                    desc = obj["description"]
                    if "${{" in desc or "${%" in desc:
                        obj["description"] = self.render(desc)
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)
        walk(schema)

    def render_with_extra(self, template: str, placeholders: dict) -> str:
        result = self.render(template)
        for key, val in placeholders.items():
            result = result.replace(f"${{{{ {key} }}}}", str(val))
        return result
