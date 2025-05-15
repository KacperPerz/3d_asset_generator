# gradio_app/core_logic/config.py
import os

# S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# Service URLs
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://localhost:5001") # Default for local dev
# THREED_GENERATION_SERVICE_URL = os.getenv("THREED_GENERATION_SERVICE_URL", "http://localhost:5002") # Removed

# Simple check for essential S3 config
if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION, S3_BUCKET_NAME]):
    print("Warning: One or more AWS S3 environment variables are not set.")

if not LLM_SERVICE_URL:
    print("Warning: LLM_SERVICE_URL environment variable is not set.") 