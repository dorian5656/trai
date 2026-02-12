#!/bin/bash
# 文件名: cleanup_envs.sh
# 描述: 后台执行 Conda 环境重命名与清理任务

# 定义日志文件
LOG_FILE="env_cleanup.log"

echo "开始执行环境清理任务 - $(date)" > "$LOG_FILE"

# 1. 清理旧环境 (如果存在)
echo "正在删除 trai_31014_whf..." >> "$LOG_FILE"
conda env remove --name trai_31014_whf -y >> "$LOG_FILE" 2>&1

echo "正在删除 trai_31014_whf_dev..." >> "$LOG_FILE"
conda env remove --name trai_31014_whf_dev -y >> "$LOG_FILE" 2>&1

# 2. 处理 Dev 环境
echo "正在克隆 Dev 环境: trai_31014_whf_trai_dev_20260202 -> trai_31014_whf_dev_20260202..." >> "$LOG_FILE"
conda create --name trai_31014_whf_dev_20260202 --clone trai_31014_whf_trai_dev_20260202 -y >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    echo "Dev 环境克隆成功，正在删除源环境..." >> "$LOG_FILE"
    conda env remove --name trai_31014_whf_trai_dev_20260202 -y >> "$LOG_FILE" 2>&1
else
    echo "Dev 环境克隆失败，跳过删除源环境。" >> "$LOG_FILE"
fi

# 3. 处理 Pro 环境 (源环境清理)
# 注意：假设 Pro 环境的新克隆已经在之前的手动操作中完成了 (trai_31014_whf_pro_20260202)
# 这里只负责清理旧的 Pro 源环境 (trai_31014_whf_trai_pro_20260202)
echo "正在检查是否需要清理旧 Pro 源环境: trai_31014_whf_trai_pro_20260202..." >> "$LOG_FILE"
# 简单检查新环境是否存在
if conda env list | grep -q "trai_31014_whf_pro_20260202"; then
    echo "检测到新 Pro 环境已存在，正在删除旧源环境..." >> "$LOG_FILE"
    conda env remove --name trai_31014_whf_trai_pro_20260202 -y >> "$LOG_FILE" 2>&1
else
    echo "警告: 未检测到新 Pro 环境 (trai_31014_whf_pro_20260202)，跳过删除旧源环境以防数据丢失。" >> "$LOG_FILE"
fi

echo "所有任务执行完毕 - $(date)" >> "$LOG_FILE"
