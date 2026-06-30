"""
增强版音频分析器 - 语音特征提取
功能：语速计算、停顿检测、卡顿检测、音量波动分析
"""

import logging
from typing import Optional, List, Tuple
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)

# 检测阈值常量
SILENCE_THRESHOLD_DB = -40.0          # 静音判定阈值（dB）
HESITATION_THRESHOLD_MS = 1500        # 卡顿判定阈值（毫秒）
LONG_SILENCE_THRESHOLD_MS = 3000      # 长静音判定阈值（毫秒）
MIN_PAUSE_DURATION_MS = 300           # 最小停顿判定时长（毫秒）

# 语速评估
SLOW_SPEECH_RATE = 3.0               # 慢速阈值（字/秒）
FAST_SPEECH_RATE = 8.0               # 快速阈值（字/秒）
NORMAL_SPEECH_RATE = 5.0             # 正常语速（字/秒）


@dataclass
class SpeechSegment:
    """语音片段"""
    start_ms: int
    end_ms: int
    text: str
    word_count: int
    duration_ms: int
    speech_rate: float  # 字/秒
    avg_volume_db: float
    is_pause: bool = False


@dataclass
class AudioAnalysisResult:
    """音频分析结果"""
    total_duration_ms: int = 0
    speech_duration_ms: int = 0
    silence_duration_ms: int = 0

    # 语速
    avg_speaking_rate: float = 0.0    # 平均语速（字/秒）
    min_speaking_rate: float = 0.0
    max_speaking_rate: float = 0.0

    # 停顿
    total_pauses: int = 0            # 总停顿次数
    avg_pause_duration_ms: float = 0.0
    pause_segments: List[dict] = None  # [{"start": 0, "end": 500}]

    # 卡顿
    total_hesitations: int = 0       # 卡顿次数
    total_hesitation_duration_ms: int = 0
    hesitation_segments: List[dict] = None
    avg_hesitation_duration_ms: float = 0.0

    # 静音
    long_silences: int = 0           # 长静音次数
    silence_ratio: float = 0.0       # 静音占比

    # 音量
    avg_volume_db: float = -60.0
    volume_variance: float = 0.0      # 音量波动
    volume_segments: List[dict] = None  # 音量变化段

    # 原始数据
    speech_segments: List[dict] = None  # 所有语音片段

    def __post_init__(self):
        if self.pause_segments is None:
            self.pause_segments = []
        if self.hesitation_segments is None:
            self.hesitation_segments = []
        if self.volume_segments is None:
            self.volume_segments = []
        if self.speech_segments is None:
            self.speech_segments = []


class EnhancedAudioAnalyzer:
    """
    增强版音频分析器

    功能：
    1. 语速计算（字/秒）
    2. 停顿检测（区分正常停顿和卡顿）
    3. 卡顿检测（长停顿 > 1.5s）
    4. 音量波动分析
    5. Whisper 识别结果后处理
    """

    def __init__(self):
        # 状态
        self._silence_buffer: List[float] = []  # 近期音量缓存
        self._silence_start_ms: Optional[int] = None
        self._last_speech_end_ms: int = 0
        self._session_speech_segments: List[SpeechSegment] = []

    def reset(self):
        """重置分析器状态（用于新会话）"""
        self._silence_buffer = []
        self._silence_start_ms = None
        self._last_speech_end_ms = 0
        self._session_speech_segments = []

    def analyze_from_whisper_result(
        self,
        whisper_result: dict,
        sample_rate: int = 16000,
    ) -> AudioAnalysisResult:
        """
        从 Whisper 识别结果分析音频特征

        Args:
            whisper_result: Whisper transcribe 返回结果
                {
                    "text": "...",
                    "segments": [{"start": 0.0, "end": 5.0, "text": "..."}],
                }
            sample_rate: 采样率

        Returns:
            AudioAnalysisResult: 分析结果
        """
        import re

        segments = whisper_result.get("segments", [])
        if not segments:
            return AudioAnalysisResult()

        total_duration_ms = int(float(segments[-1]["end"]) * 1000) if segments else 0

        speech_segments = []
        pause_segments = []
        hesitation_segments = []
        volume_segments = []

        total_speech_duration_ms = 0
        total_pause_duration_ms = 0
        total_speech_chars = 0

        prev_end_ms = 0

        for seg in segments:
            start_ms = int(float(seg["start"]) * 1000)
            end_ms = int(float(seg["end"]) * 1000)
            text = seg.get("text", "").strip()

            # 计算字数（中文按字符，英文按单词）
            # 粗略估算：中文1字=1词，英文1词≈1.5字
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
            english_words = len(re.findall(r'[a-zA-Z]+', text))
            word_count = chinese_chars + int(english_words * 1.5)

            duration_ms = end_ms - start_ms
            speech_rate = (word_count / (duration_ms / 1000)) if duration_ms > 0 else 0

            speech_segments.append({
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text": text,
                "word_count": word_count,
                "duration_ms": duration_ms,
                "speech_rate": speech_rate,
            })

            total_speech_duration_ms += duration_ms
            total_speech_chars += word_count

            # 检测停顿
            if prev_end_ms > 0:
                pause_duration = start_ms - prev_end_ms

                if pause_duration >= MIN_PAUSE_DURATION_MS:
                    pause_seg = {
                        "start": prev_end_ms,
                        "end": start_ms,
                        "duration_ms": pause_duration,
                    }
                    pause_segments.append(pause_seg)
                    total_pause_duration_ms += pause_duration

                    # 卡顿判定（> 1.5s）
                    if pause_duration >= HESITATION_THRESHOLD_MS:
                        hesitation_segments.append(pause_seg)

            prev_end_ms = end_ms

        # 计算静音总时长（总时长 - 语音时长）
        silence_duration_ms = total_duration_ms - total_speech_duration_ms

        # 统计长静音（> 3s）
        long_silences = sum(1 for p in pause_segments if p["duration_ms"] >= LONG_SILENCE_THRESHOLD_MS)

        # 计算平均语速
        avg_speech_rate = total_speech_chars / (total_speech_duration_ms / 1000) if total_speech_duration_ms > 0 else 0

        # 计算语速范围
        rates = [s["speech_rate"] for s in speech_segments if s["speech_rate"] > 0]
        min_rate = min(rates) if rates else 0
        max_rate = max(rates) if rates else 0

        # 计算停顿统计
        total_pauses = len(pause_segments)
        avg_pause_duration = total_pause_duration_ms / total_pauses if total_pauses > 0 else 0

        # 计算卡顿统计
        total_hesitations = len(hesitation_segments)
        total_hesitation_duration = sum(h["duration_ms"] for h in hesitation_segments)
        avg_hesitation_duration = total_hesitation_duration / total_hesitations if total_hesitations > 0 else 0

        # 简化音量分析（使用相对值）
        # 实际项目中应该传入原始音频数据进行音量分析
        avg_volume_db = -30.0  # 假设正常音量
        volume_variance = 10.0  # 假设波动

        result = AudioAnalysisResult(
            total_duration_ms=total_duration_ms,
            speech_duration_ms=total_speech_duration_ms,
            silence_duration_ms=silence_duration_ms,
            avg_speaking_rate=round(avg_speech_rate, 2),
            min_speaking_rate=round(min_rate, 2),
            max_speaking_rate=round(max_rate, 2),
            total_pauses=total_pauses,
            avg_pause_duration_ms=round(avg_pause_duration, 1),
            pause_segments=pause_segments,
            total_hesitations=total_hesitations,
            total_hesitation_duration_ms=total_hesitation_duration,
            hesitation_segments=hesitation_segments,
            avg_hesitation_duration_ms=round(avg_hesitation_duration, 1),
            long_silences=long_silences,
            silence_ratio=round(silence_duration_ms / total_duration_ms, 3) if total_duration_ms > 0 else 0,
            avg_volume_db=avg_volume_db,
            volume_variance=volume_variance,
            volume_segments=volume_segments,
            speech_segments=speech_segments,
        )

        return result

    def analyze_audio_data(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        whisper_model=None,
    ) -> AudioAnalysisResult:
        """
        直接从音频数据（bytes）分析

        Args:
            audio_data: 原始音频字节数据
            sample_rate: 采样率
            whisper_model: Whisper 模型实例（可选，用于语音识别）

        Returns:
            AudioAnalysisResult: 分析结果
        """
        import tempfile
        import wave
        from pathlib import Path

        # 保存为临时 WAV 文件
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            with wave.open(f, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)
            temp_path = f.name

        try:
            # 调用 Whisper 识别
            if whisper_model is None:
                # 懒加载 Whisper
                import whisper
                model = whisper.load_model("base")
            else:
                model = whisper_model

            result = model.transcribe(temp_path, language="zh")
            return self.analyze_from_whisper_result(result, sample_rate)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def estimate_speech_quality(self, result: AudioAnalysisResult) -> dict:
        """
        基于分析结果评估语音质量

        Returns:
            dict: {
                "score": float,  # 0-100
                "speed_score": float,  # 语速得分
                "fluency_score": float,  # 流畅度得分
                "volume_score": float,  # 音量得分
                "issues": list,  # 问题列表
            }
        """
        score = 100.0
        speed_score = 100.0
        fluency_score = 100.0
        volume_score = 100.0
        issues = []

        total_duration = result.total_duration_ms / 1000  # 转为秒
        if total_duration == 0:
            return {"score": 0, "speed_score": 0, "fluency_score": 0, "volume_score": 0, "issues": ["无音频数据"]}

        # 1. 语速评估
        avg_rate = result.avg_speaking_rate
        if avg_rate < SLOW_SPEECH_RATE:
            speed_score = max(0, 50 + (avg_rate / SLOW_SPEECH_RATE) * 50)
            issues.append(f"语速偏慢 ({avg_rate:.1f} 字/秒)")
        elif avg_rate > FAST_SPEECH_RATE:
            speed_score = max(0, 100 - (avg_rate - FAST_SPEECH_RATE) * 15)
            if avg_rate > FAST_SPEECH_RATE * 1.5:
                issues.append(f"语速过快 ({avg_rate:.1f} 字/秒)")
        else:
            speed_score = 100.0

        # 2. 流畅度评估（基于停顿和卡顿）
        pause_ratio = result.total_pauses / (total_duration / 60) if total_duration > 0 else 0  # 次/分钟
        hesitation_ratio = result.total_hesitations

        if pause_ratio > 20:  # > 20次/分钟 = 过多次停顿
            fluency_score -= min(30, (pause_ratio - 20) * 2)
            issues.append(f"停顿过于频繁 ({pause_ratio:.0f} 次/分钟)")

        if hesitation_ratio > 5:
            fluency_score -= min(30, hesitation_ratio * 5)
            issues.append(f"卡顿较多 ({hesitation_ratio} 次)")

        # 长静音惩罚
        if result.long_silences > 2:
            fluency_score -= result.long_silences * 5
            issues.append(f"存在长沉默 ({result.long_silences} 次 > 3秒)")

        fluency_score = max(0, fluency_score)

        # 3. 音量评估
        if result.volume_variance > 20:
            volume_score = max(50, 100 - (result.volume_variance - 20) * 2)
            issues.append("音量波动较大")

        # 综合得分
        score = speed_score * 0.3 + fluency_score * 0.5 + volume_score * 0.2
        score = round(max(0, min(100, score)), 1)

        return {
            "score": score,
            "speed_score": round(speed_score, 1),
            "fluency_score": round(fluency_score, 1),
            "volume_score": round(volume_score, 1),
            "issues": issues,
        }

    def get_talking_speed_feedback(self, result: AudioAnalysisResult) -> str:
        """获取语速反馈"""
        rate = result.avg_speaking_rate
        if rate < SLOW_SPEECH_RATE:
            return f"语速偏慢，建议适当加快，保持在 {SLOW_SPEECH_RATE}-{FAST_SPEECH_RATE} 字/秒较为理想"
        elif rate > FAST_SPEECH_RATE:
            return f"语速偏快，建议适当放慢，保持在 {SLOW_SPEECH_RATE}-{FAST_SPEECH_RATE} 字/秒较为理想"
        else:
            return "语速适中，表达流畅自然"

    def get_fluency_feedback(self, result: AudioAnalysisResult) -> str:
        """获取流畅度反馈"""
        feedback_parts = []

        if result.total_hesitations > 3:
            feedback_parts.append(f"存在较多卡顿（{result.total_hesitations}次），建议提前理清思路再回答")
        elif result.total_hesitations > 0:
            feedback_parts.append(f"偶尔有轻微卡顿（{result.total_hesitations}次），整体表达流畅")

        if result.long_silences > 0:
            feedback_parts.append(f"存在{result.long_silences}次长沉默（>3秒），面试中应避免长时间停顿")

        if result.total_pauses > 20:
            feedback_parts.append(f"停顿次数较多（{result.total_pauses}次），可能影响表达的连贯性")

        if not feedback_parts:
            return "表达流畅，思路清晰连贯"

        return "；".join(feedback_parts)


# 全局实例
enhanced_audio_analyzer = EnhancedAudioAnalyzer()
