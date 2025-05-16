# gradio_app/core_logic/config.py
import os

# URL for the LLM service
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://llm_service:5001")

# URL for the Text-to-Image service
TEXT_TO_IMAGE_SERVICE_URL = os.getenv("TEXT_TO_IMAGE_SERVICE_URL", "http://text_to_image_service:5003")

# S3 Configuration
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

# Simple check for essential S3 config
if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION, S3_BUCKET_NAME]):
    print("Warning: One or more AWS S3 environment variables are not set.")

if not LLM_SERVICE_URL:
    print("Warning: LLM_SERVICE_URL environment variable is not set.") 