# gradio_app/core_logic/service_clients.py
import requests
import json
from .config import LLM_SERVICE_URL, TEXT_TO_IMAGE_SERVICE_URL, THREED_GENERATION_SERVICE_URL

def call_llm_service(prompt: str) -> dict:
    """Calls the LLM service to expand the prompt."""
    try:
        response = requests.post(f"{LLM_SERVICE_URL}/expand-prompt/", json={"prompt": prompt})
        response.raise_for_status() 
        return response.json() 
    except requests.exceptions.RequestException as e:
        print(f"Error calling LLM service: {e}")
        # Consider returning a more specific error structure or raising a custom exception
        return {"error": str(e), "details": "Failed to get response from LLM service"}

def call_text_to_image_service(prompt: str) -> bytes | None:
    """Calls the Text-to-Image service and returns the image bytes."""
    try:
        # The service expects a JSON payload with a "prompt" field
        response = requests.post(f"{TEXT_TO_IMAGE_SERVICE_URL}/generate-image/", json={"prompt": prompt})
        response.raise_for_status()
        # The service should return raw image data
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Error calling Text-to-Image service: {e}")
        return None

def call_threed_generation_service(prompt: str, image_input_url: str | None = None, model_id: str = "tencent/hunyuan3d-2") -> bytes | None:
    """Calls the 3D Generation service and returns the 3D model file bytes (e.g., GLB).
    
    Args:
        prompt: The text prompt for 3D model generation (used as caption by Synexa).
        image_input_url: Optional public S3 URL for an input image to be used by the 3D model service.
        model_id: The specific model ID to use (defaulting to Synexa's tencent/hunyuan3d-2).
                  This could be made selectable in the UI later.
                  
    Returns:
        Bytes of the 3D model file if successful, None otherwise.
    """
    try:
        payload = {"prompt": prompt, "model_id": model_id}
        if image_input_url:
            payload["image_s3_key"] = image_input_url # The 3D service API expects 'image_s3_key' in its GenerationRequest
            
        # Use json.dumps for a more complete log of the payload
        print(f"Calling 3D Gen Service at {THREED_GENERATION_SERVICE_URL}/generate-3d/ with payload: {json.dumps(payload)}")
        response = requests.post(f"{THREED_GENERATION_SERVICE_URL}/generate-3d/", json=payload, timeout=300) # Increased timeout for potentially long 3D generation
        response.raise_for_status()
        # The service should return raw model file data (e.g., .glb)
        # Check content type if necessary, e.g. response.headers.get('content-type') == 'model/gltf-binary'
        return response.content
    except requests.exceptions.Timeout:
        print(f"Timeout calling 3D Generation service for prompt: {prompt}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error calling 3D Generation service: {e}")
        # Log more details if available, e.g., response.text
        # if hasattr(e, 'response') and e.response is not None:
        #     print(f"Response content from 3D service on error: {e.response.text}")
        return None
