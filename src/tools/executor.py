"""Exécuteur d'outils."""
import os, subprocess, re, fnmatch
from pathlib import Path
from typing import Generator


class ToolExecutor:
    def __init__(self, workspace="./workspace", mcp_manager=None):
        self.workspace = os.path.abspath(workspace)
        self.mcp_manager = mcp_manager

    def execute(self, tool_name: str, arguments: dict) -> dict:
        # Vérifier si c'est un outil MCP
        if tool_name.startswith("mcp__"):
            real_name = tool_name[5:]
            if self.mcp_manager:
                result = self.mcp_manager.call_tool(real_name, arguments)
                return {
                    "success": not result.get("isError", False),
                    "output": str(result.get("content", "")),
                    "error": "" if not result.get("isError") else str(result)
                }
            return {"success": False, "output": "", "error": "MCP non configuré"}

        handler = getattr(self, f"_exec_{tool_name}", None)
        if not handler:
            return {"success": False, "output": "", "error": f"Outil inconnu: {tool_name}"}
        try:
            return handler(arguments)
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _exec_bash(self, args):
        cmd = args["command"]
        timeout = args.get("timeout", 300)
        cwd = args.get("working_dir", self.workspace)
        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=cwd)
            output = proc.stdout
            if proc.stderr:
                output += "\n[STDERR]\n" + proc.stderr
            max_out = 500000
            if len(output) > max_out:
                output = output[:max_out] + "\n[TRONQUÉ]"
            return {
                "success": proc.returncode == 0,
                "output": output,
                "error": "" if proc.returncode == 0 else f"Exit code: {proc.returncode}"
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": f"Timeout après {timeout}s"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _exec_read_file(self, args):
        path = self._resolve(args["path"])
        if not os.path.isfile(path):
            return {"success": False, "output": "", "error": f"Fichier introuvable: {path}"}
        try:
            with open(path, "r", errors="replace") as f:
                lines = f.readlines()
            offset = max(0, args.get("offset", 1) - 1)
            limit = args.get("limit", 200)
            selected = lines[offset:offset + limit]
            numbered = "".join(f"{i + offset + 1:>6}\t{line}" for i, line in enumerate(selected))
            return {"success": True, "output": numbered, "total_lines": len(lines)}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _exec_write_file(self, args):
        path = self._resolve(args["path"])
        content = args["content"]
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            return {"success": True, "output": f"Fichier écrit: {path} ({len(content)} chars)", "error": ""}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _exec_edit_file(self, args):
        path = self._resolve(args["path"])
        old_t = args["old_text"]
        new_t = args["new_text"]
        if not os.path.isfile(path):
            return {"success": False, "output": "", "error": f"Fichier introuvable: {path}"}
        try:
            with open(path, "r") as f:
                content = f.read()
            if old_t not in content:
                return {"success": False, "output": "", "error": "Texte à remplacer non trouvé"}
            new_content = content.replace(old_t, new_t, 1)
            with open(path, "w") as f:
                f.write(new_content)
            return {"success": True, "output": f"Remplacement effectué dans {path}", "error": ""}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _exec_list_dir(self, args):
        path = self._resolve(args["path"])
        recursive = args.get("recursive", False)
        if not os.path.isdir(path):
            return {"success": False, "output": "", "error": f"Répertoire introuvable: {path}"}
        try:
            if recursive:
                items = []
                for root, dirs, files in os.walk(path):
                    for f in sorted(files):
                        items.append(os.path.join(root, f))
                    for d in sorted(dirs):
                        items.append(os.path.join(root, d) + "/")
            else:
                items = sorted(os.listdir(path))
            return {"success": True, "output": "\n".join(items) if isinstance(items, list) else str(items), "error": ""}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _exec_search_files(self, args):
        pattern = args["pattern"]
        path = self._resolve(args["path"])
        file_pat = args.get("file_pattern", "*")
        results = []
        try:
            regex = re.compile(pattern)
            for root, dirs, files in os.walk(path):
                for fname in files:
                    if not fnmatch.fnmatch(fname, file_pat):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "r", errors="replace") as f:
                            for i, line in enumerate(f, 1):
                                if regex.search(line):
                                    results.append(f"{fpath}:{i}: {line.strip()[:200]}")
                    except Exception:
                        pass
                    if len(results) > 100:
                        break
            return {
                "success": True,
                "output": "\n".join(results) if results else "Aucun résultat",
                "match_count": len(results)
            }
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _resolve(self, path):
        if os.path.isabs(path):
            return path
        return os.path.join(self.workspace, path)
