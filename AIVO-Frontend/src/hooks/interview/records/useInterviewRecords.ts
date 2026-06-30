import { useInfiniteQuery } from "@tanstack/react-query";
import { interviewService } from "@/services/interviewService";
import { useAppSelector } from "@/store/hooks";
import type { UserRespDTO } from "@/types/auth";

type UnknownRecord = Record<string, unknown>;

type InterviewRecordUserIdentity =
  | Pick<UserRespDTO, "id" | "username">
  | null
  | undefined;

type UseInterviewRecordsOptions = {
  enabled?: boolean;
};

const PAGE_SIZE = 20;

const getInterviewRecordUserKey = (user: InterviewRecordUserIdentity) => {
  if (!user) return "anonymous";
  if (typeof user.id === "number" && Number.isFinite(user.id) && user.id > 0) {
    return `id:${user.id}`;
  }
  if (user.username) return `username:${user.username}`;
  return "anonymous";
};

export function useInterviewRecords(options: UseInterviewRecordsOptions = {}) {
  const { isAuthenticated, currentUser, authEpoch } = useAppSelector(
    (state) => state.user,
  );
  const enabled = (options.enabled ?? true) && isAuthenticated;
  const userKey = getInterviewRecordUserKey(currentUser);

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    status,
    refetch,
  } = useInfiniteQuery({
    queryKey: ["interview-records", userKey, authEpoch],
    queryFn: async ({ pageParam = 1 }) => {
      const result = await interviewService.pageInterviewRecords({
        pageNum: pageParam,
        pageSize: PAGE_SIZE,
      });
      // 兼容后端返回的 pageNum 字段
      if (result && !result.current && "pageNum" in result) {
        Object.defineProperty(result, "current", {
          value: (result as unknown as UnknownRecord).pageNum,
          writable: true,
          configurable: true,
        });
      }
      return result;
    },
    getNextPageParam: (lastPage) => {
      if (!lastPage) return undefined;
      if (!Array.isArray(lastPage.records)) return undefined;
      if (lastPage.records.length < PAGE_SIZE) return undefined;
      const currentPage = Number(lastPage.current) || 1;
      const totalPages = Number(lastPage.pages) || 1;
      if (currentPage >= totalPages) return undefined;
      return currentPage + 1;
    },
    initialPageParam: 1,
    enabled,
  });

  return {
    interviewRecords: data?.pages.flatMap((page) => page.records ?? []) ?? [],
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    status,
    refetch,
  };
}
