"""仪态评估服务 - 综合 AI 模型打分"""

import logging
from dataclasses import dataclass, asdict
from typing import Optional

from app.agents.ai_client import ai_client
from app.integrations.mediapipe import DemeanorData, HeadPose, ExpressionScore

logger = logging.getLogger(__name__)


@dataclass
class DemeanorScore:
    """仪态评分结果"""
    total_score: float          # 总分 0-100
    posture_score: float        # 仪态端正度 0-100
    expression_score: float     # 表情管理 0-100
    eye_contact_score: float   # 眼神交流 0-100
    confidence_score: float     # 自信度 0-100
    feedback: str               # 详细反馈
    suggestions: list[str]     # 改进建议


class DemeanorEvaluationService:
    """仪态评估服务"""

    def __init__(self):
        self.ai_client = ai_client

    def _calculate_rule_based_score(self, data: DemeanorData) -> dict:
        """基于规则计算基础分数"""
        posture_score = 100.0
        expression_score = 100.0
        eye_contact_score = 100.0

        # 头部姿态评分
        if data.head_pose:
            yaw = abs(data.head_pose.yaw)
            pitch = abs(data.head_pose.pitch)
            roll = abs(data.head_pose.roll)

            # 偏航角过大（转头太多）
            if yaw > 30:
                posture_score -= (yaw - 30) * 1.5
            elif yaw > 15:
                posture_score -= (yaw - 15) * 0.8

            # 俯仰角过大（低头/抬头太多）
            if pitch > 20:
                posture_score -= (pitch - 20) * 1.2
            elif pitch > 10:
                posture_score -= (pitch - 10) * 0.5

            # 翻滚角过大（歪头）
            if roll > 15:
                posture_score -= (roll - 15) * 1.5

            posture_score = max(0.0, min(100.0, posture_score))

            # 眼神评估（基于 yaw 角，侧面表示眼神偏离）
            eye_contact_score = max(0.0, 100.0 - yaw * 1.5)

        # 表情评分
        if data.expression:
            dominant = data.expression.dominant
            happy = data.expression.happiness
            neutral = data.expression.neutral

            if dominant in ["anger", "sadness"]:
                expression_score = 40.0
            elif dominant == "surprise":
                expression_score = 60.0
            elif dominant == "happiness" and happy > 30:
                expression_score = 85.0
            else:
                expression_score = max(60.0, neutral + 10)

        # 清晰度
        if data.face_blur_score < 50:
            posture_score *= 0.7
            expression_score *= 0.7

        # 人脸占比
        if data.face_size_ratio < 0.05:
            posture_score *= 0.8
            eye_contact_score *= 0.8

        return {
            "posture_score": round(posture_score, 1),
            "expression_score": round(expression_score, 1),
            "eye_contact_score": round(eye_contact_score, 1),
        }

    def _calculate_confidence_score(self, data: DemeanorData, rule_scores: dict) -> float:
        """计算自信度分数"""
        confidence = 100.0

        # 表情平静且微笑 → 自信
        if data.expression:
            happy = data.expression.happiness
            if happy > 20 and happy < 60:
                confidence += 10
            elif happy >= 60:
                confidence += 5
            elif happy < 10:
                confidence -= 10

        # 头部姿态稳定 → 自信
        if data.head_pose:
            stability = 20 - abs(data.head_pose.yaw) - abs(data.head_pose.pitch)
            confidence += max(0, stability)

        # 检测置信度
        confidence += (data.confidence - 0.5) * 20 if data.confidence else 0

        # 规则分数影响
        avg_rule = sum([
            rule_scores["posture_score"],
            rule_scores["expression_score"],
            rule_scores["eye_contact_score"]
        ]) / 3
        confidence = confidence * 0.5 + avg_rule * 0.5

        return round(max(0.0, min(100.0, confidence)), 1)

    async def evaluate(
        self,
        demeanor_data: DemeanorData | list[DemeanorData],
    ) -> DemeanorScore:
        """
        综合评估仪态表现

        Args:
            demeanor_data: 单帧数据或视频多帧数据

        Returns:
            DemeanorScore: 评估结果
        """
        # 聚合多帧数据
        if isinstance(demeanor_data, list):
            if not demeanor_data:
                return DemeanorScore(
                    total_score=60.0,
                    posture_score=60.0,
                    expression_score=60.0,
                    eye_contact_score=60.0,
                    confidence_score=60.0,
                    feedback="无仪态数据",
                    suggestions=["请确保摄像头正常工作"]
                )

            # 计算平均值
            avg_posture = []
            avg_expression = []
            avg_eye = []
            avg_confidence = []

            for frame_data in demeanor_data:
                rule_scores = self._calculate_rule_based_score(frame_data)
                avg_posture.append(rule_scores["posture_score"])
                avg_expression.append(rule_scores["expression_score"])
                avg_eye.append(rule_scores["eye_contact_score"])
                avg_confidence.append(frame_data.confidence)

            base_scores = {
                "posture_score": sum(avg_posture) / len(avg_posture),
                "expression_score": sum(avg_expression) / len(avg_expression),
                "eye_contact_score": sum(avg_eye) / len(avg_eye),
            }
            avg_conf = sum(avg_confidence) / len(avg_confidence) if avg_confidence else 0.5
        else:
            base_scores = self._calculate_rule_based_score(demeanor_data)
            avg_conf = demeanor_data.confidence

        # 计算自信度
        conf_score = self._calculate_confidence_score(demeanor_data, base_scores)

        # 计算总分
        total = (
            base_scores["posture_score"] * 0.30 +
            base_scores["expression_score"] * 0.25 +
            base_scores["eye_contact_score"] * 0.25 +
            conf_score * 0.20
        )

        # 收集表情和姿态详情
        if isinstance(demeanor_data, list):
            sample = demeanor_data[0] if demeanor_data else None
        else:
            sample = demeanor_data

        # 调用大模型生成详细反馈
        feedback, suggestions = await self._generate_feedback(
            sample, base_scores, conf_score
        )

        return DemeanorScore(
            total_score=round(total, 1),
            posture_score=round(base_scores["posture_score"], 1),
            expression_score=round(base_scores["expression_score"], 1),
            eye_contact_score=round(base_scores["eye_contact_score"], 1),
            confidence_score=conf_score,
            feedback=feedback,
            suggestions=suggestions,
        )

    async def _generate_feedback(
        self,
        data: DemeanorData,
        base_scores: dict,
        confidence_score: float,
    ) -> tuple[str, list[str]]:
        """调用大模型生成反馈和建议"""
        try:
            # 构建描述
            pose_desc = ""
            expr_desc = ""
            conf_desc = ""

            if data.head_pose:
                yaw = data.head_pose.yaw
                pitch = data.head_pose.pitch
                roll = data.head_pose.roll

                issues = []
                if abs(yaw) > 20:
                    issues.append(f"头部向{'左' if yaw > 0 else '右'}偏转{abs(yaw):.1f}°")
                if abs(pitch) > 15:
                    issues.append(f"头部{'低头' if pitch > 0 else '抬头'}{abs(pitch):.1f}°")
                if abs(roll) > 10:
                    issues.append(f"头部歪斜{abs(roll):.1f}°")

                pose_desc = "；".join(issues) if issues else "姿态端正"

            if data.expression:
                dominant = data.expression.dominant
                expr_map = {
                    "happiness": "表情自然、略带微笑",
                    "neutral": "表情平静",
                    "sadness": "表情略显低落",
                    "anger": "表情严肃",
                    "surprise": "表情惊讶",
                }
                expr_desc = expr_map.get(dominant, "表情正常")

            conf_map = {
                (80, 100): "显得非常自信",
                (60, 80): "表现较为自信",
                (40, 60): "略显紧张",
                (0, 40): "明显紧张",
            }
            for (low, high), desc in conf_map.items():
                if low <= confidence_score < high:
                    conf_desc = desc
                    break

            prompt = f"""作为面试官，请对候选人的仪态表现进行评价。

仪态数据：
- 姿态评估：{pose_desc}
- 表情状态：{expr_desc}
- 自信程度：{conf_desc}

分项评分：
- 仪态端正度：{base_scores['posture_score']:.1f}/100
- 表情管理：{base_scores['expression_score']:.1f}/100
- 眼神交流：{base_scores['eye_contact_score']:.1f}/100
- 自信度：{confidence_score:.1f}/100

请用中文回复，返回JSON格式：
{{
    "feedback": "一段50-80字的总体评价",
    "suggestions": ["建议1", "建议2", "建议3"]
}}"""

            response = await self.ai_client.chat(
                messages=[{"role": "user", "content": prompt}],
                stream=False,
            )

            # 解析 JSON
            import json
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            result = json.loads(response.strip())
            return result.get("feedback", "仪态表现良好"), result.get("suggestions", [])

        except Exception as e:
            logger.error(f"生成仪态反馈失败: {e}")
            return "仪态表现一般", ["保持自然微笑", "注意眼神交流"]


demeanor_service = DemeanorEvaluationService()
