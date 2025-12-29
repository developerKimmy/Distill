import { useState, useMemo, memo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getIssue } from '../api/issues';
import { LoadingFallback, FollowButton } from '../components/common';
import { useFollowMutation } from '../hooks';
import { formatShortDate, formatFullDate } from '../utils/dateFormat';
import type { IssueDetail } from '../types';

// memo for list items only
const ArticleCard = memo(function ArticleCard({
  article
}: {
  article: IssueDetail['snapshots'][0]['articles'][0]
}) {
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

  // 날짜별로 스냅샷 그룹핑
  const groupedByDate = useMemo(() => {
    if (!issue?.snapshots) return new Map<string, IssueDetail['snapshots']>();

    const groups = new Map<string, IssueDetail['snapshots']>();
    for (const snapshot of issue.snapshots) {
      const dateKey = snapshot.date;
      if (!groups.has(dateKey)) {
        groups.set(dateKey, []);
      }
      groups.get(dateKey)!.push(snapshot);
    }

    // 날짜순 정렬된 Map 반환
    return new Map(
      [...groups.entries()].sort((a, b) =>
        new Date(b[0]).getTime() - new Date(a[0]).getTime()
      )
    );
  }, [issue?.snapshots]);

  const sortedDates = useMemo(() => [...groupedByDate.keys()], [groupedByDate]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  // 선택된 날짜의 스냅샷들 (시간순 정렬)
  const selectedDateData = useMemo(() => {
    const date = selectedDate || sortedDates[0];
    if (!date) return null;

    const snapshots = groupedByDate.get(date) || [];
    if (snapshots.length === 0) return null;

    // 시간순 정렬 (오래된 순)
    const sortedSnapshots = [...snapshots].sort(
      (a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
    );

    // 모든 기사 통합 (중복 제거)
    const allArticles = sortedSnapshots.flatMap(s => s.articles);
    const totalArticleCount = sortedSnapshots.reduce((sum, s) => sum + s.articleCount, 0);

    return {
      date,
      snapshots: sortedSnapshots,
      articles: allArticles,
      articleCount: totalArticleCount,
    };
  }, [selectedDate, sortedDates, groupedByDate]);

  // 시간 포맷 (HH:mm)
  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false });
  };

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
            <Link to="/" className="text-xs sm:text-sm text-gray-500 hover:text-gray-700">
              ← 돌아가기
            </Link>
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mt-2">
              <div className="min-w-0">
                <h1 className="text-xl sm:text-2xl font-bold text-gray-900">{issue.name}</h1>
                <p className="text-xs sm:text-sm text-gray-500 mt-1">
                  {issue.category && (
                    <span className="inline-block bg-gray-100 px-2 py-0.5 rounded mr-2">
                      {issue.category}
                    </span>
                  )}
                  <span className="block sm:inline mt-1 sm:mt-0">
                    {formatFullDate(issue.firstSeenAt)} ~ {formatFullDate(issue.lastSeenAt)}
                    <span className="ml-2">({issue.totalSnapshots}일간 추적)</span>
                  </span>
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
                </button>
              ))}
            </div>
          )}

          {/* 선택된 날짜 정보 */}
          {selectedDateData && (
            <div className="bg-white rounded-lg border border-gray-200 p-3 sm:p-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 sm:gap-0 mb-3 sm:mb-4">
                <h2 className="text-base sm:text-lg font-semibold">
                  {formatFullDate(selectedDateData.date)}
                </h2>
                <span className="text-xs sm:text-sm text-amber-600 font-medium">
                  기사 {selectedDateData.articleCount}개
                </span>
              </div>

              {/* 타임라인 */}
              <div className="mb-6">
                {/* 타임라인 헤더 */}
                <div className="flex items-center gap-2 mb-4 overflow-x-auto pb-2">
                  {selectedDateData.snapshots.map((snapshot, idx) => (
                    <div key={snapshot.id} className="flex items-center">
                      {/* 점 */}
                      <div className="w-2 h-2 rounded-full bg-gray-400 shrink-0" />
                      {/* 시간 */}
                      <span className="text-xs font-medium text-gray-600 ml-1 mr-1 whitespace-nowrap">
                        {formatTime(snapshot.createdAt)}
                      </span>
                      {/* 연결선 (마지막 제외) */}
                      {idx < selectedDateData.snapshots.length - 1 && (
                        <div className="w-8 h-px bg-gray-300" />
                      )}
                    </div>
                  ))}
                </div>

                {/* 스냅샷 내용 */}
                <div className="space-y-6">
                  {selectedDateData.snapshots.map((snapshot, idx) => (
                    <div key={snapshot.id}>
                      {/* 시간 라벨 */}
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs font-medium text-white bg-gray-500 px-2 py-0.5 rounded">
                          {formatTime(snapshot.createdAt)}
                        </span>
                        {idx === selectedDateData.snapshots.length - 1 && (
                          <span className="text-[10px] text-amber-600 font-medium">최신</span>
                        )}
                      </div>
                      {/* 요약 */}
                      {snapshot.summary && (
                        <p className="text-sm sm:text-base text-gray-700 mb-3">
                          {snapshot.summary}
                        </p>
                      )}
                      {/* 콘텐츠 (최신 스냅샷에만 표시) */}
                      {idx === selectedDateData.snapshots.length - 1 && snapshot.contents?.length > 0 && (
                        <div className="space-y-3">
                          {snapshot.contents.map((content) => (
                            <div
                              key={content.id}
                              className="p-3 sm:p-4 bg-amber-50 border border-amber-200 rounded-lg"
                            >
                              <div className="flex items-center gap-2 mb-2">
                                <h4 className="font-semibold text-gray-900 text-sm sm:text-base">
                                  {content.title}
                                </h4>
                                {content.verified && (
                                  <span className="text-[10px] sm:text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full">
                                    검증됨
                                  </span>
                                )}
                              </div>
                              <div className="prose prose-sm prose-gray max-w-none overflow-x-auto prose-table:w-full prose-table:border-collapse prose-th:border prose-th:border-gray-300 prose-th:bg-gray-100 prose-th:p-2 prose-td:border prose-td:border-gray-300 prose-td:p-2">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{content.content}</ReactMarkdown>
                              </div>
                              <div className="mt-2 text-[10px] sm:text-xs text-gray-500">
                                신뢰도: {Math.round(content.confidenceScore * 100)}%
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                      {/* 구분선 */}
                      {idx < selectedDateData.snapshots.length - 1 && (
                        <hr className="mt-6 border-gray-200" />
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* 비로그인 CTA */}
              {!isLoggedIn && (
                <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-lg p-4 sm:p-5 mb-4 sm:mb-6">
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

              {/* 기사 목록 */}
              <div className="space-y-2 sm:space-y-3">
                <h3 className="text-xs sm:text-sm font-medium text-gray-700">📰 관련 기사</h3>
                {selectedDateData.articles.map((article) => (
                  <ArticleCard key={article.id} article={article} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </LoadingFallback>
  );
}
