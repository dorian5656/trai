import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env explicitly
backend_dir = Path(__file__).resolve().parent.parent
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"Loaded .env from {env_path}")
else:
    print(f"Warning: .env not found at {env_path}")

# Add backend to path
sys.path.append(str(backend_dir.parent))

from backend.app.config import settings
import boto3

def create_buckets():
    print(f"Connecting to S3 at {settings.S3_ENDPOINT_URL}...")
    s3 = boto3.client(
        's3',
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION_NAME
    )
    
    buckets = [settings.S3_BUCKET_NAME, settings.S3_IMAGE_BUCKET_NAME]
    
    for bucket_name in buckets:
        if not bucket_name:
            continue
            
        try:
            s3.head_bucket(Bucket=bucket_name)
            print(f"Bucket '{bucket_name}' already exists.")
        except Exception:
            print(f"Creating bucket '{bucket_name}'...")
            try:
                s3.create_bucket(Bucket=bucket_name)
                print(f"Bucket '{bucket_name}' created successfully.")
            except Exception as e:
                print(f"Failed to create bucket '{bucket_name}': {e}")

if __name__ == "__main__":
    create_buckets()
