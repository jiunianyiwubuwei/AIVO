/**
 * TTS 播放 Hook - 管理面试对话中的语音播放
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { browserTtsService } from "@/services/browserTtsService";
import type { ChatMessage } from "@/lib/chat";

type TtsState = "idle" | "playing" | "loading" | "error";

export function useChatTtsPlayback(_messages: ChatMessage[]) {
  const [state, setState] = useState<TtsState>("idle");
  const [currentMessageId, setCurrentMessageId] = useState<string | null>(null);
  const errorRef = useRef<string | null>(null);
  const currentTextRef = useRef<string | null>(null);

  // 检查 TTS 是否可用
  const isAvailable = browserTtsService.isAvailable();

  // 播放文本
  const play = useCallback(async (text: string, messageId: string) => {
    if (!isAvailable) {
      errorRef.current = "浏览器不支持语音播放";
      setState("error");
      return;
    }

    try {
      setState("loading");
      setCurrentMessageId(messageId);
      currentTextRef.current = text;

      await browserTtsService.speak({
        text,
        lang: "zh-CN",
        rate: 0.9, // 稍慢一点，便于听清
        pitch: 1,
        volume: 1,
      });

      setState("idle");
      setCurrentMessageId(null);
      currentTextRef.current = null;
    } catch (error) {
      setState("error");
      errorRef.current = error instanceof Error ? error.message : "播放失败";
      setCurrentMessageId(null);
      currentTextRef.current = null;
    }
  }, [isAvailable]);

  // 停止播放
  const stop = useCallback(() => {
    browserTtsService.cancel();
    setState("idle");
    setCurrentMessageId(null);
    currentTextRef.current = null;
  }, []);

  // 切换消息播放
  const toggleMessagePlayback = useCallback((message: ChatMessage) => {
    // 如果当前正在播放这个消息，则停止
    if (currentMessageId === message.id && state === "playing") {
      stop();
      return;
    }

    // 停止当前播放，开始播放新消息
    stop();
    if (message.content) {
      play(message.content, message.id);
    }
  }, [currentMessageId, state, stop, play]);

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      browserTtsService.cancel();
    };
  }, []);

  return {
    isAvailable,
    state,
    currentMessageId,
    error: errorRef.current,
    play,
    stop,
    toggleMessagePlayback,
  };
}
