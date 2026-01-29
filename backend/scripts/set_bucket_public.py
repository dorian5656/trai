import sys
import json
import boto3
from pathlib import Path
from dotenv import load_dotenv

# Load .env
backend_dir = Path(__file__).resolve().parent.parent
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Add backend to path
sys.path.append(str(backend_dir.parent))

from backend.app.config import settings

def set_public_policy(bucket_name):
    print(f"[-] Connecting to S3 at {settings.S3_ENDPOINT_URL}...")
    s3 = boto3.client(
        's3',
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION_NAME
    )
    
    # Define Public Read Policy
    bucket_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadGetObject",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket_name}/*"
            }
        ]
    }
    
    policy_json = json.dumps(bucket_policy)
    
    try:
        print(f"[-] Setting public policy for bucket: {bucket_name}")
        s3.put_bucket_policy(Bucket=bucket_name, Policy=policy_json)
        print(f"[+] Successfully set public read policy for '{bucket_name}'")
    except Exception as e:
        print(f"[!] Failed to set policy for '{bucket_name}': {e}")

if __name__ == "__main__":
    # Set for the new image bucket
    target_bucket = settings.S3_IMAGE_BUCKET_NAME
    if target_bucket:
        set_public_policy(target_bucket)
    else:
        print("[!] S3_IMAGE_BUCKET_NAME not set in config")
        
    # Optional: also set for the old one if needed, but sticking to requirement
    # set_public_policy("trai-images") 
