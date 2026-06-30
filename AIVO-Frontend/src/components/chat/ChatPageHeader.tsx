import { APP_BRAND_NAME } from "@/lib/branding";
import { Plus, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ROUTES } from "@/lib/constants";
import { useNavigate } from "react-router-dom";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { resetChatRuntime, setChatRuntimeSession } from "@/store/slices/chatSlice";
import { aiService } from "@/services/aiService";
import { useState } from "react";

type ChatPageHeaderProps = {
  selectedModelName?: string;
};

export default function ChatPageHeader({
  selectedModelName,
}: ChatPageHeaderProps) {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const [isCreating, setIsCreating] = useState(false);
  const currentUser = useAppSelector((state) => state.user.currentUser);

  const handleNewChat = async () => {
    if (isCreating) return;

    setIsCreating(true);
    try {
      // Create a new conversation on the backend
      const response = await aiService.createConversation({
        userName: currentUser?.username || "Guest",
        firstMessage: "",
      });

      const newSessionId = response?.sessionId;
      if (newSessionId) {
        // Reset chat state and set new session
        dispatch(resetChatRuntime());
        dispatch(setChatRuntimeSession({
          sessionId: newSessionId,
          title: response.conversationTitle || "新对话",
        }));
        // Navigate to the new session
        navigate(`${ROUTES.chat}/${newSessionId}`, { replace: true });
      } else {
        // Fallback: just reset and go to chat root
        dispatch(resetChatRuntime());
        navigate(ROUTES.chat, { replace: true });
      }
    } catch (error) {
      console.error("Failed to create new conversation:", error);
      // Fallback: just reset and go to chat root
      dispatch(resetChatRuntime());
      navigate(ROUTES.chat, { replace: true });
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="sticky top-0 z-10 flex items-center justify-between border-b bg-white/50 px-6 py-4 backdrop-blur-sm">
      <div className="flex items-center gap-2">
        <img
          src="/aivo-mark.svg"
          alt={APP_BRAND_NAME}
          className="h-8 w-8 rounded-full border border-slate-200 object-cover"
        />
        <h2 className="font-semibold">{APP_BRAND_NAME}</h2>
        {selectedModelName ? (
          <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-600">
            {selectedModelName}
          </span>
        ) : null}
      </div>
      <Button
        variant="outline"
        size="sm"
        className="gap-1.5"
        onClick={handleNewChat}
        disabled={isCreating}
      >
        {isCreating ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Plus className="h-4 w-4" />
        )}
        新对话
      </Button>
    </div>
  );
}
