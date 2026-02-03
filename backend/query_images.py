import asyncio
import sys
import os

# 添加项目根目录到 sys.path，确保可以导入 app 模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.utils.pg_utils import PGUtils

async def query_user_images(user_id):
    sql = "SELECT id, user_id, prompt, url, created_at FROM user_images WHERE user_id = :user_id ORDER BY created_at DESC"
    images = await PGUtils.fetch_all(sql, {"user_id": user_id})
    
    print(f"Found {len(images)} images for user {user_id}:")
    for img in images:
        print(f"[{img['created_at']}] ID: {img['id']}, Prompt: {img['prompt']}, URL: {img['url']}")

if __name__ == "__main__":
    if len(sys.path) > 1:
        # 确保在 backend 目录下运行或者正确设置 PYTHONPATH
        pass
    
    try:
        asyncio.run(query_user_images("A6666"))
    except Exception as e:
        print(f"Error: {e}")
