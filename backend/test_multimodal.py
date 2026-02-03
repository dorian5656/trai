import requests
import sys
import time

BASE_URL = "http://127.0.0.1:5778"
LOGIN_URL = f"{BASE_URL}/api/v1/auth/login"
CHAT_URL = f"{BASE_URL}/api/v1/ai/image/chat/image"

def test_multimodal():
    # Wait for server to be ready
    print("Waiting for server...")
    time.sleep(10) 
    
    # 1. Login
    print(f"Logging in to {LOGIN_URL}...")
    try:
        resp = requests.post(LOGIN_URL, data={"username": "A6666", "password": "123456"})
        if resp.status_code != 200:
            print(f"Login failed: {resp.status_code} {resp.text}")
            return
        token_data = resp.json()
        access_token = token_data.get("access_token")
        print(f"Login success. Token: {access_token[:10]}...")
    except Exception as e:
        print(f"Login connection error: {e}")
        return

    # 2. Multimodal Chat
    print(f"Sending multimodal chat request...")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": "http://192.168.0.190:12001/trai_images/chat/20260203/4fa1e2bddb1d4d04b18631bf27cd4903.jpg"},
                    {"type": "text", "text": "这张图片里有什么?"}
                ]
            }
        ],
        "model": "Qwen/Qwen3-VL-4B-Instruct",
        "temperature": 0.7,
        "max_tokens": 512
    }
    
    try:
        # Long timeout for model loading and inference
        resp = requests.post(CHAT_URL, json=payload, headers=headers, timeout=300)
        if resp.status_code == 200:
            print("Chat success!")
            print(resp.json())
        else:
            print(f"Chat failed: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"Chat connection error: {e}")

if __name__ == "__main__":
    test_multimodal()
