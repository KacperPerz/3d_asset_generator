# gradio_app/core_logic/service_clients.py
import requests
import json
from .config import LLM_SERVICE_URL, TEXT_TO_IMAGE_SERVICE_URL

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

def call_text_to_image_service(prompt: str, num_inference_steps: int = 5, guidance_scale: float = 7.0) -> bytes | None:
    """Calls the text-to-image generation service and returns the image bytes."""
    if not TEXT_TO_IMAGE_SERVICE_URL:
        print("Text-to-Image service URL not configured. Skipping call.")
        return None

    endpoint = f"{TEXT_TO_IMAGE_SERVICE_URL}/generate-image/"
    payload = {
        "prompt": prompt,
        "num_inference_steps": num_inference_steps,
        "guidance_scale": guidance_scale
    }
    print(f"Calling Text-to-Image service at {endpoint} with prompt: '{prompt}'")
    try:
        response = requests.post(endpoint, json=payload, timeout=120) # Increased timeout for image generation
        response.raise_for_status() # Raises an HTTPError for bad responses (4XX or 5XX)
        
        # The response should directly be the image bytes
        # The content type should be 'image/png' or similar, set by FileResponse
        if 'image' in response.headers.get('Content-Type', '').lower():
            print("Successfully received image data from Text-to-Image service.")
            return response.content # Get the raw image bytes
        else:
            print(f"Unexpected Content-Type from Text-to-Image service: {response.headers.get('Content-Type')}")
            print(f"Response text: {response.text[:200]}...") # Log part of the response if it's not an image
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error calling Text-to-Image service: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred when calling Text-to-Image service: {e}")
        return None
