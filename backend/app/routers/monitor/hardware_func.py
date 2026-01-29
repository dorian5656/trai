#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/monitor/hardware_func.py
# 作者：whf
# 日期：2026-01-26
# 描述：系统硬件与环境监控逻辑 (Func)

import torch
import shutil
import psutil
import os
import subprocess
import xml.etree.ElementTree as ET
from backend.app.utils.logger import logger

try:
    import paddle
    PADDLE_AVAILABLE = True
except ImportError:
    PADDLE_AVAILABLE = False

class HardwareMonitor:
    """
    硬件监控逻辑封装
    """
    
    @staticmethod
    def get_nvidia_smi_info():
        """
        调用 nvidia-smi 获取详细 GPU 信息
        """
        try:
            # 尝试获取 XML 格式的详细信息
            result = subprocess.run(['nvidia-smi', '-q', '-x'], capture_output=True, text=True, check=True)
            xml_data = result.stdout
            
            root = ET.fromstring(xml_data)
            gpus = []
            
            driver_version = root.find('driver_version').text if root.find('driver_version') is not None else "Unknown"
            cuda_version = root.find('cuda_version').text if root.find('cuda_version') is not None else "Unknown"
            
            for gpu in root.findall('gpu'):
                product_name = gpu.find('product_name').text
                uuid = gpu.find('uuid').text
                
                # 显存信息
                fb_memory = gpu.find('fb_memory_usage')
                total_mem = fb_memory.find('total').text if fb_memory is not None else "N/A"
                used_mem = fb_memory.find('used').text if fb_memory is not None else "N/A"
                free_mem = fb_memory.find('free').text if fb_memory is not None else "N/A"
                
                # 利用率
                utilization = gpu.find('utilization')
                gpu_util = utilization.find('gpu_util').text if utilization is not None else "N/A"
                mem_util = utilization.find('memory_util').text if utilization is not None else "N/A"
                
                # 温度
                temperature = gpu.find('temperature')
                gpu_temp = temperature.find('gpu_temp').text if temperature is not None else "N/A"
                
                gpus.append({
                    "product_name": product_name,
                    "uuid": uuid,
                    "memory": {
                        "total": total_mem,
                        "used": used_mem,
                        "free": free_mem
                    },
                    "utilization": {
                        "gpu": gpu_util,
                        "memory": mem_util
                    },
                    "temperature": gpu_temp
                })
                
            return {
                "available": True,
                "driver_version": driver_version,
                "cuda_version": cuda_version,
                "gpu_count": len(gpus),
                "gpus": gpus
            }
        except FileNotFoundError:
            return {"available": False, "error": "nvidia-smi not found in PATH"}
        except Exception as e:
            logger.warning(f"nvidia-smi parsing failed: {e}")
            return {"available": False, "error": str(e)}

    @classmethod
    def check_gpu_env(cls):
        """
        检测系统 GPU 环境 (Torch, Paddle, Nvidia-smi)
        """
        # 1. Nvidia-smi System Check
        nvidia_info = cls.get_nvidia_smi_info()
        
        # 2. Torch Check
        torch_available = torch.cuda.is_available()
        torch_count = torch.cuda.device_count() if torch_available else 0
        torch_name = torch.cuda.get_device_name(0) if torch_available and torch_count > 0 else "N/A"
        torch_version = torch.__version__
        
        # 3. Paddle Check
        paddle_info = {"available": False, "version": "N/A", "device": "N/A"}
        if PADDLE_AVAILABLE:
            paddle_available = paddle.device.is_compiled_with_cuda()
            paddle_device = paddle.device.get_device()
            paddle_info = {
                "available": paddle_available,
                "device": paddle_device,
                "version": paddle.__version__
            }
        
        info = {
            "nvidia_smi": nvidia_info,
            "torch": {
                "cuda_available": torch_available,
                "device_count": torch_count,
                "device_name": torch_name,
                "version": torch_version
            },
            "paddle": paddle_info,
            "system_cuda": os.environ.get("CUDA_VISIBLE_DEVICES", "Not Set")
        }
        
        if nvidia_info["available"] or torch_available or paddle_info["available"]:
            logger.info(f"GPU 环境检测完成")
        else:
            logger.warning(f"GPU 环境检测显示无可用 GPU")
            
        return info

    @staticmethod
    def check_system_resources():
        """
        检测系统 CPU、内存、磁盘资源
        """
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        
        # Memory
        mem = psutil.virtual_memory()
        mem_info = {
            "total_gb": round(mem.total / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "percent": mem.percent
        }
        
        # Disk
        disk = shutil.disk_usage(".")
        disk_info = {
            "total_gb": round(disk.total / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2)
        }
        
        data = {
            "cpu": {
                "percent": cpu_percent,
                "cores": cpu_count
            },
            "memory": mem_info,
            "disk": disk_info
        }
        return data
