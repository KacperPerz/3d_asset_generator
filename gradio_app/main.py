# gradio_app/main.py
import gradio as gr
import requests
import os
import json
import time

from core_logic.pipeline import generate_asset_pipeline
from core_logic.s3_utils import (
    S3_CLIENT_INITIALIZED, 
    get_s3_client, 
    get_presigned_url,
    list_s3_image_keys,
    list_s3_json_keys,    # New import
    get_s3_json_content   # New import
)
from core_logic.config import LLM_SERVICE_URL, S3_BUCKET_NAME # New import for S3_BUCKET_NAME


def s3_status_check():
    # S3_CLIENT_INITIALIZED is imported from core_logic.s3_utils
    if S3_CLIENT_INITIALIZED:
        try:
            client = get_s3_client() # Imported from core_logic.s3_utils
            if client:
                client.list_buckets() # A simple operation to check credentials and connectivity
                return "<p style='color:green;font-weight:bold;'>S3 Client Initialized and Connected Successfully (via s3_utils).</p>"
            else: # Should not happen if S3_CLIENT_INITIALIZED is true, but good to check
                return "<p style='color:orange;font-weight:bold;'>S3 Client reported as initialized by s3_utils, but get_s3_client() returned None.</p>"
        except Exception as e:
            return f"<p style='color:orange;font-weight:bold;'>S3 Client Initialized (via s3_utils) but Connection Test Failed: {str(e)}</p><p>Please check AWS credentials, region, and bucket name in your .env file and S3 bucket CORS/Permissions.</p>"
    else:
        return "<p style='color:red;font-weight:bold;'>S3 Client FAILED to Initialize (via s3_utils).</p><p>Uploads to S3 will be skipped. Please check AWS environment variables (loaded by core_logic.config) and boto3 installation.</p>"

def llm_service_status_check():
    if LLM_SERVICE_URL:
        return f"<p style='color:green;font-weight:bold;'>LLM Service URL Configured:</p><p>{LLM_SERVICE_URL}</p>"
    else:
        return "<p style='color:red;font-weight:bold;'>LLM_SERVICE_URL is NOT configured.</p><p>The application will not be able to contact the LLM service.</p>"

def ui_process_request(prompt_text):
    if not prompt_text:
        # Ensure this matches the number of outputs for the "Generate Asset" tab
        return None, None, "Please enter a prompt." # JSON output, Image, Status

    print(f"Received prompt: {prompt_text}")
    
    final_json_str, image_s3_key, error_msg = generate_asset_pipeline(prompt_text)

    status_update = "Processing complete."
    image_url_for_display = None

    if error_msg:
        status_update = f"Error: {error_msg}"
        return None, None, status_update # JSON output, Image, Status

    if image_s3_key:
        image_url_for_display = get_presigned_url(object_key=image_s3_key, bucket_name_override=S3_BUCKET_NAME)
        if image_url_for_display:
            status_update += f" Image available. S3 key: {image_s3_key}."
        else:
            status_update += f" Image S3 key: {image_s3_key}, but failed to generate presigned URL."
    else:
        status_update += " No image was generated or uploaded."

    # Return values should match the Gradio outputs order for the "Generate Asset" tab
    return final_json_str, image_url_for_display, status_update # JSON, Image, Status

# --- Handler for S3 Image Viewer ---
def populate_s3_image_dropdown():
    """Lists image keys from S3 and updates the dropdown choices."""
    if not S3_CLIENT_INITIALIZED:
        gr.Warning("S3 client not initialized. Cannot list images.")
        return gr.Dropdown(choices=[], value=None) # Update Dropdown with empty choices
    
    image_keys = list_s3_image_keys(bucket_name_param=S3_BUCKET_NAME, prefix="images/") # Use S3_BUCKET_NAME from config
    if not image_keys:
        gr.Info("No images found in S3 under 'images/' prefix or error listing.")
        return gr.Dropdown(choices=[], value=None)
    
    return gr.Dropdown(choices=image_keys, value=image_keys[0] if image_keys else None)

def load_s3_image_to_viewer(selected_s3_key):
    """Loads the selected S3 image into the image viewer using a presigned URL."""
    if not selected_s3_key:
        return None # Return None if no key is selected, clearing the image viewer
    if not S3_CLIENT_INITIALIZED:
        gr.Warning("S3 client not initialized. Cannot fetch image.")
        return None

    # Use S3_BUCKET_NAME from config for generating presigned URL
    presigned_image_url = get_presigned_url(object_key=selected_s3_key, bucket_name_override=S3_BUCKET_NAME)
    if presigned_image_url:
        return presigned_image_url
    else:
        gr.Error(f"Failed to generate presigned URL for {selected_s3_key}.")
        return None

# --- Handlers for S3 JSON Metadata Viewer ---
def populate_s3_json_dropdown():
    """Lists JSON metadata keys from S3 and updates the dropdown choices."""
    if not S3_CLIENT_INITIALIZED:
        gr.Warning("S3 client not initialized. Cannot list JSON metadata.")
        return gr.Dropdown(choices=[], value=None)
    
    json_keys = list_s3_json_keys(bucket_name_param=S3_BUCKET_NAME, prefix="metadata/") # Use S3_BUCKET_NAME from config
    if not json_keys:
        gr.Info("No JSON metadata found in S3 under 'metadata/' prefix or error listing.")
        return gr.Dropdown(choices=[], value=None)
    
    return gr.Dropdown(choices=json_keys, value=json_keys[0] if json_keys else None)

def load_s3_json_and_linked_image_to_viewer(selected_s3_json_key):
    """Loads the selected S3 JSON metadata, displays its content,
       and attempts to load and display its linked image if specified within the JSON."""
    if not selected_s3_json_key:
        return "", None # JSON content, Image URL
    
    if not S3_CLIENT_INITIALIZED:
        gr.Warning("S3 client not initialized. Cannot fetch JSON metadata or linked image.")
        return "Error: S3 client not initialized.", None

    # Fetch JSON content
    json_content_str = get_s3_json_content(object_key=selected_s3_json_key, bucket_name_param=S3_BUCKET_NAME)
    
    linked_image_url = None
    display_json_str = ""

    if json_content_str is not None:
        try:
            parsed_json = json.loads(json_content_str)
            display_json_str = json.dumps(parsed_json, indent=2)
            
            # Look for the linked image S3 key within the JSON metadata
            linked_image_s3_key = parsed_json.get('image_s3_key')
            if linked_image_s3_key:
                gr.Info(f"Found linked image key in metadata: {linked_image_s3_key}")
                linked_image_url = get_presigned_url(object_key=linked_image_s3_key, bucket_name_override=S3_BUCKET_NAME)
                if not linked_image_url:
                    gr.Warning(f"Could not generate presigned URL for linked image: {linked_image_s3_key}")
            else:
                gr.Info("No 'image_s3_key' found in the selected JSON metadata.")
        except json.JSONDecodeError:
            gr.Warning(f"Content for {selected_s3_json_key} is not valid JSON. Displaying raw content.")
            display_json_str = json_content_str # Display raw content
    else:
        gr.Error(f"Failed to fetch content for {selected_s3_json_key}.")
        display_json_str = f"Error: Could not load content for {selected_s3_json_key}."
        
    return display_json_str, linked_image_url

# --- Gradio Interface Definition ---
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🖼️ AI Asset Generator & S3 Viewer")
    gr.Markdown("Enter a text description of a game asset. The LLM will expand it into a JSON specification, which will be saved to AWS S3. 3D model generation is currently disabled.")
    
    with gr.Row():
        s3_status_html = gr.HTML(s3_status_check())
        llm_status_html = gr.HTML(llm_service_status_check())

    with gr.Tabs():
        with gr.TabItem("Generate Asset"):
            gr.Markdown("## Generate New Asset")
            gr.Markdown("Enter a text description of an asset. The LLM will expand it into a JSON specification, an image will be generated, and both will be saved to AWS S3.")
            with gr.Row():
                prompt_input = gr.Textbox(label="Asset Description Prompt", placeholder="e.g., futuristic laser sword, ancient magical shield", scale=3)
            
            submit_button = gr.Button("Generate Asset (JSON + Image)")

            gr.Markdown("## Generation Status & Outputs")
            gen_status_output = gr.Textbox(label="Generation Status", lines=3, interactive=False)
            
            with gr.Row():
                gen_json_output = gr.Code(label="Generated JSON Specification", language="json", lines=10, interactive=False)
                gen_image_output = gr.Image(label="Generated Image Preview", type="filepath", height=300)

            submit_button.click(
                fn=ui_process_request,
                inputs=[prompt_input],
                outputs=[gen_json_output, gen_image_output, gen_status_output]
            )

        with gr.TabItem("View S3 Images"):
            gr.Markdown("## View Existing Images from S3")
            refresh_s3_images_button = gr.Button("Refresh Image List from S3")
            
            s3_image_key_dropdown = gr.Dropdown(
                label="Select S3 Image Key", 
                choices=[], 
                interactive=True
            )
            s3_image_viewer = gr.Image(label="S3 Image Viewer", type="filepath", height=400)

            refresh_s3_images_button.click(
                fn=populate_s3_image_dropdown,
                inputs=None,
                outputs=[s3_image_key_dropdown]
            )
            s3_image_key_dropdown.change(
                fn=load_s3_image_to_viewer,
                inputs=[s3_image_key_dropdown],
                outputs=[s3_image_viewer]
            )

        with gr.TabItem("View S3 Metadata"):
            gr.Markdown("## View Existing JSON Metadata & Linked Image from S3")
            refresh_s3_json_button = gr.Button("Refresh Metadata List from S3")
            
            s3_json_key_dropdown = gr.Dropdown(
                label="Select S3 JSON Key", 
                choices=[], 
                interactive=True
            )
            with gr.Row():
                s3_json_viewer = gr.Code(label="S3 JSON Content Viewer", language="json", lines=20, interactive=False, scale=1)
                s3_metadata_linked_image_viewer = gr.Image(label="Linked Image from Metadata", type="filepath", height=400, scale=1)

            refresh_s3_json_button.click(
                fn=populate_s3_json_dropdown,
                inputs=None,
                outputs=[s3_json_key_dropdown]
            )
            s3_json_key_dropdown.change(
                fn=load_s3_json_and_linked_image_to_viewer,
                inputs=[s3_json_key_dropdown],
                outputs=[s3_json_viewer, s3_metadata_linked_image_viewer]
            )
    
    # Initial population of dropdowns when the app loads
    def initial_load():
        # Returns a tuple of updates for the dropdowns
        # Errors/warnings will be handled by gr.Warning/Info within the functions themselves
        image_dd_update = populate_s3_image_dropdown()
        json_dd_update = populate_s3_json_dropdown()
        return image_dd_update, json_dd_update

    demo.load(initial_load, None, [s3_image_key_dropdown, s3_json_key_dropdown])


if __name__ == "__main__":
    print("Attempting to launch Gradio demo from main.py (with linked image in metadata viewer)...")
    demo.launch(server_name="0.0.0.0", server_port=7860, debug=True) 