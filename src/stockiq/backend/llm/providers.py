"""Multi-provider LLM wrappers and in-process forecast cache."""

import os

from stockiq.backend.cache import MemoryCache
from stockiq.backend.config import CACHE_TTL
from stockiq.backend.llm.prompts import _SYSTEM, _USER_TMPL, _parse_json


PROVIDERS: dict[str, dict] = {
    "groq": {
        "label":   "Llama 3.3 70B (Groq)",
        "model":   "llama-3.3-70b-versatile",
        "env_var": "GROQ_API_KEY",
        "free":    True,
    },
    "gemini": {
        "label":   "Gemini 2.0 Flash (Google)",
        "model":   "gemini-2.0-flash",
        "env_var": "GOOGLE_API_KEY",
        "free":    True,
    },
    "anthropic": {
        "label":   "Claude (Anthropic)",
        "model":   "claude-opus-4-6",
        "env_var": "ANTHROPIC_API_KEY",
        "free":    False,
    },
}


def get_secret(key: str) -> str:
    return os.environ.get(key, "")


def _call_anthropic(context_json: str, user_key: str = "") -> list[dict]:
    import anthropic
    api_key = user_key or get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        return []
    client = anthropic.Anthropic(api_key=api_key)
    raw = client.messages.create(
        model=PROVIDERS["anthropic"]["model"],
        max_tokens=4096,
        system=_SYSTEM,
        messages=[{"role": "user", "content": _USER_TMPL.format(context_json=context_json)}],
    )
    text = next((b.text for b in raw.content if b.type == "text"), "")
    return _parse_json(text) if text else []


def _call_groq(context_json: str, user_key: str = "") -> list[dict]:
    from groq import Groq
    api_key = user_key or get_secret("GROQ_API_KEY")
    if not api_key:
        return []
    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=PROVIDERS["groq"]["model"],
        max_tokens=4096,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": _USER_TMPL.format(context_json=context_json)},
        ],
    )
    text = resp.choices[0].message.content or ""
    return _parse_json(text) if text else []


def _call_gemini(context_json: str, user_key: str = "") -> list[dict]:
    from google import genai
    from google.genai import types
    api_key = user_key or get_secret("GOOGLE_API_KEY")
    if not api_key:
        return []
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=PROVIDERS["gemini"]["model"],
        contents=_USER_TMPL.format(context_json=context_json),
        config=types.GenerateContentConfig(system_instruction=_SYSTEM, max_output_tokens=4096),
    )
    text = resp.text or ""
    return _parse_json(text) if text else []


_CALLERS = {
    "anthropic": _call_anthropic,
    "groq":      _call_groq,
    "gemini":    _call_gemini,
}

_forecast_cache = MemoryCache()


def fetch_ai_prediction(
    cache_key: str,
    _context_json: str,
    provider: str = "groq",
    _user_key: str = "",
) -> list[dict]:
    """Fetch a 10-day SPY forecast from the selected AI provider.

    cache_key  = "YYYY-MM-DD-HH-<provider>" — stable for one hour.
    _context_json and _user_key are prefixed with _ to signal they are not
    part of the cache key (mirrors @st.cache_data leading-underscore convention).
    """
    store_key = f"{cache_key}-{provider}"
    ttl = CACHE_TTL["fetch_ai_prediction"]

    result, hit = _forecast_cache.get(store_key)
    if hit:
        return result

    caller = _CALLERS.get(provider)
    if caller is None:
        raise ValueError(f"Unknown provider: {provider!r}")

    result = caller(_context_json, user_key=_user_key)
    _forecast_cache.set(store_key, result, ttl)
    return result
