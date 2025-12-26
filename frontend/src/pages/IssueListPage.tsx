import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getIssues } from '../api/issues';
import type { Issue } from '../types';

export default function IssueListPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['issues', 1, 100],
    queryFn: () => getIssues(1, 100),
  });

  // 콘텐츠/뉴스 분리 및 카테고리별 그룹핑
  const { contentsByCategory, newsByCategory } = useMemo(() => {
    if (!data?.items) {
      return { contentsByCategory: {}, newsByCategory: {} };
    }

    const contents: Issue[] = [];
    const news: Issue[] = [];

    data.items.forEach((issue) => {
      if (issue.hasContent) {
        contents.push(issue);
      } else {
        news.push(issue);
      }
    });

    const groupByCategory = (issues: Issue[]) => {
      return issues.reduce((acc, issue) => {
        const category = issue.category || '기타';
        if (!acc[category]) {
          acc[category] = [];
        }
        acc[category].push(issue);
        return acc;
      }, {} as Record<string, Issue[]>);
    };

    return {
      contentsByCategory: groupByCategory(contents),
      newsByCategory: groupByCategory(news),
    };
  }, [data]);

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return `${d.getMonth() + 1}/${d.getDate()}`;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-gray-500">로딩 중...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-gray-500">이슈를 불러올 수 없습니다.</p>
      </div>
    );
  }

  const categoryColors: Record<string, string> = {
    정치: 'bg-red-100 text-red-800',
    경제: 'bg-amber-100 text-amber-800',
    사회: 'bg-emerald-100 text-emerald-800',
    IT: 'bg-sky-100 text-sky-800',
    문화: 'bg-violet-100 text-violet-800',
    기타: 'bg-gray-100 text-gray-800',
  };

  const renderIssueCard = (issue: Issue) => (
    <Link
      key={issue.id}
      to={`/issues/${issue.id}`}
      className="block bg-white rounded-lg border border-gray-200 p-4 hover:border-amber-300 transition-colors"
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-gray-900 truncate">{issue.name}</h3>
          <p className="text-sm text-gray-500 mt-1">
            {formatDate(issue.firstSeenAt)} ~ {formatDate(issue.lastSeenAt)}
            <span className="ml-2">({issue.totalSnapshots}일)</span>
          </p>
        </div>
        {issue.latestArticleCount && (
          <span className="ml-4 text-sm text-amber-600 font-medium whitespace-nowrap">
            기사 {issue.latestArticleCount}개
          </span>
        )}
      </div>
    </Link>
  );

  const renderCategorySection = (
    categorizedIssues: Record<string, Issue[]>,
    sectionTitle: string,
    sectionIcon: string
  ) => {
    const categories = Object.keys(categorizedIssues).sort();

    if (categories.length === 0) {
      return null;
    }

    return (
      <div className="space-y-6">
        <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
          <span>{sectionIcon}</span>
          {sectionTitle}
          <span className="text-sm font-normal text-gray-500">
            ({Object.values(categorizedIssues).flat().length}개)
          </span>
        </h2>

        {categories.map((category) => (
          <div key={category} className="space-y-3">
            <div className="flex items-center gap-2">
              <span
                className={`px-2 py-1 rounded-full text-sm font-medium ${
                  categoryColors[category] || categoryColors['기타']
                }`}
              >
                {category}
              </span>
              <span className="text-sm text-gray-500">
                ({categorizedIssues[category].length})
              </span>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {categorizedIssues[category].map(renderIssueCard)}
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">이슈 목록</h1>
        <p className="text-sm text-gray-500">
          총 {data?.total || 0}개 이슈
        </p>
      </div>

      {/* 콘텐츠 섹션 */}
      {renderCategorySection(contentsByCategory, '콘텐츠', '📝')}

      {/* 구분선 */}
      {Object.keys(contentsByCategory).length > 0 &&
        Object.keys(newsByCategory).length > 0 && (
          <hr className="border-gray-200" />
        )}

      {/* 뉴스 섹션 */}
      {renderCategorySection(newsByCategory, '뉴스', '📰')}

      {/* 데이터 없음 */}
      {Object.keys(contentsByCategory).length === 0 &&
        Object.keys(newsByCategory).length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-500">등록된 이슈가 없습니다.</p>
          </div>
        )}
    </div>
  );
}
