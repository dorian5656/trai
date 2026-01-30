import requests
import os

# 配置
BASE_URL = "http://localhost:6001"
AUDIO_FILE = "backend/222.mp3"
USERNAME = "A6666"
PASSWORD = "123456"

def login():
    """获取访问令牌"""
    print(f"🔑 正在登录用户 {USERNAME}...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={"username": USERNAME, "password": PASSWORD}
        )
        if response.status_code == 200:
            token = response.json().get("access_token")
            print("✅ 登录成功")
            return token
        else:
            print(f"❌ 登录失败: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 登录请求异常: {e}")
        return None

def test_transcribe(token):
    """测试语音转写"""
    import json
    # current_audio_file = "222.mp3"
    current_audio_file = os.path.join(os.path.dirname(__file__), "backend", "temp", "233.mp3")
    
    if not os.path.exists(current_audio_file):
        print(f"❌ 错误: 音频文件不存在: {current_audio_file}")
        print("请将测试音频文件放在 backend/temp/233.mp3")
        return
        
    api_url = f"{BASE_URL}/api/v1/speech/transcribe"
    print(f"🎤 正在测试语音识别接口... (文件: {current_audio_file})")
    print(f"API 地址: {api_url}")

    # 3. 发送请求
    try:
        with open(current_audio_file, "rb") as f:
            files = {"file": (os.path.basename(current_audio_file), f, "audio/mpeg")}
            headers = {"Authorization": f"Bearer {token}"}
            
            response = requests.post(
                api_url, 
                files=files,
                headers=headers,
                timeout=120  # 设置较长的超时时间，因为模型加载和推理可能较慢
            )
            
        print(f"Status Code: {response.status_code}")
        try:
            # 打印完整响应
            json_resp = response.json()
            print("Response JSON:")
            print(json.dumps(json_resp, ensure_ascii=False, indent=2))
            
            if response.status_code == 200 and json_resp.get("code") == 200:
                print(f"✅ 识别成功! 结果: {json_resp['data']['text']}")
                print(f"🔗 音频 URL: {json_resp['data'].get('url', '未返回 URL')}")
            else:
                print(f"❌ 识别失败: {json_resp.get('msg', '未知错误')}")
        except json.JSONDecodeError:
            print(f"Response Text: {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ 请求超时 (Timeout)！可能是模型正在加载或推理时间过长。")

if __name__ == "__main__":
    # 确保在项目根目录运行
    if not os.path.exists("backend"):
        print("❌ 请在项目根目录 (trai/) 下运行此脚本")
        exit(1)
        
    token = login()
    if token:
        test_transcribe(token)
