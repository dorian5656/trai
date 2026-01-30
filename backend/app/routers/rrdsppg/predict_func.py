#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/rrdsppg/predict_func.py
# 作者：whf
# 日期：2026-01-26
# 描述：人人都是品牌官 - 智能预测逻辑 (Func)

from pathlib import Path
import shutil
import uuid
import os
import torch
import paddle
from fastapi import UploadFile
from typing import Optional
from backend.app.utils.logger import logger
from backend.app.utils.yolo_utils import YoloHelper
from backend.app.utils.ocr_utils import OcrHelper
from backend.app.routers.monitor.ai_models_func import ModelManager
from backend.app.utils.download_utils import DownloadUtils
from backend.app.config import settings
import asyncio
from difflib import SequenceMatcher
import re
import string
import os

# 临时文件存储路径
TEMP_DIR = settings.BASE_DIR / "temp" / "rrdsppg"

class PredictManager:
    """
    预测逻辑管理
    """

    @staticmethod
    async def initialize():
        """
        服务启动时加载模型和检查环境
        """
        # 1. 检查并创建临时文件夹
        if not TEMP_DIR.exists():
            TEMP_DIR.mkdir(parents=True, exist_ok=True)
            logger.info(f"已创建临时文件上传目录: {TEMP_DIR}")
        else:
            logger.info(f"临时文件上传目录已存在: {TEMP_DIR}")

        # 2. 检查测试图片
        # 注意：测试图片通常在 backend/temp 下，不在 rrdsppg 子目录
        # 这里为了兼容性，可以保留对上级目录的检查，或者不再强求测试图片
        pass

        # 3. 初始化模型服务并同步
        try:
            await ModelManager.initialize()
        except Exception as e:
            logger.error(f"模型服务初始化失败: {e}")

        # 4. 加载 YOLO 模型 (基于数据库配置)
        try:
            yolo_config = await ModelManager.get_model_config("heart_like.pt")
            if yolo_config and yolo_config.get("is_enabled"):
                default_path = settings.BASE_DIR / "app" / "models" / "heart_like" / "heart_like.pt"
                yolo_path = Path(yolo_config.get("path") or default_path)
                if yolo_path.exists():
                    use_gpu = yolo_config.get("use_gpu", True)
                    device = "0" if use_gpu and torch.cuda.is_available() else "cpu"
                    YoloHelper.load_model(str(yolo_path), device=device)
                    await ModelManager.update_model_status("heart_like.pt", "loaded")
                else:
                    logger.warning(f"YOLO模型文件未找到: {yolo_path}")
                    await ModelManager.update_model_status("heart_like.pt", "error", "File not found")
            else:
                logger.info("YOLO模型未启用或配置不存在，跳过加载")
        except Exception as e:
            logger.error(f"YOLO模型加载异常: {e}")
            await ModelManager.update_model_status("heart_like.pt", "error", str(e))
            
        # 5. PaddleOCR 预热检查 (基于数据库配置)
        try:
            # OCR 目前是内置工具，没有对应的单一模型文件记录，这里假设它是一个通用服务
            # 或者我们可以在 scan 时手动添加一个虚拟的 'ocr_service' 记录
            logger.info("正在进行 PaddleOCR 启动自检...")
            OcrHelper.initialize(use_gpu=True) # 默认尝试使用 GPU
            OcrHelper.release_memory() 
        except Exception as e:
            logger.critical(f"PaddleOCR 启动自检失败: {e}")
            # 必须抛出异常以终止服务启动，避免带病运行
            raise e

    @staticmethod
    def check_gpu():
        """
        检查系统 GPU 可用性 (Torch & Paddle)
        """
        # Torch Check
        torch_available = torch.cuda.is_available()
        torch_count = torch.cuda.device_count() if torch_available else 0
        torch_name = torch.cuda.get_device_name(0) if torch_available and torch_count > 0 else "N/A"
        
        # Paddle Check
        paddle_available = paddle.device.is_compiled_with_cuda()
        paddle_device = paddle.device.get_device()
        
        info = {
            "torch": {
                "available": torch_available,
                "device_count": torch_count,
                "device_name": torch_name,
                "version": torch.__version__
            },
            "paddle": {
                "available": paddle_available,
                "device": paddle_device,
                "version": paddle.__version__
            }
        }
        
        if torch_available or paddle_available:
            logger.info(f"GPU 检测通过: {info}")
        else:
            logger.warning(f"未检测到 GPU: {info}")
            
        return info

    @staticmethod
    async def predict_composite(request):
        """
        组合预测逻辑 (OCR + YOLO) - 视频号
        逻辑:
        1. 先进行 OCR 相似度比对
        2. 如果 OCR 相似度 > 0.55，则继续进行 YOLO 检测 (红心/点赞)
        3. 如果两者都满足，则相似度为 1.0，否则 0.0
        """
        # 确保目录存在
        if not TEMP_DIR.exists():
            TEMP_DIR.mkdir(parents=True, exist_ok=True)
            
        template_local_path = None
        target_local_path = None
        
        try:
            # --- 1. 下载图片 (OCR 和 YOLO 共用) ---
            download_tasks = [
                DownloadUtils.download_image(request.templatePath, TEMP_DIR),
                DownloadUtils.download_image(request.targetPath, TEMP_DIR)
            ]
            paths = await asyncio.gather(*download_tasks)
            template_local_path = paths[0]
            target_local_path = paths[1]
            
            if not template_local_path or not target_local_path:
                raise Exception("图片下载失败")
                
            # --- 2. 运行 OCR ---
            ocr_tasks = [
                OcrHelper.predict(template_local_path),
                OcrHelper.predict(target_local_path)
            ]
            ocr_results = await asyncio.gather(*ocr_tasks)
            
            # 计算 OCR 相似度
            # 复用 predict_ocr_url 中的清洗逻辑? 
            # 简单起见，这里先用未清洗的，或者如果需要清洗，需要提取 clean_text 函数
            # 为了保持一致性，我们把 clean_text 逻辑提取出来比较好，但为了不破坏现有结构，暂时内联复制一份核心逻辑
            
            text_template = "".join([item.get("text", "") for item in (ocr_results[0] or [])])
            text_target = "".join([item.get("text", "") for item in (ocr_results[1] or [])])
            
            # 获取清洗配置
            remove_letters = str(os.getenv("RRDSPPG_OCR_FILTER_REMOVE_LETTERS", "true")).lower() == "true"
            remove_digits = str(os.getenv("RRDSPPG_OCR_FILTER_REMOVE_DIGITS", "true")).lower() == "true"
            remove_punct = str(os.getenv("RRDSPPG_OCR_FILTER_REMOVE_PUNCTUATION", "true")).lower() == "true"
            remove_before_kw = os.getenv("RRDSPPG_OCR_FILTER_REMOVE_BEFORE_KEYWORD", "")
            remove_after_kw = os.getenv("RRDSPPG_OCR_FILTER_REMOVE_AFTER_KEYWORD", "")
            
            def clean_text_helper(text):
                if not text: return ""
                
                # 1. 移除字符 (英文字母、数字、标点) - 优先级调整：先移除干扰字符
                if remove_letters: text = re.sub(r'[a-zA-Z]', '', text)
                if remove_digits: text = re.sub(r'[0-9]', '', text)
                if remove_punct:
                    cn_punctuations = r"[！-～\u3000-\u303F\uFF00-\uFFEF\u2000-\u206F\u2E80-\u2EFF]"
                    text = re.sub(f'[{re.escape(string.punctuation)}]', '', text)
                    text = re.sub(cn_punctuations, '', text)
                    text = re.sub(r'\s+', '', text)
                
                # 2. 关键词截断 (后执行)
                if remove_before_kw:
                    kws = [k.strip() for k in remove_before_kw.split(",") if k.strip()]
                    for kw in kws:
                        if kw in text:
                            idx = text.find(kw)
                            if idx != -1: text = text[idx + len(kw):]
                if remove_after_kw:
                    kws = [k.strip() for k in remove_after_kw.split(",") if k.strip()]
                    for kw in kws:
                        if kw in text:
                            idx = text.find(kw)
                            if idx != -1: text = text[:idx]
                return text

            cleaned_template = clean_text_helper(text_template)
            cleaned_target = clean_text_helper(text_target)
            
            ocr_similarity = SequenceMatcher(None, cleaned_template, cleaned_target).ratio()
            logger.info(f"组合预测 - OCR相似度: {ocr_similarity}")
            
            # --- 3. 判断是否需要运行 YOLO ---
            # 条件: OCR 相似度 > 0.55
            yolo_match = False
            yolo_info = None # 用于 itzx 返回
            
            if ocr_similarity > 0.55:
                logger.info("OCR 相似度达标 (>0.55)，开始 YOLO 检测...")
                
                # 运行 YOLO (复用 YoloHelper)
                # 对模板进行 YOLO 检测提取必需类别
                required_classes = set()
                tpl_yolo_results = await YoloHelper.predict(template_local_path, conf=0.25)
                
                # 获取配置
                required_class_config = os.getenv("RRDSPPG_YOLO_REQUIRED_CLASSES", "红心,已点赞").split(",")
                required_class_config = [c.strip() for c in required_class_config if c.strip()]
                
                for res in tpl_yolo_results:
                    c_name = res.get("class_name")
                    if c_name in required_class_config:
                        required_classes.add(c_name)
                
                # 对目标进行 YOLO 检测
                target_yolo_results = await YoloHelper.predict(target_local_path, conf=0.25)
                target_classes = {r.get("class_name") for r in target_yolo_results}
                
                # 匹配逻辑 (子集匹配)
                if required_classes:
                    if required_classes.issubset(target_classes):
                        yolo_match = True
                else:
                    # 模板没检测到红心/点赞，是否默认为 True? 
                    # 根据之前逻辑：如果没有模板限制，只要检测到东西就算 1.0 -> 这里为了严谨，如果没有限制，算通过
                    if target_yolo_results:
                        yolo_match = True
                        
                yolo_info = {
                    "template_classes": list(required_classes),
                    "target_classes": list(target_classes),
                    "template_detections": tpl_yolo_results,
                    "target_detections": target_yolo_results
                }
                logger.info(f"YOLO 检测结果: Match={yolo_match}, Required={required_classes}, Target={target_classes}")
            else:
                logger.info("OCR 相似度未达标 (<=0.6)，跳过 YOLO 检测")
                
            # --- 4. 最终判定 ---
            # 只有当 OCR > 0.6 且 YOLO 匹配成功时，最终相似度为 1.0
            final_similarity = 1.0 if (ocr_similarity > 0.6 and yolo_match) else 0.0
            
            # --- 5. 格式化返回 (itzx) ---
            itzx = getattr(request, 'itzx', 0)
            if itzx is None: itzx = 0
            
            # itzx=2: 详细 debug 信息
            if itzx == 2:
                return {
                    "similarity_score": final_similarity,
                    "ocr": {
                        "similarity": ocr_similarity,
                        "template_text_clean": cleaned_template,
                        "target_text_clean": cleaned_target
                    },
                    "yolo": {
                        "match": yolo_match,
                        "details": yolo_info
                    }
                }
            
            # itzx=1: 合并信息
            elif itzx == 1:
                return {
                    "similarity_score": final_similarity,
                    "ocr_similarity": ocr_similarity,
                    "yolo_match": yolo_match,
                    "template_classes": yolo_info["template_classes"] if yolo_info else [],
                    "target_classes": yolo_info["target_classes"] if yolo_info else []
                }
                
            # itzx=0: 仅相似度
            else:
                return {
                    "similarity_score": final_similarity
                }

        except Exception as e:
            logger.error(f"组合预测失败: {e}")
            raise e
        finally:
            # 清理
            # 注意: 不再删除 TEMP_DIR 目录本身，只删除文件
            # 并且在删除前稍微等待一下，或者使用 ignore_errors=True
            if template_local_path and Path(template_local_path).exists():
                try: os.remove(template_local_path)
                except: pass
            if target_local_path and Path(target_local_path).exists():
                try: os.remove(target_local_path)
                except: pass

    @staticmethod
    async def predict_yolo(file: Optional[UploadFile], itzx: int = 0, targetPath: str = None, templatePath: str = None):
        """
        YOLO 预测逻辑 (支持文件对象或 URL)
        """
        # 设置默认置信度
        conf = 0.25 
        logger.info(f"YOLO预测请求: file={file.filename if file else 'None'}, targetPath={targetPath}, templatePath={templatePath}, itzx={itzx}")
        
        # 0. 如果提供了 templatePath (模板图片URL)，需要先通过 OCR 识别模板图片的关键词 (如"红心"或"已点赞")
        # 从而确定本次检测的目标类别。
        # 这里简化逻辑：用户指示"先看templatePath 这个提取出是红心还是点赞"
        # 假设我们通过 OCR 识别模板图片，发现包含 "红心" 或 "点赞" 相关的字样？
        # 或者也许这里是指 YOLO 检测模板图片？
        # 用户的描述："先看templatePath 这个提取出是红心还是点赞" -> 这听起来像分类或 OCR
        # "如果 有红心或者点赞 那么 targetPath 必须有红心的点赞" -> 这意味着 targetPath 的检测结果必须包含与 templatePath 匹配的类别
        
        # 解析：
        # 1. 识别 templatePath 的内容 (假设通过 OCR 或 YOLO)
        #    由于之前的 context 中 templatePath 是 OCR 用的，这里假设用户意图是通过 OCR 识别文字？
        #    但用户又说 "yolo 是这样的"，且提到了 "红心" (class_name)，这更像是 YOLO 的类别。
        #    可能意图是：对 templatePath 进行 YOLO 检测，看里面有什么类别 (红心/已点赞)。
        # 2. 对 targetPath 进行 YOLO 检测。
        # 3. 比较两者：如果 templatePath 有 "红心"，则 targetPath 也必须有 "红心"；如果 templatePath 有 "已点赞"，则 targetPath 也必须有 "已点赞"。
        # 4. 如果匹配，similarity_score = 1.0，否则 0.0。
        
        # 让我们先实现对 targetPath 的标准 YOLO 检测
        
        # 确保目录存在
        if not TEMP_DIR.exists():
            TEMP_DIR.mkdir(parents=True, exist_ok=True)
            
        temp_file_path = None
        temp_template_path = None # 如果需要检测模板
        
        try:
            # --- 1. 处理 targetPath 图片 (必须有) ---
            if file:
                # 方式A: 处理上传文件
                file_ext = os.path.splitext(file.filename)[1]
                temp_filename = f"{uuid.uuid4()}{file_ext}"
                temp_file_path = TEMP_DIR / temp_filename
                
                with open(temp_file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
            elif targetPath:
                # 方式B: 处理 URL 下载
                try:
                    downloaded_path_str = await DownloadUtils.download_image(targetPath, TEMP_DIR)
                    if not downloaded_path_str:
                        raise Exception("下载图片失败")
                    temp_file_path = Path(downloaded_path_str)
                except Exception as e:
                    logger.error(f"YOLO 图片下载失败: {targetPath}, error: {e}")
                    raise Exception(f"图片下载失败: {e}")
            else:
                raise Exception("必须提供 file (文件上传) 或 targetPath (图片URL)")
            
            # --- 2. 如果提供了 templatePath，也下载并检测 (用于确定目标类别) ---
            required_classes = set() # 必须包含的类别名称
            tpl_results = []
            if templatePath:
                try:
                    template_path_str = await DownloadUtils.download_image(templatePath, TEMP_DIR)
                    if template_path_str:
                        temp_template_path = Path(template_path_str)
                        # 对模板进行 YOLO 检测
                        tpl_results = await YoloHelper.predict(str(temp_template_path), conf=conf)
                        # 获取必需的分类列表
                        required_class_config = os.getenv("RRDSPPG_YOLO_REQUIRED_CLASSES", "红心,已点赞").split(",")
                        # 去除空格
                        required_class_config = [c.strip() for c in required_class_config if c.strip()]
                        
                        for res in tpl_results:
                            c_name = res.get("class_name")
                            if c_name in required_class_config:
                                required_classes.add(c_name)
                        logger.info(f"从模板提取的必需类别: {required_classes}")
                except Exception as e:
                    logger.warning(f"模板图片处理失败: {templatePath}, error: {e}")
                    # 如果模板处理失败，是否要报错？或者降级？暂时仅记录日志
            
            # --- 3. 对目标图片进行 YOLO 检测 ---
            results = await YoloHelper.predict(str(temp_file_path), conf=conf)
            
            # --- 4. 格式化返回结果 ---
            
            # 计算匹配状态
            target_classes = {r.get("class_name") for r in results}
            is_match = False
            if required_classes:
                # 必须包含所有必需类别 (子集关系)
                # 即 required_classes 必须是 target_classes 的子集
                if required_classes.issubset(target_classes):
                    is_match = True
            else:
                # 没有模板限制，只要检测到东西就算 1.0
                if results and len(results) > 0:
                    is_match = True
            
            similarity_score = 1.0 if is_match else 0.0

            # itzx=2: 返回详细的对比结果 (模板 vs 目标)
            if itzx == 2:
                return {
                    "similarity_score": similarity_score,
                    "template": {
                        "classes": list(required_classes),
                        "detections": tpl_results
                    },
                    "target": {
                        "classes": list(target_classes),
                        "detections": results
                    }
                }
                
            # itzx=1: 返回相似度 + 关键信息 (分类展示)
            elif itzx == 1:
                response_data = {
                    "similarity_score": similarity_score,
                    "template_classes": list(required_classes),
                    "target_classes": list(target_classes)
                }
                
                # 如果有匹配，返回最佳匹配项
                if is_match:
                    # 优先返回匹配上的那个类别
                    # 实际上用户需求变了：不再需要 best_match 字段
                    # "比如这个就不用要 best_match"
                    pass
                
                return response_data
           
            # itzx=0: 仅返回相似度
            else:
                return {
                    "similarity_score": similarity_score
                }
            
        except Exception as e:
            logger.error(f"YOLO预测失败: {e}")
            raise e
        finally:
            # 清理临时文件
            if temp_file_path and temp_file_path.exists():
                try: os.remove(temp_file_path)
                except: pass
            if temp_template_path and temp_template_path.exists():
                try: os.remove(temp_template_path)
                except: pass

    @staticmethod
    async def predict_ocr_url(request):
        """
        OCR 预测逻辑 (URL版本)
        """
        template_local_path = None
        target_local_path = None
        
        # 确保目录存在
        if not TEMP_DIR.exists():
            TEMP_DIR.mkdir(parents=True, exist_ok=True)
            
        try:
            # 1. 下载图片
            # 并发下载两张图片
            try:
                download_tasks = [
                    DownloadUtils.download_image(request.templatePath, TEMP_DIR),
                    DownloadUtils.download_image(request.targetPath, TEMP_DIR)
                ]
                
                # results顺序: template, target
                paths = await asyncio.gather(*download_tasks)
                template_local_path = paths[0]
                target_local_path = paths[1]
            except Exception as e:
                logger.warning(f"图片下载失败: {e}")
                itzx_val = getattr(request, 'itzx', 0)
                if itzx_val is None: itzx_val = 0
                
                error_msg = f"图片无法访问: {str(e)}"
                if itzx_val == 2:
                    return {
                        "similarity_score": 0.0,
                        "error": "ImageDownloadError",
                        "details": error_msg
                    }
                elif itzx_val == 1:
                    return {
                        "similarity_score": 0.0,
                        "error": error_msg
                    }
                else:
                    return {
                        "similarity_score": 0.0
                    }
            
            # 2. 并发进行 OCR 识别
            ocr_tasks = [
                OcrHelper.predict(template_local_path),
                OcrHelper.predict(target_local_path)
            ]
            
            ocr_results = await asyncio.gather(*ocr_tasks)
            
            # 3. 根据 itzx 参数返回不同结果
            # 1. 解析参数
            itzx_val = getattr(request, 'itzx', 0)
            if itzx_val is None:
                itzx_val = 0

            # 2. 文本处理 (合并)
            # 注意：这是计算相似度的基础
            text_template = "".join([item.get("text", "") for item in (ocr_results[0] or [])])
            text_target = "".join([item.get("text", "") for item in (ocr_results[1] or [])])
            
            # 3. 计算原始相似度 (Uncleaned)
            raw_similarity = SequenceMatcher(None, text_template, text_target).ratio()
            
            # 4. 计算阈值后分数 (业务规则: >0.55 则为 1.0)
            threshold_score = 1.0 if raw_similarity > 0.55 else 0.0

            # --- New Cleaning Logic (Applied globally for consistency if needed, but mainly for itzx=0 and 2) ---
            # 获取配置
            remove_letters = str(os.getenv("RRDSPPG_OCR_FILTER_REMOVE_LETTERS", "true")).lower() == "true"
            remove_digits = str(os.getenv("RRDSPPG_OCR_FILTER_REMOVE_DIGITS", "true")).lower() == "true"
            remove_punct = str(os.getenv("RRDSPPG_OCR_FILTER_REMOVE_PUNCTUATION", "true")).lower() == "true"
            remove_before_kw = os.getenv("RRDSPPG_OCR_FILTER_REMOVE_BEFORE_KEYWORD", "")
            remove_after_kw = os.getenv("RRDSPPG_OCR_FILTER_REMOVE_AFTER_KEYWORD", "")

            def clean_text(text):
                if not text: return ""
                
                # 1. 移除字符 (英文字母、数字、标点) - 优先级调整：先移除干扰字符
                # 这样可以避免 "详1情" 这种中间夹杂字符导致关键词匹配失败的情况
                
                # 1.1 移除英文字母 (a-z, A-Z)
                if remove_letters:
                    text = re.sub(r'[a-zA-Z]', '', text)
                # 1.2 移除数字 (0-9)
                if remove_digits:
                    text = re.sub(r'[0-9]', '', text)
                # 1.3 移除标点符号 (英文标点 + 中文标点 + 特殊符号)
                if remove_punct:
                    # 英文标点
                    text = re.sub(f'[{re.escape(string.punctuation)}]', '', text)
                    # 中文标点及特殊符号 (扩充范围)
                    # \u3000-\u303F: CJK 标点符号
                    # \uFF00-\uFFEF: 全角ASCII、全角标点
                    # \u2000-\u206F: 常用标点
                    # 额外添加: “ ” ‘ ’ · ★ √
                    cn_punctuations = r"[！-～\u3000-\u303F\uFF00-\uFFEF\u2000-\u206F\u2E80-\u2EFF·★√]"
                    text = re.sub(cn_punctuations, '', text)
                    # 再次清理可能残留的空格
                    text = re.sub(r'\s+', '', text)
                
                # 2. 关键词截断 (后执行)
                # 此时文本已经比较纯净，匹配成功率更高
                
                # 2.1 移除 remove_before_kw 之前的内容 (包含关键词)
                # 支持逗号分隔的多个关键词
                if remove_before_kw:
                    kws = [k.strip() for k in remove_before_kw.split(",") if k.strip()]
                    for kw in kws:
                        if kw in text:
                            idx = text.find(kw)
                            if idx != -1:
                                text = text[idx + len(kw):]

                # 2.2 移除 remove_after_kw 之后的内容 (包含关键词)
                if remove_after_kw:
                    kws = [k.strip() for k in remove_after_kw.split(",") if k.strip()]
                    for kw in kws:
                        if kw in text:
                            idx = text.find(kw)
                            if idx != -1:
                                text = text[:idx]

                return text

            # 对文本进行清洗并计算清洗后的相似度
            cleaned_template = clean_text(text_template)
            cleaned_target = clean_text(text_target)
            cleaned_raw_similarity = SequenceMatcher(None, cleaned_template, cleaned_target).ratio()
            cleaned_threshold_score = 1.0 if cleaned_raw_similarity > 0.55 else 0.0
            # -------------------------------------------------------------------------------------------

            # 5. 根据 itzx 构建响应
            if itzx_val == 1:
                # itzx=1: 返回清洗后的文本 + 基于清洗文本的相似度
                return {
                    "template_text": cleaned_template,
                    "target_text": cleaned_target,
                    "similarity_score": cleaned_threshold_score,
                    "raw_similarity": cleaned_raw_similarity
                }
            elif itzx_val == 2:
                # itzx=2: 返回原始文本 (未清洗)
                return {
                    "template_text_raw": text_template,
                    "target_text_raw": text_target,
                    "similarity_score": threshold_score,
                    "raw_similarity": raw_similarity
                }
            else:
                # 默认情况 (itzx=0 或其他未知值): 仅返回相似度分数
                # 修改：使用清洗后的相似度
                return {
                    "similarity_score": cleaned_threshold_score
                }
            
        except Exception as e:
            logger.error(f"OCR预测失败 (URL模式): {e}")
            raise e
        finally:
            # 清理临时目录
            # 修正: 不再删除整个目录，只删除当前请求下载的文件
            if template_local_path and Path(template_local_path).exists():
                try: os.remove(template_local_path)
                except: pass
            if target_local_path and Path(target_local_path).exists():
                try: os.remove(target_local_path)
                except: pass

    @staticmethod
    async def predict_ocr(file: UploadFile):
        """
        OCR 预测逻辑
        """
        # 确保目录存在
        if not TEMP_DIR.exists():
            TEMP_DIR.mkdir(parents=True, exist_ok=True)
            
        temp_file_path = None
        try:
            # 保存上传文件
            file_ext = os.path.splitext(file.filename)[1]
            temp_filename = f"{uuid.uuid4()}{file_ext}"
            temp_file_path = TEMP_DIR / temp_filename
            
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
                
            # 调用 OCR 工具类进行预测
            results = await OcrHelper.predict(str(temp_file_path))
            return results
            
        except Exception as e:
            logger.error(f"OCR预测失败: {e}")
            raise e
        finally:
            # 清理临时文件
            if temp_file_path and temp_file_path.exists():
                try:
                    os.remove(temp_file_path)
                except Exception as e:
                    logger.warning(f"临时文件清理失败: {e}")
