import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import argparse
import os

# 获取当前脚本所在目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 默认模型路径指向 backend/app/models 下的对应目录
# 支持通过环境变量覆盖默认路径
DEFAULT_MODEL_PATH = os.getenv("MODEL_PATH", os.path.abspath(os.path.join(CURRENT_DIR, "../../models/Qwen/Qwen2.5-0.5B-CyberSec")))

def main():
    parser = argparse.ArgumentParser(description="Qwen2.5-0.5B-CyberSec 推理脚本")
    parser.add_argument("--model_path", type=str, default=DEFAULT_MODEL_PATH, help="模型路径")
    parser.add_argument("--prompt", type=str, default="如何防御SQL注入攻击？", help="输入的问题")
    args = parser.parse_args()

    print(f"Loading model from {args.model_path}...")
    try:
        # 加载分词器
        tokenizer = AutoTokenizer.from_pretrained(args.model_path, trust_remote_code=True)
        
        # 加载模型 (自动检测 GPU)
        model = AutoModelForCausalLM.from_pretrained(
            args.model_path,
            torch_dtype="auto",
            device_map="auto",
            trust_remote_code=True
        )
    except Exception as e:
        print(f"Error loading model: {e}")
        return

    # 构造对话消息
    messages = [
        {"role": "system", "content": "You are a helpful cybersecurity assistant."},
        {"role": "user", "content": args.prompt}
    ]
    
    # 应用对话模板
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
    
    # 编码输入
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

    print(f"\nQuestion: {args.prompt}")
    print("-" * 50)
    print("Generating response...")

    # 生成回答
    generated_ids = model.generate(
        **model_inputs,
        max_new_tokens=512,      # 最大生成长度
        temperature=0.7,         # 温度 (0.0-1.0)，越高越随机
        top_p=0.9,               # 核采样概率
        do_sample=True           # 启用采样
    )
    
    # 解码输出 (去除输入的 prompt 部分)
    generated_ids = [
        output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
    ]
    response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

    print("-" * 50)
    print(f"Response:\n{response}")
    print("-" * 50)

if __name__ == "__main__":
    main()
