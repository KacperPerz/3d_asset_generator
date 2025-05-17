import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError, NoRegionError
import json

from .config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_DEFAULT_REGION,
    S3_BUCKET_NAME,
    S3_JSON_FOLDER,
    S3_IMAGE_FOLDER,
    S3_MODEL_FOLDER
)

# Global S3 client
S3_CLIENT = None
S3_CLIENT_INITIALIZED = False

# Check if all S3 related environment variables (imported from config) are present
# These are resolved when config.py is imported.
ALL_S3_CONFIG_PRESENT_FROM_CONFIG = all([
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_DEFAULT_REGION,
    S3_BUCKET_NAME
])

if ALL_S3_CONFIG_PRESENT_FROM_CONFIG:
    try:
        print(f"Attempting to initialize S3 client. Region: {AWS_DEFAULT_REGION}")
        if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY: # Explicit credentials
            print("Using explicit AWS credentials from environment.")
            S3_CLIENT = boto3.client(
                's3',
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region_name=AWS_DEFAULT_REGION
            )
            S3_CLIENT_INITIALIZED = True
        else: 
            print("Using IAM role or shared AWS credentials file (no explicit keys in env).")
            S3_CLIENT = boto3.client(
                's3',
                region_name=AWS_DEFAULT_REGION
            )
            S3_CLIENT_INITIALIZED = True
        
        print("S3 client object created.")

    except (NoRegionError, NoCredentialsError, PartialCredentialsError) as e:
        print(f"S3 Configuration Error: AWS credentials not found, incomplete, or region issue. {e}")
        S3_CLIENT_INITIALIZED = False
    except ClientError as e:
        print(f"S3 ClientError during initialization or connectivity test: {e}")
        S3_CLIENT_INITIALIZED = False
    except Exception as e:
        print(f"An unexpected error occurred during S3 client initialization: {e}")
        S3_CLIENT_INITIALIZED = False
else:
    missing_configs = []
    if not AWS_ACCESS_KEY_ID: missing_configs.append("AWS_ACCESS_KEY_ID")
    if not AWS_SECRET_ACCESS_KEY: missing_configs.append("AWS_SECRET_ACCESS_KEY")
    if not AWS_DEFAULT_REGION: missing_configs.append("AWS_DEFAULT_REGION")
    if not S3_BUCKET_NAME: missing_configs.append("S3_BUCKET_NAME")
    print(f"S3 client not initialized: Missing S3 config: {', '.join(missing_configs)}.")

def get_s3_client():
    """Returns the initialized S3 client if available, else None."""
    return S3_CLIENT

def check_s3_configuration():
    if not S3_BUCKET_NAME:
        print("S3_BUCKET_NAME is not set. Please configure it in your environment.")
        return False
    client = get_s3_client()
    if not client or not S3_CLIENT_INITIALIZED:
        print("S3 client could not be initialized. Check credentials and region configuration.")
        return False
    return True

def upload_file_obj_to_s3(file_obj_or_bytes, object_key: str, content_type: str = None):
    """
    Uploads a file-like object or bytes to an S3 bucket.
    Args:
        file_obj_or_bytes: Bytes or a file-like object (e.g., io.BytesIO).
        object_key: The key (path and filename) for the object in S3.
        content_type: The MIME type of the file.
    Returns:
        True if upload was successful, False otherwise.
    Raises:
        ValueError if S3_BUCKET_NAME is not set.
        ClientError on S3 API errors.
    """
    if not S3_BUCKET_NAME:
        raise ValueError("S3_BUCKET_NAME is not configured.")
    
    s3_client = get_s3_client()
    if not s3_client:
        print(f"S3 client not available. Cannot upload {object_key}.")
        return False

    extra_args = {}
    if content_type:
        extra_args['ContentType'] = content_type

    try:
        if isinstance(file_obj_or_bytes, bytes):
            import io
            file_obj = io.BytesIO(file_obj_or_bytes)
        else:
            file_obj = file_obj_or_bytes
            file_obj.seek(0) # Ensure read starts from the beginning for file-like objects

        s3_client.upload_fileobj(file_obj, S3_BUCKET_NAME, object_key, ExtraArgs=extra_args)
        print(f"Successfully uploaded {object_key} to bucket {S3_BUCKET_NAME}.")
        return True
    except ClientError as e:
        print(f"ClientError during S3 upload of {object_key}: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error during S3 upload of {object_key}: {e}")
        raise

def get_presigned_url(object_key: str, expiration: int = 3600) -> str | None:
    """Generate a presigned URL to share an S3 object."""
    if not S3_BUCKET_NAME:
        print("Error: S3_BUCKET_NAME is not set. Cannot generate presigned URL.")
        return None
        
    s3_client = get_s3_client()
    if not s3_client:
        print(f"S3 client not available. Cannot get presigned URL for {object_key}.")
        return None
    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': S3_BUCKET_NAME,
                                                            'Key': object_key},
                                                    ExpiresIn=expiration,
                                                    HttpMethod='GET')
    except ClientError as e:
        print(f"Error generating presigned URL for {object_key}: {e}")
        return None
    return response

def list_s3_keys(prefix: str) -> list[str]:
    """Lists keys in S3 bucket with a given prefix."""
    if not check_s3_configuration():
        return []
    s3_client = get_s3_client()
    keys = []
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=prefix):
            if "Contents" in page:
                for item in page["Contents"]:
                    keys.append(item["Key"])
    except ClientError as e:
        print(f"Error listing S3 keys with prefix {prefix}: {e}")
    return keys

def list_s3_json_keys() -> list[str]:
    return list_s3_keys(S3_JSON_FOLDER)

def list_s3_image_keys() -> list[str]:
    return list_s3_keys(S3_IMAGE_FOLDER)

def list_s3_model_keys() -> list[str]:
    """Lists all .glb model keys in the S3_MODEL_FOLDER."""
    return [key for key in list_s3_keys(S3_MODEL_FOLDER) if key.lower().endswith('.glb')]

def get_s3_json_content(object_key: str) -> dict | None:
    """Retrieves and parses JSON content from an S3 object."""
    if not check_s3_configuration():
        return None
    s3_client = get_s3_client()
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=object_key)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except ClientError as e:
        print(f"Error getting S3 JSON content for {object_key}: {e}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {object_key}: {e}")
    return None

def list_json_metadata_with_prompts() -> list[tuple[str, str]]:
    """
    Lists JSON files from S3_JSON_FOLDER and extracts their _user_prompt.
    Returns a list of tuples: (display_string, json_s3_key).
    Display_string is "User Prompt: <prompt> (File: <filename>)" or just filename if prompt missing.
    """
    if not check_s3_configuration():
        return []
    
    json_keys = list_s3_json_keys()
    metadata_with_prompts = []
    for key in json_keys:
        if not key.lower().endswith('.json'):
            continue
        content = get_s3_json_content(key)
        filename = key.split('/')[-1]
        if content and isinstance(content, dict):
            user_prompt = content.get("_user_prompt", "N/A")
            display_name = f"Prompt: {user_prompt} (File: {filename})"
            metadata_with_prompts.append((display_name, key))
        else:
            metadata_with_prompts.append((f"File: {filename} (could not parse prompt)", key))
            
    metadata_with_prompts.sort(key=lambda x: x[1]) 
    return metadata_with_prompts

def list_images_with_prompts_from_metadata() -> list[tuple[str, str]]:
    """
    Fetches all JSON metadata, extracts image_s3_key and _user_prompt.
    Returns a list of tuples: (display_prompt_for_image, image_s3_key).
    """
    if not check_s3_configuration():
        return []

    all_json_metadata = list_json_metadata_with_prompts()
    images_with_prompts = []

    for _, json_key in all_json_metadata:
        content = get_s3_json_content(json_key)
        if content and isinstance(content, dict):
            image_s3_key = content.get("image_s3_key")
            user_prompt = content.get("_user_prompt", "N/A")
            
            if image_s3_key:
                image_filename = image_s3_key.split('/')[-1]
                display_name = f"Prompt: {user_prompt} (Image: {image_filename})"
                images_with_prompts.append((display_name, image_s3_key))
                
    images_with_prompts.sort(key=lambda x: x[1])
    return images_with_prompts

def list_models_with_prompts_from_metadata() -> list[tuple[str, str]]:
    """
    Fetches all JSON metadata, extracts model_s3_key and _user_prompt.
    Returns a list of tuples: (display_prompt_for_model, model_s3_key).
    """
    if not check_s3_configuration():
        return []

    all_json_metadata = list_json_metadata_with_prompts()
    models_with_prompts = []

    for _, json_key in all_json_metadata:
        content = get_s3_json_content(json_key)
        if content and isinstance(content, dict):
            model_s3_key = content.get("model_s3_key")
            user_prompt = content.get("_user_prompt", "N/A")
            
            if model_s3_key:
                model_filename = model_s3_key.split('/')[-1]
                display_name = f"Prompt: {user_prompt} (Model: {model_filename})"
                models_with_prompts.append((display_name, model_s3_key))
                
    models_with_prompts.sort(key=lambda x: x[1])
    return models_with_prompts
