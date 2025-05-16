import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError, NoRegionError

# Use S3 configuration variables imported from config.py
from .config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_DEFAULT_REGION,
    S3_BUCKET_NAME # This is the primary bucket name from config
)

s3_client = None
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
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_DEFAULT_REGION
        )
        S3_CLIENT_INITIALIZED = True
        print("S3 client initialized successfully in s3_utils using variables from config.py.")
    except NoRegionError:
        print(f"S3 client initialization failed in s3_utils: AWS region ('{AWS_DEFAULT_REGION}') not configured correctly or invalid.")
    except (NoCredentialsError, PartialCredentialsError):
        print("S3 client initialization failed in s3_utils: AWS credentials not found or incomplete (via config.py).")
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code in ["InvalidAccessKeyId", "SignatureDoesNotMatch", "AccessDenied"]:
            print(f"S3 client initialization failed in s3_utils: Invalid AWS credentials or permissions ({error_code}) - {e}")
        else:
            print(f"S3 client initialization failed in s3_utils due to ClientError ({error_code}): {e}")
    except Exception as e:
        print(f"S3 client initialization failed in s3_utils with an unexpected error: {e}")
else:
    missing_configs = []
    if not AWS_ACCESS_KEY_ID: missing_configs.append("AWS_ACCESS_KEY_ID")
    if not AWS_SECRET_ACCESS_KEY: missing_configs.append("AWS_SECRET_ACCESS_KEY")
    if not AWS_DEFAULT_REGION: missing_configs.append("AWS_DEFAULT_REGION")
    if not S3_BUCKET_NAME: missing_configs.append("S3_BUCKET_NAME")
    print(f"S3 client not initialized in s3_utils: Missing one or more AWS S3 variables from config.py: {', '.join(missing_configs)}.")

def get_s3_client():
    """Returns the initialized S3 client if available, else None."""
    return s3_client

def upload_file_obj_to_s3(file_obj, target_bucket_name, object_name, content_type=None):
    """Uploads a file-like object to an S3 bucket."""
    if not S3_CLIENT_INITIALIZED or not s3_client:
        return None, "S3 client not initialized. Cannot upload."
    if not target_bucket_name:
        return None, "S3 bucket name not provided for upload."
    
    try:
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type
        
        s3_client.upload_fileobj(file_obj, target_bucket_name, object_name, ExtraArgs=extra_args)
        # Use AWS_DEFAULT_REGION from config.py for URL construction
        s3_url = f"https://{target_bucket_name}.s3.{AWS_DEFAULT_REGION}.amazonaws.com/{object_name}"
        print(f"Successfully uploaded {object_name} to {s3_url}")
        return s3_url, None
    except (NoCredentialsError, PartialCredentialsError, ClientError) as e:
        return None, f"S3 related error during upload: {e}"
    except Exception as e:
        return None, f"Unexpected error during S3 file object upload: {e}"

def get_presigned_url(object_key, bucket_name_override=None, expiration=3600):
    """Generate a presigned URL to share an S3 object.
       Uses S3_BUCKET_NAME from config.py by default, can be overridden by bucket_name_override.
    """
    if not S3_CLIENT_INITIALIZED or not s3_client:
        print("S3 client not initialized. Cannot generate presigned URL.")
        return None
    
    # Use bucket_name_override if provided, otherwise default to S3_BUCKET_NAME from config.py
    effective_bucket_name = bucket_name_override if bucket_name_override else S3_BUCKET_NAME
    if not effective_bucket_name:
        print("Target bucket name not provided or configured. Cannot generate presigned URL.")
        return None

    try:
        response = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': effective_bucket_name, 'Key': object_key},
            ExpiresIn=expiration
        )
        return response
    except (NoCredentialsError, PartialCredentialsError, ClientError) as e:
        print(f"S3 related error generating presigned URL: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error generating presigned URL: {e}")
        return None

def list_s3_image_keys(bucket_name_param=None, prefix="images/"):
    """Lists image object keys from an S3 bucket under a given prefix.

    Args:
        bucket_name_param: The specific bucket to list from. Defaults to S3_BUCKET_NAME from config.
        prefix: The prefix under which to look for images (e.g., "images/").

    Returns:
        list: A list of S3 object keys for images found, or an empty list if error/none found.
    """
    if not S3_CLIENT_INITIALIZED or not s3_client:
        print("S3 client not initialized. Cannot list S3 objects.")
        return []

    target_bucket = bucket_name_param if bucket_name_param else S3_BUCKET_NAME
    if not target_bucket:
        print("Target bucket name not provided or configured. Cannot list S3 objects.")
        return []

    image_keys = []
    common_image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')

    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=target_bucket, Prefix=prefix)

        for page in page_iterator:
            if "Contents" in page:
                for obj in page["Contents"]:
                    key = obj["Key"]
                    if key.lower().endswith(common_image_extensions) and not key.endswith('/'): # Ensure it's not a "folder"
                        image_keys.append(key)
        
        print(f"Found {len(image_keys)} images in s3://{target_bucket}/{prefix}")
        return image_keys
    except (NoCredentialsError, PartialCredentialsError, ClientError) as e:
        print(f"S3 related error listing objects: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error listing S3 objects: {e}")
        return []

def list_s3_json_keys(bucket_name_param=None, prefix="metadata/"):
    """Lists JSON object keys from an S3 bucket under a given prefix.

    Args:
        bucket_name_param: The specific bucket to list from. Defaults to S3_BUCKET_NAME from config.
        prefix: The prefix under which to look for JSON files (e.g., "metadata/").

    Returns:
        list: A list of S3 object keys for JSON files found, or an empty list if error/none found.
    """
    if not S3_CLIENT_INITIALIZED or not s3_client:
        print("S3 client not initialized. Cannot list S3 JSON objects.")
        return []

    target_bucket = bucket_name_param if bucket_name_param else S3_BUCKET_NAME
    if not target_bucket:
        print("Target bucket name not provided or configured. Cannot list S3 JSON objects.")
        return []

    json_keys = []
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=target_bucket, Prefix=prefix)

        for page in page_iterator:
            if "Contents" in page:
                for obj in page["Contents"]:
                    key = obj["Key"]
                    if key.lower().endswith('.json') and not key.endswith('/'): # Ensure it's a .json file and not a "folder"
                        json_keys.append(key)
        
        print(f"Found {len(json_keys)} JSON files in s3://{target_bucket}/{prefix}")
        return json_keys
    except (NoCredentialsError, PartialCredentialsError, ClientError) as e:
        print(f"S3 related error listing JSON objects: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error listing S3 JSON objects: {e}")
        return []

def get_s3_json_content(object_key, bucket_name_param=None):
    """Fetches the string content of a JSON file from S3.

    Args:
        object_key: The S3 object key for the JSON file.
        bucket_name_param: The specific bucket. Defaults to S3_BUCKET_NAME from config.

    Returns:
        str: The content of the JSON file as a string, or None if error.
    """
    if not S3_CLIENT_INITIALIZED or not s3_client:
        print(f"S3 client not initialized. Cannot get content for {object_key}.")
        return None

    target_bucket = bucket_name_param if bucket_name_param else S3_BUCKET_NAME
    if not target_bucket:
        print(f"Target bucket name not provided or configured. Cannot get content for {object_key}.")
        return None

    try:
        response = s3_client.get_object(Bucket=target_bucket, Key=object_key)
        file_content = response['Body'].read().decode('utf-8')
        return file_content
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print(f"S3 object not found: s3://{target_bucket}/{object_key}")
        else:
            print(f"S3 ClientError getting object {object_key}: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error getting S3 object {object_key}: {e}")
        return None
