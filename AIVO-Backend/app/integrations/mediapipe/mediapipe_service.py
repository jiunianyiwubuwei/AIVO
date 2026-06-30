"""MediaPipe 仪态评估服务 - 人脸检测、表情识别、头部姿态"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# 项目本地模型目录
MODELS_DIR = Path(__file__).parent.parent.parent.parent / "models" / "mediapipe"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# FaceMesh 模型文件路径
FACE_LANDMARKER_MODEL = MODELS_DIR / "face_landmarker.task"


@dataclass
class HeadPose:
    """头部姿态角"""
    yaw: float   # 偏航角 - 左右转头
    pitch: float # 俯仰角 - 上下点头
    roll: float  # 翻滚角 - 歪头


@dataclass
class ExpressionScore:
    """表情评分（0-100）"""
    happiness: float
    sadness: float
    anger: float
    surprise: float
    neutral: float
    dominant: str


@dataclass
class DemeanorData:
    """仪态数据汇总"""
    face_detected: bool
    face_count: int
    head_pose: Optional[HeadPose] = None
    expression: Optional[ExpressionScore] = None
    face_blur_score: float = 100.0
    face_size_ratio: float = 0.0
    confidence: float = 0.0
    timestamp_ms: int = 0


class MediaPipeDemeanorAnalyzer:
    """MediaPipe 仪态分析器（使用 Tasks API 或 OpenCV Haar Cascade 备用）"""

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

        # 3D 人脸模型关键点
        self._face_3d_model_points = np.array([
            [-0.5, 0.0, -0.5],     # 左眼外角
            [0.5, 0.0, -0.5],      # 右眼外角
            [0.0, 0.5, -0.5],      # 鼻尖
            [-1.5, -0.5, -1.5],    # 左嘴角
            [1.5, -0.5, -1.5],     # 右嘴角
            [0.0, -1.5, -0.0],     # 下巴中心
        ], dtype=np.float64)

        self._dist_coeffs = np.zeros((4, 1), dtype=np.float64)

    def _ensure_initialized(self):
        """延迟初始化 FaceMesh 或 Haar Cascade"""
        if self._initialized:
            return

        # 优先使用 MediaPipe FaceLandmarker
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
                logger.info(f"MediaPipe FaceLandmarker 已加载，模型路径: {FACE_LANDMARKER_MODEL}")
            except Exception as e:
                logger.warning(f"MediaPipe FaceLandmarker 初始化失败: {e}，使用 Haar Cascade 备用")
                self._use_face_mesh = False
        else:
            logger.warning(f"MediaPipe 模型文件不存在: {FACE_LANDMARKER_MODEL}，使用 Haar Cascade 备用")
            logger.warning(f"请运行 scripts/download_models.py 下载模型")
            self._use_face_mesh = False

        self._initialized = True

    def _get_camera_matrix(self, width: int, height: int):
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

    def _estimate_head_pose(self, landmarks) -> Optional[HeadPose]:
        """根据人脸关键点估计头部姿态"""
        try:
            h, w = 480, 640

            # MediaPipe FaceMesh 关键点索引
            left_eye = 33    # 左眼外角
            right_eye = 263  # 右眼外角
            nose_tip = 1     # 鼻尖
            left_mouth = 61  # 左嘴角
            right_mouth = 291 # 右嘴角
            chin = 152       # 下巴

            if len(landmarks) <= max(left_eye, right_eye, nose_tip, left_mouth, right_mouth, chin):
                return None

            image_points = np.array([
                [landmarks[left_eye][0] * w, landmarks[left_eye][1] * h],
                [landmarks[right_eye][0] * w, landmarks[right_eye][1] * h],
                [landmarks[nose_tip][0] * w, landmarks[nose_tip][1] * h],
                [landmarks[left_mouth][0] * w, landmarks[left_mouth][1] * h],
                [landmarks[right_mouth][0] * w, landmarks[right_mouth][1] * h],
                [landmarks[chin][0] * w, landmarks[chin][1] * h],
            ], dtype=np.float64)

            success, rotation_vec, _ = cv2.solvePnP(
                self._face_3d_model_points,
                image_points,
                self._get_camera_matrix(w, h),
                self._dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE,
            )

            if not success:
                return HeadPose(yaw=0.0, pitch=0.0, roll=0.0)

            rot_mat, _ = cv2.Rodrigues(rotation_vec)
            proj_mat = np.hstack((rot_mat, np.zeros((3, 1))))
            _, _, _, _, _, _, euler_angles = cv2.decomposeProjectionMatrix(proj_mat)

            yaw, pitch, roll = euler_angles.flatten()
            return HeadPose(yaw=float(yaw), pitch=float(pitch), roll=float(roll))
        except Exception as e:
            logger.warning(f"头部姿态估计失败: {e}")
            return None

    def _detect_expression(self, landmarks) -> ExpressionScore:
        """基于关键点计算表情分数（简化版）"""
        try:
            # 关键点索引
            left_eye_top = 159
            left_eye_bottom = 145
            right_eye_top = 386
            right_eye_bottom = 374
            mouth_top = 13
            mouth_bottom = 14
            left_eye_corner = 33
            right_eye_corner = 263

            if len(landmarks) <= max(left_eye_top, right_eye_top, mouth_top, left_eye_corner):
                return ExpressionScore(
                    happiness=50, sadness=10, anger=5,
                    surprise=5, neutral=30, dominant="neutral"
                )

            def dist(a, b):
                return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

            eye_distance = dist(landmarks[left_eye_corner], landmarks[right_eye_corner])
            mouth_open = dist(landmarks[mouth_top], landmarks[mouth_bottom]) / (eye_distance + 1e-6)
            left_eye_open = dist(landmarks[left_eye_top], landmarks[left_eye_bottom]) / (eye_distance + 1e-6)
            right_eye_open = dist(landmarks[right_eye_top], landmarks[right_eye_bottom]) / (eye_distance + 1e-6)

            mouth_w = dist(landmarks[61][:2], landmarks[291][:2]) if len(landmarks) > 291 else 0.5
            mouth_h = mouth_open * eye_distance
            smile_ratio = mouth_w / (mouth_h + 1e-6) if mouth_h > 0 else 1.0

            happiness = min(100.0, smile_ratio * 100)
            sadness = max(0.0, 50 - smile_ratio * 60 + mouth_open * 30)
            anger = 5.0
            surprise = min(100.0, mouth_open * 150)
            neutral = max(0.0, 100.0 - happiness - sadness - anger - surprise)

            scores = {"happiness": happiness, "sadness": sadness, "anger": anger,
                      "surprise": surprise, "neutral": neutral}
            dominant = max(scores, key=scores.get)

            return ExpressionScore(
                happiness=happiness, sadness=sadness, anger=anger,
                surprise=surprise, neutral=neutral, dominant=dominant
            )
        except Exception as e:
            logger.warning(f"表情识别失败: {e}")
            return ExpressionScore(
                happiness=50, sadness=10, anger=5,
                surprise=5, neutral=30, dominant="neutral"
            )

    def _calc_face_blur(self, image: np.ndarray) -> float:
        """计算图像清晰度"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            score = min(100.0, laplacian_var / 5.0)
            return float(score)
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

    async def analyze_frame(self, frame: np.ndarray, timestamp_ms: int = 0) -> DemeanorData:
        """
        分析单帧图像（优先使用 MediaPipe FaceLandmarker，回退到 OpenCV Haar Cascade）

        Args:
            frame: BGR 格式的图像 numpy array
            timestamp_ms: 时间戳（毫秒）

        Returns:
            DemeanorData: 仪态数据
        """
        self._ensure_initialized()

        h, w = frame.shape[:2]
        blur_score = self._calc_face_blur(frame)
        landmarks = None

        # 优先使用 MediaPipe FaceLandmarker
        if self._use_face_mesh and self._face_landmarker:
            try:
                import mediapipe as mp
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                result = self._face_landmarker.detect(mp_image)

                if result.face_landmarks and len(result.face_landmarks) > 0:
                    face_landmarks = result.face_landmarks[0]
                    # 转换为 (x, y, z) 格式
                    landmarks = [[lm.x, lm.y, lm.z] for lm in face_landmarks]
                    logger.debug(f"MediaPipe 检测到 {len(face_landmarks)} 个关键点")
            except Exception as e:
                logger.warning(f"MediaPipe FaceLandmarker 检测失败: {e}")

        # 如果 MediaPipe 未检测到，使用 Haar Cascade 备用
        if not landmarks:
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )

            if len(faces) == 0:
                return DemeanorData(
                    face_detected=False,
                    face_count=0,
                    face_blur_score=blur_score,
                    timestamp_ms=timestamp_ms,
                )

            # 取最大的人脸
            face = max(faces, key=lambda f: f[2] * f[3])
            x, y, fw, fh = face

            # 计算人脸大小比例
            face_size_ratio = (fw * fh) / (w * h)
            landmarks = self._generate_synthetic_landmarks(x, y, fw, fh)

            head_pose = self._estimate_head_pose(landmarks)
            expression = self._detect_expression(landmarks)

            return DemeanorData(
                face_detected=True,
                face_count=len(faces),
                head_pose=head_pose,
                expression=expression,
                face_blur_score=blur_score,
                face_size_ratio=face_size_ratio,
                confidence=0.8,
                timestamp_ms=timestamp_ms,
            )

        # MediaPipe 检测成功
        face_size_ratio = self._calc_face_size_ratio(landmarks, h, w)
        head_pose = self._estimate_head_pose(landmarks)
        expression = self._detect_expression(landmarks)

        return DemeanorData(
            face_detected=True,
            face_count=1,
            head_pose=head_pose,
            expression=expression,
            face_blur_score=blur_score,
            face_size_ratio=face_size_ratio,
            confidence=1.0,
            timestamp_ms=timestamp_ms,
        )

    def _generate_synthetic_landmarks(self, x, y, w, h) -> list:
        """生成简化的人脸关键点（供头部姿态估计使用）"""
        # 基于人脸框生成近似关键点
        cx, cy = x + w // 2, y + h // 2

        landmarks = []
        # 468 个关键点位置（MediaPipe 格式），这里简化为 468 个均匀分布的点
        for i in range(468):
            # 简化的椭圆分布
            t = i / 468 * 2 * 3.14159
            r = 0.3 + 0.2 * (i % 10) / 10
            lx = cx + int(w * r * 0.5 * (1 if i % 2 == 0 else -1) * (0.5 + 0.5 * (i % 7) / 7))
            ly = cy + int(h * r * 0.6 * (1 if i % 3 == 0 else -1) * (0.3 + 0.7 * (i % 11) / 11))
            landmarks.append([lx / 640, ly / 480, 0])  # 归一化坐标

        # 确保关键点存在
        landmarks[33] = [x / 640, (y + h // 4) / 480, 0]      # 左眼
        landmarks[263] = [(x + w) / 640, (y + h // 4) / 480, 0] # 右眼
        landmarks[1] = [(x + w // 2) / 640, (y + h // 2) / 480, 0] # 鼻尖
        landmarks[61] = [(x + w // 4) / 640, (y + h * 3 // 4) / 480, 0] # 左嘴角
        landmarks[291] = [(x + w * 3 // 4) / 640, (y + h * 3 // 4) / 480, 0] # 右嘴角
        landmarks[152] = [(x + w // 2) / 640, (y + h) / 480, 0] # 下巴

        return landmarks

    async def analyze_video(
        self,
        video_path: str,
        sample_interval_sec: float = 1.0,
    ) -> list[DemeanorData]:
        """分析视频文件"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频文件: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        interval_frames = max(1, int(fps * sample_interval_sec))

        results = []
        frame_idx = 0
        timestamp_ms = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % interval_frames == 0:
                data = await self.analyze_frame(frame, timestamp_ms=int(timestamp_ms))
                results.append(data)

            frame_idx += 1
            timestamp_ms = cap.get(cv2.CAP_PROP_POS_MSEC)

        cap.release()
        return results


mediapipe_analyzer = MediaPipeDemeanorAnalyzer()
