'''
Local Easy Apply answer memory.
Saves and reuses answers from failed-question pauses and pre-submit corrections.
'''

import json
import os
import re
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.select import Select
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException

from config.questions import save_and_reuse_answers, saved_answers_path
from config.settings import click_gap
from modules.helpers import buffer, print_lg
from modules.clickers_and_finders import try_xp, find_by_class


def normalize_question_label(label: str) -> str:
    '''
    Normalize a question label for use as a stable JSON key.
    '''
    if not label:
        return ""
    cleaned = re.sub(r'\s*\[.*?\]\s*$', '', str(label), flags=re.DOTALL)
    cleaned = cleaned.lower()
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = cleaned.strip(' :?-')
    return cleaned


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def load_saved_answers() -> dict:
    '''
    Load saved answers from JSON. Returns {} if missing or invalid.
    '''
    try:
        if not os.path.exists(saved_answers_path):
            return {}
        with open(saved_answers_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        print_lg(f"Failed to load saved answers from {saved_answers_path}: {e}")
        return {}


def get_saved_answer(label: str) -> str | None:
    '''
    Return a previously saved answer for `label`, or None.
    Tries exact key first, then partial/alias matches for work-experience fields.
    '''
    if not save_and_reuse_answers:
        return None
    key = normalize_question_label(label)
    if not key:
        return None
    data = load_saved_answers()

    def _answer_from_entry(entry) -> str | None:
        if not entry:
            return None
        if isinstance(entry, dict):
            answer = entry.get('answer')
            return str(answer) if answer is not None and str(answer).strip() != '' else None
        if isinstance(entry, str) and entry.strip():
            return entry
        return None

    # Exact match
    found = _answer_from_entry(data.get(key))
    if found is not None:
        return found

    # Partial match: only when keys are meaningfully similar (avoid "phone" matching "phone country code")
    for saved_key, entry in data.items():
        if not saved_key or saved_key == 'phone country code':
            continue
        # Skip very short keys for partial matching
        if len(saved_key) < 8 and saved_key != key:
            continue
        if saved_key == key:
            continue
        # Prefer containment only when the shorter key is a large portion of the longer one
        shorter, longer = (saved_key, key) if len(saved_key) <= len(key) else (key, saved_key)
        if shorter in longer and len(shorter) / max(len(longer), 1) >= 0.7:
            found = _answer_from_entry(entry)
            if found is not None:
                return found

    # Common work-experience aliases
    aliases = {
        'month of from': ['from month', 'start month', 'month of start'],
        'year of from': ['from year', 'start year', 'year of start'],
        'month of to': ['to month', 'end month', 'month of end'],
        'year of to': ['to year', 'end year', 'year of end'],
        'description': ['work experience description', 'role description', 'job description'],
        'city': ['work city', 'location city', 'job city'],
        'company': ['company name', 'employer', 'organization'],
        'your title': ['title', 'job title', 'role title', 'position'],
    }
    for canonical, alts in aliases.items():
        keys = [canonical] + alts
        if any(a in key or key in a for a in keys):
            for candidate in keys:
                found = _answer_from_entry(data.get(candidate))
                if found is not None:
                    return found
            for saved_key, entry in data.items():
                if any(a in saved_key or saved_key in a for a in keys):
                    found = _answer_from_entry(entry)
                    if found is not None:
                        return found
    return None


def upsert_saved_answers(entries: list[dict], force_overwrite: bool = True) -> int:
    '''
    Upsert answer entries into the JSON store.
    Each entry: {"label": str, "answer": str, "type": str}
    - force_overwrite=True: replace existing values (use for user corrections)
    - force_overwrite=False: keep existing values, only add missing keys
    Returns number of answers written/updated.
    '''
    if not save_and_reuse_answers:
        return 0
    data = load_saved_answers()
    updated = 0
    now = datetime.now().isoformat(timespec='seconds')
    for entry in entries:
        label = entry.get('label', '')
        answer = entry.get('answer', '')
        q_type = entry.get('type', 'text')
        key = normalize_question_label(label)
        if not key:
            continue
        if key == 'phone country code' and answer and str(answer).isdigit():
            continue
        if answer is None:
            continue
        answer_str = str(answer).strip()
        if answer_str == '' or answer_str.lower() == 'select an option':
            continue
        # Skip obviously trash select leftovers
        if answer_str.lower() in ('yes', 'no') and q_type == 'select' and any(
            m in key for m in ('month', 'year', 'date', 'from', 'to')
        ):
            continue
        if key in data and not force_overwrite:
            continue
        data[key] = {
            'answer': answer_str,
            'type': q_type,
            'updated_at': now,
            'source': 'user' if force_overwrite else 'bot',
        }
        updated += 1
    if updated:
        try:
            _ensure_parent_dir(saved_answers_path)
            with open(saved_answers_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print_lg(f"Failed to write saved answers to {saved_answers_path}: {e}")
            return 0
    return updated


def _extract_question_label(question: WebElement, control: WebElement | None = None, fallback: str = 'Unknown') -> str:
    '''
    Best-effort extraction of a clean question label from a form element.
    Prefers aria-label on the control (important for Month/Year of From/To).
    '''
    if control is not None:
        try:
            aria = (control.get_attribute('aria-label') or '').strip()
            if aria:
                return aria
        except Exception:
            pass
    try:
        radio_title = try_xp(question, './/span[@data-test-form-builder-radio-button-form-component__title]', False)
        if radio_title:
            try:
                hidden = find_by_class(radio_title, 'visually-hidden', 0.5)
                if hidden and hidden.text:
                    return hidden.text.strip()
            except Exception:
                pass
            if radio_title.text:
                return radio_title.text.strip()
    except Exception:
        pass
    try:
        label = try_xp(question, './/label[@for]', False)
        if label:
            try:
                hidden = label.find_element(By.CLASS_NAME, 'visually-hidden')
                if hidden and hidden.text:
                    return hidden.text.strip()
            except Exception:
                pass
            try:
                span = label.find_element(By.TAG_NAME, 'span')
                if span and span.text:
                    return span.text.strip()
            except Exception:
                pass
            if label.text:
                return label.text.strip()
    except Exception:
        pass
    try:
        hidden = try_xp(question, ".//span[@class='visually-hidden']", False)
        if hidden and hidden.text:
            return hidden.text.strip()
    except Exception:
        pass
    return fallback


def read_visible_form_answers(modal: WebElement) -> list[dict]:
    '''
    Read currently visible Easy Apply form field answers from `modal`.
    Returns list of {label, answer, type}.
    '''
    results: list[dict] = []
    try:
        all_questions = modal.find_elements(By.XPATH, ".//div[@data-test-form-element]")
    except Exception:
        return results

    for question in all_questions:
        try:
            select_el = try_xp(question, './/select', False)
            if select_el:
                label = _extract_question_label(question, select_el)
                # Keep both aria and visible label when useful for reuse
                try:
                    aria = (select_el.get_attribute('aria-label') or '').strip()
                    base = _extract_question_label(question)
                    if aria and base and base.lower() != aria.lower() and base.lower() != 'unknown':
                        label = f"{base} {aria}".strip()
                    elif aria:
                        label = aria
                except Exception:
                    pass
                if normalize_question_label(label) == 'phone country code':
                    continue
                select = Select(select_el)
                answer = select.first_selected_option.text
                results.append({'label': label, 'answer': answer, 'type': 'select'})
                # Also store under aria-label alone for easier reuse
                try:
                    aria = (select_el.get_attribute('aria-label') or '').strip()
                    if aria and normalize_question_label(aria) != normalize_question_label(label):
                        results.append({'label': aria, 'answer': answer, 'type': 'select'})
                except Exception:
                    pass
                continue

            radio = try_xp(question, './/fieldset[@data-test-form-builder-radio-button-form-component="true"]', False)
            if radio:
                label = _extract_question_label(question)
                answer = ''
                for option in radio.find_elements(By.TAG_NAME, 'input'):
                    if option.is_selected():
                        option_id = option.get_attribute('id')
                        option_label = try_xp(radio, f'.//label[@for="{option_id}"]', False)
                        answer = option_label.text.strip() if option_label and option_label.text else (option.get_attribute('value') or '')
                        break
                results.append({'label': label, 'answer': answer, 'type': 'radio'})
                continue

            text = try_xp(question, ".//input[@type='text']", False)
            if text:
                label = _extract_question_label(question, text)
                results.append({'label': label, 'answer': text.get_attribute('value') or '', 'type': 'text'})
                continue

            text_area = try_xp(question, './/textarea', False)
            if text_area:
                label = _extract_question_label(question, text_area)
                results.append({'label': label, 'answer': text_area.get_attribute('value') or '', 'type': 'textarea'})
                continue

            checkbox = try_xp(question, ".//input[@type='checkbox']", False)
            if checkbox:
                label = _extract_question_label(question, checkbox)
                results.append({
                    'label': label,
                    'answer': 'true' if checkbox.is_selected() else 'false',
                    'type': 'checkbox',
                })
                continue
        except Exception:
            continue
    return results


def capture_current_page_and_save(modal: WebElement, force_overwrite: bool = True) -> int:
    '''
    Snapshot the current Easy Apply page and upsert into the JSON store.
    Use force_overwrite=True after the user manually corrects fields.
    '''
    if not save_and_reuse_answers:
        return 0
    entries = read_visible_form_answers(modal)
    count = upsert_saved_answers(entries, force_overwrite=force_overwrite)
    print_lg(f"Saved {count} answer(s) from current Easy Apply page to {saved_answers_path} (overwrite={force_overwrite}).")
    return count


def _click_modal_span(modal: WebElement, text: str) -> bool:
    '''
    Click a button/span with exact normalized text inside the modal.
    '''
    try:
        el = modal.find_element(By.XPATH, f'.//span[normalize-space(.)="{text}"]')
        el.click()
        return True
    except Exception:
        try:
            el = modal.find_element(By.XPATH, f'.//button[contains(., "{text}")]')
            el.click()
            return True
        except Exception:
            return False


def capture_all_pages_and_save(modal: WebElement, max_pages: int = 15) -> int:
    '''
    Walk Back to the first Easy Apply page, snapshot each page while
    advancing with Next/Review, then upsert all collected answers.
    Never clicks Submit Application.
    '''
    if not save_and_reuse_answers:
        return 0

    for _ in range(max_pages):
        if not _click_modal_span(modal, 'Back'):
            break
        buffer(click_gap)

    collected: list[dict] = []
    for _ in range(max_pages):
        collected.extend(read_visible_form_answers(modal))
        try:
            review = modal.find_element(By.XPATH, './/span[normalize-space(.)="Review"]')
            try:
                review.click()
            except ElementClickInterceptedException:
                pass
            buffer(click_gap)
            break
        except NoSuchElementException:
            pass

        if not _click_modal_span(modal, 'Next'):
            break
        buffer(click_gap)

    # Deduplicate by normalized label, keep last value seen
    dedup: dict[str, dict] = {}
    for entry in collected:
        key = normalize_question_label(entry.get('label', ''))
        if key:
            dedup[key] = entry
    count = upsert_saved_answers(list(dedup.values()), force_overwrite=True)
    print_lg(f"Saved {count} answer(s) from Easy Apply walk to {saved_answers_path}.")
    return count
