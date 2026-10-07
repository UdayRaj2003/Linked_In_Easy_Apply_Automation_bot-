'''
Author:     Sai Vignesh Golla
LinkedIn:   https://www.linkedin.com/in/saivigneshgolla/

Copyright (C) 2024 Sai Vignesh Golla

License:    GNU Affero General Public License
            https://www.gnu.org/licenses/agpl-3.0.en.html
            
GitHub:     https://github.com/GodsScion/Auto_job_applier_linkedIn

Support me: https://github.com/sponsors/GodsScion

version:    26.01.20.5.08
'''


# Imports
import os
import csv
import re
import sys
import time
import pyautogui
from pathlib import Path

# Set CSV field size limit to prevent field size errors
csv.field_size_limit(1000000)  # Set to 1MB instead of default 131KB

from random import choice, shuffle, randint
from datetime import datetime, timedelta
from urllib.parse import urlencode

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.select import Select
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, NoSuchWindowException, ElementNotInteractableException, WebDriverException, StaleElementReferenceException, TimeoutException, InvalidSessionIdException

from config.personals import *
from config.questions import *
from config.search import *
from config.secrets import use_AI, username, password, ai_provider, extract_job_skills_with_ai
from config.settings import *

from modules.open_chrome import *
from modules.helpers import *
from modules.clickers_and_finders import *
from modules.validator import validate_config
from modules.saved_answers import get_saved_answer, capture_current_page_and_save, capture_all_pages_and_save

if use_AI:
    # Import only the configured provider to avoid unused SDK warnings/failures.
    _provider = (ai_provider or "openai").lower()
    if _provider == "openai":
        from modules.ai.openaiConnections import (
            ai_create_openai_client,
            ai_extract_skills,
            ai_answer_question,
            ai_close_openai_client,
        )
    elif _provider == "deepseek":
        from modules.ai.deepseekConnections import (
            deepseek_create_client,
            deepseek_extract_skills,
            deepseek_answer_question,
        )
        # DeepSeek reuses OpenAI client close helper when available
        try:
            from modules.ai.openaiConnections import ai_close_openai_client
        except Exception:
            def ai_close_openai_client(client):  # type: ignore
                return None
    elif _provider == "gemini":
        from modules.ai.geminiConnections import (
            gemini_create_client,
            gemini_extract_skills,
            gemini_answer_question,
        )
    else:
        raise ValueError(
            f'Unsupported ai_provider="{ai_provider}". Use "openai", "deepseek", or "gemini".'
        )

from typing import Literal

# Shared connector only — never import resume_engine from the LinkedIn bot.
_LINKEDIN_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _LINKEDIN_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from connectors import prepare_resume, _is_valid_resume_file
from modules.bot_control import (
    BotStopped,
    raise_if_stopped,
    should_stop,
    start_stop_controls,
)
from modules.ai_runtime import (
    disable_ai_and_resume_on_rate_limit,
    disable_resume_engine_on_rate_limit,
    is_ai_enabled,
    is_resume_engine_enabled,
)
from modules.resume_score import apply_resume_score_gate
from modules.jd_outreach import maybe_send_jd_outreach

# Move mouse to the top-left screen corner to abort (PyAutoGUI failsafe).
pyautogui.FAILSAFE = True
try:
    FailSafeException = pyautogui.FailSafeException
except AttributeError:  # pragma: no cover
    from pyautogui import FailSafeException  # type: ignore
# if use_resume_generator:    from resume_generator import is_logged_in_GPT, login_GPT, open_resume_chat, create_custom_resume


#< Global Variables and logics

if run_in_background == True:
    pause_at_failed_question = False
    pause_before_submit = False
    run_non_stop = False

first_name = first_name.strip()
middle_name = middle_name.strip()
last_name = last_name.strip()
full_name = first_name + " " + middle_name + " " + last_name if middle_name else first_name + " " + last_name

useNewResume = True
randomly_answered_questions = set()

tabs_count = 1
easy_applied_count = 0
external_jobs_count = 0
failed_count = 0
skip_count = 0
dailyEasyApplyLimitReached = False

re_experience = re.compile(r'[(]?\s*(\d+)\s*[)]?\s*[-to]*\s*\d*[+]*\s*year[s]?', re.IGNORECASE)

desired_salary_lakhs = str(round(desired_salary / 100000, 2))
desired_salary_monthly = str(round(desired_salary/12, 2))
desired_salary = str(desired_salary)

current_ctc_lakhs = str(round(current_ctc / 100000, 2))
current_ctc_monthly = str(round(current_ctc/12, 2))
current_ctc = str(current_ctc)

notice_period_months = str(notice_period//30)
notice_period_weeks = str(notice_period//7)
notice_period = str(notice_period)

aiClient = None
consecutive_dead_cycles = 0
cycle_had_usable_listings = False
stop_due_to_dead_cycles = False
##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------
about_company_for_ai = None # TODO extract about company for AI
##<

#>


#< Login Functions
def is_logged_in_LN() -> bool:
    '''
    Function to check if user is logged-in in LinkedIn
    * Returns: `True` if user is logged-in or `False` if not
    '''
    current = driver.current_url.lower()
    if "/feed" in current: return True
    if "/login" in current or "/uas/login" in current: return False
    # IMPORTANT: use click=False so login checks never submit the empty form
    if try_linkText(driver, "Sign in"): return False
    if try_xp(driver, '//button[@type="submit" and contains(text(), "Sign in")]', click=False): return False
    if try_linkText(driver, "Join now"): return False
    print_lg("Didn't find Sign in link, so assuming user is logged in!")
    return True


def _fill_linkedin_login_field(field_type: str, value: str, timeout: float = 15.0) -> bool:
    '''
    Fill LinkedIn username/password using visible/interactable fields.
    LinkedIn often has hidden duplicate inputs; presence alone is not enough.
    '''
    if field_type == "username":
        locators = [
            (By.ID, "username"),
            (By.NAME, "session_key"),
            (By.CSS_SELECTOR, "input#username"),
            (By.XPATH, '//input[@autocomplete="username"]'),
            (By.XPATH, '//form[contains(@class,"login") or @id="organic-div"]//input[@type="text"]'),
            (By.XPATH, '//input[@type="email"]'),
        ]
    else:
        locators = [
            (By.ID, "password"),
            (By.NAME, "session_password"),
            (By.CSS_SELECTOR, "input#password"),
            (By.XPATH, '//input[@autocomplete="current-password"]'),
            (By.XPATH, '//form[contains(@class,"login") or @id="organic-div"]//input[@type="password"]'),
            (By.XPATH, '//input[@type="password"]'),
        ]

    end_time = time.time() + timeout
    last_error = None

    while time.time() < end_time:
        for by, selector in locators:
            try:
                elements = driver.find_elements(by, selector)
                for field in elements:
                    try:
                        if not field.is_displayed() or not field.is_enabled():
                            continue
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", field)
                        try:
                            WebDriverWait(driver, 2).until(EC.element_to_be_clickable(field))
                            field.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", field)

                        try:
                            field.clear()
                            field.send_keys(Keys.CONTROL, "a")
                            field.send_keys(value)
                        except Exception:
                            # JS fallback for stubborn LinkedIn inputs
                            driver.execute_script(
                                """
                                const el = arguments[0], val = arguments[1];
                                el.focus();
                                el.value = val;
                                el.dispatchEvent(new Event('input', { bubbles: true }));
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                                """,
                                field,
                                value,
                            )

                        # Confirm value stuck
                        current_val = field.get_attribute("value") or ""
                        if current_val == value or (value and value in current_val):
                            print_lg(f"Filled LinkedIn {field_type} field using selector: {selector}")
                            return True
                    except Exception as e:
                        last_error = e
                        continue
            except Exception as e:
                last_error = e
                continue
        sleep(0.4)

    print_lg(f"Couldn't fill {field_type} field. URL: {driver.current_url} | Title: {driver.title}")
    if last_error:
        print_lg(f"{field_type} field error:", last_error)
    return False


def _click_linkedin_signin_button() -> bool:
    '''
    Click the LinkedIn Sign in button, with JS/Enter fallbacks.
    '''
    selectors = [
        (By.XPATH, '//button[@type="submit" and contains(@class,"btn__primary")]'),
        (By.CSS_SELECTOR, 'button.btn__primary--large'),
        (By.CSS_SELECTOR, 'button[data-litms-control-urn="login-submit"]'),
        (By.XPATH, '//button[@type="submit" and contains(., "Sign in")]'),
        (By.XPATH, '//button[contains(@class,"sign-in") or contains(@aria-label,"Sign in")]'),
        (By.XPATH, '//form[@id="organic-div" or contains(@class,"login")]//button[@type="submit"]'),
        (By.XPATH, '//button[@type="submit"]'),
    ]

    for by, selector in selectors:
        try:
            buttons = driver.find_elements(by, selector)
            for btn in buttons:
                try:
                    if not btn.is_displayed() or not btn.is_enabled():
                        continue
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                    try:
                        btn.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", btn)
                    print_lg(f"Clicked Sign in using selector: {selector}")
                    return True
                except Exception:
                    continue
        except Exception:
            continue

    # Fallback: press Enter on password field
    try:
        for pwd in driver.find_elements(By.XPATH, '//input[@type="password"]'):
            if pwd.is_displayed():
                pwd.send_keys(Keys.ENTER)
                print_lg("Submitted login form with Enter key on password field.")
                return True
    except Exception:
        pass

    # Fallback: submit the login form via JS
    try:
        submitted = driver.execute_script(
            """
            const form = document.querySelector('form#organic-div, form.login__form, form[action*="login"]');
            if (form) { form.requestSubmit ? form.requestSubmit() : form.submit(); return true; }
            return false;
            """
        )
        if submitted:
            print_lg("Submitted login form via JavaScript.")
            return True
    except Exception:
        pass

    return False


def login_LN() -> None:
    '''
    Function to login for LinkedIn
    * Tries to login using given `username` and `password` from `secrets.py`
    * If failed, tries to login using saved LinkedIn profile button if available
    * If both failed, asks user to login manually
    '''
    # Always land on login page fresh before filling credentials
    if "linkedin.com/login" not in driver.current_url.lower():
        open_url_with_retries(driver, "https://www.linkedin.com/login", attempts=3, wait_secs=2.0)
        print_lg("LinkedIn login opened. Waiting 5 seconds before entering credentials...")
        sleep(5)
    else:
        print_lg("Already on LinkedIn login page. Entering credentials...")

    if username == "username@example.com" and password == "example_password":
        print_lg("User did not configure username and password in secrets.py, hence can't login automatically! Please login manually!")
        if block_on_login_prompts:
            pyautogui.alert("User did not configure username and password in secrets.py, hence can't login automatically! Please login manually!", "Login Manually","Okay")
        manual_login_retry(is_logged_in_LN, 2)
        return

    try:
        WebDriverWait(driver, 20).until(
            EC.any_of(
                EC.presence_of_element_located((By.ID, "username")),
                EC.presence_of_element_located((By.NAME, "session_key")),
                EC.presence_of_element_located((By.XPATH, '//input[@type="password"]')),
            )
        )
    except Exception as e:
        print_lg(f"Login form did not appear. URL: {driver.current_url} | Title: {driver.title}", e)

    try:
        user_ok = _fill_linkedin_login_field("username", username, 10)
        pass_ok = _fill_linkedin_login_field("password", password, 10)
        if user_ok and pass_ok:
            if not _click_linkedin_signin_button():
                print_lg("Couldn't find/click Sign in button after filling credentials.")
        else:
            print_lg("Couldn't Login! Username/password fields were not available.")
            print_lg(f"Current page -> URL: {driver.current_url} | Title: {driver.title}")
    except Exception as e1:
        try:
            profile_button = find_by_class(driver, "profile__details")
            profile_button.click()
        except Exception as e2:
            print_lg("Couldn't Login!", e1, e2)

    try:
        # Wait until successful redirect, indicating successful login
        WebDriverWait(driver, 30).until(EC.url_contains("/feed"))
        return print_lg("Login successful!")
    except Exception as e:
        print_lg("Seems like login attempt failed! Possibly due to wrong credentials, captcha, or already logged in! Try logging in manually!")
        print_lg(f"After login attempt -> URL: {driver.current_url} | Title: {driver.title}")
        # print_lg(e)
        manual_login_retry(is_logged_in_LN, 2)
#>



def get_applied_job_ids() -> set[str]:
    '''
    Function to get a `set` of applied job's Job IDs
    * Returns a set of Job IDs from existing applied jobs history csv file
    '''
    job_ids: set[str] = set()
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                job_ids.add(row[0])
    except FileNotFoundError:
        print_lg(f"The CSV file '{file_name}' does not exist.")
    return job_ids



_LOCATION_INPUT_XPATHS = [
    ".//input[@aria-label='City, state, or zip code' and not(@disabled)]",
    ".//input[@aria-label='City, state, or zip code']",
    ".//input[contains(@aria-label,'City, state')]",
    ".//input[contains(@aria-label,'City, postal')]",
    ".//input[contains(@aria-label,'Search location')]",
    ".//input[@aria-label='Location' and not(@disabled)]",
    ".//input[contains(@aria-label,'Location')]",
    "(//input[contains(@class,'jobs-search-box__text-input')])[2]",
]
_ALL_FILTERS_XPATHS = [
    '//button[normalize-space()="All filters"]',
    '//button[contains(@aria-label,"All filters")]',
    '//button[contains(@aria-label,"all filters")]',
    '//button[contains(@aria-label,"Show all filters")]',
    '//span[normalize-space()="All filters"]/ancestor::button[1]',
    '//button[contains(@class,"search-reusables__all-filters-pill-button")]',
]
_SHOW_RESULTS_XPATHS = [
    '//button[contains(translate(@aria-label, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "apply current filters to show")]',
    '//button[contains(normalize-space(),"Show results")]',
    '//button[contains(@class,"search-reusables__secondary-filters-show-results-button")]',
]


def _wait_jobs_search_ready(timeout: int = 15) -> bool:
    try:
        WebDriverWait(driver, timeout).until(
            EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input.jobs-search-box__text-input")),
                EC.presence_of_element_located((By.XPATH, "//li[@data-occludable-job-id]")),
                EC.presence_of_element_located((By.XPATH, '//button[contains(@aria-label,"All filters") or normalize-space()="All filters"]')),
            )
        )
        return True
    except Exception:
        print_lg(
            f"Jobs search UI did not appear in {timeout}s. "
            f"URL: {driver.current_url} | Title: {driver.title}"
        )
        return False


def _find_by_xpaths(xpaths: list[str], timeout: float = 0) -> WebElement | None:
    end = time.time() + max(timeout, 0)
    while True:
        for xp in xpaths:
            try:
                for el in driver.find_elements(By.XPATH, xp):
                    try:
                        if el.is_displayed():
                            return el
                    except Exception:
                        continue
            except Exception:
                continue
        if time.time() >= end:
            return None
        sleep(0.3)


def _js_click(el: WebElement) -> bool:
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        sleep(0.15)
        el.click()
        return True
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            return False


def _apply_top_bar_filters() -> None:
    '''LinkedIn moved common filters to top-bar pills. Use them if All filters is missing.'''
    print_lg("Applying filters from the top bar (All filters button not available).")
    if sort_by:
        wait_span_click(driver, sort_by, 3)
    if date_posted:
        wait_span_click(driver, "Date posted", 3)
        wait_span_click(driver, date_posted, 3)
    if experience_level:
        wait_span_click(driver, "Experience level", 3)
        multi_sel_noWait(driver, experience_level)
    if easy_apply_only:
        easy_btn = _find_by_xpaths([
            '//button[contains(@aria-label,"Easy Apply filter")]',
            '//div[contains(@class,"search-reusables")]//button[contains(normalize-space(),"Easy Apply")]',
        ])
        if easy_btn:
            checked = (easy_btn.get_attribute("aria-checked") or "").lower()
            if checked != "true":
                _js_click(easy_btn)
                buffer(click_gap)
        else:
            wait_span_click(driver, "Easy Apply", 2)


def set_search_location() -> None:
    '''
    Function to set search location
    '''
    wanted = (search_location or "").strip()
    if not wanted:
        return
    print_lg(f'Setting search location as: "{wanted}"')
    _wait_jobs_search_ready(12)
    try:
        search_location_ele = _find_by_xpaths(_LOCATION_INPUT_XPATHS, timeout=8)
        if search_location_ele:
            current_val = (search_location_ele.get_attribute("value") or "").strip().lower()
            if wanted.lower() in current_val:
                print_lg(f'Location already "{search_location_ele.get_attribute("value")}" — leaving it.')
                return
            text_input(actions, search_location_ele, wanted, "Search Location")
            return
        print_lg("Search Location input was not given! Will continue with LinkedIn's current location.")
    except ElementNotInteractableException:
        try_xp(driver, ".//label[@class='jobs-search-box__input-icon jobs-search-box__keywords-label']")
        actions.send_keys(Keys.TAB, Keys.TAB).perform()
        actions.key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
        actions.send_keys(wanted).perform()
        sleep(2)
        actions.send_keys(Keys.ENTER).perform()
        try_xp(driver, ".//button[@aria-label='Cancel']")
    except Exception as e:
        try_xp(driver, ".//button[@aria-label='Cancel']")
        print_lg("Failed to update search location, continuing with default location!", e)


def apply_filters() -> None:
    '''
    Function to apply job search filters (All filters modal, with top-bar fallback).
    '''
    set_search_location()

    try:
        recommended_wait = 1 if click_gap < 1 else 0
        _wait_jobs_search_ready(12)

        all_btn = _find_by_xpaths(_ALL_FILTERS_XPATHS, timeout=12)
        if all_btn is None:
            _apply_top_bar_filters()
            return

        if not _js_click(all_btn):
            raise ElementNotInteractableException("All filters button not clickable")
        buffer(recommended_wait)

        wait_span_click(driver, sort_by)
        wait_span_click(driver, date_posted)
        buffer(recommended_wait)

        multi_sel_noWait(driver, experience_level) 
        multi_sel_noWait(driver, companies, actions)
        if experience_level or companies: buffer(recommended_wait)

        multi_sel_noWait(driver, job_type)
        multi_sel_noWait(driver, on_site)
        if job_type or on_site: buffer(recommended_wait)

        if easy_apply_only: boolean_button_click(driver, actions, "Easy Apply")
        
        multi_sel_noWait(driver, location)
        multi_sel_noWait(driver, industry)
        if location or industry: buffer(recommended_wait)

        multi_sel_noWait(driver, job_function)
        multi_sel_noWait(driver, job_titles)
        if job_function or job_titles: buffer(recommended_wait)

        if under_10_applicants: boolean_button_click(driver, actions, "Under 10 applicants")
        if in_your_network: boolean_button_click(driver, actions, "In your network")
        if fair_chance_employer: boolean_button_click(driver, actions, "Fair Chance Employer")

        wait_span_click(driver, salary)
        buffer(recommended_wait)
        
        multi_sel_noWait(driver, benefits)
        multi_sel_noWait(driver, commitments)
        if benefits or commitments: buffer(recommended_wait)

        show_results_button = _find_by_xpaths(_SHOW_RESULTS_XPATHS, timeout=6)
        if show_results_button is None:
            raise NoSuchElementException("Show results button not found in All filters panel")
        _js_click(show_results_button)

        global pause_after_filters
        if pause_after_filters and "Turn off Pause after search" == pyautogui.confirm("These are your configured search results and filter. It is safe to change them while this dialog is open, any changes later could result in errors and skipping this search run.", "Please check your results", ["Turn off Pause after search", "Look's good, Continue"]):
            pause_after_filters = False

    except Exception as e:
        print_lg("Setting the preferences failed!", e)
        print_lg(
            f"URL: {driver.current_url} | Title: {driver.title} | "
            f"block_on_filter_error={block_on_filter_error}"
        )
        try:
            _apply_top_bar_filters()
        except Exception as pill_err:
            print_lg("Top-bar filter fallback also failed:", pill_err)
        if block_on_filter_error:
            try:
                pyautogui.confirm(
                    f"Faced error while applying filters. Please make sure correct filters are selected, "
                    f"click on show results and click on any button of this dialog. "
                    f"Can't turn off Pause after search when error occurs!\n\nERROR: {e}",
                    "Filter setup failed",
                    ["Doesn't look good, but Continue XD", "Look's good, Continue"],
                )
            except Exception as dialog_err:
                print_lg("Could not show filter-error dialog; continuing anyway.", dialog_err)



def get_page_info() -> tuple[WebElement | None, int | None]:
    '''
    Function to get pagination element and current page number
    '''
    try:
        pagination_element = try_find_by_classes(driver, ["jobs-search-pagination__pages", "artdeco-pagination", "artdeco-pagination__pages"])
        scroll_to_view(driver, pagination_element)
        current_page = int(pagination_element.find_element(By.XPATH, "//button[contains(@class, 'active')]").text)
    except Exception as e:
        print_lg("Failed to find Pagination element, hence couldn't scroll till end!")
        pagination_element = None
        current_page = None
        print_lg(e)
    return pagination_element, current_page



def get_job_main_details(job: WebElement, blacklisted_companies: set, rejected_jobs: set) -> tuple[str, str, str, str, str, bool]:
    '''
    # Function to get job main details.
    Returns a tuple of (job_id, title, company, work_location, work_style, skip)
    * job_id: Job ID
    * title: Job title
    * company: Company name
    * work_location: Work location of this job
    * work_style: Work style of this job (Remote, On-site, Hybrid)
    * skip: A boolean flag to skip this job
    '''
    skip = False
    job_details_button = job.find_element(By.TAG_NAME, 'a')  # job.find_element(By.CLASS_NAME, "job-card-list__title")  # Problem in India
    scroll_to_view(driver, job_details_button, True)
    job_id = job.get_dom_attribute('data-occludable-job-id')
    title = job_details_button.text
    title = title[:title.find("\n")]
    # company = job.find_element(By.CLASS_NAME, "job-card-container__primary-description").text
    # work_location = job.find_element(By.CLASS_NAME, "job-card-container__metadata-item").text
    other_details = job.find_element(By.CLASS_NAME, 'artdeco-entity-lockup__subtitle').text
    index = other_details.find(' · ')
    company = other_details[:index]
    work_location = other_details[index+3:]
    work_style = work_location[work_location.rfind('(')+1:work_location.rfind(')')]
    work_location = work_location[:work_location.rfind('(')].strip()
    
    # Skip if previously rejected due to blacklist or already applied
    if company in blacklisted_companies:
        print_lg(f'Skipping "{title} | {company}" job (Blacklisted Company). Job ID: {job_id}!')
        skip = True
    elif job_id in rejected_jobs: 
        print_lg(f'Skipping previously rejected "{title} | {company}" job. Job ID: {job_id}!')
        skip = True
    try:
        if job.find_element(By.CLASS_NAME, "job-card-container__footer-job-state").text == "Applied":
            skip = True
            print_lg(f'Already applied to "{title} | {company}" job. Job ID: {job_id}!')
    except: pass
    try: 
        if not skip:
            job_details_button.click()
            try:
                WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.CLASS_NAME, "jobs-description__container"))
                )
                sleep(1.2)  
            except Exception:
                print_lg(f"Warning: Job Details view panel took too long to load for Job ID: {job_id}")
            # --------------------------------------

    except Exception as e:
        print_lg(f'Failed to click "{title} | {company}" job on details button. Job ID: {job_id}!') 
        # print_lg(e)
        discard_job()
        job_details_button.click() # To pass the error outside
    buffer(click_gap)
    return (job_id,title,company,work_location,work_style,skip)


# Function to check for Blacklisted words in About Company
def check_blacklist(rejected_jobs: set, job_id: str, company: str, blacklisted_companies: set) -> tuple[set, set, WebElement] | ValueError:
    jobs_top_card = try_find_by_classes(driver, ["job-details-jobs-unified-top-card__primary-description-container","job-details-jobs-unified-top-card__primary-description","jobs-unified-top-card__primary-description","jobs-details__main-content"])
    about_company_org = find_by_class(driver, "jobs-company__box")
    scroll_to_view(driver, about_company_org)
    about_company_org = about_company_org.text
    about_company = about_company_org.lower()
    skip_checking = False
    for word in about_company_good_words:
        if word.lower() in about_company:
            print_lg(f'Found the word "{word}". So, skipped checking for blacklist words.')
            skip_checking = True
            break
    if not skip_checking:
        for word in about_company_bad_words: 
            if word.lower() in about_company: 
                rejected_jobs.add(job_id)
                blacklisted_companies.add(company)
                raise ValueError(f'\n"{about_company_org}"\n\nContains "{word}".')
    buffer(click_gap)
    scroll_to_view(driver, jobs_top_card)
    return rejected_jobs, blacklisted_companies, jobs_top_card



# Function to extract years of experience required from About Job
def extract_years_of_experience(text: str) -> int:
    # Extract all patterns like '10+ years', '5 years', '3-5 years', etc.
    matches = re.findall(re_experience, text)
    if len(matches) == 0: 
        print_lg(f'\n{text}\n\nCouldn\'t find experience requirement in About the Job!')
        return 0
    return max([int(match) for match in matches if int(match) <= 12])



def get_job_description(
) -> tuple[
    str | Literal['Unknown'],
    int | Literal['Unknown'],
    bool,
    str | None,
    str | None
    ]:
    '''
    # Job Description
    Function to extract job description from About the Job.
    ### Returns:
    - `jobDescription: str | 'Unknown'`
    - `experience_required: int | 'Unknown'`
    - `skip: bool`
    - `skipReason: str | None`
    - `skipMessage: str | None`
    '''
    try:
        ##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------
        jobDescription = "Unknown"
        ##<
        experience_required = "Unknown"
        found_masters = 0
        jobDescription = find_by_class(driver, "jobs-box__html-content").text
        jobDescriptionLow = jobDescription.lower()
        skip = False
        skipReason = None
        skipMessage = None
        for word in bad_words:
            if word.lower() in jobDescriptionLow:
                skipMessage = f'\n{jobDescription}\n\nContains bad word "{word}". Skipping this job!\n'
                skipReason = "Found a Bad Word in About Job"
                skip = True
                break
        if not skip and security_clearance == False and ('polygraph' in jobDescriptionLow or 'clearance' in jobDescriptionLow or 'secret' in jobDescriptionLow):
            skipMessage = f'\n{jobDescription}\n\nFound "Clearance" or "Polygraph". Skipping this job!\n'
            skipReason = "Asking for Security clearance"
            skip = True
        if not skip:
            if did_masters and 'master' in jobDescriptionLow:
                print_lg(f'Found the word "master" in \n{jobDescription}')
                found_masters = 2
            experience_required = extract_years_of_experience(jobDescription)
            if current_experience > -1 and experience_required > current_experience + found_masters:
                skipMessage = f'\n{jobDescription}\n\nExperience required {experience_required} > Current Experience {current_experience + found_masters}. Skipping this job!\n'
                skipReason = "Required experience is high"
                skip = True
    except Exception as e:
        if jobDescription == "Unknown":    print_lg("Unable to extract job description!")
        else:
            experience_required = "Error in extraction"
            print_lg("Unable to extract years of experience required!")
            # print_lg(e)
    finally:
        return jobDescription, experience_required, skip, skipReason, skipMessage
        


def _resolve_resume_engine_root() -> Path:
    '''Resolve resume_engine_root relative to the LinkedIn bot directory when needed.'''
    root = Path(resume_engine_root)
    if not root.is_absolute():
        root = (_LINKEDIN_DIR / root).resolve()
    return root


def _is_job_description_usable(description: str | None) -> tuple[bool, str]:
    '''
    JD gate before calling the Resume Engine connector.
    Returns (usable, reason).
    '''
    if description is None or description == "Unknown":
        return False, "JD extraction failed"
    text = str(description).strip()
    if not text:
        return False, "JD extraction failed"
    if len(text) < int(min_jd_chars):
        return False, "Insufficient JD content"
    return True, "ok"


def _assemble_job_text(
    title: str,
    company: str,
    work_location: str,
    work_style: str,
    description: str,
) -> str:
    return (
        f"Job Title: {title}\n"
        f"Company: {company}\n"
        f"Location: {work_location}\n"
        f"Work Style: {work_style}\n\n"
        f"{description.strip()}"
    )


def _prepare_resume_pdf_for_job(
    title: str,
    company: str,
    work_location: str,
    work_style: str,
    description: str,
) -> str:
    '''
    Resolve which resume file to upload for this Easy Apply job.
    Tailored engine DOCX (else PDF) only when personalization succeeds;
    otherwise config/questions.py default_resume_path (not engine fallback_master).
    '''
    if not is_resume_engine_enabled():
        return default_resume_path

    usable, reason = _is_job_description_usable(description)
    if not usable:
        print_lg(f"Skipping Resume Engine ({reason}). Uploading default resume.")
        return default_resume_path

    raise_if_stopped()
    job_text = _assemble_job_text(title, company, work_location, work_style, description)
    output_dir = (_LINKEDIN_DIR / generated_resume_path / "generated").resolve()
    print_lg(
        f"Requesting personalized resume via connector "
        f"(timeout={resume_generation_timeout}s)... "
        f"[STOP BOT window / Ctrl+Shift+Q to cancel]"
    )
    template_choice = globals().get("resume_template_name", "template2")
    result = prepare_resume(
        job_text,
        engine_root=_resolve_resume_engine_root(),
        template=template_choice,
        output_dir=output_dir,
        timeout=float(resume_generation_timeout),
        cancel_check=should_stop,
    )
    if result.reason == "cancelled":
        raise BotStopped("Resume generation cancelled by user")
    # Resume Engine quota / rate limit — disable Resume Engine only (LinkedIn AI stays on)
    if disable_resume_engine_on_rate_limit(result.reason, source="Resume Engine"):
        print_lg("Uploading default resume after Resume Engine API limit.")
        return default_resume_path
    if result.personalized:
        preferred = result.resume_path
        if preferred is not None:
            print_lg(f"Resume ready (personalized): {preferred} [{result.reason}]")
            return str(preferred)
    if result.pdf_path is not None and not result.personalized:
        print_lg(
            f"Resume Engine returned master fallback ({result.pdf_path}) [{result.reason}]. "
            f"Uploading your default resume instead: {default_resume_path}"
        )
        return default_resume_path

    print_lg(
        f"Resume Engine unavailable ({result.reason}). "
        f"Uploading default resume: {default_resume_path}"
    )
    return default_resume_path


def _resume_path_for_csv(resume: str) -> str:
    '''Absolute path of the resume used (or default), so the CSV can open it later.'''
    text = (resume or "").strip()
    if text and text.lower() not in ("pending", "previous resume") and os.path.isfile(os.path.abspath(text)):
        return os.path.abspath(text)
    fallback = os.path.abspath(default_resume_path)
    if os.path.isfile(fallback):
        return fallback
    return text or fallback


# Function to upload resume
def upload_resume(modal: WebElement, resume: str) -> tuple[bool, str]:
    '''Send PDF or DOCX path into a visible/hidden file input under the Easy Apply modal.'''
    path = os.path.abspath(resume)
    if not os.path.isfile(path):
        print_lg(f"Resume file missing, cannot upload: {path}")
        return False, path
    for xp in (
        './/input[@name="file"]',
        './/input[@type="file"]',
        './/input[contains(translate(@accept,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"pdf") or contains(translate(@accept,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"doc") or contains(translate(@accept,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"word") or contains(translate(@accept,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"msword")]',
    ):
        try:
            inputs = modal.find_elements(By.XPATH, xp)
            for file_input in inputs:
                try:
                    file_input.send_keys(path)
                    sleep(1.5)
                    return True, path
                except Exception:
                    continue
        except Exception:
            continue
    return False, path


def _click_resume_edit_on_review(modal: WebElement) -> bool:
    '''
    Review page shows Resume summary + Edit; file input appears only after Edit.
    Prefer the Edit control tied to the Resume section (not Contact / Questions).
    '''
    xpaths = [
        './/button[contains(translate(@aria-label,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"edit") and contains(translate(@aria-label,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"resume")]',
        './/button[contains(@aria-label,"Edit resume") or contains(@aria-label,"edit resume")]',
        './/*[self::h2 or self::h3 or self::span][normalize-space()="Resume" or starts-with(normalize-space(),"Resume")]/ancestor::div[1]//button[.//span[normalize-space()="Edit"] or normalize-space()="Edit"]',
        './/*[self::h2 or self::h3][contains(normalize-space(),"Resume")]/following::button[.//span[normalize-space()="Edit"] or normalize-space()="Edit"][1]',
    ]
    for xp in xpaths:
        try:
            for btn in modal.find_elements(By.XPATH, xp):
                try:
                    if not btn.is_displayed():
                        continue
                    scroll_to_view(driver, btn)
                    try:
                        btn.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", btn)
                    print_lg('Clicked Resume "Edit" on Review page.')
                    buffer(click_gap)
                    sleep(1)
                    return True
                except Exception:
                    continue
        except Exception:
            continue

    # Fallback: Edit buttons whose nearby text mentions Resume
    try:
        edits = modal.find_elements(
            By.XPATH,
            './/button[.//span[normalize-space()="Edit"] or normalize-space()="Edit"]',
        )
        for btn in edits:
            try:
                if not btn.is_displayed():
                    continue
                container = btn.find_element(By.XPATH, "./ancestor::div[4]")
                chunk = (container.text or "")[:400].lower()
                if "resume" in chunk and "additional questions" not in chunk.split("resume")[0][-40:]:
                    scroll_to_view(driver, btn)
                    try:
                        btn.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", btn)
                    print_lg('Clicked Resume "Edit" on Review page (fallback).')
                    buffer(click_gap)
                    sleep(1)
                    return True
            except Exception:
                continue
    except Exception:
        pass
    print_lg('Could not find Resume "Edit" on Review page.')
    return False


def _resolve_resume_path_or_fallback(resume: str | None) -> str:
    '''Use generated PDF/DOCX if it exists and validates; otherwise default_resume_path.'''
    if resume:
        path = os.path.abspath(resume)
        if _is_valid_resume_file(Path(path)):
            return path
        if os.path.isfile(path):
            print_lg(f"Resume path failed validation ({resume}); using fallback default resume.")
        else:
            print_lg(f"Resume path not found ({resume}); using fallback default resume.")
    fallback = os.path.abspath(default_resume_path)
    if not os.path.isfile(fallback):
        print_lg(f"Fallback resume also missing: {fallback}")
    elif not _is_valid_resume_file(Path(fallback)):
        print_lg(f"Fallback resume failed validation: {fallback}")
    return fallback


def _send_resume_to_file_inputs(scope: WebElement | None, resume_path: str) -> tuple[bool, str]:
    '''Try file inputs under modal, then under Easy Apply root.'''
    path = os.path.abspath(resume_path)
    uploaded, label = upload_resume(scope if scope is not None else driver, path)
    if uploaded:
        return uploaded, label
    try:
        for el in driver.find_elements(
            By.XPATH,
            '//div[contains(@class,"jobs-easy-apply")]//input[@type="file" or @name="file"]',
        ):
            try:
                el.send_keys(path)
                sleep(1.5)
                return True, path
            except Exception:
                continue
    except Exception as e:
        print_lg("Driver-scoped resume upload failed:", e)
    return False, path


def _find_easy_apply_button(texts: tuple[str, ...] | list[str], modal: WebElement | None = None) -> tuple[WebElement | None, str]:
    '''Find a displayed Easy Apply footer/action button by label. Returns (element, label).'''
    scopes: list = []
    if modal is not None:
        scopes.append(modal)
    scopes.append(driver)
    for text in texts:
        xpaths = [
            f'.//span[normalize-space(.)="{text}"]',
            f'.//button[normalize-space(.)="{text}"]',
            f'.//button[.//span[normalize-space(.)="{text}"]]',
            f'.//button[contains(@aria-label,"{text}")]',
            f'//div[contains(@class,"jobs-easy-apply")]//span[normalize-space(.)="{text}"]',
            f'//div[contains(@class,"jobs-easy-apply")]//button[.//span[normalize-space(.)="{text}"] or normalize-space(.)="{text}"]',
            f'//footer//span[normalize-space(.)="{text}"]',
            f'//footer//button[.//span[normalize-space(.)="{text}"] or normalize-space(.)="{text}"]',
        ]
        for scope in scopes:
            for xp in xpaths:
                try:
                    for el in scope.find_elements(By.XPATH, xp):
                        try:
                            if el.is_displayed():
                                return el, text
                        except Exception:
                            continue
                except Exception:
                    continue
    return None, ""


def _submit_application_visible(modal: WebElement | None = None) -> bool:
    el, _ = _find_easy_apply_button(("Submit application",), modal)
    return el is not None


def _advance_easy_apply_toward_submit(modal: WebElement | None, max_steps: int = 12) -> tuple[WebElement | None, bool]:
    '''
    After Resume Edit + upload, footer is one of: Review / Next / Submit application.
    Prefer Review (back to summary), then Next/Continue, until Submit is available.
    '''
    for step in range(max_steps):
        try:
            modal = _refresh_easy_apply_modal()
        except Exception:
            pass

        if _submit_application_visible(modal):
            print_lg("Submit application is available.")
            return modal, True

        # After resume upload: Review first (returns to summary), then Next/Continue.
        action, label = _find_easy_apply_button(
            ("Review", "Next", "Continue", "Save"),
            modal,
        )
        if action is None:
            try:
                if modal is not None:
                    action = _click_easy_apply_modal_action(modal)
                    if action is not None:
                        label = (action.text or "action").strip() or "action"
            except Exception:
                action = None

        if action is None:
            print_lg(
                f"No Review/Next/Continue/Save after resume upload "
                f"(step {step + 1}/{max_steps})."
            )
            break

        print_lg(f'After resume edit/upload, clicking "{label}" (step {step + 1}/{max_steps})...')
        try:
            scroll_to_view(driver, action)
        except Exception:
            pass
        try:
            action.click()
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", action)
            except Exception as e:
                print_lg(f'Failed clicking "{label}" after resume upload:', e)
                break
        buffer(click_gap)
        sleep(0.8)

        # If we just hit Review, Submit is often on the next paint — check immediately
        if label == "Review":
            sleep(0.6)
            try:
                modal = _refresh_easy_apply_modal()
            except Exception:
                pass
            if _submit_application_visible(modal):
                print_lg("Submit application is available after Review.")
                return modal, True

    try:
        modal = _refresh_easy_apply_modal()
    except Exception:
        pass
    ready = _submit_application_visible(modal)
    if not ready:
        print_lg("Could not reach Submit application after advancing from resume edit.")
    return modal, ready


def _upload_resume_on_review(modal: WebElement, resume: str) -> tuple[bool, str, WebElement]:
    '''
    Required Review flow:
      1) Click Resume Edit  (opens mid-form resume step)
      2) Upload generated PDF, or fallback default_resume_path
      3) Next/Continue/Review until Submit is available
    '''
    resume_path = _resolve_resume_path_or_fallback(resume)
    using_fallback = os.path.abspath(resume_path) == os.path.abspath(default_resume_path)
    if using_fallback:
        print_lg(f"Will upload fallback resume after Edit: {resume_path}")
    else:
        print_lg(f"Will upload generated resume after Edit: {resume_path}")

    # Always Edit first on Review (file input is not on the collapsed summary).
    edited = _click_resume_edit_on_review(modal)
    if not edited:
        print_lg('Resume Edit not found — trying upload anyway in case file input is already open.')
    try:
        modal = _refresh_easy_apply_modal()
    except Exception:
        pass
    sleep(1.2)

    uploaded, label = _send_resume_to_file_inputs(modal, resume_path)

    # If generated upload failed, force fallback default (even if resolve already preferred it)
    if not uploaded and not using_fallback:
        fallback = _resolve_resume_path_or_fallback(None)
        print_lg(f"Generated resume upload failed; uploading fallback: {fallback}")
        uploaded, label = _send_resume_to_file_inputs(modal, fallback)
        if uploaded:
            resume_path = fallback

    if uploaded:
        print_lg(f"Uploaded resume after Resume Edit: {label}")
        sleep(1.5)  # LinkedIn needs a moment after file attach before Next enables
        modal, _ = _advance_easy_apply_toward_submit(modal)
    else:
        print_lg("Resume upload failed after Edit (no file input). LinkedIn previous resume may remain.")
        # Still try to get back to Review/Submit from mid-form Edit view
        if edited:
            modal, _ = _advance_easy_apply_toward_submit(modal)

    return uploaded, resume_path, modal

# Function to answer common questions for Easy Apply
def answer_common_questions(label: str, answer: str) -> str:
    if 'sponsorship' in label or 'visa' in label: answer = require_visa
    return answer


def _ai_answer_for_field(
    question: str,
    options: list[str] | None = None,
    question_type: str = "text",
    job_description: str | None = None,
) -> str | None:
    '''Ask AI for an interview-maximizing answer. Returns cleaned string or None.'''
    if not (is_ai_enabled() and aiClient):
        return None
    try:
        raw = None
        provider = (ai_provider or "").lower()
        if provider == "openai":
            raw = ai_answer_question(
                aiClient, question, options=options, question_type=question_type,
                job_description=job_description, user_information_all=user_information_all,
            )
        elif provider == "deepseek":
            raw = deepseek_answer_question(
                aiClient, question, options=options, question_type=question_type,
                job_description=job_description, about_company=None, user_information_all=user_information_all,
            )
        elif provider == "gemini":
            raw = gemini_answer_question(
                aiClient, question, options=options, question_type=question_type,
                job_description=job_description, about_company=None, user_information_all=user_information_all,
            )
        if isinstance(raw, dict):
            return None
        answer = (raw or "").strip().strip('"').strip("'")
        # Strip accidental "Answer:" prefixes
        for prefix in ("answer:", "final answer:", "option:"):
            if answer.lower().startswith(prefix):
                answer = answer[len(prefix):].strip()
        if answer:
            print_lg(f'AI Answered received for question "{question}" \nhere is answer: "{answer}"')
            return answer
    except Exception as e:
        print_lg("Failed to get AI answer!", e)
    return None


def _match_ai_option(ai_answer: str, options_text: list[str]) -> str | None:
    '''Map AI text to the closest provided option label.'''
    if not ai_answer or not options_text:
        return None
    cleaned = ai_answer.strip().strip('"').strip("'")
    for opt in options_text:
        if opt.strip().lower() == cleaned.lower():
            return opt
    for opt in options_text:
        if cleaned.lower() in opt.lower() or opt.lower() in cleaned.lower():
            return opt
    # Prefer Yes-like if AI said yes
    if cleaned.lower() in ("yes", "y", "true", "agree"):
        for opt in options_text:
            ol = opt.lower()
            if ol.startswith("yes") or ol == "y" or "agree" in ol or "i do" in ol or "i have" in ol:
                return opt
    return None


_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _get_employment_date_defaults() -> tuple[str, str, str, str]:
    '''
    Returns (from_month, from_year, to_month, to_year).
    Prefers saved_answers.json values, then sensible defaults.
    Default To = March 2026 (user preference); From = December prior year span.
    '''
    saved_from_m = get_saved_answer("month of from")
    saved_from_y = get_saved_answer("year of from")
    saved_to_m = get_saved_answer("month of to")
    saved_to_y = get_saved_answer("year of to")
    return (
        saved_from_m or "December",
        saved_from_y or "2025",
        saved_to_m or "March",
        saved_to_y or "2026",
    )


def _select_options_look_like_months(options_text: list[str]) -> bool:
    months = {m.lower() for m in _MONTH_NAMES}
    hits = sum(1 for o in options_text if o.strip().lower() in months)
    return hits >= 6


def _select_options_look_like_years(options_text: list[str]) -> bool:
    hits = sum(1 for o in options_text if o.strip().isdigit() and len(o.strip()) == 4)
    return hits >= 5


def _pick_select_option(select: Select, options_text: list[str], desired: str) -> str | None:
    '''
    Try exact, then case-insensitive, then partial match for a select option.
    '''
    if not desired:
        return None
    try:
        select.select_by_visible_text(desired)
        return desired
    except Exception:
        pass
    desired_l = desired.lower().strip()
    for option in options_text:
        if option.lower().strip() == desired_l:
            select.select_by_visible_text(option)
            return option
    for option in options_text:
        if desired_l in option.lower() or option.lower() in desired_l:
            if option.strip() and option.lower() not in ("select an option", "select", "month", "year"):
                select.select_by_visible_text(option)
                return option
    return None


def _resolve_month_year_answer(label: str, aria_label: str, options_text: list[str]) -> str | None:
    '''
    Resolve answer for month/year employment date dropdowns.
    Always fills From and To (does not skip To). Uses saved_answers when present.
    '''
    combined = f"{label} {aria_label}".lower()
    from_month, from_year, to_month, to_year = _get_employment_date_defaults()
    is_from = any(k in combined for k in ["from", "start", "began", "beginning"])
    is_to = any(k in combined for k in ["to", "end", "until", "present"]) and "today" not in combined

    # Direct saved-key lookups first
    if _select_options_look_like_months(options_text) or "month" in combined:
        if is_to and not is_from:
            return get_saved_answer("month of to") or get_saved_answer(aria_label) or to_month
        if is_from:
            return get_saved_answer("month of from") or get_saved_answer(aria_label) or from_month
        # ambiguous month dropdown under dates of employment — prefer From then To by aria
        if "to" in combined:
            return get_saved_answer("month of to") or to_month
        return get_saved_answer("month of from") or from_month

    if _select_options_look_like_years(options_text) or "year" in combined:
        if is_to and not is_from:
            return get_saved_answer("year of to") or get_saved_answer(aria_label) or to_year
        if is_from:
            return get_saved_answer("year of from") or get_saved_answer(aria_label) or from_year
        if "to" in combined:
            return get_saved_answer("year of to") or to_year
        return get_saved_answer("year of from") or from_year

    return None


def _modal_has_open_save_form(modal: WebElement) -> bool:
    '''
    True when an inline editor with Save is open (work experience / education / similar).
    In that case we must click Save before Next.
    '''
    try:
        save_el = None
        for xpath in (
            './/span[normalize-space(.)="Save"]',
            './/button[contains(., "Save")]',
            './/button[@aria-label="Save"]',
        ):
            try:
                save_el = modal.find_element(By.XPATH, xpath)
                if save_el.is_displayed():
                    break
                save_el = None
            except Exception:
                continue
        if save_el is None:
            return False
        body = (modal.text or "").lower()
        markers = [
            "your title", "dates of employment", "i currently work",
            "school", "degree", "field of study", "cancel",
            "month of from", "year of from", "description",
        ]
        return any(m in body for m in markers)
    except Exception:
        return False


def _click_add_more_if_needed(modal: WebElement) -> bool:
    '''
    On Work experience / Education list pages, open the editor via "+ Add more".
    Only when overwrite_previous_answers is True — otherwise keep LinkedIn's existing entries.
    '''
    if not overwrite_previous_answers:
        return False
    if _modal_has_open_save_form(modal):
        return False
    body = (modal.text or "").lower()
    if "work experience" not in body and "education" not in body and "add more" not in body:
        return False
    # Empty list or need another entry
    for xpath in (
        './/button[contains(normalize-space(.), "Add more")]',
        './/span[contains(normalize-space(.), "Add more")]',
        './/a[contains(normalize-space(.), "Add more")]',
        './/*[contains(normalize-space(.), "+ Add more")]',
        './/button[contains(., "Add")]',
    ):
        try:
            els = modal.find_elements(By.XPATH, xpath)
            for el in els:
                try:
                    if not el.is_displayed():
                        continue
                    txt = (el.text or "").strip().lower()
                    if "add" not in txt:
                        continue
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                    try:
                        el.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", el)
                    print_lg('Clicked "+ Add more" to open the form editor.')
                    buffer(click_gap)
                    sleep(1)
                    return True
                except Exception:
                    continue
        except Exception:
            continue
    return False


def _click_easy_apply_modal_action(modal: WebElement) -> WebElement | None:
    '''
    Find the best Easy Apply action button.
    If a Save-form editor is open, prefer Save over Next (critical for Oracle/PyjamaHR).
    '''
    # Work experience / education editor open -> Save first
    if _modal_has_open_save_form(modal):
        for text in ("Save",):
            try:
                el = modal.find_element(By.XPATH, f'.//span[normalize-space(.)="{text}"]')
                if el.is_displayed():
                    return el
            except NoSuchElementException:
                pass
            try:
                el = modal.find_element(By.XPATH, f'.//button[contains(., "{text}")]')
                if el.is_displayed():
                    return el
            except NoSuchElementException:
                pass

    for text in ("Review", "Next", "Continue", "Save"):
        try:
            el = modal.find_element(By.XPATH, f'.//span[normalize-space(.)="{text}"]')
            if el.is_displayed():
                return el
        except NoSuchElementException:
            pass
        try:
            el = modal.find_element(By.XPATH, f'.//button[contains(., "{text}")]')
            if el.is_displayed():
                return el
        except NoSuchElementException:
            pass
    try:
        return modal.find_element(By.XPATH, './/button[contains(span, "Next")]')
    except NoSuchElementException:
        return None


def _pick_phone_country_code(select: Select, options_text: list[str], prev_answer: str) -> str | None:
    '''
    Prefer India (+91) / configured country for phone country code. Never leave this to random.
    '''
    preferred = []
    if prev_answer and prev_answer.lower() not in ("select an option", ""):
        preferred.append(prev_answer)
    preferred.extend([
        "India (+91)",
        "India +91",
        "+91",
        "India",
    ])
    # Also try personals country if available
    try:
        if country:
            preferred.append(str(country))
            preferred.append(f"{country} (+91)")
    except Exception:
        pass

    # Build options if caller passed empty list
    if not options_text:
        try:
            options_text = [o.text for o in select.options]
        except Exception:
            options_text = []

    for candidate in preferred:
        picked = _pick_select_option(select, options_text, candidate)
        if picked:
            return picked
    # Last resort: search any option containing +91 or India
    for option in options_text:
        low = option.lower()
        if "+91" in low or low.strip().startswith("india"):
            try:
                select.select_by_visible_text(option)
                return option
            except Exception:
                continue
    return None


def _location_answer_text(work_location: str) -> str:
    '''Best-effort city string for Easy Apply location typeahead.'''
    city = (current_city or "").strip()
    if city:
        # Enrich short city names so LinkedIn suggestions match (e.g. Pune District…)
        parts = [city]
        try:
            if state and state.lower() not in city.lower():
                parts.append(state.strip())
        except Exception:
            pass
        try:
            if country and country.lower() not in city.lower():
                parts.append(country.strip())
        except Exception:
            pass
        return ", ".join(parts) if len(parts) > 1 else city
    return (work_location or "").strip()


def _select_typeahead_suggestion(input_el: WebElement, typed: str) -> bool:
    '''
    After typing into a LinkedIn typeahead (Location city), pick a suggestion.
    Clicks the best matching option; falls back to ArrowDown+Enter on the input.
    '''
    typed_norm = (typed or "").strip().lower()
    city_token = typed_norm.split(",")[0].strip() if typed_norm else ""
    try:
        input_el.click()
    except Exception:
        pass
    sleep(1.5)

    option_xpaths = [
        '//div[@role="listbox"]//div[@role="option"]',
        '//ul[@role="listbox"]//li[@role="option"]',
        '//div[contains(@class,"basic-typeahead")]//div[@role="option"]',
        '//div[contains(@class,"search-typeahead-v2__hit")]',
        '//div[contains(@class,"typeahead-results")]//div[@role="option"]',
        '//div[contains(@id,"typeahead") or contains(@class,"typeahead")]//div[@role="option"]',
    ]
    candidates: list[WebElement] = []
    for xp in option_xpaths:
        try:
            for el in driver.find_elements(By.XPATH, xp):
                try:
                    if el.is_displayed() and (el.text or "").strip():
                        candidates.append(el)
                except Exception:
                    continue
            if candidates:
                break
        except Exception:
            continue

    best = None
    best_score = -1
    for el in candidates:
        try:
            t = (el.text or "").strip()
            tl = t.lower()
            score = 0
            if typed_norm and tl == typed_norm:
                score = 100
            elif typed_norm and typed_norm in tl:
                score = 90
            elif city_token and tl.startswith(city_token):
                score = 80
            elif city_token and city_token in tl:
                score = 70
            if score > best_score:
                best_score = score
                best = el
        except Exception:
            continue

    if best is not None and best_score >= 70:
        label = (best.text or "").strip()
        try:
            scroll_to_view(driver, best)
            best.click()
            print_lg(f'Selected city typeahead: "{label}"')
            sleep(0.4)
            return True
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", best)
                print_lg(f'Selected city typeahead (JS): "{label}"')
                sleep(0.4)
                return True
            except Exception as e:
                print_lg("Typeahead option click failed:", e)

    # Keyboard fallback (must target the input, not a stale ActionChains queue)
    try:
        input_el.send_keys(Keys.ARROW_DOWN)
        sleep(0.25)
        input_el.send_keys(Keys.ENTER)
        print_lg("Selected city typeahead via keyboard fallback.")
        sleep(0.4)
        return True
    except Exception as e:
        print_lg("City typeahead selection failed:", e)
        return False


# Function to answer the questions for Easy Apply
def answer_questions(modal: WebElement, questions_list: set, work_location: str, job_description: str | None = None ) -> set:
    # Get all questions from the page
     
    all_questions = modal.find_elements(By.XPATH, ".//div[@data-test-form-element]")
    # all_questions = modal.find_elements(By.CLASS_NAME, "jobs-easy-apply-form-element")
    # all_list_questions = modal.find_elements(By.XPATH, ".//div[@data-test-text-entity-list-form-component]")
    # all_single_line_questions = modal.find_elements(By.XPATH, ".//div[@data-test-single-line-text-form-component]")
    # all_questions = all_questions + all_list_questions + all_single_line_questions

    # Pre-pass: apply saved "I currently work here" (default UNCHECKED so To dates can be filled)
    for Question in all_questions:
        try:
            checkbox = try_xp(Question, ".//input[@type='checkbox']", False)
            if not checkbox:
                continue
            label = try_xp(Question, ".//span[@class='visually-hidden']", False)
            label_org = label.text if label else ""
            label_l = label_org.lower()
            try:
                lab2 = try_xp(Question, ".//label[@for]", False)
                if lab2 and lab2.text:
                    label_l = (label_l + " " + lab2.text).lower()
                    if not label_org:
                        label_org = lab2.text
            except Exception:
                pass
            if any(k in label_l for k in ["currently work", "i currently work", "current role", "still work here"]):
                saved_cw = get_saved_answer(label_org) or get_saved_answer("i currently work here")
                # User wants To dates filled (March 2026) -> do NOT force-check this box
                want_checked = bool(saved_cw) and saved_cw.lower() in ("true", "yes", "1", "checked")
                is_checked = checkbox.is_selected()
                if want_checked and not is_checked:
                    try:
                        actions.move_to_element(checkbox).click().perform()
                        print_lg('Checked "I currently work here" from saved answers.')
                        sleep(0.5)
                    except Exception:
                        driver.execute_script("arguments[0].click();", checkbox)
                elif (not want_checked) and is_checked:
                    try:
                        actions.move_to_element(checkbox).click().perform()
                        print_lg('Unchecked "I currently work here" so To dates (March 2026) can be filled.')
                        sleep(0.5)
                    except Exception:
                        driver.execute_script("arguments[0].click();", checkbox)
        except Exception:
            continue

    for Question in all_questions:
        # Check if it's a select Question
        select = try_xp(Question, ".//select", False)
        if select:
            # Skip disabled dropdowns (common for "To" dates when "I currently work here" is checked)
            try:
                if not select.is_enabled():
                    continue
            except Exception:
                pass
            label_org = "Unknown"
            try:
                label = Question.find_element(By.TAG_NAME, "label")
                label_org = label.find_element(By.TAG_NAME, "span").text
            except: pass
            aria_label = ""
            try:
                aria_label = select.get_attribute("aria-label") or ""
                if (not label_org or label_org == "Unknown") and aria_label:
                    label_org = aria_label
                elif aria_label and aria_label.lower() not in label_org.lower():
                    label_org = f"{label_org} {aria_label}".strip()
            except Exception:
                pass
            answer = 'Yes'
            label = label_org.lower()
            select = Select(select)
            selected_option = select.first_selected_option.text
            optionsText = []
            options = '"List of phone country codes"'
            is_phone_country = 'phone country code' in label or label.strip() == 'phone country code'
            if not is_phone_country:
                optionsText = [option.text for option in select.options]
                options = "".join([f' "{option}",' for option in optionsText])
            else:
                # Still load options for matching India (+91); do not skip the list entirely
                try:
                    optionsText = [option.text for option in select.options]
                except Exception:
                    optionsText = []
            prev_answer = selected_option
            saved_answer = get_saved_answer(label_org)
            # Also try saving key without duplicated noise
            if saved_answer is None:
                saved_answer = get_saved_answer(aria_label) if aria_label else None
            # Never use a plain phone-number saved value as a country code
            if is_phone_country and saved_answer and saved_answer.isdigit():
                saved_answer = None
            if is_phone_country and saved_answer and '+91' not in saved_answer and 'india' not in saved_answer.lower():
                # Ignore clearly wrong saved country codes; prefer India
                if not any(x in saved_answer for x in ['+', 'India', 'india']):
                    saved_answer = None

            needs_fill = (
                saved_answer is not None
                or overwrite_previous_answers
                or selected_option == "Select an option"
                or not selected_option.strip()
            )
            # Always correct phone country code if it's not India/+91
            if is_phone_country and '+91' not in selected_option and 'india' not in selected_option.lower():
                needs_fill = True
            # Month/Year placeholders on Oracle/LinkedIn work experience forms
            if selected_option.strip().lower() in ("month", "year", "select", "select an option", ""):
                if _select_options_look_like_months(optionsText) or _select_options_look_like_years(optionsText) or any(
                    k in label for k in ("month", "year", "date", "from", "to", "employment")
                ):
                    needs_fill = True
            # Re-fill invalid month/year leftovers (e.g. previous random "Yes" attempts)
            if not needs_fill and (
                _select_options_look_like_months(optionsText) or _select_options_look_like_years(optionsText)
            ):
                if selected_option.strip().lower() in ("yes", "no", "select an option", "month", "year", ""):
                    needs_fill = True

            if needs_fill:
                ##> ------ WINDY_WINDWARD Email:karthik.sarode23@gmail.com - Added fuzzy logic to answer location based questions ------
                if is_phone_country:
                    picked = _pick_phone_country_code(select, optionsText, prev_answer)
                    if picked:
                        answer = picked
                        print_lg(f'Set phone country code to "{answer}"')
                    else:
                        answer = prev_answer
                        print_lg(f'Could not set India (+91); leaving phone country code as "{prev_answer}"')
                    questions_list.add((f'{label_org} [ {options} ]', answer, "select", prev_answer))
                    continue

                if saved_answer is not None:
                    answer = saved_answer
                else:
                    date_answer = _resolve_month_year_answer(label, aria_label, optionsText)
                    if date_answer is not None:
                        answer = date_answer
                    elif 'email' in label or 'phone' in label:
                        answer = prev_answer
                    elif 'gender' in label or 'sex' in label:
                        answer = gender
                    elif 'disability' in label:
                        answer = disability_status
                    elif 'proficiency' in label:
                        answer = 'Professional'
                    elif any(loc_word in label for loc_word in ['location', 'city', 'state', 'country']):
                        if 'country' in label:
                            answer = country
                        elif 'state' in label:
                            answer = state
                        elif 'city' in label:
                            answer = current_city if current_city else work_location
                        else:
                            answer = work_location
                    else:
                        answer = answer_common_questions(label, "")
                        # AI picks interview-maximizing option when no heuristic match
                        if not answer and optionsText:
                            ai_ans = _ai_answer_for_field(
                                label_org,
                                options=optionsText,
                                question_type="single_select",
                                job_description=job_description,
                            )
                            matched = _match_ai_option(ai_ans, optionsText) if ai_ans else None
                            answer = matched or ai_ans or "Yes"

                picked = _pick_select_option(select, optionsText, str(answer))
                if picked is not None:
                    answer = picked
                else:
                    # Define similar phrases for common answers
                    possible_answer_phrases = []
                    if answer == 'Decline':
                        possible_answer_phrases = ["Decline", "not wish", "don't wish", "Prefer not", "not want"]
                    elif isinstance(answer, str) and 'yes' in answer.lower():
                        possible_answer_phrases = ["Yes", "Agree", "I do", "I have"]
                    elif isinstance(answer, str) and 'no' in answer.lower():
                        possible_answer_phrases = ["No", "Disagree", "I don't", "I do not"]
                    else:
                        # Try partial matching for any answer
                        possible_answer_phrases = [str(answer)]
                        # Add lowercase and uppercase variants
                        possible_answer_phrases.append(str(answer).lower())
                        possible_answer_phrases.append(str(answer).upper())
                        # Try without special characters
                        possible_answer_phrases.append(''.join(c for c in str(answer) if c.isalnum()))
                    ##<
                    foundOption = False
                    for phrase in possible_answer_phrases:
                        for option in optionsText:
                            # Check if phrase is in option or option is in phrase (bidirectional matching)
                            if phrase.lower() in option.lower() or option.lower() in phrase.lower():
                                try:
                                    select.select_by_visible_text(option)
                                    answer = option
                                    foundOption = True
                                    break
                                except Exception:
                                    continue
                        if foundOption:
                            break
                    if not foundOption:
                        # Ask AI before random — pick the option that maximizes interview chances
                        if optionsText and not (_select_options_look_like_months(optionsText) or _select_options_look_like_years(optionsText)):
                            ai_ans = _ai_answer_for_field(
                                label_org,
                                options=optionsText,
                                question_type="single_select",
                                job_description=job_description,
                            )
                            matched = _match_ai_option(ai_ans, optionsText) if ai_ans else None
                            if matched:
                                try:
                                    select.select_by_visible_text(matched)
                                    answer = matched
                                    foundOption = True
                                    print_lg(f'AI selected dropdown option "{answer}" for "{label_org}"')
                                except Exception:
                                    pass
                        if not foundOption and (_select_options_look_like_months(optionsText) or _select_options_look_like_years(optionsText)):
                            # For month/year, pick a sensible option instead of pure random
                            fallback = _resolve_month_year_answer(label, aria_label, optionsText)
                            picked = _pick_select_option(select, optionsText, fallback) if fallback else None
                            if picked:
                                answer = picked
                                foundOption = True
                                print_lg(f'Filled date dropdown "{label_org}" with "{answer}"')
                        if not foundOption:
                            print_lg(f'Failed to find an option with text "{answer}" for question labelled "{label_org}", answering randomly!')
                            select.select_by_index(randint(1, len(select.options)-1))
                            answer = select.first_selected_option.text
                            randomly_answered_questions.add((f'{label_org} [ {options} ]',"select"))
            questions_list.add((f'{label_org} [ {options} ]', answer, "select", prev_answer))
            continue
        
        # Check if it's a radio Question
        radio = try_xp(Question, './/fieldset[@data-test-form-builder-radio-button-form-component="true"]', False)
        if radio:
            prev_answer = None
            label = try_xp(radio, './/span[@data-test-form-builder-radio-button-form-component__title]', False)
            try: label = find_by_class(label, "visually-hidden", 2.0)
            except: pass
            label_org = label.text if label else "Unknown"
            answer = 'Yes'
            label = label_org.lower()
            clean_label_org = label_org

            label_org += ' [ '
            options = radio.find_elements(By.TAG_NAME, 'input')
            options_labels = []
            option_texts = []
            
            for option in options:
                id = option.get_attribute("id")
                option_label = try_xp(radio, f'.//label[@for="{id}"]', False)
                opt_text = option_label.text if option_label else "Unknown"
                option_texts.append(opt_text)
                options_labels.append( f'"{opt_text}"<{option.get_attribute("value")}>' ) # Saving option as "label <value>"
                if option.is_selected(): prev_answer = options_labels[-1]
                label_org += f' {options_labels[-1]},'

            saved_answer = get_saved_answer(clean_label_org)
            if saved_answer is not None or overwrite_previous_answers or prev_answer is None:
                if saved_answer is not None:
                    answer = saved_answer
                elif 'citizenship' in label or 'employment eligibility' in label: answer = us_citizenship
                elif 'veteran' in label or 'protected' in label: answer = veteran_status
                elif 'disability' in label or 'handicapped' in label: 
                    answer = disability_status
                else:
                    answer = answer_common_questions(label, "")
                    # AI chooses the interview-maximizing radio option
                    if not answer:
                        ai_ans = _ai_answer_for_field(
                            clean_label_org,
                            options=option_texts,
                            question_type="single_select",
                            job_description=job_description,
                        )
                        matched = _match_ai_option(ai_ans, option_texts) if ai_ans else None
                        answer = matched or ai_ans or "Yes"
                foundOption = try_xp(radio, f".//label[normalize-space()='{answer}']", False)
                if foundOption: 
                    actions.move_to_element(foundOption).click().perform()
                else:    
                    possible_answer_phrases = ["Decline", "not wish", "don't wish", "Prefer not", "not want"] if answer == 'Decline' else [answer]
                    ele = options[0]
                    answer = options_labels[0]
                    matched_ai = False
                    for phrase in possible_answer_phrases:
                        for i, option_label in enumerate(options_labels):
                            if phrase in option_label:
                                foundOption = options[i]
                                ele = foundOption
                                answer = f'Decline ({option_label})' if len(possible_answer_phrases) > 1 else option_label
                                matched_ai = True
                                break
                        if foundOption: break
                    # If still unmatched, try AI against option texts
                    if not foundOption and option_texts:
                        ai_ans = _ai_answer_for_field(
                            clean_label_org,
                            options=option_texts,
                            question_type="single_select",
                            job_description=job_description,
                        )
                        matched = _match_ai_option(ai_ans, option_texts) if ai_ans else None
                        if matched:
                            for i, opt_text in enumerate(option_texts):
                                if opt_text == matched:
                                    ele = options[i]
                                    answer = options_labels[i]
                                    foundOption = ele
                                    matched_ai = True
                                    break
                    # Default to Yes-like option rather than first option when possible
                    if not foundOption:
                        for i, opt_text in enumerate(option_texts):
                            ol = (opt_text or "").lower()
                            if ol.startswith("yes") or ol in ("y", "true") or "agree" in ol or "i have" in ol or "willing" in ol:
                                ele = options[i]
                                answer = options_labels[i]
                                foundOption = ele
                                break
                    actions.move_to_element(ele).click().perform()
                    if not foundOption: randomly_answered_questions.add((f'{label_org} ]',"radio"))
            else: answer = prev_answer
            questions_list.add((label_org+" ]", answer, "radio", prev_answer))
            continue
        
        # Check if it's a text question
        text = try_xp(Question, ".//input[@type='text']", False)
        if text: 
            label = try_xp(Question, ".//label[@for]", False)
            try: label = label.find_element(By.CLASS_NAME,'visually-hidden')
            except: pass
            label_org = label.text if label else "Unknown"
            answer = "" # years_of_experience
            label = label_org.lower()
            is_location_typeahead = (
                'city' in label
                or 'location' in label
                or ('address' in label and 'email' not in label and 'mail' not in label)
            )

            prev_answer = text.get_attribute("value")
            saved_answer = get_saved_answer(label_org)
            if saved_answer is not None or not prev_answer or overwrite_previous_answers:
                if saved_answer is not None:
                    answer = saved_answer
                elif 'experience' in label or 'years' in label: answer = years_of_experience
                elif 'phone' in label or 'mobile' in label: answer = phone_number
                elif 'street' in label: answer = street
                elif is_location_typeahead:
                    answer = _location_answer_text(work_location)
                elif 'signature' in label: answer = full_name # 'signature' in label or 'legal name' in label or 'your name' in label or 'full name' in label: answer = full_name     # What if question is 'name of the city or university you attend, name of referral etc?'
                elif 'name' in label:
                    if 'full' in label: answer = full_name
                    elif 'first' in label and 'last' not in label: answer = first_name
                    elif 'middle' in label and 'last' not in label: answer = middle_name
                    elif 'last' in label and 'first' not in label: answer = last_name
                    elif 'employer' in label: answer = recent_employer
                    else: answer = full_name
                elif 'company' in label or 'employer' in label or 'organization' in label:
                    answer = recent_employer
                elif (
                    'title' in label
                    and 'city' not in label
                    and not any(
                        w in label
                        for w in (
                            'salary', 'compensation', 'ctc', 'pay', 'hybrid',
                            'wfh', 'remote', 'agree', 'available', 'expected',
                        )
                    )
                ):
                    # Work-experience job title only — not "this position is..." screening Qs
                    answer = get_saved_answer("your title") or get_saved_answer(label_org) or "QA Analyst"
                elif 'school' in label or 'university' in label or 'college' in label:
                    answer = get_saved_answer(label_org) or ""
                elif 'notice' in label:
                    if 'month' in label:
                        answer = notice_period_months
                    elif 'week' in label:
                        answer = notice_period_weeks
                    else: answer = notice_period
                elif 'salary' in label or 'compensation' in label or 'ctc' in label or 'pay' in label: 
                    if 'current' in label or 'present' in label:
                        if 'month' in label:
                            answer = current_ctc_monthly
                        elif 'lakh' in label:
                            answer = current_ctc_lakhs
                        else:
                            answer = current_ctc
                    else:
                        if 'month' in label:
                            answer = desired_salary_monthly
                        elif 'lakh' in label:
                            answer = desired_salary_lakhs
                        else:
                            answer = desired_salary
                elif 'linkedin' in label: answer = linkedIn
                elif 'website' in label or 'blog' in label or 'portfolio' in label or 'link' in label: answer = website
                elif 'scale of 1-10' in label: answer = confidence_level
                elif 'headline' in label: answer = linkedin_headline
                elif ('hear' in label or 'come across' in label) and 'this' in label and ('job' in label or 'position' in label): answer = "https://github.com/GodsScion/Auto_job_applier_linkedIn"
                elif 'state' in label or 'province' in label: answer = state
                elif 'zip' in label or 'postal' in label or 'code' in label: answer = zipcode
                elif 'country' in label: answer = country
                else: answer = answer_common_questions(label,answer)
                ##> ------ Yang Li : MARKYangL - Feature ------
                if answer == "":
                    if is_ai_enabled() and aiClient:
                        try:
                            if ai_provider.lower() == "openai":
                                answer = ai_answer_question(aiClient, label_org, question_type="text", job_description=job_description, user_information_all=user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                answer = deepseek_answer_question(aiClient, label_org, options=None, question_type="text", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            elif ai_provider.lower() == "gemini":
                                answer = gemini_answer_question(aiClient, label_org, options=None, question_type="text", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            else:
                                randomly_answered_questions.add((label_org, "text"))
                                answer = years_of_experience
                            if answer and isinstance(answer, str) and len(answer) > 0:
                                print_lg(f'AI Answered received for question "{label_org}" \nhere is answer: "{answer}"')
                            else:
                                randomly_answered_questions.add((label_org, "text"))
                                answer = years_of_experience
                        except Exception as e:
                            disable_ai_and_resume_on_rate_limit(e, source="AI answer")
                            print_lg("Failed to get AI answer!", e)
                            randomly_answered_questions.add((label_org, "text"))
                            answer = years_of_experience
                    else:
                        randomly_answered_questions.add((label_org, "text"))
                        answer = years_of_experience
                ##<
                text.clear()
                text.send_keys(answer)
                # Location (city) fields need an explicit typeahead pick, including saved answers
                if is_location_typeahead and answer:
                    _select_typeahead_suggestion(text, str(answer))
            questions_list.add((label, text.get_attribute("value"), "text", prev_answer))
            continue

        # Check if it's a textarea question
        text_area = try_xp(Question, ".//textarea", False)
        if text_area:
            label = try_xp(Question, ".//label[@for]", False)
            label_org = label.text if label else "Unknown"
            label = label_org.lower()
            answer = ""
            prev_answer = text_area.get_attribute("value")
            saved_answer = get_saved_answer(label_org)
            if saved_answer is not None or not prev_answer or overwrite_previous_answers:
                if saved_answer is not None:
                    answer = saved_answer
                elif 'summary' in label: answer = linkedin_summary
                elif 'cover' in label: answer = cover_letter
                elif 'description' in label:
                    # Work experience / role description
                    answer = (linkedin_summary or cover_letter or "").strip()
                if answer == "":
                ##> ------ Yang Li : MARKYangL - Feature ------
                    if is_ai_enabled() and aiClient:
                        try:
                            if ai_provider.lower() == "openai":
                                answer = ai_answer_question(aiClient, label_org, question_type="textarea", job_description=job_description, user_information_all=user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                answer = deepseek_answer_question(aiClient, label_org, options=None, question_type="textarea", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            elif ai_provider.lower() == "gemini":
                                answer = gemini_answer_question(aiClient, label_org, options=None, question_type="textarea", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            else:
                                randomly_answered_questions.add((label_org, "textarea"))
                                answer = ""
                            if answer and isinstance(answer, str) and len(answer) > 0:
                                print_lg(f'AI Answered received for question "{label_org}" \nhere is answer: "{answer}"')
                            else:
                                randomly_answered_questions.add((label_org, "textarea"))
                                answer = ""
                        except Exception as e:
                            disable_ai_and_resume_on_rate_limit(e, source="AI answer")
                            print_lg("Failed to get AI answer!", e)
                            randomly_answered_questions.add((label_org, "textarea"))
                            answer = ""
                    else:
                        randomly_answered_questions.add((label_org, "textarea"))
                        answer = ""
            text_area.clear()
            text_area.send_keys(answer)
            questions_list.add((label, text_area.get_attribute("value"), "textarea", prev_answer))
            ##<
            continue

        # Check if it's a checkbox question
        checkbox = try_xp(Question, ".//input[@type='checkbox']", False)
        if checkbox:
            label = try_xp(Question, ".//span[@class='visually-hidden']", False)
            label_org = label.text if label else "Unknown"
            label = label_org.lower()
            answer = try_xp(Question, ".//label[@for]", False)  # Sometimes multiple checkboxes are given for 1 question, Not accounted for that yet
            answer = answer.text if answer else "Unknown"
            prev_answer = checkbox.is_selected()
            checked = prev_answer
            saved_answer = get_saved_answer(label_org)
            if saved_answer is not None:
                want_checked = saved_answer.lower() in ("true", "yes", "1", "checked")
                if want_checked != checkbox.is_selected():
                    try:
                        actions.move_to_element(checkbox).click().perform()
                        checked = want_checked
                    except Exception as e:
                        print_lg("Checkbox click failed!", e)
                        pass
                else:
                    checked = want_checked
            elif any(k in label for k in ["currently work", "i currently work", "current role", "still work here"]):
                # Work experience forms: check "I currently work here" so To-date can be optional/present
                if not prev_answer:
                    try:
                        actions.move_to_element(checkbox).click().perform()
                        checked = True
                        print_lg(f'Checked "{label_org}" for current employment.')
                    except Exception as e:
                        print_lg("Checkbox click failed!", e)
                        pass
            elif not prev_answer:
                try:
                    actions.move_to_element(checkbox).click().perform()
                    checked = True
                except Exception as e:
                    print_lg("Checkbox click failed!", e)
                    pass
            questions_list.add((f'{label} ([X] {answer})', checked, "checkbox", prev_answer))
            continue


    # Select todays date
    try_xp(driver, "//button[contains(@aria-label, 'This is today')]")

    # Collect important skills
    # if 'do you have' in label and 'experience' in label and ' in ' in label -> Get word (skill) after ' in ' from label
    # if 'how many years of experience do you have in ' in label -> Get word (skill) after ' in '

    return questions_list




def external_apply(pagination_element: WebElement, job_id: str, job_link: str, resume: str, date_listed, application_link: str, screenshot_name: str) -> tuple[bool, str, int]:
    '''
    Function to open new tab and save external job application links
    '''
    global tabs_count, dailyEasyApplyLimitReached
    if easy_apply_only:
        try:
            if _linkedin_daily_submission_limit_reached():
                _mark_daily_limit_and_stop_search()
        except Exception:
            pass
        print_lg("Easy apply failed I guess!")
        if pagination_element != None: return True, application_link, tabs_count
    try:
        wait.until(EC.element_to_be_clickable((By.XPATH, ".//button[contains(@class,'jobs-apply-button') and contains(@class, 'artdeco-button--3')]"))).click() # './/button[contains(span, "Apply") and not(span[contains(@class, "disabled")])]'
        wait_span_click(driver, "Continue", 1, True, False)
        windows = driver.window_handles
        tabs_count = len(windows)
        driver.switch_to.window(windows[-1])
        application_link = driver.current_url
        print_lg('Got the external application link "{}"'.format(application_link))
        if close_tabs and driver.current_window_handle != linkedIn_tab: driver.close()
        driver.switch_to.window(linkedIn_tab)
        return False, application_link, tabs_count
    except Exception as e:
        # print_lg(e)
        print_lg("Failed to apply!")
        failed_job(job_id, job_link, resume, date_listed, "Probably didn't find Apply button or unable to switch tabs.", e, application_link, screenshot_name)
        global failed_count
        failed_count += 1
        return True, application_link, tabs_count



def follow_company(modal: WebDriver = driver) -> None:
    '''
    Function to follow or un-follow easy applied companies based om `follow_companies`
    '''
    try:
        follow_checkbox_input = try_xp(modal, ".//input[@id='follow-company-checkbox' and @type='checkbox']", False)
        if follow_checkbox_input and follow_checkbox_input.is_selected() != follow_companies:
            try_xp(modal, ".//label[@for='follow-company-checkbox']")
    except Exception as e:
        print_lg("Failed to update follow companies checkbox!", e)
    


#< Failed attempts logging
def failed_job(job_id: str, job_link: str, resume: str, date_listed, error: str, exception: Exception, application_link: str, screenshot_name: str) -> None:
    '''
    Function to update failed jobs list in excel
    '''
    try:
        with open(failed_file_name, 'a', newline='', encoding='utf-8') as file:
            fieldnames = ['Job ID', 'Job Link', 'Resume Tried', 'Date listed', 'Date Tried', 'Assumed Reason', 'Stack Trace', 'External Job link', 'Screenshot Name']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if file.tell() == 0: writer.writeheader()
            writer.writerow({'Job ID':truncate_for_csv(job_id), 'Job Link':truncate_for_csv(job_link), 'Resume Tried':truncate_for_csv(_resume_path_for_csv(resume)), 'Date listed':truncate_for_csv(date_listed), 'Date Tried':datetime.now(), 'Assumed Reason':truncate_for_csv(error), 'Stack Trace':truncate_for_csv(exception), 'External Job link':truncate_for_csv(application_link), 'Screenshot Name':truncate_for_csv(screenshot_name)})
            file.close()
    except Exception as e:
        print_lg("Failed to update failed jobs list!", e)
        if block_on_failed_logging:
            pyautogui.alert("Failed to update the excel of failed jobs!\nProbably because of 1 of the following reasons:\n1. The file is currently open or in use by another program\n2. Permission denied to write to the file\n3. Failed to find the file", "Failed Logging")


def screenshot(driver: WebDriver, job_id: str, failedAt: str) -> str:
    '''
    Function to to take screenshot for debugging
    - Returns screenshot name as String
    '''
    screenshot_name = "{} - {} - {}.png".format( job_id, failedAt, str(datetime.now()) )
    path = logs_folder_path+"/screenshots/"+screenshot_name.replace(":",".")
    # special_chars = {'*', '"', '\\', '<', '>', ':', '|', '?'}
    # for char in special_chars:  path = path.replace(char, '-')
    driver.save_screenshot(path.replace("//","/"))
    return screenshot_name
#>



def submitted_jobs(job_id: str, title: str, company: str, work_location: str, work_style: str, description: str, experience_required: int | Literal['Unknown', 'Error in extraction'], 
                   skills: list[str] | Literal['In Development'], hr_name: str | Literal['Unknown'], hr_link: str | Literal['Unknown'], resume: str, 
                   reposted: bool, date_listed: datetime | Literal['Unknown'], date_applied:  datetime | Literal['Pending'], job_link: str, application_link: str, 
                   questions_list: set | None, connect_request: Literal['In Development']) -> None:
    '''
    Function to create or update the Applied jobs CSV file, once the application is submitted successfully
    '''
    try:
        with open(file_name, mode='a', newline='', encoding='utf-8') as csv_file:
            fieldnames = ['Job ID', 'Title', 'Company', 'Work Location', 'Work Style', 'About Job', 'Experience required', 'Skills required', 'HR Name', 'HR Link', 'Resume', 'Re-posted', 'Date Posted', 'Date Applied', 'Job Link', 'External Job link', 'Questions Found', 'Connect Request']
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            if csv_file.tell() == 0: writer.writeheader()
            writer.writerow({'Job ID':truncate_for_csv(job_id), 'Title':truncate_for_csv(title), 'Company':truncate_for_csv(company), 'Work Location':truncate_for_csv(work_location), 'Work Style':truncate_for_csv(work_style), 
                            'About Job':truncate_for_csv(description), 'Experience required': truncate_for_csv(experience_required), 'Skills required':truncate_for_csv(skills), 
                                'HR Name':truncate_for_csv(hr_name), 'HR Link':truncate_for_csv(hr_link), 'Resume':truncate_for_csv(_resume_path_for_csv(resume)), 'Re-posted':truncate_for_csv(reposted), 
                                'Date Posted':truncate_for_csv(date_listed), 'Date Applied':truncate_for_csv(date_applied), 'Job Link':truncate_for_csv(job_link), 
                                'External Job link':truncate_for_csv(application_link), 'Questions Found':truncate_for_csv(questions_list), 'Connect Request':truncate_for_csv(connect_request)})
        csv_file.close()
    except Exception as e:
        print_lg("Failed to update submitted jobs list!", e)
        if block_on_failed_logging:
            pyautogui.alert("Failed to update the excel of applied jobs!\nProbably because of 1 of the following reasons:\n1. The file is currently open or in use by another program\n2. Permission denied to write to the file\n3. Failed to find the file", "Failed Logging")



# Function to discard the job application
def _is_dead_browser_error(exc: BaseException) -> bool:
    '''True only when the Chrome/WebDriver session is actually dead — not timeouts.'''
    if isinstance(exc, (NoSuchWindowException, InvalidSessionIdException)):
        return True
    if isinstance(exc, TimeoutException):
        return False
    if isinstance(exc, (ConnectionResetError, ConnectionError, OSError)):
        return True
    if isinstance(exc, WebDriverException):
        msg = (str(exc) or "").lower()
        dead_markers = (
            "invalid session id",
            "chrome not reachable",
            "disconnected",
            "session deleted",
            "browser has closed",
            "no such window",
            "target window already closed",
            "unable to connect to renderer",
            "connection refused",
        )
        return any(m in msg for m in dead_markers)
    return False


def _refresh_easy_apply_modal() -> WebElement:
    '''Re-locate the Easy Apply modal after DOM updates (avoids stale element).'''
    return find_by_class(driver, "jobs-easy-apply-modal")


def _easy_apply_on_review_or_submit() -> bool:
    '''True if Review/Submit controls are already visible (modal near the end).'''
    for text in ("Submit application", "Review", "Done"):
        try:
            els = driver.find_elements(
                By.XPATH,
                f'//*[self::button or self::span][contains(normalize-space(.), "{text}")]',
            )
            if any(el.is_displayed() for el in els):
                return True
        except Exception:
            continue
    return False


def discard_job() -> None:
    try:
        actions.send_keys(Keys.ESCAPE).perform()
        buffer(click_gap)
        if not wait_span_click(driver, 'Discard', 2):
            # Already closed or no discard prompt — not fatal
            try:
                actions.send_keys(Keys.ESCAPE).perform()
            except Exception:
                pass
    except Exception as e:
        print_lg("Discard job cleanup skipped:", e)






def build_jobs_search_url(job_title: str) -> str:
    '''
    Build a parameterized LinkedIn jobs search URL (no UI filter clicks).
    Empty optional values are omitted so we do not send blank query flags.
    '''
    params = []
    if (search_actively_hiring or "").strip():
        params.append(("f_AL", search_actively_hiring.strip()))
    if (search_experience_levels or "").strip():
        levels = ",".join(p.strip() for p in search_experience_levels.split(",") if p.strip())
        if levels:
            params.append(("f_E", levels))
    if (search_time_posted or "").strip():
        params.append(("f_TPR", search_time_posted.strip()))
    if (search_geo_id or "").strip():
        params.append(("geoId", search_geo_id.strip()))
    params.append(("keywords", job_title))
    origin = (search_origin or "").strip() or "JOB_SEARCH_PAGE_JOB_FILTER"
    params.append(("origin", origin))
    if (search_sort_order or "").strip():
        params.append(("sortBy", search_sort_order.strip()))
    return "https://www.linkedin.com/jobs/search/?" + urlencode(params)


# Detect LinkedIn empty search results ("No matching jobs found.")
def _no_matching_jobs_found() -> bool:
    try:
        for xpath in (
            '//*[contains(normalize-space(.), "No matching jobs found")]',
            '//h1[contains(., "No matching jobs")]',
            '//h2[contains(., "No matching jobs")]',
        ):
            try:
                els = driver.find_elements(By.XPATH, xpath)
                for el in els:
                    if el.is_displayed() and "no matching jobs" in (el.text or "").lower():
                        return True
            except Exception:
                continue
        body = (driver.find_element(By.TAG_NAME, "body").text or "").lower()
        return "no matching jobs found" in body
    except Exception:
        return False


_DAILY_LIMIT_PHRASES = (
    "we limit daily submissions",
    "save this job and apply tomorrow",
    "exceeded the daily application limit",
    "daily application limit",
    "limit daily submissions to maintain quality",
)


def _linkedin_daily_submission_limit_reached() -> bool:
    '''True when LinkedIn disabled Easy Apply due to daily submission / anti-bot cap.'''
    try:
        for xp in (
            '//*[contains(@class,"artdeco-inline-feedback")]',
            '//*[contains(@class,"jobs-s-apply")]',
            '//*[contains(@class,"jobs-apply-button")]/..',
        ):
            try:
                for el in driver.find_elements(By.XPATH, xp):
                    try:
                        if not el.is_displayed():
                            continue
                        text = (el.text or "").lower()
                        if any(p in text for p in _DAILY_LIMIT_PHRASES):
                            return True
                    except Exception:
                        continue
            except Exception:
                continue
        body = (driver.find_element(By.TAG_NAME, "body").text or "").lower()
        return any(p in body for p in _DAILY_LIMIT_PHRASES)
    except Exception:
        return False


def _mark_daily_limit_and_stop_search() -> None:
    global dailyEasyApplyLimitReached
    dailyEasyApplyLimitReached = True
    print_lg(
        "\n###############  LinkedIn daily application limit reached  ###############\n"
        'Message like: "We limit daily submissions... Save this job and apply tomorrow."\n'
        f"Pausing applying for {daily_limit_pause_hours} hour(s) "
        f"(config/settings.py → daily_limit_pause_hours).\n"
    )


def _pause_after_daily_limit() -> None:
    '''Sleep daily_limit_pause_hours, abortable via STOP BOT / Ctrl+Shift+Q.'''
    hours = max(1, int(daily_limit_pause_hours))
    total_sec = hours * 3600
    print_lg(
        f"Daily-limit pause started at {datetime.now()}. "
        f"Will resume around {datetime.now() + timedelta(seconds=total_sec)} "
        f"({hours} hour(s))."
    )
    slept = 0
    chunk = 60
    while slept < total_sec:
        raise_if_stopped()
        if keep_screen_awake:
            try:
                pyautogui.press("shift")
            except Exception:
                pass
        remaining = total_sec - slept
        wait_s = min(chunk, remaining)
        sleep(wait_s)
        slept += wait_s
        left_min = (total_sec - slept) // 60
        if slept % 1800 == 0 or slept >= total_sec:
            print_lg(
                f"Daily-limit pause: {slept // 60} min elapsed, {left_min} min remaining."
            )
    print_lg(f"Daily-limit pause finished at {datetime.now()}. Resuming search.")


# Function to apply to jobs
def apply_to_jobs(search_terms: list[str]) -> None:
    applied_jobs = get_applied_job_ids()
    rejected_jobs = set()
    blacklisted_companies = set()
    global current_city, failed_count, skip_count, easy_applied_count, external_jobs_count, tabs_count, pause_before_submit, pause_at_failed_question, useNewResume, cycle_had_usable_listings
    current_city = current_city.strip()

    if randomize_search_order:  shuffle(search_terms)
    for searchTerm in search_terms:
        search_url = build_jobs_search_url(searchTerm)
        driver.get(search_url)
        print_lg("\n________________________________________________________________________________________________________________________\n")
        print_lg(f'\n>>>> Now searching for "{searchTerm}" <<<<\n\n')
        print_lg(f"Search URL: {search_url}")
        sleep(2)
        _wait_jobs_search_ready(15)

        buffer(2)
        sleep(2)

        # If filters yield zero results, move on to the next search query immediately
        if _no_matching_jobs_found():
            print_lg(f'No matching jobs found for "{searchTerm}". Switching to next search query...\n')
            continue

        current_count = 0
        try:
            while current_count < switch_number:
                # Wait until job listings are loaded
                try:
                    wait.until(EC.presence_of_all_elements_located((By.XPATH, "//li[@data-occludable-job-id]")))
                except Exception:
                    if _no_matching_jobs_found():
                        print_lg(f'No matching jobs found for "{searchTerm}". Switching to next search query...\n')
                        break
                    raise

                pagination_element, current_page = get_page_info()

                # Find all job listings in current page
                buffer(3)
                job_listings = driver.find_elements(By.XPATH, "//li[@data-occludable-job-id]")  
                if not job_listings:
                    if _no_matching_jobs_found():
                        print_lg(f'No matching jobs found for "{searchTerm}". Switching to next search query...\n')
                    else:
                        print_lg(f'No job listings loaded for "{searchTerm}". Switching to next search query...\n')
                    break

                listing_count = len(job_listings)
                cycle_had_usable_listings = True
                listings_lost = False
                for job_index in range(listing_count):
                    raise_if_stopped()
                    if keep_screen_awake:
                        try:
                            pyautogui.press('shift')
                        except Exception:
                            pass
                    if current_count >= switch_number: break
                    # Re-find cards each iteration — DOM goes stale after Easy Apply closes
                    try:
                        fresh_listings = driver.find_elements(By.XPATH, "//li[@data-occludable-job-id]")
                        if job_index >= len(fresh_listings):
                            print_lg("Job list changed/shortened after apply; continuing from next page/search.")
                            break
                        job = fresh_listings[job_index]
                    except StaleElementReferenceException as e:
                        print_lg(
                            f'Job listings went stale for "{searchTerm}"; '
                            f"switching to next search query...",
                            e,
                        )
                        listings_lost = True
                        break
                    except Exception as e:
                        print_lg(
                            f'Could not refresh job listings for "{searchTerm}"; '
                            f"switching to next search query...",
                            e,
                        )
                        listings_lost = True
                        break

                    print_lg("\n-@-\n")

                    try:
                        job_id,title,company,work_location,work_style,skip = get_job_main_details(job, blacklisted_companies, rejected_jobs)
                    except StaleElementReferenceException as e:
                        print_lg(
                            f'Stale job card on "{searchTerm}"; switching to next search query...',
                            e,
                        )
                        listings_lost = True
                        break
                    
                    if skip: continue
                    # Redundant fail safe check for applied jobs!
                    # NOTE: find_by_class raises TimeoutException when the "already applied"
                    # link is absent — that is normal and must NOT kill the run.
                    try:
                        if job_id in applied_jobs:
                            print_lg(f'Already applied to "{title} | {company}" job. Job ID: {job_id}!')
                            continue
                        if find_by_class(driver, "jobs-s-apply__application-link", 2):
                            print_lg(f'Already applied to "{title} | {company}" job. Job ID: {job_id}!')
                            continue
                    except Exception as e:
                        if _is_dead_browser_error(e):
                            raise
                        print_lg(f'Trying to Apply to "{title} | {company}" job. Job ID: {job_id}')

                    job_link = "https://www.linkedin.com/jobs/view/"+job_id
                    application_link = "Easy Applied"
                    date_applied = "Pending"
                    hr_link = "Unknown"
                    hr_name = "Unknown"
                    connect_request = "In Development" # Still in development
                    date_listed = "Unknown"
                    skills = "Needs an AI" # Still in development
                    resume = "Pending"
                    reposted = False
                    questions_list = None
                    screenshot_name = "Not Available"

                    try:
                        rejected_jobs, blacklisted_companies, jobs_top_card = check_blacklist(rejected_jobs,job_id,company,blacklisted_companies)
                    except ValueError as e:
                        print_lg("JD rejected by existing eligibility rules")
                        print_lg(e, 'Skipping this job!\n')
                        failed_job(job_id, job_link, resume, date_listed, "Found Blacklisted words in About Company", e, "Skipped", screenshot_name)
                        skip_count += 1
                        continue
                    except Exception as e:
                        print_lg("Failed to scroll to About Company!")
                        # print_lg(e)



                    # Hiring Manager info
                    try:
                        hr_info_card = WebDriverWait(driver,2).until(EC.presence_of_element_located((By.CLASS_NAME, "hirer-card__hirer-information")))
                        hr_link = hr_info_card.find_element(By.TAG_NAME, "a").get_attribute("href")
                        hr_name = hr_info_card.find_element(By.TAG_NAME, "span").text
                        # if connect_hr:
                        #     driver.switch_to.new_window('tab')
                        #     driver.get(hr_link)
                        #     wait_span_click("More")
                        #     wait_span_click("Connect")
                        #     wait_span_click("Add a note")
                        #     message_box = driver.find_element(By.XPATH, "//textarea")
                        #     message_box.send_keys(connect_request_message)
                        #     if close_tabs: driver.close()
                        #     driver.switch_to.window(linkedIn_tab) 
                        # def message_hr(hr_info_card):
                        #     if not hr_info_card: return False
                        #     hr_info_card.find_element(By.XPATH, ".//span[normalize-space()='Message']").click()
                        #     message_box = driver.find_element(By.XPATH, "//div[@aria-label='Write a message…']")
                        #     message_box.send_keys()
                        #     try_xp(driver, "//button[normalize-space()='Send']")        
                    except Exception as e:
                        print_lg(f'HR info was not given for "{title}" with Job ID: {job_id}!')
                        # print_lg(e)


                    # Calculation of date posted
                    time_posted_text = None
                    try:
                        # try: time_posted_text = find_by_class(driver, "jobs-unified-top-card__posted-date", 2).text
                        # except: 
                        time_posted_text = jobs_top_card.find_element(By.XPATH, './/span[contains(normalize-space(), " ago")]').text
                        print("Time Posted: " + time_posted_text)
                        if time_posted_text.__contains__("Reposted"):
                            reposted = True
                            time_posted_text = time_posted_text.replace("Reposted", "")
                        date_listed = calculate_date_posted(time_posted_text.strip())
                    except Exception as e:
                        print_lg("Failed to calculate the date posted!",e)

                    # Recent-job gate (reusable job_age_minutes). OFF → always apply.
                    parsed_age = parse_job_age_minutes(time_posted_text)
                    if parsed_age is None:
                        job_age_minutes = recent_job_default_age_minutes
                    else:
                        job_age_minutes = parsed_age
                    if recent_job_feature_enabled:
                        posted_label = (time_posted_text or "unknown").strip() or "unknown"
                        if is_within_recent_job_window(
                            job_age_minutes,
                            enabled=True,
                            max_age_minutes=recent_job_max_age_minutes,
                        ):
                            print_lg(
                                f"[Recent Job] Posted: {posted_label} | Age: {job_age_minutes} min | "
                                f"Limit: {recent_job_max_age_minutes} min | APPLY"
                            )
                        else:
                            print_lg("JD rejected by existing eligibility rules")
                            print_lg(
                                f"[Recent Job] Age: {job_age_minutes} min | "
                                f"Limit: {recent_job_max_age_minutes} min | SKIP"
                            )
                            failed_job(
                                job_id,
                                job_link,
                                resume,
                                date_listed,
                                "Job older than recent_job_max_age_minutes",
                                f"job_age_minutes={job_age_minutes} > limit={recent_job_max_age_minutes}",
                                "Skipped",
                                screenshot_name,
                            )
                            rejected_jobs.add(job_id)
                            skip_count += 1
                            continue

                    description, experience_required, skip, reason, message = get_job_description()
                    if skip:
                        print_lg("JD rejected by existing eligibility rules")
                        print_lg(message)
                        failed_job(job_id, job_link, resume, date_listed, reason, message, "Skipped", screenshot_name)
                        rejected_jobs.add(job_id)
                        skip_count += 1
                        continue

                    jd_usable, _jd_reason = _is_job_description_usable(description)
                    continue_apply, score_reason, score_message = apply_resume_score_gate(
                        description, aiClient, jd_usable
                    )
                    if not continue_apply:
                        failed_job(
                            job_id,
                            job_link,
                            resume,
                            date_listed,
                            score_reason,
                            score_message,
                            "Skipped",
                            screenshot_name,
                        )
                        rejected_jobs.add(job_id)
                        skip_count += 1
                        continue

                    
                    if is_ai_enabled() and extract_job_skills_with_ai and description != "Unknown":
                        ##> ------ Yang Li : MARKYangL - Feature ------
                        try:
                            raise_if_stopped()
                            if ai_provider.lower() == "openai":
                                skills = ai_extract_skills(aiClient, description)
                            elif ai_provider.lower() == "deepseek":
                                skills = deepseek_extract_skills(aiClient, description)
                            elif ai_provider.lower() == "gemini":
                                skills = gemini_extract_skills(aiClient, description)
                            else:
                                skills = "In Development"
                            print_lg(f"Extracted skills using {ai_provider} AI")
                        except BotStopped:
                            raise
                        except Exception as e:
                            disable_ai_and_resume_on_rate_limit(e, source="skills extraction")
                            print_lg("Failed to extract skills:", e)
                            skills = "Error extracting skills"
                        ##<
                    elif not extract_job_skills_with_ai:
                        skills = "Skills extraction skipped"

                    uploaded = False
                    if _linkedin_daily_submission_limit_reached():
                        _mark_daily_limit_and_stop_search()
                        return
                    # Case 1: Easy Apply Button
                    # First try the classic button with "Easy" in aria-label
                    is_easy_apply = try_xp(driver, ".//button[contains(@class,'jobs-apply-button') and contains(@class, 'artdeco-button--3') and contains(@aria-label, 'Easy')]")
                    # Fallback 1: check if apply link contains Easy Apply URL pattern
                    if not is_easy_apply:
                        try:
                            apply_link_el = driver.find_element(By.XPATH, ".//a[contains(@href, 'openSDUIApplyFlow=true')]")
                            if apply_link_el:
                                apply_link_el.click()
                                is_easy_apply = True
                                print_lg("Detected Easy Apply via URL pattern (openSDUIApplyFlow)")
                        except:
                            pass
                    # Fallback 2: click any Apply button and check if Easy Apply modal appears
                    if not is_easy_apply:
                        try:
                            apply_btn = driver.find_element(By.XPATH, ".//button[contains(@class,'jobs-apply-button')]")
                            if apply_btn:
                                tabs_before = len(driver.window_handles)
                                apply_btn.click()
                                buffer(click_gap)
                                tabs_after = len(driver.window_handles)
                                if tabs_after > tabs_before:
                                    # New tab opened — external apply, close it and go back
                                    driver.switch_to.window(driver.window_handles[-1])
                                    if close_tabs and driver.current_window_handle != linkedIn_tab: driver.close()
                                    driver.switch_to.window(linkedIn_tab)
                                    print_lg("External apply detected via new tab, skipping")
                                else:
                                    try:
                                        find_by_class(driver, "jobs-easy-apply-modal")
                                        is_easy_apply = True
                                        print_lg("Detected Easy Apply via modal appearance after click")
                                    except:
                                        # Modal didn't appear — dismiss
                                        try: actions.send_keys(Keys.ESCAPE).perform()
                                        except: pass
                        except:
                            pass
                    if is_easy_apply:
                        try: 
                            try:
                                errored = ""
                                resume_pdf_path = default_resume_path
                                modal = _refresh_easy_apply_modal()
                                wait_span_click(modal, "Next", 1)
                                resume = "Previous resume"
                                next_button = True
                                questions_list = set()
                                next_counter = 0
                                stale_retries = 0
                                while next_button:
                                    next_counter += 1
                                    if next_counter >= 15: 
                                        if pause_at_failed_question:
                                            screenshot(driver, job_id, "Needed manual intervention for failed question")
                                            help_timeout_sec = max(1, int(failed_question_timeout_minutes)) * 60
                                            help_decision = pyautogui.alert(
                                                "Couldn't answer one or more questions.\n\n"
                                                "1. CORRECT the form in LinkedIn now (replace any wrong/random values).\n"
                                                "2. Do NOT click Back/Next/Review/Save in LinkedIn.\n"
                                                "3. Click \"Continue\" here.\n\n"
                                                f"If you do nothing for {failed_question_timeout_minutes} min, "
                                                "this application is discarded and the bot moves on.\n\n"
                                                "ONLY your corrected answers will be saved to config/saved_answers.json.\n"
                                                "Bot random answers are NOT saved automatically anymore.\n\n"
                                                "You can turn off \"Pause at failed question\" in config/questions.py",
                                                "Help Needed - Correct then Continue",
                                                "Continue",
                                                timeout=help_timeout_sec,
                                            )
                                            if help_decision == "Timeout":
                                                print_lg(
                                                    f"Help Needed timed out after {failed_question_timeout_minutes} min. "
                                                    "Discarding application and moving to next job."
                                                )
                                                screenshot_name = screenshot(driver, job_id, "Help timeout discarded")
                                                errored = "help_timeout"
                                                raise Exception("Help timeout — discarded")
                                            try:
                                                modal = _refresh_easy_apply_modal()
                                                # Force-overwrite with whatever the USER left on screen
                                                capture_current_page_and_save(modal, force_overwrite=True)
                                            except Exception as e:
                                                print_lg("Failed to save answers after failed-question pause!", e)
                                            # Prefer continuing with the user's values (no immediate re-randomize)
                                            try:
                                                modal = _refresh_easy_apply_modal()
                                                action_btn = _click_easy_apply_modal_action(modal)
                                                if action_btn is not None:
                                                    print_lg(f'After your edits, clicking: "{(action_btn.text or "").strip()}"')
                                                    try:
                                                        action_btn.click()
                                                    except (ElementClickInterceptedException, StaleElementReferenceException):
                                                        driver.execute_script("arguments[0].click();", action_btn)
                                                    buffer(click_gap)
                                                    next_counter = 1
                                                    continue
                                            except Exception as e:
                                                print_lg("Could not click continue after your edits; will retry with saved answers.", e)
                                            next_counter = 1
                                            continue
                                        if questions_list: print_lg("Stuck for one or some of the following questions...", questions_list)
                                        screenshot_name = screenshot(driver, job_id, "Failed at questions")
                                        errored = "stuck"
                                        raise Exception("Seems like stuck in a continuous loop of next, probably because of new questions.")
                                    try:
                                        modal = _refresh_easy_apply_modal()
                                        # Open work experience / education editor if only "+ Add more" is shown
                                        try:
                                            _click_add_more_if_needed(modal)
                                        except Exception as e:
                                            print_lg("Add more click failed:", e)
                                        questions_list = answer_questions(modal, questions_list, work_location, job_description=description)
                                        # Resume generate/upload happens on Review (before Submit), not mid-form.
                                        # Do NOT auto-save bot fills here — that was saving random/trash answers.
                                        # Your corrections are saved only on pause Continue / before-submit confirm.
                                        next_button = _click_easy_apply_modal_action(modal)
                                        if next_button is None:
                                            # Maybe need Add more first
                                            if _click_add_more_if_needed(modal):
                                                questions_list = answer_questions(modal, questions_list, work_location, job_description=description)
                                                next_button = _click_easy_apply_modal_action(modal)
                                        if next_button is None:
                                            if _easy_apply_on_review_or_submit():
                                                print_lg("Easy Apply appears ready for Review/Submit; leaving step loop.")
                                                break
                                            print_lg("No Next/Review/Save/Continue button found on Easy Apply modal.")
                                            raise NoSuchElementException("Easy Apply continue button not found")
                                        action_text = (next_button.text or "").strip()
                                        # Extra safety: never Next while Save form is open
                                        if action_text.lower() == "next" and _modal_has_open_save_form(modal):
                                            save_btn = None
                                            for xpath in ('.//span[normalize-space(.)="Save"]', './/button[contains(., "Save")]'):
                                                try:
                                                    save_btn = modal.find_element(By.XPATH, xpath)
                                                    if save_btn.is_displayed():
                                                        next_button = save_btn
                                                        action_text = "Save"
                                                        break
                                                except Exception:
                                                    pass
                                        print_lg(f'Clicking Easy Apply action: "{action_text or next_button.tag_name}"')
                                        try:
                                            next_button.click()
                                        except ElementClickInterceptedException:
                                            driver.execute_script("arguments[0].click();", next_button)
                                        except StaleElementReferenceException:
                                            # Re-find action after refresh and retry once
                                            modal = _refresh_easy_apply_modal()
                                            next_button = _click_easy_apply_modal_action(modal)
                                            if next_button is None:
                                                if _easy_apply_on_review_or_submit():
                                                    break
                                                raise
                                            try:
                                                next_button.click()
                                            except ElementClickInterceptedException:
                                                driver.execute_script("arguments[0].click();", next_button)
                                        # After Save, wait briefly for list view / Next to appear
                                        if action_text.lower() == "save":
                                            sleep(1.5)
                                            buffer(click_gap)
                                        stale_retries = 0
                                    except StaleElementReferenceException as e:
                                        stale_retries += 1
                                        print_lg(f"Stale Easy Apply modal element; refreshing ({stale_retries}/3)...", e)
                                        if stale_retries > 3:
                                            raise
                                        buffer(click_gap)
                                        continue
                                    buffer(click_gap)

                            except NoSuchElementException: errored = "nose"
                            finally:
                                if questions_list and errored not in ("stuck", "help_timeout"):
                                    print_lg("Answered the following questions...", questions_list)
                                    print("\n\n" + "\n".join(str(question) for question in questions_list) + "\n\n")
                                # Stuck / help-timeout: skip Review/resume/submit; outer except discards.
                                if errored in ("stuck", "help_timeout"):
                                    pass
                                else:
                                    wait_span_click(driver, "Review", 1, scrollTop=True)
                                    try:
                                        modal = _refresh_easy_apply_modal()
                                    except Exception:
                                        modal = driver
                                    # Review flow: generate (or fallback) → Edit Resume → upload → Submit.
                                    print_lg("On Review page — preparing resume for upload...")
                                    resume_pdf_path = _prepare_resume_pdf_for_job(
                                        title, company, work_location, work_style, description
                                    )
                                    # Always land on a real file: generated PDF or default_resume_path
                                    resume_pdf_path = _resolve_resume_path_or_fallback(resume_pdf_path)
                                    maybe_send_jd_outreach(description, resume_pdf_path)
                                    try:
                                        modal = _refresh_easy_apply_modal()
                                    except Exception:
                                        modal = driver
                                    if not uploaded:
                                        uploaded, resume, modal = _upload_resume_on_review(
                                            modal, resume_pdf_path
                                        )
                                        if uploaded:
                                            print_lg(f"Uploaded resume on Review: {resume}")
                                        else:
                                            print_lg(
                                                "Could not upload after Resume Edit; "
                                                "continuing with previously uploaded LinkedIn resume."
                                            )
                                            resume = os.path.abspath(resume_pdf_path)
                                    # Resume Edit leaves mid-form — advance Next→… until Submit exists
                                    try:
                                        modal = _refresh_easy_apply_modal()
                                    except Exception:
                                        modal = driver
                                    if not _submit_application_visible(modal):
                                        print_lg("Submit not visible yet — advancing with Next/Continue/Review...")
                                        modal, _ = _advance_easy_apply_toward_submit(modal)
                                    cur_pause_before_submit = pause_before_submit
                                    if cur_pause_before_submit:
                                        decision = pyautogui.confirm('1. Please verify your information.\n2. If you edited something, please return to this final screen.\n3. DO NOT CLICK "Submit Application".\n\nYour edits will be saved automatically when you click Submit Application.\n\n\n\nYou can turn off "Pause before submit" setting in config.py\nTo TEMPORARILY disable pausing, click "Disable Pause"', "Confirm your information",["Disable Pause", "Discard Application", "Submit Application"])
                                        if decision == "Discard Application":
                                            raise Exception("Job application discarded by user!")
                                        pause_before_submit = False if "Disable Pause" == decision else True
                                        if decision == "Submit Application":
                                            try:
                                                modal = _refresh_easy_apply_modal()
                                                capture_all_pages_and_save(modal)
                                                print_lg("Saved your verified answers before submit.")
                                            except Exception as e:
                                                print_lg("Failed to save answers before submit!", e)
                                    try:
                                        modal = _refresh_easy_apply_modal()
                                    except Exception:
                                        modal = driver
                                    follow_company(modal)
                                    submit_btn, _ = _find_easy_apply_button(("Submit application",), modal)
                                    submitted_ok = False
                                    if submit_btn is not None:
                                        try:
                                            scroll_to_view(driver, submit_btn)
                                            submit_btn.click()
                                        except Exception:
                                            try:
                                                driver.execute_script("arguments[0].click();", submit_btn)
                                            except Exception:
                                                submit_btn = None
                                        if submit_btn is not None:
                                            submitted_ok = True
                                    if not submitted_ok:
                                        submitted_ok = bool(
                                            wait_span_click(driver, "Submit application", 2, scrollTop=True)
                                        )
                                    if submitted_ok:
                                        date_applied = datetime.now()
                                        if not wait_span_click(driver, "Done", 2):
                                            actions.send_keys(Keys.ESCAPE).perform()
                                    elif cur_pause_before_submit and "Yes" in pyautogui.confirm("You submitted the application, didn't you 😒?", "Failed to find Submit Application!", ["Yes", "No"]):
                                        date_applied = datetime.now()
                                        wait_span_click(driver, "Done", 2)
                                    else:
                                        print_lg(
                                            "Submit application still not available after resume "
                                            "Next/Review advance — discarding this application."
                                        )
                                        raise Exception(
                                            "Failed to reach Submit application after resume edit/upload"
                                        )


                        except Exception as e:
                            print_lg("Failed to Easy apply!")
                            # print_lg(e)
                            critical_error_log("Somewhere in Easy Apply process",e)
                            fail_reason = "Help timeout — discarded" if "Help timeout" in str(e) else "Problem in Easy Applying"
                            failed_job(job_id, job_link, resume, date_listed, fail_reason, e, application_link, screenshot_name)
                            failed_count += 1
                            discard_job()
                            continue
                    else:
                        # Case 2: Apply externally
                        skip, application_link, tabs_count = external_apply(pagination_element, job_id, job_link, resume, date_listed, application_link, screenshot_name)
                        if dailyEasyApplyLimitReached:
                            print_lg("\n###############  Daily application limit for Easy Apply is reached!  ###############\n")
                            return
                        if skip: continue

                    submitted_jobs(job_id, title, company, work_location, work_style, description, experience_required, skills, hr_name, hr_link, resume, reposted, date_listed, date_applied, job_link, application_link, questions_list, connect_request)
                    # Keep uploading a fresh PDF every Easy Apply when Resume Engine is enabled.
                    if uploaded and not is_resume_engine_enabled():
                        useNewResume = False

                    print_lg(f'Successfully saved "{title} | {company}" job. Job ID: {job_id} info')
                    current_count += 1
                    if application_link == "Easy Applied": easy_applied_count += 1
                    else:   external_jobs_count += 1
                    applied_jobs.add(job_id)



                if listings_lost:
                    print_lg(f'Skipping remaining pages for "{searchTerm}" after job-list loss.\n')
                    break

                # Switching to next page
                if pagination_element == None:
                    print_lg("Couldn't find pagination element, probably at the end page of results!")
                    break
                try:
                    # Re-locate pagination — prior Easy Apply can stale the old element
                    pagination_element, current_page = get_page_info()
                    if pagination_element is None:
                        print_lg("Couldn't find pagination element after apply; switching to next search.")
                        break
                    pagination_element.find_element(By.XPATH, f"//button[@aria-label='Page {current_page+1}']").click()
                    print_lg(f"\n>-> Now on Page {current_page+1} \n")
                except StaleElementReferenceException:
                    print_lg(
                        f'Pagination went stale for "{searchTerm}"; '
                        f"switching to next search query...\n"
                    )
                    break
                except NoSuchElementException:
                    print_lg(f"\n>-> Didn't find Page {current_page+1}. Probably at the end page of results!\n")
                    break

        except BotStopped:
            raise
        except StaleElementReferenceException as e:
            print_lg(
                f'Job listings/pagination stale for "{searchTerm}"; '
                f"switching to next search query...",
                e,
            )
            continue
        except Exception as e:
            if _is_dead_browser_error(e):
                print_lg("Browser window closed or session is invalid. Ending application process.", e)
                raise
            if _no_matching_jobs_found():
                print_lg(f'No matching jobs found for "{searchTerm}". Switching to next search query...\n')
                continue
            # Do NOT dump page_source (floods logs). Move to next keyword search.
            print_lg(
                f'Failed to find/keep Job listings for "{searchTerm}"; '
                f"switching to next search query...",
                e,
            )
            critical_error_log("In Applier", e)
            continue

        
def run(total_runs: int) -> int:
    global consecutive_dead_cycles, cycle_had_usable_listings, stop_due_to_dead_cycles, dailyEasyApplyLimitReached
    if dailyEasyApplyLimitReached:
        _pause_after_daily_limit()
        dailyEasyApplyLimitReached = False
    print_lg("\n########################################################################################################################\n")
    print_lg(f"Date and Time: {datetime.now()}")
    print_lg(f"Cycle number: {total_runs}")
    print_lg(f"Currently looking for jobs via URL search: f_TPR='{search_time_posted}', sortBy='{search_sort_order}', geoId='{search_geo_id}', f_E='{search_experience_levels}', f_AL='{search_actively_hiring}'")
    cycle_had_usable_listings = False
    apply_to_jobs(search_terms)
    print_lg("########################################################################################################################\n")
    if dailyEasyApplyLimitReached:
        _pause_after_daily_limit()
        dailyEasyApplyLimitReached = False
        consecutive_dead_cycles = 0
        buffer(3)
        return total_runs + 1
    if cycle_had_usable_listings:
        consecutive_dead_cycles = 0
    else:
        consecutive_dead_cycles += 1
        print_lg(
            f"Dead cycle {consecutive_dead_cycles}/{max_dead_cycles or '∞'}: "
            "no usable job listings this cycle (search/filter page failed)."
        )
        if max_dead_cycles > 0 and consecutive_dead_cycles >= max_dead_cycles:
            stop_due_to_dead_cycles = True
            print_lg(
                f"Stopping 10-min cycle loop after {consecutive_dead_cycles} consecutive dead cycles. "
                "Set max_dead_cycles in config/settings.py to change this."
            )
            return total_runs + 1
    if not stop_due_to_dead_cycles:
        print_lg("Sleeping for 10 min...")
        sleep(300)
        print_lg("Few more min... Gonna start with in next 5 min...")
        sleep(300)
    buffer(3)
    return total_runs + 1



chatGPT_tab = False
linkedIn_tab = False

def main() -> None:
    # Sponsor popup disabled so startup is not blocked
    print_lg("Starting Auto Job Applier...")
    if show_stop_button:
        start_stop_controls()
    else:
        print_lg("Stop button disabled (show_stop_button=False). Use Ctrl+C or mouse top-left corner.")
    total_runs = 1
    try:
        global linkedIn_tab, tabs_count, useNewResume, aiClient
        alert_title = "Error Occurred. Closing Browser!"
        validate_config()
        
        if not os.path.exists(default_resume_path):
            print_lg(f'Missing default resume at "{default_resume_path}" — continuing with previous LinkedIn upload.')
            if block_on_missing_resume:
                pyautogui.alert(text='Your default resume "{}" is missing! Please update it\'s folder path "default_resume_path" in config.py\n\nOR\n\nAdd a resume with exact name and path (check for spelling mistakes including cases).\n\n\nFor now the bot will continue using your previous upload from LinkedIn!'.format(default_resume_path), title="Missing Resume", button="OK")
            useNewResume = False
        elif is_resume_engine_enabled():
            engine_root = _resolve_resume_engine_root()
            print_lg(f"Resume Engine enabled via connector. Root: {engine_root}")
            print_lg(
                f"Resume generation timeout: {resume_generation_timeout}s | "
                f"min_jd_chars: {min_jd_chars}"
            )
        if use_resume_score_gate:
            print_lg(
                f"Resume score gate ON (threshold={resume_score_threshold}/100). "
                f"Scoring uses the same AI key/model as config/secrets.py. "
                f"JDs are scored only after existing eligibility rules pass."
            )
            if not use_AI:
                print_lg(
                    "WARNING: use_resume_score_gate is True but use_AI is False — "
                    "eligible JDs will be skipped because scoring cannot run."
                )
        else:
            print_lg("Resume score gate OFF — applying without JD vs resume scoring.")
        if use_jd_email_outreach:
            print_lg(
                f"JD email outreach ON. After resume PDF resolve, if the JD has an email, "
                f"send_outreach fires in the background (root={ai_outreach_root})."
            )
        else:
            print_lg("JD email outreach OFF.")
        
        # Login to LinkedIn
        tabs_count = len(driver.window_handles)
        open_url_with_retries(driver, "https://www.linkedin.com/login", attempts=4, wait_secs=3.0)
        print_lg("LinkedIn opened. Waiting 5 seconds...")
        sleep(5)
        if not is_logged_in_LN(): login_LN()
        
        linkedIn_tab = driver.current_window_handle

        # # Login to ChatGPT in a new tab for resume customization
        # if use_resume_generator:
        #     try:
        #         driver.switch_to.new_window('tab')
        #         driver.get("https://chat.openai.com/")
        #         if not is_logged_in_GPT(): login_GPT()
        #         open_resume_chat()
        #         global chatGPT_tab
        #         chatGPT_tab = driver.current_window_handle
        #     except Exception as e:
        #         print_lg("Opening OpenAI chatGPT tab failed!")
        if is_ai_enabled():
            if ai_provider == "openai":
                aiClient = ai_create_openai_client()
            ##> ------ Yang Li : MARKYangL - Feature ------
            # Create DeepSeek client
            elif ai_provider == "deepseek":
                aiClient = deepseek_create_client()
            elif ai_provider == "gemini":
                aiClient = gemini_create_client()
            ##<

            try:
                about_company_for_ai = " ".join([word for word in (first_name+" "+last_name).split() if len(word) > 3])
                print_lg(f"Extracted about company info for AI: '{about_company_for_ai}'")
            except Exception as e:
                print_lg("Failed to extract about company info!", e)
        
        # Start applying to jobs
        driver.switch_to.window(linkedIn_tab)
        total_runs = run(total_runs)
        while(run_non_stop):
            if stop_due_to_dead_cycles:
                print_lg("Exiting run_non_stop loop (max_dead_cycles reached).")
                break
            if cycle_date_posted:
                date_options = ["Any time", "Past month", "Past week", "Past 24 hours"]
                global date_posted
                date_posted = date_options[date_options.index(date_posted)+1 if date_options.index(date_posted)+1 > len(date_options) else -1] if stop_date_cycle_at_24hr else date_options[0 if date_options.index(date_posted)+1 >= len(date_options) else date_options.index(date_posted)+1]
            if alternate_sortby:
                global sort_by
                sort_by = "Most recent" if sort_by == "Most relevant" else "Most relevant"
                total_runs = run(total_runs)
                if stop_due_to_dead_cycles:
                    break
                sort_by = "Most recent" if sort_by == "Most relevant" else "Most relevant"
            total_runs = run(total_runs)
            if stop_due_to_dead_cycles:
                break
        

    except BotStopped as e:
        print_lg(f"Bot stopped by user: {e}")
    except FailSafeException:
        print_lg("PyAutoGUI failsafe: mouse moved to top-left corner. Stopping bot.")
    except Exception as e:
        if _is_dead_browser_error(e):
            print_lg("Browser window closed or session is invalid. Exiting.", e)
        else:
            critical_error_log("In Applier Main", e)
            try:
                if block_on_critical_error:
                    pyautogui.alert(e, alert_title)
                else:
                    print_lg(f"Critical error (non-blocking): {e}")
            except Exception:
                print_lg("Could not show error alert:", e)
    finally:
        summary = "Total runs: {}\nJobs Easy Applied: {}\nExternal job links collected: {}\nTotal applied or collected: {}\nFailed jobs: {}\nIrrelevant jobs skipped: {}\n".format(total_runs,easy_applied_count,external_jobs_count,easy_applied_count + external_jobs_count,failed_count,skip_count)
        print_lg(summary)
        print_lg("\n\nTotal runs:                     {}".format(total_runs))
        print_lg("Jobs Easy Applied:              {}".format(easy_applied_count))
        print_lg("External job links collected:   {}".format(external_jobs_count))
        print_lg("                              ----------")
        print_lg("Total applied or collected:     {}".format(easy_applied_count + external_jobs_count))
        print_lg("\nFailed jobs:                    {}".format(failed_count))
        print_lg("Irrelevant jobs skipped:        {}\n".format(skip_count))
        if randomly_answered_questions: print_lg("\n\nQuestions randomly answered:\n  {}  \n\n".format(";\n".join(str(question) for question in randomly_answered_questions)))
        quotes = choice([
            "Never quit. You're one step closer than before. - Sai Vignesh Golla", 
            "All the best with your future interviews, you've got this. - Sai Vignesh Golla", 
            "Keep up with the progress. You got this. - Sai Vignesh Golla", 
            "If you're tired, learn to take rest but never give up. - Sai Vignesh Golla",
            "Success is not final, failure is not fatal, It is the courage to continue that counts. - Winston Churchill (Not a sponsor)",
            "Believe in yourself and all that you are. Know that there is something inside you that is greater than any obstacle. - Christian D. Larson (Not a sponsor)",
            "Every job is a self-portrait of the person who does it. Autograph your work with excellence. - Jessica Guidobono (Not a sponsor)",
            "The only way to do great work is to love what you do. If you haven't found it yet, keep looking. Don't settle. - Steve Jobs (Not a sponsor)",
            "Opportunities don't happen, you create them. - Chris Grosser (Not a sponsor)",
            "The road to success and the road to failure are almost exactly the same. The difference is perseverance. - Colin R. Davis (Not a sponsor)",
            "Obstacles are those frightful things you see when you take your eyes off your goal. - Henry Ford (Not a sponsor)",
            "The only limit to our realization of tomorrow will be our doubts of today. - Franklin D. Roosevelt (Not a sponsor)",
            ])
        sponsors = "Be the first to have your name here!"
        timeSaved = (easy_applied_count * 80) + (external_jobs_count * 20) + (skip_count * 10)
        timeSavedMsg = ""
        if timeSaved > 0:
            timeSaved += 60
            timeSavedMsg = f"In this run, you saved approx {round(timeSaved/60)} mins ({timeSaved} secs), please consider supporting the project."
        msg = f"{quotes}\n\n\n{timeSavedMsg}\nYou can also get your quote and name shown here, or prioritize your bug reports by supporting the project at:\n\nhttps://github.com/sponsors/GodsScion\n\n\nSummary:\n{summary}\n\n\nBest regards,\nSai Vignesh Golla\nhttps://www.linkedin.com/in/saivigneshgolla/\n\nTop Sponsors:\n{sponsors}"
        if block_on_exit_summary:
            pyautogui.alert(msg, "Exiting..")
        print_lg(msg,"Closing the browser...")
        if tabs_count >= 10:
            msg = "NOTE: IF YOU HAVE MORE THAN 10 TABS OPENED, PLEASE CLOSE OR BOOKMARK THEM!\n\nOr it's highly likely that application will just open browser and not do anything next time!" 
            if block_on_exit_summary:
                pyautogui.alert(msg,"Info")
            print_lg("\n"+msg)
        ##> ------ Yang Li : MARKYangL - Feature ------
        if use_AI and aiClient:
            try:
                if ai_provider.lower() == "openai":
                    ai_close_openai_client(aiClient)
                elif ai_provider.lower() == "deepseek":
                    ai_close_openai_client(aiClient)
                elif ai_provider.lower() == "gemini":
                    pass # Gemini client does not need to be closed
                print_lg(f"Closed {ai_provider} AI client.")
            except Exception as e:
                print_lg("Failed to close AI client:", e)
        ##<
        try:
            if driver:
                driver.quit()
        except (WebDriverException, ConnectionResetError, OSError) as e:
            print_lg("Browser already closed or connection reset during quit.", e)
        except Exception as e: 
            print_lg("When quitting browser (non-fatal):", e)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_lg("Interrupted by user. Exiting cleanly.")
    except (ConnectionResetError, OSError) as e:
        print_lg("Connection closed during shutdown (non-fatal).", e)
