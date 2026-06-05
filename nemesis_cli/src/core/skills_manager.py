import os
import shutil
from pathlib import Path

from nemesis_cli.src.core.utils import get_resource_path

class SkillManager:
    def __init__(self, tools_dir="tools_library"):
        self.tools_dir = Path(tools_dir).resolve()
        if not self.tools_dir.exists():
            self.tools_dir.mkdir(parents=True, exist_ok=True)

    def list_installed(self):
        skills = []
        for item in self.tools_dir.iterdir():
            if item.is_dir():
                skill_md = item / "SKILL.md"
                if skill_md.exists():
                    skills.append(self._parse_skill_md(skill_md))
        return skills

    def _parse_skill_md(self, path):
        import re
        content = path.read_text(encoding="utf-8")
        match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL | re.MULTILINE)
        if match:
            import yaml
            data = yaml.safe_load(match.group(1))
            data["path"] = str(path.parent)
            return data
        return {"name": path.parent.name, "description": "No description", "version": "0.0.0"}

    def install_from_local(self, source_path):
        src = Path(source_path)
        if not src.exists(): return False, "Source introuvable"
        dest = self.tools_dir / src.name
        if dest.exists(): return False, "Skill déjà installé"
        shutil.copytree(src, dest)
        return True, f"Skill '{src.name}' installé."

    def install_from_url(self, url):
        # Logique simplifiée pour l'exemple
        return False, "Installation par URL non implémentée dans cette version."
