import { useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getIssues, followIssue, unfollowIssue } from '../api/issues';
import { isLoggedIn } from '../utils/categories';
import type { Issue } from '../types';

export default function IssueListPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const loggedIn = isLoggedIn();

  const { data, isLoading, error } = useQuery({
    queryKey: ['issues', 1, 100],
    queryFn: () => getIssues(1, 100),
  });

  const followMutation = useMutation({
    mutationFn: (issueId: string) => followIssue(issueId),
    onMutate: async (issueId) => {
      await queryClient.cancelQueries({ queryKey: ['issues', 1, 100] });
      const previous = queryClient.getQueryData(['issues', 1, 100]);
      queryClient.setQueryData(['issues', 1, 100], (old: any) => ({
        ...old,
        items: old?.items?.map((issue: Issue) =>
          issue.id === issueId ? { ...issue, isFollowing: true } : issue
        ),
      }));
      return { previous };
    },
    onError: (_err, _issueId, context) => {
      queryClient.setQueryData(['issues', 1, 100], context?.previous);
    },
  });

  const unfollowMutation = useMutation({
    mutationFn: (issueId: string) => unfollowIssue(issueId),
    onMutate: async (issueId) => {
      await queryClient.cancelQueries({ queryKey: ['issues', 1, 100] });
      const previous = queryClient.getQueryData(['issues', 1, 100]);
      queryClient.setQueryData(['issues', 1, 100], (old: any) => ({
        ...old,
        items: old?.items?.map((issue: Issue) =>
          issue.id === issueId ? { ...issue, isFollowing: false } : issue
        ),
      }));
      return { previous };
    },
    onError: (_err, _issueId, context) => {
      queryClient.setQueryData(['issues', 1, 100], context?.previous);
    },
  });

  const handleFollowClick = (e: React.MouseEvent, issue: Issue) => {
    e.preventDefault();
    e.stopPropagation();

    if (!loggedIn) {
      navigate('/register');
      return;
    }

    if (issue.isFollowing) {
      unfollowMutation.mutate(issue.id);
    } else {
      followMutation.mutate(issue.id);
    }
  };

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

  const categoryColors: Record<string, { badge: string; dot: string }> = {
    정치: { badge: 'bg-rose-100 text-rose-800', dot: 'bg-rose-600' },
    경제: { badge: 'bg-amber-100 text-amber-800', dot: 'bg-amber-500' },
    사회: { badge: 'bg-teal-100 text-teal-800', dot: 'bg-teal-500' },
    세계: { badge: 'bg-blue-100 text-blue-800', dot: 'bg-blue-500' },
    연예: { badge: 'bg-pink-100 text-pink-800', dot: 'bg-pink-500' },
    'IT/과학': { badge: 'bg-violet-100 text-violet-800', dot: 'bg-violet-600' },
    기타: { badge: 'bg-gray-100 text-gray-800', dot: 'bg-gray-500' },
  };

  const renderIssueCard = (issue: Issue) => (
    <Link
      key={issue.id}
      to={`/issues/${issue.id}`}
      className="block bg-white rounded-lg border border-gray-200 p-4 hover:border-amber-300 transition-colors"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-gray-900 truncate">{issue.name}</h3>
          <p className="text-sm text-gray-500 mt-1">
            {formatDate(issue.firstSeenAt)} ~ {formatDate(issue.lastSeenAt)}
            <span className="ml-2">({issue.totalSnapshots}일)</span>
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {issue.latestArticleCount && (
            <span className="text-sm text-amber-600 font-medium whitespace-nowrap">
              기사 {issue.latestArticleCount}개
            </span>
          )}
          <button
            onClick={(e) => handleFollowClick(e, issue)}
            className={`
              p-1.5 rounded-full transition-colors
              ${issue.isFollowing
                ? 'bg-amber-100 text-amber-600 hover:bg-amber-200'
                : 'bg-gray-100 text-gray-400 hover:bg-gray-200 hover:text-gray-600'
              }
            `}
            title={issue.isFollowing ? '팔로우 중' : '팔로우'}
          >
            <svg className="w-4 h-4" fill={issue.isFollowing ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
          </button>
        </div>
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
                  (categoryColors[category] || categoryColors['기타']).badge
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

      {/* 카테고리 범례 */}
      <div className="flex items-center gap-5 text-sm text-gray-600">
        {Object.entries(categoryColors)
          .filter(([key]) => key !== '기타')
          .map(([category, colors]) => (
            <span key={category} className="flex items-center gap-1.5">
              <span className={`w-2.5 h-2.5 rounded-sm ${colors.dot}`}></span>
              {category}
            </span>
          ))}
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
