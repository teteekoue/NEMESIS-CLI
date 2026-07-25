import os
from pathlib import Path

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"

def get_system_prompt():
    p = _PROMPT_DIR / "system.txt"
    if p.exists():
        return p.read_text()
    return _DEFAULT_SYSTEM

def get_plan_prompt():
    p = _PROMPT_DIR / "plan.txt"
    if p.exists():
        return p.read_text()
    return "Tu es en mode PLAN. Crée un plan structuré en JSON avant d'exécuter."

def get_sub_agent_prompt():
    p = _PROMPT_DIR / "sub_agent.txt"
    if p.exists():
        return p.read_text()
    return "Tu es un sous-agent NEMESIS. Complète ta tâche et rapporte les résultats."
