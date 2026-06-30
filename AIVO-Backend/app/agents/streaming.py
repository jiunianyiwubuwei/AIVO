"""流式响应处理器 - 支持 SSE 格式和错误处理"""

import json
import asyncio
from typing import AsyncIterator, Optional, Callable
from dataclasses import dataclass
from enum import Enum


class StreamEventType(str, Enum):
    """SSE 事件类型"""
    CONTENT = "content"
    THINKING = "thinking"
    PROGRESS = "progress"
    ERROR = "error"
    DONE = "done"
    PING = "ping"


@dataclass
class StreamEvent:
    """流式事件"""
    type: StreamEventType
    data: dict

    def to_sse(self) -> str:
        """转换为 SSE 格式"""
        return f"data: {json.dumps(self.data, ensure_ascii=False)}\n\n"

    @classmethod
    def content(cls, content: str, delta: bool = True) -> "StreamEvent":
        """内容事件"""
        return cls(
            type=StreamEventType.CONTENT,
            data={"type": "content", "content": content, "delta": delta}
        )

    @classmethod
    def thinking(cls, thinking: str) -> "StreamEvent":
        """思考中事件"""
        return cls(
            type=StreamEventType.THINKING,
            data={"type": "thinking", "thinking": thinking}
        )

    @classmethod
    def progress(cls, current: int, total: int, message: str = "") -> "StreamEvent":
        """进度事件"""
        return cls(
            type=StreamEventType.PROGRESS,
            data={
                "type": "progress",
                "current": current,
                "total": total,
                "message": message,
                "percent": int(current / total * 100) if total > 0 else 0
            }
        )

    @classmethod
    def error(cls, error: str, code: str = "UNKNOWN") -> "StreamEvent":
        """错误事件"""
        return cls(
            type=StreamEventType.ERROR,
            data={"type": "error", "error": error, "code": code}
        )

    @classmethod
    def done(cls, session_id: str = "", metadata: dict = None) -> "StreamEvent":
        """完成事件"""
        return cls(
            type=StreamEventType.DONE,
            data={
                "type": "done",
                "session_id": session_id,
                "metadata": metadata or {}
            }
        )

    @classmethod
    def ping(cls) -> "StreamEvent":
        """心跳事件"""
        return cls(
            type=StreamEventType.PING,
            data={"type": "ping"}
        )


class StreamingHandler:
    """流式响应处理器"""

    def __init__(
        self,
        session_id: str = "",
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        ping_interval: float = 30.0,
    ):
        self.session_id = session_id
        self.on_complete = on_complete
        self.on_error = on_error
        self.ping_interval = ping_interval
        self._full_response = ""
        self._cancelled = False

    @property
    def full_response(self) -> str:
        """获取完整响应"""
        return self._full_response

    @property
    def is_cancelled(self) -> bool:
        """检查是否已取消"""
        return self._cancelled

    def cancel(self):
        """取消流式响应"""
        self._cancelled = True

    def reset(self):
        """重置状态"""
        self._full_response = ""
        self._cancelled = False

    async def process_stream(
        self,
        stream: AsyncIterator[str],
        progress_callback: Optional[Callable] = None,
    ) -> str:
        """
        处理流式响应

        Args:
            stream: 流式数据源
            progress_callback: 进度回调

        Returns:
            完整响应文本
        """
        self.reset()
        buffer = ""

        try:
            async for chunk in stream:
                if self._cancelled:
                    break

                buffer += chunk
                self._full_response += chunk

                # 回调进度
                if progress_callback:
                    await progress_callback(chunk, len(self._full_response))

            return self._full_response

        except Exception as e:
            if self.on_error:
                await self.on_error(e)
            raise

        finally:
            if self.on_complete:
                await self.on_complete(self._full_response)

    async def event_generator(
        self,
        content_stream: AsyncIterator[str],
        include_ping: bool = True,
    ) -> AsyncIterator[str]:
        """
        生成 SSE 事件流

        Args:
            content_stream: 内容流
            include_ping: 是否包含心跳

        Yields:
            SSE 格式的事件
        """
        last_ping_time = asyncio.get_event_loop().time()
        buffer = ""

        try:
            async for chunk in content_stream:
                if self._cancelled:
                    # 发送取消事件
                    yield StreamEvent.error("Stream cancelled", "CANCELLED").to_sse()
                    break

                buffer += chunk
                self._full_response += chunk

                # 发送内容事件
                yield StreamEvent.content(chunk).to_sse()

                # 检查是否需要发送心跳
                if include_ping:
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_ping_time >= self.ping_interval:
                        yield StreamEvent.ping().to_sse()
                        last_ping_time = current_time

        except Exception as e:
            yield StreamEvent.error(str(e), "STREAM_ERROR").to_sse()

        finally:
            # 发送完成事件
            yield StreamEvent.done(
                session_id=self.session_id,
                metadata={"response_length": len(self._full_response)}
            ).to_sse()


def create_error_response(error: Exception) -> str:
    """创建错误响应"""
    event = StreamEvent.error(
        error=str(error),
        code=getattr(error, "code", "UNKNOWN") if hasattr(error, "code") else "UNKNOWN"
    )
    return event.to_sse()


def create_progress_response(current: int, total: int, message: str = "") -> str:
    """创建进度响应"""
    event = StreamEvent.progress(current, total, message)
    return event.to_sse()


def create_content_response(content: str) -> str:
    """创建内容响应"""
    event = StreamEvent.content(content)
    return event.to_sse()


def create_done_response(session_id: str = "", metadata: dict = None) -> str:
    """创建完成响应"""
    event = StreamEvent.done(session_id, metadata)
    return event.to_sse()
