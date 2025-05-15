# gradio_app/main.py
import gradio as gr
import requests
import os
import json
import time

from core_logic.pipeline import generate_asset_pipeline
from core_logic.s3_utils import S3_CLIENT_INITIALIZED, get_s3_client # For checking S3 status
from core_logic.config import LLM_SERVICE_URL # To display which LLM service is being used

def call_llm_service(user_prompt_text):
    service_endpoint = f"{LLM_SERVICE_URL}/expand-prompt/"
    payload = {"prompt": user_prompt_text}
    print(f"Calling LLM service at {service_endpoint} with payload: {payload}")
    try:
        response = requests.post(service_endpoint, json=payload, timeout=60)
        response.raise_for_status() # Raise an HTTPError for bad responses (4XX or 5XX)
        print(f"LLM service responded with: {response.status_code}")
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        error_detail = "Unknown error from LLM service."
        try:
            error_detail = http_err.response.json().get("detail", error_detail)
        except json.JSONDecodeError:
            error_detail = http_err.response.text if http_err.response.text else error_detail
        print(f"HTTP error calling LLM service: {http_err} - Detail: {error_detail}")
        raise gr.Error(f"LLM service error: {error_detail}")
    except requests.exceptions.RequestException as req_err:
        print(f"Request error calling LLM service: {req_err}")
        raise gr.Error(f"Could not connect to LLM service: {req_err}")

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
    if not prompt_text.strip():
        return "Please enter a prompt.", None # Status, JSON output

    # The pipeline now returns (json_data, status_string)
    json_data, status_string = generate_asset_pipeline(prompt_text)
    
    json_string_output = ""
    if json_data:
        try:
            json_string_output = json.dumps(json_data, indent=2)
        except Exception as e:
            status_string += f"\nError formatting JSON for display: {str(e)}"
            json_string_output = f"Error displaying JSON: {str(e)}"
    elif not status_string: # If json_data is None and status is also empty
        status_string = "Pipeline returned no data and no specific error message."

    return status_string, json_string_output

# --- Gradio Interface Definition ---
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🖼️ AI 3D Asset Generator Lite (S3 + LLM Only)")
    gr.Markdown("Enter a text description of a game asset. The LLM will expand it into a JSON specification, which will be saved to AWS S3. 3D model generation is currently disabled.")
    
    with gr.Row():
        s3_status_html = gr.HTML(s3_status_check())
        llm_status_html = gr.HTML(llm_service_status_check())
        
    with gr.Row():
        prompt_input = gr.Textbox(label="Asset Description Prompt", placeholder="e.g., futuristic laser sword, ancient magical shield")
    
    submit_button = gr.Button("Generate Asset Specification")

    gr.Markdown("## Generation Status & Logs")
    status_output = gr.Textbox(label="Status", lines=5, interactive=False)
    
    gr.Markdown("## Generated JSON Specification")
    json_output = gr.Code(label="JSON Specification", language="json", lines=10, interactive=False)

    submit_button.click(
        fn=ui_process_request,
        inputs=[prompt_input],
        outputs=[status_output, json_output]
    )

if __name__ == "__main__":
    print("Attempting to launch Gradio demo from main.py (structured)...")
    # Ensure that Python can find the 'core_logic' package.
    # When running with `python main.py` from within `gradio_app`, relative imports should work.
    # When Docker builds, this structure is also fine.
    demo.launch(server_name="0.0.0.0", server_port=7860, debug=True) 