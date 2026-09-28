'''
Multiple LLM API keys with failover on rate-limit / auth errors.

Primary key: config.secrets.llm_api_key
Extra keys:  config.secrets.llm_api_keys (list of strings)

On 429 / invalid-key, rotate to the next unused key for this process.
AI is only disabled after every key has failed.
'''

from __future__ import annotations

import re

from config.secrets import llm_api_key
from modules.helpers import print_lg

try:
    from config.secrets import llm_api_keys as _config_extra_keys
except ImportError:
    _config_extra_keys = []

_AUTH_OR_QUOTA_PATTERNS = (
    r"\b429\b",
    r"too many requests",
    r"rate[_ ]?limit",
    r"free-models-per-day",
    r"free_tier_daily",
    r"openrouter_free_tier",
    r"quota.?exceeded",
    r"insufficient.?quota",
    r"\b401\b",
    r"\b403\b",
    r"invalid.?api.?key",
    r"incorrect.?api.?key",
    r"unauthorized",
    r"user not found",
    r"key not found",
    r"authentication",
)

_keys: list[str] = []
_index = 0
_exhausted = False


def _normalize_keys() -> list[str]:
    collected: list[str] = []
    extra = _config_extra_keys
    if isinstance(extra, str):
        extra = [extra]
    if not isinstance(extra, (list, tuple)):
        extra = []
    for raw in extra:
        key = str(raw or "").strip()
        if key and key not in collected:
            collected.append(key)
    primary = str(llm_api_key or "").strip()
    if primary and primary not in collected:
        collected.insert(0, primary)
    return collected


def reset_key_pool() -> None:
    global _keys, _index, _exhausted
    _keys = _normalize_keys()
    _index = 0
    _exhausted = False


def api_keys() -> list[str]:
    if not _keys and not _exhausted:
        reset_key_pool()
    return list(_keys)


def current_api_key() -> str:
    keys = api_keys()
    if not keys:
        return str(llm_api_key or "")
    return keys[min(_index, len(keys) - 1)]


def key_count() -> int:
    return len(api_keys())


def current_key_label() -> str:
    keys = api_keys()
    if not keys:
        return "none"
    return f"{_index + 1}/{len(keys)}"


def is_key_failover_error(exc_or_text) -> bool:
    text = str(exc_or_text or "")
    if not text:
        return False
    return any(re.search(p, text, flags=re.IGNORECASE) for p in _AUTH_OR_QUOTA_PATTERNS)


def apply_key_to_client(client) -> None:
    '''Set the OpenAI-compatible client's api_key to the current pool key.'''
    if client is None:
        return
    key = current_api_key()
    try:
        client.api_key = key
    except Exception:
        pass
    try:
        import google.generativeai as genai

        genai.configure(api_key=key)
    except Exception:
        pass


def rotate_api_key(exc_or_text=None) -> bool:
    '''
    Advance to the next key. Returns True if another key is available.
    False if this was the last key (caller should disable AI).
    '''
    global _index, _exhausted
    keys = api_keys()
    if not keys:
        _exhausted = True
        return False
    if _index + 1 >= len(keys):
        _exhausted = True
        print_lg(
            f"All {len(keys)} AI API key(s) exhausted "
            f"({str(exc_or_text)[:180] if exc_or_text else 'no remaining keys'})."
        )
        return False
    _index += 1
    print_lg(
        f"Switching to AI API key {current_key_label()} "
        f"after error: {str(exc_or_text)[:180] if exc_or_text else 'failover'}"
    )
    return True


reset_key_pool()
