import asyncio
import json
import os
import sys
from dotenv import load_dotenv

# 添加项目根目录到 sys.path
sys.path.append(os.getcwd())

# 加载环境变量
env_path = os.path.join(os.getcwd(), 'backend', '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"已加载环境变量: {env_path}")
else:
    print(f"⚠️ 未找到环境变量文件: {env_path}")

from backend.app.config import settings
import aioboto3

async def set_public_policy(bucket_name):
    session = aioboto3.Session()
    async with session.client(
        's3',
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION_NAME
    ) as s3:
        try:
            # 检查 Bucket 是否存在
            try:
                await s3.head_bucket(Bucket=bucket_name)
                print(f"✅ Bucket '{bucket_name}' 存在")
            except Exception:
                print(f"⚠️ Bucket '{bucket_name}' 不存在，正在创建...")
                await s3.create_bucket(Bucket=bucket_name)
                print(f"✅ Bucket '{bucket_name}' 创建成功")

            # 设置公开读 Policy
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "PublicRead",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                    }
                ]
            }
            
            print(f"正在设置 '{bucket_name}' 为公开读模式...")
            await s3.put_bucket_policy(
                Bucket=bucket_name,
                Policy=json.dumps(policy)
            )
            print(f"✅ 成功设置 '{bucket_name}' 的公开读策略！")
            
        except Exception as e:
            print(f"❌ 操作失败: {e}")

if __name__ == "__main__":
    bucket_name = settings.S3_SPEECH_BUCKET_NAME or "trai_speech"
    print(f"目标 Bucket: {bucket_name}")
    asyncio.run(set_public_policy(bucket_name))
