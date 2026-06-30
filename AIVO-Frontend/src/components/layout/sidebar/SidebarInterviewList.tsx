"use client";

import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/button";
import { Trash2 } from "lucide-react";
import type { InterviewRecordResult } from "@/services/interviewService";
import { ROUTES } from "@/lib/constants";
import { interviewService } from "@/services/interviewService";
import { useQueryClient } from "@tanstack/react-query";
import { useAppSelector } from "@/store/hooks";

type SidebarInterviewListProps = {
  records: InterviewRecordResult[];
  activePathname: string;
  activeSessionId: string | null;
  hasNextPage: boolean | undefined;
  isFetchingNextPage: boolean;
  onOpenRecord: (sessionId: string) => void;
};

const formatDate = (value?: string | null) => {
  if (!value) return "Unknown date";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString();
};

const formatScore = (value?: number | null) => {
  if (typeof value !== "number" || Number.isNaN(value)) return "--";
  return String(value);
};

const getScoreColor = (score?: number | null) => {
  if (typeof score !== "number" || Number.isNaN(score)) return "text-slate-400";
  if (score >= 80) return "text-emerald-600";
  if (score >= 60) return "text-amber-600";
  return "text-red-500";
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

export default function SidebarInterviewList({
  records,
  activePathname,
  activeSessionId,
  hasNextPage,
  isFetchingNextPage,
  onOpenRecord,
}: SidebarInterviewListProps) {
  const queryClient = useQueryClient();
  const { currentUser, authEpoch } = useAppSelector((state) => state.user);

  const [deleteConfirm, setDeleteConfirm] = useState<{ open: boolean; sessionId: string | null }>({
    open: false,
    sessionId: null,
  });

  const handleDelete = async (sessionId: string) => {
    try {
      await interviewService.deleteInterviewRecord(sessionId);
    } catch (error: unknown) {
      // 即使删除失败（记录可能已不存在），仍然刷新列表
      console.warn("Delete interview record warning:", error);
    }
    // 清除缓存，强制重新获取
    queryClient.removeQueries({
      queryKey: ["interview-records", `id:${currentUser?.id}`, authEpoch],
    });
    setDeleteConfirm({ open: false, sessionId: null });
  };

  return (
    <>
      {records.map((record) => {
        const isActive =
          activePathname.startsWith(ROUTES.interviewReport) &&
          activeSessionId === record.sessionId;

        // 优先显示综合评分，其次是回答得分，最后是原始总分
        const rawScore = record.compositeScore ?? record.interviewScore ?? record.totalScore;
        // 处理 0 分的情况（优先检查综合评分，再检查回答得分）
        const score = (rawScore === 0 && record.compositeScore === 0 && record.interviewScore === 0)
          ? 0
          : (rawScore ?? null);
        const scoreColor = getScoreColor(score);

        return (
          <div key={record.sessionId} className="group relative mb-1">
            <Button
              variant={isActive ? "secondary" : "ghost"}
              className="mb-1 h-auto w-full justify-start rounded-xl px-3 py-2 text-left font-normal hover:bg-slate-100 pr-10"
              onClick={() => onOpenRecord(record.sessionId)}
            >
              <div className="flex w-full flex-col gap-0.5 overflow-hidden">
                <span className="truncate text-sm font-medium text-slate-700">
                  {record.interviewDirection || "面试记录"}
                </span>
                <span className="flex items-center gap-2 truncate text-[10px] text-slate-400">
                  <span>{formatDate(record.startTime || record.createTime)}</span>
                  <span className="text-slate-300">·</span>
                  <span className={scoreColor}>得分 {formatScore(score)}</span>
                </span>
              </div>
            </Button>

            <Button
              variant="ghost"
              size="sm"
              className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0 opacity-0 group-hover:opacity-100 hover:bg-red-100 hover:text-red-600 transition-opacity"
              onClick={(e) => {
                e.stopPropagation();
                setDeleteConfirm({ open: true, sessionId: record.sessionId });
              }}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        );
      })}

      {isFetchingNextPage ? (
        <div className="py-2 text-center text-xs text-slate-400">加载中...</div>
      ) : null}

      {!hasNextPage && records.length > 0 ? (
        <div className="py-2 text-center text-xs text-slate-300">没有更多了</div>
      ) : null}

      {!isFetchingNextPage && records.length === 0 ? (
        <div className="py-4 text-center text-xs text-slate-400">暂无面试记录</div>
      ) : null}

      <ConfirmDialog
        isOpen={deleteConfirm.open}
        title="确认删除"
        description="确定要删除这个面试记录吗？删除后无法恢复。"
        confirmText="删除"
        confirmClassName="bg-red-600 hover:bg-red-700"
        onConfirm={() => deleteConfirm.sessionId && handleDelete(deleteConfirm.sessionId)}
        onCancel={() => setDeleteConfirm({ open: false, sessionId: null })}
      />
    </>
  );
}
