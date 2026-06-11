"""
OllamaManager — Robust connection manager for local Ollama API.

Solves the "flickering Online/Offline" problem by:
  1. Caching health status with TTL (avoids hammering Ollama)
  2. Grace period: requires N consecutive failures before marking OFFLINE
  3. Quick recovery: one success brings it back ONLINE
  4. Background health checks (non-blocking)
  5. Singleton pattern — shared across all requests

Usage:
    from backend.services.ollama_manager import ollama_manager

    # Fast cached status check (for UI polling)
    status = ollama_manager.get_status()  # → {"state": "online", "models": [...]}

    # Actual Ollama operations
    result = ollama_manager.generate(prompt, model, temperature)
    models = ollama_manager.list_models()
"""

import json
import os
import threading
import time
import urllib.request
from typing import Dict, Any, List, Optional


# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────

OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
HEALTH_CACHE_TTL = 8.0          # seconds — how long cached health is valid
HEALTH_CHECK_TIMEOUT = 5.0     # seconds — timeout for health probe
GENERATE_TIMEOUT = 300.0       # seconds — timeout for LLM generation
LOAD_TIMEOUT = 60.0            # seconds — timeout for model load

# Grace period: how many consecutive failures before marking OFFLINE
OFFLINE_THRESHOLD = 2


# ──────────────────────────────────────────────────────────────────────────────
# OllamaManager
# ──────────────────────────────────────────────────────────────────────────────

class OllamaManager:
    """
    Thread-safe singleton that manages Ollama connectivity.

    State machine:
        UNKNOWN  → first check pending
        ONLINE   → recently succeeded
        OFFLINE  → exceeded failure threshold
        ERROR    → unexpected exception (not connection refused)
    """

    _instance: Optional["OllamaManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "OllamaManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self.base_url = OLLAMA_URL
        self._state = "unknown"          # unknown | online | offline | error
        self._models: List[str] = []
        self._last_error: Optional[str] = None
        self._consecutive_failures = 0
        self._last_check_time = 0.0
        self._check_lock = threading.Lock()
        self._bg_thread: Optional[threading.Thread] = None
        self._shutdown = False

        # Start background health checker
        self._start_background_checker()

    # ── Public API ──

    def get_status(self) -> Dict[str, Any]:
        """
        Fast cached status — safe to call from UI polling every few seconds.
        Returns immediately without blocking on network I/O.
        """
        with self._check_lock:
            age = time.time() - self._last_check_time
            stale = age > HEALTH_CACHE_TTL

            # If stale, trigger a background refresh (bg thread may be stuck/slow)
            if stale:
                self._trigger_background_check()

            return {
                "state": self._state,
                "models": self._models,
                "last_error": self._last_error,
                "cached_age_seconds": round(age, 1),
                "stale": stale,
                "url": self.base_url,
            }

    def list_models(self) -> List[str]:
        """Return installed model names. Forces fresh fetch."""
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/tags",
                headers={"Content-Type": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=HEALTH_CHECK_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m["name"] for m in data.get("models", [])]
                self._on_success(models)
                return models
        except Exception as e:
            self._on_failure(str(e))
            return []

    def generate(
        self,
        prompt: str,
        model: str = "qwen2.5-coder:7b",
        temperature: float = 0.3,
        num_ctx: int = 8192,
    ) -> str:
        """
        Send a generation request to Ollama.
        Raises OllamaError on failure (caller should catch and return JSON error).
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "30m",
            "options": {
                "temperature": temperature,
                "num_ctx": num_ctx,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=GENERATE_TIMEOUT) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                self._on_success(self._models)  # keep existing models
                return result.get("response", "")
        except urllib.error.URLError as e:
            err = str(e)
            self._on_failure(err)
            raise OllamaError(f"Ollama connection failed: {err}")
        except Exception as e:
            self._on_failure(str(e))
            raise OllamaError(f"Ollama request failed: {e}")

    def load_model(self, model: str = "qwen2.5-coder:7b") -> Dict[str, Any]:
        """Load/keep a model in memory."""
        try:
            payload = {
                "model": model,
                "prompt": "hi",
                "stream": False,
                "keep_alive": "30m",
                "options": {
                    "temperature": 0.1,
                    "num_ctx": 8192,
                },
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=LOAD_TIMEOUT) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                # Ensure the loaded model is tracked in our models list
                current_models = list(self._models)
                if model not in current_models:
                    current_models.append(model)
                self._on_success(current_models)
                return {
                    "loaded": True,
                    "model": model,
                    "response": result.get("response", ""),
                }
        except urllib.error.URLError as e:
            err = str(e)
            self._on_failure(err)
            return {
                "loaded": False,
                "model": model,
                "error": f"Ollama is not running on {self.base_url}. Start it with: ollama serve",
            }
        except Exception as e:
            self._on_failure(str(e))
            return {
                "loaded": False,
                "model": model,
                "error": f"Ollama error: {e}",
            }

    def model_status(self, model: str = "qwen2.5-coder:7b") -> Dict[str, Any]:
        """Check if a specific model is currently loaded in Ollama memory."""
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/ps",
                headers={"Content-Type": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=HEALTH_CHECK_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = data.get("models", [])
                for m in models:
                    if m.get("name") == model:
                        return {
                            "loaded": True,
                            "model": model,
                            "details": {
                                "size": m.get("size", 0),
                                "size_vram": m.get("size_vram", 0),
                                "expires_at": m.get("expires_at"),
                            },
                        }
                return {
                    "loaded": False,
                    "model": model,
                    "error": f"Model {model} is not currently loaded in memory.",
                }
        except urllib.error.URLError as e:
            err = str(e)
            self._on_failure(err)
            return {
                "loaded": False,
                "model": model,
                "error": f"Ollama is not running on {self.base_url}. Start it with: ollama serve",
            }
        except Exception as e:
            self._on_failure(str(e))
            return {
                "loaded": False,
                "model": model,
                "error": f"Ollama error: {e}",
            }

    def health(self) -> Dict[str, Any]:
        """Force a fresh health check."""
        self._perform_health_check()
        with self._check_lock:
            return {
                "reachable": self._state == "online",
                "state": self._state,
                "models": self._models,
                "error": self._last_error,
            }

    def shutdown(self) -> None:
        """Stop background thread. Call on app shutdown."""
        self._shutdown = True

    # ── Internal ──

    def _on_success(self, models: List[str]) -> None:
        with self._check_lock:
            self._state = "online"
            self._models = models
            self._last_error = None
            self._consecutive_failures = 0
            self._last_check_time = time.time()

    def _on_failure(self, error: str) -> None:
        with self._check_lock:
            self._consecutive_failures += 1
            self._last_error = error
            self._last_check_time = time.time()

            if self._consecutive_failures >= OFFLINE_THRESHOLD:
                if "refused" in error.lower() or "10061" in error:
                    self._state = "offline"
                else:
                    self._state = "error"

    def _perform_health_check(self) -> None:
        """Synchronous health probe."""
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/tags",
                headers={"Content-Type": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=HEALTH_CHECK_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m["name"] for m in data.get("models", [])]
                self._on_success(models)
        except Exception as e:
            self._on_failure(str(e))

    def _start_background_checker(self) -> None:
        """Launch daemon thread that periodically checks Ollama health."""
        def _loop():
            while not self._shutdown:
                try:
                    self._perform_health_check()
                except Exception:
                    pass
                # Sleep in small increments so shutdown is responsive
                for _ in range(int(HEALTH_CACHE_TTL * 2)):
                    if self._shutdown:
                        break
                    time.sleep(0.5)

        t = threading.Thread(target=_loop, daemon=True, name="ollama-health")
        t.start()
        self._bg_thread = t

    def _trigger_background_check(self) -> None:
        """Fire off a one-shot background check immediately."""
        def _once():
            try:
                self._perform_health_check()
            except Exception:
                pass

        t = threading.Thread(target=_once, daemon=True)
        t.start()


class OllamaError(Exception):
    """Raised when an Ollama operation fails."""
    pass


# Singleton export
ollama_manager = OllamaManager()
