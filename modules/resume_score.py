'''
JD vs resume scoring gate.

Runs only after existing eligibility/experience rules have already passed.
Uses the same AI client and llm_api_key as LinkedIn form answers.
'''

from __future__ import annotations

import json
import re

from config.questions import user_information_all
from config.secrets import ai_provider
from config.settings import use_resume_score_gate, resume_score_threshold
from modules.ai_runtime import is_ai_enabled
from modules.bot_control import BotStopped, raise_if_stopped
from modules.helpers import print_lg


def parse_resume_score(result) -> int | None:
    '''Extract an integer 0-100 from an AI scoring response.'''
    if result is None:
        return None
    if isinstance(result, (int, float)):
        return _clamp_score(int(result))
    if isinstance(result, dict):
        if result.get("error") and "score" not in result:
            return None
        if "score" in result:
            return parse_resume_score(result.get("score"))
        nested = result.get("data")
        if nested is not None and nested is not result:
            return parse_resume_score(nested)
        return None
    text = str(result).strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return parse_resume_score(obj)
        if isinstance(obj, (int, float)):
            return _clamp_score(int(obj))
    except Exception:
        pass
    match = re.search(r"\b(100|[0-9]{1,2})\b", text)
    if match:
        return _clamp_score(int(match.group(1)))
    return None


def _clamp_score(value: int) -> int:
    return max(0, min(100, value))


def _call_scoring_model(ai_client, job_description: str, resume_text: str):
    provider = (ai_provider or "openai").lower()
    if provider == "deepseek":
        from modules.ai.deepseekConnections import deepseek_score_jd_vs_resume
        return deepseek_score_jd_vs_resume(ai_client, job_description, resume_text)
    if provider == "gemini":
        from modules.ai.geminiConnections import gemini_score_jd_vs_resume
        return gemini_score_jd_vs_resume(ai_client, job_description, resume_text)
    from modules.ai.openaiConnections import ai_score_jd_vs_resume
    return ai_score_jd_vs_resume(ai_client, job_description, resume_text)


def apply_resume_score_gate(
    job_description: str,
    ai_client,
    jd_usable: bool,
) -> tuple[bool, str | None, str | None]:
    '''
    After eligibility has already passed, optionally score JD vs resume.

    Returns:
    - continue_apply: True to generate resume / apply
    - skip_reason: failed_job reason (or None)
    - skip_message: failed_job detail (or None)

    If scoring fails due to any condition (AI failure, AI disabled, missing resume text,
    insufficient JD content, exception, unparseable output), it passes by default.
    '''
    if not use_resume_score_gate:
        return True, None, None

    if not jd_usable:
        print_lg("Resume Score skipped — insufficient JD content (passing gate by default)")
        return True, None, None

    if not (is_ai_enabled() and ai_client):
        print_lg("Resume Score skipped — AI disabled or client unavailable (passing gate by default)")
        return True, None, None

    resume_text = (user_information_all or "").strip()
    if not resume_text:
        print_lg("Resume Score skipped — user_information_all is empty (passing gate by default)")
        return True, None, None

    raise_if_stopped()
    try:
        raw = _call_scoring_model(ai_client, job_description, resume_text)
    except BotStopped:
        raise
    except Exception as e:
        print_lg("Resume Score failed due to AI/system error (passing gate by default):", e)
        return True, None, None

    score = parse_resume_score(raw)
    if score is None:
        print_lg(f"Resume Score skipped — could not parse score from AI response: {raw!r} (passing gate by default)")
        return True, None, None

    print_lg(f"JD passed eligibility — Resume Score: {score}/100")
    if score < resume_score_threshold:
        msg = f"JD rejected — Resume Score: {score}/100 < threshold {resume_score_threshold}"
        print_lg(msg)
        return False, "Low resume score", msg

    print_lg("JD qualified — generating tailored resume")
    return True, None, None

