"""AI 模型客户端 - 支持多种提供商

本模块提供向后兼容的接口。
核心 Prompt 已迁移到 app/agents/prompts.py 模块。
"""

import json
import os
from typing import AsyncIterator, Optional

import httpx
from openai import AsyncOpenAI

from app.core.config import settings
from app.agents.prompts import (
    build_question_generation_prompt,
    build_summary_prompt,
    ANSWER_EVALUATION_PROMPT,
    FOLLOW_UP_PROMPT,
)


def _create_http_client() -> httpx.AsyncClient:
    """创建 HTTP 客户端，支持代理"""
    timeout = httpx.Timeout(120.0, connect=30.0)
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    if proxy:
        return httpx.AsyncClient(timeout=timeout, proxy=proxy)
    return httpx.AsyncClient(timeout=timeout)


class AIModelClient:
    """AI 模型客户端"""

    def __init__(self):
        self.providers: dict = {}
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

    def chat(
        self,
        messages: list[dict],
        provider: Optional[str] = None,
        stream: bool = True,
        **kwargs,
    ) -> AsyncIterator[str] | str:
        """发送聊天请求"""
        provider_name = provider or settings.ai.default_provider

        if provider_name not in self.providers:
            raise ValueError(f"Unknown provider: {provider_name}")

        provider_config = self.providers[provider_name]
        client = provider_config["client"]
        model = provider_config["model"]

        system_messages = [m for m in messages if m.get("role") == "system"]
        user_messages = [m for m in messages if m.get("role") != "system"]

        if not system_messages:
            system_messages = [{
                "role": "system",
                "content": "你是一个专业的面试官，擅长技术面试。请根据用户的表现给予客观评价。"
            }]

        all_messages = system_messages + user_messages

        if stream:
            return self._stream_response(client, model, all_messages, **kwargs)
        return self._blocking_response(client, model, all_messages, **kwargs)

    async def _blocking_response(
        self,
        client: AsyncOpenAI,
        model: str,
        messages: list[dict],
        **kwargs,
    ) -> str:
        """阻塞式响应"""
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs,
        )
        return response.choices[0].message.content or ""

    async def _stream_response(
        self,
        client: AsyncOpenAI,
        model: str,
        messages: list[dict],
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式响应"""
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            **kwargs,
        )

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def generate_questions(
        self,
        direction: str,
        resume_content: Optional[str] = None,
        count: int = 5,
    ) -> list[dict]:
        """生成面试问题"""
        prompt = build_question_generation_prompt(direction, resume_content, count)

        response = await self.chat(
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )

        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            data = json.loads(response.strip())

            if isinstance(data, dict):
                self._last_resume_analysis = {
                    "score": data.get("resumeScore"),
                    "analysis": data.get("resumeAnalysis"),
                    "strengths": data.get("resumeStrengths", []),
                    "weaknesses": data.get("resumeWeaknesses", []),
                }
                return data.get("questions", [])
            else:
                self._last_resume_analysis = None
                return data if isinstance(data, list) else []

        except json.JSONDecodeError:
            self._last_resume_analysis = None
            return self._parse_questions_from_text(response)

    def get_last_resume_score(self) -> Optional[int]:
        """获取上一次生成问题时的简历评分"""
        analysis = getattr(self, "_last_resume_analysis", None)
        return analysis.get("score") if analysis else None

    def get_last_resume_analysis(self) -> Optional[dict]:
        """获取上一次生成问题时的简历分析详情"""
        return getattr(self, "_last_resume_analysis", None)

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
    ) -> dict:
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
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            result = json.loads(response.strip())

            score = result.get("score", 60)
            if "follow_up_needed" not in result:
                result["follow_up_needed"] = score < 60

            if "follow_up_question" not in result and result.get("follow_up_needed"):
                result["follow_up_question"] = "你刚才的回答还可以继续深入，能详细说说具体的实现细节吗？"

            return result
        except json.JSONDecodeError:
            return {
                "score": 60,
                "evaluation": response,
                "suggestions": "评估生成失败",
                "follow_up_needed": False,
                "follow_up_question": None,
            }

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


# 全局 AI 客户端
ai_client = AIModelClient()
