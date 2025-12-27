import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getIssues } from '../api/issues';
import { LoadingFallback, IssueCard, CategoryBadge } from '../components/common';
import { useFollowMutation } from '../hooks';
import { AVAILABLE_CATEGORIES } from '../utils/constants';
import type { Issue } from '../types';

interface CategorySectionProps {
  categorizedIssues: Record<string, Issue[]>;
  sectionTitle: string;
  sectionIcon: string;
  onFollowClick: (e: React.MouseEvent, issue: Issue) => void;
}

function CategorySection({
  categorizedIssues,
  sectionTitle,
  sectionIcon,
  onFollowClick,
}: CategorySectionProps) {
  const categories = Object.keys(categorizedIssues).sort();
  if (categories.length === 0) return null;

  const totalCount = Object.values(categorizedIssues).flat().length;

  return (
    <div className="space-y-4 sm:space-y-6">
      <h2 className="text-lg sm:text-xl font-bold text-gray-900 flex items-center gap-2">
        <span>{sectionIcon}</span>
        {sectionTitle}
        <span className="text-xs sm:text-sm font-normal text-gray-500">
          ({totalCount}개)
        </span>
      </h2>

      {categories.map((category) => (
        <div key={category} className="space-y-2 sm:space-y-3">
          <div className="flex items-center gap-2">
            <CategoryBadge category={category} />
            <span className="text-xs sm:text-sm text-gray-500">
              ({categorizedIssues[category].length})
            </span>
          </div>
          <div className="grid gap-2 sm:gap-3 md:grid-cols-2">
            {categorizedIssues[category].map((issue) => (
              <IssueCard
                key={issue.id}
                issue={issue}
                onFollowClick={onFollowClick}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function CategoryLegend() {
  return (
    <div className="flex flex-wrap items-center gap-3 sm:gap-5 text-xs sm:text-sm text-gray-600">
      {AVAILABLE_CATEGORIES.map((category) => (
        <CategoryBadge key={category} category={category} variant="dot" />
      ))}
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

  // Memoized grouping logic
  const { contentsByCategory, newsByCategory } = useMemo(() => {
    if (!data?.items) {
      return { contentsByCategory: {}, newsByCategory: {} };
    }

    const groupByCategory = (issues: Issue[]) => {
      return issues.reduce((acc, issue) => {
        const category = issue.category || '기타';
        if (!acc[category]) acc[category] = [];
        acc[category].push(issue);
        return acc;
      }, {} as Record<string, Issue[]>);
    };

    const contents = data.items.filter((issue) => issue.hasContent);
    const news = data.items.filter((issue) => !issue.hasContent);

    return {
      contentsByCategory: groupByCategory(contents),
      newsByCategory: groupByCategory(news),
    };
  }, [data?.items]);

  const hasContents = Object.keys(contentsByCategory).length > 0;
  const hasNews = Object.keys(newsByCategory).length > 0;

  return (
    <LoadingFallback
      isLoading={isLoading}
      error={error as Error | null}
      errorMessage="이슈를 불러올 수 없습니다."
    >
      <div className="space-y-6 sm:space-y-8">
        <div className="flex items-center justify-between">
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">이슈 목록</h1>
          <p className="text-xs sm:text-sm text-gray-500">
            총 {data?.total || 0}개 이슈
          </p>
        </div>

        <CategoryLegend />

        {/* 콘텐츠 섹션 */}
        <CategorySection
          categorizedIssues={contentsByCategory}
          sectionTitle="콘텐츠"
          sectionIcon="📝"
          onFollowClick={handleFollowClick}
        />

        {/* 구분선 */}
        {hasContents && hasNews && <hr className="border-gray-200" />}

        {/* 뉴스 섹션 */}
        <CategorySection
          categorizedIssues={newsByCategory}
          sectionTitle="뉴스"
          sectionIcon="📰"
          onFollowClick={handleFollowClick}
        />

        {/* 데이터 없음 */}
        {!hasContents && !hasNews && (
          <div className="text-center py-12">
            <p className="text-gray-500">등록된 이슈가 없습니다.</p>
          </div>
        )}
      </div>
    </LoadingFallback>
  );
}
