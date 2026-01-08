import { useState, useMemo, useCallback } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { searchAll, getSuggestions } from '../api/search';
import { CategoryBadge, LoadingOverlay } from '../components/common';
import { formatFullDate } from '../utils/dateFormat';
import type { IssueSearchResult, ArticleSearchResult, ContentSearchResult } from '../types';

// 디바운스 훅
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useMemo(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

// 이슈 검색 결과 카드
function IssueResultCard({ issue }: { issue: IssueSearchResult }) {
  const navigate = useNavigate();

  return (
    <div
      onClick={() => navigate(`/issues/${issue.id}`)}
      className="p-3 bg-white border border-gray-200 rounded-lg hover:border-amber-300 hover:shadow-sm transition-all cursor-pointer"
    >
      <div className="flex items-center gap-2 mb-1">
        <CategoryBadge category={issue.category || '기타'} size="sm" />
        {issue.whatType && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">
            {issue.whatType}
          </span>
        )}
        {issue.similarity !== null && (
          <span className="text-[10px] text-gray-400 ml-auto">
            {Math.round(issue.similarity * 100)}% 매칭
          </span>
        )}
      </div>
      <h3 className="font-medium text-gray-900 text-sm">{issue.name}</h3>
      {issue.whatSummary && (
        <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{issue.whatSummary}</p>
      )}
      <p className="text-[10px] text-gray-400 mt-1">
        {issue.articleCount || 0}개 기사
      </p>
    </div>
  );
}

// 기사 검색 결과 카드
function ArticleResultCard({ article }: { article: ArticleSearchResult }) {
  const navigate = useNavigate();

  return (
    <div
      onClick={() => window.open(article.url, '_blank')}
      className="block p-3 bg-white border border-gray-200 rounded-lg hover:border-amber-300 hover:shadow-sm transition-all cursor-pointer"
    >
      <p className="font-medium text-gray-900 text-sm line-clamp-2">{article.title}</p>
      {article.description && (
        <p className="text-xs text-gray-600 mt-1 line-clamp-2">{article.description}</p>
      )}
      <div className="flex items-center gap-2 mt-1.5 text-[10px] text-gray-400">
        {article.press && <span>{article.press}</span>}
        {article.publishedAt && <span>· {formatFullDate(article.publishedAt)}</span>}
        {article.issueName && article.issueId && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/issues/${article.issueId}`);
            }}
            className="text-amber-600 hover:underline"
          >
            {article.issueName}
          </button>
        )}
      </div>
    </div>
  );
}

// 콘텐츠 검색 결과 카드
function ContentResultCard({ content }: { content: ContentSearchResult }) {
  const navigate = useNavigate();

  return (
    <div
      onClick={() => content.issueId && navigate(`/issues/${content.issueId}`)}
      className={`p-3 bg-amber-50 border border-amber-200 rounded-lg hover:shadow-sm transition-all ${content.issueId ? 'cursor-pointer' : ''}`}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs font-medium text-amber-700">
          {content.title || '콘텐츠'}
        </span>
        {content.verified && (
          <span className="text-[10px] bg-green-100 text-green-700 px-1 py-0.5 rounded">
            검증됨
          </span>
        )}
        {content.similarity !== null && (
          <span className="text-[10px] text-gray-400 ml-auto">
            {Math.round(content.similarity * 100)}% 매칭
          </span>
        )}
      </div>
      {content.contentPreview && (
        <p className="text-xs text-gray-600 line-clamp-3">{content.contentPreview}</p>
      )}
      <div className="flex items-center gap-2 mt-1.5 text-[10px] text-gray-400">
        {content.issueName && content.issueId && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/issues/${content.issueId}`);
            }}
            className="text-amber-600 hover:underline"
          >
            {content.issueName} →
          </button>
        )}
        {content.createdAt && <span>· {formatFullDate(content.createdAt)}</span>}
      </div>
    </div>
  );
}

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuery = searchParams.get('q') || '';
  const [query, setQuery] = useState(initialQuery);
  const [activeTab, setActiveTab] = useState<'all' | 'issues' | 'articles' | 'contents'>('all');

  const debouncedQuery = useDebounce(query, 300);

  // 검색 쿼리
  const { data: searchResults, isLoading, isFetching, error } = useQuery({
    queryKey: ['search', debouncedQuery],
    queryFn: () => searchAll(debouncedQuery, 30),
    enabled: debouncedQuery.length >= 2,
  });

  // 자동완성
  const { data: suggestions } = useQuery({
    queryKey: ['suggestions', debouncedQuery],
    queryFn: () => getSuggestions(debouncedQuery, 5),
    enabled: debouncedQuery.length >= 1 && debouncedQuery.length < 10,
  });

  // 검색 핸들러
  const handleSearch = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      setSearchParams({ q: query.trim() });
    }
  }, [query, setSearchParams]);

  // 제안 클릭 핸들러
  const handleSuggestionClick = useCallback((suggestion: string) => {
    setQuery(suggestion);
    setSearchParams({ q: suggestion });
  }, [setSearchParams]);

  // 탭별 결과 카운트
  const counts = useMemo(() => {
    if (!searchResults) return { issues: 0, articles: 0, contents: 0, total: 0 };
    return {
      issues: searchResults.issues.length,
      articles: searchResults.articles.length,
      contents: searchResults.contents.length,
      total: searchResults.total
    };
  }, [searchResults]);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <LoadingOverlay isLoading={isFetching && !isLoading} />
      {/* 헤더 */}
      <div>
        <Link to="/issues" className="text-xs sm:text-sm text-gray-500 hover:text-gray-700">
          ← 이슈 목록
        </Link>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 mt-2">검색</h1>
      </div>

      {/* 검색 입력 */}
      <form onSubmit={handleSearch}>
        <div className="relative">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="이슈, 기사, 콘텐츠 검색..."
            className="w-full px-4 py-3 pr-12 border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-amber-500 outline-none"
          />
          <button
            type="submit"
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-amber-500"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </button>
        </div>

        {/* 자동완성 제안 */}
        {suggestions && suggestions.suggestions.length > 0 && query.length >= 1 && !isLoading && (
          <div className="mt-2 flex flex-wrap gap-2">
            {suggestions.suggestions.map((suggestion, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleSuggestionClick(suggestion)}
                className="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded-full hover:bg-amber-100 hover:text-amber-700 transition-colors"
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
      </form>

      {/* 로딩 */}
      {isLoading && debouncedQuery.length >= 2 && (
        <LoadingOverlay isLoading={true} />
      )}

      {error && (
        <div className="text-center py-8 text-red-500">
          검색 중 오류가 발생했습니다.
        </div>
      )}

      {!isLoading && searchResults && (
        <>
          {/* 탭 */}
          <div className="flex items-center gap-1 border-b border-gray-200">
            {[
              { key: 'all', label: '전체', count: counts.total },
              { key: 'issues', label: '이슈', count: counts.issues },
              { key: 'articles', label: '기사', count: counts.articles },
              { key: 'contents', label: '콘텐츠', count: counts.contents },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key as typeof activeTab)}
                className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                  activeTab === tab.key
                    ? 'border-amber-500 text-amber-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab.label}
                <span className="ml-1 text-xs opacity-70">({tab.count})</span>
              </button>
            ))}
          </div>

          {/* 결과 */}
          <div className="space-y-4">
            {counts.total === 0 && (
              <div className="text-center py-8 text-gray-500">
                "{searchResults.query}"에 대한 검색 결과가 없습니다.
              </div>
            )}

            {/* 이슈 결과 */}
            {(activeTab === 'all' || activeTab === 'issues') && searchResults.issues.length > 0 && (
              <div>
                {activeTab === 'all' && (
                  <h2 className="text-sm font-semibold text-gray-700 mb-2">
                    이슈 ({counts.issues})
                  </h2>
                )}
                <div className="space-y-2">
                  {searchResults.issues.slice(0, activeTab === 'all' ? 5 : undefined).map((issue) => (
                    <IssueResultCard key={issue.id} issue={issue} />
                  ))}
                </div>
              </div>
            )}

            {/* 기사 결과 */}
            {(activeTab === 'all' || activeTab === 'articles') && searchResults.articles.length > 0 && (
              <div>
                {activeTab === 'all' && (
                  <h2 className="text-sm font-semibold text-gray-700 mb-2">
                    기사 ({counts.articles})
                  </h2>
                )}
                <div className="space-y-2">
                  {searchResults.articles.slice(0, activeTab === 'all' ? 5 : undefined).map((article) => (
                    <ArticleResultCard key={article.id} article={article} />
                  ))}
                </div>
              </div>
            )}

            {/* 콘텐츠 결과 */}
            {(activeTab === 'all' || activeTab === 'contents') && searchResults.contents.length > 0 && (
              <div>
                {activeTab === 'all' && (
                  <h2 className="text-sm font-semibold text-gray-700 mb-2">
                    콘텐츠 ({counts.contents})
                  </h2>
                )}
                <div className="space-y-2">
                  {searchResults.contents.slice(0, activeTab === 'all' ? 5 : undefined).map((content) => (
                    <ContentResultCard key={content.id} content={content} />
                  ))}
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* 검색 전 상태 */}
      {!isLoading && !searchResults && debouncedQuery.length < 2 && (
        <div className="text-center py-12">
          <div className="text-4xl mb-3">🔍</div>
          <p className="text-gray-500">검색어를 입력하세요</p>
          <p className="text-xs text-gray-400 mt-1">이슈, 기사, 생성된 콘텐츠를 검색합니다</p>
        </div>
      )}
    </div>
  );
}
