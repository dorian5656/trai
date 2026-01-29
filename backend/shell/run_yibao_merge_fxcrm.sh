#!/bin/bash
# 医保数据同步脚本
# 作者: liuhd
# 日期: 2026-01-28 14:14:00
# 描述: 封装运行医保码抓取与 CRM 同步的一体化 Python 脚本

# 开启严格模式：遇到错误退出 (-e)，未定义变量报错 (-u)，管道故障传递 (-o pipefail)
set -euo pipefail

# 获取当前脚本所在目录的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 设置 Python 脚本路径
PYTHON_SCRIPT="$SCRIPT_DIR/../app/yibaocode/yibao_merge_fxcrm.py"

# 检查 Python 脚本是否存在
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "错误: 找不到 Python 脚本: $PYTHON_SCRIPT"
    exit 1
fi

# 指定 Conda 环境 Python 解释器
# 用户指定环境: nhsa_post_crm
CONDA_PYTHON_WSL="/mnt/c/Users/Administrator/.conda/envs/nhsa_post_crm/python.exe"
CONDA_PYTHON_GIT="/c/Users/Administrator/.conda/envs/nhsa_post_crm/python.exe"
CONDA_PYTHON_WIN="C:\\Users\\Administrator\\.conda\\envs\\nhsa_post_crm\\python.exe"
if [ -f "$CONDA_PYTHON_WSL" ]; then
    CONDA_PYTHON="$CONDA_PYTHON_WSL"
elif [ -f "$CONDA_PYTHON_GIT" ]; then
    CONDA_PYTHON="$CONDA_PYTHON_GIT"
else
    CONDA_PYTHON=""
fi

# 检查指定环境的 python 是否存在
if [ -f "$CONDA_PYTHON" ]; then
    PYTHON_CMD="$CONDA_PYTHON"
    echo ">>> 使用指定 Conda 环境: nhsa_post_crm ($CONDA_PYTHON)"
else
    if command -v powershell.exe >/dev/null 2>&1; then
        if [[ "$SCRIPT_DIR" == /mnt/* ]]; then
            D="$(echo "$SCRIPT_DIR" | cut -d'/' -f3)"
            R="$(echo "$SCRIPT_DIR" | cut -d'/' -f4- | sed 's|/|\\|g')"
            WORKDIR_WIN="${D}:\\${R}"
        else
            WORKDIR_WIN="$(echo "$SCRIPT_DIR" | sed 's|/|\\|g')"
        fi
        powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '${CONDA_PYTHON_WIN}' -ArgumentList 'yibao_merge_fxcrm.py' -WorkingDirectory '${WORKDIR_WIN}' -Wait; exit \$LASTEXITCODE"
        EXIT_CODE=$?
        echo ">>> 结束时间: $(date '+%Y-%m-%d %H:%M:%S')"
        exit $EXIT_CODE
    fi
    PYTHON_CMD="python"
    echo ">>> 警告: 未找到指定环境 Python ($CONDA_PYTHON)，尝试使用系统默认 python"
fi

# 切换到脚本所在目录运行，确保相对路径正确 (如 .env 读取)
cd "$SCRIPT_DIR" || exit 1

echo ">>> 开始执行医保抓取推送任务..."
echo ">>> 时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ">>> 脚本: $PYTHON_SCRIPT"

# 运行 Python 脚本
RUN_SCRIPT="$PYTHON_SCRIPT"
if [[ "$PYTHON_CMD" == /mnt/* || "$PYTHON_CMD" == /c/* ]]; then
    if [[ "$PYTHON_SCRIPT" == /mnt/* ]]; then
        D2="$(echo "$PYTHON_SCRIPT" | cut -d'/' -f3)"
        R2="$(echo "$PYTHON_SCRIPT" | cut -d'/' -f4- | sed 's|/|\\|g')"
        RUN_SCRIPT="${D2}:\\${R2}"
    else
        RUN_SCRIPT="$(echo "$PYTHON_SCRIPT" | sed 's|/|\\|g')"
    fi
fi
"$PYTHON_CMD" "$RUN_SCRIPT"
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ">>> 任务执行成功."
else
    echo ">>> 任务执行失败，退出码: $EXIT_CODE"
fi

echo ">>> 结束时间: $(date '+%Y-%m-%d %H:%M:%S')"
exit $EXIT_CODE
