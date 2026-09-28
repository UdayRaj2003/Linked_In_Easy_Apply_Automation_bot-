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

import os
import shutil
import time
from pathlib import Path

from modules.helpers import get_default_temp_profile, make_directories
from config.settings import (
    run_in_background,
    stealth_mode,
    disable_extensions,
    safe_mode,
    file_name,
    failed_file_name,
    logs_folder_path,
    generated_resume_path,
    block_on_chrome_open_error,
)
from config.questions import default_resume_path
if stealth_mode:
    import undetected_chromedriver as uc
else:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from modules.helpers import find_default_profile_directory, critical_error_log, print_lg
from selenium.common.exceptions import SessionNotCreatedException, WebDriverException


def _guest_profile_path(*, fresh: bool = False) -> str:
    '''
    Guest profile under C:\\temp (or platform equivalent).
    Uses a unique subfolder on retry/fresh to avoid DevToolsActivePort lock crashes.
    '''
    base = Path(get_default_temp_profile())
    if fresh:
        profile = base.parent / f"{base.name}-{os.getpid()}-{int(time.time())}"
    else:
        profile = base
    if fresh and profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
    elif fresh is False and (profile / "DevToolsActivePort").exists():
        # Stale lock from a previous crashed Chrome — clear profile
        print_lg(f"Removing stale Chrome guest profile lock under {profile}")
        shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    return str(profile)


def _apply_stable_chrome_options(options) -> None:
    '''Flags that reduce DNS / session flakiness on Windows Wi‑Fi.'''
    options.add_argument("--disable-features=AsyncDns,DnsOverHttps,OptimizationHints")
    options.add_argument("--dns-over-https-mode=off")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-client-side-phishing-detection")
    options.add_argument("--disable-default-apps")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-allow-origins=*")
    options.page_load_strategy = "normal"


def createChromeSession(isRetry: bool = False):
    make_directories([
        file_name,
        failed_file_name,
        logs_folder_path+"/screenshots",
        default_resume_path,
        generated_resume_path+"/temp",
        generated_resume_path+"/generated",
    ])
    options = uc.ChromeOptions() if stealth_mode else Options()
    if run_in_background:
        options.add_argument("--headless=new")
    if disable_extensions:
        options.add_argument("--disable-extensions")

    _apply_stable_chrome_options(options)

    print_lg("IF YOU HAVE MORE THAN 10 TABS OPENED, PLEASE CLOSE OR BOOKMARK THEM! Or it's highly likely that application will just open browser and not do anything!")
    profile_dir = find_default_profile_directory()
    if isRetry or safe_mode or not profile_dir:
        print_lg("Logging in with a guest profile, Web history will not be saved!")
        guest = _guest_profile_path(fresh=isRetry)
        options.add_argument(f"--user-data-dir={guest}")
        options.add_argument("--remote-debugging-port=0")
    else:
        options.add_argument(f"--user-data-dir={profile_dir}")
        options.add_argument("--remote-debugging-port=0")

    if stealth_mode:
        print_lg("Downloading Chrome Driver... This may take some time. Undetected mode requires download every run!")
        driver = uc.Chrome(options=options)
    else:
        # Let Selenium Manager pick a ChromeDriver matching the installed Chrome.
        driver = webdriver.Chrome(options=options)

    try:
        driver.set_page_load_timeout(60)
        driver.set_script_timeout(30)
    except Exception:
        pass
    try:
        driver.maximize_window()
    except Exception:
        pass
    wait = WebDriverWait(driver, 5)
    actions = ActionChains(driver)
    return options, driver, actions, wait


def open_url_with_retries(driver, url: str, attempts: int = 4, wait_secs: float = 3.0) -> bool:
    '''
    Navigate to url with retries for transient DNS / network errors
    (e.g. net::ERR_NAME_NOT_RESOLVED).
    '''
    last_err = None
    for i in range(1, attempts + 1):
        try:
            print_lg(f"Opening {url} (attempt {i}/{attempts})...")
            driver.get(url)
            current = (driver.current_url or "").lower()
            if "chrome-error://" in current or current.startswith("data:"):
                raise WebDriverException(f"Chrome error page after navigation: {current}")
            return True
        except Exception as e:
            last_err = e
            msg = str(e)
            print_lg(f"Navigation failed (attempt {i}/{attempts}): {msg[:200]}")
            if i < attempts:
                time.sleep(wait_secs * i)
    if last_err is not None:
        raise last_err
    return False


try:
    options, driver, actions, wait = None, None, None, None
    options, driver, actions, wait = createChromeSession()
except SessionNotCreatedException as e:
    critical_error_log("Failed to create Chrome Session, retrying with guest profile", e)
    time.sleep(2)
    options, driver, actions, wait = createChromeSession(True)
except Exception as e:
    msg = 'Seems like Google Chrome is out dated. Update browser and try again! \n\n\nIf issue persists, try Safe Mode. Set, safe_mode = True in config.py \n\nPlease check GitHub discussions/support for solutions https://github.com/GodsScion/Auto_job_applier_linkedIn \n                                   OR \nReach out in discord ( https://discord.gg/fFp7uUzWCY )'
    if isinstance(e, TimeoutError):
        msg = "Couldn't download Chrome-driver. Set stealth_mode = False in config!"
    print_lg(msg)
    critical_error_log("In Opening Chrome", e)
    if block_on_chrome_open_error:
        from pyautogui import alert
        alert(msg, "Error in opening chrome")
    try:
        driver.quit()
    except NameError:
        exit()
