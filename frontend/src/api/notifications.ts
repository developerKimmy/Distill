import client from './client';
import type { NotificationListResponse } from '../types';

// 알림 목록 조회
export const getNotifications = async (
  page = 1,
  size = 20,
  unreadOnly = false
): Promise<NotificationListResponse> => {
  const { data } = await client.get('/notifications', {
    params: { page, size, unread_only: unreadOnly },
  });
  return data;
};

// 읽지 않은 알림 개수
export const getUnreadCount = async (): Promise<{ count: number }> => {
  const { data } = await client.get('/notifications/unread-count');
  return data;
};

// 알림 읽음 처리
export const markAsRead = async (notificationId: string): Promise<{ success: boolean }> => {
  const { data } = await client.put(`/notifications/${notificationId}/read`);
  return data;
};

// 모든 알림 읽음 처리
export const markAllAsRead = async (): Promise<{ success: boolean }> => {
  const { data } = await client.put('/notifications/read-all');
  return data;
};
