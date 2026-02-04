import torch
import os
import gc
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from backend.app.utils.logger import logger
from anyio import to_thread

# 尝试导入 modelscope 相关库 (可选依赖)
try:
    # 优先尝试从 transformers 导入模型类 (更通用)
    from transformers import Qwen2_5_VLForConditionalGeneration, Qwen3VLForConditionalGeneration, AutoProcessor
    from qwen_vl_utils import process_vision_info
    _MODELSCOPE_AVAILABLE = True
except ImportError:
    try:
        # Fallback if Qwen3 is not available
        from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
        from qwen_vl_utils import process_vision_info
        Qwen3VLForConditionalGeneration = None
        _MODELSCOPE_AVAILABLE = True
    except ImportError:
        _MODELSCOPE_AVAILABLE = False
    logger.warning("⚠️ transformers 或 qwen_vl_utils 未安装，ModelScopeUtils 功能受限")

class ModelScopeUtils:
    """
    ModelScope 模型通用工具类 (管理本地 ModelScope 模型加载与推理)
    支持: 
    - 多GPU自动选择 (按显存空闲)
    - 显存自动卸载 (避免OOM)
    - 异步队列锁 (防止推理冲突)
    """
    _instances = {} # 缓存不同模型的实例 (model_name -> {"model": ..., "processor": ..., "device": ...})
    _inference_lock = asyncio.Lock() # 全局推理锁，防止并发推理导致显存爆炸或模型切换冲突
    
    # 默认模型路径映射 (可扩展)
    # 格式: "ShortName": "Relative/Path/To/Model"
    _MODEL_PATHS = {
        "Qwen3-VL-4B-Instruct": "Qwen/Qwen3-VL-4B-Instruct",
        "Qwen3-VL-8B-Instruct": "Qwen/Qwen3-VL-8B-Instruct",
        "Qwen/Qwen3-VL-4B-Instruct": "Qwen/Qwen3-VL-4B-Instruct",
        "Qwen/Qwen3-VL-8B-Instruct": "Qwen/Qwen3-VL-8B-Instruct"
    }

    @classmethod
    def get_model_path(cls, model_name: str) -> str:
        """
        获取模型绝对路径 (支持自动发现)
        """
        base_path = Path(__file__).parent.parent.parent / "app" / "models"
        
        # 1. 查表
        relative_path = cls._MODEL_PATHS.get(model_name)
        
        # 2. 如果表中没有，尝试自动发现
        if not relative_path:
            # 如果传入的是 namespace/model_name 格式，直接尝试拼接
            if "/" in model_name:
                parts = model_name.split("/")
                if len(parts) >= 2:
                    potential_path = base_path / parts[0] / parts[1]
                    if potential_path.exists():
                        return str(potential_path)

            logger.info(f"正在自动扫描查找模型: {model_name} ...")
            relative_path = cls._scan_and_find_model(model_name)
            if relative_path:
                logger.success(f"已自动定位模型路径: {relative_path}")
                # 缓存结果
                cls._MODEL_PATHS[model_name] = relative_path
        
        if not relative_path:
            # 如果是 full id 且不存在，返回预期的路径以便后续下载
            if "/" in model_name:
                 return str(base_path / model_name)
            return ""
            
        return str(base_path / relative_path)
    
    @classmethod
    def _scan_and_find_model(cls, model_name: str) -> Optional[str]:
        """
        扫描 models 目录查找匹配的模型路径
        """
        base_path = Path(__file__).parent.parent.parent / "app" / "models"
        if not base_path.exists():
            return None
            
        # 1. 精确匹配目录名
        # 遍历所有子目录寻找 config.json
        for root, dirs, files in os.walk(base_path):
            if "config.json" in files:
                abs_path = Path(root)
                # 检查目录名是否匹配 model_name
                if abs_path.name.lower() == model_name.lower():
                    # 找到匹配，计算相对路径
                    rel_path = abs_path.relative_to(base_path)
                    return str(rel_path).replace("\\", "/")
                    
        return None
        
    @classmethod
    def check_model_exists(cls, model_name: str = "Qwen/Qwen3-VL-4B-Instruct") -> bool:
        """
        检查模型文件是否存在
        """
        path_str = cls.get_model_path(model_name)
        if not path_str:
            return False
        path = Path(path_str)
        return path.exists() and (path / "config.json").exists()

    @classmethod
    def _get_best_device(cls) -> str:
        """
        获取最佳计算设备 (优先选择空闲显存最大的 GPU)
        """
        if not torch.cuda.is_available():
            return "cpu"
        
        try:
            device_count = torch.cuda.device_count()
            if device_count == 1:
                return "cuda:0"
            
            # 多卡选择：选择剩余显存最大的卡
            max_free_memory = 0
            best_device_idx = 0
            
            for i in range(device_count):
                free_memory = torch.cuda.mem_get_info(i)[0]
                if free_memory > max_free_memory:
                    max_free_memory = free_memory
                    best_device_idx = i
            
            device_str = f"cuda:{best_device_idx}"
            logger.info(f"⚡ [GPU选择] 自动选择显存最充足设备: {device_str} (剩余: {max_free_memory / 1024**3:.2f} GB)")
            return device_str
            
        except Exception as e:
            logger.warning(f"获取最佳设备失败，回退到 cuda:0: {e}")
            return "cuda:0"
    
    @classmethod
    def unload_model(cls, model_name: str):
        """
        卸载指定模型以释放显存
        """
        if model_name in cls._instances:
            logger.info(f"🧹 正在卸载模型: {model_name}")
            del cls._instances[model_name]
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.success(f"模型 {model_name} 已卸载，显存已清理")
    
    @classmethod
    def _load_model(cls, model_name: str):
        """
        加载指定模型 (懒加载 + 自动显存管理)
        注意：必须在 _inference_lock 保护下调用
        """
        if not _MODELSCOPE_AVAILABLE:
            raise RuntimeError("请先安装 modelscope: pip install modelscope qwen-vl-utils")

        if model_name in cls._instances:
            return cls._instances[model_name]

        model_path = cls.get_model_path(model_name)
        if not cls.check_model_exists(model_name):
             # 自动下载
             logger.info(f"📥 ModelScope 模型未找到，开始下载: {model_name} -> {cls.BASE_MODEL_DIR}")
             try:
                 from modelscope.hub.snapshot_download import snapshot_download
                 # 下载到 backend/app/models
                 snapshot_download(model_name, cache_dir=str(cls.BASE_MODEL_DIR))
                 logger.success(f"✅ [{model_name}] 模型下载完成")
                 
                 # 重新获取路径 (以防万一)
                 model_path = cls.get_model_path(model_name)
             except Exception as e:
                 logger.error(f"❌ [{model_name}] 模型下载失败: {e}")
                 raise e

        try:
            # 策略：如果已加载其他模型，先卸载以释放显存 (单卡/资源受限场景)
            if cls._instances:
                logger.warning(f"⚠️ 资源受限: 正在卸载其他模型以加载 {model_name}...")
                for name in list(cls._instances.keys()):
                    # 如果需要同时运行多个模型，这里需要更复杂的策略
                    cls.unload_model(name)

            logger.info(f"正在加载 ModelScope 模型 [{model_name}]: {model_path}")
            
            # 智能选择设备
            device = cls._get_best_device()
            logger.info(f"[{model_name}] 使用设备: {device}")

            # 根据模型类型加载
            if "Qwen3-VL" in model_name:
                if Qwen3VLForConditionalGeneration is None:
                     raise ImportError("当前 transformers 版本不支持 Qwen3-VL")
                model_class = Qwen3VLForConditionalGeneration
            elif "Qwen2.5-VL" in model_name or "Qwen2-VL" in model_name:
                model_class = Qwen2_5_VLForConditionalGeneration
            else:
                 # Default fallback or error
                 raise NotImplementedError(f"尚未支持该模型类型的加载: {model_name}")

            # 使用 AutoModel 自动适配 Qwen2/2.5/3 VL
            model = model_class.from_pretrained(
                model_path,
                torch_dtype=torch.bfloat16 if "cuda" in device else torch.float32,
                # trust_remote_code=True, # 允许加载自定义代码
                ignore_mismatched_sizes=True,  # 允许忽略权重形状不匹配 (如微调头差异)
            ).to(device)
            processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
            
            cls._instances[model_name] = {
                "model": model,
                "processor": processor,
                "device": device
            }
            logger.success(f"[{model_name}] 加载成功!")
            return cls._instances[model_name]
            
        except Exception as e:
            logger.error(f"[{model_name}] 加载失败: {e}")
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            raise RuntimeError(f"Failed to load model {model_name}: {e}")

    @classmethod
    def _run_inference_sync(cls, model_name: str, messages: List[Dict[str, Any]], max_new_tokens: int, streamer=None) -> str:
        """
        同步执行推理逻辑 (将被运行在线程池中)
        """
        instance = cls._load_model(model_name)
        model = instance["model"]
        processor = instance["processor"]
        device = instance["device"]
        
        # Qwen-VL 特有处理逻辑
        if "Qwen" in model_name:
            # 1. 应用聊天模板
            text = processor.apply_chat_template(
                messages, 
                tokenize=False, 
                add_generation_prompt=True
            )
            
            # 2. 处理视觉信息
            image_inputs, video_inputs = process_vision_info(messages)
            
            # 3. 编码输入
            inputs = processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            )
            
            # 移至设备
            inputs = inputs.to(device)

            # Debug Log: Print Input Shapes
            logger.info(f"[{model_name}] Input Keys: {list(inputs.keys())}")
            if "pixel_values" in inputs:
                logger.info(f"[{model_name}] pixel_values shape: {inputs['pixel_values'].shape}")
            if "image_grid_thw" in inputs:
                logger.info(f"[{model_name}] image_grid_thw: {inputs['image_grid_thw']}")
            if "input_ids" in inputs:
                logger.info(f"[{model_name}] input_ids shape: {inputs['input_ids'].shape}")

            # 4. 生成
            logger.info(f"[{model_name}] 开始推理...")
            if streamer:
                # 使用 streamer 进行流式生成
                model.generate(**inputs, max_new_tokens=max_new_tokens, streamer=streamer)
                return "" # 流式模式下返回值由 streamer 处理，这里返回空或最后累积的文本
            else:
                generated_ids = model.generate(**inputs, max_new_tokens=max_new_tokens)
                
                # 5. 解码
                generated_ids_trimmed = [
                    out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
                ]
                
                output_text = processor.batch_decode(
                    generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
                )
                
                result = output_text[0]
                logger.info(f"[{model_name}] 推理完成: {result[:50]}...")
                return result
            
        return "Unsupported model architecture"

    @classmethod
    async def chat_completion_stream(
        cls, 
        messages: List[Dict[str, Any]], 
        model_name: str = "Qwen/Qwen3-VL-4B-Instruct",
        max_new_tokens: int = 512
    ):
        """
        执行对话推理 (异步流式)
        """
        from transformers import TextIteratorStreamer
        import threading

        # 加载模型 (获取 processor)
        # 注意: 这里需要在主线程加载，因为 load_model 可能涉及下载和 GPU 操作
        async with cls._inference_lock:
            instance = cls._load_model(model_name)
            processor = instance["processor"]
            
            # 创建 Streamer
            streamer = TextIteratorStreamer(processor, skip_prompt=True, skip_special_tokens=True)
            
            # 在新线程中运行 generate
            # 注意: generate 是阻塞的，必须在线程中运行，否则会阻塞 event loop 导致无法 yield
            thread = threading.Thread(
                target=cls._run_inference_sync, 
                kwargs={
                    "model_name": model_name,
                    "messages": messages,
                    "max_new_tokens": max_new_tokens,
                    "streamer": streamer
                }
            )
            thread.start()

            # 在主线程中 yield streamer 的输出
            # streamer 是一个迭代器，会阻塞等待新 token
            try:
                for new_text in streamer:
                    yield new_text
            except Exception as e:
                logger.error(f"流式生成异常: {e}")
                yield f"[ERROR: {str(e)}]"
            finally:
                thread.join()

    @classmethod
    async def chat_completion(
        cls, 
        messages: List[Dict[str, Any]], 
        model_name: str = "Qwen/Qwen3-VL-4B-Instruct",
        max_new_tokens: int = 512
    ) -> str:
        """
        执行对话推理 (异步队列 + 线程池)
        """
        # 使用锁确保同一时间只有一个模型操作在进行 (防止模型切换冲突)
        async with cls._inference_lock:
            try:
                # 将 CPU 密集型的加载和推理任务放入线程池执行，避免阻塞事件循环
                result = await to_thread.run_sync(
                    cls._run_inference_sync,
                    model_name,
                    messages,
                    max_new_tokens,
                    None # No streamer
                )
                return result
                
            except torch.cuda.OutOfMemoryError:
                logger.error(f"显存不足 (OOM) 执行模型: {model_name}")
                cls.unload_model(model_name)
                raise RuntimeError("GPU Out of Memory. Please try again later.")
            except Exception as e:
                logger.error(f"推理过程发生未知错误: {e}")
                raise e