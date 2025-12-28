import { useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { format, parseISO } from 'date-fns';
import { ko } from 'date-fns/locale';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getDailyDigest, type DigestIssue, type DigestCategory } from '../api/issues';
import { LoadingFallback, CategoryBadge } from '../components/common';
import { getCategoryColors } from '../utils/constants';

function IssueCard({ issue }: { issue: DigestIssue }) {
  const navigate = useNavigate();
  const colors = getCategoryColors(issue.category);

  return (
    <div
      onClick={() => navigate(`/issues/${issue.id}`)}
      className="p-3 bg-white border border-gray-200 rounded-lg hover:border-amber-300 hover:shadow-sm transition-all cursor-pointer"
    >
      <div className="flex items-start gap-3">
        <div className={`w-1 self-stretch rounded-full ${colors.bg}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="font-medium text-gray-900 text-sm truncate">{issue.name}</h4>
            {issue.isNew && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 text-red-600 font-medium">
                NEW
              </span>
            )}
          </div>
          {issue.summary && (
            <p className="text-xs text-gray-600 line-clamp-2 mb-2">{issue.summary}</p>
          )}
          {issue.contentTitle && (
            <div className="text-xs text-amber-700 bg-amber-50 px-2 py-1 rounded">
              {issue.contentTitle}
            </div>
          )}
          <div className="text-[10px] text-gray-400 mt-2">
            기사 {issue.articleCount}개
          </div>
        </div>
      </div>
    </div>
  );
}

function CategorySection({ category }: { category: DigestCategory }) {
  return (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-3">
        <CategoryBadge category={category.category} size="md" />
        <span className="text-xs text-gray-500">
          {category.issues.length}개 이슈 · 기사 {category.totalArticles}개
        </span>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {category.issues.map((issue, idx) => (
          <IssueCard key={`${category.category}-${issue.id}-${idx}`} issue={issue} />
        ))}
      </div>
    </div>
  );
}

export default function DailyDigestPage() {
  const { date } = useParams<{ date: string }>();

  const displayDate = useMemo(() => {
    if (!date) return '';
    try {
      return format(parseISO(date), 'yyyy년 M월 d일 (EEEE)', { locale: ko });
    } catch {
      return date;
    }
  }, [date]);

  const { data, isLoading, error } = useQuery({
    queryKey: ['daily-digest', date],
    queryFn: () => getDailyDigest(date!),
    enabled: !!date,
  });

  return (
    <LoadingFallback
      isLoading={isLoading}
      error={error as Error | null}
      errorMessage="다이제스트를 불러올 수 없습니다."
    >
      {data && (
        <div className="max-w-4xl mx-auto">
          {/* 헤더 */}
          <div className="mb-6">
            <Link to="/" className="text-xs sm:text-sm text-gray-500 hover:text-gray-700">
              ← 캘린더로 돌아가기
            </Link>
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900 mt-2">
              {displayDate} 브리핑
            </h1>
            {data.updatedAt && (
              <p className="text-xs text-gray-400 mt-1">
                마지막 업데이트: {format(parseISO(data.updatedAt), 'HH:mm', { locale: ko })}
              </p>
            )}
          </div>

          {/* 통계 요약 */}
          <div className="grid grid-cols-3 gap-3 mb-6">
            <div className="bg-white border border-gray-200 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-gray-900">{data.totalIssues}</div>
              <div className="text-xs text-gray-500">총 이슈</div>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-red-600">{data.newIssuesCount}</div>
              <div className="text-xs text-gray-500">신규 이슈</div>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-amber-600">{data.totalArticles}</div>
              <div className="text-xs text-gray-500">총 기사</div>
            </div>
          </div>

          {/* 다이제스트 요약 */}
          {data.digestSummary && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
              <div className="prose prose-sm max-w-none
                prose-headings:text-gray-900 prose-h1:text-lg prose-h1:font-bold prose-h1:mt-4 prose-h1:mb-2
                prose-h2:text-base prose-h2:font-semibold prose-h2:mt-3 prose-h2:mb-1 prose-h2:text-amber-800
                prose-h3:font-medium prose-h3:mt-2 prose-h3:text-gray-800
                prose-p:text-gray-700 prose-li:text-gray-700
                prose-table:text-xs prose-th:bg-amber-100 prose-th:p-2 prose-td:p-2 prose-td:border-amber-200
                prose-hr:border-amber-200">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {data.digestSummary}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {/* 카테고리별 이슈 */}
          <div>
            {data.categories.map((category) => (
              <CategorySection key={category.category} category={category} />
            ))}
          </div>

          {/* 빈 상태 */}
          {data.categories.length === 0 && (
            <div className="text-center py-12">
              <p className="text-gray-500">이 날짜에는 수집된 이슈가 없습니다.</p>
            </div>
          )}
        </div>
      )}
    </LoadingFallback>
  );
}
