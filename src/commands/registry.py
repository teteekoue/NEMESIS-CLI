from dataclasses import dataclass, field
from typing import Callable, List, Optional

@dataclass
class Command:
    name: str
    description: str
    handler: Callable
    usage: str = ""
    category: str = "general"
    aliases: List[str] = field(default_factory=list)

class CommandRegistry:
    def __init__(self):
        self._commands = {}

    def register(self, name, description, usage="", category="general", aliases=None):
        def decorator(handler):
            self._commands[name] = Command(name, description, handler, usage, category, aliases or [])
            for a in (aliases or []):
                self._commands[a] = self._commands[name]
            return handler
        return decorator

    def get(self, name):
        return self._commands.get(name)

    def list_all(self):
        return list(set(self._commands.values()))

    def list_by_category(self):
        cats = {}
        for cmd in self.list_all():
            cats.setdefault(cmd.category, []).append(cmd)
        return cats

    def get_names(self):
        return [c.name for c in self.list_all()]
