#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：backend/app/scripts/ace_step_music_test.py
# 作者：wuhao
# 日期：2026-02-12 16:50:07
# 描述：ACE-Step1.5 音乐生成测试脚本（含存储、落库与飞书通知）

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Tuple

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from backend.app.config import settings
from backend.app.utils.logger import logger
from backend.app.utils.upload_utils import UploadUtils
from backend.app.utils.pg_utils import PGUtils
from backend.app.utils.feishu_utils import feishu_bot
from backend.app.routers.upload.upload_func import UserAudio


class AceStepMusicTester:
    """
    ACE-Step1.5 音乐生成测试类
    """

    def __init__(
        self,
        prompt: str,
        user_id: str,
        model_id: str,
        output_dir: Path,
        force_download: bool
    ):
        """
        初始化测试参数
        """
        self.prompt = prompt
        self.user_id = user_id
        self.model_id = model_id
        self.output_dir = output_dir
        self.model_dir = settings.BASE_DIR / "app" / "models" / "ACE-Step" / "Ace-Step1.5"
        self.force_download = force_download

    def _is_model_ready(self) -> bool:
        """
        检查模型是否已存在
        """
        if not self.model_dir.exists():
            return False
        for file_path in self.model_dir.rglob("*"):
            if file_path.is_file():
                return True
        return False

    def download_model(self) -> Path:
        """
        下载模型到本地目录
        """
        if self._is_model_ready() and not self.force_download:
            logger.info(f"模型已存在，跳过下载: {self.model_dir}")
            return self.model_dir
        try:
            from modelscope.hub.snapshot_download import snapshot_download
        except Exception as e:
            logger.error(f"模型下载失败，缺少 modelscope 依赖: {e}")
            raise e
        self.model_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"开始下载模型: {self.model_id}")
        snapshot_download(
            model_id=self.model_id,
            revision="master",
            local_dir=str(self.model_dir)
        )
        logger.success(f"模型下载完成: {self.model_dir}")
        return self.model_dir

    def _resolve_task_name(self) -> str:
        """
        获取可用的 ModelScope 任务名称
        """
        try:
            from modelscope.utils.constant import Tasks
            if hasattr(Tasks, "text_to_music"):
                return Tasks.text_to_music
            if hasattr(Tasks, "text2music"):
                return Tasks.text2music
        except Exception:
            pass
        return "text2music"

    def generate_music(self) -> Tuple[Path, int]:
        """
        执行文本生成音乐推理并保存音频
        """
        try:
            from modelscope.pipelines import pipeline
        except Exception as e:
            logger.error(f"模型推理失败，缺少 modelscope pipeline 依赖: {e}")
            raise e
        task_name = self._resolve_task_name()
        logger.info(f"开始加载推理管线: {task_name}")
        pipe = pipeline(task=task_name, model=str(self.model_dir))
        logger.info(f"开始生成音乐，提示词: {self.prompt}")
        result = pipe(self.prompt)
        audio_data, sample_rate = self._extract_audio_result(result)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"ace_step_{uuid.uuid4().hex}.wav"
        output_path = self.output_dir / file_name
        self._save_audio(output_path, audio_data, sample_rate)
        logger.success(f"音乐生成完成: {output_path}")
        return output_path, sample_rate

    def _extract_audio_result(self, result: Any) -> Tuple[Any, int]:
        """
        解析推理结果中的音频与采样率
        """
        sample_rate = 44100
        audio_data = result
        if isinstance(result, dict):
            for key in ["output_wav", "wav", "audio", "output", "result"]:
                if key in result:
                    audio_data = result[key]
                    break
            for key in ["sample_rate", "sr"]:
                if key in result and result[key]:
                    sample_rate = int(result[key])
                    break
        if isinstance(audio_data, tuple) and len(audio_data) == 2:
            audio_data, sample_rate = audio_data
        return audio_data, sample_rate

    def _save_audio(self, output_path: Path, audio_data: Any, sample_rate: int) -> None:
        """
        保存音频为 wav 文件
        """
        try:
            import soundfile as sf
        except Exception as e:
            logger.error(f"保存音频失败，缺少 soundfile 依赖: {e}")
            raise e
        if isinstance(audio_data, (str, Path)):
            src_path = Path(audio_data)
            if src_path.exists():
                output_path.write_bytes(src_path.read_bytes())
                return
        if isinstance(audio_data, (bytes, bytearray)):
            output_path.write_bytes(bytes(audio_data))
            return
        sf.write(str(output_path), audio_data, samplerate=sample_rate)

    def _get_duration(self, audio_path: Path) -> float:
        """
        计算音频时长
        """
        try:
            import soundfile as sf
            info = sf.info(str(audio_path))
            return float(info.duration)
        except Exception as e:
            logger.warning(f"读取音频时长失败: {e}")
            return 0.0

    async def upload_and_record(self, audio_path: Path, sample_rate: int) -> Dict[str, Any]:
        """
        上传音频并记录到数据库
        """
        audio_bytes = audio_path.read_bytes()
        url, object_key, size = await UploadUtils.save_from_bytes(
            audio_bytes,
            audio_path.name,
            module="music",
            content_type="audio/wav"
        )
        duration = self._get_duration(audio_path)
        session_factory = PGUtils.get_session_factory()
        async with session_factory() as session:
            record = UserAudio(
                user_id=self.user_id,
                filename=audio_path.name,
                s3_key=object_key,
                url=url,
                size=size,
                duration=duration,
                mime_type="audio/wav",
                module="music",
                source="generated",
                prompt=self.prompt,
                text_content=self.prompt,
                meta_data={
                    "model_id": self.model_id,
                    "sample_rate": sample_rate,
                    "local_path": str(audio_path)
                }
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
        return {
            "url": url,
            "object_key": object_key,
            "size": size,
            "duration": duration
        }

    def notify_feishu(self, payload: Dict[str, Any]) -> None:
        """
        发送飞书通知
        """
        url = payload.get("url", "")
        duration = payload.get("duration", 0.0)
        content = (
            "🎵 音乐生成完成\n"
            f"提示词: {self.prompt}\n"
            f"模型: {self.model_id}\n"
            f"时长: {duration:.2f}s\n"
            f"地址: {url}"
        )
        feishu_bot.send_webhook_message(content)

    async def run(self) -> None:
        """
        执行完整流程
        """
        self.download_model()
        audio_path, sample_rate = self.generate_music()
        payload = await self.upload_and_record(audio_path, sample_rate)
        self.notify_feishu(payload)
        logger.success(f"流程完成: {json.dumps(payload, ensure_ascii=False)}")


def parse_args() -> argparse.Namespace:
    """
    解析命令行参数
    """
    parser = argparse.ArgumentParser(description="ACE-Step1.5 音乐生成测试脚本")
    parser.add_argument(
        "--prompt",
        type=str,
        default="女性 流行音乐，清亮女声，现代流行编曲",
        help="生成提示词"
    )
    parser.add_argument(
        "--user_id",
        type=str,
        default="system",
        help="入库用户ID"
    )
    parser.add_argument(
        "--model_id",
        type=str,
        default="ACE-Step/Ace-Step1.5",
        help="ModelScope 模型ID"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=str(settings.BASE_DIR / "temp" / "music"),
        help="本地输出目录"
    )
    parser.add_argument(
        "--force_download",
        action="store_true",
        help="强制重新下载模型"
    )
    return parser.parse_args()


def main() -> None:
    """
    主入口
    """
    args = parse_args()
    tester = AceStepMusicTester(
        prompt=args.prompt,
        user_id=args.user_id,
        model_id=args.model_id,
        output_dir=Path(args.output_dir),
        force_download=args.force_download
    )
    asyncio.run(tester.run())


if __name__ == "__main__":
    main()
