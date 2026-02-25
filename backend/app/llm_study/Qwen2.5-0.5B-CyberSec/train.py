import os
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig
)
from peft import LoraConfig, PeftModel
from trl import SFTTrainer, SFTConfig
from accelerate import PartialState
import sys
import shutil

# ==============================================================================
# 路径配置 (请根据实际环境修改)
# ==============================================================================
# 获取当前脚本所在目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 基座模型路径 (假设在 backend/app/models/Qwen 下)
# 如果不存在，建议修改为实际路径
BASE_MODEL = os.path.abspath(os.path.join(CURRENT_DIR, "../../models/Qwen/Qwen2.5-0.5B-Instruct"))

# 训练数据 (JSONL) - 请将数据集放置在此处或修改路径
DATA_FILE = os.path.join(CURRENT_DIR, "dataset.jsonl")
# 输出路径 (当前目录)
OUTPUT_DIR = CURRENT_DIR 
# 临时适配器路径
ADAPTER_DIR = os.path.join(CURRENT_DIR, "adapter_temp")

def main():
    # 1. 加载 Tokenizer
    print(f"Loading tokenizer from {BASE_MODEL}")
    try:
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
        tokenizer.pad_token = tokenizer.eos_token
    except Exception as e:
        print(f"Error loading base model: {e}")
        print(f"Please check if base model exists at: {BASE_MODEL}")
        return
    
    # 2. 加载数据集 (流式加载节省内存)
    print(f"Loading dataset from {DATA_FILE}")
    dataset = load_dataset("json", data_files=DATA_FILE, split="train", streaming=True)
    
    # 数据格式化函数
    def format_batch(batch):
        output_texts = []
        instructions = batch['instruction']
        inputs = batch['input']
        outputs = batch['output']
        
        for i in range(len(instructions)):
            instruction = instructions[i]
            input_text = inputs[i]
            response = outputs[i]
            if input_text:
                text = f"Instruction: {instruction}\nInput: {input_text}\nResponse: {response}"
            else:
                text = f"Instruction: {instruction}\nResponse: {response}"
            output_texts.append(text)
        return {"text": output_texts}

    dataset = dataset.map(format_batch, batched=True, remove_columns=["instruction", "input", "output"])

    # 3. QLoRA 量化配置 (4-bit)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    # 4. 加载基座模型
    print(f"Loading base model from {BASE_MODEL}")
    device_map = {"": PartialState().process_index} # 多卡适配
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=bnb_config,
        device_map=device_map,
        trust_remote_code=True
    )
    
    # 5. LoRA 配置
    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    )
    
    # 6. 训练参数配置
    training_args = SFTConfig(
        output_dir=ADAPTER_DIR,
        dataset_text_field="text",
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        logging_steps=5,
        max_steps=50,          # 演示用，实际训练建议增加步数 (如 1000+)
        save_steps=25,
        bf16=True,             # 开启 BF16 加速
        fp16=False,
        ddp_find_unused_parameters=False,
        optim="paged_adamw_8bit",
        report_to="none"
    )
    
    # 7. 开始训练
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        peft_config=peft_config,
        args=training_args,
    )
    
    print("Starting training...")
    trainer.train()
    trainer.save_model(ADAPTER_DIR)
    
    # 8. 清理显存 (为合并模型做准备)
    print("Cleaning up memory...")
    del model
    del trainer
    torch.cuda.empty_cache()
    import gc
    gc.collect()
    
    # 9. 合并模型并保存 (仅主进程执行)
    if PartialState().is_main_process:
        print("Merging model...")
        try:
            # 重新加载 FP16 基座模型
            base_model = AutoModelForCausalLM.from_pretrained(
                BASE_MODEL,
                torch_dtype=torch.float16,
                device_map="auto",
                trust_remote_code=True
            )
            # 加载适配器并合并
            model = PeftModel.from_pretrained(base_model, ADAPTER_DIR)
            model = model.merge_and_unload()
            
            # 保存完整模型
            print(f"Saving merged model to {OUTPUT_DIR}")
            model.save_pretrained(OUTPUT_DIR)
            tokenizer.save_pretrained(OUTPUT_DIR)
            print("Done!")
            
            # 清理临时文件
            # shutil.rmtree(ADAPTER_DIR)
        except Exception as e:
            print(f"Error merging model: {e}")

if __name__ == "__main__":
    main()
