# gradio_app/core_logic/config.py
import os

# LLM Service Configuration
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://localhost:8000")

# Text-to-Image Service Configuration
TEXT_TO_IMAGE_SERVICE_URL = os.getenv("TEXT_TO_IMAGE_SERVICE_URL", "http://localhost:8001")

# 3D Generation Service Configuration
THREED_GENERATION_SERVICE_URL = os.getenv("THREED_GENERATION_SERVICE_URL", "http://localhost:8002")

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# Default folder for JSON metadata in S3
S3_JSON_FOLDER = "metadata/"
S3_IMAGE_FOLDER = "images/"
S3_MODEL_FOLDER = "models/" # New folder for 3D models

# Simple check for essential S3 config
if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION, S3_BUCKET_NAME]):
    print("Warning: One or more AWS S3 environment variables are not set.")

if not LLM_SERVICE_URL:
    print("Warning: LLM_SERVICE_URL environment variable is not set.") 