#!/usr/bin/env python3
"""Module d'execution d'actions pour l'agent CLI"""
import os, subprocess, sys, json, signal, time, shutil, re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Generator
from uploader import FileUploader

class ActionExecutor:
    def __init__(self, workspace="./workspace", bridge=None):
        self.workspace_root = Path(workspace).resolve()
        if not self.workspace_root.exists():
            self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.bridge = bridge
        self.uploader = FileUploader()
        self.processes = {}

    def resolve_path(self, path):
        p = Path(path.strip())
        return p.resolve() if p.is_absolute() else (self.workspace_root / p).resolve()

    def list_dir(self, path):
        try:
            target = self.resolve_path(path)
            if not target.is_dir():
                return {"success": False, "stdout": "Erreur: Dossier non trouve"}
            result = subprocess.run(["tree", "-L", "2", str(target)], capture_output=True, text=True)
            return {"success": result.returncode == 0, "stdout": result.stdout if result.returncode == 0 else result.stderr}
        except Exception as e:
            return {"success": False, "stdout": str(e)}

    def execute_bash_live(self, command, async_mode=False):
        if async_mode:
            log_path = self.workspace_root / f"proc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            proc = subprocess.Popen(f"{command} > '{log_path}' 2>&1", shell=True, executable="/bin/bash", preexec_fn=os.setsid, cwd=self.workspace_root)
            self.processes[proc.pid] = {"cmd": command, "log": str(log_path), "start": datetime.now().isoformat()}
            yield {"success": True, "stdout": f"PID {proc.pid} lance en arriere-plan.\nLogs: {log_path.name}"}
        else:
            full_output = []
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, executable="/bin/bash", cwd=self.workspace_root)
            start = time.time()
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    full_output.append(line)
                    yield {"partial": True, "line": line}
                if time.time() - start > 300:
                    process.kill()
                    yield {"success": False, "stdout": "".join(full_output) + "\n[TIMEOUT] Commande depasse 5 minutes, arretee."}
                    return
            yield {"success": process.returncode == 0, "stdout": "".join(full_output)}

    def validate_code(self, file_path):
        target = self.resolve_path(file_path)
        if not target.exists():
            return {"success": False, "stdout": "Fichier inexistant"}
        if target.suffix == ".py":
            result = subprocess.run([sys.executable, "-m", "py_compile", str(target)], capture_output=True, text=True)
        else:
            result = subprocess.run(["sh", "-n", str(target)], capture_output=True, text=True)
        return {"success": result.returncode == 0, "stdout": result.stdout + result.stderr}

    def _extract_action_content(self, content):
        """Extrait tout le texte entre les triples backticks englobants."""
        # Regex pour trouver le contenu d'un bloc de code (triple backticks)
        pattern = re.compile(r'^```.*?\n(.*?)\n```$', re.DOTALL | re.MULTILINE)
        match = pattern.search(content.strip())
        return match.group(1).strip() if match else content.strip()

    def smart_write(self, path, content, mode="w"):
        try:
            file_path = self.resolve_path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            clean = self._extract_action_content(content)
            if not clean:
                return {"success": False, "stdout": "Contenu vide apres nettoyage - fichier non ecrit"}
            with open(file_path, mode, encoding="utf-8") as f:
                f.write(clean + "\n")
            msg = f"Fichier ecrit: {file_path} ({len(clean)} caracteres)"
            if file_path.suffix in [".py", ".sh"]:
                val = self.validate_code(str(file_path))
                if not val["success"]:
                    msg += " (attention syntaxe)"
            return {"success": True, "stdout": msg}
        except Exception as e:
            return {"success": False, "stdout": str(e)}

    def patch_file(self, path, start_line, end_line, new_content):
        try:
            file_path = self.resolve_path(path)
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            clean = self._strip_wrapping_backticks(new_content)
            if not clean:
                return {"success": False, "stdout": "Contenu vide apres nettoyage - patch non applique"}
            lines[max(0, start_line-1):end_line] = [l + "\n" for l in clean.splitlines()]
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            msg = f"Patch applique: {file_path}"
            if file_path.suffix in [".py", ".sh"]:
                val = self.validate_code(str(file_path))
                if not val["success"]:
                    msg += " (attention syntaxe)"
            return {"success": True, "stdout": msg}
        except Exception as e:
            return {"success": False, "stdout": str(e)}

    def replace_file(self, path, content):
        """
        Remplace un ou plusieurs blocs dans un fichier.
        Format attendu dans content:
            <<<<<<< SEARCH
            bloc a chercher
            =======
            bloc de remplacement
            >>>>>>> REPLACE

        Supporte plusieurs blocs SEARCH/REPLACE dans une seule action.
        Chaque bloc SEARCH doit etre UNIQUE dans le fichier.
        """
        try:
            file_path = self.resolve_path(path)
            if not file_path.exists():
                return {"success": False, "stdout": f"Fichier introuvable: {path}"}

            # Sauvegarde de securite (checkpoint)
            with open(file_path, "r", encoding="utf-8") as f:
                original = f.read()

            modified = original
            replacements_done = 0
            errors = []

            # Parser les blocs SEARCH/REPLACE avec une Regex robuste
            # Format attendu: SEARCH\n\n```...```\n\nREPLACE\n\n```...```\n\nEND
            # On utilise re.DOTALL pour permettre aux points de matcher les sauts de ligne
            pattern = re.compile(r'SEARCH\s+(.*?)\s+REPLACE\s+(.*?)\s+END', re.DOTALL)
            
            # On cherche le nom du fichier (première ligne)
            lines = content.strip().split("\n", 1)
            file_path = self.resolve_path(lines[0].strip())
            body = lines[1] if len(lines) > 1 else ""
            
            matches = pattern.findall(body)
            if not matches:
                return {"success": False, "stdout": "Format REPLACE invalide. Attendu: Fichier\\nSEARCH\\n...\\nREPLACE\\n...\\nEND"}

            for search_content, replace_content in matches:
                search_part = self._strip_wrapping_backticks(search_content)
                replace_part = self._strip_wrapping_backticks(replace_content)

                if not search_part:
                    errors.append("Bloc SEARCH vide après nettoyage")
                    continue

                # Compter les occurrences
                count = modified.count(search_part)
                if count == 0:
                    errors.append(f"Bloc introuvable: {search_part[:50]}...")
                    continue
                if count > 1:
                    errors.append(f"Bloc trouvé {count} fois (doit être unique): {search_part[:50]}...")
                    continue

                modified = modified.replace(search_part, replace_part, 1)
                replacements_done += 1

            if replacements_done == 0:
                return {"success": False, "stdout": f"Aucun remplacement effectue. Erreurs: {'; '.join(errors) if errors else 'Aucun bloc SEARCH valide trouve'}"}

            # Ecrire le fichier modifie
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(modified)

            msg = f"Replace: {replacements_done} bloc(s) remplace(s) dans {file_path}"
            if errors:
                msg += f" | Erreurs ignorees: {'; '.join(errors)}"
            if file_path.suffix in [".py", ".sh"]:
                val = self.validate_code(str(file_path))
                if not val["success"]:
                    # Restaurer la sauvegarde si erreur de syntaxe
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(original)
                    return {"success": False, "stdout": f"Erreur de syntaxe apres replace - modifications annulees. Verifiez les blocs."}
            return {"success": True, "stdout": msg}
        except Exception as e:
            return {"success": False, "stdout": str(e)}

    def _is_text_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                f.read(1024)
            return True
        except (UnicodeDecodeError, IsADirectoryError):
            return False

    def read_file(self, paths):
        MAX_SIZE = 10 * 1024 * 1024
        temp_files = []
        try:
            resolved = []
            for p in paths:
                fp = self.resolve_path(p.strip())
                if not fp.exists():
                    return {"success": False, "stdout": f"Fichier introuvable: {p.strip()}"}
                if fp.stat().st_size > MAX_SIZE:
                    return {"success": False, "stdout": f"Fichier trop volumineux (>10 Mo): {fp.name}"}
                resolved.append(fp)
            if len(resolved) == 1:
                src = resolved[0]
                if not self._is_text_file(src):
                    url = self.uploader.upload(str(src))
                    return {"success": True, "stdout": f"Fichier binaire uploade directement: {url}"}
                with open(src, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                txt_name = src.stem + ".txt"
                txt_path = self.workspace_root / txt_name
                txt_content = "=== " + src.name + " ===\n" + content
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(txt_content)
                temp_files.append(txt_path)
                url = self.uploader.upload(str(txt_path))
                return {"success": True, "stdout": f"Fichier converti et uploade: {url}"}
            else:
                code_path = self.workspace_root / "code.txt"
                with open(code_path, "w", encoding="utf-8") as out:
                    for i, src in enumerate(resolved):
                        if not self._is_text_file(src):
                            out.write("=== " + src.name + " (BINAIRE - non convertible) ===\n")
                            continue
                        with open(src, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read()
                        out.write("=== " + src.name + " ===\n")
                        out.write(content)
                        if i < len(resolved) - 1:
                            out.write("\n\n" + "=" * 60 + "\n\n")
                temp_files.append(code_path)
                url = self.uploader.upload(str(code_path))
                return {"success": True, "stdout": f"{len(resolved)} fichiers fusionnes et uploades: {url}"}
        except Exception as e:
            return {"success": False, "stdout": str(e)}
        finally:
            for tf in temp_files:
                try:
                    if tf.exists():
                        tf.unlink()
                except Exception:
                    pass

    def check_process(self, pid):
        if pid not in self.processes:
            return {"success": False, "stdout": "PID inconnu"}
        try:
            os.kill(pid, 0)
        except OSError:
            return {"success": True, "stdout": f"PID {pid} termine."}
        with open(self.processes[pid]["log"], "r") as f:
            logs = f.readlines()[-20:]
        return {"success": True, "stdout": f"PID {pid} actif. Logs:\n" + "".join(logs)}

    def kill_process(self, pid):
        if pid not in self.processes:
            return {"success": False, "stdout": "PID inconnu"}
        try:
            os.kill(pid, signal.SIGTERM)
            del self.processes[pid]
        except OSError:
            pass
        return {"success": True, "stdout": f"Processus {pid} arrete."}

    def cleanup_logs(self):
        count = 0
        for pid, info in list(self.processes.items()):
            try:
                os.kill(pid, 0)
            except OSError:
                if os.path.exists(info["log"]):
                    os.remove(info["log"])
                    count += 1
                del self.processes[pid]
        return {"success": True, "stdout": f"Nettoyage : {count} logs supprimes."}

    def execute_pdf_to_text(self, pdf_file_path, output_dir):
        if not shutil.which("soffice"):
            return {"success": False, "stdout": "LibreOffice non installe. sudo apt install libreoffice"}
        try:
            pdf_path = self.resolve_path(pdf_file_path)
            output_path = self.resolve_path(output_dir)
            cmd = f"soffice --headless --convert-to txt:Text --outdir '{output_path}' '{pdf_path}'"
            subprocess.run(cmd, shell=True, executable="/bin/bash")
            txt_path = output_path / (pdf_path.stem + ".txt")
            if txt_path.exists():
                with open(txt_path, "r") as f:
                    return {"success": True, "stdout": f.read()}
            return {"success": False, "stdout": "Echec de l'extraction."}
        except Exception as e:
            return {"success": False, "stdout": str(e)}

    def execute_html_to_pdf(self, html_file_path, output_dir):
        if not shutil.which("soffice"):
            return {"success": False, "stdout": "LibreOffice non installe. sudo apt install libreoffice"}
        try:
            html_path = self.resolve_path(html_file_path)
            output_path = self.resolve_path(output_dir)
            cmd = f"soffice --headless --convert-to pdf --outdir '{output_path}' '{html_path}'"
            subprocess.run(cmd, shell=True, executable="/bin/bash")
            return {"success": True, "stdout": f"PDF genere dans {output_path}"}
        except Exception as e:
            return {"success": False, "stdout": str(e)}

    def execute_upload(self, file_path):
        try:
            target = self.resolve_path(file_path)
            if not target.exists():
                return {"success": False, "stdout": f"Fichier introuvable: {target}"}
            url = self.uploader.upload(str(target))
            return {"success": True, "stdout": f"Fichier uploade: {url}"}
        except Exception as e:
            return {"success": False, "stdout": str(e)}

    def update_tracker(self, project_path, task, status):
        try:
            root = self.resolve_path(project_path)
            todo_file = root / "todo.md"
            json_file = root / "projets.json"
            data = {}
            if json_file.exists():
                with open(json_file, "r") as f:
                    data = json.load(f)
            data[task] = {"status": status, "updated": datetime.now().isoformat()}
            with open(json_file, "w") as f:
                json.dump(data, f, indent=4)
            with open(todo_file, "w") as f:
                f.write("# Taches du Projet\n\n")
                for t, info in data.items():
                    mark = "x" if info["status"] == "done" else " "
                    f.write(f"- [{mark}] {t} ({info['status']})\n")
            return {"success": True, "stdout": f"Tracker mis a jour : {task}"}
        except Exception as e:
            return {"success": False, "stdout": str(e)}

    def apply_patch(self, patch_content):
        """Applique un diff généré par l'IA via la commande système 'patch'."""
        try:
            patch_file = self.workspace_root / "temp_patch.diff"
            clean_patch = self._extract_action_content(patch_content)
            
            with open(patch_file, "w", encoding="utf-8") as f:
                f.write(clean_patch)
            
            cmd = ["patch", "-p0", "-N", "--fuzz=2", "--input", str(patch_file)]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.workspace_root)
            
            if patch_file.exists():
                patch_file.unlink()
            
            if result.returncode == 0:
                return {"success": True, "stdout": "Patch appliqué avec succès."}
            else:
                return {"success": False, "stdout": f"Erreur lors de l'application du patch:\n{result.stderr}"}
        except Exception as e:
            return {"success": False, "stdout": str(e)}

    def execute_action(self, action_type, content):
        try:
            if action_type == "bash":
                p = content.split("|", 1)
                yield from self.execute_bash_live(p[1].strip(), p[0].strip().lower() == "asynchrone")
            elif action_type == "write":
                p = content.split("|", 1)
                yield self.smart_write(p[0].strip(), p[1], "w")
            elif action_type == "append":
                p = content.split("|", 1)
                yield self.smart_write(p[0].strip(), p[1], "a")
            elif action_type == "patch":
                yield self.apply_patch(content)
            elif action_type == "read":
                p = [x.strip() for x in content.split("|") if x.strip()]
                if not p:
                    yield {"success": False, "stdout": "Aucun fichier specifie"}
                else:
                    yield self.read_file(p)
            elif action_type == "list_dir":
                yield self.list_dir(content)
            elif action_type == "validate":
                yield self.validate_code(content)
            elif action_type == "html_to_pdf":
                p = content.split("|")
                yield self.execute_html_to_pdf(p[0].strip(), p[1].strip())
            elif action_type == "pdf_to_text":
                p = content.split("|")
                yield self.execute_pdf_to_text(p[0].strip(), p[1].strip())
            elif action_type == "update_tracker":
                p = content.split("|")
                yield self.update_tracker(p[0].strip(), p[1].strip(), p[2].strip())
            elif action_type == "upload":
                yield self.execute_upload(content.strip())
            elif action_type == "status":
                yield self.check_process(int(content.strip()))
            elif action_type == "kill_process":
                yield self.kill_process(int(content.strip()))
            elif action_type == "cleanup_logs":
                yield self.cleanup_logs()
            elif action_type == "stop_all":
                for pid in list(self.processes.keys()):
                    os.kill(pid, signal.SIGTERM)
                self.processes.clear()
                yield {"success": True, "stdout": "Tout est arrete."}
            else:
                yield {"success": False, "stdout": f"Action inconnue: {action_type}"}
        except Exception as e:
            yield {"success": False, "stdout": str(e)}

def create_executor_from_config(config, bridge=None):
    workspace = config.get("security", {}).get("workspace", "./workspace")
    return ActionExecutor(workspace=workspace, bridge=bridge)
