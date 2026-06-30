"""
仪态数据时序跟踪器 - 聚合与统计
功能：从大量帧级数据中计算时序统计，输出结构化报告
"""

import logging
from typing import Optional, List, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 检测阈值
LOOK_DOWN_PITCH_THRESHOLD = 15      # 低头角度阈值（度）
LOOK_UP_PITCH_THRESHOLD = -10       # 仰头角度阈值（度）
TURN_LEFT_YAW_THRESHOLD = 20       # 左转头角度阈值（度）
TURN_RIGHT_YAW_THRESHOLD = -20      # 右转头角度阈值（度）
TILT_ROLL_THRESHOLD = 10          # 歪头角度阈值（度）

# 眨眼相关
BLINK_MIN_DURATION_MS = 100        # 最小眨眼时长
BLINK_MAX_DURATION_MS = 400        # 最大眨眼时长
EYES_CLOSED_THRESHOLD = 0.15       # 闭眼判定阈值

# 视线偏移
GAZE_OFF_THRESHOLD = 0.15         # 视线偏移阈值

# 表情相关
NEGATIVE_EMOTION_MIN_DURATION_MS = 2000  # 负面情绪判定最小持续时长

# 肢体相关
HUNCHBACK_THRESHOLD = 0.3          # 驼背判定阈值
BODY_SWAY_THRESHOLD = 0.15         # 身体晃动阈值
HAND_MOTION_THRESHOLD = 0.5        # 手部动作阈值


class DemeanorTracker:
    """
    仪态数据时序跟踪器

    接收视频帧级数据流，实时聚合，面试结束时输出完整统计报告。

    使用方式：
    1. 面试开始 → reset()
    2. 每收到一帧 → append_video_frame(frame_data)
    3. 面试结束 → compute_final_statistics() → ComprehensiveDemeanorReport
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """重置跟踪器（面试开始时调用）"""
        self._video_frames: List = []       # 视频帧数据列表
        self._audio_segments: List = []    # 音频片段数据列表
        self._start_time_ms: int = 0       # 面试开始时间戳
        self._end_time_ms: int = 0         # 面试结束时间戳
        self._frame_count: int = 0         # 总帧数
        self._valid_frame_count: int = 0   # 有效帧数

        # 眨眼相关状态
        self._blink_list: List[Dict] = []  # [{"start": ms, "end": ms, "duration": ms}]
        self._current_blink_start: Optional[int] = None
        self._eyes_closed_start: Optional[int] = None
        self._last_eye_openness: float = 1.0

        # 视线相关状态
        self._gaze_off_start: Optional[int] = None
        self._current_gaze_direction: str = "center"

        # 表情相关状态
        self._current_emotion_start: Optional[int] = None
        self._current_emotion_type: str = "neutral"
        self._emotion_episodes: List[Dict] = []  # [{"emotion": str, "start": ms, "end": ms, "duration": ms}]
        self._negative_episodes: List[Dict] = []  # 负面情绪片段

        # 头部姿态相关状态
        self._current_head_state_start: Optional[int] = None
        self._current_head_state: str = "stable"
        self._head_state_episodes: Dict[str, List] = {
            "looking_down": [],
            "looking_up": [],
            "turning_left": [],
            "turning_right": [],
            "tilting": [],
        }

        # 肢体相关状态
        self._current_body_state_start: Optional[int] = None
        self._current_body_state: str = "proper"
        self._body_state_episodes: Dict[str, List] = {
            "hunchback": [],
            "arm_crossed": [],
            "swaying": [],
            "excessive_hand_motion": [],
        }

        # 音频相关状态
        self._silence_start: Optional[int] = None
        self._silence_episodes: List[Dict] = []

    def set_time_range(self, start_ms: int, end_ms: int):
        """设置面试时间范围"""
        self._start_time_ms = start_ms
        self._end_time_ms = end_ms

    def append_video_frame(self, frame_data) -> Dict:
        """
        追加一帧视频数据

        Args:
            frame_data: VideoFrameData 实例或 dict

        Returns:
            dict: 当前帧的分析摘要（用于实时反馈）
        """
        from app.integrations.mediapipe.enhanced_demeanor_models import VideoFrameData

        # 兼容 dict 或 dataclass
        if isinstance(frame_data, dict):
            frame_data = VideoFrameData.from_dict(frame_data)
        elif not isinstance(frame_data, VideoFrameData):
            raise TypeError(f"Expected VideoFrameData or dict, got {type(frame_data)}")

        self._video_frames.append(frame_data)
        self._frame_count += 1

        if not frame_data.face_detected:
            return {"face_detected": False}

        self._valid_frame_count += 1
        ts = frame_data.timestamp_ms

        # ========== 1. 眨眼检测 ==========
        self._track_blink(frame_data, ts)

        # ========== 2. 视线追踪 ==========
        self._track_gaze(frame_data, ts)

        # ========== 3. 表情追踪 ==========
        self._track_expression(frame_data, ts)

        # ========== 4. 头部姿态追踪 ==========
        self._track_head_pose(frame_data, ts)

        # ========== 5. 肢体姿态追踪 ==========
        self._track_body_posture(frame_data, ts)

        # 构建实时摘要
        summary = {
            "timestamp_ms": ts,
            "face_detected": True,
            "frame_index": self._frame_count,
            "head_pose": None,
            "eye_state": None,
            "expression": None,
            "body_posture": None,
        }

        if frame_data.head_pose:
            hp = frame_data.head_pose
            summary["head_pose"] = {
                "yaw": hp.yaw,
                "pitch": hp.pitch,
                "roll": hp.roll,
                "is_stable": hp.is_stable,
                "state": self._classify_head_state(hp),
            }

        if frame_data.eye_state:
            es = frame_data.eye_state
            summary["eye_state"] = {
                "avg_openness": es.avg_eye_openness,
                "is_blinking": es.is_blinking,
                "gaze_direction": es.gaze_direction,
            }

        if frame_data.expression:
            expr = frame_data.expression
            summary["expression"] = {
                "dominant": expr.dominant,
                "is_negative": expr.is_negative,
            }

        if frame_data.body_posture:
            bp = frame_data.body_posture
            summary["body_posture"] = {
                "is_sitting_up": bp.is_sitting_up,
                "arm_crossed": bp.arm_crossed,
            }

        return summary

    def append_audio_segment(self, segment_data) -> Dict:
        """
        追加一段音频数据

        Args:
            segment_data: AudioFrameData 实例或 dict

        Returns:
            dict: 当前片段的分析摘要
        """
        from app.integrations.mediapipe.enhanced_demeanor_models import AudioFrameData

        if isinstance(segment_data, dict):
            segment_data = AudioFrameData.from_dict(segment_data)
        elif not isinstance(segment_data, AudioFrameData):
            raise TypeError(f"Expected AudioFrameData or dict, got {type(segment_data)}")

        self._audio_segments.append(segment_data)

        ts = segment_data.timestamp_ms

        # 静音追踪
        if segment_data.is_silent:
            if self._silence_start is None:
                self._silence_start = ts
        else:
            if self._silence_start is not None:
                silence_duration = ts - self._silence_start
                self._silence_episodes.append({
                    "start": self._silence_start,
                    "end": ts,
                    "duration_ms": silence_duration,
                })
                self._silence_start = None

        return {
            "timestamp_ms": ts,
            "speech_rate": segment_data.speech_rate,
            "volume_db": segment_data.volume_db,
            "is_silent": segment_data.is_silent,
        }

    def _track_blink(self, frame_data, ts: int):
        """追踪眨眼"""
        eye_state = frame_data.eye_state
        if not eye_state:
            return

        avg_openness = eye_state.avg_eye_openness

        # 检测眨眼开始
        if avg_openness < EYES_CLOSED_THRESHOLD:
            if self._current_blink_start is None and self._last_eye_openness >= EYES_CLOSED_THRESHOLD:
                self._current_blink_start = ts

        # 检测眨眼结束
        elif self._current_blink_start is not None:
            blink_duration = ts - self._current_blink_start

            # 判定为眨眼（时长在合理范围内）
            if BLINK_MIN_DURATION_MS <= blink_duration <= BLINK_MAX_DURATION_MS:
                self._blink_list.append({
                    "start": self._current_blink_start,
                    "end": ts,
                    "duration_ms": blink_duration,
                })

            # 判定为闭眼走神（时长超过眨眼最大时长）
            elif blink_duration > BLINK_MAX_DURATION_MS:
                if self._eyes_closed_start is None:
                    self._eyes_closed_start = self._current_blink_start

            self._current_blink_start = None

        self._last_eye_openness = avg_openness

    def _track_gaze(self, frame_data, ts: int):
        """追踪视线方向"""
        eye_state = frame_data.eye_state
        if not eye_state:
            return

        direction = eye_state.gaze_direction
        offset_x = abs(eye_state.gaze_offset_x)
        offset_y = abs(eye_state.gaze_offset_y)

        # 判定视线是否偏离
        is_off = offset_x > GAZE_OFF_THRESHOLD or offset_y > GAZE_OFF_THRESHOLD

        if is_off:
            if self._gaze_off_start is None:
                self._gaze_off_start = ts
                self._current_gaze_direction = direction
        else:
            if self._gaze_off_start is not None:
                gaze_off_duration = ts - self._gaze_off_start
                # 只记录明显的长时间视线偏移
                if gaze_off_duration > 500:  # > 500ms
                    pass  # 可以添加视线偏移统计
                self._gaze_off_start = None

    def _track_expression(self, frame_data, ts: int):
        """追踪表情变化"""
        expression = frame_data.expression
        if not expression:
            return

        current_emotion = expression.dominant

        # 表情切换
        if current_emotion != self._current_emotion_type:
            # 保存上一个表情片段
            if self._current_emotion_start is not None and self._current_emotion_type:
                duration = ts - self._current_emotion_start
                episode = {
                    "emotion": self._current_emotion_type,
                    "start": self._current_emotion_start,
                    "end": ts,
                    "duration_ms": duration,
                }
                self._emotion_episodes.append(episode)

                # 记录负面情绪片段
                if self._current_emotion_type in ["sadness", "anger", "fear", "disgust"]:
                    if duration >= NEGATIVE_EMOTION_MIN_DURATION_MS:
                        self._negative_episodes.append(episode)

            # 开始新的表情
            self._current_emotion_start = ts
            self._current_emotion_type = current_emotion

    def _track_head_pose(self, frame_data, ts: int):
        """追踪头部姿态"""
        head_pose = frame_data.head_pose
        if not head_pose:
            return

        # 分类当前头部状态
        state = self._classify_head_state(head_pose)

        if state != self._current_head_state:
            # 保存上一个状态片段
            if self._current_head_state_start is not None:
                duration = ts - self._current_head_state_start
                episode = {
                    "start": self._current_head_state_start,
                    "end": ts,
                    "duration_ms": duration,
                }

                # 添加到对应的状态列表
                state_key = self._map_state_to_key(self._current_head_state)
                if state_key:
                    self._head_state_episodes[state_key].append(episode)

            self._current_head_state_start = ts
            self._current_head_state = state

    def _track_body_posture(self, frame_data, ts: int):
        """追踪肢体姿态"""
        body = frame_data.body_posture
        if not body:
            return

        # 分类当前肢体状态
        states = []
        if not body.is_sitting_up:
            states.append("hunchback")
        if body.arm_crossed:
            states.append("arm_crossed")
        if body.body_sway > BODY_SWAY_THRESHOLD:
            states.append("swaying")
        if body.has_excessive_hand_motion:
            states.append("excessive_hand_motion")

        current_state = "|".join(states) if states else "proper"

        if current_state != self._current_body_state:
            if self._current_body_state_start is not None:
                duration = ts - self._current_body_state_start
                episode = {
                    "start": self._current_body_state_start,
                    "end": ts,
                    "duration_ms": duration,
                }

                # 保存到对应状态
                old_states = self._current_body_state.split("|")
                for old in old_states:
                    if old and old != "proper":
                        if old in self._body_state_episodes:
                            self._body_state_episodes[old].append(episode)

            self._current_body_state_start = ts
            self._current_body_state = current_state

    def _classify_head_state(self, head_pose) -> str:
        """分类头部状态"""
        if not head_pose:
            return "unknown"

        yaw, pitch, roll = head_pose.yaw, head_pose.pitch, head_pose.roll

        if abs(yaw) < 10 and abs(pitch) < 8 and abs(roll) < 8:
            return "stable"
        if pitch > LOOK_DOWN_PITCH_THRESHOLD:
            return "looking_down"
        if pitch < LOOK_UP_PITCH_THRESHOLD:
            return "looking_up"
        if yaw > TURN_LEFT_YAW_THRESHOLD:
            return "turning_left"
        if yaw < TURN_RIGHT_YAW_THRESHOLD:
            return "turning_right"
        if abs(roll) > TILT_ROLL_THRESHOLD:
            return "tilting"

        return "slight_movement"

    def _map_state_to_key(self, state: str) -> Optional[str]:
        """将状态字符串映射为键名"""
        mapping = {
            "stable": None,
            "looking_down": "looking_down",
            "looking_up": "looking_up",
            "turning_left": "turning_left",
            "turning_right": "turning_right",
            "tilting": "tilting",
        }
        return mapping.get(state)

    def finalize(self):
        """结束追踪，处理未完成的状态片段"""
        if self._current_emotion_start is not None and self._current_emotion_type:
            # 保存最后一个表情片段
            duration = self._frame_count  # 用帧数估算
            self._emotion_episodes.append({
                "emotion": self._current_emotion_type,
                "start": self._current_emotion_start,
                "end": self._end_time_ms,
                "duration_ms": self._end_time_ms - self._current_emotion_start,
            })

        if self._current_head_state_start is not None:
            state_key = self._map_state_to_key(self._current_head_state)
            if state_key:
                self._head_state_episodes[state_key].append({
                    "start": self._current_head_state_start,
                    "end": self._end_time_ms,
                    "duration_ms": self._end_time_ms - self._current_head_state_start,
                })

        if self._current_body_state_start is not None:
            old_states = self._current_body_state.split("|")
            for old in old_states:
                if old and old != "proper" and old in self._body_state_episodes:
                    self._body_state_episodes[old].append({
                        "start": self._current_body_state_start,
                        "end": self._end_time_ms,
                        "duration_ms": self._end_time_ms - self._current_body_state_start,
                    })

        if self._silence_start is not None:
            self._silence_episodes.append({
                "start": self._silence_start,
                "end": self._end_time_ms,
                "duration_ms": self._end_time_ms - self._silence_start,
            })

    def compute_final_statistics(self) -> Dict:
        """
        计算最终统计数据

        Returns:
            dict: 包含所有维度的时序统计
        """
        from app.integrations.mediapipe.enhanced_demeanor_models import (
            HeadPoseStatistics, EyeStatistics, ExpressionStatistics,
            BodyStatistics, AudioStatistics,
        )

        self.finalize()

        total_duration_ms = self._end_time_ms - self._start_time_ms
        valid_frames = self._valid_frame_count

        # ========== 1. 头部姿态统计 ==========
        head_stats = HeadPoseStatistics(
            total_duration_ms=total_duration_ms,
            valid_frames=valid_frames,
            total_looking_down_ms=sum(e["duration_ms"] for e in self._head_state_episodes["looking_down"]),
            looking_down_episodes=self._head_state_episodes["looking_down"],
            total_looking_up_ms=sum(e["duration_ms"] for e in self._head_state_episodes["looking_up"]),
            looking_up_episodes=self._head_state_episodes["looking_up"],
            total_turning_left_ms=sum(e["duration_ms"] for e in self._head_state_episodes["turning_left"]),
            total_turning_right_ms=sum(e["duration_ms"] for e in self._head_state_episodes["turning_right"]),
            turning_left_count=len(self._head_state_episodes["turning_left"]),
            turning_right_count=len(self._head_state_episodes["turning_right"]),
            turning_episodes=self._head_state_episodes["turning_left"] + self._head_state_episodes["turning_right"],
            total_tilting_ms=sum(e["duration_ms"] for e in self._head_state_episodes["tilting"]),
            tilting_episodes=self._head_state_episodes["tilting"],
            stable_frames=valid_frames - sum([
                len(self._head_state_episodes["looking_down"]),
                len(self._head_state_episodes["looking_up"]),
                len(self._head_state_episodes["turning_left"]),
                len(self._head_state_episodes["turning_right"]),
                len(self._head_state_episodes["tilting"]),
            ]),
        )

        # 计算平均低头时长
        ld_episodes = self._head_state_episodes["looking_down"]
        head_stats.avg_looking_down_duration_ms = (
            sum(e["duration_ms"] for e in ld_episodes) / len(ld_episodes)
            if ld_episodes else 0
        )

        lu_episodes = self._head_state_episodes["looking_up"]
        head_stats.avg_looking_up_duration_ms = (
            sum(e["duration_ms"] for e in lu_episodes) / len(lu_episodes)
            if lu_episodes else 0
        )

        # 稳定性比率
        if total_duration_ms > 0:
            unstable_ms = (
                head_stats.total_looking_down_ms +
                head_stats.total_looking_up_ms +
                head_stats.total_turning_left_ms +
                head_stats.total_turning_right_ms +
                head_stats.total_tilting_ms
            )
            head_stats.stability_rate = 1.0 - (unstable_ms / total_duration_ms)

        # ========== 2. 眼部状态统计 ==========
        blink_list = self._blink_list
        total_blinks = len(blink_list)

        # 计算眨眼频率（次/分钟）
        duration_min = total_duration_ms / 60000.0
        blink_frequency = total_blinks / duration_min if duration_min > 0 else 0

        eye_stats = EyeStatistics(
            total_duration_ms=total_duration_ms,
            valid_frames=valid_frames,
            total_blinks=total_blinks,
            blink_frequency=round(blink_frequency, 2),
            avg_blink_duration_ms=(
                sum(e["duration_ms"] for e in blink_list) / total_blinks
                if total_blinks > 0 else 0
            ),
            blink_episodes=blink_list,
        )

        # ========== 3. 表情统计 ==========
        emotion_episodes = self._emotion_episodes
        emotion_totals = {
            "happiness": 0,
            "sadness": 0,
            "anger": 0,
            "surprise": 0,
            "fear": 0,
            "disgust": 0,
            "neutral": 0,
        }

        for ep in emotion_episodes:
            emotion_totals[ep["emotion"]] = emotion_totals.get(ep["emotion"], 0) + ep["duration_ms"]

        expr_stats = ExpressionStatistics(
            total_duration_ms=total_duration_ms,
            valid_frames=valid_frames,
            happiness_ratio=emotion_totals["happiness"] / total_duration_ms if total_duration_ms > 0 else 0,
            sadness_ratio=emotion_totals["sadness"] / total_duration_ms if total_duration_ms > 0 else 0,
            anger_ratio=emotion_totals["anger"] / total_duration_ms if total_duration_ms > 0 else 0,
            surprise_ratio=emotion_totals["surprise"] / total_duration_ms if total_duration_ms > 0 else 0,
            fear_ratio=emotion_totals["fear"] / total_duration_ms if total_duration_ms > 0 else 0,
            disgust_ratio=emotion_totals["disgust"] / total_duration_ms if total_duration_ms > 0 else 0,
            neutral_ratio=emotion_totals["neutral"] / total_duration_ms if total_duration_ms > 0 else 0,
            dominant_expression=self._get_dominant_emotion(emotion_totals),
            negative_ratio=sum([
                emotion_totals["sadness"],
                emotion_totals["anger"],
                emotion_totals["fear"],
                emotion_totals["disgust"],
            ]) / total_duration_ms if total_duration_ms > 0 else 0,
            total_negative_duration_ms=sum([
                emotion_totals["sadness"],
                emotion_totals["anger"],
                emotion_totals["fear"],
                emotion_totals["disgust"],
            ]),
            negative_episodes=self._negative_episodes,
            longest_negative_episode_ms=(
                max((e["duration_ms"] for e in self._negative_episodes), default=0)
            ),
            negative_episode_count=len(self._negative_episodes),
            smiling_ratio=emotion_totals["happiness"] / total_duration_ms if total_duration_ms > 0 else 0,
        )

        # ========== 4. 肢体统计 ==========
        body_episodes = self._body_state_episodes
        hunchback_ms = sum(e["duration_ms"] for e in body_episodes["hunchback"])
        arm_crossed_ms = sum(e["duration_ms"] for e in body_episodes["arm_crossed"])

        body_stats = BodyStatistics(
            total_duration_ms=total_duration_ms,
            valid_frames=valid_frames,
            total_arm_crossed_ms=arm_crossed_ms,
            arm_crossed_episodes=body_episodes["arm_crossed"],
            arm_crossed_ratio=arm_crossed_ms / total_duration_ms if total_duration_ms > 0 else 0,
            total_hunchback_ms=hunchback_ms,
            hunchback_episodes=body_episodes["hunchback"],
            hunchback_ratio=hunchback_ms / total_duration_ms if total_duration_ms > 0 else 0,
            total_body_sway_ms=sum(e["duration_ms"] for e in body_episodes["swaying"]),
            sway_episodes=body_episodes["swaying"],
            total_hand_motion_ms=sum(e["duration_ms"] for e in body_episodes["excessive_hand_motion"]),
            excessive_hand_motion_ms=sum(e["duration_ms"] for e in body_episodes["excessive_hand_motion"]),
            hand_motion_episodes=body_episodes["excessive_hand_motion"],
            proper_posture_ratio=1.0 - (
                hunchback_ms + arm_crossed_ms
            ) / total_duration_ms if total_duration_ms > 0 else 0,
        )

        # ========== 5. 音频统计 ==========
        total_silence_ms = sum(e["duration_ms"] for e in self._silence_episodes)

        audio_stats = AudioStatistics(
            total_duration_ms=total_duration_ms,
            silence_duration_ms=total_silence_ms,
            silence_ratio=total_silence_ms / total_duration_ms if total_duration_ms > 0 else 0,
            long_silences=sum(1 for e in self._silence_episodes if e["duration_ms"] > 3000),
        )

        return {
            "head_pose_stats": head_stats,
            "eye_stats": eye_stats,
            "expression_stats": expr_stats,
            "body_stats": body_stats,
            "audio_stats": audio_stats,
        }

    def _get_dominant_emotion(self, emotion_totals: Dict) -> str:
        """获取主表情"""
        if not emotion_totals:
            return "neutral"
        return max(emotion_totals, key=emotion_totals.get)

    def get_summary(self) -> Dict:
        """获取当前跟踪状态的简要摘要"""
        return {
            "total_frames": self._frame_count,
            "valid_frames": self._valid_frame_count,
            "total_blinks": len(self._blink_list),
            "negative_episodes": len(self._negative_episodes),
            "emotion_episodes": len(self._emotion_episodes),
        }


# 全局实例（每个会话应创建新实例）
def create_tracker() -> DemeanorTracker:
    """创建新的跟踪器实例"""
    return DemeanorTracker()
