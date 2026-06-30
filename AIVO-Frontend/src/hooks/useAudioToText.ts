/**
 * 空实现的 AudioToText hook - ASR 功能已移除
 */
import { useCallback, useState } from "react";

export function useAudioToText() {
  const [isRecording, setIsRecording] = useState(false);
  const transcription = "";
  const error = null;

  const startRecording = useCallback(async () => {
    setIsRecording(true);
  }, []);

  const stopRecording = useCallback(() => {
    setIsRecording(false);
  }, []);

  return {
    isRecording,
    transcription,
    error,
    startRecording,
    stopRecording,
  };
}

export function useAudioToTextComposerBridge(_options: {
  enabled: boolean;
  isRecording: boolean;
  transcription: string;
  value: string;
  onChange: (value: string) => void;
}) {
  // 空实现
}
