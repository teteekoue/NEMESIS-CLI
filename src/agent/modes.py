#!/usr/bin/env python3
"""Modes d'agent: Plan et Dual Model."""
import json, re
from typing import Callable, Optional


class PlanMode:
    def __init__(self, agent):
        self.agent = agent
        self.current_plan = None

    def create_plan(self, task: str, callback: Callable = None) -> dict:
        plan_request = (
            "[MODE PLAN] Crée un plan structuré pour cette tâche:\n\n"
            f"{task}\n\n"
            "Réponds UNIQUEMENT avec ce JSON:\n"
            '{"plan": "description", "steps": [{"id": 1, "description": "...", "done": false}]}'
        )
        orig = self.agent.system_prompt
        self.agent.set_system_prompt(
            orig + "\n\n[MODE PLAN ACTIF - Réponds UNIQUEMENT en JSON avec un champ \"steps\"]"
        )
        result = self.agent.chat(plan_request, callback=callback)
        self.agent.set_system_prompt(orig)
        plan = self._parse_plan(result.get("content", ""))
        self.current_plan = plan
        return plan

    def execute_step(self, step: dict, callback=None):
        msg = f"[Étape {step.get('id', '?')}] {step['description']}"
        return self.agent.chat(msg, callback=callback)

    def execute_all(self, callback=None):
        if not self.current_plan or not self.current_plan.get("steps"):
            return []
        results = []
        for step in self.current_plan["steps"]:
            if step.get("done"):
                continue
            if callback:
                callback("plan_step", {"step": step})
            result = self.execute_step(step, callback=callback)
            step["done"] = True
            results.append({"step": step, "result": result})
        return results

    def _parse_plan(self, content):
        for pat in [r'```json\s*(\{[^`]*?"steps"\s*:\s*\[[^\]]*\][^`]*?\})\s*```',
                    r'(\{"plan"[^}]*"steps"\s*:\s*\[[^\]]*\][^}]*\})']:
            m = re.search(pat, content, re.S)
            if m:
                try:
                    p = json.loads(m.group(1))
                    if "steps" in p:
                        return p
                except Exception:
                    pass
        return {"plan": content[:200], "steps": [{"id": 1, "description": content, "done": False}]}


class DualModelMode:
    def __init__(self, provider_a, provider_b, tool_defs, tool_exec, system_prompt, debug=False):
        self.provider_a = provider_a
        self.provider_b = provider_b
        self.tool_defs = tool_defs
        self.tool_exec = tool_exec
        self.system_prompt = system_prompt
        self.debug = debug

    def execute(self, task: str, max_rounds: int = 3, callback=None) -> dict:
        msgs_a = [{"role": "system", "content": self.system_prompt + "\n[MODE DUAL - RÔLE: GÉNÉRATEUR] Produis une solution de haute qualité."}]
        msgs_b = [{"role": "system", "content": "Tu es un réviseur expert. Évalue la solution. Réponds en JSON: {\"approved\": bool, \"issues\": [], \"feedback\": \"...\"}. Si la solution est bonne, approuve."}]
        last_content = ""
        last_review = None
        for rnd in range(1, max_rounds + 1):
            if callback:
                callback("dual_round", {"round": rnd})
            if rnd == 1:
                msgs_a.append({"role": "user", "content": f"Tâche: {task}\nProduis une solution complète."})
            else:
                msgs_a.append({"role": "user", "content": f"Retours (round {rnd-1}): {json.dumps(last_review, ensure_ascii=False)}\nAméliore ta solution."})
            resp_a = self.provider_a.chat(msgs_a, self.tool_defs)
            if resp_a.tool_calls:
                msgs_a.append({
                    "role": "assistant", "content": resp_a.content or "",
                    "tool_calls": [{"id": t["id"], "type": "function",
                                   "function": {"name": t["name"], "arguments": t["arguments"]}}
                                  for t in resp_a.tool_calls]
                })
                for tc in resp_a.tool_calls:
                    args = json.loads(tc["arguments"]) if isinstance(tc["arguments"], str) else tc["arguments"]
                    r = self.tool_exec.execute(tc["name"], args)
                    msgs_a.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(r)})
                resp_a = self.provider_a.chat(msgs_a, self.tool_defs)
            msgs_a.append({"role": "assistant", "content": resp_a.content})
            last_content = resp_a.content or ""
            review_msg = f"Tâche: {task}\n\nSolution:\n{last_content}\nÉvalue."
            msgs_b.append({"role": "user", "content": review_msg})
            resp_b = self.provider_b.chat(msgs_b)
            msgs_b.append({"role": "assistant", "content": resp_b.content})
            review = self._parse_review(resp_b.content)
            last_review = review
            if callback:
                callback("review_result", {"round": rnd, "approved": review.get("approved")})
            if review.get("approved"):
                return {"content": last_content, "rounds": rnd, "review": review, "status": "approved"}
        return {"content": last_content, "rounds": max_rounds, "review": last_review, "status": "max_rounds"}

    def _parse_review(self, content):
        m = re.search(r'```(?:json)?\s*(\{[^`]*?"approved"[^`]*?\})\s*```', content, re.S)
        if m:
            try:
                r = json.loads(m.group(1))
                r.setdefault("approved", False)
                r.setdefault("issues", [])
                r.setdefault("feedback", content)
                return r
            except Exception:
                pass
        m2 = re.search(r'\{[^{]*?"approved"\s*:\s*(?:true|false)[^}]*\}', content, re.S)
        if m2:
            try:
                r = json.loads(m2.group(0))
                r.setdefault("approved", False)
                r.setdefault("issues", [])
                r.setdefault("feedback", content)
                return r
            except Exception:
                pass
        approval_words = ["approuv", "approved", "approve", "bon", "good", "correct", "bien", "well", "valid"]
        return {
            "approved": any(w in content.lower() for w in approval_words),
            "issues": [],
            "feedback": content
        }
