# gradio_app/core_logic/pipeline.py
import gradio as gr
import json
import os
import uuid
from .s3_utils import (
    upload_to_s3,
)
from .service_clients import (
    call_llm_service,
)

TEMP_ASSET_DIR = "temp_assets"
if not os.path.exists(TEMP_ASSET_DIR):
    os.makedirs(TEMP_ASSET_DIR)


def generate_asset_pipeline(user_prompt_text: str):
    """
    Main pipeline for processing the user request.
    1. Call LLM service to get expanded JSON spec.
    2. Save JSON spec to a local temp file.
    3. Upload JSON spec to S3.
    Returns the JSON spec (as a Python dict) and a status message string.
    """
    status_messages = []

    # 1. Call LLM Service
    status_messages.append(f"Sending prompt to LLM service: '{user_prompt_text[:50]}...'")
    expanded_spec_dict, llm_error = call_llm_service(user_prompt_text)
    
    if llm_error:
        status_messages.append(f"LLM Service Error: {llm_error}")
        # Return None for JSON, and the collected status messages
        return None, "\n".join(status_messages) 
    
    if not expanded_spec_dict:
        status_messages.append("Failed to get expanded specification from LLM service (empty response).")
        return None, "\n".join(status_messages)
    
    status_messages.append("Successfully received expanded JSON from LLM service.")

    # Generate a unique ID for this asset generation process
    asset_id = str(uuid.uuid4())
    
    # Define file paths
    json_filename = f"{asset_id}_metadata.json"
    local_json_path = os.path.join(TEMP_ASSET_DIR, json_filename)

    # 2. Save JSON spec locally (temp)
    try:
        with open(local_json_path, 'w') as f:
            json.dump(expanded_spec_dict, f, indent=4)
        status_messages.append(f"Saved JSON metadata locally to {local_json_path}")
    except IOError as e:
        status_messages.append(f"Error saving JSON locally: {e}")
        # Decide if this is fatal or if we can proceed to S3 upload anyway
        # For now, let's allow proceeding but log the error.

    # 3. Upload JSON to S3
    s3_json_key = f"metadata/{json_filename}" # Store in a 'metadata' "folder"
    
    # Ensure S3 client is available before attempting upload
    # This check might be better in s3_utils or called once at app startup
    # from .s3_utils import S3_CLIENT_INITIALIZED # local import for clarity
    # if not S3_CLIENT_INITIALIZED:
    #     status_messages.append("S3 client not initialized. Cannot upload JSON.")
    # else:
    json_s3_url, s3_error = upload_to_s3(local_json_path, s3_json_key)
    if s3_error:
        status_messages.append(f"S3 Upload Error (JSON): {s3_error}")
    elif json_s3_url:
        status_messages.append(f"JSON metadata uploaded to S3: {json_s3_url}")
    else:
        # This case implies upload_to_s3 returned (None, None) which means S3 might be disabled
        status_messages.append("JSON metadata S3 upload skipped or failed (S3 client might not be initialized).")

    # Clean up local JSON file after S3 upload attempt (if it exists)
    if os.path.exists(local_json_path):
        try:
            os.remove(local_json_path)
            status_messages.append(f"Cleaned up local JSON file: {local_json_path}")
        except OSError as e:
            status_messages.append(f"Error deleting local JSON file {local_json_path}: {e}")
            # Log this error, but it's not critical for the flow's success

    status_messages.append("3D model generation and preview are currently disabled.")
    
    # Return the Python dictionary for the JSON spec and the consolidated status messages
    return expanded_spec_dict, "\n".join(status_messages)
