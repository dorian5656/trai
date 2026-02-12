# LLM 学习笔记：Llama 3.1 8B Instruct 部署

本项目是基于 Datawhale `self-llm` 教程的学习实践。

## 📂 目录结构

- `download_model.py`: 使用 ModelScope 下载模型脚本
- `main.py`: 基于 FastAPI 的推理服务

## 🛠️ 环境准备

请确保已激活项目的 conda 环境 (`trai_31014_whf_pro_20260202`)。

需要安装以下依赖：

```bash
pip install modelscope transformers accelerate fastapi uvicorn
```

*注意：`requirements.txt` 可能已包含部分依赖，请根据实际情况补充安装。*

## 🚀 快速开始

### 1. 下载模型

执行下载脚本，模型将保存至 `backend/app/models/LLM-Research/Meta-Llama-3.1-8B-Instruct`。

```bash
# 在项目根目录下执行
python backend/app/llm_study/llama3_1/download_model.py
```

**注意**: 模型大小约 15GB，请确保磁盘空间充足。

### 2. 启动 API 服务

```bash
# 在项目根目录下执行
python backend/app/llm_study/llama3_1/main.py
```

服务将启动在 `http://0.0.0.0:6006`。

### 3. 调用测试

可以使用 curl 进行测试：

```bash
curl -X POST "http://127.0.0.1:6006" \
     -H 'Content-Type: application/json' \
     -d '{"prompt": "你好，请介绍一下你自己"}'
```

## 🔗 参考资料

- [Datawhale self-llm Llama3.1 教程](https://github.com/datawhalechina/self-llm/blob/master/models/Llama3_1/01-Llama3_1-8B-Instruct%20FastApi%20%E9%83%A8%E7%BD%B2%E8%B0%83%E7%94%A8.md)
