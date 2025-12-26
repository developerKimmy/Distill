import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  format,
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  addDays,
  addMonths,
  subMonths,
  isSameMonth,
  isSameDay,
  isBefore,
  isAfter,
  startOfDay,
  max,
  min,
} from 'date-fns';
import { ko } from 'date-fns/locale';
import { getGlobalBatchStatus } from '../api/batch';
import { getIssuesForCalendar, getBatchDates, type CalendarIssue } from '../api/issues';

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

const CATEGORY_COLORS: Record<string, { bg: string; text: string }> = {
  정치: { bg: 'bg-rose-600', text: 'text-white' },
  경제: { bg: 'bg-amber-500', text: 'text-white' },
  사회: { bg: 'bg-teal-500', text: 'text-white' },
  세계: { bg: 'bg-blue-500', text: 'text-white' },
  연예: { bg: 'bg-pink-500', text: 'text-white' },
  'IT/과학': { bg: 'bg-violet-600', text: 'text-white' },
};

interface WeekIssue {
  issue: CalendarIssue;
  startCol: number; // 0-6
  endCol: number; // 0-6
  row: number;
  isStart: boolean; // 이번 주에서 시작하는지
  isEnd: boolean; // 이번 주에서 끝나는지
}

export default function CalendarPage() {
  const navigate = useNavigate();
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const today = startOfDay(new Date());

  const { data: batchStatus } = useQuery({
    queryKey: ['globalBatchStatus'],
    queryFn: getGlobalBatchStatus,
  });

  const { data: issues } = useQuery({
    queryKey: ['issues-calendar'],
    queryFn: getIssuesForCalendar,
  });

  const { data: batchDates } = useQuery({
    queryKey: ['batchDates', currentMonth.getFullYear(), currentMonth.getMonth() + 1],
    queryFn: () => getBatchDates(currentMonth.getFullYear(), currentMonth.getMonth() + 1),
  });

  const activeDates = useMemo(() => {
    if (!batchDates) return new Set<string>();
    return new Set(batchDates);
  }, [batchDates]);

  // 주 단위로 캘린더 생성
  const weeks = useMemo(() => {
    const monthStart = startOfMonth(currentMonth);
    const monthEnd = endOfMonth(currentMonth);
    const calStart = startOfWeek(monthStart, { weekStartsOn: 0 });
    const calEnd = endOfWeek(monthEnd, { weekStartsOn: 0 });

    const result: Date[][] = [];
    let day = calStart;
    let week: Date[] = [];

    while (day <= calEnd) {
      week.push(day);
      if (week.length === 7) {
        result.push(week);
        week = [];
      }
      day = addDays(day, 1);
    }

    return result;
  }, [currentMonth]);

  // 주별 이슈 배치 계산
  const getWeekIssues = (weekDays: Date[]): WeekIssue[] => {
    if (!issues) return [];

    const weekStart = weekDays[0];
    const weekEnd = weekDays[6];
    const result: WeekIssue[] = [];
    const rows: boolean[][] = []; // 각 row의 column 사용 여부

    // 이 주에 해당하는 이슈 필터링
    const weekIssues = issues.filter((issue) => {
      const issueStart = startOfDay(new Date(issue.firstSeenAt));
      const issueEnd = startOfDay(new Date(issue.lastSeenAt));
      return !isAfter(issueStart, weekEnd) && !isBefore(issueEnd, weekStart);
    });

    // 시작일 기준 정렬 (더 긴 이슈 우선)
    weekIssues.sort((a, b) => {
      const aStart = new Date(a.firstSeenAt);
      const bStart = new Date(b.firstSeenAt);
      const aDuration = new Date(a.lastSeenAt).getTime() - aStart.getTime();
      const bDuration = new Date(b.lastSeenAt).getTime() - bStart.getTime();
      if (aStart.getTime() !== bStart.getTime()) {
        return aStart.getTime() - bStart.getTime();
      }
      return bDuration - aDuration;
    });

    weekIssues.forEach((issue) => {
      const issueStart = startOfDay(new Date(issue.firstSeenAt));
      const issueEnd = startOfDay(new Date(issue.lastSeenAt));

      // 이 주에서의 시작/끝 column 계산
      const visibleStart = max([issueStart, weekStart]);
      const visibleEnd = min([issueEnd, weekEnd]);

      const startCol = Math.floor(
        (visibleStart.getTime() - weekStart.getTime()) / (1000 * 60 * 60 * 24)
      );
      const endCol = Math.floor(
        (visibleEnd.getTime() - weekStart.getTime()) / (1000 * 60 * 60 * 24)
      );

      // 빈 row 찾기
      let rowIndex = 0;
      while (true) {
        if (!rows[rowIndex]) {
          rows[rowIndex] = Array(7).fill(false);
        }
        let canFit = true;
        for (let c = startCol; c <= endCol; c++) {
          if (rows[rowIndex][c]) {
            canFit = false;
            break;
          }
        }
        if (canFit) {
          for (let c = startCol; c <= endCol; c++) {
            rows[rowIndex][c] = true;
          }
          break;
        }
        rowIndex++;
        if (rowIndex > 10) break; // 안전장치
      }

      result.push({
        issue,
        startCol,
        endCol,
        row: rowIndex,
        isStart: isSameDay(issueStart, visibleStart),
        isEnd: isSameDay(issueEnd, visibleEnd),
      });
    });

    return result;
  };

  const handleDateClick = (date: Date) => {
    const dateStr = format(date, 'yyyy-MM-dd');
    const isPast = isBefore(startOfDay(date), today);
    const hasIssues = activeDates.has(dateStr);
    if (!isPast || hasIssues) {
      navigate(`/report/${dateStr}`);
    }
  };

  const handleIssueClick = (e: React.MouseEvent, issueId: string) => {
    e.stopPropagation();
    navigate(`/issues/${issueId}`);
  };

  const isDisabled = (date: Date) => {
    const dateStr = format(date, 'yyyy-MM-dd');
    const isPast = isBefore(startOfDay(date), today);
    return isPast && !activeDates.has(dateStr);
  };

  return (
    <div className="max-w-5xl mx-auto">
      {/* 배치 상태 */}
      <div className="mb-6 flex items-center justify-between text-sm text-gray-500">
        <span>
          마지막 수집:{' '}
          {batchStatus?.lastRunAt
            ? new Date(batchStatus.lastRunAt).toLocaleString('ko-KR')
            : '-'}
        </span>
        <span>다음 수집: {batchStatus?.schedule.join(', ')}</span>
      </div>

      {/* 캘린더 */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        {/* 헤더 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <button
            onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}
            className="p-2 hover:bg-gray-100 rounded transition-colors"
          >
            <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <h2 className="text-lg font-semibold text-gray-900">
            {format(currentMonth, 'yyyy년 M월', { locale: ko })}
          </h2>
          <button
            onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
            className="p-2 hover:bg-gray-100 rounded transition-colors"
          >
            <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>

        {/* 요일 헤더 */}
        <div className="grid grid-cols-7 border-b border-gray-200">
          {WEEKDAYS.map((day, i) => (
            <div
              key={day}
              className={`py-3 text-center text-sm font-medium ${
                i === 0 ? 'text-red-500' : i === 6 ? 'text-blue-500' : 'text-gray-700'
              }`}
            >
              {day}
            </div>
          ))}
        </div>

        {/* 주별 렌더링 */}
        {weeks.map((weekDays, weekIdx) => {
          const weekIssues = getWeekIssues(weekDays);
          const issueRowHeight = 22;
          const maxVisibleRows = 3; // 최대 3개 행까지 표시

          return (
            <div key={weekIdx} className="relative h-[120px]">
              {/* 날짜 행 */}
              <div className="grid grid-cols-7 h-full">
                {weekDays.map((date, dayIdx) => {
                  const isCurrentMonth = isSameMonth(date, currentMonth);
                  const isToday = isSameDay(date, today);
                  const disabled = isDisabled(date);
                  const dayOfWeek = date.getDay();

                  return (
                    <div
                      key={dayIdx}
                      onClick={() => isCurrentMonth && !disabled && handleDateClick(date)}
                      className={`
                        border-b border-r border-gray-100 p-2 h-full
                        ${dayIdx === 6 ? 'border-r-0' : ''}
                        ${isCurrentMonth ? '' : 'bg-gray-50'}
                        ${disabled ? 'bg-gray-50 cursor-default' : 'cursor-pointer hover:bg-gray-50'}
                      `}
                    >
                      <div className="flex justify-end">
                        <span
                          className={`
                            inline-flex items-center justify-center w-7 h-7 text-sm
                            ${isToday ? 'bg-gray-900 text-white rounded-full font-semibold' : ''}
                            ${!isToday && disabled ? 'text-gray-300' : ''}
                            ${!isToday && !disabled && isCurrentMonth && dayOfWeek === 0 ? 'text-red-500' : ''}
                            ${!isToday && !disabled && isCurrentMonth && dayOfWeek === 6 ? 'text-blue-500' : ''}
                            ${!isToday && !disabled && isCurrentMonth && dayOfWeek !== 0 && dayOfWeek !== 6 ? 'text-gray-900' : ''}
                            ${!isCurrentMonth ? 'text-gray-300' : ''}
                          `}
                        >
                          {format(date, 'd')}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* 이슈 바 (절대 위치) */}
              <div
                className="absolute left-0 right-0 pointer-events-none overflow-hidden"
                style={{ top: '36px', height: `${maxVisibleRows * issueRowHeight}px` }}
              >
                {weekIssues
                  .filter((wi) => wi.row < maxVisibleRows)
                  .map((wi, idx) => {
                    const colors = CATEGORY_COLORS[wi.issue.category || ''] || {
                      bg: 'bg-gray-500',
                      text: 'text-white',
                    };
                    const leftPercent = (wi.startCol / 7) * 100;
                    const widthPercent = ((wi.endCol - wi.startCol + 1) / 7) * 100;

                    return (
                      <div
                        key={`${wi.issue.id}-${idx}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleIssueClick(e, wi.issue.id);
                        }}
                        className={`
                          absolute pointer-events-auto cursor-pointer
                          ${colors.bg} ${colors.text}
                          text-xs truncate px-2 py-0.5
                          hover:opacity-80 transition-opacity
                          ${wi.isStart ? 'rounded-l' : ''}
                          ${wi.isEnd ? 'rounded-r' : ''}
                        `}
                        style={{
                          left: `calc(${leftPercent}% + 4px)`,
                          width: `calc(${widthPercent}% - 8px)`,
                          top: `${wi.row * issueRowHeight}px`,
                          height: '20px',
                          lineHeight: '20px',
                        }}
                        title={wi.issue.name}
                      >
                        {wi.isStart && wi.issue.name}
                      </div>
                    );
                  })}
              </div>
            </div>
          );
        })}
      </div>

    </div>
  );
}
