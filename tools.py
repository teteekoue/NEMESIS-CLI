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

    # =====================================================================
    # NOUVEAU SYSTEME REPLACE (Search & Replace en cascade 4 niveaux)
    # =====================================================================

    def _normalize_whitespace(self, text):
        """Niveau 2 : reduit les espaces multiples a un seul, strip debut/fin de ligne."""
        lines = []
        for line in text.splitlines():
            lines.append(re.sub(r'[ \t]+', ' ', line).strip())
        return '\n'.join(lines)

    def _strip_indent(self, text):
        """Niveau 3 : supprime toute indentation en debut de ligne."""
        lines = []
        for line in text.splitlines():
            lines.append(line.lstrip())
        return '\n'.join(lines)

    def _levenshtein_ratio(self, a, b):
        """Niveau 4 : ratio de similarite entre deux chaines (0.0 a 1.0)."""
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        m, n = len(a), len(b)
        if m == 0 or n == 0:
            return 0.0
        # Matrice optimisee (une seule ligne)
        prev = list(range(n + 1))
        curr = [0] * (n + 1)
        for i in range(1, m + 1):
            curr[0] = i
            for j in range(1, n + 1):
                cost = 0 if a[i-1] == b[j-1] else 1
                curr[j] = min(prev[j] + 1, curr[j-1] + 1, prev[j-1] + cost)
            prev, curr = curr, prev
        distance = prev[n]
        max_len = max(m, n)
        return 1.0 - (distance / max_len)

    def _find_block_position(self, original_content, normalized_search, normalized_full, level):
        """Retrouve la position du bloc SEARCH dans le contenu original."""
        pos = normalized_full.find(normalized_search)
        if pos == -1:
            return -1, -1

        # Compter les caracteres pour retrouver la position dans l'original
        orig_lines = original_content.splitlines(True)
        norm_lines = normalized_full.splitlines(True)
        search_lines = normalized_search.splitlines(True)

        line_count = 0
        char_count = 0
        for i, line in enumerate(norm_lines):
            if char_count >= pos:
                line_count = i
                break
            char_count += len(line)

        # Compter la longueur du bloc original correspondant
        start_pos = 0
        for i in range(line_count):
            start_pos += len(orig_lines[i])

        end_line = min(line_count + len(search_lines), len(orig_lines))
        end_pos = start_pos
        for i in range(line_count, end_line):
            end_pos += len(orig_lines[i])

        return start_pos, end_pos

    def _search_and_replace_block(self, content, search_block, replace_block, file_path_for_errors=""):
        """
        Cherche search_block dans content avec 4 niveaux de tolerance,
        puis le remplace par replace_block.
        Retourne (new_content, success, error_message).
        """
        # Niveau 1 : Exact
        count = content.count(search_block)
        if count == 1:
            new_content = content.replace(search_block, replace_block, 1)
            return new_content, True, None
        elif count > 1:
            return content, False, f"Bloc trouve {count} fois dans le fichier. Ajoute plus de contexte pour le rendre unique."

        # Niveau 2 : Normalisation des espaces
        norm_search = self._normalize_whitespace(search_block)
        norm_content = self._normalize_whitespace(content)
        count = norm_content.count(norm_search)
        if count == 1:
            start, end = self._find_block_position(content, norm_search, norm_content, "whitespace")
            if start >= 0:
                new_content = content[:start] + replace_block + content[end:]
                return new_content, True, None
            return content, False, "Erreur interne : bloc normalise trouve mais position introuvable."
        elif count > 1:
            return content, False, f"Bloc trouve {count} fois apres normalisation. Ajoute plus de contexte."

        # Niveau 3 : Ignore l'indentation
        noindent_search = self._strip_indent(search_block)
        noindent_content = self._strip_indent(content)
        count = noindent_content.count(noindent_search)
        if count == 1:
            start, end = self._find_block_position(content, noindent_search, noindent_content, "noindent")
            if start >= 0:
                new_content = content[:start] + replace_block + content[end:]
                return new_content, True, None
            return content, False, "Erreur interne : bloc sans indentation trouve mais position introuvable."
        elif count > 1:
            return content, False, f"Bloc trouve {count} fois apres suppression de l'indentation. Ajoute plus de contexte."

        # Niveau 4 : Flou (Levenshtein)
        best_ratio = 0.0
        best_start = -1
        best_end = -1
        lines = content.splitlines(True)
        search_lines = search_block.splitlines(True)
        search_len = len(search_block)
        total_len = len(content)

        for i in range(len(lines) - len(search_lines) + 1):
            # Fenetre approximative basee sur les lignes
            window_start = sum(len(l) for l in lines[:i])
            window_end = window_start + sum(len(l) for l in lines[i:i+len(search_lines)])
            window_end = min(window_end, total_len)
            window_text = content[window_start:window_end]
            ratio = self._levenshtein_ratio(search_block, window_text)
            if ratio > best_ratio:
                best_ratio = ratio
                best_start = window_start
                best_end = window_end

        if best_ratio >= 0.85:
            new_content = content[:best_start] + replace_block + content[best_end:]
            return new_content, True, None

        # Echec total : generer un feedback utile
        context_lines = []
        file_lines = content.splitlines()
        for idx, line in enumerate(file_lines[:20], 1):
            if search_block.splitlines()[0].strip()[:20] in line:
                start_ctx = max(0, idx - 3)
                end_ctx = min(len(file_lines), idx + 5)
                for ln in range(start_ctx, end_ctx):
                    context_lines.append(f"   {ln+1}| {file_lines[ln]}")
                break
        if not context_lines:
            total_lines = len(file_lines)
            mid = total_lines // 2
            for ln in range(max(0, mid-3), min(total_lines, mid+5)):
                context_lines.append(f"   {ln+1}| {file_lines[ln]}")

        ctx_str = '\n'.join(context_lines[:15]) if context_lines else "Fichier vide ou illisible."
        return content, False, f"Bloc SEARCH introuvable (meme avec tolerance floue).\nContenu actuel autour de la zone probable :\n{ctx_str}\nLe fichier a peut-etre deja ete modifie ? Verifie avec read ou cat."

    def replace_file(self, path, content):
        """
        Remplace un ou plusieurs blocs dans un fichier.
        Format : le nom du fichier sur la premiere ligne, puis blocs SEARCH/REPLACE.
        Chaque bloc est traite sequentiellement (l'ordre compte).
        """
        try:
            file_path = self.resolve_path(path)
            if not file_path.exists():
                return {"success": False, "stdout": f"Fichier introuvable: {path}"}

            with open(file_path, "r", encoding="utf-8") as f:
                original = f.read()

            # Parser les blocs : le contenu est deja nettoye par _extract_action_content
            # Format attendu : <<<<<<< SEARCH\n...\n=======\n...\n>>>>>>> REPLACE
            blocks = content.split("<<<<<<< SEARCH")
            if len(blocks) < 2:
                return {"success": False, "stdout": "Aucun bloc SEARCH trouve. Format attendu : <<<<<<< SEARCH\\n...\\n=======\\n...\\n>>>>>>> REPLACE"}

            modified = original
            replacements_done = 0
            errors = []

            for block in blocks[1:]:
                if ">>>>>>> REPLACE" not in block:
                    continue
                if "=======" not in block:
                    continue

                parts = block.split("=======", 1)
                if len(parts) != 2:
                    continue

                search_part = parts[0].strip()
                replace_part = parts[1].split(">>>>>>> REPLACE")[0].strip()

                if not search_part:
                    errors.append("Bloc SEARCH vide - ignore.")
                    continue

                new_content, success, error = self._search_and_replace_block(
                    modified, search_part, replace_part, str(file_path)
                )

                if success:
                    modified = new_content
                    replacements_done += 1
                elif error:
                    errors.append(error)

            if replacements_done == 0:
                return {"success": False, "stdout": f"Aucun remplacement effectue.\nErreurs :\n" + '\n'.join(f'  - {e}' for e in errors)}

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(modified)

            msg = f"Replace: {replacements_done} bloc(s) remplace(s) dans {file_path}"
            if errors:
                msg += f"\nBlocs ignores :\n" + '\n'.join(f'  - {e}' for e in errors)

            if file_path.suffix in [".py", ".sh"]:
                val = self.validate_code(str(file_path))
                if not val["success"]:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(original)
                    return {"success": False, "stdout": f"Erreur de syntaxe apres replace - modifications annulees."}

            return {"success": True, "stdout": msg}
        except Exception as e:
            return {"success": False, "stdout": str(e)}

    # =====================================================================
    # FIN DU NOUVEAU SYSTEME REPLACE
    # =====================================================================

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
            elif action_type == "replace":
                lines = content.strip().split("\n", 1)
                if len(lines) < 2:
                    yield {"success": False, "stdout": "Format replace invalide. Attendu: fichier\\n<<<<<<< SEARCH..."}
                else:
                    file_path = lines[0].strip()
                    replace_content = lines[1] if len(lines) > 1 else ""
                    yield self.replace_file(file_path, replace_content)
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
