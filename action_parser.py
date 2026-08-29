#!/usr/bin/env python3
"""
Ultra-robust JSON-only tool call parser for NEMESIS CLI.

Only the JSON format is supported. The parser is designed to extract and
repair tool calls from LLM responses even when they contain:
  - Large multi-line content (code, file bodies, etc.)
  - Unescaped newlines, tabs, backslashes, quotes inside string values
  - Trailing commas, single quotes, unquoted keys
  - Truncated JSON
  - Surrounding prose or markdown fences

Supported call shapes (all equivalent after normalisation):
  {"tool": "name", "parameters": {...}}
  {"name": "name", "arguments": {...}}
  {"action": "name", "params": {...}}

Public API:
  ActionParser.parse(raw_response) -> {"text": str, "action": None | {"type": str, "content": dict}}
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple


class ActionParser:
    """Strict JSON tool-call parser with aggressive repair for LLM output."""

    # Canonical tool names (underscores). Keep in sync with the executor.
    VALID_TOOLS: Set[str] = {
        "read_file",
        "write_file",
        "edit",
        "bash",
        "get_task_output",
        "kill_task",
        "list_dir",
        "grep",
        "glob",
        "git",
        "todo",
        "apply_patch",
        "web_search",
        "web_fetch",
        "delete_file",
        "mcp_list",
        "mcp_tools_list",
        "mcp_call",
        "list_agents",
        "delegate_task",
        "check_reports",
        # Legacy
        "write",
        "read",
        "replace",
        "append",
        "validate",
        "status",
        "kill_process",
        "stop_all",
        "cleanup_logs",
        "update_tracker",
        "skills_list",
        "search_replace",
    }

    # Map any historical / alternate name onto the canonical name.
    LEGACY_MAP: Dict[str, str] = {
        "search_replace": "edit",
        "search-replace": "edit",
        "replace": "edit",
        "write": "write_file",
        "read": "read_file",
        "read-file": "read_file",
        "write-file": "write_file",
        "get-task-output": "get_task_output",
        "kill-task": "kill_task",
        "list-dir": "list_dir",
        "web-search": "web_search",
        "web-fetch": "web_fetch",
        "delete-file": "delete_file",
    }

    def __init__(self, extra_valid_tools: Optional[Set[str]] = None):
        if extra_valid_tools:
            self.VALID_TOOLS = self.VALID_TOOLS | set(extra_valid_tools)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def parse(self, raw_response: str) -> Dict[str, Any]:
        """Parse a raw LLM response and extract at most one tool call.

        Returns:
            {"text": str, "action": None | {"type": str, "content": dict}}
        """
        result: Dict[str, Any] = {"text": raw_response or "", "action": None}

        if not raw_response or not isinstance(raw_response, str):
            return result

        if raw_response.startswith("FEEDBACK:"):
            return result

        # 1. Prefer fenced ```json ... ``` blocks
        action, consumed = self._extract_from_fences(raw_response)
        if action:
            text = self._remove_matched_fence(raw_response, consumed)
            result["text"] = text
            result["action"] = action
            return result

        # 2. Any balanced {...} object that looks like a tool call
        action, span = self._extract_largest_tool_json(raw_response)
        if action:
            text = (raw_response[: span[0]] + raw_response[span[1] :]).strip()
            result["text"] = text
            result["action"] = action
            return result

        return result

    # ------------------------------------------------------------------
    # Fence extraction
    # ------------------------------------------------------------------

    def _extract_from_fences(self, text: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Return (action, matched_fence_text) or (None, None)."""
        # ```json ... ```  or  ```JSON ... ```  or plain ``` ... ```
        patterns = [
            re.compile(r"```(?:json|JSON)\s*\n?(.*?)```", re.S),
            re.compile(r"```\s*\n?(\{.*?\})\s*```", re.S),
        ]
        for pat in patterns:
            for m in pat.finditer(text):
                candidate = m.group(1).strip()
                if not candidate.startswith("{"):
                    continue
                action = self._parse_json_candidate(candidate)
                if action:
                    return action, m.group(0)
        return None, None

    def _remove_matched_fence(self, full: str, fence: str) -> str:
        if not fence:
            return full.strip()
        return full.replace(fence, "", 1).strip()

    # ------------------------------------------------------------------
    # Largest balanced JSON extraction
    # ------------------------------------------------------------------

    def _extract_largest_tool_json(
        self, text: str
    ) -> Tuple[Optional[Dict], Tuple[int, int]]:
        """Scan for the largest balanced {...} that validates as a tool call."""
        starts = [i for i, c in enumerate(text) if c == "{"]
        best: Optional[Dict] = None
        best_span = (0, 0)

        for start in starts:
            end = self._find_matching_brace(text, start)
            if end < 0:
                # Possibly truncated – try repairing from start to end of text
                candidate = text[start:]
                action = self._parse_json_candidate(candidate)
                if action and (best is None or len(candidate) > best_span[1] - best_span[0]):
                    best = action
                    best_span = (start, len(text))
                continue

            candidate = text[start:end]
            action = self._parse_json_candidate(candidate)
            if action and (best is None or (end - start) > (best_span[1] - best_span[0])):
                best = action
                best_span = (start, end)

        return best, best_span

    def _find_matching_brace(self, s: str, start: int) -> int:
        """Return index past the matching '}' or -1 if not found / unbalanced."""
        depth = 0
        in_string = False
        escape = False
        i = start
        while i < len(s):
            ch = s[i]
            if escape:
                escape = False
                i += 1
                continue
            if ch == "\\":
                escape = True
                i += 1
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                i += 1
                continue
            if in_string:
                i += 1
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
        return -1

    # ------------------------------------------------------------------
    # Core JSON parsing + progressive repair
    # ------------------------------------------------------------------

    def _parse_json_candidate(self, raw: str) -> Optional[Dict[str, Any]]:
        """Try strict parse, then a series of repairs."""
        s = raw.strip()
        if not s.startswith("{"):
            return None

        # Fast path
        try:
            obj = json.loads(s)
            return self._validate_tool_obj(obj)
        except (json.JSONDecodeError, ValueError):
            pass

        # Progressive repairs
        repairs = [
            self._repair_newlines_in_strings,
            self._repair_trailing_commas,
            self._repair_comments,
            self._repair_unquoted_keys,
            self._repair_single_quotes,
            self._repair_control_chars,
            self._repair_truncated,
            self._repair_python_escapes,
        ]

        # Apply repairs cumulatively and also try each in isolation
        candidate = s
        for repair in repairs:
            candidate = repair(candidate)
            try:
                obj = json.loads(candidate)
                result = self._validate_tool_obj(obj)
                if result:
                    return result
            except (json.JSONDecodeError, ValueError):
                continue

        # Last resort: extract the largest parsable substring after heavy repair
        heavily = self._repair_newlines_in_strings(
            self._repair_control_chars(self._repair_trailing_commas(s))
        )
        try:
            obj = json.loads(heavily)
            return self._validate_tool_obj(obj)
        except (json.JSONDecodeError, ValueError):
            pass

        # Try to close and parse a prefix
        for length in range(len(heavily), max(len(heavily) // 2, 20), -1):
            prefix = heavily[:length]
            closed = self._repair_truncated(prefix)
            try:
                obj = json.loads(closed)
                result = self._validate_tool_obj(obj)
                if result:
                    return result
            except (json.JSONDecodeError, ValueError):
                continue

        return None

    # ------------------------------------------------------------------
    # Individual repair functions
    # ------------------------------------------------------------------

    def _repair_newlines_in_strings(self, s: str) -> str:
        """Escape real newlines / tabs / CRs that appear inside JSON strings."""
        result: List[str] = []
        in_string = False
        escape = False
        i = 0
        while i < len(s):
            ch = s[i]
            if escape:
                result.append(ch)
                escape = False
                i += 1
                continue
            if ch == "\\":
                result.append(ch)
                escape = True
                i += 1
                continue
            if ch == '"':
                in_string = not in_string
                result.append(ch)
                i += 1
                continue
            if in_string:
                if ch == "\n":
                    result.append("\\n")
                elif ch == "\r":
                    result.append("\\r")
                elif ch == "\t":
                    result.append("\\t")
                else:
                    result.append(ch)
            else:
                result.append(ch)
            i += 1
        return "".join(result)

    def _repair_trailing_commas(self, s: str) -> str:
        s = re.sub(r",\s*}", "}", s)
        s = re.sub(r",\s*]", "]", s)
        return s

    def _repair_comments(self, s: str) -> str:
        s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
        s = re.sub(r"//[^\n]*", "", s)
        return s

    def _repair_unquoted_keys(self, s: str) -> str:
        return re.sub(
            r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)',
            r'\1"\2"\3',
            s,
        )

    def _repair_single_quotes(self, s: str) -> str:
        """Convert single-quoted strings that look like JSON delimiters."""
        # Only touch delimiters, not apostrophes inside already-double-quoted text.
        # Heuristic: 'key':  and  : 'value'  patterns.
        s = re.sub(r"'\s*:", '":', s)
        s = re.sub(r":\s*'", ': "', s)
        s = re.sub(r"'\s*,", '",', s)
        s = re.sub(r",\s*'", ', "', s)
        s = re.sub(r"\{\s*'", '{"', s)
        s = re.sub(r"'\s*\}", '"}', s)
        s = re.sub(r"\[\s*'", '["', s)
        s = re.sub(r"'\s*\]", '"]', s)
        return s

    def _repair_control_chars(self, s: str) -> str:
        """Remove or escape other control characters that break json.loads."""
        # Keep \t \n \r already handled; strip the rest of C0 controls.
        return "".join(
            ch if (ord(ch) >= 32 or ch in "\t\n\r") else " "
            for ch in s
        )

    def _repair_truncated(self, s: str) -> str:
        """Append missing closing braces / brackets."""
        depth_brace = 0
        depth_bracket = 0
        in_string = False
        escape = False
        for ch in s:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth_brace += 1
            elif ch == "}":
                depth_brace -= 1
            elif ch == "[":
                depth_bracket += 1
            elif ch == "]":
                depth_bracket -= 1
        # If we are still inside a string, close it
        if in_string:
            s += '"'
        s += "]" * max(depth_bracket, 0)
        s += "}" * max(depth_brace, 0)
        return s

    def _repair_python_escapes(self, s: str) -> str:
        """Handle common Python-style escapes that LLMs inject into JSON strings."""
        # Convert triple-double quotes that sometimes appear inside content
        s = s.replace('"""', '\\"\\"\\"')
        # Fix bare backslashes that are not valid JSON escapes
        # (keep known escapes: \" \\ \/ \b \f \n \r \t \uXXXX)
        def _fix_backslash(m: re.Match) -> str:
            nxt = m.group(1)
            if nxt in '"\\/bfnrtu':
                return m.group(0)
            # Invalid escape → double the backslash
            return "\\\\" + nxt

        s = re.sub(r'\\(.)', _fix_backslash, s)
        return s

    # ------------------------------------------------------------------
    # Validation / normalisation
    # ------------------------------------------------------------------

    def _normalize_tool_name(self, name: str) -> str:
        name = name.strip().replace("-", "_")
        return self.LEGACY_MAP.get(name, name)

    def _validate_tool_obj(self, obj: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(obj, dict):
            return None

        tool_name = (
            obj.get("tool")
            or obj.get("name")
            or obj.get("action")
            or ""
        )
        if not tool_name or not isinstance(tool_name, str):
            return None

        tool_name = self._normalize_tool_name(tool_name)
        if tool_name not in self.VALID_TOOLS:
            return None

        params = (
            obj.get("parameters")
            or obj.get("arguments")
            or obj.get("params")
            or {}
        )
        if not isinstance(params, dict):
            params = {"value": params}

        # Alias parameter names for the edit tool (old_string / new_string stay canonical)
        if tool_name == "edit":
            if "old_string" not in params and "search" in params:
                params["old_string"] = params.pop("search")
            if "new_string" not in params and "replace" in params:
                params["new_string"] = params.pop("replace")

        return {"type": tool_name, "content": params}

    def get_valid_tools(self) -> Set[str]:
        return self.VALID_TOOLS.copy()
