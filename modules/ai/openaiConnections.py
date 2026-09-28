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


import time

from config.secrets import *
from config.settings import showAiErrorAlerts
from config.personals import ethnicity, gender, disability_status, veteran_status
from config.questions import *
from config.search import security_clearance, did_masters

from modules.helpers import print_lg, critical_error_log, convert_to_json
from modules.ai.prompts import *
from modules.ai_runtime import disable_ai_and_resume_on_rate_limit, is_ai_enabled, try_rotate_ai_key
from modules.ai_keys import apply_key_to_client, current_api_key, current_key_label, key_count
from modules.bot_control import BotStopped, raise_if_stopped

from pyautogui import confirm
from openai import OpenAI
from openai.types.model import Model
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from typing import Iterator, Literal


apiCheckInstructions = """

1. Make sure your AI API connection details like url, key, model names, etc are correct.
2. If you're using an local LLM, please check if the server is running.
3. Check if appropriate LLM and Embedding models are loaded and running.

Open `secret.py` in `/config` folder to configure your AI API connections.

ERROR:
"""

# Function to show an AI error alert
def ai_error_alert(message: str, stackTrace: str, title: str = "AI Connection Error") -> None:
    """
    Function to show an AI error alert and log it.
    On rate/quota limits (HTTP 429), disables LinkedIn AI + Resume Engine for this run.
    """
    global showAiErrorAlerts
    if disable_ai_and_resume_on_rate_limit(f"{message} {stackTrace}", source="LinkedIn AI"):
        # Rate-limit dialog already shown by ai_runtime; skip the huge generic popup.
        critical_error_log(message, stackTrace)
        return
    if showAiErrorAlerts:
        if "Pause AI error alerts" == confirm(f"{message}{stackTrace}\n", title, ["Pause AI error alerts", "Okay Continue"]):
            showAiErrorAlerts = False
    critical_error_log(message, stackTrace)


# Function to check if an error occurred
def ai_check_error(response: ChatCompletion | ChatCompletionChunk) -> None:
    """
    Function to check if an error occurred.
    * Takes in `response` of type `ChatCompletion` or `ChatCompletionChunk`
    * Raises a `ValueError` if an error is found
    """
    if response.model_extra.get("error"):
        raise ValueError(
            f'Error occurred with API: "{response.model_extra.get("error")}"'
        )


# Function to create an OpenAI client
def ai_create_openai_client() -> OpenAI:
    """
    Function to create an OpenAI client.
    * Takes no arguments
    * Returns an `OpenAI` object
    """
    try:
        print_lg("Creating OpenAI client...")
        if not is_ai_enabled():
            raise ValueError("AI is not enabled! Please enable it by setting `use_AI = True` in `secrets.py` in `config` folder.")
        
        client = OpenAI(
            base_url=llm_api_url,
            api_key=current_api_key() or llm_api_key,
            timeout=float(ai_request_timeout),
        )

        models = ai_get_models_list(client)
        if "error" in models:
            raise ValueError(models[1])
        if len(models) == 0:
            raise ValueError("No models are available!")
        model_ids = [model.id for model in models]
        if llm_model not in model_ids:
            print_lg(
                f"Warning: Model `{llm_model}` was not in the API catalog "
                f"({len(model_ids)} models listed). Continuing anyway — OpenRouter often omits IDs."
            )
        
        print_lg("---- SUCCESSFULLY CREATED OPENAI CLIENT! ----")
        print_lg(f"Using API URL: {llm_api_url}")
        print_lg(f"Using Model: {llm_model}")
        print_lg(f"API keys configured: {key_count()} (using {current_key_label()})")
        print_lg(f"Models available from API: {len(model_ids)}")
        print_lg("Check './config/secrets.py' for more details.\n")
        print_lg("---------------------------------------------")

        return client
    except Exception as e:
        ai_error_alert(f"Error occurred while creating OpenAI client. {apiCheckInstructions}", e)


# Function to close an OpenAI client
def ai_close_openai_client(client: OpenAI) -> None:
    """
    Function to close an OpenAI client.
    * Takes in `client` of type `OpenAI`
    * Returns no value
    """
    try:
        if client:
            print_lg("Closing OpenAI client...")
            client.close()
    except Exception as e:
        ai_error_alert("Error occurred while closing OpenAI client.", e)



# Function to get list of models available in OpenAI API
def ai_get_models_list(client: OpenAI) -> list[ Model | str]:
    """
    Function to get list of models available in OpenAI API.
    * Takes in `client` of type `OpenAI`
    * Returns a `list` object
    """
    try:
        print_lg("Getting AI models list...")
        if not client: raise ValueError("Client is not available!")
        models = client.models.list()
        ai_check_error(models)
        # Do not dump the full OpenRouter/OpenAI catalog into the console.
        count = len(models.data) if getattr(models, "data", None) is not None else 0
        print_lg(f"Fetched {count} available model(s) from API (details omitted).")
        return models.data
    except Exception as e:
        critical_error_log("Error occurred while getting models list!", e)
        return ["error", e]

def model_supports_temperature(model_name: str) -> bool:
    """
    Checks if the specified model supports the temperature parameter.
    
    Args:
        model_name (str): The name of the AI model.
    
    Returns:
        bool: True if the model supports temperature adjustments, otherwise False.
    """
    return model_name in ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o", "gpt-4o-mini"]

# Function to get chat completion from OpenAI API
def ai_completion(client: OpenAI, messages: list[dict], response_format: dict = None, temperature: float = 0, stream: bool = stream_output) -> dict | ValueError:
    """
    Function that completes a chat and prints and formats the results of the OpenAI API calls.
    * Takes in `client` of type `OpenAI`
    * Takes in `messages` of type `list[dict]`. Example: `[{"role": "user", "content": "Hello"}]`
    * Takes in `response_format` of type `dict` for JSON representation, default is `None`
    * Takes in `temperature` of type `float` for temperature, default is `0`
    * Takes in `stream` of type `bool` to indicate if it's a streaming call or not
    * Returns a `dict` object representing JSON response, will try to convert to JSON if `response_format` is given
    """
    if not client: raise ValueError("Client is not available!")

    raise_if_stopped()
    last_error = None
    attempts = max(1, key_count() or 1)
    for attempt in range(attempts):
        apply_key_to_client(client)
        params = {
            "model": llm_model,
            "messages": messages,
            "stream": stream,
            "timeout": float(ai_request_timeout),
        }

        if model_supports_temperature(llm_model):
            params["temperature"] = temperature
        if response_format and llm_spec in ["openai", "openai-like"]:
            params["response_format"] = response_format

        try:
            completion = client.chat.completions.create(**params)

            result = ""

            # Log response
            if stream:
                print_lg("--STREAMING STARTED")
                deadline = time.time() + float(ai_request_timeout)
                for chunk in completion:
                    raise_if_stopped()
                    if time.time() > deadline:
                        raise TimeoutError(
                            f"AI stream exceeded ai_request_timeout={ai_request_timeout}s"
                        )
                    ai_check_error(chunk)
                    chunkMessage = chunk.choices[0].delta.content
                    if chunkMessage != None:
                        result += chunkMessage
                    print_lg(chunkMessage, end="", flush=True)
                print_lg("\n--STREAMING COMPLETE")
            else:
                raise_if_stopped()
                ai_check_error(completion)
                result = completion.choices[0].message.content

            if response_format:
                result = convert_to_json(result)

            print_lg("\nAI Answer to Question:\n")
            print_lg(result, pretty=response_format)
            return result
        except BotStopped:
            raise
        except Exception as e:
            last_error = e
            if try_rotate_ai_key(e, source="LinkedIn AI"):
                print_lg(f"Retrying AI call with API key {current_key_label()}...")
                continue
            raise
    if last_error:
        raise last_error
    raise ValueError("AI completion failed with no remaining API keys.")


def ai_extract_skills(client: OpenAI, job_description: str, stream: bool = stream_output) -> dict | ValueError:
    """
    Function to extract skills from job description using OpenAI API.
    * Takes in `client` of type `OpenAI`
    * Takes in `job_description` of type `str`
    * Takes in `stream` of type `bool` to indicate if it's a streaming call
    * Returns a `dict` object representing JSON response
    """
    print_lg("-- EXTRACTING SKILLS FROM JOB DESCRIPTION")
    try:        
        prompt = extract_skills_prompt.format(job_description)

        messages = [{"role": "user", "content": prompt}]
        ##> ------ Dheeraj Deshwal : dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Bug fix ------
        return ai_completion(client, messages, response_format=extract_skills_response_format, stream=stream)
    ##<
    except BotStopped:
        raise
    except Exception as e:
        ai_error_alert(f"Error occurred while extracting skills from job description. {apiCheckInstructions}", e)


##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------
def ai_answer_question(
    client: OpenAI, 
    question: str, options: list[str] | None = None, question_type: Literal['text', 'textarea', 'single_select', 'multiple_select'] = 'text', 
    job_description: str = None, about_company: str = None, user_information_all: str = None,
    stream: bool = stream_output
) -> dict | ValueError:
    """
    Function to generate AI-based answers for questions in a form.
    
    Parameters:
    - `client`: OpenAI client instance.
    - `question`: The question being answered.
    - `options`: List of options (for `single_select` or `multiple_select` questions).
    - `question_type`: Type of question (text, textarea, single_select, multiple_select) It is restricted to one of four possible values.
    - `job_description`: Optional job description for context.
    - `about_company`: Optional company details for context.
    - `user_information_all`: information about you, AI cna use to answer question eg: Resume-like user information.
    - `stream`: Whether to use streaming AI completion.
    
    Returns:
    - `str`: The AI-generated answer.
    """

    print_lg("-- ANSWERING QUESTION using AI")
    try:
        prompt = ai_answer_prompt.format(user_information_all or "N/A", question)
         # Append optional details if provided
        if options and (question_type in ['single_select', 'multiple_select']):
            options_str = "OPTIONS:\n" + "\n".join([f"- {option}" for option in options])
            prompt += f"\n\n{options_str}"
            if question_type == 'single_select':
                prompt += "\n\nSelect exactly ONE option from the list above. Copy the option text EXACTLY. Choose the option that maximizes interview chances."
            else:
                prompt += "\n\nYou may select MULTIPLE options if appropriate. Prefer favorable options that maximize interview chances."
        if job_description and job_description != "Unknown":
            prompt += f"\nJob Description:\n{job_description}"
        if about_company and about_company != "Unknown":
            prompt += f"\nAbout the Company:\n{about_company}"

        messages = [{"role": "user", "content": prompt}]
        print_lg("Prompt we are passing to AI: ", prompt)
        response =  ai_completion(client, messages, stream=stream)
        # print_lg("Response from AI: ", response)
        return response
    except Exception as e:
        ai_error_alert(f"Error occurred while answering question. {apiCheckInstructions}", e)
##<


def ai_gen_experience(
    client: OpenAI, 
    job_description: str, about_company: str, 
    required_skills: dict, user_experience: dict,
    stream: bool = stream_output
) -> dict | ValueError:
    pass



def ai_generate_resume(
    client: OpenAI, 
    job_description: str, about_company: str, required_skills: dict,
    stream: bool = stream_output
) -> dict | ValueError:
    '''
    Function to generate resume. Takes in user experience and template info from config.
    '''
    pass



def ai_generate_coverletter(
    client: OpenAI, 
    job_description: str, about_company: str, required_skills: dict,
    stream: bool = stream_output
) -> dict | ValueError:
    '''
    Function to generate resume. Takes in user experience and template info from config.
    '''
    pass



##< Evaluation Agents
def ai_score_jd_vs_resume(
    client: OpenAI,
    job_description: str,
    resume_text: str,
    stream: bool = False,
) -> dict | ValueError:
    """
    Score how well resume_text matches job_description (0-100).
    Uses the same OpenAI-compatible client / llm_api_key as other AI calls.
    """
    print_lg("-- SCORING JD vs RESUME")
    try:
        prompt = fill_resume_score_prompt(resume_text, job_description)
        messages = [{"role": "user", "content": prompt}]
        try:
            return ai_completion(
                client,
                messages,
                response_format=resume_score_response_format,
                stream=stream,
            )
        except Exception:
            # Many OpenRouter / openai-like models reject json_schema; retry as plain text.
            return ai_completion(client, messages, stream=stream)
    except BotStopped:
        raise
    except Exception as e:
        ai_error_alert(
            f"Error occurred while scoring JD vs resume. {apiCheckInstructions}",
            e,
        )
        return {"error": str(e)}



def ai_check_job_relevance(
    client: OpenAI, 
    job_description: str, about_company: str,
    stream: bool = stream_output
) -> dict:
    pass
#>