'''
Runtime AI / Resume Engine switches for the current bot process.

LinkedIn answer-filling AI and Resume Engine are independent:
- Rate limit on LinkedIn AI → disable only form-answer AI; Resume Engine keeps running.
- Rate limit on Resume Engine → disable only Resume Engine; LinkedIn AI keeps running.
'''

from __future__ import annotations

import re

from config.secrets import use_AI as _config_use_ai
from config.settings import use_resume_engine as _config_use_resume_engine
from modules.helpers import print_lg

_ai_disabled = False
_resume_engine_disabled = False
_ai_disable_reason = ""
_resume_disable_reason = ""

_RATE_LIMIT_PATTERNS = (
    r"\b429\b",
    r"too many requests",
    r"rate[_ ]?limit",
    r"free-models-per-day",
    r"free_tier_daily",
    r"openrouter_free_tier",
    r"quota.?exceeded",
    r"insufficient.?quota",
    r"x-ratelimit-remaining['\"]?\s*[:=]\s*['\"]?0\b",
)


def is_rate_limit_error(exc_or_text) -> bool:
    text = str(exc_or_text or "")
    if not text:
        return False
    return any(re.search(p, text, flags=re.IGNORECASE) for p in _RATE_LIMIT_PATTERNS)


def disable_linkedin_ai_on_rate_limit(exc_or_text, *, source: str = "LinkedIn AI") -> bool:
    '''
    If rate/quota limited, disable LinkedIn answer-filling AI only for this process.
    Resume Engine is left alone.
    '''
    global _ai_disabled, _ai_disable_reason
    if not is_rate_limit_error(exc_or_text):
        return False
    if _ai_disabled:
        return True

    _ai_disabled = True
    _ai_disable_reason = str(exc_or_text)[:300]
    print_lg(
        f"\n*** API RATE/QUOTA LIMIT HIT ({source}) ***\n"
        f"Disabling LinkedIn AI answers for this run only.\n"
        f"Resume Engine keeps running. Easy Apply continues with saved/heuristic answers.\n"
        f"Add credits or wait for daily reset to re-enable LinkedIn AI on the next run.\n"
        f"Reason: {_ai_disable_reason}\n"
    )
    return True


def disable_resume_engine_on_rate_limit(exc_or_text, *, source: str = "Resume Engine") -> bool:
    '''
    If rate/quota limited, disable Resume Engine only for this process.
    LinkedIn answer AI is left alone.
    '''
    global _resume_engine_disabled, _resume_disable_reason
    if not is_rate_limit_error(exc_or_text):
        return False
    if _resume_engine_disabled:
        return True

    _resume_engine_disabled = True
    _resume_disable_reason = str(exc_or_text)[:300]
    print_lg(
        f"\n*** API RATE/QUOTA LIMIT HIT ({source}) ***\n"
        f"Disabling Resume Engine for this run only.\n"
        f"LinkedIn AI answers keep running. Uploading default resume instead.\n"
        f"Add credits or wait for daily reset to re-enable Resume Engine on the next run.\n"
        f"Reason: {_resume_disable_reason}\n"
    )
    return True


def disable_ai_and_resume_on_rate_limit(exc_or_text, *, source: str = "AI") -> bool:
    '''
    Backward-compatible helper for LinkedIn AI call sites.
    Disables LinkedIn answer AI only — does NOT disable Resume Engine.
    '''
    return disable_linkedin_ai_on_rate_limit(exc_or_text, source=source)


def is_ai_enabled() -> bool:
    return bool(_config_use_ai) and not _ai_disabled


def is_resume_engine_enabled() -> bool:
    return bool(_config_use_resume_engine) and not _resume_engine_disabled


def rate_limit_disable_reason() -> str:
    parts = []
    if _ai_disable_reason:
        parts.append(f"AI: {_ai_disable_reason}")
    if _resume_disable_reason:
        parts.append(f"Resume: {_resume_disable_reason}")
    return " | ".join(parts)
