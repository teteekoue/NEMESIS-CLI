#!/usr/bin/env python3
"""
Script de test d'upload — teste 20+ fournisseurs pour trouver ceux qui acceptent
les requetes automatisees sans captcha.
Usage: python test_upload.py [fichier]
"""
import requests
import sys
import os
import time

# Fichier a uploader (par defaut: integration.txt)
TARGET_FILE = sys.argv[1] if len(sys.argv) > 1 else "../integration.txt"

if not os.path.exists(TARGET_FILE):
    print(f"ERREUR: Fichier introuvable: {TARGET_FILE}")
    sys.exit(1)

print(f"Test d'upload avec: {TARGET_FILE} ({os.path.getsize(TARGET_FILE)} octets)")
print("=" * 70)

# Fournisseurs a tester (nom, url, methode, headers optionnels, extracteur d'URL)
PROVIDERS = [
    # 1. oshi.at - service minimaliste
    ("oshi.at", {
        "url": "https://oshi.at",
        "files_key": "file",
        "extractor": lambda r: r.text.strip() if r.status_code == 200 else None,
    }),

    # 2. litterbox.catbox.moe
    ("litterbox", {
        "url": "https://litterbox.catbox.moe/resources/internals/api.php",
        "files_key": "fileToUpload",
        "data": {"reqtype": "fileupload", "time": "1h"},
        "extractor": lambda r: r.text.strip() if r.status_code == 200 else None,
    }),

    # 3. file.io
    ("file.io", {
        "url": "https://file.io",
        "files_key": "file",
        "extractor": lambda r: r.json().get("link") if r.status_code == 200 else None,
    }),

    # 4. transfer.sh
    ("transfer.sh", {
        "url": "https://transfer.sh",
        "files_key": "file",
        "extractor": lambda r: r.text.strip() if r.status_code == 200 else None,
    }),

    # 5. pixeldrain
    ("pixeldrain", {
        "url": "https://pixeldrain.com/api/file",
        "files_key": "file",
        "extractor": lambda r: f"https://pixeldrain.com/u/{r.json().get('id')}" if r.status_code == 200 else None,
    }),

    # 6. gofile.io
    ("gofile.io", {
        "url": "https://store1.gofile.io/uploadFile",
        "files_key": "file",
        "extractor": lambda r: r.json().get("data", {}).get("downloadPage") if r.status_code == 200 else None,
    }),

    # 7. tmpfiles.org
    ("tmpfiles.org", {
        "url": "https://tmpfiles.org/api/v1/upload",
        "files_key": "file",
        "extractor": lambda r: r.json().get("data", {}).get("url", "").replace("tmpfiles.org/", "tmpfiles.org/dl/") if r.status_code == 200 and r.json().get("status") == "success" else None,
    }),

    # 8. cyberdrop.me
    ("cyberdrop", {
        "url": "https://api.cyberdrop.me/api/upload",
        "files_key": "file",
        "extractor": lambda r: r.json().get("url") if r.status_code == 200 else None,
    }),

    # 9. uguu.se
    ("uguu.se", {
        "url": "https://uguu.se/upload",
        "files_key": "files[]",
        "extractor": lambda r: r.json().get("files", [{}])[0].get("url") if r.status_code == 200 else None,
    }),

    # 10. s-ul.eu
    ("s-ul.eu", {
        "url": "https://s-ul.eu/api/v1/upload",
        "files_key": "file",
        "headers": {"User-Agent": "ShareX/15.0"},
        "data": {"wizard": "false", "max_downloads": "0"},
        "extractor": lambda r: r.json().get("url") if r.status_code == 200 else None,
    }),

    # 11. x0.at
    ("x0.at", {
        "url": "https://x0.at",
        "files_key": "file",
        "extractor": lambda r: r.text.strip() if r.status_code == 200 else None,
    }),

    # 12. envs.sh
    ("envs.sh", {
        "url": "https://envs.sh",
        "files_key": "file",
        "extractor": lambda r: r.text.strip() if r.status_code == 200 else None,
    }),

    # 13. bashupload.com
    ("bashupload", {
        "url": "https://bashupload.com",
        "files_key": "file",
        "extractor": lambda r: r.text.strip().split("upload/")[-1].strip() if r.status_code == 200 else None,
    }),

    # 14. temp.sh
    ("temp.sh", {
        "url": "https://temp.sh/upload",
        "files_key": "file",
        "extractor": lambda r: r.text.strip() if r.status_code == 200 else None,
    }),

    # 15. keep.sh
    ("keep.sh", {
        "url": "https://keep.sh",
        "files_key": "file",
        "extractor": lambda r: r.text.strip() if r.status_code == 200 else None,
    }),

    # 16. t.opnxng.com
    ("opnxng", {
        "url": "https://t.opnxng.com/upload",
        "files_key": "file",
        "extractor": lambda r: r.text.strip() if r.status_code == 200 else None,
    }),

    # 17. 0x0.st (pour reference - on sait qu'il est down)
    ("0x0.st", {
        "url": "https://0x0.st",
        "files_key": "file",
        "extractor": lambda r: r.text.strip() if r.status_code == 200 and r.text.startswith("http") else None,
    }),

    # 18. filebin.net
    ("filebin.net", {
        "url": "https://filebin.net",
        "files_key": "file",
        "extractor": lambda r: f"https://filebin.net/{r.json().get('bin', {}).get('id')}" if r.status_code in (200, 201) else None,
    }),

    # 19. tiiny.host
    ("tiiny.host", {
        "url": "https://api.tiiny.host/v1/upload",
        "files_key": "file",
        "extractor": lambda r: r.json().get("url") if r.status_code == 200 else None,
    }),

    # 20. pomf.lain.la
    ("pomf.lain.la", {
        "url": "https://pomf.lain.la/upload.php",
        "files_key": "files[]",
        "extractor": lambda r: r.json().get("files", [{}])[0].get("url") if r.status_code == 200 else None,
    }),

    # 21. catbox.moe (direct)
    ("catbox.moe", {
        "url": "https://catbox.moe/user/api.php",
        "files_key": "fileToUpload",
        "data": {"reqtype": "fileupload"},
        "extractor": lambda r: r.text.strip() if r.status_code == 200 else None,
    }),

    # 22. free.keep.sh
    ("free.keep.sh", {
        "url": "https://free.keep.sh",
        "files_key": "file",
        "extractor": lambda r: r.text.strip() if r.status_code == 200 else None,
    }),
]


success_count = 0
fail_count = 0

for name, config in PROVIDERS:
    try:
        filename = os.path.basename(TARGET_FILE)
        with open(TARGET_FILE, "rb") as f:
            files = {config["files_key"]: (filename, f)}
            data = config.get("data", {})
            headers = config.get("headers", {})
            
            resp = requests.post(
                config["url"],
                files=files,
                data=data,
                headers=headers,
                timeout=15
            )
        
        url = config["extractor"](resp)
        
        if url:
            print(f"[OK] {name:20s} → {url}")
            success_count += 1
        else:
            print(f"[KO] {name:20s} → HTTP {resp.status_code} | {resp.text[:100].strip()}")
            fail_count += 1
    
    except requests.exceptions.Timeout:
        print(f"[KO] {name:20s} → TIMEOUT")
        fail_count += 1
    except requests.exceptions.ConnectionError:
        print(f"[KO] {name:20s} → CONNEXION REFUSEE")
        fail_count += 1
    except Exception as e:
        print(f"[KO] {name:20s} → ERREUR: {str(e)[:80]}")
        fail_count += 1
    
    time.sleep(0.5)  # Pause pour ne pas flooder

print("=" * 70)
print(f"Resultat: {success_count} succes, {fail_count} echecs sur {len(PROVIDERS)} fournisseurs")
print(f"Fichiers utilisables: ceux marques [OK] ci-dessus")
