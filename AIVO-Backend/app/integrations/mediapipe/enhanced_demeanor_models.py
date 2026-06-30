"""
增强版仪态分析数据模型 - 支持时序统计
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime


# ============ 1. 视频帧级数据 ============

@dataclass
class EyeState:
    """眼部状态（单帧）"""
    left_eye_openness: float = 1.0   # 左眼睁开度 0-1
    right_eye_openness: float = 1.0  # 右眼睁开度 0-1
    avg_eye_openness: float = 1.0    # 平均睁开度
    is_blinking: bool = False        # 是否正在眨眼
    gaze_direction: str = "center"   # 视线方向: left/right/center/up/down
    gaze_offset_x: float = 0.0       # 视线水平偏移 -1~1
    gaze_offset_y: float = 0.0       # 视线垂直偏移 -1~1


@dataclass
class HeadPoseStats:
    """头部姿态统计（单帧）"""
    yaw: float = 0.0      # 偏航角 - 左右转头（度）
    pitch: float = 0.0    # 俯仰角 - 上下点头（度）
    roll: float = 0.0     # 翻滚角 - 歪头（度）
    is_stable: bool = True  # 姿态是否稳定

    # 时序状态
    is_looking_down: bool = False   # 是否低头
    is_looking_up: bool = False     # 是否仰头
    is_turning_left: bool = False   # 是否向左转头
    is_turning_right: bool = False  # 是否向右转头
    is_tilting: bool = False        # 是否歪头


@dataclass
class FacialExpression:
    """面部表情（单帧）"""
    happiness: float = 0.0      # 高兴 0-100
    sadness: float = 0.0         # 悲伤 0-100
    anger: float = 0.0           # 愤怒 0-100
    surprise: float = 0.0        # 惊讶 0-100
    fear: float = 0.0            # 恐惧 0-100
    disgust: float = 0.0          # 厌恶 0-100
    neutral: float = 100.0       # 中性 0-100
    dominant: str = "neutral"     # 主表情类型
    is_negative: bool = False    # 是否为负面情绪
    negative_duration_ms: float = 0.0  # 负面情绪持续时长累计


@dataclass
class BodyPosture:
    """肢体姿态（单帧）"""
    shoulder_distance_ratio: float = 0.0  # 肩膀距离/画面宽度（驼背检测）
    is_leaning_forward: bool = False      # 是否前倾
    is_leaning_back: bool = False         # 是否后仰
    is_sitting_up: bool = True            # 是否坐直
    arm_crossed: bool = False              # 是否抱臂
    body_sway: float = 0.0                # 身体晃动幅度
    hand_movement: float = 0.0            # 手部动作幅度
    has_excessive_hand_motion: bool = False  # 是否有过度手部动作


@dataclass
class VideoFrameData:
    """单帧视频数据"""
    timestamp_ms: int = 0              # 时间戳（毫秒）
    frame_index: int = 0              # 帧序号

    # 人脸检测
    face_detected: bool = False
    face_count: int = 0
    face_blur_score: float = 100.0     # 清晰度 0-100
    face_size_ratio: float = 0.0       # 人脸占画面比例
    confidence: float = 0.0            # 检测置信度

    # 子模块
    head_pose: Optional[HeadPoseStats] = None
    eye_state: Optional[EyeState] = None
    expression: Optional[FacialExpression] = None
    body_posture: Optional[BodyPosture] = None

    def to_dict(self) -> dict:
        """转换为字典（用于序列化）"""
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "VideoFrameData":
        """从字典创建"""
        head_pose = None
        if d.get("head_pose"):
            head_pose = HeadPoseStats(**d["head_pose"])

        eye_state = None
        if d.get("eye_state"):
            eye_state = EyeState(**d["eye_state"])

        expression = None
        if d.get("expression"):
            expression = FacialExpression(**d["expression"])

        body_posture = None
        if d.get("body_posture"):
            body_posture = BodyPosture(**d["body_posture"])

        return cls(
            timestamp_ms=d.get("timestamp_ms", 0),
            frame_index=d.get("frame_index", 0),
            face_detected=d.get("face_detected", False),
            face_count=d.get("face_count", 0),
            face_blur_score=d.get("face_blur_score", 100.0),
            face_size_ratio=d.get("face_size_ratio", 0.0),
            confidence=d.get("confidence", 0.0),
            head_pose=head_pose,
            eye_state=eye_state,
            expression=expression,
            body_posture=body_posture,
        )


# ============ 2. 音频帧级数据 ============

@dataclass
class AudioFrameData:
    """单段音频数据"""
    timestamp_ms: int = 0              # 时间戳（毫秒）
    duration_ms: int = 0              # 音频片段时长（毫秒）
    text: str = ""                    # 识别文本
    words: list = field(default_factory=list)  # 分词信息 [{"word": "Hello", "start": 0.0, "end": 0.5}]

    # 声学特征
    volume: float = 0.0               # 音量 RMS 0-1
    volume_db: float = -60.0          # 音量分贝
    is_silent: bool = True            # 是否静音
    silence_duration_ms: int = 0       # 静音时长

    # 语言特征
    char_count: int = 0               # 字符数
    speech_rate: float = 0.0           # 即时语速（字/秒）

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AudioFrameData":
        return cls(**d)


# ============ 3. 时序统计结果 ============

@dataclass
class HeadPoseStatistics:
    """头部姿态时序统计"""
    total_duration_ms: int = 0              # 总时长
    valid_frames: int = 0                   # 有效帧数

    # 低头
    total_looking_down_ms: int = 0          # 低头总时长
    looking_down_episodes: list = field(default_factory=list)  # [{"start": 0, "end": 5000}]
    avg_looking_down_duration_ms: float = 0.0

    # 仰头
    total_looking_up_ms: int = 0
    looking_up_episodes: list = field(default_factory=list)
    avg_looking_up_duration_ms: float = 0.0

    # 左右偏转
    total_turning_left_ms: int = 0          # 左转总时长
    total_turning_right_ms: int = 0         # 右转总时长
    turning_left_count: int = 0              # 左转频次
    turning_right_count: int = 0            # 右转频次
    turning_episodes: list = field(default_factory=list)  # [{"direction": "left", "start": 0, "end": 3000}]

    # 歪头
    total_tilting_ms: int = 0
    tilting_episodes: list = field(default_factory=list)

    # 稳定性
    stable_frames: int = 0
    stability_rate: float = 1.0             # 稳定性比率

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EyeStatistics:
    """眼部状态时序统计"""
    total_duration_ms: int = 0
    valid_frames: int = 0

    # 眨眼
    total_blinks: int = 0                   # 总眨眼次数
    blink_frequency: float = 0.0            # 眨眼频率（次/分钟）
    avg_blink_duration_ms: float = 0.0      # 平均眨眼时长
    blink_episodes: list = field(default_factory=list)  # [{"start": 0, "end": 200}]

    # 视线偏移
    total_gaze_off_center_ms: int = 0      # 视线偏离中心总时长
    gaze_off_center_episodes: list = field(default_factory=list)
    gaze_left_ms: int = 0                  # 视线偏左时长
    gaze_right_ms: int = 0                 # 视线偏右时长
    gaze_up_ms: int = 0                    # 视线偏上时长
    gaze_down_ms: int = 0                  # 视线偏下时长

    # 闭眼走神
    total_eyes_closed_ms: int = 0          # 闭眼总时长（排除眨眼）
    eyes_closed_episodes: list = field(default_factory=list)  # 长闭眼 > 500ms
    avg_eyes_closed_duration_ms: float = 0.0

    # 眨眼频率分段
    blink_rate_segments: list = field(default_factory=list)  # [{"start": 0, "end": 60000, "count": 15}]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExpressionStatistics:
    """面部表情时序统计"""
    total_duration_ms: int = 0
    valid_frames: int = 0

    # 各表情占比
    happiness_ratio: float = 0.0           # 高兴占比 0-1
    sadness_ratio: float = 0.0
    anger_ratio: float = 0.0
    surprise_ratio: float = 0.0
    fear_ratio: float = 0.0
    disgust_ratio: float = 0.0
    neutral_ratio: float = 1.0

    # 主表情
    dominant_expression: str = "neutral"
    dominant_time_ratio: float = 0.0

    # 负面情绪
    negative_ratio: float = 0.0            # 负面情绪占比
    total_negative_duration_ms: int = 0
    negative_episodes: list = field(default_factory=list)  # [{"emotion": "anger", "start": 0, "end": 5000}]
    longest_negative_episode_ms: int = 0
    negative_episode_count: int = 0

    # 微笑
    smiling_ratio: float = 0.0            # 微笑占比
    genuine_smile_ratio: float = 0.0       # 真诚微笑占比

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BodyStatistics:
    """肢体动作时序统计"""
    total_duration_ms: int = 0
    valid_frames: int = 0

    # 抱臂
    total_arm_crossed_ms: int = 0
    arm_crossed_episodes: list = field(default_factory=list)
    arm_crossed_ratio: float = 0.0

    # 驼背
    total_hunchback_ms: int = 0
    hunchback_episodes: list = field(default_factory=list)
    hunchback_ratio: float = 0.0

    # 身体晃动
    total_body_sway_ms: int = 0
    sway_amplitude_avg: float = 0.0
    sway_amplitude_max: float = 0.0
    sway_episodes: list = field(default_factory=list)  # 明显晃动片段

    # 手部小动作
    total_hand_motion_ms: int = 0
    hand_motion_count: int = 0             # 手部动作次数
    excessive_hand_motion_ms: int = 0      # 过度手部动作时长
    hand_motion_episodes: list = field(default_factory=list)

    # 坐姿综合
    proper_posture_ratio: float = 1.0     # 端正坐姿占比
    poor_posture_ratio: float = 0.0       # 不良姿势占比

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AudioStatistics:
    """音频特征时序统计"""
    total_duration_ms: int = 0
    speech_duration_ms: int = 0            # 有效语音时长
    silence_duration_ms: int = 0           # 静音总时长

    # 语速
    avg_speaking_rate: float = 0.0         # 平均语速（字/秒）
    min_speaking_rate: float = 0.0
    max_speaking_rate: float = 0.0
    speaking_rate_segments: list = field(default_factory=list)  # [{"start": 0, "end": 30000, "rate": 5.0}]

    # 停顿
    total_pauses: int = 0                 # 总停顿次数
    avg_pause_duration_ms: float = 0.0
    pause_episodes: list = field(default_factory=list)  # [{"start": 5000, "end": 5500}]

    # 卡顿（长停顿）
    total_hesitations: int = 0            # 卡顿次数
    total_hesitation_duration_ms: int = 0
    hesitation_episodes: list = field(default_factory=list)  # > 1500ms 的停顿
    avg_hesitation_duration_ms: float = 0.0

    # 音量
    avg_volume_db: float = -60.0
    volume_variance: float = 0.0           # 音量波动
    volume_segments: list = field(default_factory=list)  # 音量变化段

    # 静音分析
    long_silences: int = 0                 # 长静音次数（> 3秒）
    silence_ratio: float = 0.0             # 静音占比

    def to_dict(self) -> dict:
        return asdict(self)


# ============ 4. 综合报告 ============

@dataclass
class ComprehensiveDemeanorReport:
    """综合仪态报告 - 面试结束时的最终输出"""

    # 元信息
    session_id: str = ""
    interview_start_time: str = ""         # ISO 格式
    interview_end_time: str = ""
    total_duration_ms: int = 0
    valid_video_frames: int = 0
    valid_audio_segments: int = 0

    # 各维度时序统计
    head_pose_stats: Optional[HeadPoseStatistics] = None
    eye_stats: Optional[EyeStatistics] = None
    expression_stats: Optional[ExpressionStatistics] = None
    body_stats: Optional[BodyStatistics] = None
    audio_stats: Optional[AudioStatistics] = None

    # ============ 评分维度 ============
    # 头部姿态评分
    head_pose_score: float = 70.0          # 0-100
    head_pose_breakdown: dict = field(default_factory=dict)

    # 眼部/眼神评分
    eye_contact_score: float = 70.0
    eye_contact_breakdown: dict = field(default_factory=dict)

    # 表情管理评分
    expression_score: float = 70.0
    expression_breakdown: dict = field(default_factory=dict)

    # 肢体仪态评分
    body_posture_score: float = 70.0
    body_posture_breakdown: dict = field(default_factory=dict)

    # 语音表达评分
    speech_score: float = 70.0
    speech_breakdown: dict = field(default_factory=dict)

    # ============ 综合评分 ============
    demeanor_total_score: float = 70.0    # 仪态总分
    demeanor_grade: str = "B"             # A/B/C/D/E

    # ============ 大模型评语 ============
    llm_overall_comment: str = ""         # 整体评语
    llm_strengths: list = field(default_factory=list)     # 优点
    llm_weaknesses: list = field(default_factory=list)    # 不足
    llm_suggestions: list = field(default_factory=list)   # 改进建议

    # ============ 大模型详细评分（新格式） ============
    # 仪态专项得分（0-30分）- 头部、眼神、表情、肢体
    llm_posture_score: float = 0.0
    # 语言表达专项得分（0-30分）- 语速、停顿、流畅度
    llm_speech_score: float = 0.0
    # 问答内容专业度得分（0-40分）- 回答准确性、专业深度
    llm_content_score: float = 0.0
    # 大模型计算的总分（0-100分）
    llm_total_score: float = 0.0

    # ============ 分项问题列表 ============
    llm_posture_issues: list = field(default_factory=list)      # 仪态问题
    llm_speech_issues: list = field(default_factory=list)       # 语音问题
    llm_content_issues: list = field(default_factory=list)      # 内容问题

    # ============ 分项改进建议 ============
    llm_posture_suggestions: list = field(default_factory=list)   # 仪态建议
    llm_speech_suggestions: list = field(default_factory=list)    # 语音建议
    llm_content_suggestions: list = field(default_factory=list)   # 内容建议

    # ============ 原始数据摘要 ============
    raw_video_frames_count: int = 0
    raw_audio_segments_count: int = 0

    def to_dict(self) -> dict:
        """转换为字典"""
        d = {
            "session_id": self.session_id,
            "interview_start_time": self.interview_start_time,
            "interview_end_time": self.interview_end_time,
            "total_duration_ms": self.total_duration_ms,
            "valid_video_frames": self.valid_video_frames,
            "valid_audio_segments": self.valid_audio_segments,
            "head_pose_stats": self.head_pose_stats.to_dict() if self.head_pose_stats else {},
            "eye_stats": self.eye_stats.to_dict() if self.eye_stats else {},
            "expression_stats": self.expression_stats.to_dict() if self.expression_stats else {},
            "body_stats": self.body_stats.to_dict() if self.body_stats else {},
            "audio_stats": self.audio_stats.to_dict() if self.audio_stats else {},
            "head_pose_score": self.head_pose_score,
            "head_pose_breakdown": self.head_pose_breakdown,
            "eye_contact_score": self.eye_contact_score,
            "eye_contact_breakdown": self.eye_contact_breakdown,
            "expression_score": self.expression_score,
            "expression_breakdown": self.expression_breakdown,
            "body_posture_score": self.body_posture_score,
            "body_posture_breakdown": self.body_posture_breakdown,
            "speech_score": self.speech_score,
            "speech_breakdown": self.speech_breakdown,
            "demeanor_total_score": self.demeanor_total_score,
            "demeanor_grade": self.demeanor_grade,
            "llm_overall_comment": self.llm_overall_comment,
            "llm_strengths": self.llm_strengths,
            "llm_weaknesses": self.llm_weaknesses,
            "llm_suggestions": self.llm_suggestions,
            # 新增详细评分字段
            "llm_posture_score": self.llm_posture_score,
            "llm_speech_score": self.llm_speech_score,
            "llm_content_score": self.llm_content_score,
            "llm_total_score": self.llm_total_score,
            "llm_posture_issues": self.llm_posture_issues,
            "llm_speech_issues": self.llm_speech_issues,
            "llm_content_issues": self.llm_content_issues,
            "llm_posture_suggestions": self.llm_posture_suggestions,
            "llm_speech_suggestions": self.llm_speech_suggestions,
            "llm_content_suggestions": self.llm_content_suggestions,
            "raw_video_frames_count": self.raw_video_frames_count,
            "raw_audio_segments_count": self.raw_audio_segments_count,
        }
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ComprehensiveDemeanorReport":
        """从字典创建"""
        head_pose_stats = None
        if d.get("head_pose_stats"):
            head_pose_stats = HeadPoseStatistics(**d["head_pose_stats"])

        eye_stats = None
        if d.get("eye_stats"):
            eye_stats = EyeStatistics(**d["eye_stats"])

        expression_stats = None
        if d.get("expression_stats"):
            expression_stats = ExpressionStatistics(**d["expression_stats"])

        body_stats = None
        if d.get("body_stats"):
            body_stats = BodyStatistics(**d["body_stats"])

        audio_stats = None
        if d.get("audio_stats"):
            audio_stats = AudioStatistics(**d["audio_stats"])

        return cls(
            session_id=d.get("session_id", ""),
            interview_start_time=d.get("interview_start_time", ""),
            interview_end_time=d.get("interview_end_time", ""),
            total_duration_ms=d.get("total_duration_ms", 0),
            valid_video_frames=d.get("valid_video_frames", 0),
            valid_audio_segments=d.get("valid_audio_segments", 0),
            head_pose_stats=head_pose_stats,
            eye_stats=eye_stats,
            expression_stats=expression_stats,
            body_stats=body_stats,
            audio_stats=audio_stats,
            head_pose_score=d.get("head_pose_score", 70.0),
            head_pose_breakdown=d.get("head_pose_breakdown", {}),
            eye_contact_score=d.get("eye_contact_score", 70.0),
            eye_contact_breakdown=d.get("eye_contact_breakdown", {}),
            expression_score=d.get("expression_score", 70.0),
            expression_breakdown=d.get("expression_breakdown", {}),
            body_posture_score=d.get("body_posture_score", 70.0),
            body_posture_breakdown=d.get("body_posture_breakdown", {}),
            speech_score=d.get("speech_score", 70.0),
            speech_breakdown=d.get("speech_breakdown", {}),
            demeanor_total_score=d.get("demeanor_total_score", 70.0),
            demeanor_grade=d.get("demeanor_grade", "B"),
            llm_overall_comment=d.get("llm_overall_comment", ""),
            llm_strengths=d.get("llm_strengths", []),
            llm_weaknesses=d.get("llm_weaknesses", []),
            llm_suggestions=d.get("llm_suggestions", []),
            # 新增详细评分字段
            llm_posture_score=d.get("llm_posture_score", 0.0),
            llm_speech_score=d.get("llm_speech_score", 0.0),
            llm_content_score=d.get("llm_content_score", 0.0),
            llm_total_score=d.get("llm_total_score", 0.0),
            llm_posture_issues=d.get("llm_posture_issues", []),
            llm_speech_issues=d.get("llm_speech_issues", []),
            llm_content_issues=d.get("llm_content_issues", []),
            llm_posture_suggestions=d.get("llm_posture_suggestions", []),
            llm_speech_suggestions=d.get("llm_speech_suggestions", []),
            llm_content_suggestions=d.get("llm_content_suggestions", []),
            raw_video_frames_count=d.get("raw_video_frames_count", 0),
            raw_audio_segments_count=d.get("raw_audio_segments_count", 0),
        )
