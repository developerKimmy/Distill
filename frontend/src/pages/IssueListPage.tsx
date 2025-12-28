import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { format, parseISO, isToday, isYesterday, differenceInDays } from 'date-fns';
import { ko } from 'date-fns/locale';
import { getIssues } from '../api/issues';
import { LoadingFallback, CategoryBadge } from '../components/common';
import { useFollowMutation } from '../hooks';
import { getCategoryColors } from '../utils/constants';
import type { Issue } from '../types';

function formatRelativeDate(dateString: string): string {
  const date = parseISO(dateString);
  if (isToday(date)) return '오늘';
  if (isYesterday(date)) return '어제';
  const days = differenceInDays(new Date(), date);
  if (days < 7) return `${days}일 전`;
  return format(date, 'M월 d일 (E)', { locale: ko });
}

function IssueRow({
  issue,
  onFollowClick
}: {
  issue: Issue;
  onFollowClick: (e: React.MouseEvent, issue: Issue) => void;
}) {
  const navigate = useNavigate();
  const colors = getCategoryColors(issue.category);

  return (
    <div
      onClick={() => navigate(`/issues/${issue.id}`)}
      className="flex items-center gap-3 p-3 bg-white border border-gray-200 rounded-lg hover:border-amber-300 hover:shadow-sm transition-all cursor-pointer"
    >
      {/* 카테고리 인디케이터 */}
      <div className={`w-1 self-stretch rounded-full ${colors.bg}`} />

      {/* 콘텐츠 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <CategoryBadge category={issue.category || '기타'} size="sm" />
          {issue.hasContent && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-100 text-green-700">
              콘텐츠
            </span>
          )}
        </div>
        <h3 className="font-medium text-gray-900 truncate text-sm">{issue.name}</h3>
      </div>

      {/* 기사 수 */}
      <div className="text-xs text-gray-500 whitespace-nowrap">
        {issue.latestArticleCount || 0}개 기사
      </div>

      {/* 팔로우 버튼 */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onFollowClick(e, issue);
        }}
        className={`p-1.5 rounded-full transition-colors ${
          issue.isFollowing
            ? 'text-amber-500 hover:bg-amber-50'
            : 'text-gray-400 hover:bg-gray-100'
        }`}
      >
        <svg className="w-4 h-4" fill={issue.isFollowing ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
        </svg>
      </button>
    </div>
  );
}

export default function IssueListPage() {
  const queryKey = useMemo(() => ['issues', 1, 100], []);

  const { data, isLoading, error } = useQuery({
    queryKey,
    queryFn: () => getIssues(1, 100),
  });

  const { handleFollowClick } = useFollowMutation({ queryKey });

  // 날짜별 그룹핑
  const groupedByDate = useMemo(() => {
    if (!data?.items) return {};

    return data.items.reduce((acc, issue) => {
      const date = issue.lastSeenAt.split('T')[0];
      if (!acc[date]) acc[date] = [];
      acc[date].push(issue);
      return acc;
    }, {} as Record<string, Issue[]>);
  }, [data?.items]);

  const sortedDates = useMemo(() =>
    Object.keys(groupedByDate).sort((a, b) => b.localeCompare(a)),
    [groupedByDate]
  );

  return (
    <LoadingFallback
      isLoading={isLoading}
      error={error as Error | null}
      errorMessage="이슈를 불러올 수 없습니다."
    >
      <div className="max-w-3xl mx-auto space-y-6">
        {/* 헤더 */}
        <div className="flex items-center justify-between">
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">이슈 목록</h1>
          <p className="text-xs sm:text-sm text-gray-500">
            총 {data?.total || 0}개
          </p>
        </div>

        {/* 날짜별 이슈 목록 */}
        <div className="space-y-6">
          {sortedDates.map((date) => (
            <div key={date}>
              {/* 날짜 헤더 */}
              <div className="flex items-center gap-3 mb-3">
                <div className="text-sm font-semibold text-gray-800">
                  {formatRelativeDate(date)}
                </div>
                <div className="flex-1 h-px bg-gray-200" />
                <div className="text-xs text-gray-400">
                  {groupedByDate[date].length}개
                </div>
              </div>

              {/* 이슈 리스트 */}
              <div className="space-y-2">
                {groupedByDate[date].map((issue) => (
                  <IssueRow
                    key={issue.id}
                    issue={issue}
                    onFollowClick={handleFollowClick}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* 빈 상태 */}
        {sortedDates.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-500">등록된 이슈가 없습니다.</p>
          </div>
        )}
      </div>
    </LoadingFallback>
  );
}
