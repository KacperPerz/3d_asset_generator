import boto3

from .config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_DEFAULT_REGION,
    S3_BUCKET_NAME,
)

s3_client = None
S3_CLIENT_INITIALIZED = False

# Directly check if all S3 related environment variables are present
ALL_S3_CONFIG_PRESENT = all([
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_DEFAULT_REGION,
    S3_BUCKET_NAME
])

if ALL_S3_CONFIG_PRESENT:
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_DEFAULT_REGION
        )
        # s3_client.list_buckets() # This would require list permissions, might be too much for init
        S3_CLIENT_INITIALIZED = True
        print("S3 client initialized successfully in s3_utils.")
    except Exception as e:
        print(f"Error initializing S3 client in s3_utils: {e}")
        # s3_client will remain None and S3_CLIENT_INITIALIZED will remain False
else:
    print("S3 client not initialized in s3_utils: Missing one or more AWS S3 environment variables.")

def get_s3_client():
    """Returns the initialized S3 client if available, else None."""
    if S3_CLIENT_INITIALIZED:
        return s3_client
    return None

def upload_to_s3(local_file_path: str, s3_key: str):
    if not S3_CLIENT_INITIALIZED or not s3_client:
        print(f"S3 client not available. Cannot upload {local_file_path}.")
        return None, "S3 client not configured or failed to initialize. Cannot upload file."
    try:
        print(f"Uploading {local_file_path} to S3 bucket {S3_BUCKET_NAME} as {s3_key}")
        s3_client.upload_file(local_file_path, S3_BUCKET_NAME, s3_key)
        s3_url = f"s3://{S3_BUCKET_NAME}/{s3_key}"
        print(f"Upload successful: {s3_url}")
        return s3_url, None
    except Exception as e:
        error_message = f"Error uploading {local_file_path} to S3: {e}"
        print(error_message)
        # Return error status
        return None, error_message

def generate_s3_presigned_url(s3_key: str):
    if not S3_CLIENT_INITIALIZED or not s3_client:
        print(f"S3 client not available. Cannot generate presigned URL for {s3_key}.")
        # Return error status
        return None, "S3 client not configured or failed to initialize. Cannot generate presigned URL."
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=3600  # URL valid for 1 hour
        )
        print(f"Generated presigned URL for {s3_key}: {url}")
        return url, None
    except Exception as e:
        error_message = f"Error generating presigned URL for {s3_key}: {e}"
        print(error_message)
        # Return error status
        return None, error_message 