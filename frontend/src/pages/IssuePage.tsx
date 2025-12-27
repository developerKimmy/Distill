import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import { getIssue, followIssue, unfollowIssue } from '../api/issues';
import { isLoggedIn } from '../utils/categories';

export default function IssuePage() {
  const { issueId } = useParams<{ issueId: string }>();
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const loggedIn = isLoggedIn();

  const { data: issue, isLoading, error } = useQuery({
    queryKey: ['issue', issueId],
    queryFn: () => getIssue(issueId!),
    enabled: !!issueId,
  });

  const followMutation = useMutation({
    mutationFn: () => followIssue(issueId!),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ['issue', issueId] });
      const previous = queryClient.getQueryData(['issue', issueId]);
      queryClient.setQueryData(['issue', issueId], (old: any) => ({
        ...old,
        isFollowing: true,
      }));
      return { previous };
    },
    onError: (_err, _vars, context) => {
      queryClient.setQueryData(['issue', issueId], context?.previous);
    },
  });

  const unfollowMutation = useMutation({
    mutationFn: () => unfollowIssue(issueId!),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ['issue', issueId] });
      const previous = queryClient.getQueryData(['issue', issueId]);
      queryClient.setQueryData(['issue', issueId], (old: any) => ({
        ...old,
        isFollowing: false,
      }));
      return { previous };
    },
    onError: (_err, _vars, context) => {
      queryClient.setQueryData(['issue', issueId], context?.previous);
    },
  });

  const handleFollowToggle = () => {
    if (!loggedIn) {
      navigate('/register');
      return;
    }
    if (issue?.isFollowing) {
      unfollowMutation.mutate();
    } else {
      followMutation.mutate();
    }
  };

  const isFollowLoading = followMutation.isPending || unfollowMutation.isPending;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-gray-500">로딩 중...</p>
      </div>
    );
  }

  if (error || !issue) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-gray-500">이슈를 불러올 수 없습니다.</p>
      </div>
    );
  }

  // 최신 스냅샷이 기본 선택
  const sortedSnapshots = [...issue.snapshots].sort(
    (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
  );

  const selectedSnapshot = selectedSnapshotId
    ? sortedSnapshots.find((s) => s.id === selectedSnapshotId)
    : sortedSnapshots[0];

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return `${d.getMonth() + 1}/${d.getDate()}`;
  };

  const formatFullDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`;
  };

  // 기사 수 최대값 (그래프용)
  const maxArticleCount = Math.max(...sortedSnapshots.map((s) => s.articleCount));

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div>
        <Link to="/" className="text-sm text-gray-500 hover:text-gray-700">
          ← 돌아가기
        </Link>
        <div className="flex items-start justify-between mt-1">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{issue.name}</h1>
            <p className="text-sm text-gray-500 mt-1">
              {issue.category && (
                <span className="inline-block bg-gray-100 px-2 py-0.5 rounded mr-2">
                  {issue.category}
                </span>
              )}
              {formatFullDate(issue.firstSeenAt)} ~ {formatFullDate(issue.lastSeenAt)}
              <span className="ml-2">({issue.totalSnapshots}일간 추적)</span>
            </p>
          </div>
          {/* 팔로우 버튼 */}
          <button
            onClick={handleFollowToggle}
            disabled={isFollowLoading}
            className={`
              shrink-0 flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors
              ${issue.isFollowing
                ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                : 'bg-amber-500 text-white hover:bg-amber-600'
              }
              disabled:opacity-50
            `}
          >
            {issue.isFollowing ? (
              <>
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/>
                </svg>
                팔로우 중
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
                팔로우
              </>
            )}
          </button>
        </div>
      </div>

      {/* 추이 그래프 */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h2 className="text-sm font-medium text-gray-700 mb-4">기사량 추이</h2>
        <div className="flex items-end gap-2 h-32">
          {[...sortedSnapshots].reverse().map((snapshot) => (
            <button
              key={snapshot.id}
              onClick={() => setSelectedSnapshotId(snapshot.id)}
              className={`flex-1 flex flex-col items-center gap-1 group`}
            >
              <div
                className={`w-full rounded-t transition-colors ${
                  selectedSnapshot?.id === snapshot.id
                    ? 'bg-amber-500'
                    : 'bg-gray-300 group-hover:bg-gray-400'
                }`}
                style={{
                  height: `${(snapshot.articleCount / maxArticleCount) * 100}%`,
                  minHeight: '4px',
                }}
              />
              <span className="text-xs text-gray-500">{formatDate(snapshot.date)}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 선택된 날짜 정보 */}
      {selectedSnapshot && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">
              {formatFullDate(selectedSnapshot.date)}
            </h2>
            <span className="text-sm text-amber-600 font-medium">
              기사 {selectedSnapshot.articleCount}개
            </span>
          </div>

          {selectedSnapshot.summary && (
            <p className="text-gray-700 mb-4">{selectedSnapshot.summary}</p>
          )}

          {/* 감성 점수 */}
          {selectedSnapshot.sentimentScore !== null && (
            <div className="mb-4">
              <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                <span>부정</span>
                <span>중립</span>
                <span>긍정</span>
              </div>
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-red-400 via-yellow-400 to-green-400"
                  style={{
                    width: `${((selectedSnapshot.sentimentScore + 1) / 2) * 100}%`,
                  }}
                />
              </div>
            </div>
          )}

          {/* 생성된 콘텐츠 */}
          {selectedSnapshot.contents && selectedSnapshot.contents.length > 0 && (
            <div className="space-y-4 mb-6">
              <h3 className="text-sm font-medium text-gray-700 flex items-center gap-2">
                📝 생성된 콘텐츠
                {selectedSnapshot.contents[0].verified && (
                  <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                    검증됨
                  </span>
                )}
              </h3>
              {selectedSnapshot.contents.map((content) => {
                // 디버깅: 콘텐츠 확인
                console.log('Content raw:', JSON.stringify(content.content.slice(0, 200)));
                return (
                  <div
                    key={content.id}
                    className="p-4 bg-amber-50 border border-amber-200 rounded-lg"
                  >
                    <h4 className="font-semibold text-gray-900 mb-2">
                      {content.title}
                    </h4>
                    <div className="prose prose-sm prose-gray max-w-none prose-headings:text-gray-900 prose-headings:font-bold prose-h1:text-xl prose-h2:text-lg prose-h2:mt-6 prose-h2:mb-3 prose-p:text-gray-700 prose-blockquote:border-amber-400 prose-blockquote:bg-amber-50 prose-blockquote:py-1 prose-strong:text-gray-900">
                      <ReactMarkdown>{content.content}</ReactMarkdown>
                    </div>
                    <div className="mt-3 flex items-center gap-4 text-xs text-gray-500">
                      <span>신뢰도: {Math.round(content.confidenceScore * 100)}%</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* 비로그인 사용자 CTA */}
          {!isLoggedIn() && (
            <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-lg p-5 mb-6">
              <div className="flex items-center gap-4">
                <div className="text-2xl">📬</div>
                <div className="flex-1">
                  <h3 className="font-medium text-gray-900 text-sm">
                    이 이슈의 업데이트를 이메일로 받아보세요
                  </h3>
                  <p className="text-xs text-gray-500 mt-0.5">
                    관심 이슈를 팔로우하고 새 소식을 받아볼 수 있어요.
                  </p>
                </div>
                <Link
                  to="/register"
                  className="shrink-0 bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
                >
                  시작하기
                </Link>
              </div>
            </div>
          )}

          {/* 기사 목록 */}
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-gray-700">📰 관련 기사</h3>
            {selectedSnapshot.articles.map((article) => (
              <a
                key={article.id}
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <p className="font-medium text-gray-900 line-clamp-1">
                  {article.title}
                </p>
                {article.description && (
                  <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                    {article.description}
                  </p>
                )}
                <p className="text-xs text-gray-400 mt-2">
                  {article.press}
                  {article.publishedAt && ` · ${formatFullDate(article.publishedAt)}`}
                </p>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}