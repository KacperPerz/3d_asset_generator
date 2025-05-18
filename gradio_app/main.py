# gradio_app/main.py
import gradio as gr
import json

from core_logic.pipeline import process_request_and_upload
from core_logic.s3_utils import (
    S3_CLIENT_INITIALIZED, 
    get_s3_client, 
    get_presigned_url,
    get_s3_json_content,
    list_json_metadata_with_prompts,
    list_images_with_prompts_from_metadata,
    list_s3_json_keys,
    list_s3_image_keys,
    list_s3_model_keys,
    list_models_with_prompts_from_metadata
)
from core_logic.config import LLM_SERVICE_URL, S3_BUCKET_NAME, S3_JSON_FOLDER, S3_IMAGE_FOLDER, S3_MODEL_FOLDER


def s3_status_check():
    if S3_CLIENT_INITIALIZED:
        try:
            client = get_s3_client() 
            if client:
                # client.list_buckets() # Removed to avoid needing ListBuckets permission for basic check
                # A less permission-heavy check could be to try and get bucket location if needed
                # For now, S3_CLIENT_INITIALIZED implies client object was created.
                return "<p style='color:green;font-weight:bold;'>S3 Client Initialized (via s3_utils).</p>"
            else: 
                return "<p style='color:orange;font-weight:bold;'>S3 Client reported as initialized by s3_utils, but get_s3_client() returned None.</p>"
        except Exception as e:
            return f"<p style='color:orange;font-weight:bold;'>S3 Client Initialized (via s3_utils) but Post-Init Check Failed: {str(e)}</p><p>Please check AWS credentials, region, and S3 bucket CORS/Permissions if presigned URLs or uploads fail.</p>"
    else:
        return "<p style='color:red;font-weight:bold;'>S3 Client FAILED to Initialize (via s3_utils).</p><p>Uploads to S3 will be skipped. Please check AWS environment variables and boto3 installation.</p>"

def llm_service_status_check():
    if LLM_SERVICE_URL:
        return f"<p style='color:green;font-weight:bold;'>LLM Service URL Configured:</p><p>{LLM_SERVICE_URL}</p>"
    else:
        return "<p style='color:red;font-weight:bold;'>LLM_SERVICE_URL is NOT configured.</p><p>The application will not be able to contact the LLM service.</p>"

def get_model_url_for_display(s3_key: str):
    if not s3_key:
        return None
    url = get_presigned_url(s3_key)
    print(f"Generated presigned URL for 3D model {s3_key}: {url}")
    return url

# --- Main UI Process Function --- 
def ui_process_request(text_prompt: str, output_type: str):
    if not text_prompt:
        return "{}", None, None, gr.Button(visible=False), gr.Button(visible=False), "Input prompt is empty."
    if not output_type:
        return "{}", None, None, gr.Button(visible=False), gr.Button(visible=False), "Please select an output type (Image or 3D Model)."
    
    print(f"Processing with prompt: '{text_prompt}', Output type: {output_type}")
    json_string, image_s3_key, model_s3_key, error_message = process_request_and_upload(text_prompt, output_type)

    output_json = None
    output_image_url = None
    output_model_data = None
    download_image_button_visibility = gr.Button(visible=False)
    download_model_button_visibility = gr.Button(visible=False)
    status_text = error_message # This is the error message from process_request_and_upload

    if json_string:
        output_json = json_string
    elif error_message: # Error from process_request_and_upload
        output_json = json.dumps({"error": error_message, "details": "Processing error occurred in pipeline"}, indent=2)
    else: # No JSON and no error from process_request_and_upload
        output_json = json.dumps({"status": "Processing complete. No JSON content from pipeline and no errors reported by pipeline."}, indent=2)
        if not status_text: status_text = "Processing complete. No JSON/error from pipeline."

    if image_s3_key and output_type == "Image":
        print(f"Image S3 key: {image_s3_key}")
        output_image_url = get_presigned_url(image_s3_key)
        if output_image_url:
            download_image_button_visibility = gr.Button(value="Download Image", link=output_image_url, visible=True, interactive=True)
        else:
            no_url_err = f"Failed to get presigned URL for image {image_s3_key}."
            status_text = (status_text + " | " if status_text else "") + no_url_err
            print(no_url_err)
            if output_json and isinstance(output_json, str):
                try:
                    data = json.loads(output_json)
                    data["image_error"] = no_url_err
                    output_json = json.dumps(data, indent=2)
                except json.JSONDecodeError: pass # Ignore if output_json isn't valid JSON already
                except Exception: pass

    if model_s3_key and output_type == "3D Model":
        print(f"Model S3 key: {model_s3_key}")
        model_presigned_url = get_model_url_for_display(model_s3_key)
        if model_presigned_url:
            output_model_data = model_presigned_url
            download_model_button_visibility = gr.Button(value="Download Model (.glb)", link=model_presigned_url, visible=True, interactive=True)
        else:
            no_model_url_err = f"Failed to get presigned URL for model {model_s3_key}."
            status_text = (status_text + " | " if status_text else "") + no_model_url_err
            print(no_model_url_err)
            if output_json and isinstance(output_json, str):
                try:
                    data = json.loads(output_json)
                    data["model_error"] = no_model_url_err
                    output_json = json.dumps(data, indent=2)
                except json.JSONDecodeError: pass
                except Exception: pass

    final_status = status_text if status_text else "Processing complete."

    if output_json is None:
        output_json = "{}" # Ensure JSON output is never None

    if output_type == "Image":
        output_model_data = None # Clear model output if image was generated
    elif output_type == "3D Model":
        output_image_url = None # Clear image output if model was generated

    return output_json, output_image_url, output_model_data, download_image_button_visibility, download_model_button_visibility, final_status

# --- S3 Browser Functions --- 
def populate_s3_json_dropdown():
    try:
        choices = list_json_metadata_with_prompts()
        print(f"[populate_s3_json_dropdown] Choices from S3: {choices}")
        if not choices:
            return gr.Dropdown(choices=["No JSON files found"], value=None, interactive=False, label="Select JSON by User Prompt")
        return gr.Dropdown(choices=choices, value=choices[0][1] if choices else None, label="Select JSON by User Prompt", interactive=True)
    except Exception as e:
        print(f"Error populating S3 JSON dropdown: {e}")
        return gr.Dropdown(choices=["Error loading JSONs"], value=None, interactive=False, label="Select JSON by User Prompt")

def load_s3_json_and_linked_image_to_viewer(selected_json_s3_key: str):
    print(f"[load_s3_json_and_linked_image_to_viewer] Selected S3 Key: {selected_json_s3_key}")
    linked_image_url = None
    linked_model_url = None

    if not selected_json_s3_key or selected_json_s3_key == "No JSON files found" or selected_json_s3_key == "Error loading JSONs":
        error_message = "Please select a valid JSON file from the dropdown."
        if selected_json_s3_key == "Error loading JSONs":
            error_message = "Failed to load JSON list. Please refresh."
        return json.dumps({"error": error_message, "details": selected_json_s3_key}, indent=2), None, None
    
    json_content_dict = get_s3_json_content(selected_json_s3_key) 
    
    if json_content_dict is None:
        error_message = f"Error loading JSON content from S3 for key: {selected_json_s3_key}."
        print(error_message)
        return json.dumps({"error": error_message, "s3_key": selected_json_s3_key}, indent=2), None, None

    json_display_string = json.dumps(json_content_dict, indent=2)
    
    # Try to get the specific intermediate image key first, then fall back to the general image key
    image_s3_key_to_load = json_content_dict.get("intermediate_image_s3_key")
    if not image_s3_key_to_load:
        image_s3_key_to_load = json_content_dict.get("image_s3_key")

    if image_s3_key_to_load:
        linked_image_url = get_presigned_url(image_s3_key_to_load)
        if not linked_image_url:
            print(f"Could not get presigned URL for linked image: {image_s3_key_to_load}")
            # Modify the dict directly to add warning, then re-dump for display
            warning_dict = json.loads(json_display_string) 
            warning_dict["_viewer_warning_image_url"] = f"Failed to get presigned URL for {image_s3_key_to_load}"
            json_display_string = json.dumps(warning_dict, indent=2)

    model_s3_key_from_json = json_content_dict.get("model_s3_key")
    if model_s3_key_from_json:
        linked_model_url = get_model_url_for_display(model_s3_key_from_json)
        if not linked_model_url:
            print(f"Could not get presigned URL for linked model: {model_s3_key_from_json}")
            warning_dict = json.loads(json_display_string)
            warning_dict["_viewer_warning_model_url"] = f"Failed to get presigned URL for {model_s3_key_from_json}"
            json_display_string = json.dumps(warning_dict, indent=2)
            
    return json_display_string, linked_image_url, linked_model_url

def populate_s3_image_dropdown():
    try:
        choices = list_images_with_prompts_from_metadata() 
        print(f"[populate_s3_image_dropdown] Choices from S3: {choices}")
        if not choices:
            return gr.Dropdown(choices=["No images found"], value=None, interactive=False, label="Select Image by User Prompt")
        dropdown_choices = [(f"{prompt} (Image: {key.split('/')[-1]})", key) for prompt, key in choices]
        return gr.Dropdown(choices=dropdown_choices, value=dropdown_choices[0][1] if dropdown_choices else None, label="Select Image by User Prompt", interactive=True)
    except Exception as e:
        print(f"Error populating S3 Image dropdown: {e}")
        return gr.Dropdown(choices=["Error loading images"], value=None, interactive=False, label="Select Image by User Prompt")

def load_s3_image_to_viewer(selected_image_s3_key: str):
    print(f"[load_s3_image_to_viewer] Selected S3 Key: {selected_image_s3_key}")
    if not selected_image_s3_key or selected_image_s3_key == "No images found" or selected_image_s3_key == "Error loading images":
        return None
    image_url = get_presigned_url(selected_image_s3_key)
    if not image_url:
        print(f"Could not get presigned URL for: {selected_image_s3_key}")
    return image_url

def populate_s3_model_dropdown():
    try:
        choices = list_models_with_prompts_from_metadata() 
        print(f"[populate_s3_model_dropdown] Choices from S3: {choices}") 
        if not choices:
            return gr.Dropdown(choices=["No 3D models found"], value=None, interactive=False, label="Select 3D Model by User Prompt")
        dropdown_choices = [(f"{prompt} (Model: {key.split('/')[-1]})", key) for prompt, key in choices]
        return gr.Dropdown(choices=dropdown_choices, value=dropdown_choices[0][1] if dropdown_choices else None, label="Select 3D Model by User Prompt", interactive=True)
    except Exception as e:
        print(f"Error populating S3 Model dropdown: {e}")
        return gr.Dropdown(choices=["Error loading 3D models"], value=None, interactive=False, label="Select 3D Model by User Prompt")

def load_s3_model_to_viewer(selected_model_s3_key: str):
    print(f"[load_s3_model_to_viewer] Selected S3 Key: {selected_model_s3_key}") 
    source_image_url = None
    model_url = None

    if not selected_model_s3_key or selected_model_s3_key == "No 3D models found"\
        or selected_model_s3_key == "Error loading 3D models":
        return None, None # Return None for both model and image

    # Attempt to get the model URL first
    model_url = get_model_url_for_display(selected_model_s3_key)
    if not model_url:
        print(f"[load_s3_model_to_viewer] Could not get presigned URL for 3D model: {selected_model_s3_key}")
        # model_url is already None, will proceed to find source image

    # Try to find the source image from metadata, regardless of model_url success
    try:
        all_json_s3_keys = list_s3_json_keys()
        found_source_image_key = None
        for json_s3_key in all_json_s3_keys:
            json_content = get_s3_json_content(json_s3_key)
            if json_content and json_content.get("model_s3_key") == selected_model_s3_key:
                found_source_image_key = json_content.get("intermediate_image_s3_key") # Corrected key name
                if found_source_image_key:
                    print(f"[load_s3_model_to_viewer] Found source image key '{found_source_image_key}'\
                           in metadata '{json_s3_key}' for model '{selected_model_s3_key}'")
                    break # Found the image key
                else:
                    print(f"[load_s3_model_to_viewer] Metadata '{json_s3_key}' linked to model\
                           '{selected_model_s3_key}' but contains no 'intermediate_image_s3_key' field.")
            
        if found_source_image_key:
            source_image_url = get_presigned_url(found_source_image_key)
            if not source_image_url:
                print(f"[load_s3_model_to_viewer] Could not get presigned URL for source image: {found_source_image_key}")
        else:
            print(f"[load_s3_model_to_viewer] No source image key found in any metadata for model: {selected_model_s3_key}")
    except Exception as e:
        print(f"[load_s3_model_to_viewer] Error while trying to find source image for model '{selected_model_s3_key}': {e}")

    return model_url, source_image_url

# --- Function to update visibility of output previews --- 
def update_output_visibility(output_choice: str):
    if output_choice == "Image":
        return {
            gen_image_output: gr.Image(visible=True),
            gen_image_download_button: gr.Button(visible=False), # Visibility handled by ui_process_request based on actual file
            gen_model_output: gr.Model3D(visible=False, value=None), # Hide and clear model output
            gen_model_download_button: gr.Button(visible=False)
        }
    elif output_choice == "3D Model":
        return {
            gen_image_output: gr.Image(visible=False, value=None), # Hide and clear image output
            gen_image_download_button: gr.Button(visible=False),
            gen_model_output: gr.Model3D(visible=True),
            gen_model_download_button: gr.Button(visible=False) # Visibility handled by ui_process_request
        }
    return {} # Should not happen

# --- Gradio Interface Definition ---
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🖼️ AI Asset Generator & S3 Viewer")
    
    with gr.Row():
        s3_status_html = gr.HTML(s3_status_check())
        llm_status_html = gr.HTML(llm_service_status_check())
    

    with gr.Tabs():
        with gr.TabItem("Generate Asset"):
            gr.Markdown("## Generate New Asset")
            with gr.Row():
                prompt_input = gr.Textbox(label="Asset Description Prompt",\
                                           placeholder="e.g., futuristic laser sword", scale=3)
            
            output_type_radio = gr.Radio(
                choices=["Image", "3D Model"], 
                label="Select Output Type", 
                value="Image" 
            )
            
            submit_button = gr.Button("Generate Asset")

            gr.Markdown("## Generation Status & Outputs")
            gen_status_output = gr.Textbox(label="Generation Status", lines=1, interactive=False) 
            
            with gr.Row():
                gen_json_output = gr.JSON(label="Generated JSON Specification")
            with gr.Row(): 
                with gr.Column() as image_output_col: # Assign to variable for easier reference if needed
                    gen_image_output = gr.Image(label="Generated Image Preview", type="filepath",\
                                                 interactive=False, visible=True) # Visible by default
                    gen_image_download_button = gr.Button("Download Image", visible=False)
                with gr.Column() as model_output_col: # Assign to variable
                    gen_model_output = gr.Model3D(label="Generated 3D Model Preview",\
                                                   interactive=False, visible=False) # Hidden by default
                    gen_model_download_button = gr.Button("Download Model (.glb)", visible=False)
            
            # Event handler for radio button change
            output_type_radio.change(
                fn=update_output_visibility,
                inputs=[output_type_radio],
                outputs=[
                    gen_image_output, 
                    gen_image_download_button, 
                    gen_model_output, 
                    gen_model_download_button
                ]
            )

            submit_button.click(
                fn=ui_process_request,
                inputs=[prompt_input, output_type_radio], 
                outputs=[
                    gen_json_output, 
                    gen_image_output, 
                    gen_model_output, 
                    gen_image_download_button, 
                    gen_model_download_button, 
                    gen_status_output
                ]
            )

        with gr.TabItem("View S3 Images"):
            gr.Markdown("## View Existing Images from S3")
            refresh_s3_images_button = gr.Button("Refresh Image List from S3")
            s3_image_key_dropdown = gr.Dropdown(label="Select Image by User Prompt", choices=[], interactive=True)
            s3_image_viewer = gr.Image(label="S3 Image Viewer", type="filepath", height=400)
            refresh_s3_images_button.click(fn=populate_s3_image_dropdown,outputs=[s3_image_key_dropdown])
            s3_image_key_dropdown.change(fn=load_s3_image_to_viewer,inputs=[s3_image_key_dropdown],outputs=[s3_image_viewer])

        with gr.TabItem("View 3D Models"):
            gr.Markdown("## View Existing 3D Models from S3")
            refresh_s3_models_button = gr.Button("Refresh Model List from S3")
            s3_model_key_dropdown = gr.Dropdown(label="Select 3D Model by User Prompt", choices=[], interactive=True)
            with gr.Row():
                s3_model_viewer = gr.Model3D(label="S3 Model Viewer", interactive=False, scale=2)
                s3_model_source_image_viewer = gr.Image(label="Source Image for Model", type="filepath", interactive=False, scale=1)
            refresh_s3_models_button.click(fn=populate_s3_model_dropdown, outputs=[s3_model_key_dropdown])
            s3_model_key_dropdown.change(fn=load_s3_model_to_viewer,inputs=[s3_model_key_dropdown],\
                                         outputs=[s3_model_viewer, s3_model_source_image_viewer]) # Update outputs

        with gr.TabItem("View S3 Metadata"):
          gr.Markdown("## View Existing JSON Metadata & Linked Assets from S3")
          refresh_s3_json_button = gr.Button("Refresh Metadata List from S3")
          s3_json_key_dropdown = gr.Dropdown(label="Select JSON by User Prompt", choices=[], interactive=True)
          with gr.Row():
              s3_json_viewer = gr.JSON(label="S3 JSON Content Viewer")
              with gr.Column(): 
                  s3_metadata_linked_image_viewer = gr.Image(label="Linked Image from Metadata", type="filepath", interactive=False)
                  s3_metadata_linked_model_viewer = gr.Model3D(label="Linked 3D Model from Metadata", interactive=False)
          refresh_s3_json_button.click(fn=populate_s3_json_dropdown, outputs=[s3_json_key_dropdown])
          s3_json_key_dropdown.change(fn=load_s3_json_and_linked_image_to_viewer,inputs=[s3_json_key_dropdown],\
                                      outputs=[s3_json_viewer, s3_metadata_linked_image_viewer, s3_metadata_linked_model_viewer])

    
    def initial_load():
        print("[initial_load] Populating dropdowns...")
        image_dd_update = populate_s3_image_dropdown()
        json_dd_update = populate_s3_json_dropdown()
        model_dd_update = populate_s3_model_dropdown()
        print(f"[initial_load] Image Dropdown Update: {image_dd_update}")
        print(f"[initial_load] JSON Dropdown Update: {json_dd_update}")
        print(f"[initial_load] Model Dropdown Update: {model_dd_update}")
        # Also set initial visibility based on default radio choice ("Image")
        initial_visibility_updates = update_output_visibility("Image")

        return image_dd_update, json_dd_update, model_dd_update 

    demo.load(initial_load, None, [s3_image_key_dropdown, s3_json_key_dropdown, s3_model_key_dropdown])

if __name__ == "__main__":
    print("Attempting to launch Gradio demo...")
    demo.launch(server_name="0.0.0.0", server_port=7860, debug=True) 