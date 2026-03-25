"""AI summary provider with OpenAI/Gemini support and rule-based fallback."""

from __future__ import annotations

import json
from typing import Any, Dict

import requests


class AIProvider:
    OPENAI_URL = "https://api.openai.com/v1/chat/completions"
    GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, provider: str = "gemini", api_key: str = ""):
        self.provider = str(provider or "gemini").strip().lower()
        self.api_key = str(api_key or "").strip()
        self.last_status = "idle"
        self.last_error = ""

    def _mark(self, status: str, error: str = ""):
        self.last_status = str(status or "idle")
        self.last_error = str(error or "")

    def available(self) -> bool:
        return bool(self.api_key)

    def summarize_event(self, prompt: str, model: str) -> Dict[str, Any]:
        if not self.available():
            self._mark("disabled", error="ai_api_key_missing")
            raise RuntimeError("ai_api_key_missing")
        if self.provider == "openai":
            return self._summarize_openai(prompt, model)
        return self._summarize_gemini(prompt, model)

    def _summarize_openai(self, prompt: str, model: str) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": str(model or "gpt-5-mini"),
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return JSON only with keys: summary, stance, risk_tags, confidence, action_hint. "
                        "Never include markdown."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        response = requests.post(self.OPENAI_URL, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        payload = response.json()
        choices = payload.get("choices", [])
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("openai_empty_choices")
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        content = message.get("content", "") if isinstance(message, dict) else ""
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("openai_empty_content")
        result = json.loads(content)
        self._mark("ok_with_data")
        return result

    def _summarize_gemini(self, prompt: str, model: str) -> Dict[str, Any]:
        url = self.GEMINI_URL.format(model=str(model or "gemini-2.5-flash-lite"))
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "Return JSON only with keys: summary, stance, risk_tags, confidence, action_hint. "
                                "Never include markdown.\n\n"
                                f"{prompt}"
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        response = requests.post(f"{url}?key={self.api_key}", headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        payload = response.json()
        candidates = payload.get("candidates", [])
        if not isinstance(candidates, list) or not candidates:
            raise RuntimeError("gemini_empty_candidates")
        content = candidates[0].get("content", {}) if isinstance(candidates[0], dict) else {}
        parts = content.get("parts", []) if isinstance(content, dict) else []
        text = ""
        if isinstance(parts, list):
            for part in parts:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    text = part["text"]
                    break
        if not text.strip():
            raise RuntimeError("gemini_empty_content")
        result = json.loads(text)
        self._mark("ok_with_data")
        return result
