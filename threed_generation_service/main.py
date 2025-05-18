import fastapi
import httpx # Using httpx for async requests, which is good practice with FastAPI
import os
import uuid
import asyncio # Added for polling
from pydantic import BaseModel
from fastapi.responses import FileResponse, JSONResponse

# --- Configuration ---
SYNEXA_API_KEY = os.getenv("SYNEXA_API_KEY")
SYNEXA_API_URL = "https://api.synexa.ai/v1/predictions"
# Define the model we intend to use from Synexa's gallery
# As per https://synexa.ai, tencent/hunyuan3d-2 seems to be a valid model name
DEFAULT_3D_MODEL_ID = "tencent/hunyuan3d-2"

TEMP_MODEL_OUTPUT_DIR = "/home/appuser_3dgen/app/generated_3d_models_temp"
if not os.path.exists(TEMP_MODEL_OUTPUT_DIR):
    os.makedirs(TEMP_MODEL_OUTPUT_DIR, exist_ok=True)

# Polling configuration
POLLING_INTERVAL_SECONDS = 10 # How often to poll for results
POLLING_TIMEOUT_SECONDS = 300  # Max time to wait for a result (5 minutes)

app = fastapi.FastAPI()

# --- Pydantic Models ---
class GenerationRequest(BaseModel):
    prompt: str
    model_id: str | None = DEFAULT_3D_MODEL_ID # Allow overriding the model if needed
    image_s3_key: str | None = None # Optional S3 key for an input image

# ModelOutputResponse is not explicitly used for endpoint response_model due to dynamic FileResponse/JSONResponse
# but serves as a reference for the structure of the JSONResponse when a URL is returned.
class ModelOutputResponse(BaseModel):
    status: str
    message: str | None = None
    model_url: str | None = None
    prompt_used: str
    model_id_used: str

# --- API Endpoint ---
@app.post("/generate-3d/")
async def generate_3d_model(request: GenerationRequest):
    print("[3D Gen Service] Received request for /generate-3d/")
    if not SYNEXA_API_KEY:
        print("[3D Gen Service] ERROR: SYNEXA_API_KEY not configured.")
        raise fastapi.HTTPException(status_code=500, detail="SYNEXA_API_KEY not configured on server.")
    if not request.prompt:
        print("[3D Gen Service] ERROR: Prompt cannot be empty.")
        raise fastapi.HTTPException(status_code=400, detail="Prompt cannot be empty.")

    model_to_use = request.model_id or DEFAULT_3D_MODEL_ID
    print(f"[3D Gen Service] Using model: {model_to_use}, Prompt: '{request.prompt}'{f', Image S3 Key: {request.image_s3_key}' if request.image_s3_key else ''}")

    headers = {
        "x-api-key": SYNEXA_API_KEY,
        "Content-Type": "application/json",
    }

    synexa_input_payload = {}

    if model_to_use == "tencent/hunyuan3d-2":
        if not request.image_s3_key:
            print(f"[3D Gen Service] ERROR: image_s3_key is required for model '{model_to_use}'.")
            raise fastapi.HTTPException(status_code=400, detail=f"image_s3_key is required for model '{model_to_use}'.")
        
        synexa_input_payload = {
            "caption": request.prompt,  # Use prompt as caption
            "image": request.image_s3_key,
            "steps": 10,  # Renamed from num_inference_steps
            "guidance_scale": 5.5,
            "octree_resolution": 256, # Synexa expects string for this model based on their example, but API error showed int. Let's try int first.
            "shape_only": False,  # To enable textures (texture: True was the old goal)
        }
        print(f"[3D Gen Service] Constructed payload for tencent/hunyuan3d-2 (image-to-3D): {synexa_input_payload}")
    else:
        print(f"[3D Gen Service] WARNING: Using fallback payload for model '{model_to_use}'. This might not be optimal or valid.")
        synexa_input_payload = {
            "prompt": request.prompt,
            "num_inference_steps": 10,
            "guidance_scale": 5.5,
            "octree_resolution": 256,
            "face_count": 40000, # This field might not be valid for many models
            "texture": True
        }
        if request.image_s3_key:
            synexa_input_payload["image"] = request.image_s3_key
            print(f"[3D Gen Service] Added image_s3_key '{request.image_s3_key}' to fallback payload.")
        else:
            print("[3D Gen Service] No image_s3_key provided for fallback payload.")

    payload = {
        "model": model_to_use,
        "input": synexa_input_payload,
    }
    print(f"[3D Gen Service] Synexa API Initial POST Payload: {payload}")

    temp_file_path = None
    try:
        print("[3D Gen Service] Entering main try block for Synexa API call.")
        async with httpx.AsyncClient(timeout=30.0) as client: # Timeout for individual HTTP calls
            print(f"[3D Gen Service] Calling Synexa API ({SYNEXA_API_URL}) for model: {model_to_use} with prompt: '{request.prompt}'")
            
            initial_response = await client.post(SYNEXA_API_URL, headers=headers, json=payload)
            print(f"[3D Gen Service] Synexa API initial POST response status: {initial_response.status_code}")
            initial_response.raise_for_status() # Raise HTTPStatusError for bad responses (4xx or 5xx)

            prediction_result = initial_response.json()
            print(f"[3D Gen Service] Synexa API initial POST JSON response: {prediction_result}")

            prediction_id = prediction_result.get("id")
            status = prediction_result.get("status")

            # Polling logic for asynchronous predictions
            if status in ["starting", "processing"] and prediction_id:
                print(f"[3D Gen Service] Prediction started (ID: {prediction_id}, Status: {status}). Beginning polling every {POLLING_INTERVAL_SECONDS}s for {POLLING_TIMEOUT_SECONDS}s.")
                
                lapsed_time = 0
                while lapsed_time < POLLING_TIMEOUT_SECONDS:
                    await asyncio.sleep(POLLING_INTERVAL_SECONDS)
                    lapsed_time += POLLING_INTERVAL_SECONDS

                    print(f"[3D Gen Service] Polling for prediction ID: {prediction_id} (elapsed: {lapsed_time}s)")
                    get_status_url = f"{SYNEXA_API_URL}/{prediction_id}" # Common pattern for REST APIs
                    
                    # Use a new client or the same, ensure headers are set for GET
                    # Re-creating headers for polling GET request, as it might be different (though usually not for API keys)
                    poll_headers = {"x-api-key": SYNEXA_API_KEY}
                    
                    poll_response = await client.get(get_status_url, headers=poll_headers)
                    print(f"[3D Gen Service] Synexa API GET poll response status: {poll_response.status_code}")
                    poll_response.raise_for_status()
                    
                    prediction_result = poll_response.json() # Update with the latest status
                    status = prediction_result.get("status")
                    print(f"[3D Gen Service] Synexa API GET poll JSON response: {prediction_result}")

                    if status == "succeeded":
                        print(f"[3D Gen Service] Prediction ID {prediction_id} succeeded.")
                        break # Exit polling loop
                    elif status in ["failed", "canceled"]:
                        error_detail = prediction_result.get("error", "Unknown error from Synexa during polling.")
                        print(f"[3D Gen Service] ERROR: Prediction ID {prediction_id} {status}. Details: {error_detail}")
                        raise fastapi.HTTPException(status_code=500, detail=f"Synexa prediction {status}: {error_detail}")
                    elif status not in ["starting", "processing"]:
                        print(f"[3D Gen Service] WARNING: Unknown status '{status}' for prediction ID {prediction_id}. Stopping poll.")
                        raise fastapi.HTTPException(status_code=500, detail=f"Synexa prediction returned unknown status: {status}")

                    print(f"[3D Gen Service] Prediction ID {prediction_id} status: {status}. Continuing poll.")

                if status != "succeeded":
                    print(f"[3D Gen Service] ERROR: Polling timed out for prediction ID {prediction_id} after {POLLING_TIMEOUT_SECONDS}s. Last status: {status}")
                    raise fastapi.HTTPException(status_code=504, detail=f"Synexa prediction polling timed out. Last status: {status}")
            
            elif status == "succeeded":
                print("[3D Gen Service] Prediction was already successful in initial response (synchronous).")
            elif status in ["failed", "canceled"]:
                error_detail = prediction_result.get("error", "Unknown error from Synexa in initial response.")
                print(f"[3D Gen Service] ERROR: Prediction {status} in initial response. Details: {error_detail}")
                raise fastapi.HTTPException(status_code=500, detail=f"Synexa prediction {status}: {error_detail}")
            else: # No ID or unexpected initial status
                if not prediction_id:
                     print("[3D Gen Service] ERROR: No prediction ID in Synexa's initial response.")
                     raise fastapi.HTTPException(status_code=500, detail="Synexa API did not return a prediction ID.")
                else:
                    print(f"[3D Gen Service] ERROR: Unexpected initial status '{status}' from Synexa for ID {prediction_id}.")
                    raise fastapi.HTTPException(status_code=500, detail=f"Synexa API returned unexpected initial status: {status}")


            # At this point, prediction_result should contain the final successful state
            content_type = "" # Will be determined by downloaded content
            
            # Check for direct binary response (should not happen if polling was done and status was 'succeeded' with a URL)
            # This part of logic might be less relevant if polling always results in a JSON with URL.
            # However, keeping it for robustness in case Synexa API behavior varies.

            if "output" not in prediction_result or prediction_result["output"] is None:
                 # This was the previous error point if the initial response was 'starting' but had no 'output'
                 # If polling was successful, 'output' should now be populated.
                 print(f"[3D Gen Service] ERROR: Synexa JSON response (after potential polling) still lacks 'output' or 'output' is null. Response: {prediction_result}")
                 raise fastapi.HTTPException(status_code=500, detail="Synexa API response did not contain 'output' after processing.")

            # Attempt to extract model URL from common patterns within 'output'
            # This part needs to be robust to how Synexa structures the 'output' field upon success.
            output_data = prediction_result.get("output")
            model_url = None

            if isinstance(output_data, dict) and output_data.get("url"):
                model_url = output_data["url"]
            elif isinstance(output_data, list) and len(output_data) > 0:
                if isinstance(output_data[0], str) and output_data[0].startswith("http"): # List of URLs
                    model_url = output_data[0]
                elif isinstance(output_data[0], dict) and output_data[0].get("url"): # List of dicts with URLs
                     model_url = output_data[0]["url"]
            elif isinstance(output_data, str) and output_data.startswith("http"): # Direct URL string in output
                 model_url = output_data
            
            # The original example response for tencent/hunyuan3d-2 showed "output": null when "status": "starting".
            # A successful response for other models might have "output": [{"url": "..."}] or "output": "urlstring"
            # We need to ensure we handle the successful output structure correctly.
            # For now, the above extraction attempts common patterns.

            if model_url:
                print(f"[3D Gen Service] Extracted model URL: {model_url}. Downloading model...")
                # Use a new client for potentially long download, with follow_redirects
                async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as download_client: 
                    model_response = await download_client.get(model_url)
                    print(f"[3D Gen Service] Model download response status: {model_response.status_code}")
                    model_response.raise_for_status() 

                model_data = model_response.content
                content_type = model_response.headers.get("content-type", "").lower() # Get content type from download
                
                # Infer extension from URL or content type
                filename_from_url = os.path.basename(model_url).split('?')[0] 
                _, extension_from_url = os.path.splitext(filename_from_url)
                
                extension = ".glb" # Default
                if extension_from_url and len(extension_from_url) > 1:
                    extension = extension_from_url
                elif content_type:
                    if "model/gltf-binary" in content_type: extension = ".glb"
                    elif "model/obj" in content_type: extension = ".obj"
                    elif "model/vnd.gltf+json" in content_type: extension = ".gltf"
                    # Add other content-types if necessary

                filename = f"downloaded_model_{uuid.uuid4()}{extension}"
                temp_file_path = os.path.join(TEMP_MODEL_OUTPUT_DIR, filename)
                
                with open(temp_file_path, "wb") as f:
                    f.write(model_data)
                print(f"[3D Gen Service] Successfully downloaded model from Synexa URL. Saved temporarily to: {temp_file_path}")
                
                final_media_type = content_type if content_type else "application/octet-stream"
                if extension == ".glb" and not final_media_type: final_media_type = "model/gltf-binary"
                elif extension == ".obj" and not final_media_type: final_media_type = "model/obj"
                elif extension == ".gltf" and not final_media_type: final_media_type = "model/gltf+json"

                return FileResponse(temp_file_path, media_type=final_media_type, filename=filename)
            else: # No model_url found in the successful 'output'
                print(f"[3D Gen Service] ERROR: Synexa prediction succeeded but the 'output' field did not contain a usable model URL. Output content: {output_data}")
                raise fastapi.HTTPException(status_code=500, detail="Synexa API succeeded but no model URL found in output.")

            # This part for direct binary data in initial response is unlikely to be hit if polling is active.
            # It's more of a fallback for a hypothetical synchronous binary response.
            # If Synexa returns direct binary data after polling (which is unusual for 'succeeded' status that implies a URL was generated)
            # then response.content from the *polling* GET would be the model data.
            # This section might need re-evaluation based on actual Synexa behavior for polled successful responses.
            # For now, the primary path is extracting URL from JSON 'output' after successful polling.

            # elif any(ct in initial_response.headers.get("content-type", "").lower() for ct in ["model/gltf-binary", "model/obj", "model/vnd.gltf+json", "application/octet-stream"]):\n            #     print("[3D Gen Service] Synexa returned direct binary model data in initial response.")\n            #     model_data = initial_response.content\n            #     # ... (rest of direct binary handling) ...
            # else:\n            #     error_detail_response = initial_response.text\n            #     print(f"[3D Gen Service] ERROR: Unexpected content type or structure from Synexa API after initial POST: {initial_response.headers.get('content-type', '')}. Response text: {error_detail_response[:500]}...")\n            #     raise fastapi.HTTPException(status_code=500, detail=f"Unexpected content/structure from Synexa: {error_detail_response[:200]}")

    except httpx.HTTPStatusError as e:
        print(f"[3D Gen Service] ERROR caught: httpx.HTTPStatusError: {e}")
        print(f"[3D Gen Service] Exception request URL: {e.request.url if e.request else 'N/A'}")
        print(f"[3D Gen Service] Exception response status: {e.response.status_code if e.response else 'N/A'}")
        print(f"[3D Gen Service] Exception response text: {e.response.text if e.response else 'N/A'}")
        error_body = "No additional error body."
        if e.response: 
            error_body = f"Status {e.response.status_code}."
            try:
                if e.response.text:
                    error_data = e.response.json()
                    error_body += " " + (error_data.get("detail") or error_data.get("error") or str(error_data))
                elif e.response.content: 
                    error_body += " " + e.response.content.decode(errors='replace')[:500]
            except Exception as parse_exc:
                 print(f"[3D Gen Service] Error parsing error response body: {parse_exc}")
                 if e.response.content:
                    error_body += " " + e.response.content.decode(errors='replace')[:500]
        
        if 'model_response' in locals() and e.request.url == model_response.url: # type: ignore
            print(f"[3D Gen Service] Specific Error: Failed to download model from Synexa-provided URL ({e.request.url if e.request else 'N/A'}). Error: {error_body}")
            raise fastapi.HTTPException(status_code=e.response.status_code if e.response else 502, detail=f"Failed to download model from Synexa URL: {error_body}")
        else:
            print(f"[3D Gen Service] Specific Error: Synexa API request failed. Error: {error_body}")
            raise fastapi.HTTPException(status_code=e.response.status_code if e.response else 500, detail=f"Synexa API Error: {error_body}")

    except httpx.RequestError as e: 
        print(f"[3D Gen Service] ERROR caught: httpx.RequestError: {e}")
        print(f"[3D Gen Service] Exception request URL: {e.request.url if e.request else 'N/A'}")
        if 'model_url' in locals() and e.request.url == model_url: # type: ignore
            print(f"[3D Gen Service] Specific Error: Network error downloading model from Synexa-provided URL ({e.request.url if e.request else 'N/A'}): {e}")
            raise fastapi.HTTPException(status_code=503, detail=f"Service unavailable (error downloading model from Synexa URL): {e}")
        else:
            print(f"[3D Gen Service] Specific Error: Error calling Synexa API (httpx.RequestError): {e}")
            raise fastapi.HTTPException(status_code=503, detail=f"Service unavailable (Synexa API client request error): {e}")
    except Exception as e:
        print(f"[3D Gen Service] ERROR caught: Unexpected generic Exception: {type(e).__name__}: {e}")
        import traceback
        print("[3D Gen Service] Traceback:")
        traceback.print_exc()
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                print(f"[3D Gen Service] Cleaned up temporary model file due to error: {temp_file_path}")
            except Exception as e_clean:
                print(f"[3D Gen Service] Error cleaning up temporary model file {temp_file_path}: {e_clean}")
        raise fastapi.HTTPException(status_code=500, detail=f"An unexpected server error occurred: {type(e).__name__} - {str(e)}")

if __name__ == "__main__":
    # This part is for local testing of this service directly.
    # Example: `python threed_generation_service/main.py` (ensure .env with SYNEXA_API_KEY is in project root or key is in env)
    # You'll need to have uvicorn and python-dotenv installed in your local Python environment for this to work.

    # Re-check token after attempting to load .env
    if not os.getenv("SYNEXA_API_KEY"):
        print("SYNEXA_API_KEY not found in environment or .env file. Please set it to run locally.")
    else:
        import uvicorn
        print("Attempting to run 3D Generation Service locally on http://localhost:5002")
        uvicorn.run("main:app", host="0.0.0.0", port=5002, reload=True, workers=1)
