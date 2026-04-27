#!/usr/bin/env python3
"""Module d'execution d'actions pour l'agent CLI"""
import os, subprocess, sys, json, signal, time
from datetime import datetime
import shutil
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

    def _clean_backticks(self, content):
        c = content.strip()
        if c.endswith("# EOF"):
            c = c[:-5].strip()
        BTC = chr(96) + chr(96) + chr(96)
        if c.startswith(BTC) and c.endswith(BTC):
            c = c[3:-3].strip()
        return c

    def smart_write(self, path, content, mode="w"):
        try:
            file_path = self.resolve_path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            clean = self._clean_backticks(content)
            with open(file_path, mode, encoding="utf-8") as f:
                f.write(clean + chr(10))
            if file_path.suffix in [".py", ".sh"]:
                val = self.validate_code(str(file_path))
                if not val["success"]:
                    return {"success": False, "stdout": "Erreur de syntaxe detectee"}
            return {"success": True, "stdout": f"Fichier ecrit et valide: {file_path}"}
        except Exception as e:
            return {"success": False, "stdout": str(e)}

    def patch_file(self, path, start_line, end_line, new_content):
        try:
            file_path = self.resolve_path(path)
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            clean = self._clean_backticks(new_content)
            lines[max(0, start_line-1):end_line] = [l + chr(10) for l in clean.splitlines()]
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            if file_path.suffix in [".py", ".sh"]:
                val = self.validate_code(str(file_path))
                if not val["success"]:
                    return {"success": False, "stdout": "Erreur de syntaxe apres patch"}
            return {"success": True, "stdout": f"Patch applique et valide sur {file_path}"}
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
        return {"success": True, "stdout": f"PID {pid} actif. Logs:\n" + ''.join(logs)}

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
            return {"success": False, "stdout": "LibreOffice non installe. Installe-le avec: sudo apt install libreoffice"}
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
            return {"success": False, "stdout": "LibreOffice non installe. Installe-le avec: sudo apt install libreoffice"}
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
            elif action_type == "patch":
                p = content.split("|", 3)
                yield self.patch_file(p[0].strip(), int(p[1]), int(p[2]), p[3])
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
