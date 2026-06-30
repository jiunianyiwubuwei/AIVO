"""增强的 AI 模型客户端 - 支持结构化输出和更好的错误处理"""

import json
import re
from typing import AsyncIterator, Optional, Callable

import httpx
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import settings
from app.agents.prompts import (
    build_question_generation_prompt,
    build_summary_prompt,
    ANSWER_EVALUATION_PROMPT,
    FOLLOW_UP_PROMPT,
    CHAT_PROMPT,
    SYSTEM_PROMPTS,
)


class AIResponseError(Exception):
    """AI 响应错误"""
    def __init__(self, message: str, provider: str = None):
        self.message = message
        self.provider = provider
        super().__init__(self.message)


class StructuredOutput(BaseModel):
    """结构化输出基类"""
    class Config:
        extra = "allow"


class ResumeAnalysisResult(StructuredOutput):
    """简历分析结果"""
    resumeScore: int = 0
    resumeAnalysis: str = ""
    resumeStrengths: list[str] = []
    resumeWeaknesses: list[str] = []
    questions: list[dict] = []


class AnswerEvaluationResult(StructuredOutput):
    """回答评估结果"""
    score: int = 60
    accuracy: int = 12
    completeness: int = 12
    depth: int = 12
    clarity: int = 12
    relevance: int = 12
    evaluation: str = ""
    suggestions: str = ""
    follow_up_needed: bool = False
    follow_up_question: Optional[str] = None


def _create_http_client() -> httpx.AsyncClient:
    """创建 HTTP 客户端，支持代理"""
    import os
    timeout = httpx.Timeout(120.0, connect=30.0)
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    if proxy:
        return httpx.AsyncClient(timeout=timeout, proxy=proxy)
    return httpx.AsyncClient(timeout=timeout)


class EnhancedAIClient:
    """增强的 AI 模型客户端"""

    def __init__(self):
        self.providers: dict[str, dict] = {}
        self._http_client = _create_http_client()
        self._init_providers()

    def _init_providers(self):
        """初始化提供商"""
        for name, config in settings.ai.providers.items():
            if config.base_url and config.api_key:
                self.providers[name] = {
                    "client": AsyncOpenAI(
                        api_key=config.api_key,
                        base_url=config.base_url,
                        http_client=self._http_client,
                    ),
                    "model": config.model,
                }

    def _get_provider_config(self, provider: Optional[str] = None) -> tuple[AsyncOpenAI, str]:
        """获取提供商配置"""
        provider_name = provider or settings.ai.default_provider
        if provider_name not in self.providers:
            raise AIResponseError(f"Unknown provider: {provider_name}", provider_name)

        config = self.providers[provider_name]
        return config["client"], config["model"]

    def _add_system_prompt(
        self,
        messages: list[dict],
        default_prompt: str = None,
    ) -> list[dict]:
        """添加系统提示词"""
        system_messages = [m for m in messages if m.get("role") == "system"]
        user_messages = [m for m in messages if m.get("role") != "system"]

        if not system_messages and default_prompt:
            system_messages = [{"role": "system", "content": default_prompt}]

        return system_messages + user_messages

    async def chat(
        self,
        messages: list[dict],
        provider: Optional[str] = None,
        stream: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> AsyncIterator[str] | str:
        """发送聊天请求"""
        client, model = self._get_provider_config(provider)
        all_messages = self._add_system_prompt(messages)

        if stream:
            return self._stream_response(
                client, model, all_messages,
                temperature=temperature, max_tokens=max_tokens, **kwargs
            )
        return await self._blocking_response(
            client, model, all_messages,
            temperature=temperature, max_tokens=max_tokens, **kwargs
        )

    async def _blocking_response(
        self,
        client: AsyncOpenAI,
        model: str,
        messages: list[dict],
        **kwargs,
    ) -> str:
        """阻塞式响应"""
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            raise AIResponseError(f"AI request failed: {str(e)}") from e

    async def _stream_response(
        self,
        client: AsyncOpenAI,
        model: str,
        messages: list[dict],
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式响应"""
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                **kwargs,
            )

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            raise AIResponseError(f"AI stream failed: {str(e)}") from e

    def _parse_json_response(self, response: str) -> dict:
        """解析 JSON 响应"""
        # 尝试提取 JSON 代码块
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        return json.loads(response.strip())

    async def generate_questions(
        self,
        direction: str,
        resume_content: Optional[str] = None,
        count: int = 5,
    ) -> tuple[list[dict], Optional[dict]]:
        """
        生成面试问题

        Returns:
            tuple: (questions, resume_analysis)
        """
        prompt = build_question_generation_prompt(direction, resume_content, count)

        response = await self.chat(
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )

        try:
            data = self._parse_json_response(response)

            resume_analysis = None
            if isinstance(data, dict):
                resume_analysis = {
                    "score": data.get("resumeScore"),
                    "analysis": data.get("resumeAnalysis"),
                    "strengths": data.get("resumeStrengths", []),
                    "weaknesses": data.get("resumeWeaknesses", []),
                }
                return data.get("questions", []), resume_analysis

            return data if isinstance(data, list) else [], None

        except (json.JSONDecodeError, Exception):
            return self._parse_questions_from_text(response), None

    def _parse_questions_from_text(self, text: str) -> list[dict]:
        """从文本中解析问题"""
        questions = []
        for i, line in enumerate(text.strip().split("\n")):
            if line.strip() and not line.startswith("#"):
                questions.append({
                    "id": f"q_{i+1}",
                    "number": str(i + 1),
                    "content": line.strip(),
                    "category": "技术问题",
                    "difficulty": 3,
                    "expected_duration": 120,
                })
        return questions[:5]

    async def evaluate_answer(
        self,
        question: str,
        answer: str,
        follow_up_count: int = 0,
    ) -> AnswerEvaluationResult:
        """评估回答"""
        prompt = ANSWER_EVALUATION_PROMPT.format(
            question=question,
            answer=answer,
            follow_up_count=follow_up_count,
        )

        response = await self.chat(
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )

        try:
            result = self._parse_json_response(response)

            evaluation = AnswerEvaluationResult(**result)

            # 确保有追问相关字段
            if evaluation.follow_up_needed and not evaluation.follow_up_question:
                evaluation.follow_up_question = "你刚才的回答还可以继续深入，能详细说说具体的实现细节吗？"

            return evaluation

        except (json.JSONDecodeError, Exception):
            return AnswerEvaluationResult(
                score=60,
                evaluation=response,
                suggestions="评估生成失败",
                follow_up_needed=False,
            )

    async def generate_follow_up(
        self,
        question: str,
        answer: str,
        previous_follow_ups: list[str],
    ) -> str:
        """生成追问"""
        previous_text = "\n".join([f"- {q}" for q in previous_follow_ups]) if previous_follow_ups else "无"

        prompt = FOLLOW_UP_PROMPT.format(
            question=question,
            answer=answer,
            previous_text=previous_text,
        )

        response = await self.chat(
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )

        return response.strip()

    async def generate_summary(
        self,
        questions: list[dict],
        answers: list[dict],
    ) -> str:
        """生成面试总结"""
        qa_pairs = self._build_qa_pairs(questions, answers)

        if not qa_pairs:
            return "面试结束，暂无详细问答记录。"

        main_qa = [p for p in qa_pairs if not p.get("is_follow_up")]
        total_score = sum(p["score"] for p in main_qa)
        avg_score = total_score / len(main_qa) if main_qa else 0

        prompt = build_summary_prompt(
            qa_pairs=qa_pairs,
            main_count=len(main_qa),
            total_score=total_score,
            avg_score=avg_score,
        )

        response = await self.chat(
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )

        return response.strip()

    def _build_qa_pairs(self, questions: list[dict], answers: list[dict]) -> list[dict]:
        """构建问答对"""
        qa_pairs = []
        for answer in answers:
            q_number = answer.get("question_number", "")
            q_content = answer.get("question_content", "")

            if not q_content:
                for q in questions:
                    if q.get("number") == q_number or q.get("id") == q_number:
                        q_content = q.get("content", "")
                        break

            qa_pairs.append({
                "question": q_content or "未知问题",
                "answer": answer.get("answer_content", answer.get("evaluation", "")),
                "score": answer.get("score", 0),
                "feedback": answer.get("feedback", answer.get("evaluation", "")),
                "is_follow_up": answer.get("is_follow_up", False),
            })

        return qa_pairs

    async def chat_with_history(
        self,
        messages: list[dict],
        session_id: str,
        system_prompt: str = None,
        provider: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        聊天（支持上下文）

        Args:
            messages: 消息历史
            session_id: 会话 ID
            system_prompt: 系统提示词
            provider: AI 提供商
        """
        default_prompt = system_prompt or SYSTEM_PROMPTS["general"]
        full_messages = self._add_system_prompt(messages, default_prompt)

        client, model = self._get_provider_config(provider)

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=full_messages,
                stream=True,
            )

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            raise AIResponseError(f"Chat stream failed: {str(e)}") from e


# 全局实例
enhanced_ai_client = EnhancedAIClient()
