##> ------ Yang Li : MARKYangL - Feature ------
import time

from config.secrets import *
from config.settings import showAiErrorAlerts
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

def deepseek_create_client() -> OpenAI | None:
    '''
    Creates a DeepSeek client using the OpenAI compatible API.
    * Returns an OpenAI-compatible client configured for DeepSeek
    '''
    try:
        print_lg("Creating DeepSeek client...")
        if not is_ai_enabled():
            raise ValueError("AI is not enabled! Please enable it by setting `use_AI = True` in `secrets.py` in `config` folder.")
        
        ##> ------ Tim L : tulxoro - Refactor ------
        base_url = llm_api_url
        

        if base_url.endswith('/'):
            base_url = base_url[:-1]
        
        # Create client with DeepSeek endpoint
        client = OpenAI(
            base_url=base_url,
            api_key=current_api_key() or llm_api_key,
            timeout=float(ai_request_timeout),
        )
        
        print_lg("---- SUCCESSFULLY CREATED DEEPSEEK CLIENT! ----")
        print_lg(f"Using API URL: {base_url}")
        print_lg(f"Using Model: {llm_model}")
        print_lg("Check './config/secrets.py' for more details.\n")
        print_lg("---------------------------------------------")
        ##<
        return client
    except Exception as e:
        error_message = f"Error occurred while creating DeepSeek client. Make sure your API connection details are correct."
        if disable_ai_and_resume_on_rate_limit(f"{error_message} {e}", source="DeepSeek"):
            critical_error_log(error_message, e)
            return None
        critical_error_log(error_message, e)
        if showAiErrorAlerts:
            if "Pause AI error alerts" == confirm(f"{error_message}\n{str(e)}", "DeepSeek Connection Error", ["Pause AI error alerts", "Okay Continue"]):
                showAiErrorAlerts = False
        return None

def deepseek_model_supports_temperature(model_name: str) -> bool:
    '''
    Checks if the specified DeepSeek model supports the temperature parameter.
    * Takes in `model_name` of type `str` - The name of the DeepSeek model
    * Returns `bool` - True if the model supports temperature adjustments
    '''
    # DeepSeek models that support temperature (all current models)
    deepseek_models = ["deepseek-chat", "deepseek-reasoner"]
    return model_name in deepseek_models

def deepseek_completion(client: OpenAI, messages: list[dict], response_format: dict = None, temperature: float = 0, stream: bool = stream_output) -> dict | ValueError:
    '''
    Completes a chat using DeepSeek API and formats the results.
    * Takes in `client` of type `OpenAI` - The DeepSeek client
    * Takes in `messages` of type `list[dict]` - The conversation messages
    * Takes in `response_format` of type `dict` for JSON representation (optional)
    * Takes in `temperature` of type `float` for randomness control (default 0)
    * Takes in `stream` of type `bool` for streaming output (optional)
    * Returns the response as text or JSON
    '''
    if not client: 
        raise ValueError("DeepSeek client is not available!")
    
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
        
        if deepseek_model_supports_temperature(llm_model):
            params["temperature"] = temperature

        if response_format:
            params["response_format"] = response_format

        try:
            print_lg(f"Calling DeepSeek API for completion...")
            print_lg(f"Using model: {llm_model}")
            print_lg(f"Message count: {len(messages)}")
            completion = client.chat.completions.create(**params)
            
            result = ""
            if stream:
                print_lg("--STREAMING STARTED")
                deadline = time.time() + float(ai_request_timeout)
                for chunk in completion:
                    raise_if_stopped()
                    if time.time() > deadline:
                        raise TimeoutError(
                            f"DeepSeek stream exceeded ai_request_timeout={ai_request_timeout}s"
                        )
                    if chunk.model_extra and chunk.model_extra.get("error"):
                        raise ValueError(f'Error occurred with DeepSeek API: "{chunk.model_extra.get("error")}"')
                    chunk_message = chunk.choices[0].delta.content
                    if chunk_message is not None:
                        result += chunk_message
                    print_lg(chunk_message, end="", flush=True)
                print_lg("\n--STREAMING COMPLETE")
            else:
                raise_if_stopped()
                if completion.model_extra and completion.model_extra.get("error"):
                    raise ValueError(f'Error occurred with DeepSeek API: "{completion.model_extra.get("error")}"')
                result = completion.choices[0].message.content
            
            if response_format:
                result = convert_to_json(result)
            
            print_lg("\nDeepSeek Answer:\n")
            print_lg(result, pretty=response_format is not None)
            return result
        except BotStopped:
            raise
        except Exception as e:
            last_error = e
            if try_rotate_ai_key(e, source="DeepSeek AI"):
                print_lg(f"Retrying DeepSeek AI call with API key {current_key_label()}...")
                continue
            raise
    if last_error:
        raise last_error
    raise ValueError("DeepSeek AI completion failed with no remaining API keys.")


def deepseek_extract_skills(client: OpenAI, job_description: str, stream: bool = stream_output) -> dict | ValueError:
    '''
    Function to extract skills from job description using DeepSeek API.
    * Takes in `client` of type `OpenAI` - The DeepSeek client
    * Takes in `job_description` of type `str` - The job description text
    * Takes in `stream` of type `bool` to indicate if it's a streaming call
    * Returns a `dict` object representing JSON response
    '''
    try:
        print_lg("Extracting skills from job description using DeepSeek...")
        
        # Using optimized DeepSeek prompt
        prompt = deepseek_extract_skills_prompt.format(job_description)
        messages = [{"role": "user", "content": prompt}]
        
        # DeepSeek API supports json_object response format
        custom_response_format = {"type": "json_object"}
        
        # Call DeepSeek completion
        result = deepseek_completion(
            client=client,
            messages=messages,
            response_format=custom_response_format,
            stream=stream
        )
        
        # Ensure the result is a dictionary
        if isinstance(result, str):
            result = convert_to_json(result)
            
        return result
    except Exception as e:
        critical_error_log("Error occurred while extracting skills with DeepSeek!", e)
        return {"error": str(e)}

def deepseek_answer_question(
    client: OpenAI, 
    question: str, options: list[str] | None = None, 
    question_type: Literal['text', 'textarea', 'single_select', 'multiple_select'] = 'text', 
    job_description: str = None, about_company: str = None, user_information_all: str = None,
    stream: bool = stream_output
) -> dict | ValueError:
    '''
    Function to answer a question using DeepSeek AI.
    * Takes in `client` of type `OpenAI` - The DeepSeek client
    * Takes in `question` of type `str` - The question to answer
    * Takes in `options` of type `list[str] | None` - Options for select questions
    * Takes in `question_type` - Type of question (text, textarea, single_select, multiple_select)
    * Takes in optional context parameters - job_description, about_company, user_information_all
    * Takes in `stream` of type `bool` - Whether to stream the output
    * Returns the AI's answer
    '''
    try:
        print_lg(f"Answering question using DeepSeek AI: {question}")
        
        # Prepare user information
        user_info = user_information_all or ""
        
        # Prepare prompt based on question type
        prompt = ai_answer_prompt.format(user_info, question)
        
        # Add options to the prompt if available
        if options and (question_type in ['single_select', 'multiple_select']):
            options_str = "OPTIONS:\n" + "\n".join([f"- {option}" for option in options])
            prompt += f"\n\n{options_str}"
            
            if question_type == 'single_select':
                prompt += "\n\nPlease select exactly ONE option from the list above. Copy the option text EXACTLY. Choose the option that maximizes interview chances (prefer Yes/Willing/Have experience; never pick No just because profile data is missing)."
            else:
                prompt += "\n\nYou may select MULTIPLE options from the list above if appropriate. Prefer favorable options that maximize interview chances."
        
        # Add job details for context if available
        if job_description:
            prompt += f"\n\nJOB DESCRIPTION:\n{job_description}"
        
        if about_company:
            prompt += f"\n\nABOUT COMPANY:\n{about_company}"
        
        messages = [{"role": "user", "content": prompt}]
        
        # Call DeepSeek completion
        result = deepseek_completion(
            client=client,
            messages=messages,
            temperature=0.1,  # Slight randomness for more natural responses
            stream=stream
        )
        
        return result
    except Exception as e:
        critical_error_log("Error occurred while answering question with DeepSeek!", e)
        return {"error": str(e)}
##<


def deepseek_score_jd_vs_resume(
    client: OpenAI,
    job_description: str,
    resume_text: str,
    stream: bool = False,
) -> dict | str:
    '''Score JD vs resume (0-100) using the same DeepSeek client / llm_api_key.'''
    try:
        print_lg("-- SCORING JD vs RESUME (DeepSeek)")
        prompt = fill_resume_score_prompt(resume_text, job_description)
        messages = [{"role": "user", "content": prompt}]
        result = deepseek_completion(
            client=client,
            messages=messages,
            response_format={"type": "json_object"},
            stream=stream,
        )
        if isinstance(result, str):
            result = convert_to_json(result)
        return result
    except Exception as e:
        disable_ai_and_resume_on_rate_limit(e, source="DeepSeek scoring")
        critical_error_log("Error occurred while scoring JD vs resume with DeepSeek!", e)
        return {"error": str(e)}
