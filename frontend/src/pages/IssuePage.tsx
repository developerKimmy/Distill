import { useState, useMemo, memo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getIssue } from '../api/issues';
import { LoadingFallback, FollowButton, CategoryBadge } from '../components/common';
import { useFollowMutation } from '../hooks';
import { formatShortDate, formatFullDate } from '../utils/dateFormat';
import type { IssueArticle, IssueContent } from '../types';

const INITIAL_ARTICLE_COUNT = 10;

// 기사 카드 컴포넌트
const ArticleCard = memo(function ArticleCard({ article }: { article: IssueArticle }) {
  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block p-2.5 sm:p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
    >
      <p className="font-medium text-gray-900 line-clamp-2 sm:line-clamp-1 text-sm sm:text-base">
        {article.title}
      </p>
      {article.description && (
        <p className="text-xs sm:text-sm text-gray-600 mt-1 line-clamp-2">
          {article.description}
        </p>
      )}
      <p className="text-[10px] sm:text-xs text-gray-400 mt-1.5 sm:mt-2">
        {article.press}
        {article.publishedAt && ` · ${formatFullDate(article.publishedAt)}`}
      </p>
    </a>
  );
});

// 기사 목록 컴포넌트
function ArticleList({ articles }: { articles: IssueArticle[] }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const hasMore = articles.length > INITIAL_ARTICLE_COUNT;
  const displayedArticles = isExpanded ? articles : articles.slice(0, INITIAL_ARTICLE_COUNT);
  const remainingCount = articles.length - INITIAL_ARTICLE_COUNT;

  return (
    <div className="space-y-2 sm:space-y-3">
      <h3 className="text-xs sm:text-sm font-medium text-gray-700 flex items-center gap-2">
        📰 관련 기사
        <span className="text-gray-400">({articles.length}개)</span>
      </h3>
      {displayedArticles.map((article) => (
        <ArticleCard key={article.id} article={article} />
      ))}
      {hasMore && !isExpanded && (
        <button
          onClick={() => setIsExpanded(true)}
          className="w-full py-2 text-sm text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
        >
          +{remainingCount}개 더보기
        </button>
      )}
      {isExpanded && hasMore && (
        <button
          onClick={() => setIsExpanded(false)}
          className="w-full py-2 text-sm text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
        >
          접기
        </button>
      )}
    </div>
  );
}

// 콘텐츠 카드 컴포넌트
function ContentCard({ content }: { content: IssueContent }) {
  return (
    <div className="p-3 sm:p-4 bg-amber-50 border border-amber-200 rounded-lg">
      {content.content && (
        <div className="prose prose-sm prose-gray max-w-none overflow-x-auto">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content.content}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}

export default function IssuePage() {
  const { issueId } = useParams<{ issueId: string }>();

  const queryKey = useMemo(() => ['issue', issueId], [issueId]);

  const { data: issue, isLoading, error } = useQuery({
    queryKey,
    queryFn: () => getIssue(issueId!),
    enabled: !!issueId,
  });

  const { toggleFollow, isLoading: isFollowLoading } = useFollowMutation({
    queryKey,
    updateFn: (old, _issueId, isFollowing) => {
      if (!old || typeof old !== 'object') return old;
      return { ...old, isFollowing };
    },
  });

  // 날짜별로 기사 그룹핑
  const groupedArticles = useMemo(() => {
    if (!issue?.articles) return new Map<string, IssueArticle[]>();

    const groups = new Map<string, IssueArticle[]>();
    for (const article of issue.articles) {
      const dateKey = article.collectedAt?.split('T')[0] || 'unknown';
      if (!groups.has(dateKey)) {
        groups.set(dateKey, []);
      }
      groups.get(dateKey)!.push(article);
    }

    // 날짜순 정렬된 Map 반환
    return new Map(
      [...groups.entries()].sort((a, b) => b[0].localeCompare(a[0]))
    );
  }, [issue?.articles]);

  const sortedDates = useMemo(() => [...groupedArticles.keys()].filter(d => d !== 'unknown'), [groupedArticles]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  // 선택된 날짜의 기사들
  const selectedArticles = useMemo(() => {
    const date = selectedDate || sortedDates[0];
    if (!date) return [];
    return groupedArticles.get(date) || [];
  }, [selectedDate, sortedDates, groupedArticles]);

  const isLoggedIn = !!localStorage.getItem('access_token');

  return (
    <LoadingFallback
      isLoading={isLoading}
      error={error as Error | null}
      errorMessage="이슈를 불러올 수 없습니다."
    >
      {issue && (
        <div className="space-y-6">
          {/* 헤더 */}
          <div>
            <Link to="/issues" className="text-xs sm:text-sm text-gray-500 hover:text-gray-700">
              ← 이슈 목록
            </Link>
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mt-2">
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <CategoryBadge category={issue.category || '기타'} />
                  {issue.whatType && (
                    <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded">
                      {issue.whatType}
                    </span>
                  )}
                </div>
                <h1 className="text-xl sm:text-2xl font-bold text-gray-900">{issue.name}</h1>
                {issue.whatSummary && (
                  <p className="text-sm text-gray-600 mt-1">{issue.whatSummary}</p>
                )}
                <p className="text-xs sm:text-sm text-gray-500 mt-2">
                  {issue.firstSeenAt && issue.lastSeenAt && (
                    <span>
                      {formatFullDate(issue.firstSeenAt)} ~ {formatFullDate(issue.lastSeenAt)}
                    </span>
                  )}
                  <span className="ml-2">· {issue.articles.length}개 기사</span>
                </p>
              </div>
              <FollowButton
                isFollowing={issue.isFollowing}
                onClick={() => toggleFollow(issue.id, issue.isFollowing)}
                variant="full"
                disabled={isFollowLoading}
              />
            </div>
          </div>

          {/* 키워드 */}
          {issue.keywords && issue.keywords.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {issue.keywords.slice(0, 10).map((keyword, idx) => (
                <span
                  key={idx}
                  className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded-full"
                >
                  #{keyword}
                </span>
              ))}
            </div>
          )}

          {/* 엔티티 */}
          {issue.entities && issue.entities.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {issue.entities.map((entity) => (
                <span
                  key={entity.id}
                  className={`text-xs px-2 py-1 rounded-full ${
                    entity.type === 'person' ? 'bg-purple-100 text-purple-700' :
                    entity.type === 'org' ? 'bg-blue-100 text-blue-700' :
                    'bg-green-100 text-green-700'
                  }`}
                >
                  {entity.name}
                </span>
              ))}
            </div>
          )}

          {/* 콘텐츠 */}
          {issue.contents && issue.contents.length > 0 && (
            <div className="space-y-4">
              <h2 className="text-base sm:text-lg font-semibold">📝 생성된 콘텐츠</h2>
              {issue.contents.map((content) => (
                <ContentCard key={content.id} content={content} />
              ))}
            </div>
          )}

          {/* 비로그인 CTA */}
          {!isLoggedIn && (
            <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-lg p-4 sm:p-5">
              <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
                <div className="text-xl sm:text-2xl">📬</div>
                <div className="flex-1">
                  <h3 className="font-medium text-gray-900 text-xs sm:text-sm">
                    이 이슈의 업데이트를 이메일로 받아보세요
                  </h3>
                  <p className="text-xs text-gray-500 mt-0.5">
                    관심 이슈를 팔로우하고 새 소식을 받아볼 수 있어요.
                  </p>
                </div>
                <Link
                  to="/register"
                  className="shrink-0 bg-amber-500 hover:bg-amber-600 text-white text-xs sm:text-sm font-medium px-4 py-2 rounded-lg transition-colors text-center"
                >
                  시작하기
                </Link>
              </div>
            </div>
          )}

          {/* 날짜 선택 */}
          {sortedDates.length > 1 && (
            <div className="flex items-center gap-2 overflow-x-auto pb-2">
              {sortedDates.map((date) => (
                <button
                  key={date}
                  onClick={() => setSelectedDate(date)}
                  className={`px-3 py-1.5 rounded-full text-xs sm:text-sm whitespace-nowrap transition-colors ${
                    (selectedDate || sortedDates[0]) === date
                      ? 'bg-amber-500 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {formatShortDate(date)}
                  <span className="ml-1 opacity-70">({groupedArticles.get(date)?.length || 0})</span>
                </button>
              ))}
            </div>
          )}

          {/* 기사 목록 */}
          <div className="bg-white rounded-lg border border-gray-200 p-3 sm:p-4">
            <ArticleList articles={selectedArticles} />
          </div>
        </div>
      )}
    </LoadingFallback>
  );
}
