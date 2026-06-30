"use client";

import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/button";
import { Trash2 } from "lucide-react";
import type { AiConversation } from "@/types/ai";
import { aiService } from "@/services/aiService";
import { useQueryClient } from "@tanstack/react-query";
import { useAppSelector } from "@/store/hooks";
import { getConversationUserKey, getConversationsQueryKey } from "@/hooks/useConversations";

type SidebarSessionListProps = {
  conversations: AiConversation[];
  activePathname: string;
  hasNextPage: boolean | undefined;
  isFetchingNextPage: boolean;
  onOpenSession: (sessionId: string) => void;
};

// 简单的确认对话框组件
function ConfirmDialog({
  isOpen,
  title,
  description,
  confirmText = "确认",
  cancelText = "取消",
  confirmClassName,
  onConfirm,
  onCancel,
}: {
  isOpen: boolean;
  title: string;
  description: string;
  confirmText?: string;
  cancelText?: string;
  confirmClassName?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (isOpen) {
      dialog.showModal();
    } else {
      dialog.close();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return createPortal(
    <dialog
      ref={dialogRef}
      className="fixed inset-0 z-50 m-auto max-w-sm rounded-xl border border-slate-200 bg-white p-0 shadow-xl backdrop:bg-black/50"
      onClick={(e) => {
        if (e.target === dialogRef.current) onCancel();
      }}
    >
      <div className="p-6">
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        <p className="mt-2 text-sm text-slate-500">{description}</p>
      </div>
      <div className="flex items-center justify-end gap-2 border-t border-slate-100 p-4">
        <Button variant="outline" onClick={onCancel}>
          {cancelText}
        </Button>
        <Button className={confirmClassName} onClick={onConfirm}>
          {confirmText}
        </Button>
      </div>
    </dialog>,
    document.body
  );
}

export default function SidebarSessionList({
  conversations,
  activePathname,
  hasNextPage,
  isFetchingNextPage,
  onOpenSession,
}: SidebarSessionListProps) {
  const queryClient = useQueryClient();
  const { currentUser, authEpoch } = useAppSelector((state) => state.user);

  const [deleteConfirm, setDeleteConfirm] = useState<{ open: boolean; sessionId: string | null }>({
    open: false,
    sessionId: null,
  });

  const handleDelete = async (sessionId: string) => {
    try {
      await aiService.deleteConversation(sessionId);
      queryClient.removeQueries({
        queryKey: getConversationsQueryKey(getConversationUserKey(currentUser), authEpoch),
      });
    } catch (error) {
      console.error("Delete conversation failed:", error);
    }
    setDeleteConfirm({ open: false, sessionId: null });
  };

  return (
    <>
      {conversations.map((conversation) => {
        if (!conversation?.sessionId) return null;
        return (
          <div key={conversation.sessionId} className="group relative mb-1">
            <Button
              variant={activePathname.includes(conversation.sessionId) ? "secondary" : "ghost"}
              className="w-full justify-start text-left h-auto py-2 px-3 font-normal rounded-xl hover:bg-slate-100 pr-10"
              onClick={() => onOpenSession(conversation.sessionId)}
            >
              <div className="flex flex-col gap-0.5 overflow-hidden w-full">
                <span className="truncate text-sm text-slate-700 font-medium">
                  {conversation.title || "无标题会话"}
                </span>
                <span className="text-[10px] text-slate-400 truncate">
                  {conversation.createTime
                    ? new Date(conversation.createTime).toLocaleDateString()
                    : "Unknown date"}
                  · {conversation.aiName || "Unknown model"}
                  {conversation.messageCount ? ` · ${conversation.messageCount} 条消息` : ""}
                </span>
              </div>
            </Button>

            <Button
              variant="ghost"
              size="sm"
              className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0 opacity-0 group-hover:opacity-100 hover:bg-red-100 hover:text-red-600 transition-opacity"
              onClick={(e) => {
                e.stopPropagation();
                setDeleteConfirm({ open: true, sessionId: conversation.sessionId });
              }}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        );
      })}

      {isFetchingNextPage ? (
        <div className="text-center py-2 text-xs text-slate-400">加载中...</div>
      ) : null}

      {!hasNextPage && conversations.length > 0 ? (
        <div className="text-center py-2 text-xs text-slate-300">没有更多了</div>
      ) : null}

      {!isFetchingNextPage && conversations.length === 0 ? (
        <div className="text-center py-4 text-xs text-slate-400">暂无会话记录</div>
      ) : null}

      <ConfirmDialog
        isOpen={deleteConfirm.open}
        title="确认删除"
        description="确定要删除这个会话吗？删除后无法恢复。"
        confirmText="删除"
        confirmClassName="bg-red-600 hover:bg-red-700"
        onConfirm={() => deleteConfirm.sessionId && handleDelete(deleteConfirm.sessionId)}
        onCancel={() => setDeleteConfirm({ open: false, sessionId: null })}
      />
    </>
  );
}
