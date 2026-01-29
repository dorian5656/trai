import requests
import os
import sys

# 配置
BASE_URL = "http://192.168.98.183:5889/api/v1"
USERNAME = "A6666"
PASSWORD = "123456"
FILE_PATH = "backend/temp/image.png"

def login():
    print(f"[-] 正在登录用户 {USERNAME}...")
    url = f"{BASE_URL}/auth/login"
    data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        token = response.json().get("access_token")
        print(f"[+] 登录成功，Token: {token[:10]}...")
        return token
    except Exception as e:
        print(f"[!] 登录失败: {e}")
        if response:
            print(f"Response: {response.text}")
        sys.exit(1)

def upload_file(token):
    print(f"[-] 正在上传文件 {FILE_PATH}...")
    url = f"{BASE_URL}/upload/common"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    if not os.path.exists(FILE_PATH):
        print(f"[!] 文件不存在: {FILE_PATH}")
        sys.exit(1)
        
    try:
        files = {
            "file": ("image.png", open(FILE_PATH, "rb"), "image/png")
        }
        data = {
            "module": "chat"
        }
        response = requests.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()
        result = response.json()
        print(f"[+] 上传成功!")
        print(f"URL: {result.get('url')}")
        print(f"Full Response: {result}")
        
        # 验证 URL 是否包含 trai_images
        uploaded_url = result.get('url', '')
        if "trai_images" in uploaded_url:
            print("[+] 验证通过: URL 包含 trai_images Bucket 名称")
        else:
            print("[-] 验证警告: URL 未包含 trai_images (可能配置未生效或未使用 S3)")
            
    except Exception as e:
        print(f"[!] 上传失败: {e}")
        if 'response' in locals():
            print(f"Response: {response.text}")

if __name__ == "__main__":
    token = login()
    upload_file(token)
