import { useMemo, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { format, parseISO } from 'date-fns';
import { ko } from 'date-fns/locale';
import { getIssues } from '../api/issues';
import { LoadingFallback, LoadingOverlay, CategoryBadge } from '../components/common';
import { useFollowMutation } from '../hooks';
import { getCategoryColors } from '../utils/constants';
import type { IssueListItem } from '../types';

const ITEMS_PER_CATEGORY = 5;

const CATEGORY_ORDER = ['정치', '경제', '사회', '세계', '연예', 'IT/과학', '기타'];

function IssueRow({
  issue,
  onFollowClick
}: {
  issue: IssueListItem;
  onFollowClick: (e: React.MouseEvent, issue: IssueListItem) => void;
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
          {issue.whatType && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">
              {issue.whatType}
            </span>
          )}
        </div>
        <h3 className="font-medium text-gray-900 truncate text-sm">{issue.name}</h3>
        {issue.whatSummary && (
          <p className="text-xs text-gray-500 truncate mt-0.5">{issue.whatSummary}</p>
        )}
      </div>

      {/* 날짜 + 기사 수 */}
      <div className="text-xs text-gray-400 whitespace-nowrap text-right">
        {issue.firstSeenAt && (
          <div className="text-gray-500">
            {format(parseISO(issue.firstSeenAt), 'M/d', { locale: ko })}
          </div>
        )}
        <div>{issue.articleCount || 0}개</div>
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
  const queryKey = useMemo(() => ['issues', 1, 500], []);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey,
    queryFn: () => getIssues(1, 500),
  });

  const { handleFollowClick } = useFollowMutation({ queryKey });

  // 카테고리별 그룹핑 + 정렬 (1차: 최신순, 2차: 기사수)
  const groupedByCategory = useMemo(() => {
    if (!data?.items) return {};

    const grouped = data.items.reduce((acc, issue) => {
      const category = issue.category || '기타';
      if (!acc[category]) acc[category] = [];
      acc[category].push(issue);
      return acc;
    }, {} as Record<string, IssueListItem[]>);

    // 각 카테고리 내에서 정렬: 1차 최신순, 2차 기사수
    for (const category of Object.keys(grouped)) {
      grouped[category].sort((a, b) => {
        // 1차: firstSeenAt 최신순
        const dateA = a.firstSeenAt ? new Date(a.firstSeenAt).getTime() : 0;
        const dateB = b.firstSeenAt ? new Date(b.firstSeenAt).getTime() : 0;
        if (dateB !== dateA) return dateB - dateA;
        // 2차: 기사수 많은 순
        return (b.articleCount || 0) - (a.articleCount || 0);
      });
    }

    return grouped;
  }, [data?.items]);

  // 카테고리 순서대로 정렬
  const sortedCategories = useMemo(() => {
    const categories = Object.keys(groupedByCategory);
    return CATEGORY_ORDER.filter(c => categories.includes(c))
      .concat(categories.filter(c => !CATEGORY_ORDER.includes(c)));
  }, [groupedByCategory]);

  const toggleCategory = (category: string) => {
    setExpandedCategories(prev => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  };

  return (
    <LoadingFallback
      isLoading={isLoading}
      error={error as Error | null}
      errorMessage="이슈를 불러올 수 없습니다."
    >
      <LoadingOverlay isLoading={isFetching && !isLoading} />
      <div className="max-w-3xl mx-auto space-y-6">
        {/* 헤더 */}
        <div className="flex items-center justify-between">
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">이슈 목록</h1>
          <div className="flex items-center gap-3">
            <Link
              to="/search"
              className="text-sm text-gray-500 hover:text-amber-600 flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              검색
            </Link>
            <p className="text-xs sm:text-sm text-gray-500">
              총 {data?.total || 0}개
            </p>
          </div>
        </div>

        {/* 카테고리별 이슈 목록 */}
        <div className="space-y-6">
          {sortedCategories.map((category) => {
            const issues = groupedByCategory[category];
            const isExpanded = expandedCategories.has(category);
            const visibleIssues = isExpanded ? issues : issues.slice(0, ITEMS_PER_CATEGORY);
            const hasMore = issues.length > ITEMS_PER_CATEGORY;
            const colors = getCategoryColors(category);

            return (
              <div key={category}>
                {/* 카테고리 헤더 */}
                <div className="flex items-center gap-3 mb-3">
                  <div className={`text-sm font-semibold ${colors.text}`}>
                    {category}
                  </div>
                  <div className="flex-1 h-px bg-gray-200" />
                  <div className="text-xs text-gray-400">
                    {issues.length}개
                  </div>
                </div>

                {/* 이슈 리스트 */}
                <div className="space-y-2">
                  {visibleIssues.map((issue) => (
                    <IssueRow
                      key={issue.id}
                      issue={issue}
                      onFollowClick={handleFollowClick}
                    />
                  ))}
                </div>

                {/* 더보기/접기 버튼 */}
                {hasMore && (
                  <button
                    onClick={() => toggleCategory(category)}
                    className="w-full mt-2 py-2 flex items-center justify-center gap-1 text-sm text-gray-500 hover:text-amber-600 hover:bg-gray-50 rounded-lg transition-colors"
                  >
                    {isExpanded ? (
                      <>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                        </svg>
                        접기
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                        {issues.length - ITEMS_PER_CATEGORY}개 더보기
                      </>
                    )}
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {/* 빈 상태 */}
        {sortedCategories.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-500">등록된 이슈가 없습니다.</p>
          </div>
        )}
      </div>
    </LoadingFallback>
  );
}
