# gradio_app/core_logic/pipeline.py
import json
import uuid
from .s3_utils import (
    upload_file_obj_to_s3,
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

    asset_id = str(uuid.uuid4()) 

    # 1. Call LLM service (always done)
    print(f"[Pipeline] Calling LLM service for prompt: '{user_prompt}'")
    llm_response_data = call_llm_service(user_prompt)
    if not llm_response_data or llm_response_data.get("error"):
        error_message = f"LLM service error: {llm_response_data.get('details', 'Unknown error')}"
        return None, None, None, error_message # Critical error, stop here
    
    full_json_data = llm_response_data 
    full_json_data["_user_prompt"] = user_prompt
    full_json_data["_selected_output_type"] = output_type # Store the choice in metadata
    
    # 2. Conditional Image Generation
    if output_type == "Image":
        print(f"[Pipeline] Output type is Image. Calling Text-to-Image service.")
        image_prompt = full_json_data.get("expanded_prompt", user_prompt)
        
        image_bytes = call_text_to_image_service(image_prompt)
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
        print(f"[Pipeline] Output type is 3D Model. Calling 3D Generation service.")
        # Using user_prompt directly for 3D model, can be refined if LLM provides specific 3D prompt
        model_prompt = full_json_data.get("model_prompt", user_prompt)

        model_bytes = call_threed_generation_service(model_prompt) # Pass appropriate prompt
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
        else:
            threed_gen_error = "3D Generation service failed to generate model."
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
