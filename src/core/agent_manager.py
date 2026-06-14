import os
from pathlib import Path
from groq import Groq
<<<<<<< HEAD
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
=======
        p_path = get_resource_path("agent_subordinate_prompt.txt")
>>>>>>> 5380d9a25d4e84c58e2a84c467fbc6e2b0173307
        system_content = p_path.read_text() if p_path.exists() else ""
        
        # Gestion propre de l'historique
        if not self.history or self.history[0].get("role") != "system":
            self.history.insert(0, {"role": "system", "content": system_content})
        
        # Ajout du message (ou feedback)
        self.history.append({"role": role, "content": message})
        
        try:
            completion = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=self.history,
                temperature=0.6,
                max_completion_tokens=4096,
                top_p=0.95,
                stream=True,
                stop=None
            )
            
            response_text = ""
            for chunk in completion:
                content = chunk.choices[0].delta.content or ""
                response_text += content
                
            # Ajout de la réponse à l'historique pour garder le contexte
            self.history.append({"role": "assistant", "content": response_text})
            return response_text
        except Exception as e:
            return f"Erreur agent {self.name}: {str(e)}"
