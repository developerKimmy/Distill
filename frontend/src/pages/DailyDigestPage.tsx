import { useMemo, type ReactNode } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { format, parseISO } from 'date-fns';
import { ko } from 'date-fns/locale';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getDailyDigest } from '../api/issues';
import { LoadingFallback, LoadingOverlay } from '../components/common';
import { isLoggedIn } from '../utils/categories';

// 이슈 이름을 링크로 변환하는 텍스트 처리 함수
function processTextWithIssueLinks(
  text: string,
  issueMap: Record<string, string>
): ReactNode[] {
  const issueNames = Object.keys(issueMap).sort((a, b) => b.length - a.length);
  if (issueNames.length === 0) return [text];

  const pattern = new RegExp(`(${issueNames.map(n => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'g');
  const parts = text.split(pattern);

  return parts.map((part, idx) => {
    if (issueMap[part]) {
      return (
        <Link key={idx} to={`/issues/${issueMap[part]}`} className="no-underline text-inherit">
          {part}
        </Link>
      );
    }
    return part;
  });
}

// children을 처리하는 헬퍼 함수
function processChildren(children: ReactNode, issueMap: Record<string, string>): ReactNode {
  if (Array.isArray(children)) {
    return children.map((child) =>
      typeof child === 'string' ? processTextWithIssueLinks(child, issueMap) : child
    );
  }
  return typeof children === 'string' ? processTextWithIssueLinks(children, issueMap) : children;
}

// digestSummary에서 특정 카테고리 섹션만 필터링
function filterDigestByCategories(markdown: string, allowedCategories: string[]): string {
  if (allowedCategories.length === 0) return markdown;

  const lines = markdown.split('\n');
  const result: string[] = [];
  let currentSection: string | null = null;
  let inAllowedSection = true; // 헤더 영역은 항상 포함
  let headerEnded = false;

  for (const line of lines) {
    // ## 카테고리 형식 감지
    const h2Match = line.match(/^## (.+)$/);
    if (h2Match) {
      headerEnded = true;
      currentSection = h2Match[1].trim();
      inAllowedSection = allowedCategories.includes(currentSection);
    }

    // 헤더 영역(첫 ## 전까지) 또는 허용된 섹션이면 포함
    if (!headerEnded || inAllowedSection) {
      result.push(line);
    }
  }

  return result.join('\n');
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

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ['daily-digest', date, isLoggedIn()],
    queryFn: () => getDailyDigest(date!),
    enabled: !!date,
  });

  // 사용자 카테고리에 맞게 digestSummary 필터링
  const filteredDigestSummary = useMemo(() => {
    if (!data?.digestSummary || !data?.categories) return data?.digestSummary;
    const allowedCategories = data.categories.map(c => c.category);
    return filterDigestByCategories(data.digestSummary, allowedCategories);
  }, [data?.digestSummary, data?.categories]);

  return (
    <LoadingFallback
      isLoading={isLoading}
      error={error as Error | null}
      errorMessage="다이제스트를 불러올 수 없습니다."
    >
      <LoadingOverlay isLoading={isFetching && !isLoading} />
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
          {filteredDigestSummary && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
              <div className="prose prose-sm max-w-none
                prose-headings:text-gray-900 prose-h1:text-lg prose-h1:font-bold prose-h1:mt-4 prose-h1:mb-2
                prose-h2:text-base prose-h2:font-semibold prose-h2:mt-3 prose-h2:mb-1 prose-h2:text-amber-800
                prose-h3:font-medium prose-h3:mt-2 prose-h3:text-gray-800
                prose-p:text-gray-700 prose-li:text-gray-700
                prose-table:text-xs prose-th:bg-amber-100 prose-th:p-2 prose-td:p-2 prose-td:border-amber-200
                prose-hr:border-amber-200">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={data.issueMap ? {
                    p: ({ children }) => <p>{processChildren(children, data.issueMap!)}</p>,
                    h1: ({ children }) => <h1>{processChildren(children, data.issueMap!)}</h1>,
                    h2: ({ children }) => <h1 className="!text-[1.5rem] !font-semibold !mt-3 !mb-1 !text-amber-800">{processChildren(children, data.issueMap!)}</h1>,
                    h3: ({ children }) => <h3>{processChildren(children, data.issueMap!)}</h3>,
                    h4: ({ children }) => <h4>{processChildren(children, data.issueMap!)}</h4>,
                    li: ({ children }) => <li>{processChildren(children, data.issueMap!)}</li>,
                    td: ({ children }) => <td>{processChildren(children, data.issueMap!)}</td>,
                    strong: ({ children }) => <strong>{processChildren(children, data.issueMap!)}</strong>,
                  } : undefined}
                >
                  {filteredDigestSummary}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {/* 빈 상태 */}
          {!filteredDigestSummary && (
            <div className="text-center py-12">
              <p className="text-gray-500">이 날짜에는 브리핑이 없습니다.</p>
            </div>
          )}
        </div>
      )}
    </LoadingFallback>
  );
}
