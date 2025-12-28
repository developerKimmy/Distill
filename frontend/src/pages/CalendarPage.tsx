import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { format, parseISO, isToday, isYesterday, differenceInDays } from 'date-fns';
import { ko } from 'date-fns/locale';
import { getIssues } from '../api/issues';
import { getCategoryColors } from '../utils/constants';
import { LoadingFallback } from '../components/common';
import type { Issue } from '../types';

function formatRelativeDate(dateString: string): string {
  const date = parseISO(dateString);
  if (isToday(date)) return '오늘';
  if (isYesterday(date)) return '어제';
  const days = differenceInDays(new Date(), date);
  if (days < 7) return `${days}일 전`;
  return format(date, 'M월 d일', { locale: ko });
}

function IssueItem({ issue, onClick }: { issue: Issue; onClick: () => void }) {
  const colors = getCategoryColors(issue.category);

  return (
    <div
      onClick={onClick}
      className="flex items-start gap-4 p-4 bg-white border border-gray-200 rounded-lg hover:border-amber-300 hover:shadow-sm transition-all cursor-pointer"
    >
      {/* 카테고리 색상 인디케이터 */}
      <div className={`w-1 h-full min-h-[40px] rounded-full ${colors.bg}`} />

      {/* 콘텐츠 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className={`text-xs px-2 py-0.5 rounded-full ${colors.bg} ${colors.text}`}>
            {issue.category || '기타'}
          </span>
          {issue.hasContent && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">
              콘텐츠
            </span>
          )}
        </div>
        <h3 className="font-medium text-gray-900 truncate">{issue.name}</h3>
        <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
          <span>{formatRelativeDate(issue.lastSeenAt)} 업데이트</span>
          <span>기사 {issue.latestArticleCount || 0}개</span>
        </div>
      </div>

      {/* 화살표 */}
      <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
      </svg>
    </div>
  );
}

export default function CalendarPage() {
  const navigate = useNavigate();

  const { data, isLoading, error } = useQuery({
    queryKey: ['issues', 1, 50],
    queryFn: () => getIssues(1, 50),
  });

  const issues = data?.items || [];

  // 날짜별로 그룹핑
  const groupedIssues = issues.reduce((acc, issue) => {
    const date = issue.lastSeenAt.split('T')[0];
    if (!acc[date]) acc[date] = [];
    acc[date].push(issue);
    return acc;
  }, {} as Record<string, Issue[]>);

  const sortedDates = Object.keys(groupedIssues).sort((a, b) => b.localeCompare(a));

  return (
    <LoadingFallback
      isLoading={isLoading}
      error={error as Error | null}
      errorMessage="이슈를 불러올 수 없습니다."
    >
      <div className="max-w-3xl mx-auto">
        {/* 헤더 */}
        <div className="mb-6">
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">최근 업데이트된 이슈</h1>
          <p className="text-sm text-gray-500 mt-1">
            새로운 이슈와 업데이트된 이슈를 확인하세요
          </p>
        </div>

        {/* 이슈 목록 */}
        <div className="space-y-6">
          {sortedDates.map((date) => (
            <div key={date}>
              {/* 날짜 헤더 */}
              <div className="flex items-center gap-3 mb-3">
                <div className="text-sm font-medium text-gray-700">
                  {formatRelativeDate(date)}
                </div>
                <div className="flex-1 h-px bg-gray-200" />
                <div className="text-xs text-gray-400">
                  {groupedIssues[date].length}개 이슈
                </div>
              </div>

              {/* 이슈 카드들 */}
              <div className="space-y-3">
                {groupedIssues[date].map((issue) => (
                  <IssueItem
                    key={issue.id}
                    issue={issue}
                    onClick={() => navigate(`/issues/${issue.id}`)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* 빈 상태 */}
        {issues.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-500">최근 업데이트된 이슈가 없습니다.</p>
          </div>
        )}
      </div>
    </LoadingFallback>
  );
}
