#!/usr/bin/env python3
"""Module d'execution d'actions pour l'agent CLI"""
import os, subprocess, sys, json, signal, time, re, builtins, logging
from datetime import datetime

from pathlib import Path
from typing import Dict, Any, Generator
from uploader import FileUploader
from src.core.mcp_manager import MCPManager

mcp_mgr = MCPManager()

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
                if time.time() - start > 600:
                    process.kill()
                    yield {"success": False, "stdout": "".join(full_output) + "\n[TIMEOUT] Commande depasse 10 minutes, arretee."}
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

    def _normalize_whitespace(self, text):
        lines = []
        for line in text.splitlines():
            lines.append(re.sub(r'[ \t]+', ' ', line).strip())
        return '\n'.join(lines)

    def _strip_indent(self, text):
        lines = []
        for line in text.splitlines():
            lines.append(line.lstrip())
        return '\n'.join(lines)

    def _levenshtein_ratio(self, a, b):
        if not a and not b: return 1.0
        if not a or not b: return 0.0
        m, n = len(a), len(b)
        prev = builtins.list(range(n + 1))
        curr = [0] * (n + 1)
        for i in range(1, m + 1):
            curr[0] = i
            for j in range(1, n + 1):
                cost = 0 if a[i-1] == b[j-1] else 1
                curr[j] = min(prev[j] + 1, curr[j-1] + 1, prev[j-1] + cost)
            prev, curr = curr, prev
        return 1.0 - (prev[n] / max(m, n))

    def _find_block_position(self, original_content, normalized_search, normalized_full, level):
        pos = normalized_full.find(normalized_search)
        if pos == -1: return -1, -1
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
        start_pos = sum(len(orig_lines[i]) for i in range(line_count))
        end_line = min(line_count + len(search_lines), len(orig_lines))
        end_pos = start_pos + sum(len(orig_lines[i]) for i in range(line_count, end_line))
        return start_pos, end_pos

    def _search_and_replace_block(self, content, search_block, replace_block, file_path_for_errors=""):
        count = content.count(search_block)
        if count == 1:
            return content.replace(search_block, replace_block, 1), True, None
        elif count > 1:
            return content, False, f"Bloc trouve {count} fois. Ajoute du contexte."
        norm_search = self._normalize_whitespace(search_block)
        norm_content = self._normalize_whitespace(content)
        if norm_content.count(norm_search) == 1:
            start, end = self._find_block_position(content, norm_search, norm_content, "ws")
            if start >= 0: return content[:start] + replace_block + content[end:], True, None
        noindent_search = self._strip_indent(search_block)
        noindent_content = self._strip_indent(content)
        if noindent_content.count(noindent_search) == 1:
            start, end = self._find_block_position(content, noindent_search, noindent_content, "indent")
            if start >= 0: return content[:start] + replace_block + content[end:], True, None
        return content, False, "Bloc SEARCH introuvable."

    def replace_file(self, path, content):
        try:
            file_path = self.resolve_path(path)
            if not file_path.exists(): return {"success": False, "stdout": "Fichier introuvable"}
            with open(file_path, "r", encoding="utf-8") as f: original = f.read()
            blocks = content.split("<<<<<<< SEARCH")
            if len(blocks) < 2: return {"success": False, "stdout": "Format invalide"}
            modified = original
            replacements = 0
            for block in blocks[1:]:
                if ">>>>>>> REPLACE" not in block or "=======" not in block: continue
                parts = block.split("=======", 1)
                search_part = parts[0].strip()
                replace_part = parts[1].split(">>>>>>> REPLACE")[0].strip()
                new_content, success, error = self._search_and_replace_block(modified, search_part, replace_part)
                if success:
                    modified = new_content
                    replacements += 1
            if replacements == 0: return {"success": False, "stdout": "Aucun remplacement effectué"}
            with open(file_path, "w", encoding="utf-8") as f: f.write(modified)
            return {"success": True, "stdout": f"{replacements} bloc(s) remplace(s)"}
        except Exception as e: return {"success": False, "stdout": str(e)}

    def read_file(self, paths):
        MAX_SIZE = 10 * 1024 * 1024
        temp_files = []
        try:
            resolved = []
            for p in paths:
                fp = self.resolve_path(p.strip())
                if not fp.exists(): return {"success": False, "stdout": f"Fichier introuvable: {p}"}
                if fp.stat().st_size > MAX_SIZE: return {"success": False, "stdout": f"Fichier trop gros: {fp.name}"}
                resolved.append(fp)
            if len(resolved) == 1:
                src = resolved[0]
                with open(src, "r", encoding="utf-8", errors="replace") as f: content = f.read()
                txt_path = self.workspace_root / (src.stem + ".txt")
                with open(txt_path, "w", encoding="utf-8") as f: f.write(content)
                url = self.uploader.upload(str(txt_path))
                txt_path.unlink()
                return {"success": True, "stdout": f"Fichier uploade: {url}"}
            else:
                code_path = self.workspace_root / "code.txt"
                with open(code_path, "w", encoding="utf-8") as out:
                    for src in resolved:
                        with open(src, "r", encoding="utf-8", errors="replace") as f: content = f.read()
                        out.write(f"=== {src.name} ===\n{content}\n\n")
                url = self.uploader.upload(str(code_path))
                code_path.unlink()
                return {"success": True, "stdout": f"Fichiers uploades: {url}"}
        except Exception as e: return {"success": False, "stdout": str(e)}

    def check_process(self, pid):
        if pid not in self.processes: return {"success": False, "stdout": "PID inconnu"}
        try: os.kill(pid, 0)
        except OSError: return {"success": True, "stdout": f"PID {pid} termine."}
        return {"success": True, "stdout": f"PID {pid} actif."}

    def kill_process(self, pid):
        try: os.kill(pid, signal.SIGTERM)
        except: pass
        return {"success": True, "stdout": f"PID {pid} arrete."}

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
                yield self.replace_file(lines[0].strip(), lines[1])
            elif action_type == "read":
                yield self.read_file([x.strip() for x in content.split("|") if x.strip()])
            elif action_type == "list_dir":
                yield self.list_dir(content)
            elif action_type == "status":
                yield self.check_process(int(content.strip()))
            elif action_type == "kill_process":
                yield self.kill_process(int(content.strip()))
            else:
                yield {"success": False, "stdout": f"Action inconnue: {action_type}"}
        except Exception as e:
            yield {"success": False, "stdout": str(e)}

def create_executor_from_config(config, bridge=None):
    workspace = config.get("security", {}).get("workspace", "./workspace")
    return ActionExecutor(workspace=workspace, bridge=bridge)
