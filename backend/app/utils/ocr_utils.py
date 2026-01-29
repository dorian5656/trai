#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/ocr_utils.py
# 作者：whf
# 日期：2026-01-26
# 描述：PaddleOCR 工具类 (单例模式 + 线程池并发)

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any
import os
import sys
import threading # 引入线程锁

# [Patch] 尝试添加 nvidia-cudnn-cu11 的 dll 路径到环境变量 (解决 Paddle 缺失 cudnn64_8.dll 问题)
try:
    # 尝试查找 site-packages 中的 nvidia/cudnn/bin
    for path in sys.path:
        if 'site-packages' in path:
            cudnn_bin = os.path.join(path, 'nvidia', 'cudnn', 'bin')
            if os.path.exists(os.path.join(cudnn_bin, 'cudnn64_8.dll')):
                os.environ['PATH'] = cudnn_bin + os.pathsep + os.environ['PATH']
                if hasattr(os, 'add_dll_directory'):
                    os.add_dll_directory(cudnn_bin)
                # print(f"Added cuDNN to PATH: {cudnn_bin}")
                break
except Exception as e:
    pass

from paddleocr import PaddleOCR
from backend.app.utils.logger import logger

# 设置环境变量以抑制 PaddlePaddle 的调试日志
os.environ['FLAGS_eager_delete_tensor_gb'] = '0.0'
os.environ['FLAGS_allocator_strategy'] = 'naive_best_fit'

import torch

class OcrHelper:
    """
    PaddleOCR 推理工具类
    """
    _instance = None
    _ocr = None
    _executor = ThreadPoolExecutor(max_workers=2) # OCR 比较吃资源，并发数设小一点
    _lock = threading.Lock() # 添加线程锁，防止多线程并发调用 PaddleOCR 预测器导致 Tensor 内存错误

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OcrHelper, cls).__new__(cls)
        return cls._instance

    @staticmethod
    def get_free_gpu_id() -> int:
        """
        获取显存占用最小的 GPU ID
        如果无 GPU 或 GPU 都不可用，返回 -1 (表示使用 CPU)
        """
        try:
            if not torch.cuda.is_available():
                logger.warning("未检测到可用 GPU，将使用 CPU 进行 OCR 推理")
                return -1
            
            device_count = torch.cuda.device_count()
            max_free_memory = 0
            best_gpu_id = -1
            
            for i in range(device_count):
                # 获取当前显存剩余量 (byte)
                # 注意: 这里使用 torch 的接口来简单判断
                # 也可以调用 pynvml 获取更精确的显存信息
                try:
                    free_mem = torch.cuda.mem_get_info(i)[0]
                    if free_mem > max_free_memory:
                        max_free_memory = free_mem
                        best_gpu_id = i
                except Exception as e:
                    logger.warning(f"获取 GPU {i} 信息失败: {e}")
            
            if best_gpu_id != -1:
                logger.info(f"选择 GPU {best_gpu_id} (剩余显存: {max_free_memory / 1024**3:.2f} GB)")
                return best_gpu_id
            else:
                return -1

        except Exception as e:
            logger.warning(f"GPU 检测失败: {e}，将回退到 CPU")
            return -1

    @classmethod
    def release_memory(cls):
        """
        释放显存/内存
        """
        if cls._ocr is not None:
            del cls._ocr
            cls._ocr = None
            
        # 强制垃圾回收
        import gc
        gc.collect()
        
        # 释放显存
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
        logger.info("PaddleOCR 内存/显存已释放")

    @classmethod
    def get_status(cls):
        """
        获取 OCR 服务状态
        """
        return {
            "loaded": cls._ocr is not None,
            "gpu_id": cls.get_free_gpu_id()
        }

    @classmethod
    def initialize(cls, use_angle_cls: bool = True, lang: str = 'ch', use_gpu: bool = True):
        if cls._ocr is None:
            try:
                logger.info(f"正在初始化 PaddleOCR (GPU={use_gpu})...")
                
                # 1. 自动选择设备
                gpu_id = -1
                if use_gpu:
                    gpu_id = cls.get_free_gpu_id()
                
                real_use_gpu = (gpu_id != -1)
                
                # use_gpu=False 默认使用CPU，如果环境支持GPU会自动切换或需显式指定
                cls._ocr = PaddleOCR(
                    use_angle_cls=use_angle_cls, 
                    lang=lang, 
                    use_gpu=real_use_gpu,  # 显式控制
                    gpu_id=gpu_id if real_use_gpu else 0, 
                    show_log=False 
                )
                
                # 如果使用 GPU，设置环境变量 (这应该在 import paddle 之前设置，但这里尝试兼容)
                if real_use_gpu:
                    try:
                        import paddle
                        # 再次确认设备设置
                        # paddle.device.set_device(f'gpu:{gpu_id}')
                    except:
                        pass
                
                logger.success(f"PaddleOCR 初始化成功 (设备: {'GPU ' + str(gpu_id) if real_use_gpu else 'CPU'})")
            except Exception as e:
                logger.error(f"PaddleOCR 初始化失败: {e}")
                raise e

    @classmethod
    def _predict_sync(cls, image_path: str) -> List[Dict[str, Any]]:
        """
        同步 OCR 识别 (运行在线程池中)
        """
        if cls._ocr is None:
            # 懒加载
            cls.initialize()
            
        # 增加锁保护，防止并发调用导致 Paddle 内部 Tensor 状态异常
        with cls._lock:
            try:
                # 检查文件是否存在且大小不为0
                if not os.path.exists(image_path) or os.path.getsize(image_path) == 0:
                    logger.error(f"OCR输入文件无效: {image_path}")
                    return []

                # result = [ [ [box], (text, score) ], ... ]
                # PaddleOCR 返回的结构比较复杂，是一个列表的列表
                result = cls._ocr.ocr(image_path, cls=True)
                
                output = []
                if not result:
                    return output
    
                # 兼容性处理：PaddleOCR 返回格式在不同版本可能不同
                # 有时是 [ [res1, res2] ]，有时是 [res1, res2] (如果只有一张图)
                # 这里的 result 通常是 list of lists
                
                # 如果 result[0] 是 None (未检测到)
                if result[0] is None:
                    return output
                    
                for line in result[0]:
                     # line 结构: [ [[x1,y1], [x2,y2], [x3,y3], [x4,y4]], ('text', 0.99) ]
                     if not line: continue
                     
                     box = line[0]
                     text_info = line[1]
                     output.append({
                         "text": text_info[0],
                         "confidence": float(text_info[1]),
                         "box": box
                     })
                return output
            except Exception as e:
                logger.error(f"OCR推理异常: {e}")
                # 不要抛出异常，而是返回空结果，避免整个请求崩溃
                return []
                # raise e

    @classmethod
    async def predict(cls, image_path: str) -> List[Dict[str, Any]]:
        """
        异步 OCR 预测入口
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            cls._executor, 
            cls._predict_sync, 
            image_path
        )
