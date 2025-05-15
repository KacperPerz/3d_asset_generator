# gradio_app/core_logic/service_clients.py
import requests
import json
from .config import LLM_SERVICE_URL

def call_llm_service(prompt_text: str):
    """Calls the LLM service to expand the prompt."""
    if not LLM_SERVICE_URL:
        print("Error: LLM_SERVICE_URL is not configured.")
        return None, "LLM_SERVICE_URL not configured. Please check environment variables."
    
    payload = {"prompt": prompt_text}
    try:
        response = requests.post(f"{LLM_SERVICE_URL}/expand-prompt/", json=payload)
        response.raise_for_status() # Raises an HTTPError for bad responses (4XX or 5XX)
        return response.json(), None
    except requests.exceptions.RequestException as e:
        print(f"Request error calling LLM service: {e}")
        error_message = f"Error connecting to LLM service: {e}"
        if e.response is not None:
            try:
                error_detail = e.response.json().get("detail", e.response.text)
                error_message += f" - Detail: {error_detail}"
            except json.JSONDecodeError:
                error_message += f" - Detail: {e.response.text}"
        return None, error_message
