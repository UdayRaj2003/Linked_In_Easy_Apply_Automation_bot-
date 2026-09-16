'''
Fire-and-forget recruiter email via local AI_Outreach import.

Never blocks or fails Easy Apply. Do not call FastAPI /generate or /send.
'''

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from config.questions import default_resume_path
from config.settings import ai_outreach_root, use_jd_email_outreach
from modules.helpers import print_lg

_import_warned = False


def _ensure_outreach_on_path() -> Path:
    root = Path(ai_outreach_root)
    if not root.is_absolute():
        root = (Path(__file__).resolve().parent.parent / root).resolve()
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def _emails_in_jd(jd_text: str) -> list[str]:
    _ensure_outreach_on_path()
    from ai_outreach.generator import emails_in_text

    return emails_in_text(jd_text or "")


def _resume_path_for_outreach(resume_path: str | None) -> str:
    if resume_path:
        path = os.path.abspath(resume_path)
        if os.path.isfile(path):
            return path
        print_lg(f"Outreach resume missing ({resume_path}); using default resume.")
    fallback = os.path.abspath(default_resume_path)
    return fallback


def _send_in_background(jd_text: str, resume_path: str) -> None:
    try:
        _ensure_outreach_on_path()
        from ai_outreach import send_outreach

        send_outreach(jd=jd_text, resume_path=resume_path)
    except Exception as e:
        print_lg("JD email outreach failed (Easy Apply continues):", e)


def maybe_send_jd_outreach(jd_text: str | None, resume_path: str | None) -> None:
    '''
    If the gate is on and the raw JD has at least one valid email, start
    send_outreach in a daemon thread. Always returns immediately.
    '''
    global _import_warned
    if not use_jd_email_outreach:
        return
    text = (jd_text or "").strip()
    if not text or text == "Unknown":
        return

    try:
        emails = _emails_in_jd(text)
    except Exception as e:
        if not _import_warned:
            _import_warned = True
            print_lg(
                "JD email outreach unavailable (import/parse failed). "
                "Easy Apply continues without outreach.",
                e,
            )
        return

    if not emails:
        print_lg("JD email outreach skipped — no valid email in JD.")
        return

    attach = _resume_path_for_outreach(resume_path)
    print_lg(
        f"JD email outreach: found {len(emails)} email(s); "
        f"firing send_outreach (resume={attach}). Easy Apply continues."
    )
    thread = threading.Thread(
        target=_send_in_background,
        args=(text, attach),
        daemon=True,
        name="jd-email-outreach",
    )
    thread.start()
