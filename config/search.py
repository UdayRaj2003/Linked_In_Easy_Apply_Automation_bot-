# These Sentences are Searched in LinkedIn
# Enter your search terms inside '[ ]' with quotes ' "searching title" ' for each search followed by comma ', '
# Eg: ["Software Engineer", "Software Developer", "Selenium Developer"]
search_terms = [      
    "Node.js Developer",
    "Software Fresher Job",
    # "QA Fresher Job",
    "C++ Developer",
    "Python Developer",
    "QA Automation Engineer", 
    "SDET",
    "Associate Software Engineer",
    "Graduate Software Engineer",
    "Entry Level Software Engineer"
]

# Search location, this will be filled in "City, state, or zip code" search box.
# If left empty as "", tool will not fill it.
search_location = "India"

# After how many number of applications in current search should the bot switch to next search?
switch_number = 50

# Do you want to randomize the search order for search_terms?
randomize_search_order = True


# >>>>>>>>>>> LinkedIn URL Search (replaces UI filter setup) <<<<<<<<<<<
'''
The bot navigates directly to a parameterized jobs search URL.
JOB_TITLE / keywords come from search_terms above.

LinkedIn query flags:
* f_AL  — Easy Apply / actively hiring flag (typically "true")
* f_E   — experience levels: 1=Internship, 2=Entry level, 3=Associate,
          4=Mid-Senior, 5=Director, 6=Executive (comma-separated)
* f_TPR — time posted, e.g. r864 or r86400 (past 24h), r604800 (week), r2592000 (month)
* geoId — location geo id (102713980 = India)
* sortBy — DD = Most recent, R = Most relevant
* origin — keep JOB_SEARCH_PAGE_JOB_FILTER

Leave a value as "" to omit that query parameter (except keywords/origin/sortBy/geoId which should stay set).
'''
search_actively_hiring = "true"                    # f_AL: Easy Apply : "true", "false", or "" to omit
search_experience_levels = "2,3"                 # f_E: comma-separated experience codes
search_time_posted = "r1800"                        # f_TPR: LinkedIn often uses r86400 for past 24 hours
search_geo_id = "102713980"                        # geoId (India)
search_sort_order = "DD"                           # sortBy: "DD" (Most recent) or "R" (Most relevant)
search_origin = "JOB_SEARCH_PAGE_JOB_FILTER"       # origin


# >>>>>>>>>>> Job Search Filters <<<<<<<<<<<
'''
You could set your preferences or leave them as empty to not select options except for 'True or False' options. Below are some valid examples for leaving them empty:

This is below format:
QUESTION = VALID_ANSWER

## Examples of how to leave them empty. Note that True or False options cannot be left empty!
* question_1 = ""                    # answer1, answer2, answer3, etc.
* question_2 = []                    # (multiple select)
* question_3 = []                    # (dynamic multiple select)

## Some valid examples of how to answer questions:
* question_1 = "answer1"                  # "answer1", "answer2", "answer3" or ("" to not select). Answers are case sensitive.
* question_2 = ["answer1", "answer2"]     # (multiple select)
* question_3 = ["answer1", "Random AnswER"]     # (dynamic multiple select)
'''

sort_by = "Most recent"              # "Most recent", "Most relevant" or ("" to not select)
date_posted = "Past 24 hours"        # "Any time", "Past month", "Past week", "Past 24 hours" or ("" to not select)
salary = ""                          # "$40,000+", "$60,000+", "$80,000+", "$100,000+", "$120,000+", "$140,000+", "$160,000+", "$180,000+", "$200,000+"

easy_apply_only = True               # True or False, Note: True or False are case-sensitive

experience_level = [                 # (multiple select) "Internship", "Entry level", "Associate", "Mid-Senior level", "Director", "Executive"
    # "Internship",
    "Entry level",
    # "Associate"
]

job_type = [                         # (multiple select) "Full-time", "Part-time", "Contract", "Temporary", "Volunteer", "Internship", "Other"
    # "Full-time","Internship" 
]

on_site = [                          # (multiple select) "On-site", "Remote", "Hybrid"
    # "Remote",
    # "Hybrid",
    # "On-site"
]

companies = []                       # (dynamic multiple select)
location = [                         # (dynamic multiple select)
    # "Pune",
    # "Bengaluru",
    # "Hyderabad",
    # "Chennai",
    # "Noida",
    # "Gurugram",
    # "Delhi",
    # "Mumbai",
    # "Indore"
]

industry = []                        # (dynamic multiple select)
job_function = []                    # (dynamic multiple select)
job_titles = []                      # (dynamic multiple select)
benefits = []                        # (dynamic multiple select)
commitments = []                     # (dynamic multiple select)

under_10_applicants = False          # True or False, Note: True or False are case-sensitive
in_your_network = False              # True or False, Note: True or False are case-sensitive
fair_chance_employer = False         # True or False, Note: True or False are case-sensitive


## >>>>>>>>>>> RELATED SETTING <<<<<<<<<<<

# Pause after applying filters to let you modify the search results and filters?
# True = blocks until you click; False (default) = continue immediately
pause_after_filters = False           # True or False, Note: True or False are case-sensitive


## >>>>>>>>>>> SKIP IRRELEVANT JOBS <<<<<<<<<<<

# Avoid applying to these companies, and companies with these bad words in their 'About Company' section...
about_company_bad_words = [
    "Crossover",
    "Scoutit",
    "Mindrift"
]

# Skip checking for `about_company_bad_words` for these companies if they have these good words in their 'About Company' section...
about_company_good_words = [
     
    "Google",
    "Microsoft",
    "Amazon",
    "Adobe"
]

# Avoid applying to these companies if they have these bad words in their 'Job Description' section...
bad_words = [
    "unpaid",
    "intern",
    "US Citizen",
    "USA Citizen",
    "Security Clearance",
    "Active Clearance",
    "Secret Clearance",
    "Top Secret",
    "No C2C",
    "No Corp2Corp",
    "Senior Architect",
    "15+ years",
    ".NET",
    "PHP",
    "Ruby",
    "CNC",  
]

# Do you have an active Security Clearance? (True for Yes and False for No)
security_clearance = False

# Do you have a Masters degree? (True for Yes and False for No)
did_masters = False

# Avoid applying to jobs if their required experience is above your current_experience.
# Set value as -1 if you want to apply to all jobs regardless of experience requirement.
current_experience = 1