"""Whisper 语音识别服务"""

import logging
import os
from pathlib import Path
from typing import Optional

import whisper

logger = logging.getLogger(__name__)

# 项目本地模型目录
MODELS_DIR = Path(__file__).parent.parent.parent.parent / "models" / "whisper"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


class WhisperService:
    """Whisper 语音识别服务"""

    def __init__(self, model_name: str = "base"):
        self.model_name = model_name
        self._model: Optional[object] = None

    def _get_model(self):
        """懒加载模型，优先从本地加载，不存在则下载到本地"""
        if self._model is None:
            local_path = MODELS_DIR / f"{self.model_name}.pt"
            logger.info(f"加载 Whisper 模型: {self.model_name}")
            logger.info(f"模型本地路径: {local_path}")

            if local_path.exists():
                logger.info(f"从本地加载模型: {local_path}")
                self._model = whisper.load_model(str(local_path))
            else:
                # 首次使用，从网络下载到本地目录
                logger.info(f"本地模型不存在，从网络下载到: {MODELS_DIR}")
                self._model = whisper.load_model(self.model_name, download_root=str(MODELS_DIR))

        return self._model

    async def transcribe(
        self,
        audio_path: str | Path,
        language: str = "zh",
        task: str = "transcribe",
    ) -> dict:
        """
        将音频转为文字

        Args:
            audio_path: 音频文件路径
            language: 语言代码，zh=中文
            task: transcribe 或 translate

        Returns:
            {
                "text": "转写文本",
                "language": "zh",
                "segments": [{"start": 0.0, "end": 5.0, "text": "..."}],
            }
        """
        model = self._get_model()
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        result = model.transcribe(
            str(audio_path),
            language=language,
            task=task,
        )

        return {
            "text": result["text"].strip(),
            "language": result.get("language", language),
            "segments": [
                {
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg["text"].strip(),
                }
                for seg in result.get("segments", [])
            ],
        }

    async def transcribe_audio_data(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str = "zh",
    ) -> dict:
        """
        直接转写音频数据（bytes）

        Args:
            audio_data: 原始音频字节数据
            sample_rate: 采样率
            language: 语言代码
        """
        import tempfile

        model = self._get_model()

        # 写入临时文件
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            import wave
            f: IO
            f: wave.Wave_write
            # 写入 WAV 头
            with wave.open(f, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)
            temp_path = f.name

        try:
            result = await self.transcribe(temp_path, language=language)
        finally:
            Path(temp_path).unlink(missing_ok=True)

        return result


whisper_service = WhisperService()
