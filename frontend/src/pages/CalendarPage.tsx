import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Calendar, dateFnsLocalizer, type View } from 'react-big-calendar';
import { format, parse, startOfWeek, getDay } from 'date-fns';
import { ko } from 'date-fns/locale';
import { getGlobalBatchStatus } from '../api/batch';
import { getIssues } from '../api/issues';

import 'react-big-calendar/lib/css/react-big-calendar.css';

// date-fns 로컬라이저 설정
const locales = { ko };
const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: () => startOfWeek(new Date(), { weekStartsOn: 0 }),
  getDay,
  locales,
});

// 이벤트 타입
interface CalendarEvent {
  id: string;
  title: string;
  start: Date;
  end: Date;
  resource: {
    issueId: string;
    articleCount: number;
    category: string | null;
  };
}

export default function CalendarPage() {
  const navigate = useNavigate();

  // 글로벌 배치 상태
  const { data: batchStatus } = useQuery({
    queryKey: ['globalBatchStatus'],
    queryFn: getGlobalBatchStatus,
  });

  // 이슈 목록 (전체)
  const { data: issuesData } = useQuery({
    queryKey: ['issues'],
    queryFn: () => getIssues(1, 100),
  });

  // 이슈를 캘린더 이벤트로 변환
  const events: CalendarEvent[] = useMemo(() => {
    if (!issuesData?.items) return [];

    return issuesData.items.map((issue) => ({
      id: issue.id,
      title: `${issue.name} (${issue.totalSnapshots}일)`,
      start: new Date(issue.firstSeenAt),
      end: new Date(issue.lastSeenAt),
      resource: {
        issueId: issue.id,
        articleCount: issue.totalSnapshots,
        category: issue.category,
      },
    }));
  }, [issuesData]);

  // 이벤트 클릭
  const handleSelectEvent = (event: CalendarEvent) => {
    navigate(`/issues/${event.resource.issueId}`);
  };

  // 날짜 클릭
  const handleSelectSlot = ({ start }: { start: Date }) => {
    const dateStr = format(start, 'yyyy-MM-dd');
    navigate(`/report/${dateStr}`);
  };

  // 이벤트 스타일
  const eventStyleGetter = (event: CalendarEvent) => {
    const categoryColors: Record<string, string> = {
      정치: '#ef4444',
      경제: '#f59e0b',
      사회: '#10b981',
      IT: '#3b82f6',
      문화: '#8b5cf6',
    };

    const backgroundColor = event.resource.category
      ? categoryColors[event.resource.category] || '#6b7280'
      : '#6b7280';

    return {
      style: {
        backgroundColor,
        borderRadius: '4px',
        opacity: 0.9,
        color: 'white',
        border: 'none',
        fontSize: '12px',
      },
    };
  };

  // 메시지 한글화
  const messages = {
    today: '오늘',
    previous: '이전',
    next: '다음',
    month: '월',
    week: '주',
    day: '일',
    agenda: '일정',
    date: '날짜',
    time: '시간',
    event: '이벤트',
    noEventsInRange: '이 기간에 이슈가 없습니다.',
  };

  return (
    <div className="space-y-6">
      {/* 배치 상태 (read-only) */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex items-center justify-between text-sm text-gray-600">
          <span>
            마지막 수집:{' '}
            {batchStatus?.lastRunAt
              ? new Date(batchStatus.lastRunAt).toLocaleString('ko-KR')
              : '없음'}
          </span>
          <span>
            다음 수집: {batchStatus?.schedule.join(', ')}
          </span>
        </div>
      </div>

      {/* 캘린더 */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <Calendar
          localizer={localizer}
          events={events}
          startAccessor="start"
          endAccessor="end"
          style={{ height: 600 }}
          onSelectEvent={handleSelectEvent}
          onSelectSlot={handleSelectSlot}
          selectable
          eventPropGetter={eventStyleGetter}
          messages={messages}
          defaultView={'month' as View}
          views={['month'] as View[]}
          formats={{
            monthHeaderFormat: (date: Date) => format(date, 'yyyy년 M월', { locale: ko }),
            weekdayFormat: (date: Date) => format(date, 'EEE', { locale: ko }),
          }}
        />
      </div>

      {/* 범례 */}
      <div className="flex flex-wrap items-center gap-4 text-sm">
        <span className="text-gray-600">카테고리:</span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 bg-red-500 rounded"></span> 정치
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 bg-amber-500 rounded"></span> 경제
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 bg-emerald-500 rounded"></span> 사회
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 bg-sky-500 rounded"></span> IT
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 bg-violet-500 rounded"></span> 문화
        </span>
      </div>
    </div>
  );
}
