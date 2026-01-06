import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getDailyReport } from '../api/issues';
import { CategoryBadge, LoadingOverlay } from '../components/common';
import type { DailyReportIssue } from '../types';

export default function ReportPage() {
  const { date } = useParams<{ date: string }>();

  const { data: report, isLoading, isFetching, error } = useQuery({
    queryKey: ['dailyReport', date],
    queryFn: () => getDailyReport(date!),
    enabled: !!date,
  });

  if (isLoading) {
    return <LoadingOverlay isLoading={true} />;
  }

  if (error || !report) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-gray-500">리포트를 불러올 수 없습니다.</p>
      </div>
    );
  }

  const showLoadingOverlay = isFetching && !isLoading;

  // 카테고리별 그룹핑
  const groupedByCategory = report.issues.reduce((acc, issue) => {
    const category = issue.category || '기타';
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(issue);
    return acc;
  }, {} as Record<string, DailyReportIssue[]>);

  // 기사 수 기준 정렬
  Object.keys(groupedByCategory).forEach((category) => {
    groupedByCategory[category].sort((a, b) => b.articleCount - a.articleCount);
  });

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`;
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <LoadingOverlay isLoading={showLoadingOverlay} />
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <Link to="/" className="text-sm text-gray-500 hover:text-gray-700">
            ← 캘린더로 돌아가기
          </Link>
          <h1 className="text-2xl font-bold text-gray-900 mt-1">
            {formatDate(date!)} 리포트
          </h1>
        </div>
        <div className="text-right">
          <p className="text-sm font-medium text-gray-900">
            {report.totalIssues}개 이슈
          </p>
          <p className="text-xs text-gray-500">
            총 {report.totalArticles}개 기사
          </p>
        </div>
      </div>

      {/* 카테고리별 이슈 */}
      {Object.entries(groupedByCategory).map(([category, issues]) => (
        <div key={category} className="space-y-3">
          <div className="flex items-center gap-2">
            <CategoryBadge category={category} size="md" />
            <span className="text-sm text-gray-500">
              {issues.length}개 이슈
            </span>
          </div>

          <div className="space-y-2">
            {issues.map((issue) => (
              <Link
                key={issue.id}
                to={`/issues/${issue.id}`}
                className="block bg-white rounded-lg border border-gray-200 p-4 hover:border-amber-300 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-medium text-gray-900">
                        {issue.name}
                      </h3>
                      {issue.whatType && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">
                          {issue.whatType}
                        </span>
                      )}
                    </div>
                    {/* 대표 기사 미리보기 */}
                    {issue.articles && issue.articles.length > 0 && (
                      <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                        {issue.articles[0].title}
                      </p>
                    )}
                  </div>
                  <div className="ml-4 text-right">
                    <p className="text-sm font-medium text-amber-600">
                      기사 {issue.articleCount}개
                    </p>
                  </div>
                </div>

                {/* 기사 목록 미리보기 */}
                {issue.articles && issue.articles.length > 1 && (
                  <div className="mt-3 pt-3 border-t border-gray-100">
                    <div className="space-y-1">
                      {issue.articles.slice(1, 4).map((article) => (
                        <p key={article.id} className="text-xs text-gray-500 truncate">
                          · {article.title}
                          {article.press && (
                            <span className="text-gray-400"> ({article.press})</span>
                          )}
                        </p>
                      ))}
                      {issue.articles.length > 4 && (
                        <p className="text-xs text-gray-400">
                          +{issue.articles.length - 4}개 더
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </Link>
            ))}
          </div>
        </div>
      ))}

      {/* 빈 상태 */}
      {report.issues.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500">이 날짜에는 수집된 이슈가 없습니다.</p>
        </div>
      )}
    </div>
  );
}
