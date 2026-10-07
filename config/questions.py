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


###################################################### APPLICATION INPUTS ######################################################


# >>>>>>>>>>> Easy Apply Questions & Inputs <<<<<<<<<<<

# Give an relative path of your default resume to be uploaded. If file in not found, will continue using your previously uploaded resume in LinkedIn.
default_resume_path = "D:/Uday_Resume.pdf"

# What do you want to answer for questions that ask about years of experience you have, this is different from current_experience?
years_of_experience = "1"

# Do you need visa sponsorship now or in future?
require_visa = "No"

# What is the link to your portfolio website, leave it empty as "", if you want to leave this question unanswered
website = "https://github.com/UdayRaj2003"

# Please provide the link to your LinkedIn profile.
linkedIn = "https://www.linkedin.com/in/uday-raj-gupta-b7a493262/"

# What is the status of your citizenship?
# Valid options are:
# "U.S. Citizen/Permanent Resident"
# "Non-citizen allowed to work for any employer"
# "Non-citizen allowed to work for current employer"
# "Non-citizen seeking work authorization"
# "Canadian Citizen/Permanent Resident"
# "Other"
us_citizenship = "Non-citizen seeking work authorization"



## SOME ANNOYING QUESTIONS BY COMPANIES 🫠 ##

# Expected CTC (annual)
desired_salary = 600000

'''
Note: If question has the word "lakhs" in it (Example: What is your expected CTC in lakhs),
then it will add '.' before last 5 digits and answer.
'''

# Current CTC
current_ctc = 450000

'''
Note:
If asked in lakhs/months, tool automatically converts.
'''

# Notice period in days
notice_period = 0

'''
Note:
If asked in months/weeks, tool automatically converts.
'''

# Your LinkedIn headline
linkedin_headline = "SDET | Backend Developer ( SQL | Node.js | MongoDB | System Design) | Test Automation ( Python | Pytest | REST API | Playwright ) | SGSITS 2026"

# Your LinkedIn summary
linkedin_summary = """
I'm Uday Raj Gupta, a Full Stack Developer and QA Engineer with experience in building scalable web applications using the MERN stack and testing SaaS products.

• B.Tech in Electronics & Telecommunication Engineering (2026)
• Former QA Analyst at Dice
• Former SDE Intern at Sherwa.Tech
• Strong in C++, Data Structures & Algorithms, React.js, Node.js, Express.js, MongoDB, SQL and REST APIs
• Solved 250+ DSA problems on LeetCode and GeeksforGeeks
• Passionate about Software Engineering, Backend Development, AI-assisted development and Problem Solving.

Currently looking for Software Engineer and Full Stack Developer opportunities.
"""

# Cover Letter
cover_letter = """
Dear Hiring Manager,

I am Uday Raj Gupta, a Full Stack Developer and QA Analyst with experience in MERN Stack development, REST APIs, React.js, Node.js, MongoDB, SQL, API Testing, Pytest and Data Structures & Algorithms.

I have worked on real-world products during my internship at Sherwa.Tech and as a QA Analyst at Dice, where I gained experience in software development, testing, debugging, and cross-functional collaboration.

I am excited about the opportunity to contribute to your engineering team and continuously learn while building high-quality software.

Thank you for your time and consideration. I look forward to hearing from you.

Regards,
Uday Raj Gupta
"""

## ------ AI Context ------

user_information_all = """
Name: Uday Raj Gupta

Contact Information:
• Email: udayrajgupta2003@gmail.com
• Phone: +91 7470810014
• Location: Indore, India

Professional Summary:
Full Stack Developer and QA Analyst with experience in MERN stack development, REST APIs, API integration, software testing, automation testing, and scalable web application development. Strong foundation in Data Structures & Algorithms, Object-Oriented Programming, System Design, SDLC, Agile Scrum, and modern web technologies. Experienced in both software development and quality assurance across SaaS finance platforms.

Education:
Bachelor of Technology (B.Tech) in Electronics & Telecommunication Engineering
Shri G.S. Institute of Technology & Science (SGSITS), Indore
RGPV University
CGPA: 7.8
Graduated: 2026

Professional Experience:

QA Analyst | Dice Enterprises | Pune
December 2025 – March 2026

Responsibilities:
• Executed Functional, Regression, Integration, End-to-End, UAT, and API Testing.
• Validated finance modules including Expenses, Travel, Cost Allocation, Taxation, Budgeting, Approval Workflows, and Business Rules.
• Managed 158+ defects, 110+ enhancements, and 38+ feature improvements.
• Performed REST API validation using Postman and cURL.
• Worked with Jira for defect lifecycle management.
• Collaborated with developers and product managers during debugging and release cycles.
• Created and maintained test cases, execution reports, and QA documentation.
• Worked with Selenium and Python (pytest) for automation testing concepts.

Software Developer Intern | Sherwa.Tech
May 2024 – July 2024

Responsibilities:
• Built scalable React applications using Redux Toolkit.
• Developed REST APIs using Node.js, Express.js, and MongoDB.
• Designed CRUD operations and authentication workflows.
• Improved application quality through testing and documentation.
• Worked in a 7-member Agile Scrum team using Git and GitHub.

Projects:

Mini Tool App
• Modular JavaScript utility platform.
• MVC architecture.
• Progressive Web App (PWA).
• Chrome Extension support.
• API integration.
• Performance optimization.
• Dynamic routing and modular architecture.

StudyNotion
• MERN Stack EdTech platform.
• React.js frontend.
• Node.js & Express backend.
• MongoDB database.
• JWT Authentication.
• OTP Login.
• Cloudinary Integration.
• REST API architecture.
• Course management system.

Technical Skills:

Programming:
• C
• C++
• Java
• Python
• JavaScript
• SQL

Frontend:
• HTML
• CSS
• React.js
• Redux Toolkit
• Responsive Design
• Tailwind CSS
• Figma
• Flutter


Backend:
• Node.js
• Express.js
• REST APIs
• .NET Core
• Authentication
• CRUD Operations
• API Integration
• Request/Response Handling


Databases:
• MongoDB
• MySQL

Testing:
• Functional Testing
• Regression Testing
• Integration Testing
• End-to-End Testing
• UAT
• API Testing
• Selenium
• Postman
• pytest
• Test Case Design
• Test Execution
• Defect Lifecycle Management

Tools:
• Git
• GitHub
• Linux
• Jira
• Cloudinary

Computer Science Fundamentals:
• Data Structures & Algorithms
• Object-Oriented Programming
• Operating Systems
• Computer Networks
• DBMS
• SDLC
• Agile Scrum
• System Design
• Performance Optimization
• Scalability

Achievements:
• Solved 255+ Data Structures & Algorithms problems on LeetCode and GeeksforGeeks.
• Google Developers Student Club (GDSC) member.
• HackerRank Problem Solving Certified.
• HackerRank SQL Certified.
• NPTEL Machine Learning & Deep Learning Certified.
• JEE Main AIR under 59,000.

Portfolio:
GitHub: https://github.com/UdayRaj2003
LinkedIn: https://www.linkedin.com/in/uday-raj-gupta-b7a493262/

Preferred Roles:
• Software Engineer
• Software Developer
• Full Stack Developer
• Backend Developer
• Frontend Developer
• MERN Stack Developer
• QA Automation Engineer
• Software Development Engineer in Test (SDET)
• AI Engineer

Work Preferences:
• Immediate Joiner
• Open to Remote, Hybrid, and On-site roles.
• Comfortable relocating anywhere in India.
• Comfortable working in Agile Scrum teams.
• Comfortable learning new technologies quickly.

Instructions for AI:
Use only truthful information from this profile when answering application questions. Highlight relevant experience, transferable skills, projects, internships, certifications, and coursework where applicable. Do not invent experience, technologies, or certifications that are not listed above.
"""

# Name of your most recent employer
recent_employer = "Dice Enterprises"

# Confidence level (1-10)
confidence_level = "10"



# >>>>>>>>>>> RELATED SETTINGS <<<<<<<<<<<

## Allow Manual Inputs

# Pause before final submit (True = blocks run until you click)
pause_before_submit = False

# Pause if AI cannot answer (True = Help Needed dialog; False = discard/skip without waiting)
pause_at_failed_question = False

# Minutes to wait for you on "Help Needed" before discarding and moving to the next job
failed_question_timeout_minutes = 2

# Overwrite previous answers?
overwrite_previous_answers = False

# Save answers you fill/correct during pauses, and reuse them on future applications
save_and_reuse_answers = True       # True or False, Note: True or False are case-sensitive
saved_answers_path = "config/saved_answers.json"  # Local JSON store for remembered Q&A




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