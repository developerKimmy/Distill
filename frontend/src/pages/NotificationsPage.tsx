import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useNotifications, useMarkAsRead, useMarkAllAsRead } from '../hooks';
import type { Notification } from '../types';

const getNotificationIcon = (type: string) => {
  switch (type) {
    case 'article_surge':
      return '📈';
    case 'followed_update':
      return '🔔';
    case 'new_issue':
      return '🆕';
    default:
      return '📌';
  }
};

const getRelativeTime = (dateStr: string) => {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMins < 1) return '방금 전';
  if (diffMins < 60) return `${diffMins}분 전`;
  if (diffHours < 24) return `${diffHours}시간 전`;
  if (diffDays < 7) return `${diffDays}일 전`;
  return date.toLocaleDateString('ko-KR');
};

function NotificationItem({
  notification,
  onMarkAsRead,
}: {
  notification: Notification;
  onMarkAsRead: (id: string) => void;
}) {
  const handleClick = () => {
    if (!notification.isRead) {
      onMarkAsRead(notification.id);
    }
  };

  return (
    <div
      onClick={handleClick}
      className={`p-4 border-b border-gray-100 cursor-pointer transition-colors ${
        notification.isRead ? 'bg-white' : 'bg-amber-50 hover:bg-amber-100'
      }`}
    >
      <div className="flex items-start gap-3">
        <span className="text-xl">{getNotificationIcon(notification.type)}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-gray-900 truncate">{notification.title}</span>
            {!notification.isRead && (
              <span className="flex-shrink-0 w-2 h-2 bg-red-500 rounded-full" />
            )}
          </div>
          {notification.message && (
            <p className="text-sm text-gray-600 line-clamp-2">{notification.message}</p>
          )}
          <div className="flex items-center gap-2 mt-2">
            <span className="text-xs text-gray-400">{getRelativeTime(notification.createdAt)}</span>
            {notification.issueId && notification.issueName && (
              <Link
                to={`/issues/${notification.issueId}`}
                onClick={(e) => e.stopPropagation()}
                className="text-xs text-amber-600 hover:text-amber-700"
              >
                {notification.issueName} →
              </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function NotificationsPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading, error } = useNotifications(page, 20);
  const markAsRead = useMarkAsRead();
  const markAllAsRead = useMarkAllAsRead();

  const handleMarkAsRead = (id: string) => {
    markAsRead.mutate(id);
  };

  const handleMarkAllAsRead = () => {
    markAllAsRead.mutate();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12 text-gray-500">
        알림을 불러오는데 실패했습니다.
      </div>
    );
  }

  const { notifications, total, unreadCount } = data ?? {
    notifications: [],
    total: 0,
    unreadCount: 0,
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-gray-900">
          알림
          {unreadCount > 0 && (
            <span className="ml-2 text-sm font-normal text-gray-500">
              ({unreadCount}개 안 읽음)
            </span>
          )}
        </h1>
        {unreadCount > 0 && (
          <button
            onClick={handleMarkAllAsRead}
            disabled={markAllAsRead.isPending}
            className="text-sm text-amber-600 hover:text-amber-700 disabled:opacity-50"
          >
            모두 읽음 처리
          </button>
        )}
      </div>

      {notifications.length === 0 ? (
        <div className="text-center py-12 text-gray-500 bg-white rounded-lg border border-gray-200">
          <svg
            className="w-12 h-12 mx-auto mb-4 text-gray-300"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
            />
          </svg>
          새로운 알림이 없습니다.
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          {notifications.map((notification) => (
            <NotificationItem
              key={notification.id}
              notification={notification}
              onMarkAsRead={handleMarkAsRead}
            />
          ))}
        </div>
      )}

      {/* 페이지네이션 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-6">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1 text-sm border rounded disabled:opacity-50"
          >
            이전
          </button>
          <span className="text-sm text-gray-600">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1 text-sm border rounded disabled:opacity-50"
          >
            다음
          </button>
        </div>
      )}
    </div>
  );
}
