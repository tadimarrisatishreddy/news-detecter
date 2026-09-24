import json
import logging
import os
import socket
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import ollama

from config import AI_DETECTION_MODE, AI_TIMEOUT_SECONDS, GEMMA_MODEL, OLLAMA_BASE_URL

logger = logging.getLogger("ai.gemma_client")


class GemmaClientError(Exception):
    """Custom exception for Gemma AI client errors."""
    pass


def check_port_reachable(base_url: str, timeout: float = 0.3) -> bool:
    """Quick non-blocking check to verify if the server port is open."""
    try:
        parsed = urlparse(base_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 11434
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


import time

class GemmaClient:
    """
    Client for interacting with Google Gemma models via Ollama.
    Includes connection safeguards, configurable timeouts, and instant mock fallback.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        mode: Optional[str] = None,
    ):
        self.base_url = base_url or OLLAMA_BASE_URL
        self.model = model or GEMMA_MODEL
        self.timeout = timeout or AI_TIMEOUT_SECONDS
        self.mode = mode or AI_DETECTION_MODE
        self._client: Optional[ollama.Client] = None
        self._is_server_online: Optional[bool] = None
        self._last_check_time: float = 0.0

    def _get_client(self) -> ollama.Client:
        if self._client is None:
            self._client = ollama.Client(host=self.base_url, timeout=self.timeout)
        return self._client

    def is_available(self) -> bool:
        """Checks if the Ollama server is currently reachable with a 10-second cache."""
        if self.mode == "mock":
            return False

        now = time.time()
        # Re-check at most once every 10 seconds
        if self._is_server_online is None or (now - self._last_check_time) > 10.0:
            self._is_server_online = check_port_reachable(self.base_url, timeout=0.1)
            self._last_check_time = now

        return self._is_server_online


    def generate_chat_response(self, messages: List[Dict[str, str]]) -> str:
        """
        Sends chat messages to Gemma via Ollama and returns the assistant's text response.
        """
        if self.mode == "mock":
            return self._generate_mock_response(messages)

        # In auto mode, perform rapid probe before attempting chat
        if self.mode == "auto":
            if not self.is_available():
                logger.debug("Ollama service not running locally; using fallback simulation.")
                return self._generate_mock_response(messages)

        try:
            client = self._get_client()
            response = client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": 0.1,  # Deterministic, factual reasoning
                    "top_p": 0.9,
                },
            )
            return response.message.content
        except Exception as e:
            logger.warning(f"Ollama chat execution failed: {e}")
            if self.mode == "auto":
                logger.info("Falling back to local heuristic simulation (mode: auto).")
                return self._generate_mock_response(messages)
            raise GemmaClientError(f"Failed to communicate with Gemma model '{self.model}': {e}") from e

    def _generate_mock_response(self, messages: List[Dict[str, str]]) -> str:
        """
        Deterministic mock response generation for offline development and test execution.
        """
        user_message = ""
        for m in messages:
            if m.get("role") == "user":
                user_message = m.get("content", "")

        user_lower = user_message.lower()

        # Sensational or fabricated fake news patterns
        fake_cues = [
            "moon will be declared",
            "aliens",
            "replace water",
            "50,000 allowance",
            "50000 allowance",
            "shocking bombshell",
            "secret cure",
            "miracle pill",
            "100% proof",
            "they don't want you to know",
            "conspiracy",
            "secret aliens",
            "viral video",
        ]

        # Real news patterns
        real_cues = [
            "scientists announce",
            "central bank",
            "interest rate",
            "collaboration",
            "clinical trial",
            "parliament",
            "conference concludes",
            "published in",
            "weather observation satellite",
            "framework for carbon",
            "researchers published",
            "peer-reviewed",
            "quantum computing",
            "nuclear fusion",
        ]

        if any(cue in user_lower for cue in fake_cues):
            mock_payload = {
                "verdict": "LIKELY_FAKE",
                "confidence": 92,
                "explanation": "The claim exhibits strong hallmarks of fabricated misinformation, including sensationalist phrasing and lack of verifiable corroboration from official sources.",
                "key_signals": ["Sensationalist clickbait style", "Unsubstantiated factual claim", "Contradicts verified scientific or governmental records"],
                "manipulation_tactics": ["Sensationalism / emotional appeal", "Fabricated assertion"],
            }
        elif any(cue in user_lower for cue in real_cues):
            mock_payload = {
                "verdict": "LIKELY_REAL",
                "confidence": 88,
                "explanation": "The article uses objective, journalistic language consistent with legitimate news reporting and aligns with verifiable scientific and institutional developments.",
                "key_signals": ["Neutral objective tone", "Verifiable institutional attribution", "Absence of sensationalist trigger phrases"],
                "manipulation_tactics": [],
            }
        else:
            mock_payload = {
                "verdict": "UNCERTAIN",
                "confidence": 60,
                "explanation": "The claim contains ambiguous or uncorroborated assertions that require further external evidence to verify conclusively.",
                "key_signals": ["Ambiguous factual premise", "Limited contextual evidence"],
                "manipulation_tactics": [],
            }

        return json.dumps(mock_payload)


# Global default client instance
default_gemma_client = GemmaClient()
