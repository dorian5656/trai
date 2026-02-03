import requests
import sys
import time

BASE_URL = "http://127.0.0.1:5778"
LOGIN_URL = f"{BASE_URL}/api/v1/auth/login"
GEN_URL = f"{BASE_URL}/api/v1/ai/image/generations"

def test():
    # Wait for server to be ready
    print("Waiting for server...")
    time.sleep(5) 
    
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

    # 2. Generate Image
    prompt = "一个美女，和福在一起，拿着一个福，春节主题"
    print(f"Generating image with prompt: {prompt}")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    # Using Z-Image as per memory about Dify limitations and local availability
    payload = {
        "prompt": prompt,
        "model": "Z-Image"
    }
    
    try:
        # Long timeout for image generation
        resp = requests.post(GEN_URL, json=payload, headers=headers, timeout=120)
        if resp.status_code == 200:
            print("Generation success!")
            print(resp.json())
        else:
            print(f"Generation failed: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"Generation connection error: {e}")

if __name__ == "__main__":
    test()
