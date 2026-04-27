#!/usr/bin/env python3
"""
Service d'upload de fichiers pour NEMESIS CLI.
Strategie : 6 fournisseurs en cascade, du plus fiable au moins fiable.
Limite : 10 Mo maximum par fichier.
"""
import requests
import os
from typing import Optional


class FileUploader:
    """Upload de fichiers vers des services publics pour partage avec l'IA."""

    MAX_SIZE = 10 * 1024 * 1024  # 10 Mo

    def __init__(self):
        self.timeout = None
        self.providers = [
            self._upload_litterbox,
            self._upload_gofile,
            self._upload_tmpfiles,
            self._upload_uguu,
            self._upload_x0at,
            self._upload_tempsh,
        ]

    def upload(self, file_path: str) -> Optional[str]:
        """Upload un fichier. Retourne l'URL publique ou leve une exception."""
        if not os.path.exists(file_path):
            raise Exception(f"Fichier non trouve: {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size > self.MAX_SIZE:
            size_mb = file_size / (1024 * 1024)
            raise Exception(f"Fichier trop volumineux: {size_mb:.1f} Mo (max 10 Mo)")

        last_error = "Aucun fournisseur disponible"

        for provider in self.providers:
            try:
                url = provider(file_path)
                if url:
                    return url
            except Exception as e:
                last_error = str(e)
                continue

        raise Exception(f"Upload echoue. Derniere erreur: {last_error}")

    def _upload_litterbox(self, file_path: str) -> Optional[str]:
        filename = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            resp = requests.post(
                "https://litterbox.catbox.moe/resources/internals/api.php",
                files={'fileToUpload': (filename, f)},
                data={'reqtype': 'fileupload', 'time': '1h'},
                timeout=self.timeout
            )
        if resp.status_code == 200 and resp.text.strip().startswith("http"):
            return resp.text.strip()
        raise Exception(f"Litterbox HTTP {resp.status_code}")

    def _upload_gofile(self, file_path: str) -> Optional[str]:
        filename = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            resp = requests.post(
                "https://store1.gofile.io/uploadFile",
                files={'file': (filename, f)},
                timeout=self.timeout
            )
        if resp.status_code == 200:
            data = resp.json()
            url = data.get('data', {}).get('downloadPage')
            if url:
                return url
        raise Exception(f"Gofile HTTP {resp.status_code}")

    def _upload_tmpfiles(self, file_path: str) -> Optional[str]:
        filename = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            resp = requests.post(
                "https://tmpfiles.org/api/v1/upload",
                files={'file': (filename, f)},
                timeout=self.timeout
            )
        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'success':
                url = data.get('data', {}).get('url', '')
                return url.replace('tmpfiles.org/', 'tmpfiles.org/dl/')
        raise Exception(f"Tmpfiles HTTP {resp.status_code}")

    def _upload_uguu(self, file_path: str) -> Optional[str]:
        filename = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            resp = requests.post(
                "https://uguu.se/upload",
                files={'files[]': (filename, f)},
                timeout=self.timeout
            )
        if resp.status_code == 200:
            data = resp.json()
            files_list = data.get('files', [])
            if files_list and files_list[0].get('url'):
                return files_list[0]['url']
        raise Exception(f"Uguu HTTP {resp.status_code}")

    def _upload_x0at(self, file_path: str) -> Optional[str]:
        filename = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            resp = requests.post(
                "https://x0.at",
                files={'file': (filename, f)},
                timeout=self.timeout
            )
        if resp.status_code == 200 and resp.text.strip().startswith("http"):
            return resp.text.strip()
        raise Exception(f"x0.at HTTP {resp.status_code}")

    def _upload_tempsh(self, file_path: str) -> Optional[str]:
        filename = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            resp = requests.post(
                "https://temp.sh/upload",
                files={'file': (filename, f)},
                timeout=self.timeout
            )
        if resp.status_code == 200 and resp.text.strip().startswith("http"):
            return resp.text.strip()
        raise Exception(f"Temp.sh HTTP {resp.status_code}")