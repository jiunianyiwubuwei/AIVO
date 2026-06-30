import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
} from "react";
import { interviewService } from "@/services/interviewService";
import {
  buildResumeMetadata,
  isPdfResumeFile,
} from "@/hooks/interview/resume/interviewResumeAnalysis.shared";
import { resolveInterviewTypeLabel } from "@/hooks/interview/shared/interviewUtils";
import { useInterviewResumePreviewState } from "@/hooks/interview/resume/useInterviewResumePreviewState";
import { useInterviewUploadStage } from "@/hooks/interview/resume/useInterviewUploadStage";

type UseInterviewResumeAnalysisOptions = {
  interviewerSessionId: string | null;
  setInterviewerSessionId: (sessionId: string | null) => void;
  syncNextQuestion: (sessionId: string) => Promise<void>;
  resetInterviewFlow: () => void;
  clearInterviewError: () => void;
};

export function useInterviewResumeAnalysis({
  interviewerSessionId,
  setInterviewerSessionId,
  syncNextQuestion,
  resetInterviewFlow,
  clearInterviewError,
}: UseInterviewResumeAnalysisOptions) {
  const [resumeScore, setResumeScore] = useState<number | null>(null);
  const [resumeInterviewType, setResumeInterviewType] = useState<string | null>(
    null,
  );
  const [resumeSuggestions, setResumeSuggestions] = useState<string[]>([]);
  const [resumeUploadError, setResumeUploadError] = useState<string | null>(
    null,
  );
  const [isResumeOpen, setIsResumeOpen] = useState(false);
  const [interviewDirection, setInterviewDirection] = useState<string | null>(null);

  const {
    resumeName,
    setResumeName,
    resumeFileUrl,
    resumeRemoteFile,
    resumeLocalFile,
    setResumeLocalFile,
    resumePreviewError,
    setResumePreviewError,
    numPages,
    setNumPages,
    resumePreviewSource,
    resumeOpenPreviewUrl,
    replaceRemoteResumePreview,
    clearRemoteResumePreview,
    clearPreviewState,
    handleResumePreviewLoadSuccess,
    handleResumePreviewLoadError,
  } = useInterviewResumePreviewState();
  const {
    isResumeUploading,
    resumeUploadStage,
    startUploadStage,
    finishUploadStage,
  } = useInterviewUploadStage();

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const hydratedSessionIdRef = useRef<string | null>(null);

  const resolvedInterviewTypeLabel =
    resolveInterviewTypeLabel(resumeInterviewType);

  const resetResumeMetadata = useCallback(() => {
    setResumeScore(null);
    setResumeInterviewType(null);
    setInterviewDirection(null);
    setResumeSuggestions([]);
    setResumeUploadError(null);
  }, []);

  const applyResumeMetadata = useCallback(
    (metadata: {
      resumeName?: string | null;
      resumeScore: number | null;
      resumeInterviewType: string | null;
      interviewDirection: string | null;
      resumeSuggestions: string[];
    }) => {
      setResumeName(metadata.resumeName ?? null);
      setResumeScore(metadata.resumeScore);
      setResumeInterviewType(metadata.resumeInterviewType);
      setInterviewDirection(metadata.interviewDirection);
      setResumeSuggestions(metadata.resumeSuggestions);
    },
    [setResumeName],
  );

  useEffect(() => {
    if (!interviewerSessionId) {
      hydratedSessionIdRef.current = null;
      return;
    }

    if (hydratedSessionIdRef.current === interviewerSessionId) {
      return;
    }

    clearPreviewState();
    resetResumeMetadata();
  }, [clearPreviewState, interviewerSessionId, resetResumeMetadata]);

  useEffect(() => {
    if (!interviewerSessionId || isResumeUploading) {
      return;
    }
    if (hydratedSessionIdRef.current === interviewerSessionId) {
      return;
    }

    let cancelled = false;

    const hydrateResumeState = async () => {
      console.log("[ResumeAnalysis] Starting hydrateResumeState for session:", interviewerSessionId);
      try {
        const restored =
          await interviewService.restoreInterviewSession(interviewerSessionId);
        console.log("[ResumeAnalysis] /restore response:", {
          resumeFilename: restored.resumeFilename,
          resumeFileUrl: restored.resumeFileUrl,
          resumeScore: restored.resumeScore,
        });
        if (cancelled) {
          return;
        }

        applyResumeMetadata(
          buildResumeMetadata({
            resumeScore: restored.resumeScore,
            interviewType: restored.interviewType,
            interviewDirection: restored.interviewDirection,
            suggestions: restored.suggestions,
            resumeFileUrl: restored.resumeFileUrl,
            resumeFilename: restored.resumeFilename,
          }),
        );
        setResumePreviewError(null);

        try {
          console.log("[ResumeAnalysis] Fetching preview blob for session:", interviewerSessionId);
          const previewBlob =
            await interviewService.fetchInterviewResumePreviewBlob(
              interviewerSessionId,
            );
          console.log("[ResumeAnalysis] Preview blob received:", previewBlob.size, "bytes", previewBlob.type);
          if (cancelled) {
            return;
          }

          replaceRemoteResumePreview(
            previewBlob,
            URL.createObjectURL(previewBlob),
            restored.resumeFilename || "resume.pdf",
          );
        } catch (error) {
          if (cancelled) {
            return;
          }
          clearRemoteResumePreview();
          const message =
            error instanceof Error
              ? error.message
              : "Failed to load resume preview";
          setResumePreviewError(message);
          console.error("[ResumeAnalysis] Failed to load resume preview:", error);
        }

        hydratedSessionIdRef.current = interviewerSessionId;
      } catch (error) {
        if (cancelled) {
          return;
        }
        console.error("[ResumeAnalysis] Failed to restore interview session:", error);
      }
    };

    void hydrateResumeState();

    return () => {
      cancelled = true;
    };
  }, [
    clearRemoteResumePreview,
    interviewerSessionId,
    isResumeUploading,
    replaceRemoteResumePreview,
    applyResumeMetadata,
    setResumePreviewError,
  ]);

  const handleResumeFileSelect = async (
    event: ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    if (!isPdfResumeFile(file)) {
      setResumeUploadError("Only PDF files are supported");
      return;
    }

    setResumeUploadError(null);
    setResumePreviewError(null);
    clearInterviewError();
    resetInterviewFlow();

    resetResumeMetadata();
    setResumeName(file.name);
    setResumeLocalFile(file);
    clearRemoteResumePreview();
    setNumPages(1);
    setIsResumeOpen(false);
    hydratedSessionIdRef.current = null;
    startUploadStage();

    try {
      console.log("[ResumeAnalysis] Creating new session...");
      const createdSession = await interviewService.createInterviewSession();
      const sessionId = createdSession.sessionId;
      console.log("[ResumeAnalysis] Session created:", sessionId);

      console.log("[ResumeAnalysis] Uploading resume:", file.name, file.size, "bytes");
      const analyzed = await interviewService.extractInterviewQuestions({
        sessionId,
        resumePdf: file,
      });
      console.log("[ResumeAnalysis] Upload response:", {
        isSuccess: analyzed.isSuccess,
        resumeFilename: analyzed.resumeFilename,
        resumeFileUrl: analyzed.resumeFileUrl,
        resumeScore: analyzed.resumeScore,
      });

      if (analyzed.isSuccess === 0) {
        throw new Error(
          analyzed.errorMessage || "Failed to analyze resume, please retry",
        );
      }

      applyResumeMetadata(
        buildResumeMetadata({
          resumeScore: analyzed.resumeScore,
          interviewType: analyzed.interviewType,
          interviewDirection: (analyzed as Record<string, unknown>).interviewDirection as string | null ?? null,
          suggestions: analyzed.suggestions ?? null,
          resumeFileUrl: analyzed.resumeFileUrl,
          resumeFilename: analyzed.resumeFilename,
        }),
      );
      console.log("[ResumeAnalysis] Setting interviewerSessionId to:", sessionId);
      setInterviewerSessionId(sessionId);
      hydratedSessionIdRef.current = sessionId;
      setResumePreviewError(null);

      try {
        console.log("[ResumeAnalysis] Fetching preview blob...");
        const previewBlob =
          await interviewService.fetchInterviewResumePreviewBlob(sessionId);
        console.log("[ResumeAnalysis] Preview blob fetched:", previewBlob.size, "bytes");
        replaceRemoteResumePreview(
          previewBlob,
          URL.createObjectURL(previewBlob),
          analyzed.resumeFilename || file.name,
        );
        console.log("[ResumeAnalysis] Preview set successfully");
      } catch (error) {
        console.error(
          "[ResumeAnalysis] Failed to fetch proxied resume preview after upload:",
          error,
        );
      }

      await syncNextQuestion(sessionId);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Failed to upload resume, please retry";
      console.error("[ResumeAnalysis] Upload failed:", message);
      setResumeUploadError(message);
      clearRemoteResumePreview();
      setInterviewerSessionId(null);
    } finally {
      finishUploadStage();
    }
  };

  return {
    fileInputRef,
    resumeName,
    resumeFileUrl,
    resumeRemoteFile,
    resumeLocalFile,
    resumeScore,
    resumeInterviewType,
    interviewDirection,
    resumeSuggestions,
    resumePreviewError,
    resumeUploadError,
    isResumeUploading,
    resumeUploadStage,
    numPages,
    isResumeOpen,
    setIsResumeOpen,
    resumePreviewSource,
    resumeOpenPreviewUrl,
    resolvedInterviewTypeLabel,
    handleResumePreviewLoadSuccess,
    handleResumePreviewLoadError,
    handleResumeFileSelect,
  };
}
