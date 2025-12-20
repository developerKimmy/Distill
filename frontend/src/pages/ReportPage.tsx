import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getDailyReport } from '../api/issues';

export default function ReportPage() {
  const { date } = useParams<{ date: string }>();

  const { data: report, isLoading, error } = useQuery({
    queryKey: ['dailyReport', date],
    queryFn: () => getDailyReport(date!),
    enabled: !!date,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-gray-500">로딩 중...</p>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-gray-500">리포트를 불러올 수 없습니다.</p>
      </div>
    );
  }

  // 카테고리별 그룹핑
  const groupedByCategory = report.snapshots.reduce((acc, snapshot) => {
    const category = snapshot.issue.category || '기타';
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(snapshot);
    return acc;
  }, {} as Record<string, typeof report.snapshots>);

  // 기사 수 기준 정렬
  Object.keys(groupedByCategory).forEach((category) => {
    groupedByCategory[category].sort((a, b) => b.articleCount - a.articleCount);
  });

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`;
  };

  return (
    <div className="space-y-6">
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
        <p className="text-sm text-gray-500">
          총 {report.snapshots.length}개 이슈
        </p>
      </div>

      {/* 카테고리별 이슈 */}
      {Object.entries(groupedByCategory).map(([category, snapshots]) => (
        <div key={category} className="space-y-3">
          <h2 className="text-lg font-semibold text-gray-800">
            {category}
            <span className="ml-2 text-sm font-normal text-gray-500">
              ({snapshots.length})
            </span>
          </h2>

          <div className="space-y-2">
            {snapshots.map((snapshot) => (
              <Link
                key={snapshot.id}
                to={`/issues/${snapshot.issue.id}`}
                className="block bg-white rounded-lg border border-gray-200 p-4 hover:border-blue-300 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="font-medium text-gray-900">
                      {snapshot.issue.name}
                    </h3>
                    {snapshot.summary && (
                      <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                        {snapshot.summary}
                      </p>
                    )}
                  </div>
                  <div className="ml-4 text-right">
                    <p className="text-sm font-medium text-blue-600">
                      기사 {snapshot.articleCount}개
                    </p>
                    {snapshot.issue.totalSnapshots > 1 && (
                      <p className="text-xs text-gray-500 mt-1">
                        {snapshot.issue.totalSnapshots}일째 지속
                      </p>
                    )}
                  </div>
                </div>

                {/* 감성 점수 바 */}
                {snapshot.sentimentScore !== null && (
                  <div className="mt-3">
                    <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                      <span>부정</span>
                      <span>긍정</span>
                    </div>
                    <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-red-400 via-yellow-400 to-green-400"
                        style={{
                          width: `${((snapshot.sentimentScore + 1) / 2) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                )}
              </Link>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}