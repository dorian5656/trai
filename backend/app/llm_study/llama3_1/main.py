#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：backend/app/llm_study/llama3_1/main.py
# 作者：liuhd
# 日期：2026-02-11
# 描述：Llama3.1-8B-Instruct FastAPI 推理服务
# 参考：https://github.com/datawhalechina/self-llm

from fastapi import FastAPI, Request
from transformers import AutoTokenizer, AutoModelForCausalLM
import uvicorn
import json
import datetime
import torch
import os
from pathlib import Path

# 设置设备参数
DEVICE = "cuda"  # 使用CUDA
DEVICE_ID = "0"  # CUDA设备ID，如果未设置则为空
CUDA_DEVICE = f"{DEVICE}:{DEVICE_ID}" if DEVICE_ID else DEVICE  # 组合CUDA设备信息

# 清理GPU内存函数
def torch_gc():
    if torch.cuda.is_available():  # 检查是否可用CUDA
        with torch.cuda.device(CUDA_DEVICE):  # 指定CUDA设备
            torch.cuda.empty_cache()  # 清空CUDA缓存
            torch.cuda.ipc_collect()  # 收集CUDA内存碎片

# 创建FastAPI应用
app = FastAPI(title="Llama 3.1 8B Instruct API")

# 全局变量
model = None
tokenizer = None

# 模型路径 (自动推断)
# 假设模型下载在 backend/app/models/LLM-Research/Meta-Llama-3.1-8B-Instruct
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
MODEL_PATH = BASE_DIR / "app" / "models" / "LLM-Research" / "Meta-Llama-3.1-8B-Instruct"

@app.on_event("startup")
async def startup_event():
    """应用启动时加载模型"""
    global model, tokenizer
    print(f"正在加载模型，路径: {MODEL_PATH}")
    
    if not MODEL_PATH.exists():
        print(f"❌ 错误: 模型路径不存在: {MODEL_PATH}")
        print("请先运行 download_model.py 下载模型")
        return

    try:
        # 加载分词器
        tokenizer = AutoTokenizer.from_pretrained(str(MODEL_PATH), use_fast=False, trust_remote_code=True)
        # 加载模型
        model = AutoModelForCausalLM.from_pretrained(
            str(MODEL_PATH), 
            device_map="auto", 
            torch_dtype=torch.bfloat16,
            trust_remote_code=True
        )
        print("✅ 模型加载完成")
    except Exception as e:
        print(f"❌ 模型加载失败: {e}")

# 处理POST请求的端点
@app.post("/")
async def create_item(request: Request):
    global model, tokenizer
    
    if model is None or tokenizer is None:
        return {"status": 500, "message": "模型未加载"}

    try:
        json_post_raw = await request.json()  # 获取POST请求的JSON数据
        # 兼容处理: 某些客户端可能发送 JSON 字符串
        if isinstance(json_post_raw, str):
            json_post_list = json.loads(json_post_raw)
        else:
            json_post_list = json_post_raw
            
        prompt = json_post_list.get('prompt')  # 获取请求中的提示

        if not prompt:
            return {"status": 400, "message": "Prompt is required"}

        messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
        ]

        # 调用模型进行对话生成
        input_ids = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        model_inputs = tokenizer([input_ids], return_tensors="pt").to(DEVICE)
        
        generated_ids = model.generate(model_inputs.input_ids, max_new_tokens=512)
        generated_ids = [
            output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]
        
        response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
        
        now = datetime.datetime.now()  # 获取当前时间
        time = now.strftime("%Y-%m-%d %H:%M:%S")  # 格式化时间为字符串
        
        # 构建响应JSON
        answer = {
            "response": response,
            "status": 200,
            "time": time
        }
        
        # 构建日志信息
        log = "[" + time + "] " + '", prompt:"' + prompt + '", response:"' + repr(response) + '"'
        print(log)  # 打印日志
        
        torch_gc()  # 执行GPU内存清理
        
        return answer  # 返回响应
        
    except Exception as e:
        print(f"❌ 推理过程出错: {e}")
        return {"status": 500, "message": str(e)}

# 主函数入口
if __name__ == '__main__':
    # 启动FastAPI应用
    # 端口设置为 6006 (与教程一致)
    uvicorn.run(app, host='0.0.0.0', port=6006, workers=1)
