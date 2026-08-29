#!/usr/bin/env python3
"""Bridge provider - communique avec l'API Bridge sur Android."""

import requests
import json
import time
import os
import urllib.parse
from typing import Dict, Any

from providers.base import BaseProvider


class BridgeProvider(BaseProvider):
    """Provider pour l'API Bridge Android (Polling /result)."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        bridge_cfg = config.get("bridge", {})
        self.host = bridge_cfg.get("host", "192.168.1.67")
        self.port = bridge_cfg.get("port", 8080)
        self.base_url = f"http://{self.host}:{self.port}"
        self.max_retries = 3
        self.retry_delay = 5
        self._conversation = []

    def test_connection(self) -> bool:
        try:
            requests.head(f"{self.base_url}/", timeout=5)
            return True
        except Exception:
            return False

    def _extract_text(self, data: str) -> str:
        if not data:
            return ""
        try:
            json_data = json.loads(data)
            if isinstance(json_data, dict):
                for key in ["response", "text", "message", "content", "result"]:
                    if key in json_data:
                        return str(json_data[key])
            return json.dumps(json_data)
        except json.JSONDecodeError:
            return data

    def send_message(self, message: str) -> Dict[str, Any]:
        last_error = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.get(
                    f"{self.base_url}/ask", params={"q": message}, timeout=30
                )
                job_id = resp.text.strip()

                if not job_id or len(job_id) < 5:
                    last_error = f"Job ID invalide: '{job_id}'"
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay)
                        continue
                    return {"success": False, "error": last_error}

                max_polls = 200
                polls_done = 0

                while polls_done < max_polls:
                    try:
                        poll_res = requests.get(
                            f"{self.base_url}/result?id={job_id}", timeout=30
                        )
                        result = poll_res.text.strip()

                        if result == "STILL_WORKING":
                            polls_done += 1
                            time.sleep(3)
                            continue

                        if result == "Job introuvable":
                            polls_done += 1
                            if polls_done <= 3:
                                time.sleep(2)
                                continue
                            return {
                                "success": False,
                                "error": f"Job {job_id} introuvable apres {polls_done} tentatives",
                            }

                        resp_text = self._extract_text(result)
                        self._conversation.append({"role": "user", "content": message})
                        self._conversation.append({"role": "assistant", "content": resp_text})
                        return {"success": True, "response": resp_text}

                    except requests.exceptions.Timeout:
                        polls_done += 1
                        continue
                    except requests.exceptions.ConnectionError:
                        polls_done += 1
                        time.sleep(2)
                        continue

                return {"success": False, "error": "Timeout: pas de reponse apres 10 minutes"}

            except requests.exceptions.Timeout:
                last_error = "Timeout envoi message"
            except requests.exceptions.ConnectionError as e:
                last_error = f"Connexion refusee: {e}"
            except Exception as e:
                last_error = str(e)

            if attempt < self.max_retries:
                time.sleep(self.retry_delay)
                continue

        return {"success": False, "error": f"Echec apres {self.max_retries} tentatives: {last_error}"}

    def upload_file(self, path: str) -> Dict[str, Any]:
        try:
            filename = os.path.basename(path)
            url = f"{self.base_url}/upload?file={urllib.parse.quote(filename)}"
            with open(path, "rb") as f:
                res = requests.post(url, files={"file": f}, timeout=None)
                return res.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def ask_with_file(self, path: str, question: str) -> Dict[str, Any]:
        try:
            with open(path, "rb") as f:
                res = requests.post(
                    f"{self.base_url}/ask-with-file",
                    files={"file": f},
                    data={"q": question},
                    timeout=None,
                )
                return {"success": True, "response": res.text}
        except Exception as e:
            return {"success": False, "error": str(e)}
