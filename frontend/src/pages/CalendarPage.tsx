import { useMemo, useState, memo } from 'react';
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
import { getIssuesForCalendar, getBatchDates, type CalendarIssue } from '../api/issues';
import { WEEKDAYS, getCategoryColors } from '../utils/constants';
import { parseLocalDate } from '../utils/dateFormat';
import { getStoredCategories } from '../utils/categories';
import { LoadingOverlay } from '../components/common';

interface WeekIssue {
  issue: CalendarIssue;
  startCol: number;
  endCol: number;
  row: number;
  isStart: boolean;
  isEnd: boolean;
}

// memo for list items in calendar grid
const IssueBar = memo(function IssueBar({
  weekIssue,
  issueRowHeight,
  onClick,
}: {
  weekIssue: WeekIssue;
  issueRowHeight: number;
  onClick: () => void;
}) {
  const { issue, startCol, endCol, row, isStart, isEnd } = weekIssue;
  const colors = getCategoryColors(issue.category);
  const leftPercent = (startCol / 7) * 100;
  const widthPercent = ((endCol - startCol + 1) / 7) * 100;

  return (
    <div
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={`
        absolute pointer-events-auto cursor-pointer
        ${colors.bg} ${colors.text}
        text-[10px] sm:text-xs truncate px-1 sm:px-2 py-0.5
        hover:opacity-80 transition-opacity
        ${isStart ? 'rounded-l' : ''}
        ${isEnd ? 'rounded-r' : ''}
      `}
      style={{
        left: `calc(${leftPercent}% + 2px)`,
        width: `calc(${widthPercent}% - 4px)`,
        top: `${row * issueRowHeight}px`,
        height: '16px',
        lineHeight: '16px',
      }}
      title={issue.name}
    >
      {isStart && issue.name}
    </div>
  );
});

// 이슈의 달력 시작 날짜 결정 (displayDate 우선, 없으면 firstSeenAt)
function getIssueStartDate(issue: CalendarIssue): string | null {
  return issue.displayDate || issue.firstSeenAt;
}

// Pure function for week issues calculation
function calculateWeekIssues(weekDays: Date[], issues: CalendarIssue[] | undefined): WeekIssue[] {
  if (!issues) return [];

  const weekStart = weekDays[0];
  const weekEnd = weekDays[6];
  const result: WeekIssue[] = [];
  const rows: boolean[][] = [];

  // 이슈 시작일 최소 기준: 12월 25일
  const minStartDate = new Date(2025, 11, 25); // 2025-12-25

  const weekIssues = issues.filter((issue) => {
    const startDateStr = getIssueStartDate(issue);
    if (!startDateStr || !issue.lastSeenAt) return false;
    const issueStart = max([startOfDay(parseLocalDate(startDateStr)), minStartDate]);
    const issueEnd = startOfDay(parseLocalDate(issue.lastSeenAt));
    return !isAfter(issueStart, weekEnd) && !isBefore(issueEnd, weekStart);
  });

  // 기사 수 내림차순 정렬, 같으면 시작일 오름차순
  weekIssues.sort((a, b) => {
    // 1차: 기사 수 내림차순
    if (b.articleCount !== a.articleCount) {
      return b.articleCount - a.articleCount;
    }
    // 2차: 시작일 오름차순
    const aStartStr = getIssueStartDate(a);
    const bStartStr = getIssueStartDate(b);
    if (!aStartStr || !bStartStr) return 0;
    const aStart = max([parseLocalDate(aStartStr), minStartDate]);
    const bStart = max([parseLocalDate(bStartStr), minStartDate]);
    return aStart.getTime() - bStart.getTime();
  });

  weekIssues.forEach((issue) => {
    const startDateStr = getIssueStartDate(issue);
    if (!startDateStr || !issue.lastSeenAt) return;
    const issueStart = max([startOfDay(parseLocalDate(startDateStr)), minStartDate]);
    const issueEnd = startOfDay(parseLocalDate(issue.lastSeenAt));
    const visibleStart = max([issueStart, weekStart]);
    const visibleEnd = min([issueEnd, weekEnd]);

    const startCol = Math.floor((visibleStart.getTime() - weekStart.getTime()) / (1000 * 60 * 60 * 24));
    const endCol = Math.floor((visibleEnd.getTime() - weekStart.getTime()) / (1000 * 60 * 60 * 24));

    let rowIndex = 0;
    while (rowIndex <= 10) {
      if (!rows[rowIndex]) rows[rowIndex] = Array(7).fill(false);
      const canFit = !rows[rowIndex].slice(startCol, endCol + 1).some(Boolean);
      if (canFit) {
        for (let c = startCol; c <= endCol; c++) rows[rowIndex][c] = true;
        break;
      }
      rowIndex++;
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
}

export default function CalendarPage() {
  const navigate = useNavigate();
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [morePopup, setMorePopup] = useState<{
    date: Date;
    issues: CalendarIssue[];
    position: { x: number; y: number };
  } | null>(null);

  const today = startOfDay(new Date());

  const categories = getStoredCategories();

  const { data: issues, isFetching: isIssuesFetching } = useQuery({
    queryKey: ['issues-calendar', categories],
    queryFn: getIssuesForCalendar,
  });

  const { data: batchDates, isFetching: isBatchFetching } = useQuery({
    queryKey: ['batchDates', currentMonth.getFullYear(), currentMonth.getMonth() + 1, categories],
    queryFn: () => getBatchDates(currentMonth.getFullYear(), currentMonth.getMonth() + 1),
  });

  const isLoading = isIssuesFetching || isBatchFetching;

  const activeDates = useMemo(() => new Set(batchDates || []), [batchDates]);

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

  const allWeekIssues = useMemo(
    () => weeks.map((weekDays) => calculateWeekIssues(weekDays, issues)),
    [weeks, issues]
  );

  const isDisabled = (date: Date) => {
    const dateStr = format(date, 'yyyy-MM-dd');
    return isBefore(startOfDay(date), today) && !activeDates.has(dateStr);
  };

  const issueRowHeight = 18;
  const maxVisibleRows = 2;

  return (
    <div className="max-w-5xl mx-auto">
      <LoadingOverlay isLoading={isLoading} />

      {/* 캘린더 */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        {/* 헤더 */}
        <div className="flex items-center justify-between px-3 sm:px-6 py-3 sm:py-4 border-b border-gray-200">
          <button
            onClick={() => setCurrentMonth((m) => subMonths(m, 1))}
            className="p-1.5 sm:p-2 hover:bg-gray-100 rounded transition-colors"
          >
            <svg className="w-4 h-4 sm:w-5 sm:h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <h2 className="text-base sm:text-lg font-semibold text-gray-900">
            {format(currentMonth, 'yyyy년 M월', { locale: ko })}
          </h2>
          <button
            onClick={() => setCurrentMonth((m) => addMonths(m, 1))}
            className="p-1.5 sm:p-2 hover:bg-gray-100 rounded transition-colors"
          >
            <svg className="w-4 h-4 sm:w-5 sm:h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>

        {/* 요일 헤더 */}
        <div className="grid grid-cols-7 border-b border-gray-200">
          {WEEKDAYS.map((day, i) => (
            <div
              key={day}
              className={`py-2 sm:py-3 text-center text-xs sm:text-sm font-medium ${
                i === 0 ? 'text-red-500' : i === 6 ? 'text-blue-500' : 'text-gray-700'
              }`}
            >
              {day}
            </div>
          ))}
        </div>

        {/* 주별 렌더링 */}
        {weeks.map((weekDays, weekIdx) => {
          const weekIssues = allWeekIssues[weekIdx];

          return (
            <div key={weekIdx} className="relative h-[80px] sm:h-[120px]">
              <div className="grid grid-cols-7 h-full">
                {weekDays.map((date, dayIdx) => {
                  const isCurrentMonth = isSameMonth(date, currentMonth);
                  const isToday = isSameDay(date, today);
                  const disabled = isDisabled(date);
                  const dayOfWeek = date.getDay();
                  const dateStr = format(date, 'yyyy-MM-dd');
                  // 해당 날짜에 실제 기사가 수집된 이슈 중 화면에 표시되지 않은 것만 카운트
                  const hiddenIssues = weekIssues
                    .filter((wi) =>
                      wi.startCol <= dayIdx &&
                      wi.endCol >= dayIdx &&
                      wi.row >= maxVisibleRows &&
                      wi.issue.collectedDates?.includes(dateStr)
                    )
                    .map((wi) => wi.issue);

                  return (
                    <div
                      key={dayIdx}
                      onClick={() => {
                        if (isCurrentMonth && !disabled) {
                          navigate(`/report/${format(date, 'yyyy-MM-dd')}`);
                        }
                      }}
                      className={`
                        relative border-b border-r border-gray-100 p-1 sm:p-2 h-full
                        ${dayIdx === 6 ? 'border-r-0' : ''}
                        ${isCurrentMonth ? '' : 'bg-gray-50'}
                        ${disabled ? 'bg-gray-50 cursor-default' : 'cursor-pointer hover:bg-gray-50'}
                      `}
                    >
                      <div className="flex items-start justify-between">
                        <span
                          className={`
                            inline-flex items-center justify-center w-5 h-5 sm:w-7 sm:h-7 text-xs sm:text-sm
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
                        {/* 브리핑 버튼 - 활성 날짜만 표시 */}
                        {isCurrentMonth && !disabled && activeDates.has(format(date, 'yyyy-MM-dd')) && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/digest/${format(date, 'yyyy-MM-dd')}`);
                            }}
                            className="w-4 h-4 sm:w-auto sm:h-auto sm:px-1 sm:py-0.5 flex items-center justify-center bg-amber-100 text-amber-700 rounded hover:bg-amber-200 transition-colors"
                            title="브리핑 보기"
                          >
                            <span className="hidden sm:inline text-[10px]">브리핑</span>
                            <svg className="w-2.5 h-2.5 sm:hidden" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                          </button>
                        )}
                      </div>
                      {hiddenIssues.length > 0 && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            const rect = e.currentTarget.getBoundingClientRect();
                            setMorePopup({ date, issues: hiddenIssues, position: { x: rect.left, y: rect.bottom + 4 } });
                          }}
                          className="absolute bottom-0.5 sm:bottom-1 left-0.5 sm:left-1 text-[10px] sm:text-xs text-gray-500 hover:text-gray-700 hover:underline z-10"
                        >
                          +{hiddenIssues.length}
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>

              <div
                className="absolute left-0 right-0 pointer-events-none overflow-hidden top-[32px] sm:top-[48px]"
                style={{ height: `${maxVisibleRows * issueRowHeight}px` }}
              >
                {weekIssues
                  .filter((wi) => wi.row < maxVisibleRows)
                  .map((wi) => (
                    <IssueBar
                      key={`${wi.issue.id}-${wi.row}`}
                      weekIssue={wi}
                      issueRowHeight={issueRowHeight}
                      onClick={() => navigate(`/issues/${wi.issue.id}`)}
                    />
                  ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* More 팝업 */}
      {morePopup && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setMorePopup(null)} />
          <div
            className="fixed z-50 bg-white border border-gray-200 rounded-lg shadow-lg p-3 w-[calc(100vw-32px)] sm:w-auto sm:max-w-xs left-4 sm:left-auto right-4 sm:right-auto"
            style={{
              ...(window.innerWidth >= 640 && {
                left: Math.min(morePopup.position.x, window.innerWidth - 300),
              }),
              top: Math.min(morePopup.position.y, window.innerHeight - 320),
              maxHeight: '280px',
              overflowY: 'auto',
            }}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">
                {format(morePopup.date, 'M월 d일', { locale: ko })} (+{morePopup.issues.length})
              </span>
              <button onClick={() => setMorePopup(null)} className="text-gray-400 hover:text-gray-600">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="space-y-1.5">
              {morePopup.issues.map((issue) => {
                const colors = getCategoryColors(issue.category);
                return (
                  <div
                    key={issue.id}
                    onClick={() => {
                      setMorePopup(null);
                      navigate(`/issues/${issue.id}`);
                    }}
                    className={`${colors.bg} ${colors.text} text-xs px-2 py-1.5 rounded cursor-pointer hover:opacity-80 transition-opacity truncate`}
                    title={issue.name}
                  >
                    {issue.name}
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
