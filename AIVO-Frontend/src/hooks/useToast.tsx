import { useCallback, useMemo, useState } from "react";

interface Toast {
  id: number;
  message: string;
  type: "success" | "error" | "info";
}

let toastId = 0;

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, type: Toast["type"] = "info") => {
    const id = ++toastId;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3000);
  }, []);

  const toast = useMemo(
    () => ({
      success: (message: string) => showToast(message, "success"),
      error: (message: string) => showToast(message, "error"),
      info: (message: string) => showToast(message, "info"),
    }),
    [showToast],
  );

  const ToastContainer = useCallback(() => (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`animate-in slide-in-from-right fade-in rounded-lg px-4 py-3 text-sm font-medium shadow-lg ${
            t.type === "success"
              ? "bg-green-500 text-white"
              : t.type === "error"
                ? "bg-red-500 text-white"
                : "bg-slate-800 text-white"
          }`}
        >
          {t.message}
        </div>
      ))}
    </div>
  ), [toasts]);

  return { toast, ToastContainer };
}
