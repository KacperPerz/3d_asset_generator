# gradio_app/core_logic/pipeline.py
import json
import uuid
from .s3_utils import (
    upload_file_obj_to_s3,
    get_s3_public_url
)
from .service_clients import (
    call_llm_service,
    call_text_to_image_service,
    call_threed_generation_service,
)
from .config import S3_JSON_FOLDER, S3_IMAGE_FOLDER, S3_MODEL_FOLDER


def process_request_and_upload(user_prompt: str, output_type: str):
    """
    Processes the user prompt based on the selected output_type:
    1. Calls LLM service to get JSON metadata.
    2. If output_type is 'Image', calls Text-to-Image service and uploads image to S3.
    3. If output_type is '3D Model', calls 3D Generation service and uploads model to S3.
    4. Uploads JSON (which includes appropriate S3 key) to S3.
    5. Returns the JSON string, image S3 key (if any), 3D model S3 key (if any), and error message.
    """
    json_s3_key = None
    image_s3_key = None
    model_s3_key = None 
    error_message = None
    full_json_data = {}

    asset_id = str(uuid.uuid4()) # Unique identifier for the asset

    # 1. Call LLM service
    print(f"[Pipeline] Calling LLM service for prompt: '{user_prompt}'")
    llm_response_data = call_llm_service(user_prompt)
    if not llm_response_data or llm_response_data.get("error"):
        error_message = f"LLM service error: {llm_response_data.get('details', 'Unknown error')}"
        return None, None, None, error_message # Critical error, stop here
    
    full_json_data = llm_response_data 
    full_json_data["_user_prompt"] = user_prompt
    full_json_data["_selected_output_type"] = output_type # Store the choice in metadata
    
    prompt_to_use = full_json_data.get("expanded_prompt", user_prompt)

    # 2. Conditional Image Generation
    if output_type == "Image":
        print(f"[Pipeline] Output type is Image. Calling Text-to-Image service.")
        print(f"[Pipeline] Using image prompt: '{prompt_to_use}'")

        image_bytes = call_text_to_image_service(prompt_to_use)
        if image_bytes:
            image_s3_key = f"{S3_IMAGE_FOLDER}{asset_id}.png"
            try:
                upload_file_obj_to_s3(image_bytes, image_s3_key, content_type='image/png')
                print(f"[Pipeline] Successfully uploaded image to {image_s3_key}")
                full_json_data["image_s3_key"] = image_s3_key
            except Exception as e:
                img_upload_err = f"Image S3 upload error: {e}"
                error_message = (error_message + " | " if error_message else "") + img_upload_err
                print(f"[Pipeline] {img_upload_err}")
                image_s3_key = None # Upload failed, so no key
        else:
            img_gen_err = "Text-to-Image service failed to generate image."
            error_message = (error_message + " | " if error_message else "") + img_gen_err
            print(f"[Pipeline] {img_gen_err}")
    
    # 3. Conditional 3D Model Generation
    elif output_type == "3D Model":
        print(f"[Pipeline] Output type is 3D Model. Generating intermediate image first.")
        
        # FIRST: Generate image for the 3D model
        # Using the same prompt_to_use for the intermediate image for now.
        image_for_3d_prompt = prompt_to_use 
        print(f"[Pipeline] Generating intermediate image for 3D model using prompt: '{image_for_3d_prompt}'")
        image_bytes_for_3d = call_text_to_image_service(image_for_3d_prompt)
        
        temp_image_s3_key_for_3d = None # Store the S3 key for the intermediate image
        temp_image_s3_url_for_3d = None # Store the S3 public URL for the intermediate image

        if image_bytes_for_3d:
            temp_image_s3_key_for_3d = f"{S3_IMAGE_FOLDER}{asset_id}_temp_for_3d.png" # Ensure unique name
            try:
                upload_file_obj_to_s3(image_bytes_for_3d, temp_image_s3_key_for_3d, content_type='image/png')
                print(f"[Pipeline] Successfully uploaded intermediate image for 3D to S3 key: {temp_image_s3_key_for_3d}")
                full_json_data["intermediate_image_s3_key"] = temp_image_s3_key_for_3d # For traceability
                
                # Get the public URL for the uploaded image
                temp_image_s3_url_for_3d = get_s3_public_url(temp_image_s3_key_for_3d)
                if temp_image_s3_url_for_3d:
                    print(f"[Pipeline] Intermediate image S3 public URL: {temp_image_s3_url_for_3d}")
                    full_json_data["intermediate_image_s3_url"] = temp_image_s3_url_for_3d
                else:
                    # This case should ideally not happen if bucket/region are configured
                    print(f"[Pipeline] CRITICAL: Could not generate S3 public URL for key {temp_image_s3_key_for_3d}. 3D gen will likely fail.")
                    # temp_image_s3_url_for_3d remains None, error will be caught before calling 3D service

            except Exception as e:
                img_upload_err = f"Intermediate image S3 upload error for 3D: {e}"
                error_message = (error_message + " | " if error_message else "") + img_upload_err
                print(f"[Pipeline] {img_upload_err}")
                temp_image_s3_key_for_3d = None # Upload failed
                temp_image_s3_url_for_3d = None
        else:
            img_gen_err = "Text-to-Image service failed to generate intermediate image for 3D model."
            error_message = (error_message + " | " if error_message else "") + img_gen_err
            print(f"[Pipeline] {img_gen_err}")

        # SECOND: Call 3D generation service, passing the S3 URL of the generated image
        model_bytes = None
        if temp_image_s3_url_for_3d: # Only proceed if we have an image S3 URL
            print(f"[Pipeline] Using model prompt: '{prompt_to_use}' and image S3 URL: '{temp_image_s3_url_for_3d}' for 3D generation.")
            # Ensure call_threed_generation_service expects a URL (image_s3_key parameter name might be misleading now)
            model_bytes = call_threed_generation_service(prompt_to_use, image_input_url=temp_image_s3_url_for_3d)
        else:
            # If intermediate image generation/upload/URL generation failed, we cannot proceed.
            threed_img_missing_err = "Cannot call 3D generation: intermediate image S3 URL is missing or failed to generate/upload."
            error_message = (error_message + " | " if error_message else "") + threed_img_missing_err
            print(f"[Pipeline] {threed_img_missing_err}")
            # model_bytes remains None

        if model_bytes:
            model_s3_key = f"{S3_MODEL_FOLDER}{asset_id}.glb"
            try:
                upload_file_obj_to_s3(model_bytes, model_s3_key, content_type='model/gltf-binary')
                print(f"[Pipeline] Successfully uploaded 3D model to {model_s3_key}")
                full_json_data["model_s3_key"] = model_s3_key
            except Exception as e:
                model_upload_error = f"3D Model S3 upload error: {e}"
                error_message = (error_message + " | " if error_message else "") + model_upload_error
                print(f"[Pipeline] {model_upload_error}")
                model_s3_key = None # Upload failed
        elif not temp_image_s3_url_for_3d: 
            # Error about missing intermediate image already handled and logged
            pass 
        else: # temp_image_s3_url_for_3d was present, but model_bytes is still None
            threed_gen_error = "3D Generation service failed to generate model (even with an intermediate image)."
            error_message = (error_message + " | " if error_message else "") + threed_gen_error
            print(f"[Pipeline] {threed_gen_error}")
    else:
        unknown_type_err = f"Unknown output type selected: {output_type}"
        error_message = (error_message + " | " if error_message else "") + unknown_type_err
        print(f"[Pipeline] {unknown_type_err}")

    # 4. Prepare and Upload JSON metadata (always done, includes appropriate keys)
    print(f"[Pipeline] Preparing JSON metadata for upload. Current data: {full_json_data}")
    json_string_to_upload = json.dumps(full_json_data, indent=4)
    json_s3_key = f"{S3_JSON_FOLDER}{asset_id}.json"
    try:
        upload_file_obj_to_s3(json_string_to_upload.encode('utf-8'), json_s3_key, content_type='application/json')
        print(f"[Pipeline] Successfully uploaded JSON metadata to {json_s3_key}")
    except Exception as e:
        json_upload_error = f"JSON S3 upload error: {e}"
        error_message = (error_message + " | " if error_message else "") + json_upload_error
        print(f"[Pipeline] {json_upload_error}")
        # If JSON upload fails, this is critical. We return None for json_string to indicate this.
        return None, image_s3_key, model_s3_key, error_message 

    return json_string_to_upload, image_s3_key, model_s3_key, error_message
