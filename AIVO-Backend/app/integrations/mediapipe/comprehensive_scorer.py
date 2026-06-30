"""
综合仪态评估服务 - 整合视频、音频、问答数据，调用大模型打分
"""

import logging
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from app.agents.ai_client import ai_client
from app.integrations.mediapipe.enhanced_demeanor_models import (
    ComprehensiveDemeanorReport,
    HeadPoseStatistics,
    EyeStatistics,
    ExpressionStatistics,
    BodyStatistics,
    AudioStatistics,
)
from app.integrations.mediapipe.video_analyzer import enhanced_video_analyzer
from app.integrations.mediapipe.audio_analyzer import enhanced_audio_analyzer
from app.integrations.mediapipe.demeanor_tracker import DemeanorTracker, create_tracker

logger = logging.getLogger(__name__)


class ComprehensiveDemeanorScorer:
    """
    综合仪态评分服务

    功能：
    1. 接收前端推送的视频帧和音频数据
    2. 实时跟踪并聚合时序统计
    3. 面试结束时计算各维度评分
    4. 调用大模型生成综合评语和改进建议
    """

    # 评分权重
    WEIGHTS = {
        "head_pose": 0.20,       # 头部姿态
        "eye_contact": 0.20,     # 眼神交流
        "expression": 0.15,      # 表情管理
        "body_posture": 0.15,    # 肢体仪态
        "speech": 0.30,          # 语音表达
    }

    def __init__(self):
        self._trackers: Dict[str, DemeanorTracker] = {}  # session_id -> tracker

    def get_or_create_tracker(self, session_id: str) -> DemeanorTracker:
        """获取或创建指定会话的跟踪器"""
        if session_id not in self._trackers:
            self._trackers[session_id] = create_tracker()
        return self._trackers[session_id]

    def reset_tracker(self, session_id: str):
        """重置指定会话的跟踪器"""
        if session_id in self._trackers:
            del self._trackers[session_id]

    def process_video_frame(self, session_id: str, frame_data: Dict) -> Dict:
        """
        处理单帧视频数据

        Args:
            session_id: 会话ID
            frame_data: 帧数据 dict

        Returns:
            dict: 实时分析摘要
        """
        tracker = self.get_or_create_tracker(session_id)
        return tracker.append_video_frame(frame_data)

    def process_audio_segment(self, session_id: str, segment_data: Dict) -> Dict:
        """
        处理音频片段数据

        Args:
            session_id: 会话ID
            segment_data: 音频片段 dict

        Returns:
            dict: 实时分析摘要
        """
        tracker = self.get_or_create_tracker(session_id)
        return tracker.append_audio_segment(segment_data)

    def _score_head_pose(self, stats: HeadPoseStatistics) -> Dict:
        """计算头部姿态评分"""
        total_ms = max(1, stats.total_duration_ms)

        # 稳定性得分
        stability_score = stats.stability_rate * 100

        # 低头扣分
        look_down_ratio = stats.total_looking_down_ms / total_ms
        look_down_penalty = look_down_ratio * 40  # 最多扣40分

        # 仰头扣分
        look_up_ratio = stats.total_looking_up_ms / total_ms
        look_up_penalty = look_up_ratio * 30

        # 左右转头扣分
        turn_ratio = (stats.total_turning_left_ms + stats.total_turning_right_ms) / total_ms
        turn_penalty = turn_ratio * 35

        # 歪头扣分
        tilt_ratio = stats.total_tilting_ms / total_ms
        tilt_penalty = tilt_ratio * 25

        # 计算总分
        raw_score = 100 - look_down_penalty - look_up_penalty - turn_penalty - tilt_penalty
        raw_score = max(0, min(100, raw_score))

        # 综合稳定性权重
        final_score = raw_score * 0.6 + stability_score * 0.4
        final_score = round(max(0, min(100, final_score)), 1)

        breakdown = {
            "stability_rate": round(stats.stability_rate * 100, 1),
            "look_down_ratio": round(look_down_ratio * 100, 1),
            "look_up_ratio": round(look_up_ratio * 100, 1),
            "turn_ratio": round(turn_ratio * 100, 1),
            "tilt_ratio": round(tilt_ratio * 100, 1),
            "total_looking_down_ms": stats.total_looking_down_ms,
            "total_turning_left_count": stats.turning_left_count,
            "total_turning_right_count": stats.turning_right_count,
        }

        return {
            "score": final_score,
            "breakdown": breakdown,
            "issues": self._get_head_pose_issues(breakdown),
        }

    def _get_head_pose_issues(self, breakdown: Dict) -> List[str]:
        """获取头部姿态问题列表"""
        issues = []

        if breakdown["look_down_ratio"] > 10:
            issues.append(f"低头时间占比 {breakdown['look_down_ratio']:.1f}% 偏高")
        if breakdown["look_up_ratio"] > 8:
            issues.append(f"仰头时间占比 {breakdown['look_up_ratio']:.1f}% 偏高")
        if breakdown["turn_ratio"] > 15:
            issues.append(f"左右转头时间占比 {breakdown['turn_ratio']:.1f}% 偏高")
        if breakdown["tilt_ratio"] > 5:
            issues.append(f"歪头时间占比 {breakdown['tilt_ratio']:.1f}% 偏高")

        return issues

    def _score_eye_contact(self, eye_stats: EyeStatistics, head_stats: HeadPoseStatistics) -> Dict:
        """计算眼神交流评分"""
        total_ms = max(1, eye_stats.total_duration_ms)

        # 眨眼频率评分（正常范围 15-30 次/分钟）
        blink_freq = eye_stats.blink_frequency
        if 15 <= blink_freq <= 30:
            blink_score = 100
        elif blink_freq < 15:
            blink_score = max(50, 50 + (blink_freq / 15) * 50)
        else:
            blink_score = max(50, 100 - (blink_freq - 30) * 3)

        # 视线稳定性（基于头部姿态稳定性）
        gaze_stability_score = head_stats.stability_rate * 100

        # 闭眼走神扣分
        closed_ratio = eye_stats.total_eyes_closed_ms / total_ms
        closed_penalty = closed_ratio * 60

        # 计算总分
        raw_score = (blink_score * 0.3 + gaze_stability_score * 0.7) - closed_penalty
        final_score = round(max(0, min(100, raw_score)), 1)

        breakdown = {
            "blink_frequency": eye_stats.blink_frequency,
            "total_blinks": eye_stats.total_blinks,
            "eyes_closed_ms": eye_stats.total_eyes_closed_ms,
            "gaze_off_center_ms": eye_stats.total_gaze_off_center_ms,
        }

        issues = []
        if eye_stats.total_eyes_closed_ms > 3000:
            issues.append(f"闭眼走神时长 {eye_stats.total_eyes_closed_ms/1000:.1f}s 偏多")
        if blink_freq > 40:
            issues.append(f"眨眼过于频繁 ({blink_freq:.0f} 次/分钟)")

        return {
            "score": final_score,
            "breakdown": breakdown,
            "issues": issues,
        }

    def _score_expression(self, stats: ExpressionStatistics) -> Dict:
        """计算表情管理评分"""
        total_ms = max(1, stats.total_duration_ms)

        # 中性表情占比 → 得分
        neutral_ratio = stats.neutral_ratio
        happy_ratio = stats.happiness_ratio
        negative_ratio = stats.negative_ratio

        # 理想表情：大部分中性 + 适度微笑 + 少量负面
        base_score = neutral_ratio * 50 + happy_ratio * 50 - negative_ratio * 60

        # 负面情绪片段扣分
        if stats.longest_negative_episode_ms > 5000:
            base_score -= 15
        if stats.negative_episode_count > 3:
            base_score -= stats.negative_episode_count * 3

        final_score = round(max(0, min(100, base_score)), 1)

        breakdown = {
            "neutral_ratio": round(stats.neutral_ratio * 100, 1),
            "happy_ratio": round(stats.happiness_ratio * 100, 1),
            "negative_ratio": round(stats.negative_ratio * 100, 1),
            "dominant_expression": stats.dominant_expression,
            "negative_episode_count": stats.negative_episode_count,
            "longest_negative_ms": stats.longest_negative_episode_ms,
        }

        issues = []
        if stats.negative_ratio > 0.2:
            issues.append(f"负面情绪占比 {stats.negative_ratio*100:.1f}% 偏高")
        if stats.longest_negative_episode_ms > 5000:
            issues.append(f"存在持续 {stats.longest_negative_episode_ms/1000:.1f}s 的负面情绪")

        return {
            "score": final_score,
            "breakdown": breakdown,
            "issues": issues,
        }

    def _score_body_posture(self, stats: BodyStatistics) -> Dict:
        """计算肢体仪态评分"""
        total_ms = max(1, stats.total_duration_ms)

        # 驼背扣分
        hunchback_penalty = stats.hunchback_ratio * 40

        # 抱臂扣分
        arm_crossed_penalty = stats.arm_crossed_ratio * 30

        # 身体晃动扣分
        sway_ratio = stats.total_body_sway_ms / total_ms
        sway_penalty = sway_ratio * 30

        # 手部动作扣分（过度动作才扣分）
        hand_ratio = stats.excessive_hand_motion_ms / total_ms
        hand_penalty = hand_ratio * 20

        # 计算总分
        raw_score = 100 - hunchback_penalty - arm_crossed_penalty - sway_penalty - hand_penalty
        final_score = round(max(0, min(100, raw_score)), 1)

        breakdown = {
            "hunchback_ratio": round(stats.hunchback_ratio * 100, 1),
            "arm_crossed_ratio": round(stats.arm_crossed_ratio * 100, 1),
            "sway_ratio": round(sway_ratio * 100, 1),
            "hand_motion_ms": stats.excessive_hand_motion_ms,
            "proper_posture_ratio": round(stats.proper_posture_ratio * 100, 1),
        }

        issues = []
        if stats.hunchback_ratio > 0.2:
            issues.append(f"驼背时间占比 {stats.hunchback_ratio*100:.1f}% 偏高")
        if stats.arm_crossed_ratio > 0.3:
            issues.append(f"抱臂时间占比 {stats.arm_crossed_ratio*100:.1f}% 偏高")
        if stats.excessive_hand_motion_ms > 10000:
            issues.append(f"手部小动作过多 ({(stats.excessive_hand_motion_ms/1000):.1f}s)")

        return {
            "score": final_score,
            "breakdown": breakdown,
            "issues": issues,
        }

    def _score_speech(self, audio_stats: AudioStatistics) -> Dict:
        """计算语音表达评分"""
        total_ms = max(1, audio_stats.total_duration_ms)
        total_sec = total_ms / 1000

        # 语速评分（理想 4-6 字/秒）
        rate = audio_stats.avg_speaking_rate
        if 4 <= rate <= 6:
            speed_score = 100
        elif rate < 4:
            speed_score = max(30, 50 + rate * 12.5)
        else:
            speed_score = max(30, 100 - (rate - 6) * 15)

        # 卡顿扣分
        hesitation_ratio = audio_stats.total_hesitations / (total_sec / 60) if total_sec > 0 else 0  # 次/分钟
        hesitation_penalty = min(30, hesitation_ratio * 5)

        # 静音占比扣分
        silence_ratio = audio_stats.silence_ratio
        silence_penalty = silence_ratio * 40

        # 长静音次数扣分
        long_silence_penalty = min(20, audio_stats.long_silences * 5)

        # 计算总分
        raw_score = speed_score - hesitation_penalty - silence_penalty - long_silence_penalty
        final_score = round(max(0, min(100, raw_score)), 1)

        breakdown = {
            "avg_speaking_rate": audio_stats.avg_speaking_rate,
            "total_pauses": audio_stats.total_pauses,
            "total_hesitations": audio_stats.total_hesitations,
            "hesitation_duration_ms": audio_stats.total_hesitation_duration_ms,
            "silence_ratio": round(audio_stats.silence_ratio * 100, 1),
            "long_silences": audio_stats.long_silences,
        }

        issues = []
        if rate < 4:
            issues.append(f"语速偏慢 ({rate:.1f} 字/秒)")
        elif rate > 8:
            issues.append(f"语速偏快 ({rate:.1f} 字/秒)")
        if audio_stats.total_hesitations > 5:
            issues.append(f"卡顿较多 ({audio_stats.total_hesitations} 次)")
        if audio_stats.long_silences > 2:
            issues.append(f"存在 {audio_stats.long_silences} 次长沉默 (>3秒)")

        return {
            "score": final_score,
            "breakdown": breakdown,
            "issues": issues,
        }

    def _calculate_composite_score(
        self,
        head_pose_score: float,
        eye_contact_score: float,
        expression_score: float,
        body_posture_score: float,
        speech_score: float,
    ) -> tuple[float, str]:
        """计算综合评分"""
        total = (
            head_pose_score * self.WEIGHTS["head_pose"] +
            eye_contact_score * self.WEIGHTS["eye_contact"] +
            expression_score * self.WEIGHTS["expression"] +
            body_posture_score * self.WEIGHTS["body_posture"] +
            speech_score * self.WEIGHTS["speech"]
        )

        # 等级划分
        if total >= 90:
            grade = "A"
        elif total >= 80:
            grade = "B"
        elif total >= 70:
            grade = "C"
        elif total >= 60:
            grade = "D"
        else:
            grade = "E"

        return round(total, 1), grade

    async def generate_llm_feedback(
        self,
        report: ComprehensiveDemeanorReport,
        qa_data: Optional[Dict] = None,
    ) -> Dict:
        """
        调用大模型生成综合评语和改进建议

        Args:
            report: 综合报告
            qa_data: 问答数据（可选）

        Returns:
            dict: {overall_comment, strengths, weaknesses, suggestions}
        """
        # 构建完整的问答对话记录
        qa_dialogue = ""
        if qa_data:
            qa_list = qa_data.get("answers", [])
            if qa_list:
                qa_dialogue_lines = []
                for i, a in enumerate(qa_list):
                    question = a.get("question", a.get("question_content", ""))[:200]
                    answer = a.get("answer", a.get("answer_content", ""))[:500]
                    qa_dialogue_lines.append(f"面试官：{question}\n考生：{answer}")
                qa_dialogue = "\n\n".join(qa_dialogue_lines)
            else:
                qa_dialogue = "（暂无问答记录）"
        else:
            qa_dialogue = "（暂无问答记录）"

        # 构建详细的仪态量化数据
        video_summary = f"""【模拟面试场景】
1. 问答对话记录：
{qa_dialogue}

2. 考生全程仪态量化数据：
- 总时长：{report.total_duration_ms/1000:.0f}秒
- 头部姿态：
  - 低头累计 {report.head_pose_stats.total_looking_down_ms/1000:.1f}秒
  - 频繁左右转头 {report.head_pose_stats.turning_left_count + report.head_pose_stats.turning_right_count}次
  - 头部稳定性：{report.head_pose_stats.stability_rate*100:.1f}%
- 眼神：
  - 眨眼频率：{report.eye_stats.blink_frequency:.1f}次/分钟（正常15-30次/分钟）
  - 视线偏移累计 {report.eye_stats.total_gaze_off_center_ms/1000:.1f}秒
  - 存在多次长时间躲闪
- 面部表情：
  - 中性占比 {report.expression_stats.neutral_ratio*100:.1f}%
  - 微笑占比 {report.expression_stats.happiness_ratio*100:.1f}%
  - 负面情绪占比 {report.expression_stats.negative_ratio*100:.1f}%
- 肢体姿态：
  - 手部小动作频繁
  - 抱臂：{report.body_stats.arm_crossed_ratio*100:.1f}%
  - 含胸驼背：{report.body_stats.hunchback_ratio*100:.1f}%
- 语音：
  - 平均语速：{report.audio_stats.avg_speaking_rate:.1f}字/秒
  - 卡顿 {report.audio_stats.total_hesitations}次
  - 停顿频繁
  - 语速忽快忽慢"""

        # 分项评分数据
        score_breakdown = f"""【分项评分】
- 仪态专项得分（0-30分）：{report.head_pose_score * 0.3 + report.eye_contact_score * 0.3 + report.expression_score * 0.2 + report.body_stats.proper_posture_ratio * 30:.1f}分
- 语言表达专项得分（0-30分）：{report.speech_score * 0.3:.1f}分
- 问答内容专业度得分（0-40分）：待大模型根据问答内容评估"""

        # 计算总分
        content_score = 75  # 假设中等水平
        posture_score = report.head_pose_score * 0.3 + report.eye_contact_score * 0.3 + report.expression_score * 0.2 + report.body_stats.proper_posture_ratio * 30
        speech_score_value = report.speech_score * 0.3
        total_score = posture_score + speech_score_value + content_score

        prompt = f"""【面试仪态综合评估任务】

{video_summary}

{score_breakdown}
- 总分（满分100）：待计算

【评估任务】
请你完成以下评估：

1. 仪态专项得分（0-30分）
   评估维度：头部稳定、眼神交流、面部表情、肢体姿态
   重点关注：低头时间、视线偏移、负面情绪占比、肢体小动作

2. 语言表达专项得分（0-30分）
   评估维度：语速控制、停顿频率、表达流畅度
   重点关注：卡顿次数、静音占比、语速稳定性

3. 问答内容专业度得分（0-40分）
   评估维度：回答准确性、专业深度、逻辑性、相关经验
   根据问答内容评估

4. 总分（满分100）

5. 逐条指出仪态问题
   按严重程度列出所有仪态问题

6. 给出针对性面试仪态改进建议
   针对每项问题给出具体可行的改进方法

请用中文回复，返回严格的JSON格式（不包含markdown代码块）：
{{
    "posture_score": 仪态专项得分（0-30的整数或小数）,
    "speech_score": 语言表达专项得分（0-30的整数或小数）,
    "content_score": 问答内容专业度得分（0-40的整数或小数）,
    "total_score": 总分（0-100的整数或小数）,
    "posture_issues": [
        "问题1：具体描述...",
        "问题2：具体描述..."
    ],
    "speech_issues": [
        "问题1：具体描述...",
        "问题2：具体描述..."
    ],
    "content_issues": [
        "问题1：具体描述...",
        "问题2：具体描述..."
    ],
    "posture_suggestions": [
        "建议1：具体可操作的方法...",
        "建议2：具体可操作的方法..."
    ],
    "speech_suggestions": [
        "建议1：具体可操作的方法...",
        "建议2：具体可操作的方法..."
    ],
    "content_suggestions": [
        "建议1：具体可操作的方法...",
        "建议2：具体可操作的方法..."
    ]
}}

重要要求：
- 评分要客观公正，基于提供的数据
- 问题描述要具体，指出具体的数据指标
- 建议要切实可行，给出具体操作方法
- 保持专业、友善的评价语气"""

        try:
            response = await ai_client.chat(
                messages=[{"role": "user", "content": prompt}],
                stream=False,
            )

            # 解析 JSON
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            result = json.loads(response.strip())

            # 构建综合评语
            overall_comment = f"仪态专项得分{result.get('posture_score', 0)}分，语言表达{result.get('speech_score', 0)}分，问答内容{result.get('content_score', 0)}分，总分{result.get('total_score', 0)}分。"

            # 合并所有问题和优点
            posture_issues = result.get("posture_issues", [])
            speech_issues = result.get("speech_issues", [])
            content_issues = result.get("content_issues", [])
            all_issues = posture_issues + speech_issues + content_issues

            # 从问题反推优点（做得好的方面）
            strengths = []
            if report.head_pose_stats.stability_rate > 0.8:
                strengths.append("头部姿态相对稳定")
            if report.expression_stats.happiness_ratio > 0.1:
                strengths.append("保持适度微笑，表情自然")
            if report.audio_stats.avg_speaking_rate >= 4 and report.audio_stats.avg_speaking_rate <= 6:
                strengths.append("语速控制得当")
            if not strengths:
                strengths.append("整体表现中规中矩，有改进空间")

            return {
                "overall_comment": overall_comment,
                "strengths": result.get("strengths", strengths),
                "weaknesses": result.get("posture_issues", []) + result.get("speech_issues", []) + result.get("content_issues", []),
                "suggestions": result.get("posture_suggestions", []) + result.get("speech_suggestions", []) + result.get("content_suggestions", []),
                # 扩展字段
                "posture_score": result.get("posture_score", 0),
                "speech_score": result.get("speech_score", 0),
                "content_score": result.get("content_score", 0),
                "total_score": result.get("total_score", 0),
                "posture_issues": result.get("posture_issues", []),
                "speech_issues": result.get("speech_issues", []),
                "content_issues": result.get("content_issues", []),
                "posture_suggestions": result.get("posture_suggestions", []),
                "speech_suggestions": result.get("speech_suggestions", []),
                "content_suggestions": result.get("content_suggestions", []),
            }
        except Exception as e:
            logger.error(f"LLM 反馈生成失败: {e}")
            return {
                "overall_comment": "面试仪态表现一般，建议注意眼神交流和表达流畅度",
                "strengths": ["表情管理较好"],
                "weaknesses": ["表达流畅度有待提升", "仪态细节需注意"],
                "suggestions": ["保持自然微笑", "注意与面试官的眼神交流", "减少不必要的停顿"],
                "posture_score": 15,
                "speech_score": 15,
                "content_score": 30,
                "total_score": 60,
                "posture_issues": ["头部稳定性不足", "视线偏移较多"],
                "speech_issues": ["卡顿次数较多", "语速不够稳定"],
                "content_issues": ["回答深度有待加强"],
                "posture_suggestions": ["保持目视前方", "减少不必要的头部动作"],
                "speech_suggestions": ["放慢语速", "减少停顿", "提前组织语言"],
                "content_suggestions": ["加强专业知识储备", "多用实例说明"],
            }

    async def evaluate_comprehensive(
        self,
        session_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        qa_data: Optional[Dict] = None,
    ) -> ComprehensiveDemeanorReport:
        """
        综合评估 - 面试结束时调用

        Args:
            session_id: 会话ID
            start_time: 面试开始时间
            end_time: 面试结束时间
            qa_data: 问答数据

        Returns:
            ComprehensiveDemeanorReport: 综合报告
        """
        tracker = self.get_or_create_tracker(session_id)

        # 设置时间范围
        if start_time and end_time:
            start_ms = int(start_time.timestamp() * 1000)
            end_ms = int(end_time.timestamp() * 1000)
            tracker.set_time_range(start_ms, end_ms)
        else:
            tracker.set_time_range(0, 0)

        # 计算统计数据
        stats = tracker.compute_final_statistics()

        head_pose_stats = stats["head_pose_stats"]
        eye_stats = stats["eye_stats"]
        expression_stats = stats["expression_stats"]
        body_stats = stats["body_stats"]
        audio_stats = stats["audio_stats"]

        # 计算各维度评分
        head_pose_result = self._score_head_pose(head_pose_stats)
        eye_contact_result = self._score_eye_contact(eye_stats, head_pose_stats)
        expression_result = self._score_expression(expression_stats)
        body_posture_result = self._score_body_posture(body_stats)
        speech_result = self._score_speech(audio_stats)

        # 计算综合评分
        composite_score, grade = self._calculate_composite_score(
            head_pose_result["score"],
            eye_contact_result["score"],
            expression_result["score"],
            body_posture_result["score"],
            speech_result["score"],
        )

        # 构建报告
        report = ComprehensiveDemeanorReport(
            session_id=session_id,
            interview_start_time=start_time.isoformat() if start_time else "",
            interview_end_time=end_time.isoformat() if end_time else "",
            total_duration_ms=head_pose_stats.total_duration_ms,
            valid_video_frames=head_pose_stats.valid_frames,
            valid_audio_segments=audio_stats.total_duration_ms,
            head_pose_stats=head_pose_stats,
            eye_stats=eye_stats,
            expression_stats=expression_stats,
            body_stats=body_stats,
            audio_stats=audio_stats,
            head_pose_score=head_pose_result["score"],
            head_pose_breakdown=head_pose_result["breakdown"],
            eye_contact_score=eye_contact_result["score"],
            eye_contact_breakdown=eye_contact_result["breakdown"],
            expression_score=expression_result["score"],
            expression_breakdown=expression_result["breakdown"],
            body_posture_score=body_posture_result["score"],
            body_posture_breakdown=body_posture_result["breakdown"],
            speech_score=speech_result["score"],
            speech_breakdown=speech_result["breakdown"],
            demeanor_total_score=composite_score,
            demeanor_grade=grade,
            raw_video_frames_count=tracker._frame_count,
            raw_audio_segments_count=len(tracker._audio_segments),
        )

        # 调用大模型生成评语
        llm_feedback = await self.generate_llm_feedback(report, qa_data)
        report.llm_overall_comment = llm_feedback["overall_comment"]
        report.llm_strengths = llm_feedback["strengths"]
        report.llm_weaknesses = llm_feedback["weaknesses"]
        report.llm_suggestions = llm_feedback["suggestions"]

        # 新增详细评分字段
        report.llm_posture_score = llm_feedback.get("posture_score", 0.0)
        report.llm_speech_score = llm_feedback.get("speech_score", 0.0)
        report.llm_content_score = llm_feedback.get("content_score", 0.0)
        report.llm_total_score = llm_feedback.get("total_score", 0.0)
        report.llm_posture_issues = llm_feedback.get("posture_issues", [])
        report.llm_speech_issues = llm_feedback.get("speech_issues", [])
        report.llm_content_issues = llm_feedback.get("content_issues", [])
        report.llm_posture_suggestions = llm_feedback.get("posture_suggestions", [])
        report.llm_speech_suggestions = llm_feedback.get("speech_suggestions", [])
        report.llm_content_suggestions = llm_feedback.get("content_suggestions", [])

        # 清理跟踪器
        self.reset_tracker(session_id)

        return report


# 全局实例
comprehensive_scorer = ComprehensiveDemeanorScorer()
