import { useState, useMemo, memo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import { getIssue } from '../api/issues';
import { LoadingFallback, SentimentBar, FollowButton } from '../components/common';
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
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string | null>(null);

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

  const sortedSnapshots = useMemo(() => {
    if (!issue?.snapshots) return [];
    return [...issue.snapshots].sort(
      (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
    );
  }, [issue?.snapshots]);

  const maxArticleCount = useMemo(() => {
    if (sortedSnapshots.length === 0) return 1;
    return Math.max(...sortedSnapshots.map((s) => s.articleCount));
  }, [sortedSnapshots]);

  const selectedSnapshot = selectedSnapshotId
    ? sortedSnapshots.find((s) => s.id === selectedSnapshotId) || sortedSnapshots[0]
    : sortedSnapshots[0];

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

          {/* 추이 그래프 */}
          <div className="bg-white rounded-lg border border-gray-200 p-3 sm:p-4">
            <h2 className="text-xs sm:text-sm font-medium text-gray-700 mb-3 sm:mb-4">
              기사량 추이
            </h2>
            <div className="flex items-end gap-1 sm:gap-2 h-24 sm:h-32 overflow-x-auto">
              {[...sortedSnapshots].reverse().map((snapshot) => {
                const height = (snapshot.articleCount / maxArticleCount) * 100;
                const isSelected = selectedSnapshot?.id === snapshot.id;

                return (
                  <button
                    key={snapshot.id}
                    onClick={() => setSelectedSnapshotId(snapshot.id)}
                    className="flex-1 min-w-[28px] sm:min-w-[36px] flex flex-col items-center gap-1 group"
                  >
                    <div
                      className={`w-full rounded-t transition-colors ${
                        isSelected ? 'bg-amber-500' : 'bg-gray-300 group-hover:bg-gray-400'
                      }`}
                      style={{ height: `${height}%`, minHeight: '4px' }}
                    />
                    <span className="text-[10px] sm:text-xs text-gray-500">
                      {formatShortDate(snapshot.date)}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 선택된 날짜 정보 */}
          {selectedSnapshot && (
            <div className="bg-white rounded-lg border border-gray-200 p-3 sm:p-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 sm:gap-0 mb-3 sm:mb-4">
                <h2 className="text-base sm:text-lg font-semibold">
                  {formatFullDate(selectedSnapshot.date)}
                </h2>
                <span className="text-xs sm:text-sm text-amber-600 font-medium">
                  기사 {selectedSnapshot.articleCount}개
                </span>
              </div>

              {selectedSnapshot.summary && (
                <p className="text-sm sm:text-base text-gray-700 mb-3 sm:mb-4">
                  {selectedSnapshot.summary}
                </p>
              )}

              {selectedSnapshot.sentimentScore !== null && (
                <SentimentBar score={selectedSnapshot.sentimentScore} />
              )}

              {/* 생성된 콘텐츠 */}
              {selectedSnapshot.contents?.length > 0 && (
                <div className="space-y-4 mb-6">
                  <h3 className="text-sm font-medium text-gray-700 flex items-center gap-2">
                    📝 생성된 콘텐츠
                    {selectedSnapshot.contents[0].verified && (
                      <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                        검증됨
                      </span>
                    )}
                  </h3>
                  {selectedSnapshot.contents.map((content) => (
                    <div
                      key={content.id}
                      className="p-4 bg-amber-50 border border-amber-200 rounded-lg"
                    >
                      <h4 className="font-semibold text-gray-900 mb-2">{content.title}</h4>
                      <div className="prose prose-sm prose-gray max-w-none">
                        <ReactMarkdown>{content.content}</ReactMarkdown>
                      </div>
                      <div className="mt-3 text-xs text-gray-500">
                        신뢰도: {Math.round(content.confidenceScore * 100)}%
                      </div>
                    </div>
                  ))}
                </div>
              )}

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
                {selectedSnapshot.articles.map((article) => (
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
