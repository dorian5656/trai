---
license: apache-2.0
language:
- zh
- en
tags:
- cybersecurity
- qwen
- sft
- security-audit
- vulnerability-detection
base_model: Qwen/Qwen2.5-0.5B-Instruct
pipeline_tag: text-generation
---

# 🛡️ Qwen2.5-0.5B-CyberSec (幻城·天网-0.5B)

## 模型简介 (Model Introduction)

**Qwen2.5-0.5B-CyberSec**（代号：幻城·天网-0.5B）是基于 **Qwen2.5-0.5B-Instruct** 基座模型，使用 **Cybersecurity-Dataset**（幻城网安超大规模数据集）进行全量微调（SFT）后的网络安全领域专用小模型。

该模型旨在以极低的资源消耗（单卡消费级显卡甚至CPU/手机端）提供基础的网络安全知识问答、简单的安全脚本生成以及初级的漏洞解释能力。

## 🚀 快速上手 (Quick Start)

我们在模型目录下直接提供了推理脚本，方便您直接使用。

### 1. 模型推理 (Inference)

本目录 (`llm_study`) 仅包含推理与训练代码，模型权重文件位于项目模型的统一存储目录 (`backend/app/models/Qwen/Qwen2.5-0.5B-CyberSec`)。

直接运行目录下的 `inference.py` 即可（脚本已自动指向正确的模型路径）：

```bash
# 进入代码目录
cd /home/code_dev/trai/backend/app/llm_study/Qwen2.5-0.5B-CyberSec

# 运行推理 (默认问题：如何防御SQL注入攻击？)
python inference.py

# 自定义问题
python inference.py --prompt "写一个Python端口扫描脚本"
```

### 2. 模型训练 (Training)

如果您想复现微调过程，可以使用 `train.py` 脚本。

```bash
# 使用 4 张 GPU 并行训练
python -m accelerate.commands.launch --multi_gpu --num_processes=4 train.py
```

## 📊 效果对比 (Base vs CyberSec)

以下是基座模型（Base）与微调后模型（CyberSec）在相同提示词下的表现对比：

### 1. 漏洞检测
**Prompt**: `如何检测SQL注入漏洞？`

| 模型 | 回答摘要 | 特点 |
| :--- | :--- | :--- |
| **Base (基座)** | 建议使用通用工具（JMeter, Burp Suite）、进行代码审查、避免硬编码敏感信息。 | **泛泛而谈**，偏向通用软件工程建议。 |
| **CyberSec (微调)** | 直接提供 **Python 代码示例**，展示如何使用 `psycopg2`、`mysql.connector` 连接数据库并执行查询测试。 | **实战导向**，倾向于提供具体的代码实现和工具库。 |

### 2. 攻击危害分析
**Prompt**: `解释XSS攻击的危害`

| 模型 | 回答摘要 | 特点 |
| :--- | :--- | :--- |
| **Base (基座)** | 提到用户隐私泄露、数据篡改、系统漏洞利用、服务器负载增加。 | **标准化回答**，类似教科书定义。 |
| **CyberSec (微调)** | 深入提到了 **数据库注入**、**Webshell 渗透**、**RCE (远程代码执行)**、**权限提升**。 | **渗透视角**，关联了更深层次的攻击链后果。 |

### 3. 概念解释
**Prompt**: `什么是零信任架构？`

| 模型 | 回答摘要 | 特点 |
| :--- | :--- | :--- |
| **Base (基座)** | 解释了“永不信任，始终验证”的概念，提到了成本问题。 | **基础概念**。 |
| **CyberSec (微调)** | 结构化列出了“全网统一认证”、“权限分级管理”、“持续监控与审计”等核心特征及应用场景。 | **专业条理**，使用了更准确的行业术语。 |

## 模型规格 (Model Specifications)

| 属性 | 描述 |
| :--- | :--- |
| **基座模型** | Qwen/Qwen2.5-0.5B-Instruct |
| **参数量** | 0.49B (约5亿) |
| **训练数据** | [Cybersecurity-Dataset](https://www.modelscope.cn/datasets/hcnote/Cybersecurity-Dataset) (CVE, ExploitDB, WebShell, 攻防日志等) |
| **训练方法** | QLoRA (4-bit), Rank=16, Alpha=32 |
| **训练设备** | 4 x NVIDIA L20 (48GB) |
| **上下文长度** | 32K |
| **词表大小** | 151936 |

## 核心能力 (Core Capabilities)

经过微调，该模型在以下方面表现出优于基座模型的能力：

1.  **安全知识问答**：能准确解释常见的安全术语（如 SQL注入、XSS、CSRF、零信任、APT 等）。
2.  **初级代码生成**：能编写简单的 Python/Bash 安全脚本（如端口扫描、简单的 Payload 生成）。
3.  **漏洞原理分析**：能结构化地描述漏洞的成因、危害及修复建议。
4.  **攻防视角转换**：具备初步的红队（攻击）与蓝队（防御）思维，能从双向视角回答问题。

## 免责声明 (Disclaimer)

本模型仅供网络安全教育、研究及授权测试使用。使用者应遵守当地法律法规，严禁将本模型用于非法入侵、攻击或其他未授权的恶意活动。模型开发者不对使用本模型产生的任何后果承担责任。
