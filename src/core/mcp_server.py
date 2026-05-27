import sys, json

# Serveur MCP minimaliste intégré
# Il expose des outils simples que l'IA peut appeler
def main():
    while True:
        try:
            line = sys.stdin.readline()
            if not line: break
            req = json.loads(line)
            
            method = req.get("method")
            if method == "tools/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req.get("id"),
                    "result": {
                        "tools": [
                            {"name": "read_file", "description": "Lit un fichier", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
                            {"name": "list_files", "description": "Liste les fichiers", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}
                        ]
                    }
                }
            elif method == "tools/call":
                # Logique simplifiée pour l'exemple
                resp = {
                    "jsonrpc": "2.0",
                    "id": req.get("id"),
                    "result": {"content": [{"type": "text", "text": "Execution simulee de l'outil"}]}
                }
            else:
                resp = {"jsonrpc": "2.0", "id": req.get("id"), "error": {"code": -32601, "message": "Method not found"}}
            
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception:
            break

if __name__ == "__main__":
    main()
