import os
from pathlib import Path
from groq import Groq
=======
from src.core.utils import get_resource_path
>>>>>>> 5380d9a25d4e84c58e2a84c467fbc6e2b0173307

class AgentClient:
    def __init__(self, name: str, api_key: str):
        self.name = name
        self.client = Groq(api_key=api_key)
        self.history = []

    def send_message(self, message: str, role="user") -> str:
        # Initialisation : Injection forcée du prompt système en index 0
<<<<<<< HEAD
        p_path = Path("agent_subordinate_prompt.txt")