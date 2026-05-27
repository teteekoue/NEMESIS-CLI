from typing import Dict, List, Callable, Optional
from dataclasses import dataclass

@dataclass
class Command:
    name: str
    description: str
    handler: Callable
    usage: str = ""

class CommandRegistry:
    def __init__(self):
        self._commands: Dict[str, Command] = {}

    def register(self, name: str, description: str, usage: str = ""):
        def decorator(handler: Callable):
            self._commands[name] = Command(name, description, handler, usage)
            return handler
        return decorator

    def get_command(self, name: str) -> Optional[Command]:
        return self._commands.get(name)

    def list_commands(self) -> List[Command]:
        return sorted(self._commands.values(), key=lambda x: x.name)

# Instance globale pour le registre
registry = CommandRegistry()
