#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/yolo_utils.py
# 作者：whf
# 日期：2026-01-26
# 描述：YOLO 模型推理工具类 (单例模式 + 线程池并发)

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, List
from ultralytics import YOLO
from backend.app.utils.logger import logger

class YoloHelper:
    """
    YOLO 模型推理工具类
    """
    _instance = None
    _model = None
    _executor = ThreadPoolExecutor(max_workers=4)  # 限制并发数，避免显存/CPU爆炸

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(YoloHelper, cls).__new__(cls)
        return cls._instance

    @classmethod
    def load_model(cls, model_path: str, device: str = None):
        """
        加载 YOLO 模型
        :param model_path: 模型路径
        :param device: 设备 ('cpu', '0', '1' 等), 默认为 None (自动)
        """
        if cls._model is None:
            try:
                # 兼容 path 为 Path 对象或字符串
                path = Path(model_path) if isinstance(model_path, str) else model_path
                if not path.exists():
                    logger.error(f"YOLO模型文件不存在: {path}")
                    raise FileNotFoundError(f"Model not found: {path}")
                
                logger.info(f"正在加载YOLO模型: {path} (device={device})...")
                cls._model = YOLO(str(path))
                
                # 如果指定了 device，可以在这里进行 warm up 或者 fuse
                # Ultralytics YOLO 在 predict 时指定 device 更灵活，但也可以预热
                # 这里简单做个预热
                # cls._model.to(device) if device else None
                
                logger.success(f"YOLO模型加载成功: {path.name}")
            except Exception as e:
                logger.error(f"YOLO模型加载失败: {e}")
                raise e

    @classmethod
    def get_status(cls):
        """
        获取模型加载状态
        """
        return {
            "loaded": cls._model is not None,
            "info": str(cls._model.overrides) if cls._model else None
        }

    @classmethod
    def _predict_sync(cls, image_path: str, conf: float = 0.25) -> List[Dict[str, Any]]:
        """
        同步预测方法 (运行在线程池中)
        """
        if cls._model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        
        try:
            results = cls._model.predict(source=image_path, conf=conf, verbose=False)
            output = []
            
            # 解析结果
            for result in results:
                # 类别名称映射
                names = result.names
                
                # 检测框
                for box in result.boxes:
                    cls_id = int(box.cls[0])
                    output.append({
                        "class_id": cls_id,
                        "class_name": names[cls_id],
                        "confidence": float(box.conf[0]),
                        "bbox": box.xyxy[0].tolist() # [x1, y1, x2, y2]
                    })
            return output
        except Exception as e:
            logger.error(f"YOLO推理异常: {e}")
            raise e

    @classmethod
    async def predict(cls, image_path: str, conf: float = 0.25) -> List[Dict[str, Any]]:
        """
        异步预测入口
        """
        loop = asyncio.get_running_loop()
        # 在线程池中执行阻塞的推理操作
        return await loop.run_in_executor(
            cls._executor, 
            cls._predict_sync, 
            image_path, 
            conf
        )
