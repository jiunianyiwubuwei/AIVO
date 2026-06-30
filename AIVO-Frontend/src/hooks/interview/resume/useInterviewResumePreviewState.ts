import { useCallback, useEffect, useRef, useState } from "react";

export function useInterviewResumePreviewState() {
  const [resumeName, setResumeName] = useState<string | null>(null);
  const [resumeFileUrl, setResumeFileUrl] = useState<string | null>(null);
  const [resumeRemoteFile, setResumeRemoteFile] = useState<File | null>(null);
  const [resumeLocalFile, setResumeLocalFile] = useState<File | null>(null);
  const [resumePreviewError, setResumePreviewError] = useState<string | null>(
    null,
  );
  const [numPages, setNumPages] = useState(1);

  const previewObjectUrlRef = useRef<string | null>(null);

  const replaceRemoteResumePreview = useCallback(
    (
      nextBlob: Blob | null,
      nextUrl: string | null,
      nextName?: string | null,
    ) => {
      // React StrictMode cleanup runs this BEFORE the async hydration completes.
      // Guard against null blob (cleared by cleanup) but non-null URL mismatch.
      if (nextBlob === null && nextUrl === null) {
        const previousUrl = previewObjectUrlRef.current;
        if (previousUrl) {
          URL.revokeObjectURL(previousUrl);
          previewObjectUrlRef.current = null;
        }
        setResumeRemoteFile(null);
        setResumeFileUrl(null);
        console.debug("[ResumePreview] Cleared preview state (cleanup)");
        return;
      }

      if (!nextBlob) {
        console.debug("[ResumePreview] replaceRemoteResumePreview called with null blob, ignoring");
        return;
      }

      const previousUrl = previewObjectUrlRef.current;
      // Only revoke if creating a new URL (avoid revoking during re-renders)
      if (previousUrl && previousUrl !== nextUrl) {
        URL.revokeObjectURL(previousUrl);
      }

      const newUrl = nextUrl ?? URL.createObjectURL(nextBlob);
      previewObjectUrlRef.current = newUrl;

      const newFile = new File([nextBlob], nextName || "resume.pdf", {
        type: "application/pdf",
      });
      console.debug("[ResumePreview] Setting preview file:", newFile.name, newFile.size, "bytes");
      setResumeRemoteFile(newFile);
      setResumeFileUrl(newUrl);
    },
    [],
  );

  const clearRemoteResumePreview = useCallback(() => {
    replaceRemoteResumePreview(null, null);
  }, [replaceRemoteResumePreview]);

  const clearPreviewState = useCallback(() => {
    setResumeName(null);
    clearRemoteResumePreview();
    setResumeLocalFile(null);
    setResumeRemoteFile(null);
    setResumePreviewError(null);
    setNumPages(1);
  }, [clearRemoteResumePreview]);

  const handleResumePreviewLoadSuccess = useCallback((nextNumPages: number) => {
    setNumPages(nextNumPages);
    setResumePreviewError(null);
  }, []);

  const handleResumePreviewLoadError = useCallback((message: string) => {
    setResumePreviewError(message);
  }, []);

  useEffect(() => {
    return () => {
      const previousUrl = previewObjectUrlRef.current;
      if (previousUrl) {
        URL.revokeObjectURL(previousUrl);
      }
    };
  }, []);

  return {
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
    resumePreviewSource: resumeLocalFile || resumeRemoteFile || undefined,
    resumeOpenPreviewUrl: resumeFileUrl || null,
    replaceRemoteResumePreview,
    clearRemoteResumePreview,
    clearPreviewState,
    handleResumePreviewLoadSuccess,
    handleResumePreviewLoadError,
  };
}
