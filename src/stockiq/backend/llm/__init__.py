"""LLM integration package — provider wrappers and forecast caching.

To add a new provider:
  1. Add its metadata to PROVIDERS in providers.py
  2. Add a _call_<name>() function in providers.py
  3. Register it in _CALLERS
"""

from stockiq.backend.llm.providers import PROVIDERS, fetch_ai_prediction, get_secret

__all__ = ["PROVIDERS", "fetch_ai_prediction", "get_secret"]
