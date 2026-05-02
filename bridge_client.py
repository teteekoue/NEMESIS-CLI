#!/usr/bin/env python3
"""
Client HTTP pour communiquer avec l'API Bridge (Android)
Gere le protocole specifique : POST /ask puis Polling /result?id=
Tous les timeouts sont desactives pour les taches longues.
Avec mecanisme de retry (3 tentatives) en cas d'echec.
"""
import requests
import json
import time
import os
import urllib.parse
from typing import Optional, Dict, Any


class BridgeClient:
    """Client pour l'API Bridge sur Android (Version Polling /result)"""

    def __init__(self, host: str = "192.168.1.100", port: int = 8080, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{host}:{port}"
        self.max_retries = 3
        self.retry_delay = 5

    def test_connection(self) -> bool:
        try:
            requests.head(f"{self.base_url}/", timeout=None)
            return True
        except:
            return False

    def _extract_text(self, data: str) -> str:
        if not data:
            return ""
        try:
            json_data = json.loads(data)
            if isinstance(json_data, dict):
                for key in ['response', 'text', 'message', 'content', 'result']:
                    if key in json_data:
                        return str(json_data[key])
            return json.dumps(json_data)
        except json.JSONDecodeError:
            return data

    def send_message(self, message: str) -> Dict[str, Any]:
        last_error = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(f"{self.base_url}/ask", data={'q': message}, timeout=None)
                job_id = resp.text.strip()

                while True:
                    poll_res = requests.get(f"{self.base_url}/result?id={job_id}", timeout=None)
                    result = poll_res.text.strip()
                    if result != "STILL_WORKING":
                        return {'success': True, 'response': self._extract_text(result)}
                    time.sleep(3)
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
                    continue
        return {'success': False, 'error': f"Echec apres {self.max_retries} tentatives: {last_error}"}

    def upload_file(self, path: str) -> Dict[str, Any]:
        try:
            filename = os.path.basename(path)
            url = f"{self.base_url}/upload?file={urllib.parse.quote(filename)}"
            with open(path, 'rb') as f:
                res = requests.post(url, files={'file': f}, timeout=None)
                return res.json()
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def ask_with_file(self, path: str, question: str) -> Dict[str, Any]:
        try:
            with open(path, 'rb') as f:
                res = requests.post(f"{self.base_url}/ask-with-file", files={'file': f}, data={'q': question}, timeout=None)
                return {'success': True, 'response': res.text}
        except Exception as e:
            return {'success': False, 'error': str(e)}


def create_client_from_config(config: Dict[str, Any]) -> BridgeClient:
    bridge_config = config.get('bridge', {})
    return BridgeClient(
        host=bridge_config.get('host', '192.168.1.100'),
        port=bridge_config.get('port', 8080),
        timeout=None
    )