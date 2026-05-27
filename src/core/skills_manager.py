import os
import shutil
import subprocess
import requests
import zipfile
import io
import yaml
import re
from pathlib import Path
from rich.console import Console

console = Console()

class SkillManager:
    def __init__(self, library_path="tools_library"):
        self.library_path = Path(library_path)
        self.library_path.mkdir(parents=True, exist_ok=True)

    def _get_skill_metadata(self, skill_dir):
        """Lit le fichier SKILL.md pour extraire le nom et la description (compatible Claude Code)."""
        skill_path = self.library_path / skill_dir
        skill_md = skill_path / "SKILL.md"
        
        metadata = {
            "name": skill_dir,
            "description": "Aucune description disponible.",
            "version": "Inconnue"
        }

        if skill_md.exists():
            try:
                content = skill_md.read_text(encoding="utf-8")
                # Recherche du frontmatter YAML entre ---
                match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL | re.MULTILINE)
                if match:
                    data = yaml.safe_load(match.group(1))
                    if isinstance(data, dict):
                        metadata["name"] = data.get("name", metadata["name"])
                        metadata["description"] = data.get("description", metadata["description"])
                        metadata["version"] = data.get("version", metadata["version"])
            except Exception:
                pass # On garde les valeurs par défaut en cas d'erreur de lecture
        
        return metadata

    def list_installed(self):
        """Liste les skills avec leurs métadonnées extraites de SKILL.md."""
        skills = []
        for d in self.library_path.iterdir():
            if d.is_dir() and not d.name.startswith("__"):
                meta = self._get_skill_metadata(d.name)
                skills.append(meta)
        return skills

    def install_from_local(self, source_path):
        """Copie un dossier local dans tools_library."""
        source = Path(source_path)
        if not source.exists():
            return False, f"Chemin introuvable: {source_path}"
        
        dest = self.library_path / source.name
        try:
            shutil.copytree(source, dest, dirs_exist_ok=True)
            return True, f"Skill '{source.name}' installe avec succes."
        except Exception as e:
            return False, str(e)

    def install_from_url(self, url):
        """Télécharge un skill depuis une URL (ZIP ou Git)."""
        if url.endswith(".zip"):
            return self._install_via_zip(url)
        elif url.endswith(".git") or "github.com" in url:
            return self._install_via_git(url)
        else:
            return False, "Format d'URL non reconnu (utilisez .git ou .zip)."

    def _install_via_git(self, url):
        """Clone un dépôt git sans demander d'identifiants."""
        # On essaie d'extraire un nom propre pour le dossier
        repo_name = url.split("/")[-1].replace(".git", "")
        dest = self.library_path / repo_name
        
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        
        try:
            console.print(f"[dim]Clonage de {url}...[/dim]")
            subprocess.run(["git", "clone", "--depth", "1", url, str(dest)], 
                           check=True, capture_output=True, env=env)
            return True, f"Skill '{repo_name}' installe avec succes via Git."
        except subprocess.CalledProcessError as e:
            return False, f"Erreur Git: {e.stderr.decode().strip()}"
        except Exception as e:
            return False, str(e)

    def _install_via_zip(self, url):
        """Télécharge et extrait un ZIP."""
        try:
            console.print(f"[dim]Telechargement du ZIP depuis {url}...[/dim]")
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                z.extractall(self.library_path)
                return True, "Skill installe avec succes via ZIP."
        except Exception as e:
            return False, f"Erreur ZIP: {str(e)}"
