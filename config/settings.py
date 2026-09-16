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


###################################################### CONFIGURE YOUR BOT HERE ######################################################

# >>>>>>>>>>> LinkedIn Settings <<<<<<<<<<<

# Keep the External Application tabs open?
close_tabs = True                  # True or False, Note: True or False are case-sensitive
'''
Note: RECOMMENDED TO LEAVE IT AS `True`, if you set it `False`, be sure to CLOSE ALL TABS BEFORE CLOSING THE BROWSER!!!
'''

# Follow easy applied companies
follow_companies = True            # True or False, Note: True or False are case-sensitive

## Upcoming features (In Development)
# # Send connection requests to HR's 
# connect_hr = True                  # True or False, Note: True or False are case-sensitive

# # What message do you want to send during connection request? (Max. 200 Characters)
# connect_request_message = ""       # Leave Empty to send connection request without personalized invitation (recommended to leave it empty, since you only get 10 per month without LinkedIn Premium*)

# Do you want the program to run continuously until you stop it? (Beta)
run_non_stop = True                # True or False, Note: True or False are case-sensitive
'''
Note: Will be treated as False if `run_in_background = True`
'''
alternate_sortby = False             # True or False, Note: True or False are case-sensitive
cycle_date_posted = False        # True or False, Note: True or False are case-sensitive
stop_date_cycle_at_24hr = True      # True or False, Note: True or False are case-sensitive

# Stop the 10-min run_non_stop loop after this many consecutive "dead" cycles
# (a cycle with no usable job listings — search/filter page failed).
# 0 = never stop on dead cycles.
max_dead_cycles = 3                # Non-negative Integer

# Recent-job gate: when ON, only apply if job_age_minutes <= recent_job_max_age_minutes
recent_job_feature_enabled = True       # True or False, Note: True or False are case-sensitive
recent_job_max_age_minutes = 30          # Non-negative Integer (e.g. 30 = last half hour)
# Used when LinkedIn posted-time text cannot be parsed (still runs the gate when feature is ON)
recent_job_default_age_minutes = 0       # Non-negative Integer

# When LinkedIn shows "We limit daily submissions..." / Easy Apply is disabled,
# pause applying for this many hours (then resume if run_non_stop is True).
# STOP BOT / Ctrl+Shift+Q still aborts the wait.
daily_limit_pause_hours = 10             # Positive Integer (e.g. 24 = wait one day)





# >>>>>>>>>>> RESUME GENERATOR (Experimental & In Development) <<<<<<<<<<<

# Give the path to the folder where all the generated resumes are to be stored
generated_resume_path = "all resumes/" # (In Development)

# Use the shared Resume Engine (RenderCv) via connectors/resume_engine_client.py
use_resume_engine = True               # True or False, Note: True or False are case-sensitive
# Absolute or relative path to the RenderCv project root (must contain resume_engine/)
resume_engine_root = "../RenderCv"
# Max seconds to wait for resume generation before uploading default_resume_path
resume_generation_timeout = 900        # Non-negative Integer (default: 10 minutes)
# Minimum stripped job-description length required before calling the Resume Engine
min_jd_chars = 80                      # Non-negative Integer


# >>>>>>>>>>> JD vs Resume Score Gate <<<<<<<<<<<
# After existing eligibility/experience rules pass, optionally score the JD
# against the resume (same AI key/model as config/secrets.py) before applying.
use_resume_score_gate = True           # True or False, Note: True or False are case-sensitive
# Minimum score (0-100) required to generate a tailored resume and apply.
# Example: RESUME_SCORE_THRESHOLD=70
resume_score_threshold = 70            # Integer 0-100


# >>>>>>>>>>> JD Email Outreach (AI_Outreach, local import) <<<<<<<<<<<
# After eligibility + resume score + resume PDF resolve, if the JD contains an email,
# fire-and-forget send_outreach(jd, resume_path). Never blocks Easy Apply.
use_jd_email_outreach = True           # True or False, Note: True or False are case-sensitive
ai_outreach_root = r"D:\Test_all_job_bot\Python_Scrapper_Telegram\AI_Outreach"





# >>>>>>>>>>> Global Settings <<<<<<<<<<<

# Directory and name of the files where history of applied jobs is saved (Sentence after the last "/" will be considered as the file name).
file_name = "all excels/all_applied_applications_history.csv"
failed_file_name = "all excels/all_failed_applications_history.csv"
logs_folder_path = "logs/"

# Set the maximum amount of time allowed to wait between each click in secs
click_gap = 2                    # Enter max allowed secs to wait approximately. (Only Non Negative Integers Eg: 0,1,2,3,....)

# If you want to see Chrome running then set run_in_background as False (May reduce performance). 
run_in_background = False           # True or False, Note: True or False are case-sensitive ,   If True, this will make pause_at_failed_question, pause_before_submit and run_in_background as False

# If you want to disable extensions then set disable_extensions as True (Better for performance)
disable_extensions = False          # True or False, Note: True or False are case-sensitive

# Run in safe mode. Set this true if chrome is taking too long to open or if you have multiple profiles in browser. This will open chrome in guest profile!
safe_mode = True                    # True or False, Note: True or False are case-sensitive

# Do you want scrolling to be smooth or instantaneous? (Can reduce performance if True)
smooth_scroll = True               # True or False, Note: True or False are case-sensitive

# If enabled (True), the program would keep your screen active and prevent PC from sleeping. Instead you could disable this feature (set it to false) and adjust your PC sleep settings to Never Sleep or a preferred time. 
keep_screen_awake = True            # True or False, Note: True or False are case-sensitive (Note: Will temporarily deactivate when any application dialog boxes are present (Eg: Pause before submit, Help needed for a question..))

# Run in undetected mode to bypass anti-bot protections (Preview Feature, UNSTABLE. Recommended to leave it as False)
stealth_mode = False                # True or False, Note: True or False are case-sensitive

# Always-on-top STOP BOT window + Ctrl+Shift+Q while the bot runs
# (also: move mouse to the top-left corner — PyAutoGUI failsafe)
show_stop_button = True             # True or False, Note: True or False are case-sensitive


# >>>>>>>>>>> RUN BLOCKERS (dialogs that wait for a click) <<<<<<<<<<<
# False (default) = log and continue — never stall the run waiting for you.
# True = show a popup and wait until you click.
# Related pauses also live in config/questions.py and config/search.py:
#   pause_at_failed_question, pause_before_submit, pause_after_filters

block_on_filter_error = False       # "Filter setup failed" after preferences/Show results error
block_on_ai_errors = False          # AI connection / answer error confirms
block_on_failed_logging = False     # CSV / log.txt write failure alerts
block_on_missing_resume = False     # Missing default_resume_path at startup
block_on_login_prompts = False      # Manual login / "Login Required" alerts
block_on_critical_error = False     # Fatal exception alert before browser close
block_on_exit_summary = False       # Exiting summary / too-many-tabs alerts
block_on_chrome_open_error = False  # Chrome failed to start alert

# Backward-compatible alias used by AI modules
showAiErrorAlerts = block_on_ai_errors

# Use ChatGPT for resume building (Experimental Feature can break the application. Recommended to leave it as False) 
# use_resume_generator = False       # True or False, Note: True or False are case-sensitive ,   This feature may only work with 'stealth_mode = True'. As ChatGPT website is hosted by CloudFlare which is protected by Anti-bot protections!











############################################################################################################
'''
THANK YOU for using my tool 😊! Wishing you the best in your job hunt 🙌🏻!

Sharing is caring! If you found this tool helpful, please share it with your peers 🥺. Your support keeps this project alive.

Support my work on <PATREON_LINK>. Together, we can help more job seekers.

As an independent developer, I pour my heart and soul into creating tools like this, driven by the genuine desire to make a positive impact.

Your support, whether through donations big or small or simply spreading the word, means the world to me and helps keep this project alive and thriving.

Gratefully yours 🙏🏻,
Sai Vignesh Golla
'''
############################################################################################################