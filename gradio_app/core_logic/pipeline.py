# gradio_app/core_logic/pipeline.py
import gradio as gr
import json
import os
import uuid
import io # For BytesIO
from .s3_utils import (
    upload_file_obj_to_s3,
)
from .service_clients import (
    call_llm_service,
    call_text_to_image_service,
)
from .config import S3_BUCKET_NAME


def generate_asset_pipeline(user_prompt: str):
    """Orchestrates the asset generation pipeline."""
    print(f"Starting asset generation pipeline for prompt: '{user_prompt}'")

    # 1. Call LLM to expand the prompt
    # call_llm_service should return a Python dict directly (or None if error).
    asset_metadata, error_message_llm = call_llm_service(user_prompt)
    
    if error_message_llm:
        return None, None, f"LLM service error: {error_message_llm}"
    
    # Ensure asset_metadata is a dictionary after the call
    if not isinstance(asset_metadata, dict):
        error_msg = f"LLM service returned unexpected type: {type(asset_metadata)}. Expected a dictionary."
        print(error_msg)
        # If it's None, call_llm_service might have already printed an error.
        # If it's not None but also not a dict, this is a new error condition.
        if asset_metadata is not None: # Log the actual problematic data if it's not None
             print(f"Problematic data from LLM service: {asset_metadata}")
        return None, None, error_msg

    # asset_metadata is now confirmed to be a dictionary (or the function has returned an error)
    # No need for json.loads() here.

    # Add original prompt to metadata
    asset_metadata['_user_prompt'] = user_prompt
    asset_metadata['_version'] = '1.0' # Example versioning

    # 2. Generate Image using Text-to-Image Service
    image_bytes = call_text_to_image_service(user_prompt) # Using original user prompt for image
    
    image_s3_key = None
    if image_bytes:
        print("Image data received, attempting to upload to S3.")
        image_filename = f"generated_image_{uuid.uuid4()}.png"
        image_s3_key = f"images/{image_filename}" # Define an S3 path for images
        
        try:
            # Ensure S3_BUCKET_NAME is valid before calling upload
            if not S3_BUCKET_NAME:
                raise ValueError("S3_BUCKET_NAME is not configured.")
            upload_url, upload_error = upload_file_obj_to_s3(io.BytesIO(image_bytes), S3_BUCKET_NAME, image_s3_key, content_type='image/png')
            if upload_error:
                raise Exception(f"S3 upload failed: {upload_error}")
            print(f"Image uploaded to S3: {upload_url}")
            asset_metadata['image_s3_key'] = image_s3_key
        except Exception as e:
            print(f"Error uploading image to S3: {e}")
            asset_metadata['image_s3_error'] = str(e) # Log error in metadata
            # Continue without a fatal error, image_s3_key will remain None or its previous value if error occurred after assignment
    else:
        print("No image data received from Text-to-Image service.")
        asset_metadata['image_s3_key'] = None # Explicitly set to None if no image

    # 3. Upload the final JSON metadata to S3
    final_json_string_for_upload = ""
    try:
        final_json_string_for_upload = json.dumps(asset_metadata, indent=2)
        if not S3_BUCKET_NAME:
            raise ValueError("S3_BUCKET_NAME is not configured for metadata upload.")
        json_s3_filename = f"asset_{uuid.uuid4()}.json"
        json_s3_object_name = f"metadata/{json_s3_filename}"
        upload_url_json, upload_error_json = upload_file_obj_to_s3(io.BytesIO(final_json_string_for_upload.encode('utf-8')), S3_BUCKET_NAME, json_s3_object_name, content_type='application/json')
        if upload_error_json:
            raise Exception(f"S3 upload for JSON metadata failed: {upload_error_json}")
        print(f"JSON metadata uploaded to S3: {upload_url_json}")
    except ValueError as ve:
        print(f"Configuration error for S3 upload: {ve}")
        return None, None, f"Configuration error: {ve}"
    except Exception as e:
        print(f"Error uploading JSON metadata to S3: {e}")
        return None, None, f"Error uploading JSON metadata to S3: {e}"

    # Return the final JSON content (as a string for display), the image S3 key, and no error message
    return final_json_string_for_upload, image_s3_key, None
