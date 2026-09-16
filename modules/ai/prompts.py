"""
Author:     Sai Vignesh Golla
LinkedIn:   https://www.linkedin.com/in/saivigneshgolla/

Copyright (C) 2024 Sai Vignesh Golla

License:    GNU Affero General Public License
            https://www.gnu.org/licenses/agpl-3.0.en.html
            
GitHub:     https://github.com/GodsScion/Auto_job_applier_linkedIn

Support me: https://github.com/sponsors/GodsScion

version:    26.01.20.5.08
"""


##> Common Response Formats
array_of_strings = {"type": "array", "items": {"type": "string"}}
"""
Response schema to represent array of strings `["string1", "string2"]`
"""
#<


##> Extract Skills

# Structure of messages = `[{"role": "user", "content": extract_skills_prompt}]`

extract_skills_prompt = """
You are a job requirements extractor and classifier. Your task is to extract all skills mentioned in a job description and classify them into five categories:
1. "tech_stack": Identify all skills related to programming languages, frameworks, libraries, databases, and other technologies used in software development. Examples include Python, React.js, Node.js, Elasticsearch, Algolia, MongoDB, Spring Boot, .NET, etc.
2. "technical_skills": Capture skills related to technical expertise beyond specific tools, such as architectural design or specialized fields within engineering. Examples include System Architecture, Data Engineering, System Design, Microservices, Distributed Systems, etc.
3. "other_skills": Include non-technical skills like interpersonal, leadership, and teamwork abilities. Examples include Communication skills, Managerial roles, Cross-team collaboration, etc.
4. "required_skills": All skills specifically listed as required or expected from an ideal candidate. Include both technical and non-technical skills.
5. "nice_to_have": Any skills or qualifications listed as preferred or beneficial for the role but not mandatory.
Return the output in the following JSON format with no additional commentary:
{{
    "tech_stack": [],
    "technical_skills": [],
    "other_skills": [],
    "required_skills": [],
    "nice_to_have": []
}}

JOB DESCRIPTION:
{}
"""
"""
Use `extract_skills_prompt.format(job_description)` to insert `job_description`.
"""

# DeepSeek-specific optimized prompt, emphasis on returning only JSON without using json_schema
deepseek_extract_skills_prompt = """
You are a job requirements extractor and classifier. Your task is to extract all skills mentioned in a job description and classify them into five categories:
1. "tech_stack": Identify all skills related to programming languages, frameworks, libraries, databases, and other technologies used in software development. Examples include Python, React.js, Node.js, Elasticsearch, Algolia, MongoDB, Spring Boot, .NET, etc.
2. "technical_skills": Capture skills related to technical expertise beyond specific tools, such as architectural design or specialized fields within engineering. Examples include System Architecture, Data Engineering, System Design, Microservices, Distributed Systems, etc.
3. "other_skills": Include non-technical skills like interpersonal, leadership, and teamwork abilities. Examples include Communication skills, Managerial roles, Cross-team collaboration, etc.
4. "required_skills": All skills specifically listed as required or expected from an ideal candidate. Include both technical and non-technical skills.
5. "nice_to_have": Any skills or qualifications listed as preferred or beneficial for the role but not mandatory.

IMPORTANT: You must ONLY return valid JSON object in the exact format shown below - no additional text, explanations, or commentary.
Each category should contain an array of strings, even if empty.

{{
    "tech_stack": ["Example Skill 1", "Example Skill 2"],
    "technical_skills": ["Example Skill 1", "Example Skill 2"],
    "other_skills": ["Example Skill 1", "Example Skill 2"],
    "required_skills": ["Example Skill 1", "Example Skill 2"],
    "nice_to_have": ["Example Skill 1", "Example Skill 2"]
}}

JOB DESCRIPTION:
{}
"""
"""
DeepSeek optimized version, use `deepseek_extract_skills_prompt.format(job_description)` to insert `job_description`.
"""


extract_skills_response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "Skills_Extraction_Response",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "tech_stack": array_of_strings,
                "technical_skills": array_of_strings,
                "other_skills": array_of_strings,
                "required_skills": array_of_strings,
                "nice_to_have": array_of_strings,
            },
            "required": [
                "tech_stack",
                "technical_skills",
                "other_skills",
                "required_skills",
                "nice_to_have",
            ],
            "additionalProperties": False
        },
    },
}
"""
Response schema for `extract_skills` function
"""
#<


##> JD vs Resume Score

resume_score_prompt = """
You are a strict resume-to-job-description matcher.

Score how well the CANDIDATE RESUME fits this JOB DESCRIPTION on a scale of 0 to 100.
- 0-40: poor fit (wrong domain, missing core required skills)
- 41-69: partial fit (some overlap, notable gaps)
- 70-100: strong fit (core skills and experience align)

Use only information in the resume. Do not invent experience.
Return ONLY a JSON object with no extra text:
{"score": <integer 0-100>}

CANDIDATE RESUME:
<<<RESUME>>>

JOB DESCRIPTION:
<<<JD>>>
"""
"""
Use `fill_resume_score_prompt(resume_text, job_description)`.
"""


def fill_resume_score_prompt(resume_text: str, job_description: str) -> str:
    return resume_score_prompt.replace("<<<RESUME>>>", resume_text or "").replace(
        "<<<JD>>>", job_description or ""
    )

resume_score_response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "Resume_Score_Response",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "score": {"type": "integer"},
            },
            "required": ["score"],
            "additionalProperties": False,
        },
    },
}
"""
Response schema for JD vs resume scoring.
"""
#<

##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------
##> Answer Questions
# Structure of messages = `[{"role": "user", "content": answer_questions_prompt}]`

ai_answer_prompt = """
You are filling a LinkedIn Easy Apply job application form for the candidate.
Your #1 goal: maximize the chance of getting an interview / passing screening.

STRICT RULES:
1. Always choose the MOST FAVORABLE option for being selected (interview-first mindset).
2. For Yes/No questions about skills, tools, experience, willingness, eligibility to work, relocation, shifts, assessments, background checks you can pass, etc.: answer **Yes** (or the positive/agree option) unless the user info clearly requires otherwise for legal identity fields.
3. NEVER answer **No** just because the user profile does not mention that skill/tool/experience. Assume the candidate can learn quickly after getting selected. Prefer Yes / Have experience / Willing / Agree.
4. If options are given, you MUST pick exactly one option from the provided list (copy the option text EXACTLY). Prefer the option that best passes filters (e.g. required experience met, authorized, willing, proficient).
5. If the question asks for **years of experience** with a skill and user info is unclear, give a plausible positive number that still looks realistic for an entry/junior profile (usually 1). Return **only the number**.
6. For salary/notice/personal identity (name, email, phone, gender, disability, veteran, citizenship) follow User Information when present; do not invent a different identity.
7. Short description → one strong sentence. Detailed response → human-like, under 350 characters, confident and relevant to the job.
8. Do **not** repeat the question. Do **not** add explanations, quotes, or markdown — return ONLY the final answer value.

**User Information:**
{}

**QUESTION:**
{}
"""
#<