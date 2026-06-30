"""
增强版视频分析器 - MediaPipe 实现
功能：眨眼检测、视线追踪、肢体动作分析
"""

import logging
from pathlib import Path
from typing import Optional, Tuple
import math

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# 项目本地模型目录
MODELS_DIR = Path(__file__).parent.parent.parent.parent / "models" / "mediapipe"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
FACE_LANDMARKER_MODEL = MODELS_DIR / "face_landmarker.task"

# 检测阈值常量
BLINK_THRESHOLD = 0.25          # 眨眼判定阈值（眼睛睁开度低于此值视为眨眼）
BLINK_CONSECUTIVE_FRAMES = 2   # 连续多少帧低于阈值才判定为眨眼（过滤噪声）
EYE_CLOSED_THRESHOLD = 0.15    # 闭眼判定阈值
EYE_CLOSED_MIN_DURATION_MS = 500  # 闭眼走神最短判定时长(ms)

# 视线偏移阈值
GAZE_OFFSET_THRESHOLD = 0.15   # 视线偏移判定阈值

# 头部姿态阈值
LOOK_DOWN_PITCH = 15           # 低头角度阈值（度）
LOOK_UP_PITCH = -10            # 仰头角度阈值（度）
TURN_LEFT_YAW = 20             # 左转头角度阈值（度）
TURN_RIGHT_YAW = -20           # 右转头角度阈值（度）
TILT_ROLL = 10                 # 歪头角度阈值（度）


class EnhancedVideoAnalyzer:
    """
    增强版视频分析器

    功能：
    1. 眨眼检测（频率、时长）
    2. 视线追踪（方向、偏移）
    3. 头部姿态（低头/仰头/左右转/歪头）
    4. 肢体动作（抱臂/驼背/身体晃动/手部动作）
    5. 表情识别（7类情绪）
    """

    def __init__(
        self,
        max_faces: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ):
        self.max_faces = max_faces
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence

        self._face_landmarker = None
        self._use_face_mesh = False
        self._initialized = False

        # 眨眼检测状态
        self._eye_closed_frames = 0
        self._last_eye_openness = 1.0
        self._blink_in_progress = False
        self._blink_start_time = 0

        # 3D 人脸模型关键点（用于头部姿态）
        self._face_3d_model_points = np.array([
            [-0.5, 0.0, -0.5],     # 0: 左眼外角
            [0.5, 0.0, -0.5],      # 1: 右眼外角
            [0.0, 0.5, -0.5],      # 2: 鼻尖
            [-1.5, -0.5, -1.5],    # 3: 左嘴角
            [1.5, -0.5, -1.5],     # 4: 右嘴角
            [0.0, -1.5, -0.0],     # 5: 下巴中心
        ], dtype=np.float64)

        self._dist_coeffs = np.zeros((4, 1), dtype=np.float64)

        # MediaPipe FaceMesh 关键点索引
        self._MP_LANDMARKS = {
            # 眼睛
            "left_eye_outer": 33,
            "right_eye_outer": 263,
            "left_eye_inner": 133,
            "right_eye_inner": 362,
            "left_eye_top": 159,
            "left_eye_bottom": 145,
            "right_eye_top": 386,
            "right_eye_bottom": 374,
            "left_eye_center": 468,
            "right_eye_center": 473,
            # 眉毛
            "left_eyebrow_inner": 107,
            "right_eyebrow_inner": 337,
            # 嘴巴
            "mouth_left": 61,
            "mouth_right": 291,
            "mouth_top": 13,
            "mouth_bottom": 14,
            "mouth_center": 0,
            # 鼻子
            "nose_tip": 1,
            "nose_bridge": 6,
            # 轮廓
            "chin": 152,
            "forehead": 10,
            "left_cheek": 123,
            "right_cheek": 352,
            # 瞳孔
            "left_pupil": 468,
            "right_pupil": 473,
            # 肩膀检测（用头部大小估算）
            "left_temple": 234,
            "right_temple": 454,
        }

    def _ensure_initialized(self):
        """延迟初始化 MediaPipe FaceLandmarker"""
        if self._initialized:
            return

        if FACE_LANDMARKER_MODEL.exists():
            try:
                from mediapipe.tasks.python.core.base_options import BaseOptions
                from mediapipe.tasks.python.vision.core.vision_task_running_mode import VisionTaskRunningMode
                from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions

                base_options = BaseOptions(model_asset_path=str(FACE_LANDMARKER_MODEL))
                running_mode = VisionTaskRunningMode.IMAGE

                options = FaceLandmarkerOptions(
                    base_options=base_options,
                    running_mode=running_mode,
                    num_faces=self.max_faces,
                    min_face_detection_confidence=self.min_detection_confidence,
                    min_tracking_confidence=self.min_tracking_confidence,
                )

                self._face_landmarker = FaceLandmarker.create_from_options(options)
                self._use_face_mesh = True
                logger.info(f"EnhancedVideoAnalyzer: MediaPipe FaceLandmarker 已加载")
            except Exception as e:
                logger.warning(f"EnhancedVideoAnalyzer: MediaPipe 加载失败: {e}，使用 Haar Cascade 备用")
                self._use_face_mesh = False
        else:
            logger.warning(f"EnhancedVideoAnalyzer: MediaPipe 模型不存在: {FACE_LANDMARKER_MODEL}")
            self._use_face_mesh = False

        self._initialized = True

    def _get_camera_matrix(self, width: int, height: int) -> np.ndarray:
        """构建相机内参矩阵"""
        fx = width * 1.0
        fy = height * 1.0
        cx = width / 2.0
        cy = height / 2.0
        return np.array([
            [fx, 0, cx],
            [0, fy, cy],
            [0, 0, 1],
        ], dtype=np.float64)

    def _estimate_head_pose(self, landmarks) -> Tuple[float, float, float]:
        """
        根据人脸关键点估计头部姿态角
        Returns: (yaw, pitch, roll) - 度
        """
        try:
            h, w = 480, 640
            lm = self._MP_LANDMARKS

            # 提取关键点
            left_eye = landmarks[lm["left_eye_outer"]]
            right_eye = landmarks[lm["right_eye_outer"]]
            nose_tip = landmarks[lm["nose_tip"]]
            left_mouth = landmarks[lm["mouth_left"]]
            right_mouth = landmarks[lm["mouth_right"]]
            chin = landmarks[lm["chin"]]

            image_points = np.array([
                [left_eye[0] * w, left_eye[1] * h],
                [right_eye[0] * w, right_eye[1] * h],
                [nose_tip[0] * w, nose_tip[1] * h],
                [left_mouth[0] * w, left_mouth[1] * h],
                [right_mouth[0] * w, right_mouth[1] * h],
                [chin[0] * w, chin[1] * h],
            ], dtype=np.float64)

            success, rotation_vec, _ = cv2.solvePnP(
                self._face_3d_model_points,
                image_points,
                self._get_camera_matrix(w, h),
                self._dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE,
            )

            if not success:
                return 0.0, 0.0, 0.0

            rot_mat, _ = cv2.Rodrigues(rotation_vec)
            proj_mat = np.hstack((rot_mat, np.zeros((3, 1))))
            _, _, _, _, _, _, euler_angles = cv2.decomposeProjectionMatrix(proj_mat)

            yaw, pitch, roll = euler_angles.flatten()
            return float(yaw), float(pitch), float(roll)
        except Exception as e:
            logger.debug(f"头部姿态估计失败: {e}")
            return 0.0, 0.0, 0.0

    def _calculate_eye_openness(self, landmarks) -> Tuple[float, float]:
        """
        计算眼睛睁开度
        Returns: (left_openness, right_openness) - 0 到 1
        """
        try:
            lm = self._MP_LANDMARKS

            def eye_openness(top, bottom, corner_left, corner_right):
                """计算单只眼睛的睁开度"""
                # 眼睛高度
                eye_height = abs(top[1] - bottom[1])
                # 眼睛宽度
                eye_width = abs(corner_right[0] - corner_left[0])
                if eye_width < 1e-6:
                    return 0.0
                # 归一化（假设正常睁眼时高度约为宽度的 20-25%）
                return min(1.0, eye_height / (eye_width * 0.25 + 1e-6))

            left_top = landmarks[lm["left_eye_top"]]
            left_bottom = landmarks[lm["left_eye_bottom"]]
            left_left = landmarks[lm["left_eye_outer"]]
            left_right = landmarks[lm["left_eye_inner"]]

            right_top = landmarks[lm["right_eye_top"]]
            right_bottom = landmarks[lm["right_eye_bottom"]]
            right_left = landmarks[lm["right_eye_inner"]]
            right_right = landmarks[lm["right_eye_outer"]]

            left_openness = eye_openness(left_top, left_bottom, left_left, left_right)
            right_openness = eye_openness(right_top, right_bottom, right_left, right_right)

            return left_openness, right_openness
        except Exception as e:
            logger.debug(f"眼睛睁开度计算失败: {e}")
            return 1.0, 1.0

    def _detect_blink(self, left_openness: float, right_openness: float, timestamp_ms: int) -> dict:
        """
        检测眨眼
        Returns: {
            "is_blinking": bool,
            "blink_completed": bool,  # 是否刚完成一次眨眼
            "blink_duration_ms": int,
        }
        """
        avg_openness = (left_openness + right_openness) / 2.0

        result = {
            "is_blinking": False,
            "blink_completed": False,
            "blink_duration_ms": 0,
        }

        # 状态机检测眨眼
        if avg_openness < BLINK_THRESHOLD:
            # 眼睛闭合
            if not self._blink_in_progress:
                self._blink_in_progress = True
                self._blink_start_time = timestamp_ms
                self._eye_closed_frames = 1
            else:
                self._eye_closed_frames += 1

            # 连续多帧低于阈值，判定为眨眼中
            if self._eye_closed_frames >= BLINK_CONSECUTIVE_FRAMES:
                result["is_blinking"] = True
        else:
            # 眼睛睁开
            if self._blink_in_progress:
                # 刚完成一次眨眼
                blink_duration = timestamp_ms - self._blink_start_time
                # 眨眼时长应该在 100-400ms 之间，过长可能是走神/闭眼
                if blink_duration < 400:
                    result["blink_completed"] = True
                    result["blink_duration_ms"] = blink_duration
                self._blink_in_progress = False
                self._eye_closed_frames = 0

        return result

    def _estimate_gaze_direction(self, landmarks, head_yaw: float, head_pitch: float) -> dict:
        """
        估计视线方向
        Returns: {
            "direction": str,  # left/right/center/up/down
            "offset_x": float,  # -1 ~ 1
            "offset_y": float,  # -1 ~ 1
        }
        """
        try:
            lm = self._MP_LANDMARKS

            # 获取瞳孔位置
            left_pupil = landmarks[lm["left_pupil"]]
            right_pupil = landmarks[lm["right_pupil"]]

            # 获取眼角位置（参考点）
            left_eye_left = landmarks[lm["left_eye_outer"]]
            left_eye_right = landmarks[lm["left_eye_inner"]]
            right_eye_left = landmarks[lm["right_eye_inner"]]
            right_eye_right = landmarks[lm["right_eye_outer"]]

            # 计算瞳孔相对位置
            left_eye_width = left_eye_right[0] - left_eye_left[0]
            right_eye_width = right_eye_right[0] - right_eye_left[0]

            # 瞳孔中心
            left_pupil_x = left_pupil[0]
            right_pupil_x = right_pupil[0]

            # 计算相对偏移（瞳孔在眼睛中的位置）
            left_offset_x = (left_pupil_x - left_eye_left[0]) / (left_eye_width + 1e-6) - 0.5
            right_offset_x = (right_pupil_x - right_eye_left[0]) / (right_eye_width + 1e-6) - 0.5

            avg_offset_x = (left_offset_x + right_offset_x) / 2

            # 垂直方向（考虑头部俯仰）
            left_eye_top = landmarks[lm["left_eye_top"]]
            left_eye_bottom = landmarks[lm["left_eye_bottom"]]
            left_eye_height = abs(left_eye_bottom[1] - left_eye_top[1])
            left_pupil_y = left_pupil[1]

            left_offset_y = (left_pupil_y - left_eye_top[1]) / (left_eye_height + 1e-6) - 0.5

            # 考虑头部姿态补偿
            offset_x = avg_offset_x - head_yaw / 90.0 * 0.2  # 补偿头部偏转
            offset_y = left_offset_y - head_pitch / 90.0 * 0.2  # 补偿头部俯仰

            # 判定方向
            direction = "center"
            if offset_x > GAZE_OFFSET_THRESHOLD:
                direction = "left"  # 瞳孔偏左 → 视线向右看
            elif offset_x < -GAZE_OFFSET_THRESHOLD:
                direction = "right"  # 瞳孔偏右 → 视线向左看

            if offset_y > GAZE_OFFSET_THRESHOLD * 0.7:
                direction = "up"  # 瞳孔偏下 → 视线向下看
            elif offset_y < -GAZE_OFFSET_THRESHOLD * 0.7:
                direction = "down"  # 瞳孔偏上 → 视线向上看

            return {
                "direction": direction,
                "offset_x": max(-1.0, min(1.0, offset_x * 2)),
                "offset_y": max(-1.0, min(1.0, offset_y * 2)),
            }
        except Exception as e:
            logger.debug(f"视线方向估计失败: {e}")
            return {"direction": "center", "offset_x": 0.0, "offset_y": 0.0}

    def _detect_expression(self, landmarks) -> dict:
        """
        基于关键点计算表情分数
        Returns: dict with happiness, sadness, anger, surprise, neutral, dominant
        """
        try:
            lm = self._MP_LANDMARKS

            # 嘴巴参数
            mouth_left = landmarks[lm["mouth_left"]]
            mouth_right = landmarks[lm["mouth_right"]]
            mouth_top = landmarks[lm["mouth_top"]]
            mouth_bottom = landmarks[lm["mouth_bottom"]]

            mouth_width = abs(mouth_right[0] - mouth_left[0])
            mouth_height = abs(mouth_bottom[1] - mouth_top[1])
            mouth_ratio = mouth_height / (mouth_width + 1e-6)  # 嘴巴高宽比

            # 眼睛参数
            left_top = landmarks[lm["left_eye_top"]]
            left_bottom = landmarks[lm["left_eye_bottom"]]
            left_left = landmarks[lm["left_eye_outer"]]
            left_right = landmarks[lm["left_eye_inner"]]
            right_top = landmarks[lm["right_eye_top"]]
            right_bottom = landmarks[lm["right_eye_bottom"]]

            left_eye_openness = abs(left_bottom[1] - left_top[1]) / (abs(left_right[0] - left_left[0]) + 1e-6)
            right_eye_openness = abs(right_bottom[1] - right_top[1]) / (abs(left_right[0] - left_left[0]) + 1e-6)
            avg_eye_openness = (left_eye_openness + right_eye_openness) / 2

            # 眉毛参数
            left_eyebrow = landmarks[lm["left_eyebrow_inner"]]
            nose_bridge = landmarks[lm["nose_bridge"]]
            left_eye_center_y = (left_top[1] + left_bottom[1]) / 2

            eyebrow_raise = nose_bridge[1] - left_eyebrow[1]  # 眉毛与鼻梁的距离

            # 计算各情绪分数
            # 高兴：嘴角上扬 + 嘴巴张开
            happiness = 0.0
            if mouth_ratio > 0.15 and mouth_width > 0.3:  # 嘴巴张开且宽
                happiness = min(100, mouth_ratio * 200 + (mouth_width - 0.3) * 100)

            # 悲伤：眉毛下压 + 嘴角下垂
            sadness = 0.0
            if eyebrow_raise > 0.05 and mouth_ratio < 0.1:
                sadness = min(100, eyebrow_raise * 500 + (0.1 - mouth_ratio) * 200)

            # 愤怒：眉毛下压 + 嘴唇紧抿
            anger = 0.0
            if eyebrow_raise < 0.04 and mouth_ratio < 0.08:
                anger = min(100, (0.05 - eyebrow_raise) * 1000 + (0.08 - mouth_ratio) * 300)

            # 惊讶：眼睛大睁 + 嘴巴张开
            surprise = 0.0
            if avg_eye_openness > 0.2 and mouth_ratio > 0.2:
                surprise = min(100, avg_eye_openness * 200 + (mouth_ratio - 0.2) * 200)

            # 厌恶：眼睛眯起 + 嘴角下撇（简化判定）
            disgust = 0.0
            if avg_eye_openness < 0.1 and mouth_ratio < 0.1:
                disgust = min(100, (0.15 - avg_eye_openness) * 300)

            # 中性 = 100 - 其他情绪总和
            total_excited = happiness + sadness + anger + surprise + disgust
            neutral = max(0.0, 100.0 - total_excited)

            # 归一化
            total = happiness + sadness + anger + surprise + disgust + neutral
            if total > 0:
                scale = 100.0 / total
                happiness *= scale
                sadness *= scale
                anger *= scale
                surprise *= scale
                disgust *= scale
                neutral *= scale

            # 确定主表情
            scores = {
                "happiness": happiness,
                "sadness": sadness,
                "anger": anger,
                "surprise": surprise,
                "disgust": disgust,
                "neutral": neutral,
            }
            dominant = max(scores, key=scores.get)

            # 判定是否为负面情绪
            is_negative = dominant in ["sadness", "anger", "fear", "disgust"]

            return {
                "happiness": happiness,
                "sadness": sadness,
                "anger": anger,
                "surprise": surprise,
                "fear": 0.0,  # 简化版不支持恐惧检测
                "disgust": disgust,
                "neutral": neutral,
                "dominant": dominant,
                "is_negative": is_negative,
            }
        except Exception as e:
            logger.debug(f"表情识别失败: {e}")
            return {
                "happiness": 0.0, "sadness": 0.0, "anger": 0.0,
                "surprise": 0.0, "fear": 0.0, "disgust": 0.0,
                "neutral": 100.0, "dominant": "neutral", "is_negative": False,
            }

    def _detect_body_posture(self, landmarks, image_width: int, image_height: int) -> dict:
        """
        基于人脸关键点检测肢体姿态
        注意：单人正面视频中，肢体信息有限，这里做简化估算
        """
        try:
            lm = self._MP_LANDMARKS

            # 人脸边界
            forehead = landmarks[lm["forehead"]]
            chin = landmarks[lm["chin"]]
            left_cheek = landmarks[lm["left_cheek"]]
            right_cheek = landmarks[lm["right_cheek"]]
            left_temple = landmarks[lm["left_temple"]]
            right_temple = landmarks[lm["right_temple"]]

            # 估算肩膀位置（假设额头到肩膀的距离约为额头到下巴的 3-4 倍）
            face_height = abs(chin[1] - forehead[1])
            estimated_shoulder_y = chin[1] + face_height * 3.5

            # 肩膀宽度（假设肩膀宽度约为头部宽度的 2-3 倍）
            face_width = abs(right_cheek[0] - left_cheek[0])
            estimated_shoulder_width = face_width * 2.8

            # 人脸在画面中的位置
            face_center_x = (left_cheek[0] + right_cheek[0]) / 2
            face_center_y = (forehead[1] + chin[1]) / 2

            # 肩膀相对位置（相对于画面中心）
            frame_center_x = 0.5
            frame_center_y = 0.5

            shoulder_offset_x = (face_center_x - frame_center_x)
            shoulder_offset_y = (estimated_shoulder_y / image_height - frame_center_y)

            # 检测驼背（肩膀位置偏低）
            hunchback_ratio = max(0.0, min(1.0, shoulder_offset_y * 2))

            # 检测身体偏转（肩膀不在画面中心）
            body_lean = abs(shoulder_offset_x)

            # 估算抱臂（简化版：手臂位置信息不足，返回 False）
            arm_crossed = False

            # 估算身体晃动（简化版）
            body_sway = body_lean * 0.5  # 经验系数

            # 估算手部动作（简化版：无手部关键点，返回 0）
            hand_movement = 0.0

            # 综合坐姿判定
            is_sitting_up = hunchback_ratio < 0.3 and body_lean < 0.15

            return {
                "shoulder_distance_ratio": hunchback_ratio,
                "is_leaning_forward": shoulder_offset_y > 0.1,
                "is_leaning_back": shoulder_offset_y < -0.1,
                "is_sitting_up": is_sitting_up,
                "arm_crossed": arm_crossed,
                "body_sway": body_sway,
                "hand_movement": hand_movement,
                "has_excessive_hand_motion": hand_movement > 0.5,
            }
        except Exception as e:
            logger.debug(f"肢体姿态检测失败: {e}")
            return {
                "shoulder_distance_ratio": 0.0,
                "is_leaning_forward": False,
                "is_leaning_back": False,
                "is_sitting_up": True,
                "arm_crossed": False,
                "body_sway": 0.0,
                "hand_movement": 0.0,
                "has_excessive_hand_motion": False,
            }

    def _calc_face_blur(self, image: np.ndarray) -> float:
        """计算图像清晰度"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            return float(min(100.0, laplacian_var / 5.0))
        except:
            return 100.0

    def _calc_face_size_ratio(self, landmarks, image_h: int, image_w: int) -> float:
        """计算人脸占画面比例"""
        try:
            ys = [lm[1] for lm in landmarks]
            xs = [lm[0] for lm in landmarks]
            face_h = max(ys) - min(ys)
            face_w = max(xs) - min(xs)
            return float(face_h * face_w)
        except:
            return 0.1

    def analyze_frame(self, frame: np.ndarray, timestamp_ms: int = 0) -> Optional[dict]:
        """
        分析单帧图像，返回增强的仪态数据

        Returns:
            dict: {
                "face_detected": bool,
                "face_count": int,
                "confidence": float,
                "face_blur_score": float,
                "face_size_ratio": float,
                "timestamp_ms": int,
                "frame_index": int,
                "head_pose": {"yaw": float, "pitch": float, "roll": float,
                              "is_stable": bool, "is_looking_down": bool, ...},
                "eye_state": {"left_eye_openness": float, "right_eye_openness": float,
                              "avg_eye_openness": float, "is_blinking": bool,
                              "gaze_direction": str, "gaze_offset_x": float, "gaze_offset_y": float},
                "expression": {"happiness": float, ..., "dominant": str, "is_negative": bool},
                "body_posture": {...},
            }
            如果没有人脸，返回 None
        """
        from app.integrations.mediapipe.enhanced_demeanor_models import (
            VideoFrameData, HeadPoseStats, EyeState, FacialExpression, BodyPosture
        )

        self._ensure_initialized()

        h, w = frame.shape[:2]
        blur_score = self._calc_face_blur(frame)
        landmarks = None

        # 1. MediaPipe 人脸检测
        if self._use_face_mesh and self._face_landmarker:
            try:
                import mediapipe as mp
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB,
                                   data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                result = self._face_landmarker.detect(mp_image)

                if result.face_landmarks and len(result.face_landmarks) > 0:
                    face_landmarks = result.face_landmarks[0]
                    landmarks = [[lm.x, lm.y, lm.z] for lm in face_landmarks]
            except Exception as e:
                logger.debug(f"MediaPipe 检测失败: {e}")

        # 2. 备用 Haar Cascade
        if not landmarks:
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )
            if len(faces) == 0:
                return None

            face = max(faces, key=lambda f: f[2] * f[3])
            x, y, fw, fh = face
            landmarks = self._generate_synthetic_landmarks(x, y, fw, fh, w, h)
            face_size_ratio = (fw * fh) / (w * h)
        else:
            face_size_ratio = self._calc_face_size_ratio(landmarks, h, w)

        # 3. 头部姿态
        yaw, pitch, roll = self._estimate_head_pose(landmarks)
        head_pose = HeadPoseStats(
            yaw=yaw, pitch=pitch, roll=roll,
            is_stable=abs(yaw) < 15 and abs(pitch) < 10 and abs(roll) < 10,
            is_looking_down=pitch > LOOK_DOWN_PITCH,
            is_looking_up=pitch < LOOK_UP_PITCH,
            is_turning_left=yaw > TURN_LEFT_YAW,
            is_turning_right=yaw < TURN_RIGHT_YAW,
            is_tilting=abs(roll) > TILT_ROLL,
        )

        # 4. 眼部状态
        left_open, right_open = self._calculate_eye_openness(landmarks)
        avg_openness = (left_open + right_open) / 2.0

        blink_result = self._detect_blink(left_open, right_open, timestamp_ms)
        gaze = self._estimate_gaze_direction(landmarks, yaw, pitch)

        eye_state = EyeState(
            left_eye_openness=left_open,
            right_eye_openness=right_open,
            avg_eye_openness=avg_openness,
            is_blinking=blink_result["is_blinking"],
            gaze_direction=gaze["direction"],
            gaze_offset_x=gaze["offset_x"],
            gaze_offset_y=gaze["offset_y"],
        )

        # 5. 表情
        expr_dict = self._detect_expression(landmarks)
        expression = FacialExpression(
            happiness=expr_dict["happiness"],
            sadness=expr_dict["sadness"],
            anger=expr_dict["anger"],
            surprise=expr_dict["surprise"],
            fear=expr_dict["fear"],
            disgust=expr_dict["disgust"],
            neutral=expr_dict["neutral"],
            dominant=expr_dict["dominant"],
            is_negative=expr_dict["is_negative"],
        )

        # 6. 肢体姿态
        posture_dict = self._detect_body_posture(landmarks, w, h)
        body_posture = BodyPosture(
            shoulder_distance_ratio=posture_dict["shoulder_distance_ratio"],
            is_leaning_forward=posture_dict["is_leaning_forward"],
            is_leaning_back=posture_dict["is_leaning_back"],
            is_sitting_up=posture_dict["is_sitting_up"],
            arm_crossed=posture_dict["arm_crossed"],
            body_sway=posture_dict["body_sway"],
            hand_movement=posture_dict["hand_movement"],
            has_excessive_hand_motion=posture_dict["has_excessive_hand_motion"],
        )

        # 7. 组装结果
        frame_data = VideoFrameData(
            timestamp_ms=timestamp_ms,
            frame_index=0,
            face_detected=True,
            face_count=1,
            face_blur_score=blur_score,
            face_size_ratio=face_size_ratio,
            confidence=1.0 if self._use_face_mesh else 0.8,
            head_pose=head_pose,
            eye_state=eye_state,
            expression=expression,
            body_posture=body_posture,
        )

        # 添加眨眼完成标记
        blink_completed = blink_result["blink_completed"]
        frame_data.blink_completed = blink_completed
        frame_data.blink_duration_ms = blink_result["blink_duration_ms"]

        return frame_data

    def _generate_synthetic_landmarks(self, x, y, w, h, img_w, img_h) -> list:
        """生成简化的人脸关键点（供 Haar Cascade 备用使用）"""
        cx, cy = x + w // 2, y + h // 2

        landmarks = []
        for i in range(478):  # MediaPipe FaceMesh has 478 points
            t = i / 478 * 2 * 3.14159
            r = 0.3 + 0.2 * (i % 10) / 10
            lx = cx + int(w * r * 0.5 * (1 if i % 2 == 0 else -1) * (0.5 + 0.5 * (i % 7) / 7))
            ly = cy + int(h * r * 0.6 * (1 if i % 3 == 0 else -1) * (0.3 + 0.7 * (i % 11) / 11))
            landmarks.append([lx / img_w, ly / img_h, 0])

        lm = self._MP_LANDMARKS
        landmarks[lm["left_eye_outer"]] = [x / img_w, (y + h // 4) / img_h, 0]
        landmarks[lm["right_eye_outer"]] = [(x + w) / img_w, (y + h // 4) / img_h, 0]
        landmarks[lm["left_eye_inner"]] = [(x + w // 2) / img_w, (y + h // 4) / img_h, 0]
        landmarks[lm["right_eye_inner"]] = [(x + w // 2) / img_w, (y + h // 4) / img_h, 0]
        landmarks[lm["left_eye_top"]] = [(x + w // 3) / img_w, (y + h // 5) / img_h, 0]
        landmarks[lm["left_eye_bottom"]] = [(x + w // 3) / img_w, (y + h // 3) / img_h, 0]
        landmarks[lm["right_eye_top"]] = [(x + 2 * w // 3) / img_w, (y + h // 5) / img_h, 0]
        landmarks[lm["right_eye_bottom"]] = [(x + 2 * w // 3) / img_w, (y + h // 3) / img_h, 0]
        landmarks[lm["nose_tip"]] = [(x + w // 2) / img_w, (y + h // 2) / img_h, 0]
        landmarks[lm["mouth_left"]] = [(x + w // 4) / img_w, (y + 3 * h // 4) / img_h, 0]
        landmarks[lm["mouth_right"]] = [(x + 3 * w // 4) / img_w, (y + 3 * h // 4) / img_h, 0]
        landmarks[lm["mouth_top"]] = [(x + w // 2) / img_w, (y + 2 * h // 3) / img_h, 0]
        landmarks[lm["mouth_bottom"]] = [(x + w // 2) / img_w, (y + 5 * h // 6) / img_h, 0]
        landmarks[lm["chin"]] = [(x + w // 2) / img_w, (y + h) / img_h, 0]
        landmarks[lm["forehead"]] = [(x + w // 2) / img_w, y / img_h, 0]
        landmarks[lm["left_cheek"]] = [x / img_w, (y + h // 2) / img_h, 0]
        landmarks[lm["right_cheek"]] = [(x + w) / img_w, (y + h // 2) / img_h, 0]

        return landmarks

    def reset_blink_state(self):
        """重置眨眼检测状态（用于新会话）"""
        self._eye_closed_frames = 0
        self._blink_in_progress = False
        self._blink_start_time = 0


# 全局实例
enhanced_video_analyzer = EnhancedVideoAnalyzer()
