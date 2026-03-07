"""
文件名：backend/app/utils/qwen_asr_utils.py
作者：zcl & Gemini
日期：2026-03-06
描述：Qwen-ASR 语音识别工具 (懒加载实现)
"""
import torch
import asyncio
from transformers import AutoModel, AutoProcessor
from qwen_asr import Qwen3ASRModel
from backend.app.config import settings
from backend.app.utils.logger import logger

class QwenASRClient:
    _instance = None
    _asr_model = None
    _is_loading = False
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(QwenASRClient, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        # 构造函数保持轻量，不执行任何重操作
        pass

    async def initialize(self):
        """异步初始化模型，只有在未初始化时才执行。"""
        if self._initialized:
            return
        if self._is_loading:
            logger.info("Qwen-ASR 模型正在加载中，请稍候...")
            while self._is_loading:
                await asyncio.sleep(1)
            return

        self._is_loading = True
        try:
            logger.info("🚀 正在初始化 Qwen-ASR 模型...")
            device = settings.QWEN_ASR_DEVICE
            if "cuda" in device and not torch.cuda.is_available():
                logger.warning(f"⚠️ 配置的设备 {device} 不可用, 将尝试使用默认cuda设备或CPU")
                device = "cuda" if torch.cuda.is_available() else "cpu"
            model_path = settings.QWEN_ASR_MODEL_PATH
            
            if not model_path.exists():
                logger.error(f"❌ Qwen-ASR 模型路径不存在: {model_path}")
                raise FileNotFoundError(f"Qwen-ASR model path not found: {model_path}")

            processor = AutoProcessor.from_pretrained(
                model_path, trust_remote_code=True, fix_mistral_regex=True
            )
            model = AutoModel.from_pretrained(
                model_path, trust_remote_code=True
            ).to(device)

            self._asr_model = Qwen3ASRModel(backend="transformers", model=model, processor=processor)
            self._initialized = True
            logger.success(f"✅ Qwen-ASR 模型初始化成功，使用设备: {device}")

        except Exception as e:
            logger.error(f"❌ 加载 Qwen-ASR 模型失败: {e}", exc_info=True)
            self._initialized = False
            raise
        finally:
            self._is_loading = False

    async def transcribe(self, audio_path: str) -> dict:
        """对单个音频文件进行语音识别，如果模型未加载则先进行初始化。"""
        if not self._initialized:
            await self.initialize()
        
        if not self._asr_model:
             raise RuntimeError("QwenASRClient 未成功初始化，无法执行转写。")

        logger.info(f"🎤 开始使用 Qwen-ASR 对文件进行转写: {audio_path}")
        try:
            result = self._asr_model.transcribe(audio_path)
            if result and isinstance(result, list) and len(result) > 0:
                transcription = result[0]
                logger.info(f"转写成功: {audio_path}")
                return {
                    "language": transcription.language,
                    "text": transcription.text,
                }
            else:
                logger.warning(f"Qwen-ASR 未返回有效的转写结果: {audio_path}")
                return {"language": "unknown", "text": ""}
        except Exception as e:
            logger.error(f"Qwen-ASR 文件转写失败: {audio_path}, 错误: {e}", exc_info=True)
            raise

# 全局单例实例 (此时只创建对象，不加载模型)
qwen_asr_client = QwenASRClient()
