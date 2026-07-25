#!/usr/bin/env python3
"""Noyau de l'agent NEMESIS - Boucle agentic avec tool calling JSON."""
import json, uuid
from typing import Callable, Optional, List, Dict, Any


class NemesisAgent:
    def __init__(self, provider, system_prompt: str, tool_definitions: list,
                 tool_executor, workspace: str = "./workspace", debug: bool = False):
        self.provider = provider
        self.system_prompt = system_prompt
        self.tool_definitions = tool_definitions
        self.tool_executor = tool_executor
        self.workspace = workspace
        self.debug = debug
        self.conversation_id = str(uuid.uuid4())[:8]
        self.max_iterations = 100
        self.messages = [{"role": "system", "content": system_prompt}]
        self._total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self._iteration_count = 0

    def chat(self, user_message: str, callback: Callable = None) -> dict:
        self.messages.append({"role": "user", "content": user_message})
        self._iteration_count = 0
        for iteration in range(1, self.max_iterations + 1):
            self._iteration_count = iteration
            if self.debug and callback:
                callback("debug", {"msg": f"Itération {iteration}", "messages_len": len(self.messages)})
            response = self.provider.chat(self.messages, self.tools())
            self._accumulate_usage(response.usage)
            if response.tool_calls:
                self.messages.append({
                    "role": "assistant", "content": response.content or "",
                    "tool_calls": [{"id": tc["id"], "type": "function",
                                     "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                                    for tc in response.tool_calls]
                })
                for tc in response.tool_calls:
                    if callback:
                        callback("tool_call", {"name": tc["name"], "args_preview": tc["arguments"][:100]})
                    try:
                        args = json.loads(tc["arguments"]) if isinstance(tc["arguments"], str) else tc["arguments"]
                    except json.JSONDecodeError:
                        args = {}
                    result = self.tool_executor.execute(tc["name"], args)
                    result_str = json.dumps(result, ensure_ascii=False)
                    if len(result_str) > 100000:
                        result_str = result_str[:100000] + "\n[TRONQUÉ]"
                    self.messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result_str})
                    if callback:
                        callback("tool_result", {"name": tc["name"], "success": result.get("success")})
                continue
            if response.content:
                self.messages.append({"role": "assistant", "content": response.content})
                return {"content": response.content, "usage": self._total_usage.copy(), "iterations": iteration}
            return {"content": "", "usage": self._total_usage.copy(), "iterations": iteration, "error": "Réponse vide"}
        return {"content": "", "usage": self._total_usage.copy(), "iterations": self.max_iterations, "error": "Max itérations atteint"}

    def tools(self):
        all_tools = list(self.tool_definitions)
        if self.tool_executor and self.tool_executor.mcp_manager:
            mcp_tools = self.tool_executor.mcp_manager.get_all_tools()
            all_tools.extend(mcp_tools)
        return all_tools if all_tools else None

    def clear_history(self):
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self._total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def get_history(self) -> list:
        return list(self.messages)

    def get_token_usage(self) -> dict:
        return self._total_usage.copy()

    def set_system_prompt(self, prompt: str):
        self.system_prompt = prompt
        if self.messages and self.messages[0]["role"] == "system":
            self.messages[0]["content"] = prompt

    def compact_history(self, summary: str = None):
        if len(self.messages) <= 6:
            return
        if summary is None:
            summary = "[Historique compacté - échanges précédents résumés]"
        self.messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"[Résumé de la conversation précédente] {summary}"},
            {"role": "assistant", "content": "Compris, je continue avec ce contexte."}
        ] + self.messages[-4:]

    def _accumulate_usage(self, usage: dict):
        if not usage:
            return
        for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
            self._total_usage[k] = self._total_usage.get(k, 0) + usage.get(k, 0)
