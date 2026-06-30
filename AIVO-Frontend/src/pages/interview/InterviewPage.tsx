import { startTransition, useCallback, useEffect, useRef, useState } from "react";
import type { CameraPreviewHandle } from "@/components/camera/CameraPreview";
import ChatRoom from "@/components/chat/ChatRoom";
import SmartComposer from "@/components/chat/SmartComposer";
import InterviewCameraOverlay from "@/components/interview/InterviewCameraOverlay";
import InterviewHeader from "@/components/interview/InterviewHeader";
import InterviewResumePreviewDialog from "@/components/interview/InterviewResumePreviewDialog";
import InterviewResumeReferenceCard from "@/components/interview/InterviewResumeReferenceCard";
import InterviewResumeUploadCard from "@/components/interview/InterviewResumeUploadCard";
import InterviewSketchpadSheet from "@/components/interview/sketchpad/InterviewSketchpadSheet";
import { useInterviewDemeanorPolling } from "@/hooks/interview/camera/useInterviewDemeanorPolling";
import { useInterviewPageController } from "@/hooks/interview/useInterviewPageController";
import { Video } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function InterviewPage() {
  const cameraPreviewRef = useRef<CameraPreviewHandle | null>(null);
  const [isSketchpadOpen, setIsSketchpadOpen] = useState(false);
  const [showCameraReminder, setShowCameraReminder] = useState(false);
  const { chat, interview, resume, camera } = useInterviewPageController();
  const { setInput, isReady, isSubmitting, handleSend, input, messages } = chat;
  const { setIsPreviewOpen } = resume;

  // 简历上传成功后显示摄像头提醒
  useEffect(() => {
    if (resume.fileUrl && !camera.isOpen) {
      // 延迟显示提醒，等简历分析结果出来
      const timer = setTimeout(() => {
        setShowCameraReminder(true);
      }, 1500);
      return () => clearTimeout(timer);
    } else {
      setShowCameraReminder(false);
    }
  }, [resume.fileUrl, camera.isOpen]);

  // 用户开启摄像头后隐藏提醒
  useEffect(() => {
    if (camera.isOpen) {
      setShowCameraReminder(false);
    }
  }, [camera.isOpen]);

  const captureFrame = useCallback(async () => {
    return cameraPreviewRef.current?.captureFrame() ?? null;
  }, []);

  const handleInsertNotes = useCallback(
    (notes: string) => {
      if (!notes.trim()) return;
      setInput((prev) => (prev.trim() ? `${prev.trim()}\n\n${notes}` : notes));
      setIsSketchpadOpen(false);
    },
    [setInput],
  );

  const handleOpenSketchpad = useCallback(() => {
    startTransition(() => {
      setIsSketchpadOpen(true);
    });
  }, []);

  const handleOpenResume = useCallback(() => {
    startTransition(() => {
      setIsPreviewOpen(true);
    });
  }, [setIsPreviewOpen]);

  useInterviewDemeanorPolling({
    sessionId: interview.sessionId,
    enabled:
      Boolean(interview.sessionId) &&
      isReady &&
      camera.isOpen &&
      !interview.isFinished &&
      !interview.isEnding,
    captureFrame,
  });

  return (
    <>
      <ChatRoom
        header={
          <InterviewHeader
            isReady={isReady}
            interviewDirection={resume.interviewDirection}
            currentQuestionNumber={interview.currentQuestionNumber}
            isCurrentQuestionFollowUp={interview.isCurrentQuestionFollowUp}
            currentFollowUpCount={interview.currentFollowUpCount}
            isInterviewFinished={interview.isFinished}
            totalInterviewScore={interview.totalScore}
            isCameraOpen={camera.isOpen}
            isEndingInterview={interview.isEnding}
            onToggleCamera={camera.handleToggleCamera}
            onOpenSketchpad={handleOpenSketchpad}
            onEndInterview={interview.handleEndInterview}
          />
        }
        topContent={
          <div className="space-y-4">
            {/* 摄像头开启提醒 */}
            {showCameraReminder && (
              <div className="flex items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
                <div className="flex items-center gap-2">
                  <Video className="h-4 w-4 text-amber-600" />
                  <p className="text-sm text-amber-800">
                    建议开启摄像头以进行仪态评估，这将帮助您获得更完整的面试反馈
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="shrink-0 border-amber-300 text-amber-700 hover:bg-amber-100"
                  onClick={camera.handleToggleCamera}
                >
                  开启摄像头
                </Button>
              </div>
            )}
            <InterviewResumeUploadCard
              fileInputRef={resume.fileInputRef}
              isResumeUploading={resume.isUploading}
              showUploadButton={!isReady}
              resumeUploadStage={resume.uploadStage}
              resumeLocalFile={resume.localFile}
              resumeFileUrl={resume.fileUrl}
              resumeName={resume.name}
              resumePreviewError={resume.previewError}
              resumeUploadError={resume.uploadError}
              interviewError={interview.error}
              onResumeFileSelect={resume.handleFileSelect}
              onOpenResume={handleOpenResume}
            />
            <InterviewResumePreviewDialog
              open={resume.isPreviewOpen}
              onOpenChange={resume.setIsPreviewOpen}
              resumePreviewSource={resume.previewSource}
              resumePreviewError={resume.previewError}
              resumeOpenPreviewUrl={resume.previewUrl}
              numPages={resume.numPages}
              resumeScore={resume.score}
              resolvedInterviewTypeLabel={resume.interviewTypeLabel}
              resumeSuggestions={resume.suggestions}
              onLoadSuccess={resume.handlePreviewLoadSuccess}
              onLoadError={resume.handlePreviewLoadError}
            />
          </div>
        }
        messages={messages}
        inputValue={input}
        onInputChange={setInput}
        onSend={handleSend}
        customComposer={
          <SmartComposer
            value={input}
            onChange={setInput}
            onSend={handleSend}
            placeholder="输入你的回答..."
            disabled={!isReady || isSubmitting || resume.isUploading}
            showVoiceButton={true}
          />
        }
        contentOverlay={
          <InterviewCameraOverlay
            ref={cameraPreviewRef}
            isCameraOpen={camera.isOpen}
            isCameraExpanded={camera.isExpanded}
            cameraErrorCopy={camera.errorCopy}
            onCameraError={camera.handleCameraError}
            onToggleExpanded={camera.handleToggleExpanded}
          />
        }
        footer={
          <div className="mt-2 space-y-2">
            <p className="text-center text-xs text-slate-400">
              AI 生成内容可能存在误差，请以实际情况为准。
            </p>
          </div>
        }
      />

      <InterviewSketchpadSheet
        open={isSketchpadOpen}
        onOpenChange={setIsSketchpadOpen}
        sessionId={interview.sessionId}
        currentQuestionNumber={interview.currentQuestionNumber}
        currentQuestionContent={interview.currentQuestionContent}
        onInsertNotes={handleInsertNotes}
      />
      <InterviewResumeReferenceCard
        key={[
          interview.sessionId ?? "no-session",
          resume.name ?? "no-resume",
          resume.previewUrl ?? "no-preview-url",
        ].join(":")}
        open={isSketchpadOpen}
        resumeName={resume.name}
        resumePreviewSource={resume.previewSource}
        resumePreviewError={resume.previewError}
        resumeOpenPreviewUrl={resume.previewUrl}
        numPages={resume.numPages}
        onLoadSuccess={resume.handlePreviewLoadSuccess}
        onLoadError={resume.handlePreviewLoadError}
      />
    </>
  );
}
